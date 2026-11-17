"""Symbol table, subtyping, AST normalization and declaration collection for MISE 2."""
from dataclasses import dataclass, field, replace
import difflib
from itertools import zip_longest
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

from . import types
from .ast_nodes import (
    BinOp, DictLit, Emit, EntityDecl, EntryDecl, Error, EventsDecl, Expr,
    ExternDecl, FnDecl, FnRef, InterpStr, Lambda, ListLit, Lit, LuaDecl,
    Program, Prop, Sym, TalkDecl, TypeDecl, UnaryOp, VarDecl, VerbDecl,
)
from .parser import PHASES
from .types import ANY, NIL, Fn, Name, Ref, Tbl, Type, opt, parts, union, without_nil

STR, NUM, BOOL, EVENT = Name("str"), Name("num"), Name("bool"), Name("event")
TBL = Tbl(None)

_SLOT_OBJ_RE = re.compile(r"\{(?:noun|noun_obj|compass\w*)\}")
CURRENT_EVENT = frozenset({"ev", "event"})
READONLY_FIELDS = frozenset({"nam"})
ENGINE_OBJECTS = frozenset({"player"})
BUILTIN_TARGETS = frozenset({"game", "pl", "mp"})
PRIMITIVES = frozenset({"str", "num", "bool", "any", "event", "tbl", "nil", "ref"})
KINDS = {"str": STR, "num": NUM, "bool": BOOL, "nil": NIL, "raw": ANY}
PRINTABLE = union(STR, NUM, BOOL, Name("obj"), EVENT)
CONCAT = union(STR, NUM)
HANDLER_VALUE = union(STR, BOOL, Name("fn"))
_VERB_ORDER = {"verb": 0, "extend": 1, "remove": 2}

CallableDecl = Union[FnDecl, ExternDecl]


class TypeCheckError(Error):
    """A value cannot be used where its declared type is expected."""


@dataclass
class Context:
    lang: str = "ru"
    root_src: str = ""
    enums: Dict[str, Tuple[Set[str], bool]] = field(default_factory=dict)
    enum_owner: Dict[str, str] = field(default_factory=dict)
    event_names: Set[str] = field(default_factory=set)
    event_args: Dict[str, List[Type]] = field(default_factory=dict)
    event_acted: Set[str] = field(default_factory=set)

    classes: Dict[str, str] = field(default_factory=dict)
    class_decls: Dict[str, EntityDecl] = field(default_factory=dict)
    entity_of: Dict[str, EntityDecl] = field(default_factory=dict)
    objects: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, Dict[str, Type]] = field(default_factory=dict)
    prop_decls: Dict[str, Dict[str, Prop]] = field(default_factory=dict)
    ctors: Dict[str, str] = field(default_factory=dict)
    root_class: Optional[str] = None
    field_names: Set[str] = field(default_factory=set)
    entries: Dict[str, List[Tuple[str, Type]]] = field(default_factory=dict)

    fns: Dict[str, FnDecl] = field(default_factory=dict)
    externs: Dict[str, ExternDecl] = field(default_factory=dict)
    verb_tags: Set[str] = field(default_factory=set)
    globals: Dict[str, Type] = field(default_factory=dict)
    consts: Set[str] = field(default_factory=set)

    def callable_decl(self, name: str) -> Optional[CallableDecl]:
        return self.fns.get(name) or self.externs.get(name)


def attach_item_src(ctx: Context, item: Any, err: Error) -> Error:
    src = getattr(item, "src", "")
    if err.src:
        if err.src == ctx.root_src:
            err.src = ""
        return err
    if src and src != ctx.root_src:
        err.src = src
    return err


# --- Hierarchy & Type Compatibility -----------------------------------------

def root_class(ctx: Context) -> str:
    return ctx.root_class or "obj"

def room_root(ctx: Context) -> str:
    return next((c for c, fs in ctx.prop_decls.items() if "n_to" in fs), "")

def walk_class_chain(ctx: Context, kind: str) -> List[str]:
    chain, cur, seen = [], kind, set()
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = ctx.classes.get(cur)
    return chain

def inherits(ctx: Context, kind: str, root: str) -> bool:
    return root in walk_class_chain(ctx, kind)

def is_empty_collection(t: Type) -> bool:
    inner = types.tbl_inner(t)
    return isinstance(inner, Name) and inner.name == ""

def is_list_type(ctx: Context, t: Type) -> bool:
    one = types.single(t)
    return isinstance(one, Name) and any(ctx.ctors.get(c) == "std.list" for c in walk_class_chain(ctx, one.name))

def is_object_type(ctx: Context, t: Type) -> bool:
    one = types.single(t)
    return isinstance(one, Name) and (one.name in ctx.classes or one.name in ctx.objects)

def objectish(ctx: Context, t: Type) -> bool:
    return any(alt == ANY or isinstance(alt, (Ref, Tbl)) or is_object_type(ctx, alt) for alt in parts(t))

def is_scalar_ref(ctx: Context, typ: Type) -> bool:
    return any(isinstance(alt, Ref) or is_object_type(ctx, alt) for alt in parts(typ))

def is_ref_type(ctx: Context, typ: Type) -> bool:
    return any(is_scalar_ref(ctx, types.tbl_inner(alt) or alt) for alt in parts(typ))


def index_result(ctx: Context, t: Type) -> Optional[Type]:
    res: List[Type] = []
    for alt in parts(t):
        if alt == NIL:
            continue
        if alt == ANY:
            return ANY
        if types.is_tbl(alt):
            inner = types.tbl_inner(alt)
            res.append(inner if inner is not None else ANY)
        elif is_list_type(ctx, alt):
            res.append(Name(root_class(ctx)))
    return union(*res) if res else None


def _ref_fits(ctx: Context, actual: Optional[Type], expected: Optional[Type]) -> bool:
    if expected is None or expected == Name("obj"):
        return True
    if actual is None:
        return False
    return all(
        isinstance(a, Name) and any(
            isinstance(e, Name) and (e.name == "obj" or inherits(ctx, a.name, e.name))
            for e in parts(expected)
        )
        for a in parts(without_nil(actual))
    )


def atom_fits(ctx: Context, actual: Type, expected: Type) -> bool:
    """Can a single (non-union) value type be used where `expected` is wanted?"""
    if expected == ANY or actual == expected:
        return True
    if actual == ANY:
        return False
    if isinstance(expected, Ref):
        if actual == STR:
            return True
        if isinstance(actual, Ref):
            return _ref_fits(ctx, actual.inner, expected.inner)
        return isinstance(actual, Name) and is_object_type(ctx, actual) \
            and _ref_fits(ctx, actual, expected.inner)
    if isinstance(actual, Ref):
        return _ref_fits(ctx, actual.inner, expected)
    if isinstance(expected, Name) and expected.name in ctx.classes:
        return isinstance(actual, Name) and inherits(ctx, actual.name, expected.name)
    if expected == STR and isinstance(actual, Name) \
            and (actual.name in ctx.enums or actual.name == "event"):
        return True
    if types.is_tbl(expected):
        ie = types.tbl_inner(expected)
        if types.is_tbl(actual):
            ia = types.tbl_inner(actual)
            return ia is None or ie is None or is_empty_collection(actual) \
                or is_subtype(ctx, ia, ie)
        return ie is None and is_object_type(ctx, actual)
    if isinstance(expected, Fn):
        if not isinstance(actual, Fn):
            return str(actual) == "fn"
        return len(actual.params) <= len(expected.params) \
            and all(ep == ANY or is_subtype(ctx, ep, ap)
                    for ep, ap in zip(expected.params, actual.params)) \
            and (not actual.rets or not expected.rets or actual.rets == (ANY,)
                 or all(is_subtype(ctx, ar, er) for er, ar in zip(expected.rets, actual.rets)))
    return False


def is_subtype(ctx: Context, actual: Type, expected: Type) -> bool:
    return expected == ANY or actual == expected \
        or all(any(atom_fits(ctx, a, e) for e in parts(expected)) for a in parts(actual))


def need_value(t: Type, where: str, line: int) -> None:
    if types.is_optional(t):
        hint = f" (`if {where}:`)" if where.isidentifier() else ""
        raise TypeCheckError(f"{where}: possible nil, narrow it first{hint}", line)


def expect(ctx: Context, where: str, actual: Type, expected: Optional[Type], line: int = 0):
    if expected is None or expected == ANY or is_subtype(ctx, actual, expected):
        return
    if types.is_optional(actual) and not types.is_optional(expected):
        need_value(actual, where, line)
    raise TypeCheckError(f"{where}: expected {expected}, got {actual}", line)


def close_hint(word: str, pool: Iterable[str], fmt: Callable[[str], str],
               cutoff: float = 0.7) -> str:
    near = difflib.get_close_matches(word, sorted(pool), 1, cutoff)
    return fmt(near[0]) if near else ""


def enum_value(ctx: Context, name: str, enum: str) -> Optional[str]:
    vals, neg = ctx.enums.get(enum, (set(), False))
    bare = name[1:] if (name.startswith("~") and neg) else name
    return enum if bare in vals else None


def enum_hint(ctx: Context, name: str) -> str:
    candidates = {v for vals, _neg in ctx.enums.values() for v in vals}
    return close_hint(name.lstrip("~"), candidates, lambda m: f" (did you mean {m!r}?)")


def no_duplicates(names: Iterable[str], what: str, line: int):
    seen: Set[str] = set()
    for n in names:
        if n in seen:
            raise Error(f"{what} {n!r}: declared twice", line)
        seen.add(n)


def _type_alt_ok(ctx: Context, alt: Type) -> bool:
    if isinstance(alt, Tbl):
        return alt.inner is None or all(_type_alt_ok(ctx, a) for a in parts(alt.inner))
    if isinstance(alt, Ref):
        return alt.inner is None or all(isinstance(a, Name) and a.name in ctx.classes
                                        for a in parts(alt.inner))
    if isinstance(alt, Fn):
        return all(_type_alt_ok(ctx, p) for p in alt.params + alt.rets)
    if isinstance(alt, Name):
        return alt.name in PRIMITIVES or alt.name in ctx.enums or alt.name in ctx.classes
    return all(_type_alt_ok(ctx, a) for a in parts(alt))


def check_type(ctx: Context, typ: Type, where: str, line: int, label: str = "type"):
    for alt in parts(typ):
        if not _type_alt_ok(ctx, alt):
            raise Error(f"{where}: unknown {label} {str(alt)!r}", line)


def check_signature(ctx: Context, decl: CallableDecl):
    no_duplicates((pn for pn, _t in decl.params if pn != "_"),
                  f"fn {decl.name}: parameter", decl.line)
    seen_optional = False
    for pname, ptype in decl.params:
        check_type(ctx, ptype, f"fn {decl.name}({pname})", decl.line)
        optional = types.is_optional(ptype)
        if seen_optional and not optional:
            raise Error(f"fn {decl.name}: required parameter {pname!r} after an optional one",
                        decl.line)
        seen_optional = seen_optional or optional
    for rt in decl.ret_types:
        check_type(ctx, rt, f"fn {decl.name}", decl.line, "return type")
    if decl.variadic is not None:
        check_type(ctx, decl.variadic, f"fn {decl.name}(...)", decl.line)
    if isinstance(decl, ExternDecl) and (decl.params or decl.variadic) and "$" not in decl.template:
        raise Error(f"extern {decl.name}: template uses none of its parameters (expected $1 / $*)",
                    decl.line)


# --- Unified Symbol Resolution ----------------------------------------------

def resolve_global_sym(ctx: Context, name: str,
                       allow_class_str: bool = False) -> Optional[Tuple[str, Type]]:
    """Resolve a non-local name against objects, globals, classes, events and enums."""
    if name in ctx.objects:
        return "obj", Name(ctx.objects[name])
    if name in ctx.globals:
        gt = ctx.globals[name]
        return ("global_ref" if is_scalar_ref(ctx, gt) else "global"), gt
    if allow_class_str and name in ctx.classes:
        return "enum", STR
    if name in ctx.event_names:
        return "event", EVENT
    enum = ctx.enum_owner.get(name.lstrip("~"))
    if enum:
        return "enum", Name(enum)
    return None


def lit_type(ctx: Context, e: Expr) -> Type:
    if isinstance(e, Lit):
        return KINDS.get(e.kind, ANY)
    if isinstance(e, InterpStr):
        return STR
    if isinstance(e, Sym):
        found = resolve_global_sym(ctx, e.name)
        if found is not None:
            e.rk, typ = found
            return typ
        decl = ctx.callable_decl(e.name)
        if decl is not None and all(types.is_optional(pt) for _pn, pt in decl.params):
            e.rk = "value" if (isinstance(decl, ExternDecl) and decl.kind in ("value", "lvalue")) else "fn0"
            return decl.ret_types[0] if decl.ret_types else ANY
    if isinstance(e, ListLit):
        return Tbl(union(*(lit_type(ctx, it) for it in e.items)) if e.items else Name(""))
    if isinstance(e, DictLit):
        return Tbl(union(*(lit_type(ctx, v) for _k, v in e.pairs)) if e.pairs else None)
    return ANY


# --- AST Normalization & Planning -------------------------------------------

def _merge_classes(prog: Program):
    merged: Dict[str, EntityDecl] = {}
    out: List[Any] = []
    for item in prog.items:
        if not (isinstance(item, EntityDecl) and item.kind == "class" and item.name):
            out.append(item)
            continue
        decl = merged.get(item.name)
        if decl is None:
            fresh = replace(item, words=list(item.words), traits=list(item.traits),
                            props=list(item.props), handlers=list(item.handlers))
            merged[item.name] = fresh
            out.append(fresh)
            continue
        if decl.parent and item.parent and decl.parent != item.parent:
            raise Error(f"class {item.name!r}: parent differs from an earlier declaration",
                        item.line)
        decl.parent = decl.parent or item.parent
        decl.ctor = decl.ctor or item.ctor
        decl.words = decl.words or list(item.words)
        decl.traits += [t for t in item.traits if t not in decl.traits]
        decl.props.extend(item.props)
        decl.handlers += [h for h in item.handlers if h not in decl.handlers]
        decl.is_mixin = decl.is_mixin and item.is_mixin
    prog.items = out


def _check_class_cycles(ctx: Context):
    for name, decl in ctx.class_decls.items():
        seen: List[str] = []
        cur = name
        while cur in ctx.class_decls:
            if cur in seen:
                cycle = " -> ".join(seen[seen.index(cur):] + [cur])
                raise attach_item_src(ctx, decl,
                                      Error(f"class {name!r}: inheritance cycle ({cycle})", decl.line))
            seen.append(cur)
            cur = ctx.class_decls[cur].parent or ""


def _order_classes(ctx: Context) -> List[EntityDecl]:
    decls = ctx.class_decls
    order: List[EntityDecl] = []
    placed: Set[str] = set()
    active: Set[str] = set()

    def visit(name: str):
        if name in placed or name not in decls or name in active:
            return
        active.add(name)
        decl = decls[name]
        if decl.parent:
            visit(decl.parent)
        for tr in decl.traits:
            visit(tr)
        active.discard(name)
        placed.add(name)
        order.append(decl)

    for cname in decls:
        visit(cname)
    return order


def _plan_program(ctx: Context, prog: Program):
    _check_class_cycles(ctx)
    items = prog.items
    decls = [it for it in items if isinstance(it, (EventsDecl, TypeDecl, FnDecl, ExternDecl, EntryDecl))]
    luas = [it for it in items if isinstance(it, LuaDecl)]
    vars_ = [it for it in items if isinstance(it, VarDecl)]
    anon_cls = [it for it in items if isinstance(it, EntityDecl) and it.kind == "class" and not it.name]
    objs = [it for it in items if isinstance(it, TalkDecl)
            or (isinstance(it, EntityDecl) and it.kind not in ("class", "impl"))]
    verbs = sorted((it for it in items if isinstance(it, VerbDecl)),
                   key=lambda v: _VERB_ORDER[v.mode])
    impls = [it for it in items if isinstance(it, EntityDecl) and it.kind == "impl"]
    prog.items = decls + luas + vars_ + _order_classes(ctx) + anon_cls + objs + verbs + impls


# --- Declaration, Entity, Verb & Field Collection ---------------------------

def _sig_text(ts: List[Type]) -> str:
    return ", ".join(str(t) for t in ts) if ts else "no arguments"

def _clashes_enum(decl: CallableDecl) -> bool:
    return isinstance(decl, FnDecl) or all(types.is_optional(pt) for _pn, pt in decl.params)

def _verb_tag(item: VerbDecl) -> str:
    return item.tag if item.tag is not None else (item.name if item.name.startswith("#") else f"#{item.name}")


def _verb_pat_sig(pat: str, obj_type: Type) -> Optional[Tuple[str, List[Type], bool]]:
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


def _register_class_decl(ctx: Context, item: EntityDecl):
    assert item.name is not None
    if item.ctor:
        ctx.ctors[item.name] = item.ctor
    if item.parent:
        ctx.classes[item.name] = item.parent
    external = bool(item.ctor) and "." in item.ctor
    if item.parent is None and ctx.root_class is None and not external:
        ctx.root_class = item.name
    ctx.classes.setdefault(item.name, item.name if external else (item.parent or ctx.root_class or item.name))
    ctx.class_decls[item.name] = item
    for p in item.props:
        ctx.field_names.add(p.name)
        if p.typ:
            prev_p = ctx.prop_decls.setdefault(item.name, {}).get(p.name)
            if prev_p is not None and p.emit is None and prev_p.emit is not None:
                p.emit = prev_p.emit
            if prev_p is not None and prev_p.typ is not None and prev_p.typ != p.typ:
                raise Error(f"class {item.name}: field {p.name!r} is already declared as "
                            f"{prev_p.typ}, here as {p.typ}", p.line, p.src)
            ctx.prop_decls[item.name][p.name] = p
            p.is_ref = is_ref_type(ctx, p.typ)


def _register_events_decl(ctx: Context, item: EventsDecl, decl_evs: Dict[str, List[Type]],
                          ext_evs: Dict[str, Tuple[List[Type], int, EventsDecl]]):
    evs, ats = item.names, item.arg_types
    for ev in evs:
        ctx.event_names.add(ev)
        if ctx.callable_decl(ev) is not None:
            raise Error(f"event {ev}: a fn has the same name "
                        f"(a bare name would mean the event)", item.line)
        if item.extend:
            ext_evs[ev] = (list(ats), item.line, item)
        else:
            prev = decl_evs.get(ev)
            if prev is not None and prev != list(ats):
                raise Error(f"event {ev}: declared with {_sig_text(prev)}, "
                            f"here with {_sig_text(list(ats))} "
                            f"(use `extend event` to replace)", item.line)
            decl_evs[ev] = list(ats)


def _register_type_decl(ctx: Context, item: TypeDecl):
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
        existing = ctx.callable_decl(v)
        if existing is not None and _clashes_enum(existing):
            raise Error(f"type {item.name}: fn {v!r} has the same name "
                        f"(a bare name would mean the enum value)", item.line)
        ctx.enum_owner[v] = item.name


def _register_callable_decl(ctx: Context, item: CallableDecl):
    if ctx.callable_decl(item.name) is not None:
        raise Error(f"duplicate fn {item.name!r}", item.line)
    if item.name in ctx.event_names:
        raise Error(f"fn {item.name}: an event has the same name "
                    f"(a bare name would mean the event)", item.line)
    if item.name in ctx.enum_owner and _clashes_enum(item):
        raise Error(f"fn {item.name}: a value of type {ctx.enum_owner[item.name]!r} "
                    f"has the same name (a bare name would mean the enum value)", item.line)
    if isinstance(item, FnDecl):
        ctx.fns[item.name] = item
        return
    if item.kind == "lvalue":
        if item.params or item.variadic:
            raise Error(f"extern lvalue {item.name}: no parameters (it is a place, "
                        f"not a call)", item.line)
        if not item.ret_types:
            raise Error(f"extern lvalue {item.name}: declare the type "
                        f"(`extern lvalue {item.name} -> num = \"...\"`)", item.line)
    ctx.externs[item.name] = item


def _collect_declarations(ctx: Context, prog: Program) -> Dict[str, List[Type]]:
    decl_evs: Dict[str, List[Type]] = {}
    ext_evs: Dict[str, Tuple[List[Type], int, EventsDecl]] = {}
    for item in prog.items:
        try:
            match item:
                case EventsDecl():
                    _register_events_decl(ctx, item, decl_evs, ext_evs)
                case TypeDecl():
                    _register_type_decl(ctx, item)
                case FnDecl() | ExternDecl():
                    _register_callable_decl(ctx, item)
                case EntryDecl():
                    ctx.entries[item.name] = list(item.params)
                case VerbDecl() if item.mode == "verb":
                    tag = _verb_tag(item) or f"#{item.name}"
                    ctx.verb_tags.add(tag)
                    if "verb" in ctx.enums:
                        ctx.enums["verb"][0].add(tag)
                        ctx.enum_owner.setdefault(tag, "verb")
                case EntityDecl() if item.kind == "class" and item.name:
                    _register_class_decl(ctx, item)
        except Error as e:
            raise attach_item_src(ctx, item, e) from None
    for item in prog.items:
        if isinstance(item, EventsDecl):
            for at in item.arg_types:
                try:
                    check_type(ctx, at, f"event {item.names[0]}", item.line, "argument type")
                except Error as e:
                    raise attach_item_src(ctx, item, e) from None
    for ev, (ats, line, src_item) in ext_evs.items():
        if ev not in decl_evs:
            raise attach_item_src(
                ctx, src_item,
                Error(f"extend event {ev}: unknown event (declare it with `event {ev}`)", line),
            )
        decl_evs[ev] = ats
    return decl_evs


def _declare_object(ctx: Context, name: str, kind: str, line: int):
    prev = ctx.objects.get(name)
    if prev is not None and prev != kind:
        raise Error(f"{name}: already declared as {prev}, here as {kind}", line)
    if name in ctx.classes:
        raise Error(f"{name}: an object cannot share the name of a class", line)
    ctx.objects[name] = kind


def _check_override(ctx: Context, ent: EntityDecl):
    if ent.kind == "impl" or ent.name is None:
        return
    bases = ([ent.kind] if ent.kind != "class" else []) + list(ent.traits) \
        + ([ent.parent] if ent.kind == "class" and ent.parent else [])
    for p in ent.props:
        if p.value is not None and not isinstance(p.value, (list, FnRef)):
            base = next(
                (b for b in bases if any(
                    cp.name == p.name and isinstance(cp.value, (list, FnRef))
                    for cur in walk_class_chain(ctx, b)
                    for cp in (ctx.class_decls[cur].props if cur in ctx.class_decls else ())
                )),
                None,
            )
            if base is not None:
                raise Error(
                    f"{ent.name}.{p.name}: cannot overwrite the method of class {base!r} with a value "
                    f"(use a block, `&fn` or `impl {ent.name}`)", p.line)


def _inline_mixin_traits(ctx: Context, ent: EntityDecl, instantiated_classes: Set[str]):
    exp_p, exp_h, kept_tr = [], [], []
    for tr in ent.traits:
        cdecl = ctx.class_decls.get(tr)
        if cdecl and tr not in instantiated_classes:
            exp_p.extend(replace(p) for p in cdecl.props if p.value is not None)
            exp_h.extend(replace(h) for h in cdecl.handlers)
            kept_tr.extend(t for t in cdecl.traits if t not in kept_tr)
        if tr not in kept_tr:
            kept_tr.append(tr)
    ent.traits = kept_tr
    own_p = {p.name for p in ent.props}
    own_h = {(h.phase, tuple(h.events)) for h in ent.handlers}
    ent.props = [p for p in exp_p if p.name not in own_p] + ent.props
    ent.handlers = [h for h in exp_h if (h.phase, tuple(h.events)) not in own_h] + ent.handlers


def known_target(ctx: Context, name: str, allow_engine: bool = False) -> bool:
    return (name in BUILTIN_TARGETS or name.startswith("@")
            or name in ctx.objects or name in ctx.classes
            or (allow_engine and name in ENGINE_OBJECTS))


def _kind_hint(ctx: Context, ent: EntityDecl) -> str:
    if ent.name in ctx.event_names:
        h = close_hint(ent.kind, PHASES, lambda m: f" (did you mean `{m} {ent.name}`?)", 0.75)
        if h:
            return h
    if ent.kind in ctx.field_names:
        return f" (did you mean `{ent.kind} = ...`?)"
    return close_hint(ent.kind, ctx.classes, lambda m: f" (did you mean class {m!r}?)", 0.75)


def _register_entity(ctx: Context, ent: EntityDecl, instantiated_classes: Set[str]):
    if ent.kind == "class" and ent.parent and ent.parent not in ctx.classes:
        raise Error(f"class {ent.name or ''}({ent.parent}): unknown parent class", ent.line)
    _check_override(ctx, ent)
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
    if ent.kind == "impl" and ent.name and not known_target(ctx, ent.name, allow_engine=True):
        raise Error(f"impl {ent.name!r}: unknown target", ent.line)
    for ch in ent.children:
        _register_entity(ctx, ch, instantiated_classes)


def _register_entities(ctx: Context, prog: Program):
    instantiated = {it.kind for it in prog.items if isinstance(it, EntityDecl)}
    for item in prog.items:
        try:
            if isinstance(item, EntityDecl):
                _register_entity(ctx, item, instantiated)
            elif isinstance(item, TalkDecl):
                _declare_object(ctx, item.name, "talk", item.line)
        except Error as e:
            raise attach_item_src(ctx, item, e) from None


def _resolve_verb_events(ctx: Context, prog: Program, base_evs: Dict[str, List[Type]]):
    active_verbs: Dict[str, List[Tuple[str, List[Type], int, VerbDecl]]] = {}
    for item in prog.items:
        if not isinstance(item, VerbDecl):
            continue
        tag = _verb_tag(item)
        if item.mode == "verb" and not item.patterns:
            raise attach_item_src(
                ctx, item,
                Error(f"verb {item.name}: no patterns — the engine needs at least one "
                      f"(write `patterns = [\"{{noun}}/вн : {item.name.lstrip('#')}\"]`)",
                      item.line),
            )
        if item.mode == "remove":
            active_verbs.pop(tag, None)
            continue
        contribs = active_verbs.setdefault(tag, [])
        for pat in item.patterns:
            ps = _verb_pat_sig(pat, Name(root_class(ctx)))
            if ps:
                ctx.event_names.add(ps[0])
                if ps[2]:
                    ctx.event_acted.add(ps[0])
                contribs.append((ps[0], ps[1], item.line, item))

    ctx.event_args = {k: list(v) for k, v in base_evs.items()}
    for ev, sigs in base_evs.items():
        first = without_nil(sigs[0]) if sigs else None
        if isinstance(first, Name) and (first.name.startswith("obj") or first.name in ctx.classes):
            ctx.event_acted.add(ev)
    for contribs in active_verbs.values():
        for ev, slots, line, vitem in contribs:
            if ev in base_evs:
                declared = base_evs[ev]
                if len(slots) != len(declared):
                    raise attach_item_src(
                        ctx, vitem,
                        Error(f"verb pattern for {ev}: {len(slots)} argument(s), "
                              f"the event declares {len(declared)}", line),
                    )
                for i, (got, want) in enumerate(zip(slots, declared)):
                    if not is_subtype(ctx, got, want):
                        raise attach_item_src(
                            ctx, vitem,
                            Error(f"verb pattern for {ev}: argument {i + 1} is {got}, "
                                  f"the event declares {want}", line),
                        )
            elif ev not in ctx.event_args:
                ctx.event_args[ev] = list(slots)
            else:
                ctx.event_args[ev] = [union(a or NIL, b or NIL)
                                      for a, b in zip_longest(ctx.event_args[ev], slots)]


def entity_kind(ctx: Context, ent: EntityDecl) -> str:
    if ent.kind == "class":
        return ent.name or ""
    if ent.kind == "impl":
        return ctx.objects.get(ent.name or "", root_class(ctx))
    return ent.kind


def decl_of(ctx: Context, target: Any, name: str) -> Optional[Prop]:
    def find_in(kind: str) -> Optional[Prop]:
        return next((ctx.prop_decls[c][name] for c in walk_class_chain(ctx, kind)
                     if name in ctx.prop_decls.get(c, {})), None)

    ent = ctx.entity_of.get(target) if isinstance(target, str) else target
    if ent is None:
        return find_in(ctx.objects.get(target, target))
    scopes = ([ent.name or "", ent.parent] if ent.kind == "class"
              else [entity_kind(ctx, ent)]) + list(ent.traits)
    orig = ctx.entity_of.get(ent.name or "") if ent.kind == "impl" else None
    if orig is not None:
        scopes += [orig.kind] + list(orig.traits)
    return next((d for s in scopes if s in ctx.classes for d in (find_in(s),) if d), None)


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
    base_cls = ent.parent if ent.kind == "class" else ent.kind
    for src_cls in [base_cls] + [tr for tr in ent.traits if tr in ctx.classes]:
        for k, v in ctx.fields.get(src_cls, {}).items():
            fmap.setdefault(k, v)
    for p in ent.props:
        try:
            if p.typ:
                check_type(ctx, p.typ, f"{ent.name or ''}.{p.name}".lstrip("."), p.line)
        except Error as e:
            raise attach_item_src(ctx, p, e) from None
        decl = decl_of(ctx, ent, p.name)
        if decl is not None:
            p.typ = p.typ or decl.typ
            p.emit = p.emit or decl.emit
            p.type_params = p.type_params or decl.type_params
        p.is_ref = bool(p.typ and is_ref_type(ctx, p.typ))
        if p.value is not None and ent.name:
            if isinstance(p.value, Expr) and not isinstance(p.value, (FnRef, Lambda)):
                vt = lit_type(ctx, p.value)
                if p.typ is not None and (vt == ANY or is_empty_collection(vt)):
                    vt = p.typ
            else:
                vt = p.typ if p.typ is not None else Name("fn")
            fmap[p.name] = vt
        elif p.typ and ent.name:
            fmap[p.name] = p.typ
    for ch in ent.children:
        _collect_entity_fields(ctx, ch)


def _collect_var_decl(ctx: Context, item: VarDecl):
    for vn, vt, ve, vl in item.items:
        if vn in ctx.globals:
            raise Error(f"global {vn}: declared twice", vl)
        if vn in ctx.objects or vn in ctx.classes:
            raise Error(f"global {vn}: an object or a class has this name", vl)
        got = lit_type(ctx, ve)
        if vt is not None:
            check_type(ctx, vt, f"global {vn}", vl)
            if got != ANY:
                expect(ctx, f"global {vn}", got, vt, vl)
        if isinstance(ve, Sym) and not ve.rk:
            raise Error(f"{vn}: unknown name {ve.name!r}", vl)
        ctx.globals[vn] = vt if vt is not None else got
        if item.kind == "const":
            ctx.consts.add(vn)


def _collect_fields_and_refs(ctx: Context, prog: Program):
    for item in prog.items:
        try:
            match item:
                case VarDecl():
                    _collect_var_decl(ctx, item)
                case EntityDecl():
                    _collect_entity_fields(ctx, item)
                case TalkDecl():
                    _collect_entity_fields(
                        ctx, EntityDecl(kind="talk", name=item.name, props=item.props, line=item.line)
                    )
                case VerbDecl() as vd:
                    if vd.mode == "extend":
                        tag = _verb_tag(vd) or f"#{vd.name}"
                        base = tag.lstrip("#")
                        if base not in ctx.event_names and tag not in ctx.verb_tags:
                            raise Error(f"extend verb {tag}: unknown verb "
                                        f"(declare it with `verb {base}` first)", vd.line)
                    if vd.target and not known_target(ctx, vd.target):
                        raise Error(f"verb {vd.name.split('#')[-1]}: unknown target {vd.target!r}",
                                    vd.line)
        except Error as e:
            raise attach_item_src(ctx, item, e) from None


def build_context(prog: Program) -> Context:
    ctx = Context(lang=prog.lang, root_src=prog.root_src)
    _merge_classes(prog)
    base_evs = _collect_declarations(ctx, prog)
    _plan_program(ctx, prog)
    _register_entities(ctx, prog)
    _resolve_verb_events(ctx, prog, base_evs)
    _collect_fields_and_refs(ctx, prog)
    return ctx
