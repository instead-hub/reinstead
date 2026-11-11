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
    enum_owner: Dict[str, str] = field(default_factory=dict)   # value -> its type
    event_names: Set[str] = field(default_factory=set)
    event_args: Dict[str, List[str]] = field(default_factory=dict)
    event_acted: Set[str] = field(default_factory=set)   # the action takes an acted object

    classes: Dict[str, str] = field(default_factory=dict)                  # class -> parent
    class_decls: Dict[str, EntityDecl] = field(default_factory=dict)
    objects: Dict[str, str] = field(default_factory=dict)                  # id -> kind/class
    fields: Dict[str, Dict[str, Tuple[str, bool]]] = field(default_factory=dict)
    prop_decls: Dict[str, Dict[str, Prop]] = field(default_factory=dict)   # declared class fields
    ctors: Dict[str, str] = field(default_factory=dict)                  # class -> engine constructor
    root_class: Optional[str] = None                                     # the first class with no parent
    field_names: Set[str] = field(default_factory=set)
    entries: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)  # engine entry points
    lua_globals: Dict[str, GlobalDecl] = field(default_factory=dict)     # `extern global`
    ref_fields: Set[str] = field(default_factory=set)   # fields whose declared type says "reference"

    fns: Dict[str, FnDecl] = field(default_factory=dict)
    used_refs: Set[str] = field(default_factory=set)
    lua_funcs: Set[str] = field(default_factory=set)
    globals: Dict[str, Tuple[str, bool]] = field(default_factory=dict)


def split_top(t: str, sep: str) -> List[str]:
    """Split at a top-level separator: `a|b`, `fn(x, y)`, `tbl[a|b]`."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(t):
        depth += (1 if ch in "([" else -1 if ch in ")]" else 0)
        if ch == sep and depth == 0:
            parts.append(t[start:i].strip())
            start = i + 1
    parts.append(t[start:].strip())
    return parts


def split_union(t: str) -> List[str]:
    t = t.strip()
    if t.endswith("?"):
        return [p for p in split_union(t[:-1]) if p != "nil"] + ["nil"]
    parts = split_top(t, "|")
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


def _ref_inner(t: str) -> Optional[str]:
    """`ref[C]` -> C; bare `ref` is `ref[obj]`, so it returns None only for non-refs."""
    return t[4:-1] if (t.startswith("ref[") and t.endswith("]")) else None


def is_optional(t: str) -> bool:
    return "nil" in split_union(t)


def _split_types(t: str) -> List[str]:
    """Split a type list at top-level commas (`fn(a, b)`, `tbl[a|b]`)."""
    return [p for p in split_top(t, ",") if p]


def _fn_parts(t: str) -> Optional[Tuple[List[str], List[str]]]:
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


def _fn_returns(declared: Optional[str]) -> List[str]:
    """Return types of the `fn(...) -> T` alternatives of a declared type."""
    if not declared:
        return []
    return [r for alt in split_union(declared) for r in (_fn_parts(alt) or ([], []))[1]]


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
        return _is_object_type(ctx, actual) or actual == "str" or _ref_inner(actual) is not None
    want_ref = _ref_inner(expected)
    if want_ref is not None:
        got_ref = _ref_inner(actual)
        if got_ref is not None:
            return is_subtype(ctx, got_ref if got_ref else "obj", want_ref or "obj")
        if actual == "str":
            return True          # a name of an object (the engine resolves it)
        return _is_object_type(ctx, actual) and is_subtype(ctx, actual, want_ref or "obj")
    if expected in ctx.classes:
        return _inherits(ctx, actual, expected)
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
    if isinstance(expr, IndexAccess):
        return f"{_kind_name(expr.obj)}[…]"
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
    base_evs, class_at = _collect_declarations(ctx, prog)
    _register_entities(ctx, prog, class_at)
    _resolve_verb_events(ctx, prog, base_evs)
    _collect_fields_and_refs(ctx, prog)
    _typecheck_program(ctx, prog)
    return ctx


def _register_class_decl(ctx: Context, item: EntityDecl, idx: int, class_at: Dict[str, int]):
    assert item.name is not None
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
    class_at.setdefault(item.name, idx)
    if item.name in ctx.class_decls:
        ctx.class_decls[item.name].props.extend(item.props)
    else:
        ctx.class_decls[item.name] = item
    for p in item.props:
        if p.typ:
            prev_p = ctx.prop_decls.setdefault(item.name, {}).get(p.name)
            if prev_p is not None and p.emit is None and prev_p.emit is not None:
                p.emit = prev_p.emit
            ctx.prop_decls[item.name][p.name] = p
            if _is_ref_type(ctx, p.typ):
                ctx.ref_fields.add(p.name)


def _collect_declarations(ctx: Context, prog: Program) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    base_evs: Dict[str, List[str]] = {}
    class_at: Dict[str, int] = {}      # position of every `class` declaration
    decl_evs: Dict[str, List[str]] = {}
    ext_evs: Dict[str, Tuple[List[str], int]] = {}
    for idx, item in enumerate(prog.items):
        if isinstance(item, EventsDecl):
            for evs, ats in item.sigs:
                for at in ats:
                    _check_type(ctx, at, f"event {evs[0]}", item.line, "argument type")
                for ev in evs:
                    ctx.event_names.add(ev)
                    if item.extend:
                        ext_evs[ev] = (list(ats), item.line)
                    else:
                        _declare_event(decl_evs, ev, ats, item)
        elif isinstance(item, TypeDecl):
            if item.extend and item.name not in ctx.enums:
                raise Error(f"extend type {item.name!r}: unknown type", item.line)
            if item.name in ctx.enums and not item.extend:
                raise Error(f"duplicate type {item.name!r}", item.line)
            vals, neg = ctx.enums.get(item.name, (set(), False))
            vals.update(item.values)
            ctx.enums[item.name] = (vals, neg or item.negate)
            for v in item.values:
                owner = ctx.enum_owner.get(v)
                if owner is not None and owner != item.name:
                    raise Error(f"type {item.name}: {v!r} is already a value of type "
                                f"{owner!r} (an enum value belongs to one type)", item.line)
                ctx.enum_owner[v] = item.name
        elif isinstance(item, FnDecl):
            if item.name in ctx.fns:
                raise Error(f"duplicate fn {item.name!r}", item.line)
            ctx.fns[item.name] = item
        elif isinstance(item, EntryDecl):
            ctx.entries[item.name] = list(item.params)
        elif isinstance(item, GlobalDecl):
            ctx.lua_globals[item.name] = item
        elif isinstance(item, LuaDecl):
            for m in re.finditer(r"\bfunction\s+([A-Za-z_]\w*)", item.code):
                ctx.lua_funcs.add(m.group(1))
        elif isinstance(item, EntityDecl) and item.kind == "class" and item.name:
            _register_class_decl(ctx, item, idx, class_at)
    base_evs.update(decl_evs)
    base_evs.update(_apply_event_extends(decl_evs, ext_evs))
    return base_evs, class_at


def _types_str(types: List[str]) -> str:
    """`obj, str?` — a signature for a diagnostic."""
    return ", ".join(types) if types else "no arguments"


def _declare_event(decl_evs: Dict[str, List[str]], ev: str, ats: List[str], item: Any):
    """`event X: T` — a declaration; a different signature is a conflict."""
    prev = decl_evs.get(ev)
    if prev is not None and prev != list(ats):
        raise Error(f"event {ev}: declared with {_types_str(prev)}, "
                    f"here with {_types_str(list(ats))} "
                    f"(use `extend event` to replace)", item.line)
    decl_evs[ev] = list(ats)


def _apply_event_extends(decl_evs: Dict[str, List[str]],
                         ext_evs: Dict[str, Tuple[List[str], int]]) -> Dict[str, List[str]]:
    """`extend event X: T` — replace the arguments of an already declared event."""
    for ev, (ats, line) in ext_evs.items():
        if ev not in decl_evs:
            raise Error(f"extend event {ev}: unknown event "
                        f"(declare it with `event {ev}`)", line)
    return {ev: ats for ev, (ats, _l) in ext_evs.items()}


def _check_class_order(ent: EntityDecl, idx: int, class_at: Dict[str, int]):
    """A class must be declared above every use of it (the emitter keeps the source order)."""
    if ent.kind == "class":
        used = list(ent.traits) + ([ent.parent] if ent.parent else [])
    elif ent.kind == "impl":
        used = [ent.name] if ent.name else []
    else:
        used = [ent.kind] + list(ent.traits)
    for cname in used:
        if cname and class_at.get(cname, -1) > idx:
            raise Error(f"{ent.name or ent.kind}: class {cname!r} is used before its declaration "
                        f"(move `class {cname}` above)", ent.line)


def _inline_mixin_traits(ctx: Context, ent: EntityDecl, instantiated_classes: Set[str]):
    """Inline props/handlers of classes used as traits (mixins)."""
    exp_p, exp_h, kept_tr = [], [], []
    for tr in ent.traits:
        cdecl = ctx.class_decls.get(tr)
        if cdecl and tr not in instantiated_classes:
            exp_p.extend(p for p in cdecl.props if p.value is not None)
            exp_h.extend(cdecl.handlers)
            kept_tr.extend(t for t in cdecl.traits if t not in kept_tr)
            if tr not in kept_tr:
                kept_tr.append(tr)
        else:
            kept_tr.append(tr)
    ent.traits = kept_tr
    own_p = {p.name for p in ent.props}
    own_h = {(h.phase, tuple(h.events)) for h in ent.handlers}
    ent.props = [p for p in exp_p if p.name not in own_p] + ent.props
    ent.handlers = [h for h in exp_h if (h.phase, tuple(h.events)) not in own_h] + ent.handlers


def _register_entity(ctx: Context, ent: EntityDecl, idx: int,
                     class_at: Dict[str, int], instantiated_classes: Set[str]):
    _check_class_order(ent, idx, class_at)
    _check_override(ctx, ent)      # before mixin traits are inlined into the entity
    if ent.kind == "impl" and ent.name == "mp":
        ctx.event_names.update(ent.traits)
    _inline_mixin_traits(ctx, ent, instantiated_classes)
    # a nameless declaration is legal (`obj "вещь"` — the engine names it), but the
    # kind must be a declared class either way: a mistyped kind is a typo, not a new kind
    if ent.kind not in ("class", "impl"):
        if ent.kind not in ctx.classes:
            raise Error(f"unknown kind {ent.kind!r}{_kind_hint(ctx, ent)}", ent.line)
        if ent.name and not ent.name.startswith("#") and ent.name in ctx.objects:
            raise Error(f"duplicate declaration {ent.name!r}", ent.line)
        if ent.name:
            ctx.objects[ent.name] = ent.kind
    if ent.kind == "impl" and ent.name and ent.name not in ("game", "pl", "mp") \
            and not ent.name.startswith("@") and ent.name not in ctx.objects \
            and ent.name not in ctx.classes and ent.name not in ctx.fns \
            and ent.name not in ctx.lua_funcs:
        raise Error(f"impl {ent.name!r}: unknown target", ent.line)
    for ch in ent.children:
        _register_entity(ctx, ch, idx, class_at, instantiated_classes)


def _register_entities(ctx: Context, prog: Program, class_at: Dict[str, int]):
    instantiated = {it.kind for it in prog.items if isinstance(it, EntityDecl)}
    for idx, item in enumerate(prog.items):
        if isinstance(item, EntityDecl):
            _register_entity(ctx, item, idx, class_at, instantiated)
        elif isinstance(item, TalkDecl):
            ctx.objects[item.name] = "talk"
            ctx.field_names.update(p.name for p in item.props)


def _resolve_verb_events(ctx: Context, prog: Program, base_evs: Dict[str, List[str]]):
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
            ctx.event_acted.add(ev)
    for contribs in active_verbs.values():
        for ev, slots in contribs:
            if ev in base_evs:
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


def _collect_entity_fields(ctx: Context, ent: EntityDecl):
    for p in ent.props:
        ctx.field_names.add(p.name)
    fmap = ctx.fields.setdefault(ent.name, {}) if ent.name else {}
    base = ent.parent if ent.kind == "class" else ent.kind
    for src in [base] + [tr for tr in ent.traits if tr in ctx.classes]:
        for k, v in ctx.fields.get(src, {}).items():
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
        _collect_entity_fields(ctx, ch)


def _collect_fields_and_refs(ctx: Context, prog: Program):
    for item in prog.items:
        if isinstance(item, VarDecl):
            for vn, ve, _l in item.items:
                ctx.globals[vn] = _lit_type(ctx, ve)
        elif isinstance(item, EntityDecl):
            _collect_entity_fields(ctx, item)

    for item in prog.items:
        if isinstance(item, EntityDecl):
            for p in item.props:
                if p.typ:
                    _check_type(ctx, p.typ, f"{item.name or ''}.{p.name}".lstrip("."), p.line)
        elif isinstance(item, VarDecl):
            for vn, ve, vl in item.items:
                _check_var_ref(ctx, vn, ve, vl)


def _typecheck_fn(ctx: Context, item: FnDecl):
    if item.name in ctx.entries:
        want = ctx.entries[item.name]
        if len(item.params) != len(want):
            raise Error(f"entry {item.name}: the engine calls it with "
                        f"{len(want)} argument(s), declared {len(item.params)}", item.line)
    _check_signature(ctx, item)
    if item.is_extern or not isinstance(item.body, list):
        return
    env = {pn: pt for pn, pt in item.params}
    owner = item.params[0][1] if (item.params and item.params[0][0] == "s" and item.params[0][1] in ctx.classes) else None
    rets: List[str] = []
    _check_stmts(ctx, item.body, env, owner, rets, fn_decl=item if item.ret_types else None)
    falls_through = bool(item.body) and not _returns_all(item.body)
    if item.ret_types:
        if falls_through and "nil" not in split_union("|".join(item.ret_types)):
            raise Error(f"fn {item.name}: {', '.join(item.ret_types)} is declared, but a "
                        f"path leaves the body without `return` (add `return` or `pass`, "
                        f"or declare `{strip_nil(item.ret_types[0])}?`)", item.line)
    else:
        if rets and falls_through:
            rets.append("nil")
        item.ret_types = [canon_type("|".join(rets))] if rets else ["any"]


def _typecheck_program(ctx: Context, prog: Program):
    for item in prog.items:
        if isinstance(item, FnDecl):
            _typecheck_fn(ctx, item)
    for item in prog.items:
        if isinstance(item, EntityDecl):
            _check_entity(ctx, item)
        elif isinstance(item, TalkDecl):
            _check_talk(ctx, item)


def _lit_type(ctx: Context, e: Expr) -> Tuple[str, bool]:
    if isinstance(e, Lit):
        if e.kind == "table":            # `{ … }` — a Lua table
            return "tbl", False
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
        enum = ctx.enum_owner.get(e.name.lstrip("~"))
        if enum:
            e.rk = "enum"
            return enum, False
    if isinstance(e, ListLit):
        inner = canon_type("|".join(_lit_type(ctx, it)[0] for it in e.items)) if e.items else ""
        return f"tbl[{inner}]", False
    return "any", False


def _ref_error(where: str, name: str, line: int):
    raise Error(f"{where}: unknown object reference {name!r}", line)


def _check_ref_name(ctx: Context, where: str, name: str, line: int):
    """A bare object name in a reference position must be declared."""
    if name not in ctx.objects:
        _ref_error(where, name, line)


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


def _check_ref_prop(ctx: Context, ent_name: Optional[str], p: Prop):
    """Validate reference values on a reference field."""
    if p.name not in ctx.ref_fields or p.value is None or isinstance(p.value, (list, FnRef)):
        return
    if isinstance(p.value, Lit) and p.value.kind in ("raw", "lua", "num", "bool", "nil"):
        return
    where = f"{ent_name}.{p.name}" if ent_name else p.name
    if isinstance(p.value, Lit) and p.value.kind == "str":
        raise Error(f"{where}: object reference must be a bare name, not a quoted string ({p.value.val!r})", p.line)
    _check_ref_value(ctx, where, p.value, p.line)


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
        if alt == "ref" or _ref_inner(alt) is not None or _is_object_type(ctx, alt):
            return True
        inner = tbl_inner(alt)
        if inner is not None and (inner == "ref" or _ref_inner(inner) is not None
                                  or _is_object_type(ctx, inner)):
            return True
    return False


def _kind_hint(ctx: Context, ent: EntityDecl) -> str:
    """A hint for a mistyped kind or a member written without '='."""
    import difflib
    phase = difflib.get_close_matches(ent.kind, sorted(PHASES), 1, 0.75)
    if phase and ent.name in ctx.event_names:
        return f" (did you mean `{phase[0]} {ent.name}`?)"
    if ent.kind in ctx.field_names or any(ent.kind in d for d in ctx.prop_decls.values()):
        return f" (did you mean `{ent.kind} = ...`?)"
    near = difflib.get_close_matches(ent.kind, sorted(ctx.classes), 1, 0.75)
    return f" (did you mean class {near[0]!r}?)" if near else ""


def _walk_class_chain(ctx: Context, kind: str) -> List[str]:
    """The class `kind` and its ancestors in inheritance order."""
    chain: List[str] = []
    cur, seen = kind, set()
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = ctx.classes.get(cur)
    return chain


def _decl_prop(ctx: Context, kind: str, name: str) -> Optional[Prop]:
    """A field declaration looked up through the class chain of `kind`."""
    for cur in _walk_class_chain(ctx, kind):
        val = ctx.prop_decls.get(cur, {}).get(name)
        if val is not None:
            return val
    return None


def _prop_body_env(ctx: Context, kind: str, p: Prop) -> Dict[str, str]:
    """Parameters of a prop body, taken from the declared `fn(...)` of the field."""
    decl = _decl_prop(ctx, kind, p.name)
    typ = (decl.typ if decl else None) or ""
    names: List[str] = (decl.type_params if decl and decl.type_params else None) or []
    if p.params is None and names:
        p.params = list(names)
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


def _decl_emit(ctx: Context, kind: str, name: str) -> Optional[Emit]:
    """How the declared field reaches Lua (`= method attr(join)`)."""
    decl = _decl_prop(ctx, kind, name)
    return decl.emit if decl else None


def _check_emit(where: str, emit: Emit, value: Any, line: int):
    """A method-emitted field takes the value shape its form needs."""
    if emit.form == "none":
        if not (isinstance(value, Lit) and value.kind == "bool"):
            raise TypeCheckError(f"{where}: `:{emit.method}()` takes a `true`/`false` value", line)
    elif emit.form == "table":
        if not (isinstance(value, Lit) and value.kind == "table"):
            raise TypeCheckError(f"{where}: `:{emit.method}{{...}}` takes a `{{ ... }}` table", line)


def _decl_type(ctx: Context, kind: str, name: str) -> Optional[str]:
    """The declared type of a field, looked up through the class chain of `kind`."""
    decl = _decl_prop(ctx, kind, name)
    return decl.typ if decl else None


def _entity_kind(ctx: Context, ent: EntityDecl) -> str:
    """The class whose field declarations apply to this entity."""
    if ent.kind == "class":
        return ent.name or ""
    if ent.kind == "impl":
        return ctx.objects.get(ent.name or "", _root(ctx))
    return ent.kind


def _check_entity(ctx: Context, ent: EntityDecl):
    owner = ent.name
    kind = _entity_kind(ctx, ent)
    if ent.kind == "impl" and ent.children:
        raise Error(f"impl {owner}: cannot hold an object — declare it at the top level "
                    f"(or put it into another object with `with`/`found_in`)",
                    ent.children[0].line)
    for p in ent.props:
        _check_ref_prop(ctx, owner, p)
        where = f"{owner}.{p.name}" if owner else p.name
        declared = _decl_type(ctx, kind, p.name) if kind else None
        if isinstance(p.value, FnRef):
            _check_fn_target(ctx, p.value)
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
            _prop_body_env(ctx, kind, p)  # populates p.params if declared on the class
        elif isinstance(p.value, Expr):
            _check_expr(ctx, p.value, {"s": _root(ctx)}, owner, declared)
        emit = _decl_emit(ctx, kind, p.name) if kind else None
        if emit and p.value is not None:
            p.emit = emit
            _check_emit(where, emit, p.value, p.line)
    for h in ent.handlers:
        _check_handler_events(ctx, h, owner or kind)
        params, arg_names = _handler_params(ctx, owner, kind, h)
        h.params = [pn for pn, _t in params]     # what the emitter prints
        if isinstance(h.body, FnRef):
            _check_fn_target(ctx, h.body)
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
    self_t = kind if (kind in ctx.classes or kind in ctx.objects) else _root(ctx)
    params: List[Tuple[str, str]] = [("s", self_t)]
    arg_names: Dict[int, str] = {}
    is_any = any(ev in ("Any", "Default") for ev in h.events)
    if is_any:                      # `before_Default(s, ev, w, wh)` and `before_Any(...)`
        params += [("ev", "event"), ("w", _root(ctx)), ("wh", _root(ctx))]
        stripped = not (_inherits(ctx, kind, _room_root(ctx)) or owner in ("game", "mp", None))
        # the arguments follow `ev`; on the acted object the object itself is stripped
        names = ("w", "wh", "w2", "w3")
        if stripped:
            return params, {i: names[i - 1] for i in range(1, len(names) + 1)}
        return params, {i: names[i] for i in range(len(names))}
    sigs = _handler_event_args(ctx, h)
    acted = bool(sigs) and any(ev in ctx.event_acted for ev in h.events)
    room_like = _inherits(ctx, kind, _room_root(ctx)) or owner in ("game", "mp", None)
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


# the `choice` fields that are written as `name = …` in a choice (a condition is
# a truthiness test, like `if`, so it is not among them)
CHOICE_FIELDS = ("ask", "reply", "do", "onempty")


def _check_talk_body(ctx: Context, part: Any, env: Dict[str, str], owner: str,
                     want: Optional[str] = None, where: str = "", line: int = 0):
    if isinstance(part, FnRef):
        _check_fn_target(ctx, part)
        ctx.used_refs.add(part.name)
    elif isinstance(part, list):
        rets: List[str] = []
        _check_stmts(ctx, part, dict(env), owner, rets)
        returns = _fn_returns(want) if want else []
        for t in rets if returns else []:
            expect(ctx, where, t, "|".join(returns), line)
    elif isinstance(part, Expr):
        _check_expr(ctx, part, dict(env), owner, want)


def _check_talk(ctx: Context, td: TalkDecl):
    env = {"s": "talk"}
    own = ctx.fields.setdefault(td.name, {})
    for p in td.props:                       # talk-level fields (a game may add its own)
        own[p.name] = _lit_type(ctx, p.value) if isinstance(p.value, Expr) else ("fn", False)
    for name, spec in ctx.fields.get("talk", {}).items():   # what `class talk` declares
        own.setdefault(name, spec)
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

    def chk_c(c: TalkChoice):
        check_next(c)
        parts = [(c.cond, None, "when")] + [
            (getattr(c, f), _decl_type(ctx, "choice", f), f) for f in CHOICE_FIELDS
        ]
        for part, want, what in parts:
            _check_talk_body(ctx, part, env, td.name, want, f"talk {td.name}: {what}", c.line)
        for sub in c.children:
            chk_c(sub)

    _check_talk_body(ctx, td.intro, env, td.name)
    for c in td.choices:
        chk_c(c)
    for _ln, lsay, lcs in td.labels:
        _check_talk_body(ctx, lsay, env, td.name)
        for c in lcs:
            chk_c(c)


def _returns_all(stmts: List[Stmt]) -> bool:
    """Does every path through this body end with a value?

    `return <values>` and `pass` (= `return false`) count; `stop` (= `return`) does
    not, a loop may not run and a `match` is complete only with a `_` arm.
    """
    def at(i: int) -> bool:
        while i < len(stmts):
            s = stmts[i]
            if isinstance(s, ReturnStmt):
                return s.kind == "pass" or (s.kind == "return" and bool(s.values))
            if isinstance(s, IfStmt):
                if s.else_body is not None and at_body(s.else_body) \
                        and all(at_body(b) for _c, b, _l in s.branches):
                    return True
                return at(i + 1)          # no `else`: the path continues after the `if`
            if isinstance(s, MatchStmt):
                has_default = any(len(p) == 1 and isinstance(p[0], Sym) and p[0].name == "_" and not g
                                  for p, g, _b, _l in s.arms)
                if has_default and all(at_body(b) for _p, _g, b, _l in s.arms):
                    return True
                return at(i + 1)
            i += 1
        return False

    def at_body(body: List[Stmt]) -> bool:
        return _returns_all(body)

    return at(0)


def _nonnil(ctx: Context, e: Expr) -> bool:
    """Is this expression known to be a value, never nil?"""
    if isinstance(e, Lit):
        return e.kind != "nil"
    if isinstance(e, Sym):
        return (e.name in ctx.objects or e.name in ctx.event_names
                or bool(ctx.enum_owner.get(e.name.lstrip("~"))))
    # a call or a field may well be nil, a list literal never is
    return isinstance(e, (ListLit, InterpStr))


def _narrow_event_args(ctx: Context, ev_names: List[str], res: Dict[str, str],
                       arg_names: Optional[Dict[int, str]]):
    if not ev_names or not arg_names:
        return
    alts = [ctx.event_args.get(n) or [] for n in ev_names]
    for i in range(max((len(a) for a in alts), default=0)):
        types = [a[i] for a in alts if i < len(a)]
        name = arg_names.get(i)
        if types and name and name in res:
            res[name] = canon_type("|".join(types))


def _is_event_sym(e: Expr, env: Dict[str, str]) -> bool:
    return isinstance(e, Sym) and (
        e.name in CURRENT_EVENT or env.get(e.name, "").rstrip("?") == "event"
    )


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
        res[cond.name] = strip_nil(res[cond.name]) if truthy else "nil"
        return res
    if isinstance(cond, UnaryOp) and cond.op == "not":
        return _narrow(ctx, cond.operand, env, not truthy, arg_names)
    if isinstance(cond, InOp):
        if truthy and _is_event_sym(cond.subject, res):
            _narrow_event_args(ctx, [a.name for a in cond.alts if isinstance(a, Sym)], res, arg_names)
        return res
    if isinstance(cond, BinOp):
        if cond.op == "and":
            return _narrow(ctx, cond.right, _narrow(ctx, cond.left, env, True, arg_names), True, arg_names) if truthy else res
        if cond.op == "or":
            return res if truthy else _narrow(ctx, cond.right, _narrow(ctx, cond.left, env, False, arg_names), False, arg_names)
        if cond.op in ("==", "!="):
            for a, b in ((cond.left, cond.right), (cond.right, cond.left)):
                if not (isinstance(a, Sym) and a.name in res):
                    continue
                if isinstance(b, Lit) and b.kind == "nil":
                    plain = (cond.op == "!=") == truthy  # `!= nil` really means "not nil"
                    res[a.name] = strip_nil(res[a.name]) if plain else "nil"
                    return res
                if _nonnil(ctx, b):
                    if (cond.op == "==") == truthy:
                        res[a.name] = strip_nil(res[a.name])
                    break
            if cond.op == "==" and truthy and _is_event_sym(cond.left, res) and isinstance(cond.right, Sym):
                _narrow_event_args(ctx, [cond.right.name], res, arg_names)
    return res


def _check_assign_stmt(ctx: Context, s: AssignStmt, env: Dict[str, str], owner: Optional[str]):
    vt = _value_types(ctx, s.values, env, owner)
    if s.op in ("+=", "-="):
        for t in vt:
            expect(ctx, f"'{s.op}'", t, "num", s.line)
    if isinstance(s.target, Sym):
        name = s.target.name
        if name in ctx.globals:
            cur = env.get(name)
        elif name in env:
            cur = env[name]
        elif name.startswith("__"):
            cur = None
        else:
            raise Error(f"unknown name {name!r} (declare it with `local` or `global`)", s.line)
        if cur is not None and s.op == "=" and vt:
            expect(ctx, f"assignment to {name}", vt[0], cur, s.line)
        if cur is not None and s.op in ("+=", "-=") and cur != "any":
            expect(ctx, f"{name} ({s.op})", cur, "num", s.line)
        if cur in (None, "any") and vt and s.op == "=":
            env[name] = vt[0]
    else:
        _check_store(ctx, s.target, vt[0] if vt else "any", env, owner, s.line, s.op)


def _check_return_stmt(ctx: Context, s: ReturnStmt, env: Dict[str, str], owner: Optional[str],
                       rets: Optional[List[str]], fn_decl: Optional[FnDecl]):
    for v in s.values:
        t = _check_expr(ctx, v, env, owner)
        if rets is not None and t != "nil":
            rets.append(t)
    if fn_decl is not None and s.kind == "return" and s.values:
        expected = fn_decl.ret_types
        if len(s.values) > len(expected):
            raise Error(f"fn {fn_decl.name}: returns {len(s.values)} value(s), {len(expected)} declared", s.line)
        for i, v in enumerate(s.values):
            expect(ctx, f"return value {i + 1} of {fn_decl.name}", v.typ, expected[i], s.line)


def _check_stmts(ctx: Context, stmts: List[Stmt], env: Dict[str, str],
                 owner: Optional[str] = None, rets: Optional[List[str]] = None,
                 arg_names: Optional[Dict[int, str]] = None,
                 fn_decl: Optional[FnDecl] = None):
    for s in stmts:
        if isinstance(s, SayStmt):
            expect(ctx, "text to print", _check_expr(ctx, s.expr, env, owner, "str"), "str", s.line)
        elif isinstance(s, ReturnStmt):
            _check_return_stmt(ctx, s, env, owner, rets, fn_decl)
        elif isinstance(s, LocalStmt):
            vts = _value_types(ctx, s.values, env, owner)
            for i, (vn, dt) in enumerate(s.names):
                env[vn] = dt or (vts[i] if i < len(vts) else "any")
        elif isinstance(s, AssignStmt):
            _check_assign_stmt(ctx, s, env, owner)
        elif isinstance(s, CallStmt):
            if s.call.receiver is None:
                _check_value_use(ctx, s.call.func, s.line)
            _check_call(ctx, s.call, env, owner)
        elif isinstance(s, IfStmt):
            cenv = dict(env)
            for cond, body, _l in s.branches:
                _check_cond(ctx, cond, cenv, owner)
                _check_stmts(ctx, body, _narrow(ctx, cond, cenv, True, arg_names), owner, rets, arg_names, fn_decl)
                cenv = _narrow(ctx, cond, cenv, False, arg_names)
            if s.else_body is not None:
                _check_stmts(ctx, s.else_body, cenv, owner, rets, arg_names, fn_decl)
        elif isinstance(s, MatchStmt):
            st = _check_expr(ctx, s.subject, env, owner)
            for pats, guard, body, _l in s.arms:
                aenv = dict(env)
                for p in pats:
                    if not (isinstance(p, Sym) and p.name == "_"):
                        expect(ctx, "match pattern", _check_expr(ctx, p, env, owner, st), st, p.line)
                        aenv = _narrow(ctx, BinOp(line=p.line, op="==", left=s.subject, right=p),
                                       aenv, True, arg_names)
                if guard:
                    _check_cond(ctx, guard, aenv, owner)
                _check_stmts(ctx, body, aenv, owner, rets, arg_names, fn_decl)
        elif isinstance(s, ForNumStmt):
            for bound, what in ((s.start, "start"), (s.stop, "stop"), (s.step, "step")):
                if bound is not None:
                    expect(ctx, f"for bound {what}", _check_expr(ctx, bound, env, owner, "num"), "num", bound.line)
            benv = dict(env)
            benv[s.var] = s.var_type or "num"
            if s.var_type:
                expect(ctx, f"for variable {s.var}", "num", s.var_type, s.line)
            _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl)
        elif isinstance(s, ForInStmt):
            it = _check_expr(ctx, s.iter_expr, env, owner)
            el = tbl_inner(it) or (_root(ctx) if _is_object_type(ctx, it) else "any")
            benv = dict(env)
            for i, (vn, vt) in enumerate(s.vars):
                benv[vn] = vt or ("num" if (s.is_of and len(s.vars) == 2 and i == 0) else el)
            _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl)


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


def _check_fn_target(ctx: Context, ref: FnRef):
    """A `&name` must name a real function.

    An extern is a macro: it is substituted at the call site and never emitted,
    so `&has` would produce a reference to a nonexistent `fn_has` and fail at
    the first call. A plain `lua` function is a real value and stays allowed.
    """
    fn = ctx.fns.get(ref.name)
    if fn is None:
        if ref.name in ctx.lua_funcs:
            return
        raise Error(f"&{ref.name}: unknown function "
                    f"(declare it with `fn` or in a `lua` block)", ref.line)
    if fn.is_extern:
        raise Error(f"&{ref.name}: an extern is a macro, it has no function value "
                    f"(call it directly, or write a `fn` wrapper)", ref.line)


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
    for cname, fields in ctx.prop_decls.items():
        if "n_to" in fields:
            return cname
    return ""   # nothing declared: no kind is room-like


def _inherits(ctx: Context, kind: str, root: str) -> bool:
    """Is `kind` the class `root` or one of its descendants?"""
    return root in _walk_class_chain(ctx, kind)


def _is_object_type(ctx: Context, t: str) -> bool:
    """A declared class (or an instance of one) — the only things with fields."""
    return t in ctx.classes or t in ctx.objects


def _objectish(ctx: Context, t: str) -> bool:
    """Can a value of this type have fields (`x.field`)? Scalars cannot."""
    for alt in split_union(t):
        alt = alt.rstrip("?").strip()
        if alt in ("any", "ref") or alt.startswith("tbl[") or _is_object_type(ctx, alt):
            return True          # dynamic values, references and collections
    return False


def _fields_of(ctx: Context, holder: str) -> Dict[str, Tuple[str, bool]]:
    """Fields known for a holder: its own and inherited, plus (for a class) its
    instances and descendants. Conflicting declarations of one name collapse to
    `any` — that is the dynamic ("duck typing") case."""
    allowed = dict(ctx.fields.get(holder, {}))
    if holder not in ctx.classes:
        return allowed
    others = []
    for name, kind in ctx.objects.items():
        if kind == holder or _inherits(ctx, kind, holder):
            others.append(ctx.fields.get(name, {}))
    for cname in ctx.classes:
        if _inherits(ctx, cname, holder):
            others.append(ctx.fields.get(cname, {}))
    for fmap in others:
        for k, v in fmap.items():
            if k not in allowed:
                allowed[k] = v
            elif allowed[k][0] != v[0]:
                allowed[k] = ("any", False)     # seen with different types: dynamic
    return allowed


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
                 owner: Optional[str], line: int = 0, op: str = "="):
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
    spec = _fields_of(ctx, holder).get(name) if holder else None
    if spec is not None:
        ft, is_ref = spec
        if op in ("+=", "-="):                                # `+=`/`-=` are arithmetic
            if ft not in ("any", "num"):
                raise Error(f"{name}: '{op}' needs a number field (it is {ft})", line)
            return
        if ft != "any":
            expect(ctx, f"{name}", _root(ctx) if (is_ref and vt == "obj") else vt, ft, line)
        return
    if holder is not None and not name.startswith("__"):
        raise Error(f"{holder}.{name}: no such field "
                    f"(nothing declares it for {holder}; use __{name} for a dynamic value)", line)
    if name not in ctx.field_names and name not in ctx.ref_fields:
        raise Error(f"unknown field {name!r} (use __{name} for dynamic values)", line)


def _check_expr(ctx: Context, e: Expr, env: Dict[str, str], owner: Optional[str] = None,
                expected: Optional[str] = None, is_lhs: bool = False) -> str:
    t = _infer(ctx, e, env, owner, expected, is_lhs)
    if expected and not is_lhs:
        expect(ctx, _kind_name(e), t, expected, e.line)
    return t


def _infer_lambda(ctx: Context, e: Lambda, env: Dict[str, str],
                  owner: Optional[str], expected: Optional[str]) -> str:
    fparts = _fn_parts(expected) if expected else None
    eparams, erets = fparts if fparts else ([], [])
    if eparams and len(e.params) > len(eparams):
        raise TypeCheckError(f"&(…): the callback passes {len(eparams)} argument(s), "
                             f"the lambda takes {len(e.params)}", e.line)
    env2 = dict(env)
    ptypes: List[str] = []
    for i, (pn, pt) in enumerate(e.params):
        ept = eparams[i] if i < len(eparams) else None
        if pt is None:
            if not ept:
                raise TypeCheckError(
                    f"&({pn}): annotate the parameter type (`&({pn}: obj)`)", e.line)
            pt = ept
        elif ept and pt != "any" and not is_subtype(ctx, ept, pt):
            raise TypeCheckError(f"&({pn}): the callback passes {ept}, "
                                 f"the lambda declares {pt}", e.line)
        env2[pn] = pt
        ptypes.append(pt)
    if isinstance(e.body, list):
        _check_stmts(ctx, e.body, env2, owner, erets or None)
        if erets and "nil" not in split_union("|".join(erets)) and not _returns_all(e.body):
            raise TypeCheckError(
                f"&(…): the callback returns {'|'.join(erets)}, but some path leaves the body "
                f"without `return` (write an expression body or add `return`)", e.line)
    else:
        _check_expr(ctx, e.body, env2, owner, erets[0] if erets else None)
    e.typ = "fn(" + ",".join(ptypes) + ")" + (("->" + ",".join(erets)) if erets else "")
    return e.typ


def _infer(ctx: Context, e: Expr, env: Dict[str, str], owner: Optional[str] = None,
           expected: Optional[str] = None, is_lhs: bool = False) -> str:
    if isinstance(e, Lit):
        if e.kind == "table":
            e.typ = "tbl"
            return "tbl"
        if e.kind == "num" and expected:
            for alt in split_union(expected):
                if alt in ctx.enums and str(e.val) in ctx.enums[alt][0]:
                    e.typ = alt
                    return alt
        e.typ = "any" if e.kind == "raw" else e.kind
        return e.typ
    if isinstance(e, InterpStr):
        for p in e.parts:
            if isinstance(p, Expr):
                t = _check_expr(ctx, p, env, owner)
                if not is_subtype(ctx, t, "str|num|bool|obj|event") and t != "any":
                    raise TypeCheckError(f"interpolation: expected str, got {t}", p.line)
        e.typ = "str"
        return "str"
    if isinstance(e, Lambda):
        return _infer_lambda(ctx, e, env, owner, expected)
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
            _check_expr(ctx, a, env, owner, st)
        e.typ = "bool"
        return "bool"
    if isinstance(e, FnRef):
        _check_fn_target(ctx, e)
        ctx.used_refs.add(e.name)
        _check_fnref(ctx, e, expected, _kind_name(e))
        e.typ = "fn"
        return "fn"
    if isinstance(e, ListLit):
        in_exp = next((tbl_inner(alt) for alt in (split_union(expected) if expected else [])
                       if tbl_inner(alt) is not None), None)
        its = [_check_expr(ctx, it, env, owner, in_exp) for it in e.items]
        e.typ = f"tbl[{canon_type('|'.join(its)) if its else ''}]"
        return e.typ
    if isinstance(e, Sym):
        return _infer_sym(ctx, e, env, expected, is_lhs)
    if isinstance(e, FieldAccess):
        return _infer_field(ctx, e, env, owner, is_lhs)
    if isinstance(e, IndexAccess):
        ot = _check_expr(ctx, e.obj, env, owner)
        in_exp = tbl_inner(ot)
        if not (_is_object_type(ctx, ot) or ot == "tbl" or in_exp is not None):
            expect(ctx, "index", ot, "tbl", e.line)
        _check_expr(ctx, e.index, env, owner, None)
        base = in_exp if in_exp is not None else (
            _root(ctx) if _is_object_type(ctx, ot) else "any")
        e.typ = base if base in ("any", "nil") or base.endswith("?") else base + "?"
        return e.typ
    if isinstance(e, UnaryOp):
        if e.op == "-" and isinstance(e.operand, Lit) and e.operand.kind == "str":
            e.typ = "str"
            return "str"
        _check_expr(ctx, e.operand, env, owner, None if e.op == "not" else "num")
        e.typ = "bool" if e.op == "not" else "num"
        return e.typ
    if isinstance(e, BinOp):
        return _infer_binop(ctx, e, env, owner)
    if isinstance(e, Call):
        return _check_call(ctx, e, env, owner)
    return "any"


def _infer_sym(ctx: Context, e: Sym, env: Dict[str, str],
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
    enum = ctx.enum_owner.get(n.lstrip("~"))
    if enum:
        e.rk, e.typ = "enum", enum
        return e.typ
    if n in ctx.fns or n in ctx.lua_funcs:
        sig = ctx.fns.get(n)
        e.rk = "value" if (sig and sig.is_value) else "fn0"
        e.typ = sig.ret_types[0] if (sig and sig.ret_types) else "any"
        return e.typ
    if n in ctx.lua_globals:
        e.rk, e.typ = "lua_global", ctx.lua_globals[n].typ
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
    if holder is not None and not e.field.startswith("__"):
        spec = _fields_of(ctx, holder).get(e.field)
        if spec is None:
            raise Error(f"{holder}.{e.field}: no such field "
                        f"(nothing declares it for {holder}; use __{e.field} for a dynamic value)",
                        e.line)
        e.is_ref, e.typ = spec[1], spec[0]
        return spec[0]
    if e.field in ctx.field_names:
        e.typ = "any"
        return "any"
    if e.field.startswith("__"):
        e.typ = "any"
        return "any"
    raise Error(f"unknown field {e.field!r} (use __{e.field} for dynamic values)", e.line)


def _infer_binop(ctx: Context, e: BinOp, env: Dict[str, str], owner: Optional[str]) -> str:
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
    is_method = c.receiver is not None
    all_args = ([c.receiver] + c.args) if is_method else list(c.args)
    label = f"{_kind_name(c.receiver)}:{c.func}" if is_method else c.func
    # a local or a parameter of function type shadows a global `fn` of that name
    shadowed = not is_method and env.get(c.func, "").startswith("fn")
    fn = None if shadowed else ctx.fns.get(c.func)

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


def _type_alt_ok(ctx: Context, alt: str) -> bool:
    """Is this single type alternative known? `ref[C]` takes declared classes only."""
    alt = alt.rstrip("?").strip()
    inner = tbl_inner(alt)
    if inner is not None:
        return all(_type_alt_ok(ctx, a) for a in split_union(inner)) if inner else True
    ref_in = _ref_inner(alt)
    if ref_in is not None:
        return bool(ref_in) and all(a.rstrip("?").strip() in ctx.classes
                                    for a in split_union(ref_in))
    if alt in PRIMITIVES or alt in ctx.enums or alt in ctx.classes or alt == "nil":
        return True
    return alt.startswith("fn(")


def _check_type(ctx: Context, typ: str, where: str, line: int, label: str = "type"):
    """A declared type must name known classes and primitives (`ref[C]`: C is a class)."""
    for alt in split_union(typ):
        if _type_alt_ok(ctx, alt):
            continue
        raise Error(f"{where}: unknown {label} {alt!r}", line)


def _check_signature(ctx: Context, fn: FnDecl):
    """Unknown types or a required parameter after an optional one."""
    if fn.is_extern:
        return
    seen_optional = False
    for pname, ptype in fn.params:
        _check_type(ctx, ptype, f"fn {fn.name}({pname})", fn.line)
        optional = ptype == "nil" or ptype.endswith("?")
        if seen_optional and not optional:
            raise Error(f"fn {fn.name}: required parameter {pname!r} after an optional one", fn.line)
        seen_optional = seen_optional or optional
    for rt in fn.ret_types:
        _check_type(ctx, rt, f"fn {fn.name}", fn.line, "return type")


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


def _class_methods(ctx: Context, cls: str) -> Dict[str, Prop]:
    """Fields a class (and its ancestors) declare as functions."""
    methods: Dict[str, Prop] = {}
    for cur in _walk_class_chain(ctx, cls):
        cdecl = ctx.class_decls.get(cur)
        if cdecl is not None:
            for p in cdecl.props:
                if isinstance(p.value, (list, FnRef)) \
                        or (isinstance(p.value, Lit) and p.value.kind == "lua"):
                    methods.setdefault(p.name, p)
    return methods


def _check_override(ctx: Context, ent: EntityDecl):
    """An instance must not replace a class method with a plain value (STEAD3 crashes)."""
    if ent.kind == "impl" or ent.name is None:
        return
    bases = ([ent.kind] if ent.kind != "class" else []) + list(ent.traits)
    if ent.kind == "class" and ent.parent:
        bases.append(ent.parent)
    methods: Dict[str, Prop] = {}
    for base in bases:
        methods.update(_class_methods(ctx, base))
    for p in ent.props:
        if p.name in methods and p.value is not None \
                and not isinstance(p.value, (list, FnRef)) \
                and not (isinstance(p.value, Lit) and p.value.kind == "lua"):
            base = next(b for b in bases if p.name in _class_methods(ctx, b))
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
    if isinstance(cond, BinOp) and cond.op in ("and", "or"):
        _check_cond(ctx, cond.left, env, owner)
        return _check_cond(ctx, cond.right, _narrow(ctx, cond.left, env, cond.op == "and"), owner)
    _check_expr(ctx, cond, env, owner)


def _check_handler_events(ctx: Context, h: Handler, where: str):
    """A handler phase must name a declared event."""
    import difflib
    for ev in h.events:
        if ev in ctx.event_names:
            continue
        near = difflib.get_close_matches(ev, sorted(ctx.event_names), 1, 0.7)
        hint = f" (did you mean {near[0]!r}?)" if near else ""
        raise Error(f"{where}: unknown event {ev!r}{hint}", h.line)
