"""Minimalist symbol collector and type checker for MISE 2."""
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from .ast_nodes import *
from .parser import parse_source

OBJECT_KINDS = frozenset({"obj", "room", "door", "story", "ending", "talk"})
ROOM_KINDS = frozenset({"room", "story", "ending", "cutscene", "gameover"})
_SLOT_OBJ_RE = re.compile(r"\{(?:noun|noun_obj|compass\w*)\}")


@dataclass
class Context:
    lang: str = "ru"
    enums: Dict[str, Tuple[Set[str], bool]] = field(default_factory=dict)  # name -> (values, negate)
    enum_owner: Dict[str, Set[str]] = field(default_factory=dict)
    event_names: Set[str] = field(default_factory=set)
    event_args: Dict[str, List[str]] = field(default_factory=dict)
    life_args: Dict[str, List[str]] = field(default_factory=dict)

    classes: Dict[str, str] = field(default_factory=dict)                  # class -> parent
    class_decls: Dict[str, EntityDecl] = field(default_factory=dict)
    objects: Dict[str, str] = field(default_factory=dict)                  # id -> kind/class
    fields: Dict[str, Dict[str, Tuple[str, bool]]] = field(default_factory=dict)
    ref_fields: Set[str] = field(default_factory=lambda: {"with", "found_in", "scope"})

    extern_props: Dict[str, FnDecl] = field(default_factory=dict)
    fns: Dict[str, FnDecl] = field(default_factory=dict)
    used_refs: Set[str] = field(default_factory=set)
    lua_funcs: Set[str] = field(default_factory=set)
    globals: Dict[str, Tuple[str, bool]] = field(default_factory=dict)


def split_union(t: str) -> List[str]:
    t = t.strip()
    if t.endswith("?"):
        return [p for p in split_union(t[:-1]) if p != "nil"] + ["nil"]
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(t):
        depth += (1 if ch in "([" else -1 if ch in ")]" else 0)
        if ch == "|" and depth == 0:
            parts.append(t[start:i].strip())
            start = i + 1
    parts.append(t[start:].strip())
    res, has_nil = [], False
    for p in parts:
        if p == "nil":
            has_nil = True
        elif p.endswith("?"):
            has_nil = True
            if p[:-1] not in res:
                res.append(p[:-1])
        elif p and p not in res:
            res.append(p)
    return res + (["nil"] if has_nil else [])


def canon_type(t: str) -> str:
    parts = split_union(t)
    non_nil = sorted(p for p in parts if p != "nil")
    return ("|".join(non_nil) + ("?" if "nil" in parts else "")) if non_nil else "nil"


def strip_nil(t: str) -> str:
    non_nil = sorted(p for p in split_union(t) if p != "nil")
    return "|".join(non_nil) if non_nil else "nil"


def tbl_inner(t: str) -> Optional[str]:
    return t[4:-1] if (t.startswith("tbl[") and t.endswith("]")) else None


def load_includes(prog: Program, src_dir: str) -> Program:
    if not prog.includes:
        return prog
    std_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    merged = []
    for inc in prog.includes:
        paths = []
        for d in (src_dir, std_dir):
            if d and os.path.isfile(os.path.join(d, f"{inc}.mise")):
                paths.append(os.path.join(d, f"{inc}.mise"))
                lp = os.path.join(d, f"{inc}-{prog.lang}.mise")
                if os.path.isfile(lp):
                    paths.append(lp)
                break
        if not paths:
            raise Error(f"include file not found: {inc!r}")
        for p in paths:
            with open(p, "r", encoding="utf-8") as f:
                merged.extend(parse_source(f.read(), os.path.basename(p)).items)
    prog.items = merged + prog.items
    return prog


def _verb_pat_sig(pat: str) -> Optional[Tuple[str, List[str]]]:
    if ":" not in pat:
        return None
    lhs, rhs = pat.rsplit(":", 1)
    ev_parts = rhs.strip().split()
    if not ev_parts:
        return None
    toks = lhs.strip().split()
    if toks and toks[0] == "~":
        toks = toks[1:]
    slots = ["obj" if _SLOT_OBJ_RE.search(t) else "str" for t in toks if _SLOT_OBJ_RE.search(t) or t in ("*", "~*")]
    if len(ev_parts) > 1 and ev_parts[1] == "reverse" and len(slots) >= 2:
        slots[0], slots[1] = slots[1], slots[0]
    return ev_parts[0], slots


def prescan(prog: Program) -> Context:
    ctx = Context(lang=prog.lang)
    base_evs: Dict[str, List[str]] = {}

    for item in prog.items:
        if isinstance(item, TypeDecl):
            if item.name == "event":
                for life, evs, ats in item.event_sigs:
                    for ev in evs:
                        ctx.event_names.add(ev)
                        if life:
                            ctx.life_args[ev] = list(ats)
                        elif ats:
                            base_evs[ev] = list(ats)
            else:
                vals, neg = ctx.enums.get(item.name, (set(), False))
                vals.update(item.values)
                ctx.enums[item.name] = (vals, neg or item.negate)
                for v in item.values:
                    ctx.enum_owner.setdefault(v, set()).add(item.name)
        elif isinstance(item, FnDecl):
            if item.is_prop:
                ctx.extern_props[item.name] = item
            else:
                ctx.fns[item.name] = item
        elif isinstance(item, LuaDecl):
            for m in re.finditer(r"\bfunction\s+([A-Za-z_]\w*)", item.code):
                ctx.lua_funcs.add(m.group(1))
        elif isinstance(item, EntityDecl) and item.kind == "class" and item.name:
            ctx.classes[item.name] = item.parent or "obj"
            # Merge repeated `class obj`/`props obj` declarations
            if item.name in ctx.class_decls:
                ctx.class_decls[item.name].props.extend(item.props)
            else:
                ctx.class_decls[item.name] = item
            for p in item.props:
                if p.typ and any(k in p.typ for k in ("ref", "room", "door", "talk", "list")):
                    ctx.ref_fields.add(p.name)

    def register_entity(ent: EntityDecl):
        if ent.kind == "impl" and ent.name == "mp":
            ctx.event_names.update(ent.traits)
        # Expand traits that refer to classes/mixins with bodies
        exp_p, exp_h, kept_tr = [], [], []
        for tr in ent.traits:
            cdecl = ctx.class_decls.get(tr)
            if cdecl and ent.kind != "class" and tr not in ctx.enums.get("attr", (set(), False))[0]:
                # Only inline mixin-like classes if `ent.kind` is `obj` or another class
                pass
            if cdecl and not any(
                isinstance(it, EntityDecl) and it.kind == tr for it in prog.items
            ) and tr not in ("obj", "room", "door", "story", "ending", "option"):
                exp_p.extend(p for p in cdecl.props if p.value is not None)
                exp_h.extend(cdecl.handlers)
                kept_tr.extend(t for t in cdecl.traits if t not in kept_tr)
            else:
                kept_tr.append(tr)
        ent.traits = kept_tr
        own_p = {p.name for p in ent.props}
        own_h = {(h.phase, tuple(h.events)) for h in ent.handlers}
        ent.props = [p for p in exp_p if p.name not in own_p] + ent.props
        ent.handlers = [h for h in exp_h if (h.phase, tuple(h.events)) not in own_h] + ent.handlers

        if ent.kind not in ("class", "impl", "setup") and ent.name:
            ctx.objects[ent.name] = ent.kind
        for ch in ent.children:
            register_entity(ch)

    for item in prog.items:
        if isinstance(item, EntityDecl):
            register_entity(item)
        elif isinstance(item, TalkDecl):
            ctx.objects[item.name] = "talk"

    # Verb pattern signature inference
    active_verbs: Dict[str, List[Tuple[str, List[str]]]] = {}
    for item in prog.items:
        if isinstance(item, VerbDecl):
            tag = item.tag if item.tag is not None else (item.name if item.name.startswith("#") else f"#{item.name}")
            if item.mode == "remove":
                active_verbs.pop(tag, None)
            else:
                contribs = active_verbs.setdefault(tag, [])
                for pat in item.patterns:
                    ps = _verb_pat_sig(pat)
                    if ps:
                        ctx.event_names.add(ps[0])
                        contribs.append(ps)

    ctx.event_args = {k: list(v) for k, v in base_evs.items()}
    for contribs in active_verbs.values():
        for ev, slots in contribs:
            cur = ctx.event_args.get(ev)
            if cur is None:
                ctx.event_args[ev] = list(slots)
            else:
                ml = max(len(cur), len(slots))
                ctx.event_args[ev] = [
                    canon_type(f"{cur[i] if i < len(cur) else 'nil'}|{slots[i] if i < len(slots) else 'nil'}")
                    for i in range(ml)
                ]

    for item in prog.items:
        if isinstance(item, VarDecl):
            for vn, ve, _l in item.items:
                ctx.globals[vn] = _lit_type(ctx, ve)

    def collect_fields(ent: EntityDecl):
        fmap = ctx.fields.setdefault(ent.name, {}) if ent.name else {}
        base = ent.parent if ent.kind == "class" else ent.kind
        if base in ctx.fields:
            for k, v in ctx.fields[base].items():
                fmap.setdefault(k, v)
        for p in ent.props:
            if p.typ and any(k in p.typ for k in ("ref", "room", "door", "talk")):
                ctx.ref_fields.add(p.name)
            if p.value is not None and ent.name:
                fmap[p.name] = _lit_type(ctx, p.value) if isinstance(p.value, Expr) else ("fn", False)
            elif p.typ and ent.name:
                is_r = any(k in p.typ for k in ("ref", "room", "door", "talk"))
                fmap[p.name] = (p.typ, is_r)
        for ch in ent.children:
            collect_fields(ch)

    for item in prog.items:
        if isinstance(item, EntityDecl):
            collect_fields(item)

    for item in prog.items:
        if isinstance(item, EntityDecl):
            _check_refs(ctx, item)
        elif isinstance(item, VarDecl):
            for vn, ve, vl in item.items:
                _check_var_ref(ctx, vn, ve, vl)

    for item in prog.items:
        if isinstance(item, FnDecl) and not item.is_extern and isinstance(item.body, list):
            env = {pn: pt for pn, pt in item.params}
            owner = item.params[0][1] if (item.params and item.params[0][0] == "s" and item.params[0][1] in ctx.classes) else None
            rets: List[str] = []
            _check_stmts(ctx, item.body, env, owner, rets)
            if not item.ret_types:
                item.ret_types = [canon_type("|".join(rets))] if rets else ["any"]

    for item in prog.items:
        if isinstance(item, EntityDecl):
            _check_entity(ctx, item)
        elif isinstance(item, TalkDecl):
            _check_talk(ctx, item)

    return ctx


def _lit_type(ctx: Context, e: Expr) -> Tuple[str, bool]:
    if isinstance(e, Lit):
        return e.kind, False
    if isinstance(e, InterpStr):
        return "str", False
    if isinstance(e, Sym):
        if e.name in ctx.objects or e.name == "none":
            e.rk = "none" if e.name == "none" else "obj"
            return ctx.objects.get(e.name, "obj"), True
        if e.name in ctx.event_names:
            e.rk = "event"
            return "event", False
        owners = ctx.enum_owner.get(e.name.lstrip("~"))
        if owners:
            e.rk = "enum"
            return next(iter(owners)), False
    if isinstance(e, ListLit):
        return "tbl", False
    return "any", False


def _ref_error(ctx: Context, where: str, name: str, line: int):
    raise Error(f"{where}: unknown object reference {name!r}", line)


def _check_ref_name(ctx: Context, where: str, name: str, line: int):
    """A bare object name in a reference position must be declared."""
    if name != "none" and name not in ctx.objects:
        _ref_error(ctx, where, name, line)


def _check_ref_value(ctx: Context, where: str, val: Any, line: int = 0):
    """Validate a reference field value: a bare name or a list of them."""
    items = val.items if isinstance(val, ListLit) else [val]
    for it in items:
        if isinstance(it, Sym):
            _check_ref_name(ctx, where, it.name, it.line or line)
        elif isinstance(it, Lit) and it.kind == "str" and isinstance(val, ListLit):
            _check_ref_name(ctx, where, it.val.strip(), it.line or line)
        elif isinstance(it, Lit) or isinstance(it, ListLit) or isinstance(it, FnRef):
            continue  # raw/nil/bool/number/tables and handlers are not references
        else:
            raise Error(f"{where}: expected object reference, got expression", line)


def _check_refs(ctx: Context, ent: EntityDecl):
    """Validate reference values of every declaration, including nested ones."""
    for p in ent.props:
        if p.name not in ctx.ref_fields or p.value is None or isinstance(p.value, (list, FnRef)):
            continue
        where = f"{ent.name}.{p.name}" if ent.name else p.name
        if isinstance(p.value, Lit) and p.value.kind in ("raw", "num", "bool", "nil"):
            continue
        if isinstance(p.value, Lit) and p.value.kind == "str":
            raise Error(f"{where}: object reference must be a bare name, not a quoted string ({p.value.val!r})", p.line)
        _check_ref_value(ctx, where, p.value, p.line)
    for ref in ent.with_refs:
        where = f"{ent.name}.with" if ent.name else "with"
        _check_ref_name(ctx, where, ref, ent.line)
    for ch in ent.children:
        _check_refs(ctx, ch)


def _check_var_ref(ctx: Context, name: str, val: Expr, line: int):
    """A bare name as an initial value must be a declared object, event or enum value."""
    if not isinstance(val, Sym):
        return
    n = val.name
    if n == "none" or n in ctx.objects or n in ctx.event_names or n.lstrip("~") in ctx.enum_owner:
        return
    raise Error(f"{name}: unknown name {n!r}", line)


def _check_entity(ctx: Context, ent: EntityDecl):
    owner = ent.name
    kind = ent.kind if ent.kind != "impl" else ctx.objects.get(owner or "", "obj")
    for p in ent.props:
        if isinstance(p.value, FnRef):
            ctx.used_refs.add(p.value.name)
        elif isinstance(p.value, list):
            env = {"s": owner if (owner and owner in ctx.classes) else "obj", "load": "bool"}
            if p.name == "compass_look":
                env["to"] = "direction"
            elif p.name == "OnError":
                env["err"] = "str"
            elif p.name == "scope":
                env["w"] = "list"
            elif p.name in ("enter", "exit", "onenter", "onexit"):
                env["w"] = "obj"
            for pn in p.params or []:
                env.setdefault(pn, "any")
            _check_stmts(ctx, p.value, env, owner)
        elif isinstance(p.value, Expr):
            _check_expr(ctx, p.value, {"s": "obj"}, owner)
    for h in ent.handlers:
        if isinstance(h.body, FnRef):
            ctx.used_refs.add(h.body.name)
        elif isinstance(h.body, Expr):
            _check_expr(ctx, h.body, _h_env(ctx, owner, kind, h), owner, "str")
        elif isinstance(h.body, list):
            _check_stmts(ctx, h.body, _h_env(ctx, owner, kind, h), owner)
    for ch in ent.children:
        _check_entity(ctx, ch)


def _h_env(ctx: Context, owner: Optional[str], kind: str, h: Handler) -> Dict[str, str]:
    is_any = any(ev in ("Any", "Default") for ev in h.events)
    pnames = h.params if h.params is not None else (["s", "ev", "w", "wh"] if is_any else ["s", "w", "wh"])
    env = {pn: ("event" if (is_any and i == 1) else "obj") for i, pn in enumerate(pnames)}
    if len(h.events) == 1 and not is_any:
        ev = h.events[0]
        sigs = ctx.life_args.get(ev) if h.phase == "life" else ctx.event_args.get(ev)
        if sigs:
            room_like = kind in ROOM_KINDS or (kind in ctx.classes and ctx.classes.get(kind) in ROOM_KINDS) or owner in ("game", "mp", "setup", None)
            off = 1 if (room_like and h.phase != "life") else 0
            for idx, st in enumerate(sigs):
                if 0 < idx + off < len(pnames):
                    env[pnames[idx + off]] = st
    return env


def _check_talk(ctx: Context, td: TalkDecl):
    env = {"s": "obj"}
    if isinstance(td.intro, FnRef):
        ctx.used_refs.add(td.intro.name)
    elif isinstance(td.intro, list):
        _check_stmts(ctx, td.intro, dict(env), td.name)
    elif isinstance(td.intro, Expr):
        _check_expr(ctx, td.intro, dict(env), td.name)

    def chk_c(c: TalkChoice):
        for part in (c.cond, c.ask, c.reply, c.onempty, c.do_body):
            if isinstance(part, FnRef):
                ctx.used_refs.add(part.name)
            elif isinstance(part, list):
                _check_stmts(ctx, part, dict(env), td.name)
            elif isinstance(part, Expr):
                _check_expr(ctx, part, dict(env), td.name)
        for sub in c.children:
            chk_c(sub)

    for c in td.choices:
        chk_c(c)
    for _ln, lsay, lcs in td.labels:
        if isinstance(lsay, list):
            _check_stmts(ctx, lsay, dict(env), td.name)
        elif isinstance(lsay, Expr):
            _check_expr(ctx, lsay, dict(env), td.name)
        for c in lcs:
            chk_c(c)


def _narrow(ctx: Context, cond: Expr, env: Dict[str, str], truthy: bool) -> Dict[str, str]:
    res = dict(env)
    if isinstance(cond, Sym) and cond.name in res and truthy:
        res[cond.name] = strip_nil(res[cond.name])
    elif isinstance(cond, UnaryOp) and cond.op == "not":
        return _narrow(ctx, cond.operand, env, not truthy)
    elif isinstance(cond, BinOp):
        if cond.op == "and" and truthy:
            return _narrow(ctx, cond.right, _narrow(ctx, cond.left, env, True), True)
        if cond.op == "==" and truthy and isinstance(cond.left, Sym) and cond.left.name in ("ev", "event") and isinstance(cond.right, Sym):
            sigs = ctx.event_args.get(cond.right.name)
            if sigs and "w" in res and len(sigs) >= 2:
                res["w"] = sigs[1]
    return res


def _check_stmts(ctx: Context, stmts: List[Stmt], env: Dict[str, str], owner: Optional[str] = None, rets: Optional[List[str]] = None):
    for s in stmts:
        if isinstance(s, SayStmt):
            _check_expr(ctx, s.expr, env, owner, "str")
        elif isinstance(s, ReturnStmt):
            for v in s.values:
                t = _check_expr(ctx, v, env, owner)
                if rets is not None and t != "nil":
                    rets.append(t)
        elif isinstance(s, LocalStmt):
            vts = [_check_expr(ctx, v, env, owner) for v in s.values]
            for i, (vn, dt) in enumerate(s.names):
                env[vn] = dt or (vts[i] if i < len(vts) else "any")
        elif isinstance(s, AssignStmt):
            _check_expr(ctx, s.target, env, owner, is_lhs=True)
            for v in s.values:
                vt = _check_expr(ctx, v, env, owner)
                if isinstance(s.target, Sym) and env.get(s.target.name) == "any":
                    env[s.target.name] = vt
        elif isinstance(s, CallStmt):
            _check_call(ctx, s.call, env, owner)
        elif isinstance(s, IfStmt):
            cenv = dict(env)
            for cond, body, _l in s.branches:
                _check_expr(ctx, cond, cenv, owner)
                _check_stmts(ctx, body, _narrow(ctx, cond, cenv, True), owner, rets)
                cenv = _narrow(ctx, cond, cenv, False)
            if s.else_body is not None:
                _check_stmts(ctx, s.else_body, cenv, owner, rets)
        elif isinstance(s, MatchStmt):
            st = _check_expr(ctx, s.subject, env, owner)
            for pats, guard, body, _l in s.arms:
                aenv = dict(env)
                for p in pats:
                    if not (isinstance(p, Sym) and p.name == "_"):
                        _check_expr(ctx, p, env, owner, st)
                if guard:
                    _check_expr(ctx, guard, aenv, owner)
                _check_stmts(ctx, body, aenv, owner, rets)
        elif isinstance(s, ForNumStmt):
            _check_expr(ctx, s.start, env, owner, "num")
            _check_expr(ctx, s.stop, env, owner, "num")
            if s.step:
                _check_expr(ctx, s.step, env, owner, "num")
            benv = dict(env)
            benv[s.var] = s.var_type or "num"
            _check_stmts(ctx, s.body, benv, owner, rets)
        elif isinstance(s, ForInStmt):
            it = _check_expr(ctx, s.iter_expr, env, owner)
            el = tbl_inner(it) or ("obj" if it == "list" else "any")
            benv = dict(env)
            for i, (vn, vt) in enumerate(s.vars):
                benv[vn] = vt or ("num" if (s.is_of and len(s.vars) == 2 and i == 0) else el)
            _check_stmts(ctx, s.body, benv, owner, rets)


def _check_expr(ctx: Context, e: Expr, env: Dict[str, str], owner: Optional[str] = None, expected: Optional[str] = None, is_lhs: bool = False) -> str:
    if isinstance(e, Lit):
        e.typ = e.kind
        return e.kind
    if isinstance(e, InterpStr):
        for p in e.parts:
            if isinstance(p, Expr):
                _check_expr(ctx, p, env, owner)
        e.typ = "str"
        return "str"
    if isinstance(e, FnRef):
        ctx.used_refs.add(e.name)
        e.typ = "fn"
        return "fn"
    if isinstance(e, ListLit):
        in_exp = tbl_inner(expected) if expected else None
        its = [_check_expr(ctx, it, env, owner, in_exp) for it in e.items]
        e.typ = f"tbl[{canon_type('|'.join(its)) if its else ''}]"
        return e.typ
    if isinstance(e, Sym):
        n = e.name
        if n == "none":
            e.rk, e.typ = "none", "obj"
            return "obj"
        if n in env:
            e.rk, e.typ = "var", env[n]
            return e.typ
        if expected:
            exps = split_union(expected)
            if "event" in exps and n in ctx.event_names:
                e.rk, e.typ = "event", "event"
                return "event"
            for ea in exps:
                if ea in ctx.enums:
                    vals, neg = ctx.enums[ea]
                    if (n[1:] if (n.startswith("~") and neg) else n) in vals:
                        e.rk, e.typ = "enum", ea
                        return ea
        if n in ctx.objects:
            e.rk, e.typ = "obj", ctx.objects[n]
            return e.typ
        if n in ctx.extern_props:
            e.rk, e.typ = "prop", ctx.extern_props[n].ret_types[0]
            return e.typ
        if n in ctx.globals:
            gt, is_r = ctx.globals[n]
            e.rk, e.typ = ("global_ref" if is_r else "global"), gt
            return gt
        if n in ctx.classes:
            e.rk, e.typ = "enum", "str"
            return "str"
        if n in ctx.event_names:
            e.rk, e.typ = "event", "event"
            return "event"
        owners = ctx.enum_owner.get(n.lstrip("~"))
        if owners:
            e.rk, e.typ = "enum", next(iter(owners))
            return e.typ
        if n in ctx.fns:
            e.rk = "fn0"
            e.typ = ctx.fns[n].ret_types[0] if ctx.fns[n].ret_types else "any"
            return e.typ
        e.rk, e.typ = "var", "any"
        return "any"
    if isinstance(e, FieldAccess):
        _check_expr(ctx, e.obj, env, owner)
        t_owner = None
        if isinstance(e.obj, Sym):
            t_owner = owner if (e.obj.name == "s" and owner) else (e.obj.name if e.obj.name in ctx.objects else (e.obj.typ if e.obj.typ in ctx.classes else None))
        if t_owner and e.field in ctx.fields.get(t_owner, {}):
            ft, is_r = ctx.fields[t_owner][e.field]
            e.is_ref, e.typ = (is_r and not is_lhs), ft
            return ft
        if e.field in ctx.ref_fields:
            e.is_ref, e.typ = not is_lhs, "obj"
            return "obj"
        e.typ = "any"
        return "any"
    if isinstance(e, IndexAccess):
        ot = _check_expr(ctx, e.obj, env, owner)
        _check_expr(ctx, e.index, env, owner)
        e.typ = tbl_inner(ot) or ("obj" if ot == "list" else "any")
        return e.typ
    if isinstance(e, UnaryOp):
        _check_expr(ctx, e.operand, env, owner)
        e.typ = "bool" if e.op == "not" else "num"
        return e.typ
    if isinstance(e, BinOp):
        lt = _check_expr(ctx, e.left, env, owner)
        rt = _check_expr(ctx, e.right, env, owner, lt if e.op in ("==", "!=") else None)
        e.typ = "bool" if e.op in ("==", "!=", "<", "<=", ">", ">=") else ("str" if e.op == ".." else ("num" if e.op in ("+", "-", "*", "/", "%", "//") else rt))
        return e.typ
    if isinstance(e, Call):
        return _check_call(ctx, e, env, owner)
    return "any"


def _check_call(ctx: Context, c: Call, env: Dict[str, str], owner: Optional[str] = None) -> str:
    if c.callee:
        _check_expr(ctx, c.callee, env, owner)
        for a in c.args:
            _check_expr(ctx, a, env, owner)
        return "any"
    fn = ctx.fns.get(c.func)
    all_args = ([c.receiver] + c.args) if c.receiver else list(c.args)
    for i, a in enumerate(all_args):
        exp = fn.params[i][1] if (fn and i < len(fn.params)) else (fn.variadic if fn else None)
        _check_expr(ctx, a, env, owner, exp)
    c.typ = fn.ret_types[0] if (fn and fn.ret_types) else "any"
    return c.typ
