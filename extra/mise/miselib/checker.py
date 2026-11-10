"""Minimalist symbol collector and type checker for MISE 2."""
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from .ast_nodes import *
from .parser import PHASES, parse_source

# the class that declares the compass fields (`n_to` ...) is the room-like root
_SLOT_OBJ_RE = re.compile(r"\{(?:noun|noun_obj|compass\w*)\}")
# names of the current event: the handler parameter and the engine accessor
CURRENT_EVENT = frozenset({"ev", "event"})
# engine fields the game must not assign (the engine owns them)
READONLY_FIELDS = frozenset({"nam"})


class TypeCheckError(Error):
    """A value cannot be used where its declared type is expected."""


@dataclass
class Context:
    lang: str = "ru"
    enums: Dict[str, Tuple[Set[str], bool]] = field(default_factory=dict)  # name -> (values, negate)
    enum_owner: Dict[str, Set[str]] = field(default_factory=dict)
    event_names: Set[str] = field(default_factory=set)
    event_args: Dict[str, List[str]] = field(default_factory=dict)
    event_acted: Set[str] = field(default_factory=set)   # the action takes an acted object

    classes: Dict[str, str] = field(default_factory=dict)                  # class -> parent
    class_decls: Dict[str, EntityDecl] = field(default_factory=dict)
    objects: Dict[str, str] = field(default_factory=dict)                  # id -> kind/class
    fields: Dict[str, Dict[str, Tuple[str, bool]]] = field(default_factory=dict)
    prop_types: Dict[str, Dict[str, str]] = field(default_factory=dict)  # declared field types
    prop_params: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)  # their fn param names
    prop_emit: Dict[str, Dict[str, Tuple[str, str, str, str]]] = field(default_factory=dict)  # method emission
    ctors: Dict[str, str] = field(default_factory=dict)                  # class -> engine constructor
    root_class: Optional[str] = None                                     # the first class with no parent
    seen_types: Set[str] = field(default_factory=set)
    field_names: Set[str] = field(default_factory=set)
    entries: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)  # engine entry points
    lua_globals: Dict[str, str] = field(default_factory=dict)     # `extern global` -> type
    globals_lua: Dict[str, str] = field(default_factory=dict)     # `extern global` -> template
    ref_fields: Set[str] = field(default_factory=set)   # fields whose declared type says "reference"

    fns: Dict[str, FnDecl] = field(default_factory=dict)
    fn_names: Set[str] = field(default_factory=set)
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


# --- Type compatibility -----------------------------------------------------

# type names that are part of the type language; object types are classes
PRIMITIVES = frozenset({"str", "num", "bool", "any", "event", "tbl", "nil", "ref"})


def _atom_fits(ctx: Context, actual: str, expected: str) -> bool:
    """Can a single (non-union) value type be used where `expected` is wanted?"""
    if expected == "any" or actual == expected:
        return True
    if actual == "any":
        return False  # `any` never silently narrows into a concrete type
    if expected == "ref":
        return _is_object_type(ctx, actual) or actual == "str"
    if expected in ctx.classes:
        cur, seen = actual, set()
        while cur in ctx.classes and cur not in seen:
            if cur == expected:
                return True
            seen.add(cur)
            cur = ctx.classes[cur]
        return False
    if expected == "str" and actual in ctx.enums:
        return True  # an enum value can be passed where a string is wanted
    if expected == "tbl":
        # an instance of a class is a Lua table as well
        return tbl_inner(actual) is not None or _is_object_type(ctx, actual)
    in_a, in_e = tbl_inner(actual), tbl_inner(expected)
    if in_a is not None and in_e is not None:
        return in_a == "" or is_subtype(ctx, in_a, in_e)
    if expected.startswith("fn") and (actual == "fn" or actual.startswith("fn(")):
        return True  # a Lua fn is opaque, callback bodies are not compared structurally
    return False


def is_subtype(ctx: Context, actual: str, expected: str) -> bool:
    """Does every alternative of `actual` fit some alternative of `expected`?"""
    if expected == "any" or actual == expected:
        return True
    return all(any(_atom_fits(ctx, a, e) for e in split_union(expected))
               for a in split_union(actual))


def _kind_name(expr: Expr) -> str:
    """A short human-readable description of an expression for diagnostics."""
    if isinstance(expr, Sym):
        return expr.name
    if isinstance(expr, Lit):
        if expr.kind == "raw":
            return "`lua`"
        if expr.kind == "table":
            return "{…}"
        return str(expr.val)
    if isinstance(expr, FieldAccess):
        return f"{_kind_name(expr.obj)}.{expr.field}"
    if isinstance(expr, Call):
        recv = f"{_kind_name(expr.receiver)}:" if expr.receiver is not None else ""
        return f"{recv}{expr.func or 'call'}()"
    return "expression"


def expect(ctx: Context, where: str, actual: str, expected: Optional[str], line: int = 0):
    """Report a type mismatch unless `actual` can be used as `expected`."""
    if not expected or expected == "any" or is_subtype(ctx, actual, expected):
        return
    if is_optional(actual) and not is_optional(expected):
        raise TypeCheckError(f"{where}: possible nil, narrow it first "
                             f"(`if {where}:`)", line)
    raise TypeCheckError(f"{where}: expected {expected}, got {actual}", line)


def _enum_value(ctx: Context, name: str, enum: str) -> Optional[str]:
    """Return `enum` if `name` (or `~name` for a negating enum) is one of its values."""
    vals, neg = ctx.enums.get(enum, (set(), False))
    bare = name[1:] if (name.startswith("~") and neg) else name
    return enum if bare in vals else None


def _enum_hint(ctx: Context, name: str) -> str:
    """` (did you mean 'light'?)` for a value of some declared enum."""
    import difflib
    candidates = sorted({v for vals, _neg in ctx.enums.values() for v in vals})
    near = difflib.get_close_matches(name.lstrip("~"), candidates, 1, 0.7)
    return f" (did you mean {near[0]!r}?)" if near else ""


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
                sub = parse_source(f.read(), os.path.basename(p))
            # an include may include others (`stdlib` includes `core`)
            sub = load_includes(sub, os.path.dirname(p))
            merged.extend(sub.items)
    prog.items = merged + prog.items
    return prog


def tool_name(name: str) -> str:
    return name.lstrip("#")


def _verb_pat_sig(pat: str, obj_type: str = "obj") -> Optional[Tuple[str, List[str], bool]]:
    if ":" not in pat:
        return None
    lhs, rhs = pat.rsplit(":", 1)
    ev_parts = rhs.strip().split()
    if not ev_parts:
        return None
    toks = lhs.strip().split()
    if toks and toks[0] == "~":
        toks = toks[1:]
    first = next((t for t in toks if _SLOT_OBJ_RE.search(t) or t in ("*", "~*")), "")
    acted = bool(_SLOT_OBJ_RE.search(first)) and not first.startswith("~")
    slots = [obj_type if _SLOT_OBJ_RE.search(t) else "str" for t in toks if _SLOT_OBJ_RE.search(t) or t in ("*", "~*")]
    if len(ev_parts) > 1 and ev_parts[1] == "reverse" and len(slots) >= 2:
        slots[0], slots[1] = slots[1], slots[0]
    return ev_parts[0], slots, acted


# engine print helpers and plain Lua functions callable from game logic
def prescan(prog: Program) -> Context:
    ctx = Context(lang=prog.lang)
    base_evs: Dict[str, List[str]] = {}

    for item in prog.items:
        if isinstance(item, EventsDecl):
            for evs, ats in item.sigs:
                for at in ats:
                    for alt in split_union(at):
                        if alt.rstrip("?").strip() in PRIMITIVES or alt.rstrip("?").strip() in ctx.enums \
                                or alt.rstrip("?").strip() in ctx.classes \
                                or alt.startswith(("obj", "str", "num", "bool")):
                            continue
                        raise Error(f"event {evs[0]}: unknown argument type {alt!r}", item.line)
                for ev in evs:
                    ctx.event_names.add(ev)
                    base_evs[ev] = list(ats)      # `[]` = the handler gets only `s`
        elif isinstance(item, TypeDecl):
            if item.extend and item.name not in ctx.enums:
                raise Error(f"extend type {item.name!r}: unknown type", item.line)
            if item.name in ctx.seen_types and not item.extend:
                raise Error(f"duplicate type {item.name!r}", item.line)
            ctx.seen_types.add(item.name)
            vals, neg = ctx.enums.get(item.name, (set(), False))
            vals.update(item.values)
            ctx.enums[item.name] = (vals, neg or item.negate)
            for v in item.values:
                ctx.enum_owner.setdefault(v, set()).add(item.name)
        elif isinstance(item, FnDecl):
            if item.name in ctx.fns:
                raise Error(f"duplicate fn {item.name!r}", item.line)
            ctx.fns[item.name] = item
        elif isinstance(item, EntryDecl):
            ctx.entries[item.name] = list(item.params)
        elif isinstance(item, GlobalDecl):
            ctx.lua_globals[item.name] = item.typ
            ctx.globals_lua[item.name] = item.template
        elif isinstance(item, LuaDecl):
            for m in re.finditer(r"\bfunction\s+([A-Za-z_]\w*)", item.code):
                ctx.lua_funcs.add(m.group(1))
        elif isinstance(item, EntityDecl) and item.kind == "class" and item.name:
            if item.ctor:
                ctx.ctors[item.name] = item.ctor
            prev = ctx.class_decls.get(item.name)
            if prev is not None and prev.parent and item.parent and prev.parent != item.parent:
                raise Error(f"class {item.name!r}: parent differs from an earlier declaration", item.line)
            if prev is None and item.parent:
                ctx.classes[item.name] = item.parent
            external = bool(item.ctor) and "." in item.ctor
            if item.parent is None and ctx.root_class is None and not external:
                ctx.root_class = item.name
            # a class without a parent extends the root class (as `Class(t)` does);
            # an external class (`std.list`) is a root of its own
            if external:
                ctx.classes.setdefault(item.name, item.name)
            else:
                ctx.classes.setdefault(item.name, item.parent or ctx.root_class or item.name)
            # Merge repeated `class obj`/`props obj` declarations
            if item.name in ctx.class_decls:
                ctx.class_decls[item.name].props.extend(item.props)
            else:
                ctx.class_decls[item.name] = item
            for p in item.props:
                if p.typ:
                    ctx.prop_types.setdefault(item.name, {})[p.name] = p.typ
                    if p.type_params:
                        ctx.prop_params.setdefault(item.name, {})[p.name] = p.type_params
                    if p.emit:
                        ctx.prop_emit.setdefault(item.name, {})[p.name] = p.emit
                if p.typ and _is_ref_type(ctx, p.typ):
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
            # inline the props/handlers of a class used as a trait (a mixin)
            if cdecl and not any(
                isinstance(it, EntityDecl) and it.kind == tr for it in prog.items
            ):
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

        if ent.kind not in ("class", "impl") and ent.name:
            if ent.kind not in ctx.classes:
                raise Error(f"unknown kind {ent.kind!r}{_kind_hint(ctx, ent)}", ent.line)
            if not ent.name.startswith("#") and ent.name in ctx.objects:
                raise Error(f"duplicate declaration {ent.name!r}", ent.line)
            ctx.objects[ent.name] = ent.kind
        if ent.kind == "impl" and ent.name and ent.name not in ("game", "pl", "mp") \
                and not ent.name.startswith("@") and ent.name not in ctx.objects \
                and ent.name not in ctx.classes and ent.name not in ctx.fns \
                and ent.name not in ctx.lua_funcs:
            raise Error(f"impl {ent.name!r}: unknown target", ent.line)
        for ch in ent.children:
            register_entity(ch)

    for item in prog.items:
        if isinstance(item, EntityDecl):
            register_entity(item)
        elif isinstance(item, TalkDecl):
            # a talk is an instance of the class `talk` (declared in core)
            ctx.objects[item.name] = "talk"
            ctx.field_names.update(p.name for p in item.props)

    # Verb pattern signature inference
    active_verbs: Dict[str, List[Tuple[str, List[str]]]] = {}
    for item in prog.items:
        if isinstance(item, VerbDecl):
            tag = item.tag if item.tag is not None else (item.name if item.name.startswith("#") else f"#{item.name}")
            if item.mode == "verb" and not item.patterns:
                raise Error(f"verb {item.name}: no patterns — the engine needs at least one "
                            f"(write `patterns = [\"{{noun}}/вн : {tool_name(item.name)}\"]`)", item.line)
            if item.mode == "remove":
                active_verbs.pop(tag, None)
            else:
                contribs = active_verbs.setdefault(tag, [])
                for pat in item.patterns:
                    ps = _verb_pat_sig(pat, _root(ctx))
                    if ps:
                        ctx.event_names.add(ps[0])
                        if ps[2]:
                            ctx.event_acted.add(ps[0])
                        contribs.append((ps[0], ps[1]))

    ctx.event_args = {k: list(v) for k, v in base_evs.items()}
    for ev, sigs in base_evs.items():
        first = sigs[0].rstrip("?").strip() if sigs else ""
        if first and (first.startswith("obj") or first in ctx.classes):
            ctx.event_acted.add(ev)       # a declared first argument is the acted object
    for contribs in active_verbs.values():
        for ev, slots in contribs:
            if ev in base_evs:          # declared in `type event`: that signature wins
                continue
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
        for p in ent.props:
            ctx.field_names.add(p.name)
        fmap = ctx.fields.setdefault(ent.name, {}) if ent.name else {}
        base = ent.parent if ent.kind == "class" else ent.kind
        if base in ctx.fields:
            for k, v in ctx.fields[base].items():
                fmap.setdefault(k, v)
        for p in ent.props:
            is_ref = bool(p.typ) and _is_ref_type(ctx, p.typ)
            if is_ref:
                ctx.ref_fields.add(p.name)
            if p.value is not None and ent.name:
                fmap[p.name] = _lit_type(ctx, p.value) if isinstance(p.value, Expr) else ("fn", False)
            elif p.typ and ent.name:
                fmap[p.name] = (p.typ, is_ref)
        for ch in ent.children:
            collect_fields(ch)

    for item in prog.items:
        if isinstance(item, EntityDecl):
            collect_fields(item)

    for item in prog.items:
        if isinstance(item, EntityDecl):
            _check_refs(ctx, item)
            _check_override(ctx, item)
        elif isinstance(item, VarDecl):
            for vn, ve, vl in item.items:
                _check_var_ref(ctx, vn, ve, vl)

    for item in prog.items:
        if isinstance(item, FnDecl) and item.name in ctx.entries:
            want = ctx.entries[item.name]
            got = [pt for _pn, pt in item.params]
            if len(got) != len(want):
                raise Error(f"entry {item.name}: the engine calls it with "
                            f"{len(want)} argument(s), declared {len(got)}", item.line)
    for item in prog.items:
        if isinstance(item, FnDecl):
            _check_signature(ctx, item)
        if isinstance(item, FnDecl) and not item.is_extern and isinstance(item.body, list):
            env = {pn: pt for pn, pt in item.params}
            owner = item.params[0][1] if (item.params and item.params[0][0] == "s" and item.params[0][1] in ctx.classes) else None
            rets: List[str] = []
            _check_stmts(ctx, item.body, env, owner, rets)
            if item.ret_types:
                _check_returns(ctx, item, env, owner)
            else:
                item.ret_types = [canon_type("|".join(rets))] if rets else ["any"]

    for item in prog.items:
        if isinstance(item, EntityDecl):
            _check_entity(ctx, item)
        elif isinstance(item, TalkDecl):
            _check_talk(ctx, item)

    return ctx


def _lit_type(ctx: Context, e: Expr) -> Tuple[str, bool]:
    if isinstance(e, Lit):
        return ("any" if e.kind == "raw" else e.kind), False
    if isinstance(e, InterpStr):
        return "str", False
    if isinstance(e, Sym):
        if e.name in ctx.objects:
            e.rk = "obj"
            return ctx.objects[e.name], True
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
    if name not in ctx.objects:
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
        if isinstance(p.value, Lit) and p.value.kind in ("raw", "lua", "num", "bool", "nil"):
            continue
        if isinstance(p.value, Lit) and p.value.kind == "str":
            raise Error(f"{where}: object reference must be a bare name, not a quoted string ({p.value.val!r})", p.line)
        _check_ref_value(ctx, where, p.value, p.line)
    for ch in ent.children:
        _check_refs(ctx, ch)


def _check_var_ref(ctx: Context, name: str, val: Expr, line: int):
    """A bare name as an initial value must be a declared object, event or enum value."""
    if not isinstance(val, Sym):
        return
    n = val.name
    if n in ctx.objects or n in ctx.event_names or n.lstrip("~") in ctx.enum_owner:
        return
    raise Error(f"{name}: unknown name {n!r}", line)


def _is_ref_type(ctx: Context, typ: str) -> bool:
    """Does this declared type hold object references (a name or an object)?"""
    for alt in split_union(typ):
        alt = alt.rstrip("?").strip()
        if alt == "ref" or _is_object_type(ctx, alt):
            return True
        inner = tbl_inner(alt)
        if inner is not None and (inner == "ref" or _is_object_type(ctx, inner)):
            return True
    return False


def _kind_hint(ctx: Context, ent: EntityDecl) -> str:
    """A hint for a mistyped kind or a member written without '='."""
    import difflib
    phase = difflib.get_close_matches(ent.kind, sorted(PHASES), 1, 0.75)
    if phase and ent.name in ctx.event_names:
        return f" (did you mean `{phase[0]} {ent.name}`?)"
    if ent.kind in ctx.field_names or any(ent.kind in d for d in ctx.prop_types.values()):
        return f" (did you mean `{ent.kind} = ...`?)"
    near = difflib.get_close_matches(ent.kind, sorted(ctx.classes), 1, 0.75)
    return f" (did you mean class {near[0]!r}?)" if near else ""


def _prop_body_env(ctx: Context, kind: str, p: Prop) -> Dict[str, str]:
    """Parameters of a prop body, taken from the declared `fn(...)` of the field."""
    typ = _decl_type(ctx, kind, p.name) or ""
    names: List[str] = []
    cur = kind
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        names = ctx.prop_params.get(cur, {}).get(p.name, names)
        if names:
            break
        cur = ctx.classes.get(cur)
    params: List[str] = []
    for alt in split_union(typ):
        parts = _fn_parts(alt)
        if parts:
            params = parts[0]
            break
    env: Dict[str, str] = {}
    for i, t in enumerate(params):
        env[names[i] if i < len(names) and names[i] else f"_{i}"] = t
    env.setdefault("s", _root(ctx))
    for pn in p.params or []:
        env.setdefault(pn, "any")
    return env


def _decl_emit(ctx: Context, kind: str, name: str) -> Optional[Tuple[str, str, str, str]]:
    """How the declared field reaches Lua (`= method attr(join)`)."""
    cur, seen = kind, set()
    while cur and cur not in seen:
        seen.add(cur)
        spec = ctx.prop_emit.get(cur, {}).get(name)
        if spec:
            return spec
        cur = ctx.classes.get(cur)
    return None


def _check_emit(ctx: Context, where: str, emit: Tuple[str, str, str, str], value: Any, line: int):
    """A method-emitted field takes the value shape its form needs."""
    _k, mname, form, _other = emit
    if form == "none":
        if not (isinstance(value, Lit) and value.kind == "bool"):
            raise TypeCheckError(f"{where}: `:{mname}()` takes a `true`/`false` value", line)
    elif form == "table":
        if not (isinstance(value, Lit) and value.kind == "table"):
            raise TypeCheckError(f"{where}: `:{mname}{{...}}` takes a `{{ ... }}` table", line)


def _decl_type(ctx: Context, kind: str, name: str) -> Optional[str]:
    """The declared type of a field, looked up through the class chain of `kind`."""
    cur, seen = kind, set()
    while cur and cur not in seen:
        seen.add(cur)
        t = ctx.prop_types.get(cur, {}).get(name)
        if t:
            return t
        cur = ctx.classes.get(cur)
    return None


def _fn_returns(declared: str) -> List[str]:
    """Return types of the `fn(...) -> T` alternatives of a declared type."""
    res = []
    for alt in split_union(declared):
        if alt.startswith("fn(") and "->" in alt:
            rets = alt.split("->", 1)[1].rstrip("?")
            res.extend(r.strip() for r in rets.split(",") if r.strip())
    return res


def _check_entity(ctx: Context, ent: EntityDecl):
    owner = ent.name
    kind = ent.name if ent.kind == "class" else (
        ent.kind if ent.kind != "impl" else ctx.objects.get(owner or "", _root(ctx)))
    for p in ent.props:
        where = f"{owner}.{p.name}" if owner else p.name
        declared = _decl_type(ctx, kind, p.name) if kind else None
        if isinstance(p.value, FnRef):
            ctx.used_refs.add(p.value.name)
        elif isinstance(p.value, list):
            env = _prop_body_env(ctx, kind, p)
            env["load"] = "bool"
            if declared is not None and "fn(" not in declared:
                raise TypeCheckError(f"{where}: expected {declared}, got a block "
                                     f"(a block is a function)", p.line)
            rets: List[str] = []
            _check_stmts(ctx, p.value, env, owner, rets)
            want = _fn_returns(declared) if declared else []
            for t in rets:
                if want and not any(is_subtype(ctx, t, w) for w in want):
                    raise TypeCheckError(f"{where}: return {t}, declared returns "
                                         f"{', '.join(want)}", p.line)
        elif isinstance(p.value, Lit) and p.value.kind == "lua":
            pass  # a `lua` block: an opaque body
        elif isinstance(p.value, Expr):
            _check_expr(ctx, p.value, {"s": _root(ctx)}, owner, declared)
        emit = _decl_emit(ctx, kind, p.name) if kind else None
        if emit and p.value is not None:
            _check_emit(ctx, where, emit, p.value, p.line)
    for h in ent.handlers:
        _check_handler_events(ctx, h, owner or kind)
        params, arg_names = _handler_params(ctx, owner, kind, h)
        if isinstance(h.body, FnRef):
            ctx.used_refs.add(h.body.name)
            sig = "fn(" + ",".join(t for _n, t in params) + ")"
            _check_fnref(ctx, h.body, sig, f"{owner or kind}: {h.phase} {','.join(h.events)}")
        elif isinstance(h.body, list):
            _check_stmts(ctx, h.body, dict(params), owner, None, arg_names)
        elif isinstance(h.body, Expr):
            # a handler holds a string, a boolean or a function (as the engine allows)
            _check_expr(ctx, h.body, dict(params), owner, "str|bool|fn")
    for ch in ent.children:
        _check_entity(ctx, ch)


# Names of a handler's parameters, in order: `s`, then the arguments.
HANDLER_PARAMS = ("s", "w", "wh", "w2", "w3")


def _handler_event_args(ctx: Context, h: Handler) -> List[str]:
    """The event's arguments, merged over the handler's events."""
    per = [list(ctx.event_args.get(ev) or []) for ev in h.events]
    n = max((len(x) for x in per), default=0)
    out: List[str] = []
    for i in range(n):
        ts = [x[i] for x in per if i < len(x)]
        t = canon_type("|".join(dict.fromkeys(ts)))
        if any(i >= len(x) for x in per) and not t.endswith("?"):
            t += "?"                # only some of the events pass this argument
        out.append(t)
    return out


def _handler_params(ctx: Context, owner: Optional[str], kind: str, h: Handler
                    ) -> Tuple[List[Tuple[str, str]], Dict[int, str]]:
    """What a handler receives, and which parameter name each event argument has.

    The engine calls a handler as `(receiver, *action_args)`; when the receiver is
    the acted object itself the object is stripped from the arguments, otherwise
    it is passed as the first argument (named `w`).
    """
    self_t = (ctx.objects.get(owner) if owner else None) or kind
    if self_t not in ctx.classes and self_t not in ctx.objects:
        self_t = _root(ctx)
    params: List[Tuple[str, str]] = [("s", self_t)]
    arg_names: Dict[int, str] = {}
    is_any = any(ev in ("Any", "Default") for ev in h.events)
    if is_any:                      # `before_Default(s, ev, w, wh)` and `before_Any(...)`
        params += [("ev", "event"), ("w", _root(ctx)), ("wh", _root(ctx))]
        stripped = not (_inherits(ctx, kind, _room_root(ctx)) or owner in ("game", "mp", "setup", None))
        # the arguments follow `ev`; on the acted object the object itself is stripped
        names = ("w", "wh", "w2", "w3")
        if stripped:
            return params, {i: names[i - 1] for i in range(1, len(names) + 1)}
        return params, {i: names[i] for i in range(len(names))}
    sigs = _handler_event_args(ctx, h)
    acted = bool(sigs) and any(ev in ctx.event_acted for ev in h.events)
    room_like = _inherits(ctx, kind, _room_root(ctx)) or owner in ("game", "mp", "setup", None)
    stripped = acted and not room_like
    if acted and not stripped:      # the acted object comes in as `w`
        params.append(("w", _root(ctx)))
        arg_names[0] = "w"
    for i, st in enumerate(sigs[1:] if acted else sigs, start=1 if acted else 0):
        name = HANDLER_PARAMS[len(params)]
        params.append((name, st))
        arg_names[i] = name
    if h.params is not None:                      # the handler names its own
        if len(h.params) > len(params):
            raise Error(f"{h.phase} {','.join(h.events)}: the engine passes "
                        f"{len(params)} parameter(s) here, the handler declares {len(h.params)}",
                        h.line)
        params = [(h.params[i], params[i][1]) for i in range(len(h.params))]
    return params, arg_names


def _h_env(ctx: Context, owner: Optional[str], kind: str, h: Handler) -> Dict[str, str]:
    return dict(_handler_params(ctx, owner, kind, h)[0])


def _check_talk(ctx: Context, td: TalkDecl):
    env = {"s": _root(ctx)}
    labels = [ln for ln, _say, _ch in td.labels]
    for ln in labels:
        if labels.count(ln) > 1:
            raise Error(f"talk {td.name}: duplicate label {ln!r}", td.line)

    def check_next(c: TalkChoice):
        if c.next_label and c.next_label not in labels:
            raise Error(f"talk {td.name}: unknown label {c.next_label!r} "
                        f"in `next`/`->`", c.line)
        for sub in c.children:
            check_next(sub)

    for c in td.choices:
        check_next(c)
    for _ln, _say, chs in td.labels:
        for c in chs:
            check_next(c)
    if isinstance(td.intro, FnRef):
        ctx.used_refs.add(td.intro.name)
    elif isinstance(td.intro, list):
        _check_stmts(ctx, td.intro, dict(env), td.name)
    elif isinstance(td.intro, Expr):
        _check_expr(ctx, td.intro, dict(env), td.name)

    def chk_c(c: TalkChoice):
        # a condition is a truthiness test (like `if`), no type check there
        for part, want in ((c.cond, None), (c.ask, "str"), (c.reply, "str"),
                           (c.onempty, "fn"), (c.do_body, "fn")):
            if isinstance(part, FnRef):
                ctx.used_refs.add(part.name)
            elif isinstance(part, list):
                rets: List[str] = []
                _check_stmts(ctx, part, dict(env), td.name, rets)
                if want == "str":
                    for t in rets:
                        expect(ctx, f"talk {td.name}: phrase text", t, "str", c.line)
            elif isinstance(part, Expr):
                _check_expr(ctx, part, dict(env), td.name,
                            None if want == "fn" else want)
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


def _nonnil(ctx: Context, e: Expr) -> bool:
    """Is this expression known to be a value, never nil?"""
    if isinstance(e, Lit):
        return e.kind != "nil"
    if isinstance(e, Sym):
        return (e.name in ctx.objects or e.name in ctx.event_names
                or bool(ctx.enum_owner.get(e.name.lstrip("~"))))
    # a call or a field may well be nil, a list literal never is
    return isinstance(e, (ListLit, InterpStr))


def _narrow(ctx: Context, cond: Expr, env: Dict[str, str], truthy: bool,
            arg_names: Optional[Dict[int, str]] = None) -> Dict[str, str]:
    """Refine optional types inside a branch of `if`/`when`/`match`.

    Handled conditions: `x`, `not x`, `x != nil` / `x == nil`, `a and b`,
    `a or b` (short circuit) and `ev == Event` (event argument narrowing).
    """
    res = dict(env)
    if isinstance(cond, Bind) and truthy:
        vt = cond.vtyp or "any"
        for n in cond.names:
            res[n] = strip_nil(vt) if vt != "any" else "any"
        return res
    if isinstance(cond, Sym) and cond.name in res:
        if truthy:
            res[cond.name] = strip_nil(res[cond.name])
        else:
            res[cond.name] = "nil"
    elif isinstance(cond, UnaryOp) and cond.op == "not":
        return _narrow(ctx, cond.operand, env, not truthy, arg_names)
    elif isinstance(cond, BinOp):
        if cond.op == "and":
            if truthy:  # both sides hold
                return _narrow(ctx, cond.right, _narrow(ctx, cond.left, env, True, arg_names), True, arg_names)
            return res
        if cond.op == "or":
            if truthy:  # the second operand only matters when the first is false
                return res
            return _narrow(ctx, cond.right, _narrow(ctx, cond.left, env, False, arg_names), False, arg_names)
        if cond.op in ("==", "!="):
            for a, b in ((cond.left, cond.right), (cond.right, cond.left)):
                if not (isinstance(a, Sym) and a.name in res):
                    continue
                if isinstance(b, Lit) and b.kind == "nil":
                    plain = (cond.op == "!=") == truthy  # `!= nil` really means "not nil"
                    res[a.name] = strip_nil(res[a.name]) if plain else "nil"
                    return res
                if _nonnil(ctx, b):
                    # `x == <a value that is never nil>` says x is not nil
                    if (cond.op == "==") == truthy:
                        res[a.name] = strip_nil(res[a.name])
                    break
            # the current event: its accessor, or a parameter typed as one
            is_event = isinstance(cond.left, Sym) and (
                cond.left.name in CURRENT_EVENT
                or res.get(cond.left.name, "").rstrip("?") == "event")
            if cond.op == "==" and truthy and is_event and isinstance(cond.right, Sym):
                sigs = ctx.event_args.get(cond.right.name) or []
                for i, t in enumerate(sigs):
                    name = (arg_names or {}).get(i)
                    if name and name in res:
                        res[name] = t
    return res


def _check_stmts(ctx: Context, stmts: List[Stmt], env: Dict[str, str],
                 owner: Optional[str] = None, rets: Optional[List[str]] = None,
                 arg_names: Optional[Dict[int, str]] = None):
    for s in stmts:
        if isinstance(s, SayStmt):
            where = "text to print"
            expect(ctx, where, _check_expr(ctx, s.expr, env, owner, "str"), "str", s.line)
        elif isinstance(s, ReturnStmt):
            for v in s.values:
                t = _check_expr(ctx, v, env, owner)
                if rets is not None and t != "nil":
                    rets.append(t)
        elif isinstance(s, LocalStmt):
            vts = _value_types(ctx, s.values, env, owner)
            for i, (vn, dt) in enumerate(s.names):
                env[vn] = dt or (vts[i] if i < len(vts) else "any")
        elif isinstance(s, AssignStmt):
            vt = _value_types(ctx, s.values, env, owner)
            if isinstance(s.target, Sym):
                name = s.target.name
                if name in ctx.globals:
                    # a game variable (`global`/`const`) keeps the type of its initial
                    # value for reads, but writes are not type-checked (as in mise1)
                    if name in env:
                        cur = env[name]
                    else:
                        cur = None
                elif name in env:
                    cur = env[name]
                elif name.startswith("__"):
                    cur = None
                else:
                    raise Error(f"unknown name {name!r} (declare it with `local` or `global`)",
                                s.line)
                if cur is not None and s.op == "=" and vt:
                    expect(ctx, f"assignment to {name}", vt[0], cur, s.line)
                if cur in (None, "any") and vt and s.op == "=":
                    env[name] = vt[0]
            else:
                _check_store(ctx, s.target, vt[0] if vt else "any", env, owner, s.line)
        elif isinstance(s, CallStmt):
            if s.call.receiver is None and s.call.callee is None:
                _check_value_use(ctx, s.call.func, s.line)
            _check_call(ctx, s.call, env, owner)
        elif isinstance(s, IfStmt):
            cenv = dict(env)
            for cond, body, _l in s.branches:
                _check_cond(ctx, cond, cenv, owner)
                _check_stmts(ctx, body, _narrow(ctx, cond, cenv, True, arg_names), owner, rets, arg_names)
                cenv = _narrow(ctx, cond, cenv, False, arg_names)
            if s.else_body is not None:
                _check_stmts(ctx, s.else_body, cenv, owner, rets, arg_names)
        elif isinstance(s, MatchStmt):
            st = _check_expr(ctx, s.subject, env, owner)
            for pats, guard, body, _l in s.arms:
                aenv = dict(env)
                for p in pats:
                    if not (isinstance(p, Sym) and p.name == "_"):
                        expect(ctx, "match pattern", _check_expr(ctx, p, env, owner, st), st, p.line)
                        # `match ev` arms narrow the event arguments like `if ev == X`
                        aenv = _narrow(ctx, BinOp(line=p.line, op="==", left=s.subject, right=p),
                                       aenv, True, arg_names)
                if guard:
                    _check_cond(ctx, guard, aenv, owner)
                _check_stmts(ctx, body, aenv, owner, rets, arg_names)
        elif isinstance(s, ForNumStmt):
            for bound, what in ((s.start, "start"), (s.stop, "stop"), (s.step, "step")):
                if bound is not None:
                    expect(ctx, f"for bound {what}", _check_expr(ctx, bound, env, owner, "num"), "num", bound.line)
            benv = dict(env)
            benv[s.var] = s.var_type or "num"
            if s.var_type:
                expect(ctx, f"for variable {s.var}", "num", s.var_type, s.line)
            _check_stmts(ctx, s.body, benv, owner, rets)
        elif isinstance(s, ForInStmt):
            it = _check_expr(ctx, s.iter_expr, env, owner)
            # iterating a class walks its array part, so an item is an object
            el = tbl_inner(it) or (_root(ctx) if _is_object_type(ctx, it) else "any")
            benv = dict(env)
            for i, (vn, vt) in enumerate(s.vars):
                benv[vn] = vt or ("num" if (s.is_of and len(s.vars) == 2 and i == 0) else el)
            _check_stmts(ctx, s.body, benv, owner, rets)


def _split_types(t: str) -> List[str]:
    """Split a type list at top-level commas (`fn(a, b)`, `tbl[a|b]`)."""
    if not t.strip():
        return []
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(t):
        depth += (1 if ch in "([" else -1 if ch in ")]" else 0)
        if ch == "," and depth == 0:
            parts.append(t[start:i].strip())
            start = i + 1
    parts.append(t[start:].strip())
    return [p for p in parts if p]


def _fn_parts(t: str):
    """`fn(T1,T2) -> R` -> (["T1", "T2"], ["R"])."""
    if not t.startswith("fn("):
        return None
    depth, close = 0, -1
    for i, ch in enumerate(t):
        depth += (1 if ch == "(" else -1 if ch == ")" else 0)
        if depth == 0 and ch == ")":
            close = i
            break
    if close < 0:
        return None
    params = _split_types(t[3:close])
    rest = t[close + 1:]
    rets = [r.rstrip("?") for r in _split_types(rest[2:])] if rest.startswith("->") else []
    return params, rets


def _sig_ok(ctx: Context, fn: FnDecl, expected: str) -> bool:
    """Can `fn` be passed where a callback of type `expected` is wanted?"""
    parts = _fn_parts(expected)
    if parts is None:
        return False
    eparams, erets = parts
    aparams = [pt for _pn, pt in fn.params]
    if len(aparams) > len(eparams):
        return False
    for i, at in enumerate(aparams):
        et = eparams[i]
        if at == "any" or et == "any":
            continue
        if not is_subtype(ctx, et, at):
            return False
    ar = fn.ret_types or ["any"]
    if not erets or ar == ["any"]:
        return True
    return any(is_subtype(ctx, a, r) for a in ar for r in erets)


def _sig_str(fn: FnDecl) -> str:
    got = "fn(" + ",".join(pt for _pn, pt in fn.params) + ")"
    return got + ("->" + ",".join(fn.ret_types) if fn.ret_types else "")


def _check_fnref(ctx: Context, ref: FnRef, expected: Optional[str], where: str):
    """Check a `&name` reference against the callback signature expected there."""
    fn = ctx.fns.get(ref.name)
    if fn is None or not expected:
        return
    alts = [a for a in split_union(expected) if a.startswith("fn(")]
    if not alts:
        return
    if any(_sig_ok(ctx, fn, a) for a in alts):
        return
    raise TypeCheckError(f"{where}: {ref.name} is {_sig_str(fn)}, expected "
                         f"{' | '.join(alts)}", ref.line)


def _root(ctx: Context) -> str:
    """The root class (`class obj` in core) — the type of "some object"."""
    return ctx.root_class or "obj"


def _room_root(ctx: Context) -> str:
    """The class whose instances behave like rooms — the one declaring `n_to`."""
    for cname, fields in ctx.prop_types.items():
        if "n_to" in fields:
            return cname
    return ""   # nothing declared: no kind is room-like


def _inherits(ctx: Context, kind: str, root: str) -> bool:
    """Is `kind` the class `root` or one of its descendants?"""
    cur, seen = kind, set()
    while cur and cur not in seen:
        if cur == root:
            return True
        seen.add(cur)
        cur = ctx.classes.get(cur)
    return False


def _is_object_type(ctx: Context, t: str) -> bool:
    """A declared class (or an instance of one) — the only things with fields."""
    return t in ctx.classes or t in ctx.objects


def _objectish(ctx: Context, t: str) -> bool:
    """Can a value of this type have fields (`x.field`)? Scalars cannot."""
    for alt in split_union(t):
        alt = alt.rstrip("?").strip()
        if alt in ("any", "ref") or alt.startswith("tbl[") or _is_object_type(ctx, alt):
            return True          # dynamic values, references and collections
        if _is_object_type(ctx, alt):
            return True
    return False


def _owner_of(ctx: Context, target: FieldAccess, env: Dict[str, str], owner: Optional[str]) -> Optional[str]:
    """The declaration whose fields `target.obj` exposes, when it is known."""
    base = target.obj
    if not isinstance(base, Sym):
        return None
    if base.name == "s" and owner:
        return owner
    if base.name in ctx.objects:
        kind = ctx.objects[base.name]
        return base.name if (base.name in ctx.fields or kind == "class") else kind
    if base.name in ctx.classes:
        return base.name
    if base.name in env:
        t = env[base.name]
        return t if (t in ctx.classes or t in ctx.objects) else None
    return None


def _check_store(ctx: Context, target: Expr, vt: str, env: Dict[str, str],
                 owner: Optional[str], line: int = 0):
    """Validate a write: field type stability and declared field names."""
    if not isinstance(target, FieldAccess):
        _check_expr(ctx, target, env, owner, is_lhs=True)
        return
    base_t = _check_expr(ctx, target.obj, env, owner)
    if is_optional(base_t):
        raise TypeCheckError(
            f"{_kind_name(target.obj)}: possible nil, narrow it first (`if {_kind_name(target.obj)}:`)",
            line)
    name = target.field
    if name in READONLY_FIELDS:
        raise Error(f"{name}: an engine field cannot be assigned", line)
    if name.startswith("__"):
        return
    holder = _owner_of(ctx, target, env, owner)
    declared = ctx.fields.get(holder, {}) if holder else {}
    if name in declared:
        ft, is_ref = declared[name]
        if ft != "any":
            expect(ctx, f"{name}", _root(ctx) if (is_ref and vt == "obj") else vt, ft, line)
        return
    if name not in ctx.field_names and name not in ctx.ref_fields:
        raise Error(f"unknown field {name!r} (use __{name} for dynamic values)", line)


def _check_expr(ctx: Context, e: Expr, env: Dict[str, str], owner: Optional[str] = None,
                expected: Optional[str] = None, is_lhs: bool = False) -> str:
    t = _infer(ctx, e, env, owner, expected, is_lhs)
    if expected and not is_lhs:
        expect(ctx, _kind_name(e), t, expected, e.line)
    return t


def _infer(ctx: Context, e: Expr, env: Dict[str, str], owner: Optional[str] = None,
           expected: Optional[str] = None, is_lhs: bool = False) -> str:
    if isinstance(e, Lit):
        if e.kind == "table":
            e.typ = "tbl"
            return "tbl"
        if e.kind == "num" and expected:
            # a number declared as an enum alias (`2` in `gram`) is that enum value
            for alt in split_union(expected):
                if alt in ctx.enums and str(e.val) in ctx.enums[alt][0]:
                    e.typ = alt
                    return alt
        e.typ = "any" if e.kind == "raw" else e.kind
        return e.typ
    if isinstance(e, InterpStr):
        for p in e.parts:
            if isinstance(p, Expr):
                _check_expr(ctx, p, env, owner, "str")
        e.typ = "str"
        return "str"
    if isinstance(e, Bind):
        vt = _value_types(ctx, [e.value], env, owner)
        e.vtyp = vt[0] if vt else "any"
        for n in e.names:
            if n in env:
                raise Error(f"{n}: already defined (choose another name for `:=`)", e.line)
        e.typ = "bool"
        return "bool"
    if isinstance(e, InOp):
        st = _check_expr(ctx, e.subject, env, owner)
        for a in e.alts:
            _check_expr(ctx, a, env, owner, st)   # resolves names, like `==`
        e.typ = "bool"
        return "bool"
    if isinstance(e, FnRef):
        ctx.used_refs.add(e.name)
        if e.name not in ctx.fns and e.name not in ctx.lua_funcs:
            raise Error(f"unknown function {e.name!r} in a function reference", e.line)
        _check_fnref(ctx, e, expected, _kind_name(e))
        e.typ = "fn"
        return "fn"
    if isinstance(e, ListLit):
        in_exp = None
        for alt in split_union(expected) if expected else []:
            in_exp = tbl_inner(alt)
            if in_exp is not None:
                break
        its = [_check_expr(ctx, it, env, owner, in_exp) for it in e.items]
        e.typ = f"tbl[{canon_type('|'.join(its)) if its else ''}]"
        return e.typ
    if isinstance(e, Sym):
        return _infer_sym(ctx, e, env, owner, expected, is_lhs)
    if isinstance(e, FieldAccess):
        return _infer_field(ctx, e, env, owner, is_lhs)
    if isinstance(e, IndexAccess):
        ot = _check_expr(ctx, e.obj, env, owner)
        in_exp = tbl_inner(ot)
        if not (_is_object_type(ctx, ot) or ot in ("tbl", "str") or tbl_inner(ot) is not None):
            expect(ctx, "index", ot, "tbl|str", e.line)
        _check_expr(ctx, e.index, env, owner, "num" if ot != "str" else "num")
        base = in_exp if in_exp is not None else (
            _root(ctx) if _is_object_type(ctx, ot) else ("str" if ot == "str" else "any"))
        # an index may be out of range, so the element is optional
        e.typ = base if (ot == "str" or base in ("any", "nil") or base.endswith("?")) else base + "?"
        return e.typ
    if isinstance(e, UnaryOp):
        if e.op == "-" and isinstance(e.operand, Lit) and e.operand.kind == "str":
            e.typ = "str"  # the engine word marker: `-"слово/мр"` in `word = -"..."`
            return "str"
        _check_expr(ctx, e.operand, env, owner, None if e.op == "not" else "num")
        e.typ = "bool" if e.op == "not" else "num"
        return e.typ
    if isinstance(e, BinOp):
        return _infer_binop(ctx, e, env, owner, expected)
    if isinstance(e, Call):
        return _check_call(ctx, e, env, owner)
    return "any"


def _infer_sym(ctx: Context, e: Sym, env: Dict[str, str], owner: Optional[str],
               expected: Optional[str], is_lhs: bool) -> str:
    n = e.name
    if is_lhs:
        # a write target must be a local/parameter, a declared global or `__`-dynamic
        if n in env:
            e.rk, e.typ = "var", env[n]
            return e.typ
        if n in ctx.globals:
            e.rk, e.typ = "global", ctx.globals[n][0]
            return e.typ
        if n.startswith("__"):
            e.rk, e.typ = "var", "any"
            return "any"
        raise Error(f"unknown name {n!r} (declare it with `local` or `global`)", e.line)
    if n in env:
        e.rk, e.typ = "var", env[n]
        return e.typ
    if expected:
        exps = split_union(expected)
        if "event" in exps and n in ctx.event_names:
            e.rk, e.typ = "event", "event"
            return "event"
        if n in ctx.enum_owner:
            for ea in exps:
                if _enum_value(ctx, n, ea):
                    e.rk, e.typ = "enum", ea
                    return ea
    if n in ctx.objects:
        e.rk, e.typ = "obj", ctx.objects[n]
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
    if n in ctx.fns or n in ctx.lua_funcs:
        sig = ctx.fns.get(n)
        e.rk = "value" if (sig and sig.is_value) else "fn0"
        e.typ = sig.ret_types[0] if (sig and sig.ret_types) else "any"
        return e.typ
    if n in ctx.lua_globals:
        e.rk, e.typ = "lua_global", ctx.lua_globals[n]
        return e.typ
    if n.startswith("#"):
        raise Error(f"unknown tag {n!r}", e.line)
    raise Error(f"unknown name {n!r}{_enum_hint(ctx, n)}", e.line)


def _infer_field(ctx: Context, e: FieldAccess, env: Dict[str, str],
                 owner: Optional[str], is_lhs: bool) -> str:
    base_t = _check_expr(ctx, e.obj, env, owner)
    if is_lhs:
        e.typ = base_t
        return base_t
    if is_optional(base_t):
        raise TypeCheckError(
            f"{_kind_name(e.obj)}: possible nil, narrow it first (`if {_kind_name(e.obj)}:`)", e.line)
    if not _objectish(ctx, base_t):
        raise TypeCheckError(f"{_kind_name(e.obj)}: {base_t} has no fields "
                             f"(`.{e.field}`)", e.line)
    holder = _owner_of(ctx, e, env, owner)
    if holder and e.field in ctx.fields.get(holder, {}):
        ft, is_r = ctx.fields[holder][e.field]
        e.is_ref, e.typ = is_r, ft
        return ft
    if e.field in ctx.ref_fields:
        e.is_ref, e.typ = True, _root(ctx)
        return _root(ctx)
    if e.field in ctx.field_names:
        e.typ = "any"
        return "any"
    if e.field.startswith("__"):
        e.typ = "any"
        return "any"
    raise Error(f"unknown field {e.field!r} (use __{e.field} for dynamic values)", e.line)


def _infer_binop(ctx: Context, e: BinOp, env: Dict[str, str], owner: Optional[str],
                 expected: Optional[str]) -> str:
    lt = _check_expr(ctx, e.left, env, owner)
    if e.op in ("==", "!="):
        _infer(ctx, e.right, env, owner, lt)  # resolves bare names, comparing is not a type error
        e.typ = "bool"
        return "bool"
    if e.op in ("<", "<=", ">", ">="):
        for side in (e.left, e.right):
            expect(ctx, "comparison", _check_expr(ctx, side, env, owner, "num"), "num", side.line)
        e.typ = "bool"
        return "bool"
    if e.op == "..":
        for side in (e.left, e.right):
            t = _check_expr(ctx, side, env, owner)
            if not is_subtype(ctx, t, "str|num|bool|obj|event") and t != "any":
                raise TypeCheckError(f"concatenation: expected str, got {t}", side.line)
        e.typ = "str"
        return "str"
    if e.op in ("+", "-", "*", "/", "%", "//"):
        for side in (e.left, e.right):
            expect(ctx, "arithmetic", _check_expr(ctx, side, env, owner, "num"), "num", side.line)
        e.typ = "num"
        return "num"
    rt = _check_expr(ctx, e.right, env, owner)
    if e.op == "and":
        e.typ = rt
    elif e.op == "or":
        e.typ = canon_type(f"{strip_nil(lt)}|{rt}")
    else:
        e.typ = rt
    return e.typ


def _check_value_use(ctx: Context, name: str, line: int):
    """`extern value` is an expression: using it as a statement is a mistake."""
    fn = ctx.fns.get(name)
    if fn is not None and fn.is_value:
        raise Error(f"{name}: an expression, not a statement (use its value)", line)


def _check_call(ctx: Context, c: Call, env: Dict[str, str], owner: Optional[str] = None) -> str:
    """Type a call: `f a b`, `f(a, b)`, `obj:m a` and a call of a fn value."""
    if c.callee is not None:
        ct = _check_expr(ctx, c.callee, env, owner)
        if ct not in ("any", "fn") and not ct.startswith("fn("):
            raise TypeCheckError(f"{_kind_name(c.callee)}: calling a non-function value ({ct})", c.line)
        for a in c.args:
            _check_expr(ctx, a, env, owner)
        c.typ = "any"
        return "any"

    is_method = c.receiver is not None
    all_args = ([c.receiver] + c.args) if is_method else list(c.args)
    label = f"{_kind_name(c.receiver)}:{c.func}" if is_method else c.func
    fn = ctx.fns.get(c.func)

    if is_method:
        rt = c.receiver.typ
        if is_optional(rt):
            raise TypeCheckError(
                f"{_kind_name(c.receiver)}: possible nil, narrow it first (`if {_kind_name(c.receiver)}:`)",
                c.line)

    if fn is None:
        # a method of the engine (`l:add(x)`), a Lua function or a fn value
        if is_method or c.func in ctx.lua_funcs or env.get(c.func, "").startswith("fn"):
            for a in all_args:
                _check_expr(ctx, a, env, owner)
            ftype = env.get(c.func, "")
            c.typ = ftype.split("->", 1)[1].split(",")[0] if "->" in ftype else "any"
            return c.typ
        raise Error(f"unknown function {c.func!r}", c.line)

    params = fn.params
    required = sum(1 for _pn, pt in params if not (pt == "nil" or pt.endswith("?")))
    given = len(all_args)
    variadic = bool(fn.variadic)
    if given < required or (not variadic and given > len(params)):
        if variadic:
            want = f"{required}+"
        elif required == len(params):
            want = str(required)
        else:
            want = f"{required}..{len(params)}"
        raise Error(f"{label} expects {want} argument(s), got {given}", c.line)

    for i, a in enumerate(all_args):
        exp = params[i][1] if i < len(params) else (fn.variadic if variadic else None)
        got = _check_expr(ctx, a, env, owner, exp)
        if exp:
            expect(ctx, f"argument {i + 1} of {label}", got, exp, a.line)

    c.typ = fn.ret_types[0] if fn.ret_types else "any"
    return c.typ


def _check_signature(ctx: Context, fn: FnDecl):
    """Unknown types or a required parameter after an optional one."""
    if fn.is_extern:
        return
    seen_optional = False
    for pname, ptype in fn.params:
        for alt in split_union(ptype):
            if alt in PRIMITIVES or alt in ctx.enums or alt in ctx.classes \
                    or alt.startswith("fn(") or tbl_inner(alt) is not None or alt == "nil":
                continue
            raise Error(f"fn {fn.name}({pname}): unknown type {alt!r}", fn.line)
        optional = ptype == "nil" or ptype.endswith("?")
        if seen_optional and not optional:
            raise Error(f"fn {fn.name}: required parameter {pname!r} after an optional one", fn.line)
        seen_optional = seen_optional or optional
    for rt in fn.ret_types:
        for alt in split_union(rt):
            if alt in PRIMITIVES or alt in ctx.enums or alt in ctx.classes \
                    or alt.startswith("fn(") or tbl_inner(alt) is not None or alt == "nil":
                continue
            raise Error(f"fn {fn.name}: unknown return type {alt!r}", fn.line)


def _check_returns(ctx: Context, fn: FnDecl, env: Dict[str, str], owner: Optional[str]):
    """`return` inside an annotated `fn` must match its declared result types."""
    expected = fn.ret_types

    def walk(stmts: List[Stmt]):
        for s in stmts:
            if isinstance(s, ReturnStmt) and s.kind == "return":
                if not s.values:
                    continue
                if len(s.values) > len(expected):
                    raise Error(f"fn {fn.name}: returns {len(s.values)} value(s), {len(expected)} declared", s.line)
                for i, v in enumerate(s.values):
                    # types were inferred by the narrowing-aware main pass
                    expect(ctx, f"return value {i + 1} of {fn.name}", v.typ, expected[i], s.line)
            elif isinstance(s, IfStmt):
                for _c, body, _l in s.branches:
                    walk(body)
                if s.else_body:
                    walk(s.else_body)
            elif isinstance(s, MatchStmt):
                for _p, _g, body, _l in s.arms:
                    walk(body)
            elif isinstance(s, (ForNumStmt, ForInStmt)):
                walk(s.body)

    walk(fn.body)


def _value_types(ctx: Context, values: List[Expr], env: Dict[str, str],
                 owner: Optional[str]) -> List[str]:
    """Types of an expression list; a trailing call expands its multiple results."""
    res: List[str] = []
    for i, v in enumerate(values):
        t = _check_expr(ctx, v, env, owner)
        if i == len(values) - 1 and isinstance(v, Call) and v.receiver is None and v.func:
            fn = ctx.fns.get(v.func)
            if fn and len(fn.ret_types) > 1:
                res.extend(fn.ret_types)
                continue
        res.append(t)
    return res


def _check_override(ctx: Context, ent: EntityDecl):
    """An instance must not replace a class method with a plain value (STEAD3 crashes)."""
    base = ent.kind if ent.kind not in ("class", "impl") else None
    cdecl = ctx.class_decls.get(base) if base else None
    if cdecl is None:
        return
    methods = {}
    for p in cdecl.props:
        if isinstance(p.value, (list, FnRef)) or (isinstance(p.value, Lit) and p.value.kind == "lua"):
            methods[p.name] = p
    for p in ent.props:
        if p.name in methods and p.value is not None \
                and not isinstance(p.value, (list, FnRef)) \
                and not (isinstance(p.value, Lit) and p.value.kind == "lua"):
            raise Error(
                f"{ent.name}.{p.name}: cannot overwrite the method of class {base!r} with a value "
                f"(use a block, `&fn` or `impl {ent.name}`)", p.line)


def _check_cond(ctx: Context, cond: Expr, env: Dict[str, str], owner: Optional[str]):
    """Check a condition, narrowing inside its own `and`/`or` chain.

    `a and b` checks `b` with the refinements of `a` being true, `a or b`
    with the refinements of `a` being false (short circuit).
    """
    if isinstance(cond, UnaryOp) and cond.op == "not":
        return _check_cond(ctx, cond.operand, env, owner)
    if isinstance(cond, BinOp) and cond.op == "and":
        _check_cond(ctx, cond.left, env, owner)
        return _check_cond(ctx, cond.right, _narrow(ctx, cond.left, env, True), owner)
    if isinstance(cond, BinOp) and cond.op == "or":
        _check_cond(ctx, cond.left, env, owner)
        return _check_cond(ctx, cond.right, _narrow(ctx, cond.left, env, False), owner)
    _check_expr(ctx, cond, env, owner)


def is_optional(t: str) -> bool:
    return "nil" in split_union(t)


def _check_handler_events(ctx: Context, h: Handler, where: str):
    """A handler phase must name a declared event."""
    import difflib
    for ev in h.events:
        if ev in ctx.event_names:
            continue
        near = difflib.get_close_matches(ev, sorted(ctx.event_names), 1, 0.7)
        hint = f" (did you mean {near[0]!r}?)" if near else ""
        raise Error(f"{where}: unknown event {ev!r}{hint}", h.line)
