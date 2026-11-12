"""Minimalist symbol collector and type checker for MISE 2."""
import difflib
import os
import re
from itertools import zip_longest
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple
from . import types
from .ast_nodes import *
from .parser import PHASES, parse_source
from .types import ANY, NIL, Fn, Name, Ref, Tbl, Type, \
    opt, parts, ref_inner, union, without_nil

STR, NUM, BOOL, EVENT = Name("str"), Name("num"), Name("bool"), Name("event")
TBL = Tbl(None)          # a bare table: no element type

_SLOT_OBJ_RE = re.compile(r"\{(?:noun|noun_obj|compass\w*)\}")
CURRENT_EVENT = frozenset({"ev", "event"})
READONLY_FIELDS = frozenset({"nam"})
ENGINE_OBJECTS = frozenset({"player"})
BUILTIN_TARGETS = frozenset({"game", "pl", "mp"})


class TypeCheckError(Error):
    """A value cannot be used where its declared type is expected."""


@dataclass
class Context:
    lang: str = "ru"
    enums: Dict[str, Tuple[Set[str], bool]] = field(default_factory=dict)  # name -> (values, negate)
    enum_owner: Dict[str, str] = field(default_factory=dict)   # value -> its type
    event_names: Set[str] = field(default_factory=set)
    event_args: Dict[str, List[Type]] = field(default_factory=dict)
    event_acted: Set[str] = field(default_factory=set)   # the action takes an acted object

    classes: Dict[str, str] = field(default_factory=dict)                  # class -> parent
    class_decls: Dict[str, EntityDecl] = field(default_factory=dict)
    entity_of: Dict[str, EntityDecl] = field(default_factory=dict)   # an object by name
    objects: Dict[str, str] = field(default_factory=dict)                  # id -> kind/class
    fields: Dict[str, Dict[str, Type]] = field(default_factory=dict)
    prop_decls: Dict[str, Dict[str, Prop]] = field(default_factory=dict)   # declared class fields
    ctors: Dict[str, str] = field(default_factory=dict)                  # class -> engine constructor
    root_class: Optional[str] = None                                     # the first class with no parent
    field_names: Set[str] = field(default_factory=set)
    entries: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)  # engine entry points

    fns: Dict[str, FnDecl] = field(default_factory=dict)
    verb_tags: Set[str] = field(default_factory=set)     # tags of `verb`/`extend verb`
    used_refs: Set[str] = field(default_factory=set)
    lua_funcs: Set[str] = field(default_factory=set)
    globals: Dict[str, Type] = field(default_factory=dict)
    consts: Set[str] = field(default_factory=set)
    _checked_fns: Set[str] = field(default_factory=set)
    _checking_fns: Set[str] = field(default_factory=set)


# --- Type compatibility -----------------------------------------------------

PRIMITIVES = frozenset({"str", "num", "bool", "any", "event", "tbl", "nil", "ref"})
_KINDS = {"str": STR, "num": NUM, "bool": BOOL, "nil": NIL, "raw": ANY, "table": TBL}
_PRINTABLE = union(STR, NUM, BOOL, Name("obj"), EVENT)
_CONCAT = union(STR, NUM)
_HANDLER_VALUE = union(STR, BOOL, Name("fn"))


def _atom_fits(ctx: Context, actual: Type, expected: Type) -> bool:
    """Can a single (non-union) value type be used where `expected` is wanted?"""
    if expected == ANY or actual == expected:
        return True
    if actual == ANY:
        return False  # `any` never silently narrows into a concrete type
    if isinstance(expected, Ref):
        if actual == STR:
            return True
        got = ref_inner(actual)
        if got is not None:
            return _obj_fits(ctx, got, expected.name)
        return isinstance(actual, Name) and _is_object_type(ctx, actual) \
            and _obj_fits(ctx, actual.name, expected.name)
    got_ref = ref_inner(actual)
    if got_ref is not None:                # a reference where a plain object is wanted
        return _obj_fits(ctx, got_ref, getattr(expected, "name", str(expected)))
    if isinstance(expected, Name) and expected.name in ctx.classes:
        return isinstance(actual, Name) and _inherits(ctx, actual.name, expected.name)
    if expected == STR and isinstance(actual, Name) \
            and (actual.name in ctx.enums or actual.name == "event"):
        return True    # an enum value or an event is a string in the engine
    if types.is_tbl(expected):
        ie = types.tbl_inner(expected)
        if types.is_tbl(actual):
            ia = types.tbl_inner(actual)
            return ia is None or ie is None or _is_empty_collection(actual) \
                or is_subtype(ctx, ia, ie)
        return ie is None and _is_object_type(ctx, actual)
    if isinstance(expected, Fn):
        if not isinstance(actual, Fn):
            return str(actual) == "fn"
        return len(actual.params) <= len(expected.params) \
            and all(ep == ANY or is_subtype(ctx, ep, ap)
                    for ep, ap in zip(expected.params, actual.params)) \
            and (not actual.rets or not expected.rets or actual.rets == (ANY,)
                 or all(is_subtype(ctx, ar, er) for er, ar in zip(expected.rets, actual.rets)))
    return False


def _obj_fits(ctx: Context, actual_name: str, expected_name: str) -> bool:
    """`actual` is an object class/name that must fit `expected` (`A|B`, a class)."""
    if not expected_name or expected_name == "obj":
        return True
    if not actual_name:                    # a bare `ref`: some object, but which one?
        return False
    actual_name = str(without_nil(types.parse(actual_name) if isinstance(actual_name, str)
                                  else actual_name))
    return any(a in ("obj", "") or _inherits(ctx, actual_name, a)
               for a in (p.strip() for p in expected_name.split("|")))


def is_subtype(ctx: Context, actual: Type, expected: Type) -> bool:
    """Does every alternative of `actual` fit some alternative of `expected`?"""
    return expected == ANY or actual == expected \
        or all(any(_atom_fits(ctx, a, e) for e in parts(expected)) for a in parts(actual))


def _kind_name(expr: Expr) -> str:
    """A short human-readable description of an expression for diagnostics."""
    if isinstance(expr, Sym):
        return expr.name
    if isinstance(expr, Lit):
        return "`lua`" if expr.kind == "raw" else ("{…}" if expr.kind == "table" else str(expr.val))
    if isinstance(expr, FieldAccess):
        return f"{_kind_name(expr.obj)}.{expr.field}"
    if isinstance(expr, IndexAccess):
        return f"{_kind_name(expr.obj)}[…]"
    if isinstance(expr, Call):
        recv = f"{_kind_name(expr.receiver)}:" if expr.receiver is not None else ""
        return f"{recv}{expr.func or 'call'}()"
    return "expression"


def need_value(t: Type, where: str, line: int) -> None:
    """Fail unless a maybe-nil value was narrowed before use."""
    if types.is_optional(t):
        hint = f" (`if {where}:`)" if where.isidentifier() else ""
        raise TypeCheckError(f"{where}: possible nil, narrow it first{hint}", line)


def expect(ctx: Context, where: str, actual: Type, expected: Optional[Type], line: int = 0):
    """Report a type mismatch unless `actual` can be used as `expected`."""
    if expected is None or expected == ANY or is_subtype(ctx, actual, expected):
        return
    if types.is_optional(actual) and not types.is_optional(expected):
        need_value(actual, where, line)
    raise TypeCheckError(f"{where}: expected {expected}, got {actual}", line)


def _close_hint(word: str, pool: Iterable[str], fmt: Callable[[str], str],
                cutoff: float = 0.7) -> str:
    near = difflib.get_close_matches(word, sorted(pool), 1, cutoff)
    return fmt(near[0]) if near else ""


def _enum_value(ctx: Context, name: str, enum: str) -> Optional[str]:
    vals, neg = ctx.enums.get(enum, (set(), False))
    bare = name[1:] if (name.startswith("~") and neg) else name
    return enum if bare in vals else None


def _enum_hint(ctx: Context, name: str) -> str:
    candidates = {v for vals, _neg in ctx.enums.values() for v in vals}
    return _close_hint(name.lstrip("~"), candidates, lambda m: f" (did you mean {m!r}?)")


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
            merged.extend(load_includes(sub, os.path.dirname(p)).items)
    prog.items = merged + prog.items
    return prog


def _verb_tag(item: VerbDecl) -> str:
    return item.tag if item.tag is not None else (
        item.name if item.name.startswith("#") else f"#{item.name}")


def _verb_pat_sig(pat: str, obj_type: Type = Name("obj")) -> Optional[Tuple[str, List[Type], bool]]:
    if ":" not in pat:
        return None
    lhs, rhs = pat.rsplit(":", 1)
    ev_parts = rhs.strip().split()
    if not ev_parts:
        return None
    toks = lhs.strip().split()
    if toks and toks[0] == "~":
        toks = toks[1:]
    slot_toks = [t for t in toks if _SLOT_OBJ_RE.search(t) or t in ("*", "~*")]
    first = slot_toks[0] if slot_toks else ""
    acted = bool(_SLOT_OBJ_RE.search(first)) and not first.startswith("~")
    slots = [obj_type if _SLOT_OBJ_RE.search(t) else STR for t in slot_toks]
    if len(ev_parts) > 1 and ev_parts[1] == "reverse" and len(slots) >= 2:
        slots[0], slots[1] = slots[1], slots[0]
    return ev_parts[0], slots, acted


def prescan(prog: Program) -> Context:
    ctx = Context(lang=prog.lang)
    base_evs, class_at = _collect_declarations(ctx, prog)
    _register_entities(ctx, prog, class_at)
    _resolve_verb_events(ctx, prog, base_evs)   # events from patterns are known after this
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
    ctx.classes.setdefault(item.name, item.name if external else (item.parent or ctx.root_class or item.name))
    class_at.setdefault(item.name, idx)
    if item.name in ctx.class_decls:
        ctx.class_decls[item.name].props.extend(item.props)
    else:
        ctx.class_decls[item.name] = item
    for p in item.props:
        ctx.field_names.add(p.name)
        if p.typ:
            prev_p = ctx.prop_decls.setdefault(item.name, {}).get(p.name)
            if prev_p is not None and p.emit is None and prev_p.emit is not None:
                p.emit = prev_p.emit
            if prev_p is not None and prev_p.typ is not None and prev_p.typ != p.typ:
                raise Error(f"class {item.name}: field {p.name!r} is already declared as "
                            f"{prev_p.typ}, here as {p.typ}", p.line)
            ctx.prop_decls[item.name][p.name] = p
            p.is_ref = _is_ref_type(ctx, p.typ)


def _fn_clashes_enum(fn: FnDecl) -> bool:
    """User functions and 0-ary externs collide with bare enum values."""
    return not fn.is_extern or all(types.is_optional(pt) for _pn, pt in fn.params)


def _collect_declarations(ctx: Context, prog: Program) -> Tuple[Dict[str, List[Type]], Dict[str, int]]:
    class_at: Dict[str, int] = {}
    decl_evs: Dict[str, List[Type]] = {}
    ext_evs: Dict[str, Tuple[List[Type], int]] = {}
    for idx, item in enumerate(prog.items):
        if isinstance(item, EventsDecl):
            for evs, ats in item.sigs:
                for at in ats:
                    _check_type(ctx, at, f"event {evs[0]}", item.line, "argument type")
                for ev in evs:
                    ctx.event_names.add(ev)
                    if ev in ctx.fns:
                        raise Error(f"event {ev}: a fn has the same name "
                                    f"(a bare name would mean the event)", item.line)
                    if item.extend:
                        ext_evs[ev] = (list(ats), item.line)
                    else:
                        prev = decl_evs.get(ev)
                        if prev is not None and prev != list(ats):
                            raise Error(f"event {ev}: declared with {_sig_text(prev)}, "
                                        f"here with {_sig_text(list(ats))} "
                                        f"(use `extend event` to replace)", item.line)
                        decl_evs[ev] = list(ats)
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
                if v in ctx.fns and _fn_clashes_enum(ctx.fns[v]):
                    raise Error(f"type {item.name}: fn {v!r} has the same name "
                                f"(a bare name would mean the enum value)", item.line)
                ctx.enum_owner[v] = item.name
        elif isinstance(item, FnDecl):
            if item.name in ctx.fns:
                raise Error(f"duplicate fn {item.name!r}", item.line)
            if item.name in ctx.event_names:
                raise Error(f"fn {item.name}: an event has the same name "
                            f"(a bare name would mean the event)", item.line)
            if item.name in ctx.enum_owner and _fn_clashes_enum(item):
                raise Error(f"fn {item.name}: a value of type {ctx.enum_owner[item.name]!r} "
                            f"has the same name (a bare name would mean the enum value)", item.line)
            ctx.fns[item.name] = item
        elif isinstance(item, EntryDecl):
            ctx.entries[item.name] = list(item.params)
        elif isinstance(item, VerbDecl) and item.mode == "verb":
            ctx.verb_tags.add(_verb_tag(item) or f"#{item.name}")
        elif isinstance(item, LuaDecl):
            ctx.lua_funcs.update(re.findall(r"\bfunction\s+([A-Za-z_]\w*)", item.code))
        elif isinstance(item, EntityDecl) and item.kind == "class" and item.name:
            _register_class_decl(ctx, item, idx, class_at)
    for ev, (ats, line) in ext_evs.items():
        if ev not in decl_evs:
            raise Error(f"extend event {ev}: unknown event (declare it with `event {ev}`)", line)
        decl_evs[ev] = ats
    return decl_evs, class_at


def _declare_object(ctx: Context, name: str, kind: str, line: int):
    prev = ctx.objects.get(name)
    if prev is not None and prev != kind:
        raise Error(f"{name}: already declared as {prev}, here as {kind}", line)
    if name in ctx.classes:
        raise Error(f"{name}: an object cannot share the name of a class", line)
    ctx.objects[name] = kind


def _check_class_order(ent: EntityDecl, idx: int, class_at: Dict[str, int]):
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
    exp_p, exp_h, kept_tr = [], [], []
    for tr in ent.traits:
        cdecl = ctx.class_decls.get(tr)
        if cdecl and tr not in instantiated_classes:
            exp_p.extend(p for p in cdecl.props if p.value is not None)
            exp_h.extend(cdecl.handlers)
            kept_tr.extend(t for t in cdecl.traits if t not in kept_tr)
        if tr not in kept_tr:
            kept_tr.append(tr)
    ent.traits = kept_tr
    own_p = {p.name for p in ent.props}
    own_h = {(h.phase, tuple(h.events)) for h in ent.handlers}
    ent.props = [p for p in exp_p if p.name not in own_p] + ent.props
    ent.handlers = [h for h in exp_h if (h.phase, tuple(h.events)) not in own_h] + ent.handlers


def _no_duplicates(names: Iterable[str], what: str, line: int):
    seen: Set[str] = set()
    for n in names:
        if n in seen:
            raise Error(f"{what} {n!r}: declared twice", line)
        seen.add(n)


def _known_target(ctx: Context, name: str, allow_engine: bool = False) -> bool:
    return (name in BUILTIN_TARGETS or name.startswith("@")
            or name in ctx.objects or name in ctx.classes
            or (allow_engine and name in ENGINE_OBJECTS))


def _register_entity(ctx: Context, ent: EntityDecl, idx: int,
                     class_at: Dict[str, int], instantiated_classes: Set[str]):
    _check_class_order(ent, idx, class_at)
    if ent.kind == "class" and ent.parent and ent.parent not in ctx.classes:
        raise Error(f"class {ent.name or ''}({ent.parent}): unknown parent class", ent.line)
    _check_override(ctx, ent)      # before mixin traits are inlined into the entity
    if ent.kind == "impl" and ent.name == "mp":
        ctx.event_names.update(ent.traits)
    _inline_mixin_traits(ctx, ent, instantiated_classes)
    if ent.kind not in ("class", "impl"):
        if ent.kind not in ctx.classes:
            raise Error(f"unknown kind {ent.kind!r}{_kind_hint(ctx, ent)}", ent.line)
        if ent.name and not ent.name.startswith("#") and ent.name in ctx.objects:
            raise Error(f"duplicate declaration {ent.name!r}", ent.line)
        if ent.name:
            _declare_object(ctx, ent.name, ent.kind, ent.line)
            ctx.entity_of[ent.name] = ent
    if ent.kind == "impl" and ent.name and not _known_target(ctx, ent.name, allow_engine=True):
        raise Error(f"impl {ent.name!r}: unknown target", ent.line)
    for ch in ent.children:
        _register_entity(ctx, ch, idx, class_at, instantiated_classes)


def _register_entities(ctx: Context, prog: Program, class_at: Dict[str, int]):
    instantiated = {it.kind for it in prog.items if isinstance(it, EntityDecl)}
    for idx, item in enumerate(prog.items):
        if isinstance(item, EntityDecl):
            _register_entity(ctx, item, idx, class_at, instantiated)
        elif isinstance(item, TalkDecl):
            _declare_object(ctx, item.name, "talk", item.line)
            ctx.field_names.update(p.name for p in item.props)


def _check_callable_part(ctx: Context, part: Any, env: Dict[str, Type], owner: Optional[str],
                         want: Optional[Type], where: str, line: int,
                         arg_names: Optional[Dict[int, str]] = None):
    """Check a handler/talk/prop/hint body (`FnRef`, block of `Stmt`, or `Expr`)."""
    if isinstance(part, FnRef):
        _check_fnref(ctx, part, want, where)
    elif isinstance(part, list):
        rets: List[Type] = []
        _check_stmts(ctx, part, dict(env), owner, rets, arg_names)
        returns = types.fn_returns(want) if want is not None else ()
        for t in (rets if returns else ()):
            expect(ctx, where, t, union(*returns), line)
    elif isinstance(part, Expr):
        _check_expr(ctx, part, dict(env), owner, want)


def _check_verb(ctx: Context, item: VerbDecl):
    if item.mode == "extend":
        tag = _verb_tag(item) or f"#{item.name}"
        base = tag.lstrip("#")
        if base not in ctx.event_names and tag not in ctx.verb_tags:
            raise Error(f"extend verb {tag}: unknown verb "
                        f"(declare it with `verb {base}` first)", item.line)
    if item.target and not _known_target(ctx, item.target):
        raise Error(f"verb {item.name.split('#')[-1]}: unknown target {item.target!r}",
                    item.line)
    if item.hint is not None:
        where = f"verb {item.name.split('#')[-1]}: hint"
        want = Fn((Name(_root(ctx)),), (STR,)) if not isinstance(item.hint, Expr) else _HANDLER_VALUE
        _check_callable_part(ctx, item.hint, {"s": Name(_root(ctx))}, None, want, where, item.line)


def _resolve_verb_events(ctx: Context, prog: Program, base_evs: Dict[str, List[Type]]):
    active_verbs: Dict[str, List[Tuple[str, List[Type], int]]] = {}
    for item in prog.items:
        if not isinstance(item, VerbDecl):
            continue
        tag = _verb_tag(item)
        if item.mode == "verb" and not item.patterns:
            raise Error(f"verb {item.name}: no patterns — the engine needs at least one "
                        f"(write `patterns = [\"{{noun}}/вн : {item.name.lstrip('#')}\"]`)",
                        item.line)
        if item.mode == "remove":
            active_verbs.pop(tag, None)
            continue
        contribs = active_verbs.setdefault(tag, [])
        for pat in item.patterns:
            ps = _verb_pat_sig(pat, Name(_root(ctx)))
            if ps:
                ctx.event_names.add(ps[0])
                if ps[2]:
                    ctx.event_acted.add(ps[0])
                contribs.append((ps[0], ps[1], item.line))

    ctx.event_args = {k: list(v) for k, v in base_evs.items()}
    for ev, sigs in base_evs.items():
        first = without_nil(sigs[0]) if sigs else None
        if isinstance(first, Name) and (first.name.startswith("obj") or first.name in ctx.classes):
            ctx.event_acted.add(ev)
    for contribs in active_verbs.values():
        for ev, slots, line in contribs:
            if ev in base_evs:
                declared = base_evs[ev]
                if len(slots) != len(declared):
                    raise Error(f"verb pattern for {ev}: {len(slots)} argument(s), "
                                f"the event declares {len(declared)}", line)
                for i, (got, want) in enumerate(zip(slots, declared)):
                    if not is_subtype(ctx, got, want):
                        raise Error(f"verb pattern for {ev}: argument {i + 1} is {got}, "
                                    f"the event declares {want}", line)
            elif ev not in ctx.event_args:
                ctx.event_args[ev] = list(slots)
            else:
                ctx.event_args[ev] = [union(a or NIL, b or NIL)
                                      for a, b in zip_longest(ctx.event_args[ev], slots)]


def _decl_of(ctx: Context, target: Any, name: str) -> Optional[Prop]:
    ent = ctx.entity_of.get(target) if isinstance(target, str) else target
    if ent is None:
        return _decl_prop(ctx, ctx.objects.get(target, target), name)
    scopes = ([ent.name or "", ent.parent] if ent.kind == "class"
              else [_entity_kind(ctx, ent)]) + list(ent.traits)
    orig = ctx.entity_of.get(ent.name or "") if ent.kind == "impl" else None
    if orig is not None:
        scopes += [orig.kind] + list(orig.traits)
    return next((d for s in scopes if s in ctx.classes for d in (_decl_prop(ctx, s, name),) if d), None)


def _collect_entity_fields(ctx: Context, ent: EntityDecl):
    attrs = ctx.enums.get("attr", (set(), False))[0]
    for loc in ent.locations:
        if loc not in ctx.objects and loc not in ctx.classes:
            raise Error(f"{ent.name or ent.kind}: unknown location {loc!r} "
                        f"(declare it above)", ent.line)
    for tr in ent.traits:
        base = tr.lstrip("~")
        if base not in ctx.classes and base not in attrs \
                and not (ent.kind == "impl" and base in ctx.event_names):
            raise Error(f"{ent.name or ent.kind}: unknown trait {tr!r} (a class, "
                        f"a `type attr` value or, for `impl`, an event)", ent.line)
    ctx.field_names.update(p.name for p in ent.props)
    fmap = ctx.fields.setdefault(ent.name, {}) if ent.name else {}
    base = ent.parent if ent.kind == "class" else ent.kind
    for src in [base] + [tr for tr in ent.traits if tr in ctx.classes]:
        for k, v in ctx.fields.get(src, {}).items():
            fmap.setdefault(k, v)
    for p in ent.props:
        if p.typ:
            _check_type(ctx, p.typ, f"{ent.name or ''}.{p.name}".lstrip("."), p.line)
        decl = _decl_of(ctx, ent, p.name)
        if decl is not None:
            p.typ = p.typ or decl.typ
            p.emit = p.emit or decl.emit
            p.type_params = p.type_params or decl.type_params
        p.is_ref = bool(p.typ and _is_ref_type(ctx, p.typ))
        if p.value is not None and ent.name:
            if isinstance(p.value, Expr) and not isinstance(p.value, (FnRef, Lambda)):
                vt = _lit_type(ctx, p.value)
                if p.typ is not None and (vt == ANY or _is_empty_collection(vt)):
                    vt = p.typ                  # `items = []` keeps `items: tbl[T]`
            else:
                vt = p.typ if p.typ is not None else Name("fn")
            fmap[p.name] = vt
        elif p.typ and ent.name:
            fmap[p.name] = p.typ
    for ch in ent.children:
        _collect_entity_fields(ctx, ch)


def _collect_fields_and_refs(ctx: Context, prog: Program):
    for item in prog.items:
        if isinstance(item, VerbDecl):
            _check_verb(ctx, item)
        elif isinstance(item, VarDecl):
            for vn, vt, ve, vl in item.items:
                if vn in ctx.globals:
                    raise Error(f"global {vn}: declared twice", vl)
                if vn in ctx.objects or vn in ctx.classes:
                    raise Error(f"global {vn}: an object or a class has this name", vl)
                got = _lit_type(ctx, ve)
                if vt is not None:
                    _check_type(ctx, vt, f"global {vn}", vl)
                    if got != ANY:
                        expect(ctx, f"global {vn}", got, vt, vl)
                if isinstance(ve, Sym) and not ve.rk:
                    raise Error(f"{vn}: unknown name {ve.name!r}", vl)
                ctx.globals[vn] = vt if vt is not None else got
                if item.kind == "const":
                    ctx.consts.add(vn)
        elif isinstance(item, EntityDecl):
            _collect_entity_fields(ctx, item)
        elif isinstance(item, TalkDecl):
            own = ctx.fields.setdefault(item.name, {})
            for p in item.props:
                own[p.name] = _lit_type(ctx, p.value) if isinstance(p.value, Expr) else Name("fn")
            for name, spec in ctx.fields.get("talk", {}).items():
                own.setdefault(name, spec)


def _ensure_fn_checked(ctx: Context, fn: Optional[FnDecl]):
    if fn is not None and not fn.is_extern and not fn.ret_types \
            and fn.name not in ctx._checked_fns and fn.name not in ctx._checking_fns:
        _typecheck_fn(ctx, fn)


def _typecheck_fn(ctx: Context, item: FnDecl):
    if item.name in ctx._checked_fns or item.name in ctx._checking_fns:
        return
    ctx._checking_fns.add(item.name)
    try:
        if item.name in ctx.entries:
            want = ctx.entries[item.name]
            if len(item.params) != len(want):
                raise Error(f"entry {item.name}: the engine calls it with "
                            f"{len(want)} argument(s), declared {len(item.params)}", item.line)
        _check_signature(ctx, item)
        if item.is_extern or not isinstance(item.body, list):
            return
        env = dict(item.params)
        if item.variadic is not None:
            env["..."] = item.variadic
        owner = item.params[0][1] if (item.params and item.params[0][0] == "s" and item.params[0][1] in ctx.classes) else None
        rets: List[Type] = []
        _check_stmts(ctx, item.body, env, owner, rets, fn_decl=item if item.ret_types else None)
        falls_through = bool(item.body) and not _returns_all(item.body)
        if item.ret_types:
            if falls_through and not types.is_optional(union(*item.ret_types)):
                raise Error(f"fn {item.name}: {', '.join(str(t) for t in item.ret_types)} is declared, but a "
                            f"path leaves the body without `return` (add `return` or `pass`, "
                            f"or declare `{without_nil(item.ret_types[0])}?`)", item.line)
        else:
            if rets and falls_through:
                rets.append(NIL)
            item.ret_types = [union(*rets)] if rets else [ANY]
    finally:
        ctx._checking_fns.discard(item.name)
        ctx._checked_fns.add(item.name)


def _typecheck_program(ctx: Context, prog: Program):
    for item in prog.items:
        if isinstance(item, FnDecl):
            _typecheck_fn(ctx, item)
    for item in prog.items:
        if isinstance(item, VarDecl):
            for vn, vt, ve, vl in item.items:
                if not (isinstance(ve, Sym) and ve.rk in ("obj", "event", "enum")):
                    got = _check_expr(ctx, ve, {}, None, vt)
                    if vt is None:
                        ctx.globals[vn] = got
        elif isinstance(item, EntityDecl):
            _check_entity(ctx, item)
        elif isinstance(item, TalkDecl):
            _check_talk(ctx, item)


def _lit_type(ctx: Context, e: Expr) -> Type:
    if isinstance(e, Lit):
        return _KINDS.get(e.kind, ANY)
    if isinstance(e, InterpStr):
        return STR
    if isinstance(e, Sym):
        if e.name in ctx.objects:
            e.rk = "obj"
            return Name(ctx.objects[e.name])
        if e.name in ctx.globals:
            gt = ctx.globals[e.name]
            e.rk = "global_ref" if _is_scalar_ref(ctx, gt) else "global"
            return gt
        if e.name in ctx.event_names:
            e.rk = "event"
            return EVENT
        enum = ctx.enum_owner.get(e.name.lstrip("~"))
        if enum:
            e.rk = "enum"
            return Name(enum)
        fn = ctx.fns.get(e.name)
        if fn is not None and all(types.is_optional(pt) for _pn, pt in fn.params):
            e.rk = "value" if fn.is_value else "fn0"
            return fn.ret_types[0] if fn.ret_types else ANY
    if isinstance(e, ListLit):
        return Tbl(union(*(_lit_type(ctx, it) for it in e.items)) if e.items else Name(""))
    return ANY


def _check_ref_prop(ctx: Context, where: str, p: Prop):
    if not p.is_ref or p.value is None or isinstance(p.value, (list, FnRef, Lambda)):
        return
    val = p.value
    if isinstance(val, Lit) and val.kind == "str":
        raise Error(f"{where}: object reference must be a bare name, not a quoted string "
                    f"({val.val!r})", p.line)
    for it in (val.items if isinstance(val, ListLit) else [val]):
        if isinstance(it, Lit) and it.kind == "str" and isinstance(val, ListLit):
            name = it.val.strip()
            if name not in ctx.objects:
                raise Error(f"{where}: unknown object reference {name!r}", it.line or p.line)
        elif isinstance(it, Sym):
            name = it.name
            if (name not in ctx.objects and name not in ctx.globals
                    and name not in ctx.fns and name not in ctx.lua_funcs):
                raise Error(f"{where}: unknown object reference {name!r}", it.line or p.line)
        elif isinstance(it, (UnaryOp, BinOp)) and getattr(it, "op", "") not in ("and", "or"):
            raise Error(f"{where}: expected object reference, got expression", p.line)


def _is_scalar_ref(ctx: Context, typ: Type) -> bool:
    return any(isinstance(alt, Ref) or _is_object_type(ctx, alt) for alt in parts(typ))


def _is_ref_type(ctx: Context, typ: Type) -> bool:
    return any(_is_scalar_ref(ctx, types.tbl_inner(alt) or alt) for alt in parts(typ))


def _kind_hint(ctx: Context, ent: EntityDecl) -> str:
    if ent.name in ctx.event_names:
        h = _close_hint(ent.kind, PHASES, lambda m: f" (did you mean `{m} {ent.name}`?)", 0.75)
        if h:
            return h
    if ent.kind in ctx.field_names:
        return f" (did you mean `{ent.kind} = ...`?)"
    return _close_hint(ent.kind, ctx.classes, lambda m: f" (did you mean class {m!r}?)", 0.75)


def _walk_class_chain(ctx: Context, kind: str) -> List[str]:
    chain: List[str] = []
    cur, seen = kind, set()
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = ctx.classes.get(cur)
    return chain


def _decl_prop(ctx: Context, kind: str, name: str) -> Optional[Prop]:
    return next((ctx.prop_decls[c][name] for c in _walk_class_chain(ctx, kind)
                 if name in ctx.prop_decls.get(c, {})), None)


def _prop_body_env(ctx: Context, p: Prop) -> Dict[str, Type]:
    """Parameters of a prop body, taken from the declared `fn(...)` of the field."""
    names = list(p.type_params or [])
    if p.params is None and names:
        p.params = names
    one = types.fn_of(p.typ) if p.typ is not None else None
    env = {(names[i] if i < len(names) and names[i] else f"_{i}"): t
           for i, t in enumerate(one.params if one else ())}
    env.setdefault("s", Name(_root(ctx)))
    for pn in p.params or ():
        env.setdefault(pn, ANY)
    return env


def _check_emit(where: str, emit: Emit, value: Any, line: int):
    """A method-emitted field takes the value shape its form needs."""
    if emit.form == "none":
        if not (isinstance(value, Lit) and value.kind == "bool"):
            raise TypeCheckError(f"{where}: `:{emit.method}()` takes a `true`/`false` value", line)
    elif emit.form == "table":
        if not (isinstance(value, Lit) and value.kind == "table"):
            raise TypeCheckError(f"{where}: `:{emit.method}{{...}}` takes a `{{ ... }}` table", line)


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
    _no_duplicates((p.name for p in ent.props), f"{owner or kind}: field", ent.line)
    _no_duplicates((f"{h.phase} {','.join(h.events)}" for h in ent.handlers),
                   f"{owner or kind}: handler", ent.line)
    for p in ent.props:
        where = f"{owner}.{p.name}" if owner else p.name
        _check_ref_prop(ctx, where, p)
        if isinstance(p.value, list):
            env = _prop_body_env(ctx, p)
            env["load"] = BOOL
            if p.typ is not None and types.fn_of(p.typ) is None:
                raise TypeCheckError(f"{where}: expected {p.typ}, got a block "
                                     f"(a block is a function)", p.line)
            rets: List[Type] = []
            _check_stmts(ctx, p.value, env, owner, rets)
            want = types.fn_returns(p.typ) if p.typ else ()
            for t in rets:
                if want and not any(is_subtype(ctx, t, w) for w in want):
                    raise TypeCheckError(f"{where}: return {t}, declared returns "
                                         f"{', '.join(str(w) for w in want)}", p.line)
        elif isinstance(p.value, Lit) and p.value.kind == "lua":
            _prop_body_env(ctx, p)
        else:
            _check_callable_part(ctx, p.value, {"s": Name(_root(ctx))}, owner, p.typ, where, p.line)
        if p.emit and p.value is not None:
            _check_emit(where, p.emit, p.value, p.line)
    for h in ent.handlers:
        _check_handler_events(ctx, h, owner or kind)
        params, arg_names = _handler_params(ctx, owner, kind, h)
        h.params = [pn for pn, _t in params]     # what the emitter prints
        where = f"{owner or kind}: {h.phase} {','.join(h.events)}"
        want = Fn(tuple(t for _n, t in params), ()) if isinstance(h.body, FnRef) else (
            None if isinstance(h.body, list) else _HANDLER_VALUE)
        _check_callable_part(ctx, h.body, dict(params), owner, want, where, h.line, arg_names)
    for ch in ent.children:
        _check_entity(ctx, ch)


HANDLER_PARAMS = ("s", "w", "wh", "w2", "w3")
CHOICE_FIELDS = ("ask", "reply", "do", "onempty")


def _handler_event_args(ctx: Context, h: Handler) -> List[Type]:
    per = [list(ctx.event_args.get(ev) or []) for ev in h.events]
    out: List[Type] = []
    for i in range(max((len(x) for x in per), default=0)):
        t = union(*dict.fromkeys(x[i] for x in per if i < len(x)))
        out.append(opt(t) if any(i >= len(x) for x in per) and not types.is_optional(t) else t)
    return out


def _handler_params(ctx: Context, owner: Optional[str], kind: str, h: Handler
                    ) -> Tuple[List[Tuple[str, Type]], Dict[int, str]]:
    self_t = Name(kind if (kind in ctx.classes or kind in ctx.objects) else _root(ctx))
    params: List[Tuple[str, Type]] = [("s", self_t)]
    room_like = _inherits(ctx, kind, _room_root(ctx)) or owner in ("game", "mp", None)
    if any(ev in ("Any", "Default") for ev in h.events):
        params += [("ev", EVENT), ("w", Name(_root(ctx))), ("wh", Name(_root(ctx)))]
        names = ("w", "wh", "w2", "w3")
        return params, ({i: names[i - 1] for i in range(1, len(names) + 1)}
                        if not room_like else {i: names[i] for i in range(len(names))})
    sigs = _handler_event_args(ctx, h)
    acted = bool(sigs) and any(ev in ctx.event_acted for ev in h.events)
    arg_names: Dict[int, str] = {}
    if acted and room_like:      # the acted object comes in as `w`
        params.append(("w", Name(_root(ctx))))
        arg_names[0] = "w"
    for i, st in enumerate(sigs[1:] if acted else sigs, start=1 if acted else 0):
        name = HANDLER_PARAMS[len(params)]
        params.append((name, st))
        arg_names[i] = name
    if h.params is not None:
        _no_duplicates(h.params, f"{h.phase} {','.join(h.events)}: parameter", h.line)
        if len(h.params) > len(params):
            raise Error(f"{h.phase} {','.join(h.events)}: the engine passes "
                        f"{len(params)} parameter(s) here, the handler declares {len(h.params)}",
                        h.line)
        params = [(h.params[i], params[i][1]) for i in range(len(h.params))]
    return params, arg_names


def _check_talk(ctx: Context, td: TalkDecl):
    env = {"s": Name("talk")}
    _no_duplicates((p.name for p in td.props), f"talk {td.name}: field", td.line)
    labels = [ln for ln, _say, _ch in td.labels]
    for ln in labels:
        if labels.count(ln) > 1:
            raise Error(f"talk {td.name}: duplicate label {ln!r}", td.line)

    def chk_choice(c: TalkChoice):
        if c.next_label and c.next_label not in labels:
            raise Error(f"talk {td.name}: unknown label {c.next_label!r} in `next`/`->`", c.line)
        for part, want, what in [(c.cond, None, "when")] + [
            (getattr(c, f), ctx.fields.get("choice", {}).get(f), f) for f in CHOICE_FIELDS
        ]:
            _check_callable_part(ctx, part, env, td.name, want, f"talk {td.name}: {what}", c.line)
        for sub in c.children:
            chk_choice(sub)

    _check_callable_part(ctx, td.intro, env, td.name, None, "", td.line)
    for c in td.choices:
        chk_choice(c)
    for _ln, lsay, lcs in td.labels:
        _check_callable_part(ctx, lsay, env, td.name, None, "", td.line)
        for c in lcs:
            chk_choice(c)


def _returns_all(stmts: List[Stmt]) -> bool:
    """Does every path through this body end with a value?"""
    for s in stmts:
        if isinstance(s, ReturnStmt):
            return s.kind == "pass" or (s.kind == "return" and bool(s.values))
        if isinstance(s, IfStmt) and s.else_body is not None \
                and _returns_all(s.else_body) \
                and all(_returns_all(b) for _c, b, _l in s.branches):
            return True
        if isinstance(s, MatchStmt) \
                and any(len(p) == 1 and isinstance(p[0], Sym) and p[0].name == "_" and not g
                        for p, g, _b, _l in s.arms) \
                and all(_returns_all(b) for _p, _g, b, _l in s.arms):
            return True
    return False


def _nonnil(ctx: Context, e: Expr) -> bool:
    if isinstance(e, Lit):
        return e.kind != "nil"
    if isinstance(e, Sym):
        return _lit_type(ctx, e) != ANY
    return isinstance(e, (ListLit, InterpStr))


def _narrow_event_args(ctx: Context, ev_names: List[str], res: Dict[str, Type],
                       arg_names: Optional[Dict[int, str]]):
    if not ev_names or not arg_names:
        return
    alts = [ctx.event_args.get(n) or [] for n in ev_names]
    for i in range(max((len(a) for a in alts), default=0)):
        ts = [a[i] for a in alts if i < len(a)]
        name = arg_names.get(i)
        if ts and name and name in res:
            res[name] = union(*set(ts))


def _is_event_sym(e: Expr, env: Dict[str, Type]) -> bool:
    return isinstance(e, Sym) and (
        e.name in CURRENT_EVENT or without_nil(env.get(e.name, ANY)) == EVENT
    )


def _narrow(ctx: Context, cond: Expr, env: Dict[str, Type], truthy: bool,
            arg_names: Optional[Dict[int, str]] = None) -> Dict[str, Type]:
    res = dict(env)
    if isinstance(cond, Bind) and truthy:
        vt = without_nil(cond.vtyp) if (cond.vtyp and cond.vtyp != ANY) else ANY
        for n in cond.names:
            res[n] = vt
        return res
    if isinstance(cond, Sym) and cond.name in res:
        res[cond.name] = without_nil(res[cond.name]) if truthy else NIL
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
                    res[a.name] = without_nil(res[a.name]) if ((cond.op == "!=") == truthy) else NIL
                    return res
                if _nonnil(ctx, b):
                    if (cond.op == "==") == truthy:
                        res[a.name] = without_nil(res[a.name])
                    break
            if cond.op == "==" and truthy and _is_event_sym(cond.left, res) and isinstance(cond.right, Sym):
                _narrow_event_args(ctx, [cond.right.name], res, arg_names)
    return res


def _check_assign_stmt(ctx: Context, s: AssignStmt, env: Dict[str, Type], owner: Optional[str]):
    vt = _value_types(ctx, s.values, env, owner)
    if s.op in ("+=", "-="):
        for v, t in zip(s.values, vt):
            expect(ctx, f"'{s.op}'", _eval_field_for(ctx, v, t, NUM), NUM, s.line)
    if isinstance(s.target, Sym):
        name = s.target.name
        if name == "...":
            raise Error("cannot assign to '...'", s.line)
        local = name in env                    # a local shadows a global of that name
        if local:
            cur = env[name]
        elif name in ctx.consts:
            raise Error(f"{name}: a constant cannot be assigned", s.line)
        elif name in ctx.globals:
            cur = ctx.globals[name]            # a global keeps its declared type
        elif name.startswith("__"):
            cur = None
        else:
            raise Error(f"unknown name {name!r} (declare it with `local` or `global`)", s.line)
        if cur is not None and cur != ANY and s.op == "=" and vt:
            vt[0] = _eval_field_for(ctx, s.values[0], vt[0], cur)
            expect(ctx, f"assignment to {name}", vt[0], cur, s.line)
        if cur is not None and cur != ANY and s.op in ("+=", "-="):
            expect(ctx, f"{name} ({s.op})", cur, NUM, s.line)
        if local and cur in (None, ANY) and vt and s.op == "=":
            env[name] = vt[0]                  # a local takes the type of its first value
    else:
        _check_store(ctx, s.target, vt[0] if vt else ANY, env, owner, s.line, s.op,
                     s.values[0] if s.values else None)


def _check_return_stmt(ctx: Context, s: ReturnStmt, env: Dict[str, Type], owner: Optional[str],
                       rets: Optional[List[Type]], fn_decl: Optional[FnDecl]):
    exp_rets = fn_decl.ret_types if (fn_decl is not None and s.kind == "return") else None
    vts = _value_types(ctx, s.values, env, owner, len(exp_rets) if exp_rets else 1, exp_rets)
    if fn_decl is not None and s.kind == "return" and s.values:
        expected = fn_decl.ret_types
        explicit, expanded = len(s.values), len(vts)
        bad = (expanded != len(expected)) if explicit == expanded else (expanded < len(expected))
        if bad:
            raise Error(f"fn {fn_decl.name}: returns {expanded} value(s), "
                        f"{len(expected)} declared", s.line)
        for i, exp in enumerate(expected[:len(vts)]):
            expect(ctx, f"return value {i + 1} of {fn_decl.name}", vts[i], exp, s.line)
    if rets is not None:
        rets.extend(t for t in vts if t != NIL)


def _check_stmts(ctx: Context, stmts: List[Stmt], env: Dict[str, Type],
                 owner: Optional[str] = None, rets: Optional[List[Type]] = None,
                 arg_names: Optional[Dict[int, str]] = None,
                 fn_decl: Optional[FnDecl] = None, in_loop: bool = False):
    for s in stmts:
        if isinstance(s, SayStmt):
            _check_expr(ctx, s.expr, env, owner, STR)
        elif isinstance(s, ReturnStmt):
            if s.kind == "break" and not in_loop:
                raise Error("break: not inside a loop", s.line)
            _check_return_stmt(ctx, s, env, owner, rets, fn_decl)
        elif isinstance(s, LocalStmt):
            _no_duplicates((vn for vn, _t in s.names), "local", s.line)
            vts = _value_types(ctx, s.values, env, owner, len(s.names),
                               [dt for _vn, dt in s.names])
            for i, (vn, dt) in enumerate(s.names):
                got = vts[i] if i < len(vts) else None
                if dt is None:
                    env[vn] = got if got is not None else ANY
                elif got is None:            # declared, not set yet: it is nil
                    env[vn] = opt(dt)
                else:
                    expect(ctx, f"local {vn}", got, dt, s.line)
                    env[vn] = dt
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
                _check_stmts(ctx, body, _narrow(ctx, cond, cenv, True, arg_names),
                             owner, rets, arg_names, fn_decl, in_loop=in_loop)
                cenv = _narrow(ctx, cond, cenv, False, arg_names)
            if s.else_body is not None:
                _check_stmts(ctx, s.else_body, cenv, owner, rets, arg_names, fn_decl,
                             in_loop=in_loop)
        elif isinstance(s, MatchStmt):
            st = _check_expr(ctx, s.subject, env, owner)
            for idx, (pats, guard, body, _l) in enumerate(s.arms):
                has_wild = any(isinstance(p, Sym) and p.name == "_" for p in pats)
                if has_wild and len(pats) > 1:
                    raise Error("match: '_' cannot be combined with other patterns", _l)
                if has_wild and not guard and idx < len(s.arms) - 1:
                    raise Error("match: '_' must be the last arm", _l)
                aenv = dict(env)
                for p in pats:
                    if not (isinstance(p, Sym) and p.name == "_"):
                        pt = _check_expr(ctx, p, env, owner, st)
                        if pt != ANY:
                            st = _eval_field_for(ctx, s.subject, st, pt)
                        aenv = _narrow(ctx, BinOp(line=p.line, op="==", left=s.subject, right=p),
                                       aenv, True, arg_names)
                if guard:
                    _check_cond(ctx, guard, aenv, owner)
                _check_stmts(ctx, body, aenv, owner, rets, arg_names, fn_decl)
        elif isinstance(s, ForNumStmt):
            for bound in (s.start, s.stop, s.step):
                if bound is not None:
                    _check_expr(ctx, bound, env, owner, NUM)
            benv = dict(env)
            benv[s.var] = s.var_type or NUM
            if s.var_type:
                expect(ctx, f"for variable {s.var}", NUM, s.var_type, s.line)
            _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl, in_loop=True)
        elif isinstance(s, ForInStmt):
            it = _check_expr(ctx, s.iter_expr, env, owner)
            if s.is_of:
                base = _index_result(ctx, it)
                if base is None and not _is_object_type(ctx, it):
                    raise TypeCheckError(f"for … of: expected tbl, got {it}", s.line)
                el = base if base is not None else (
                    Name(_root(ctx)) if _is_object_type(ctx, it) else ANY)
            else:
                void_ext = (isinstance(s.iter_expr, Call) and s.iter_expr.receiver is None
                            and s.iter_expr.func in ctx.fns
                            and ctx.fns[s.iter_expr.func].is_extern
                            and not ctx.fns[s.iter_expr.func].ret_types)
                if void_ext or (it != ANY and not isinstance(it, Fn) and it != Name("fn")):
                    got_t = NIL if void_ext else it
                    raise TypeCheckError(f"for … in: expected an iterator, got {got_t}", s.line)
                el = ANY
            benv = dict(env)
            for i, (vn, vt) in enumerate(s.vars):
                if s.is_of:
                    elem = NUM if (len(s.vars) == 2 and i == 0) else el
                elif isinstance(it, Fn) and i < len(it.rets):
                    elem = without_nil(it.rets[i]) if i == 0 else it.rets[i]
                else:
                    elem = el
                if vt is not None and elem != ANY:
                    expect(ctx, f"for variable {vn}", elem, vt, s.line)
                benv[vn] = vt or elem
            _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl, in_loop=True)


def _sig_text(types: List[Type]) -> str:
    return ", ".join(str(t) for t in types) if types else "no arguments"


def _check_fnref(ctx: Context, ref: FnRef, expected: Optional[Type], where: str) -> Type:
    """Validate a `&name` function reference and check it against `expected`."""
    fn = ctx.fns.get(ref.name)
    if fn is None:
        if ref.name not in ctx.lua_funcs:
            raise Error(f"&{ref.name}: unknown function "
                        f"(declare it with `fn` or in a `lua` block)", ref.line)
        ctx.used_refs.add(ref.name)
        return Name("fn")
    if fn.is_extern:
        raise Error(f"&{ref.name}: an extern is a macro, it has no function value "
                    f"(call it directly, or write a `fn` wrapper)", ref.line)
    _ensure_fn_checked(ctx, fn)
    ctx.used_refs.add(ref.name)
    got = Fn(tuple(pt for _pn, pt in fn.params), tuple(fn.ret_types))
    if expected is not None:
        alts = [a for a in parts(expected) if isinstance(a, Fn)]
        if alts and not any(_atom_fits(ctx, got, a) for a in alts):
            raise TypeCheckError(f"{where}: {ref.name} is {got}, expected "
                                 f"{' | '.join(str(a) for a in alts)}", ref.line)
    return got


def _root(ctx: Context) -> str:
    return ctx.root_class or "obj"


def _room_root(ctx: Context) -> str:
    return next((c for c, fs in ctx.prop_decls.items() if "n_to" in fs), "")


def _inherits(ctx: Context, kind: str, root: str) -> bool:
    return root in _walk_class_chain(ctx, kind)


def _index_result(ctx: Context, t: Type) -> Optional[Type]:
    res: List[Type] = []
    for alt in parts(t):
        if alt == NIL:
            continue
        if alt == ANY:
            return ANY
        if types.is_tbl(alt):
            inner = types.tbl_inner(alt)
            res.append(inner if inner is not None else ANY)
        elif _is_list_type(ctx, alt):
            res.append(Name(_root(ctx)))
    return union(*res) if res else None


def _is_list_type(ctx: Context, t: Type) -> bool:
    one = types.single(t)
    return isinstance(one, Name) and any(ctx.ctors.get(cur) == "std.list"
                                         for cur in _walk_class_chain(ctx, one.name))


def _is_object_type(ctx: Context, t: Type) -> bool:
    one = types.single(t)
    return isinstance(one, Name) and (one.name in ctx.classes or one.name in ctx.objects)


def _objectish(ctx: Context, t: Type) -> bool:
    return any(alt == ANY or isinstance(alt, (Ref, Tbl)) or _is_object_type(ctx, alt)
               for alt in parts(t))


def _fields_of(ctx: Context, holder: str) -> Dict[str, Type]:
    allowed = dict(ctx.fields.get(holder, {}))
    if holder not in ctx.classes:
        return allowed
    for name, kind in list(ctx.objects.items()) + list(ctx.classes.items()):
        if not _inherits(ctx, kind if kind else name, holder):
            continue
        for k, v in ctx.fields.get(name, {}).items():
            if k not in allowed or _is_empty_collection(allowed[k]):
                allowed[k] = v
            elif allowed[k] != v and not _is_empty_collection(v):
                allowed[k] = ANY                # two real types: dynamic (duck typing)
    return allowed


def _owner_of(ctx: Context, target: FieldAccess, env: Dict[str, Type], owner: Optional[str]) -> Optional[str]:
    if not isinstance(target.obj, Sym):
        return None
    n = target.obj.name
    if n == "s" and owner:
        return owner
    if n in ctx.objects:
        return n if (n in ctx.fields or ctx.objects[n] == "class") else ctx.objects[n]
    if n in ctx.classes:
        return n
    t = str(without_nil(env[n])) if n in env else ""
    return t if (t in ctx.classes or t in ctx.objects) else None


def _resolve_index(ctx: Context, e: IndexAccess, env: Dict[str, Type],
                   owner: Optional[str], line: int) -> Tuple[Type, Type]:
    ot = _check_expr(ctx, e.obj, env, owner)
    base = _index_result(ctx, ot)
    if base is None:
        raise TypeCheckError(f"{_kind_name(e.obj)}: {ot} is not indexable "
                             f"(only a `tbl`, a list or `any`)", line)
    _check_expr(ctx, e.index, env, owner, None)
    return ot, base


def _resolve_field(ctx: Context, e: FieldAccess, env: Dict[str, Type],
                   owner: Optional[str], writing: bool = False, line: int = 0) -> Type:
    base_t = _check_expr(ctx, e.obj, env, owner)
    need_value(base_t, _kind_name(e.obj), line)
    if not writing and not _objectish(ctx, base_t):
        raise TypeCheckError(f"{_kind_name(e.obj)}: {base_t} has no fields "
                             f"(`.{e.field}`)", line)
    name = e.field
    if writing and name in READONLY_FIELDS:
        raise Error(f"{name}: an engine field cannot be assigned", line)
    if name.startswith("__"):
        return ANY
    holder = _owner_of(ctx, e, env, owner)
    decl = _decl_of(ctx, holder, name) if holder else None
    if decl is not None and decl.emit is not None:
        if writing:
            raise Error(f"{holder}.{name}: an emitted field is set by its declaration "
                        f"(`= method {decl.emit.method}(…)`), not by code", line)
        raise TypeCheckError(
            f"{_kind_name(e)}: {name!r} is write-only "
            f"(declared as `= method {decl.emit.method}(…)`); read it through the method",
            line)
    if holder is not None:
        ft = (ctx.fields.get(holder, {}).get(name) if not writing else None) \
            or _fields_of(ctx, holder).get(name)
        if ft is None:
            raise Error(f"{holder}.{name}: no such field "
                        f"(nothing declares it for {holder}; use __{name} for a dynamic value)",
                        line)
        return ft
    if name not in ctx.field_names:
        raise Error(f"unknown field {name!r} (use __{name} for dynamic values)", line)
    return ANY


def _callable_field_ret(ctx: Context, ft: Type) -> Optional[Type]:
    """For a `T | fn(obj) -> T` field union, the result type `T` of reading it."""
    alts = [a for a in parts(ft) if a != NIL]
    fns = [a for a in alts if isinstance(a, Fn)]
    vals = [a for a in alts if not isinstance(a, Fn)]
    if not (vals and fns and all(len(f.params) <= 1 and len(f.rets) == 1 for f in fns)):
        return None
    v_union = union(*vals)
    rets = [f.rets[0] for f in fns]
    if not all(is_subtype(ctx, r, v_union)
               or (_is_scalar_ref(ctx, r) and _is_scalar_ref(ctx, v_union)) for r in rets):
        return None
    res = union(*rets)
    return opt(res) if types.is_optional(ft) else res


def _eval_field_for(ctx: Context, e: Optional[Expr], ft: Type,
                    expected: Optional[Type]) -> Type:
    if not isinstance(e, FieldAccess) or expected is None or expected == ANY \
            or is_subtype(ctx, ft, expected):
        return ft
    ret = _callable_field_ret(ctx, ft)
    if ret is None or not is_subtype(ctx, ret, expected):
        return ft
    e.eval_kind = "call" if without_nil(ret) == STR else "val"
    e.is_ref = _is_scalar_ref(ctx, ret)
    e.typ = ret
    return ret


def _check_store(ctx: Context, target: Expr, vt: Type, env: Dict[str, Type],
                 owner: Optional[str], line: int = 0, op: str = "=",
                 rhs: Optional[Expr] = None):
    if isinstance(target, IndexAccess):
        ot, inner = _resolve_index(ctx, target, env, owner, line)
        need_value(ot, _kind_name(target.obj), line)
        vt = _eval_field_for(ctx, rhs, vt, inner)
        expect(ctx, _kind_name(target), vt, inner, line)
        return
    if not isinstance(target, FieldAccess):
        _check_expr(ctx, target, env, owner)
        return
    ft = _resolve_field(ctx, target, env, owner, writing=True, line=line)
    if op in ("+=", "-=") and ft not in (ANY, NUM):
        raise Error(f"{target.field}: '{op}' needs a number field (it is {ft})", line)
    elif op not in ("+=", "-=") and ft != ANY:
        vt = _eval_field_for(ctx, rhs, vt, ft)
        expect(ctx, target.field, vt, ft, line)


def _check_expr(ctx: Context, e: Expr, env: Dict[str, Type], owner: Optional[str] = None,
                expected: Optional[Type] = None) -> Type:
    e.typ = t = _infer(ctx, e, env, owner, expected)
    if expected:
        expect(ctx, _kind_name(e), t, expected, e.line)
    return t


def _infer_lambda(ctx: Context, e: Lambda, env: Dict[str, Type],
                  owner: Optional[str], expected: Optional[Type]) -> Type:
    one = types.fn_of(expected) if expected is not None else None
    eparams: Tuple[Type, ...] = one.params if one else ()
    erets: Tuple[Type, ...] = one.rets if one else ()
    if eparams and len(e.params) > len(eparams):
        raise TypeCheckError(f"&(…): the callback passes {len(eparams)} argument(s), "
                             f"the lambda takes {len(e.params)}", e.line)
    env2 = dict(env)
    env2.pop("...", None)
    ptypes: List[Type] = []
    for i, (pn, pt) in enumerate(e.params):
        ept = eparams[i] if i < len(eparams) else None
        if pt is None:
            if not ept:
                raise TypeCheckError(
                    f"&({pn}): annotate the parameter type (`&({pn}: obj)`)", e.line)
            pt = ept
        elif ept and pt != ANY and not is_subtype(ctx, ept, pt):
            raise TypeCheckError(f"&({pn}): the callback passes {ept}, "
                                 f"the lambda declares {pt}", e.line)
        env2[pn] = pt
        ptypes.append(pt)
    if isinstance(e.body, list):
        rets: List[Type] = []
        _check_stmts(ctx, e.body, env2, owner, rets)
        for t in rets:
            if erets and not any(is_subtype(ctx, t, w) for w in erets):
                raise TypeCheckError(f"&(…): returns {t}, the callback declares "
                                     f"{union(*erets)}", e.line)
        if erets and not types.is_optional(union(*erets)) and not _returns_all(e.body):
            raise TypeCheckError(
                f"&(…): the callback returns {union(*erets)}, but some path leaves the body "
                f"without `return` (write an expression body or add `return`)", e.line)
    else:
        _check_expr(ctx, e.body, env2, owner, erets[0] if erets else None)
    return Fn(tuple(ptypes), tuple(erets))


def _infer(ctx: Context, e: Expr, env: Dict[str, Type], owner: Optional[str] = None,
           expected: Optional[Type] = None) -> Type:
    if isinstance(e, Lit):
        if e.kind == "num" and expected is not None:
            for alt in parts(expected):
                if isinstance(alt, Name) and alt.name in ctx.enums \
                        and str(e.val) in ctx.enums[alt.name][0]:
                    return alt
        return _KINDS.get(e.kind, ANY)
    if isinstance(e, InterpStr):
        for p in e.parts:
            if isinstance(p, Expr):
                t = _eval_field_for(ctx, p, _check_expr(ctx, p, env, owner), _PRINTABLE)
                if not is_subtype(ctx, t, _PRINTABLE) and t != ANY:
                    raise TypeCheckError(f"interpolation: expected str, got {t}", p.line)
        return STR
    if isinstance(e, Lambda):
        return _infer_lambda(ctx, e, env, owner, expected)
    if isinstance(e, Bind):
        vt = _value_types(ctx, [e.value], env, owner, len(e.names))
        e.vtyp = vt[0] if vt else ANY
        for n in e.names:
            if n in env:
                raise Error(f"{n}: already defined (choose another name for `:=`)", e.line)
        return BOOL
    if isinstance(e, InOp):
        st = _check_expr(ctx, e.subject, env, owner)
        for a in e.alts:
            at = _check_expr(ctx, a, env, owner, st)
            if at != ANY:
                st = _eval_field_for(ctx, e.subject, st, at)
        return BOOL
    if isinstance(e, FnRef):
        return _check_fnref(ctx, e, expected, _kind_name(e))
    if isinstance(e, ListLit):
        in_exp = next((types.tbl_inner(alt) for alt in (parts(expected) if expected else [])
                       if types.tbl_inner(alt) is not None), None)
        its = [_check_expr(ctx, it, env, owner, in_exp) for it in e.items]
        return Tbl(union(*its) if its else Name(""))
    if isinstance(e, Sym):
        return _infer_sym(ctx, e, env, expected)
    if isinstance(e, FieldAccess):
        ft = _resolve_field(ctx, e, env, owner, writing=False, line=e.line)
        ft = _eval_field_for(ctx, e, ft, expected)
        e.is_ref = _is_scalar_ref(ctx, ft)
        return ft
    if isinstance(e, IndexAccess):
        _ot, base = _resolve_index(ctx, e, env, owner, e.line)
        return base if base in (ANY, NIL) or types.is_optional(base) else opt(base)
    if isinstance(e, UnaryOp):
        if e.op == "-" and isinstance(e.operand, Lit) and e.operand.kind == "str":
            return STR
        _check_expr(ctx, e.operand, env, owner, None if e.op == "not" else NUM)
        return BOOL if e.op == "not" else NUM
    if isinstance(e, BinOp):
        return _infer_binop(ctx, e, env, owner)
    if isinstance(e, Call):
        return _check_call(ctx, e, env, owner)
    return ANY


def _infer_sym(ctx: Context, e: Sym, env: Dict[str, Type],
               expected: Optional[Type]) -> Type:
    n = e.name
    if n == "...":
        if "..." not in env:
            raise Error("cannot use '...' outside a variadic function", e.line)
        e.rk = "var"
        return env["..."]
    if n in env:
        e.rk = "var"
        return env[n]
    if expected:
        exps = parts(expected)
        if EVENT in exps and n in ctx.event_names:
            e.rk = "event"
            return EVENT
        if n in ctx.enum_owner:
            for ea in exps:
                if _enum_value(ctx, n, str(ea)):
                    e.rk = "enum"
                    return Name(str(ea))
    if n in ctx.objects:
        e.rk = "obj"
        return Name(ctx.objects[n])
    if n in ctx.globals:
        gt = ctx.globals[n]
        e.rk = "global_ref" if _is_scalar_ref(ctx, gt) else "global"
        return gt
    if n in ctx.classes:
        e.rk = "enum"
        return STR
    if n in ctx.event_names:
        e.rk = "event"
        return EVENT
    enum = ctx.enum_owner.get(n.lstrip("~"))
    if enum:
        e.rk = "enum"
        return Name(enum)
    if n in ctx.fns or n in ctx.lua_funcs:
        sig = ctx.fns.get(n)
        required = sum(1 for _pn, pt in (sig.params if sig is not None else [])
                       if not types.is_optional(pt))
        if required:
            raise Error(f"{n}: needs {required} argument(s) — call it or take `&{n}`", e.line)
        _ensure_fn_checked(ctx, sig)
        e.rk = "value" if (sig and sig.is_value) else "fn0"
        return sig.ret_types[0] if (sig and sig.ret_types) else ANY
    if n.startswith("#"):
        raise Error(f"unknown tag {n!r}", e.line)
    raise Error(f"unknown name {n!r}{_enum_hint(ctx, n)}", e.line)


def _infer_binop(ctx: Context, e: BinOp, env: Dict[str, Type], owner: Optional[str]) -> Type:
    if e.op in ("<", "<=", ">", ">=", "+", "-", "*", "/", "%", "//"):
        for side in (e.left, e.right):
            _check_expr(ctx, side, env, owner, NUM)
        return BOOL if e.op in ("<", "<=", ">", ">=") else NUM
    if e.op == "..":
        for side in (e.left, e.right):
            t = _eval_field_for(ctx, side, _check_expr(ctx, side, env, owner), _CONCAT)
            if not is_subtype(ctx, t, _CONCAT) and t != ANY:
                raise TypeCheckError(f"concatenation: expected str, got {t}", side.line)
        return STR
    lt = _check_expr(ctx, e.left, env, owner)
    if e.op in ("==", "!="):
        rt = _infer(ctx, e.right, env, owner, lt)  # resolves bare names, comparing is not a type error
        if rt != ANY:
            _eval_field_for(ctx, e.left, lt, rt)
        return BOOL
    rt = _check_expr(ctx, e.right, env, owner)
    return union(lt, rt) if e.op == "and" else (union(without_nil(lt), rt) if e.op == "or" else rt)


def _check_value_use(ctx: Context, name: str, line: int):
    fn = ctx.fns.get(name)
    if fn is not None and fn.is_value:
        raise Error(f"{name}: an expression, not a statement (use its value)", line)


def _check_call(ctx: Context, c: Call, env: Dict[str, Type], owner: Optional[str] = None) -> Type:
    """Type a call: `f a b`, `f(a, b)`, `obj:m a` and a call of a fn value."""
    is_method = c.receiver is not None
    rt = _check_expr(ctx, c.receiver, env, owner) if is_method else None
    if is_method:
        need_value(rt, _kind_name(c.receiver), c.line)
    ftype = env.get(c.func)
    shadowed = not is_method and ftype is not None and types.fn_of(ftype) is not None
    fn = None if shadowed else ctx.fns.get(c.func)
    if fn is not None:
        all_args = ([c.receiver] + c.args) if is_method else list(c.args)
        label = f"{_kind_name(c.receiver)}:{c.func}" if is_method else c.func
        params = fn.params
        required = sum(1 for _pn, pt in params if not types.is_optional(pt))
        given, variadic = len(all_args), bool(fn.variadic)
        if given < required or (not variadic and given > len(params)):
            want = f"{required}+" if variadic else (
                str(required) if required == len(params) else f"{required}..{len(params)}")
            raise Error(f"{label} expects {want} argument(s), got {given}", c.line)
        for i, a in enumerate(all_args):
            exp = params[i][1] if i < len(params) else (fn.variadic if variadic else None)
            if is_method and i == 0:
                expect(ctx, f"receiver of {label}", rt, exp, a.line)
            else:
                at = _check_expr(ctx, a, env, owner, exp)
                if not is_method and c.func in ("say", "append", "line"):
                    _eval_field_for(ctx, a, at, _PRINTABLE)
        _ensure_fn_checked(ctx, fn)
        return fn.ret_types[0] if fn.ret_types else ANY

    body = without_nil(ftype) if ftype is not None else None
    one = body if isinstance(body, Fn) else None
    if not (c.func in ctx.lua_funcs or (not is_method and one is not None)
            or (is_method and rt == ANY)):
        if is_method:
            raise Error(f"unknown method {c.func!r} "
                        f"(a method call needs a function or an extern)", c.line)
        if ftype is not None:
            raise TypeCheckError(f"{c.func}: is {ftype}, not a function", c.line)
        raise Error(f"unknown function {c.func!r}", c.line)
    if one is not None:
        required = sum(1 for t in one.params if not types.is_optional(t))
        if len(c.args) < required:
            raise TypeCheckError(f"{c.func}: expects {required} argument(s), "
                                 f"got {len(c.args)}", c.line)
    for i, a in enumerate(c.args):
        _check_expr(ctx, a, env, owner,
                    one.params[i] if (one is not None and i < len(one.params)) else None)
    return one.rets[0] if (one is not None and one.rets) else ANY


def _type_alt_ok(ctx: Context, alt: Type) -> bool:
    """Is this single type alternative known? `ref[C]` takes declared classes only."""
    if isinstance(alt, Tbl):
        return alt.inner is None or all(_type_alt_ok(ctx, a) for a in parts(alt.inner))
    if isinstance(alt, Ref):
        return not alt.name or all(a.strip() in ctx.classes
                                   for a in alt.name.split("|") if a.strip())
    if isinstance(alt, Fn):
        return True
    return alt.name in PRIMITIVES or alt.name in ctx.enums or alt.name in ctx.classes


def _check_type(ctx: Context, typ: Type, where: str, line: int, label: str = "type"):
    for alt in parts(typ):
        if not _type_alt_ok(ctx, alt):
            raise Error(f"{where}: unknown {label} {str(alt)!r}", line)


def _check_signature(ctx: Context, fn: FnDecl):
    if fn.is_extern:
        return
    _no_duplicates((pn for pn, _t in fn.params), f"fn {fn.name}: parameter", fn.line)
    seen_optional = False
    for pname, ptype in fn.params:
        _check_type(ctx, ptype, f"fn {fn.name}({pname})", fn.line)
        optional = types.is_optional(ptype)
        if seen_optional and not optional:
            raise Error(f"fn {fn.name}: required parameter {pname!r} after an optional one", fn.line)
        seen_optional = seen_optional or optional
    for rt in fn.ret_types:
        _check_type(ctx, rt, f"fn {fn.name}", fn.line, "return type")
    if fn.variadic is not None:
        _check_type(ctx, fn.variadic, f"fn {fn.name}(...)", fn.line)


def _is_empty_collection(t: Type) -> bool:
    inner = types.tbl_inner(t)
    return isinstance(inner, Name) and inner.name == ""


def _value_types(ctx: Context, values: List[Expr], env: Dict[str, Type],
                 owner: Optional[str], count: int = 1,
                 hints: Optional[List[Optional[Type]]] = None) -> List[Type]:
    res: List[Type] = []
    for i, v in enumerate(values):
        hint = hints[i] if (hints and i < len(hints)) else None
        if i == len(values) - 1 and isinstance(v, Sym) and v.name == "...":
            t = _check_expr(ctx, v, env, owner)
            el = opt(t) if t != ANY else ANY
            res.extend([el] * max(1, count - len(res)))
            continue
        v.typ = t = _infer(ctx, v, env, owner, hint)
        if i == len(values) - 1 and isinstance(v, Call) and v.receiver is None and v.func:
            fn = ctx.fns.get(v.func)
            _ensure_fn_checked(ctx, fn)
            if fn and len(fn.ret_types) > 1:
                res.extend(fn.ret_types)
                continue
        res.append(t)
    return res


def _is_method_val(val: Any) -> bool:
    return isinstance(val, (list, FnRef)) or (isinstance(val, Lit) and val.kind == "lua")


def _class_methods(ctx: Context, cls: str) -> Set[str]:
    return {p.name for cur in _walk_class_chain(ctx, cls)
            for p in (ctx.class_decls[cur].props if cur in ctx.class_decls else ())
            if _is_method_val(p.value)}


def _check_override(ctx: Context, ent: EntityDecl):
    if ent.kind == "impl" or ent.name is None:
        return
    bases = ([ent.kind] if ent.kind != "class" else []) + list(ent.traits) \
        + ([ent.parent] if ent.kind == "class" and ent.parent else [])
    for p in ent.props:
        if p.value is not None and not _is_method_val(p.value):
            base = next((b for b in bases if p.name in _class_methods(ctx, b)), None)
            if base is not None:
                raise Error(
                    f"{ent.name}.{p.name}: cannot overwrite the method of class {base!r} with a value "
                    f"(use a block, `&fn` or `impl {ent.name}`)", p.line)


def _check_cond(ctx: Context, cond: Expr, env: Dict[str, Type], owner: Optional[str]):
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
    for ev in h.events:
        if ev not in ctx.event_names:
            hint = _close_hint(ev, ctx.event_names, lambda m: f" (did you mean {m!r}?)")
            raise Error(f"{where}: unknown event {ev!r}{hint}", h.line)
