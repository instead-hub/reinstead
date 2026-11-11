"""Minimalist symbol collector and type checker for MISE 2."""
import os
import re
from itertools import zip_longest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from . import types
from .ast_nodes import *
from .parser import PHASES, parse_source
from .types import ANY, NIL, Fn, Name, Ref, Tbl, Type, \
    opt, parts, ref_inner, union, without_nil

STR, NUM, BOOL, EVENT = Name("str"), Name("num"), Name("bool"), Name("event")
TBL = Tbl(None)          # a bare table: no element type

# the class that declares the compass fields (`n_to` ...) is the room-like root
_SLOT_OBJ_RE = re.compile(r"\{(?:noun|noun_obj|compass\w*)\}")
# names of the current event: the handler parameter and the engine accessor
CURRENT_EVENT = frozenset({"ev", "event"})
# engine fields the game must not assign (the engine owns them)
READONLY_FIELDS = frozenset({"nam"})
# objects the engine creates itself: `_'player'` resolves at load (`pl` is its global)
ENGINE_OBJECTS = frozenset({"player"})


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
    fields: Dict[str, Dict[str, Tuple[Type, bool]]] = field(default_factory=dict)
    prop_decls: Dict[str, Dict[str, Prop]] = field(default_factory=dict)   # declared class fields
    ctors: Dict[str, str] = field(default_factory=dict)                  # class -> engine constructor
    root_class: Optional[str] = None                                     # the first class with no parent
    field_names: Set[str] = field(default_factory=set)
    entries: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)  # engine entry points
    lua_globals: Dict[str, GlobalDecl] = field(default_factory=dict)     # `extern global`

    fns: Dict[str, FnDecl] = field(default_factory=dict)
    verb_tags: Set[str] = field(default_factory=set)     # tags of `verb`/`extend verb`
    used_refs: Set[str] = field(default_factory=set)
    lua_funcs: Set[str] = field(default_factory=set)
    globals: Dict[str, Tuple[Type, bool]] = field(default_factory=dict)






# --- Type compatibility -----------------------------------------------------

# type names that are part of the type language; object types are classes
PRIMITIVES = frozenset({"str", "num", "bool", "any", "event", "tbl", "nil", "ref"})
_KINDS = {"str": STR, "num": NUM, "bool": BOOL, "nil": NIL, "raw": ANY, "table": Tbl(None)}
# what interpolation accepts: the engine prints any value with `tostr`
_PRINTABLE = union(STR, NUM, BOOL, Name("obj"), EVENT)
# what Lua's `..` accepts: an object is a table, the engine defines no `__concat`
_CONCAT = union(STR, NUM)
# what a handler may hold as a value: a text, a boolean or a function
_HANDLER_VALUE = union(STR, BOOL, Name("fn"))


def _atom_fits(ctx: Context, actual: Type, expected: Type) -> bool:
    """Can a single (non-union) value type be used where `expected` is wanted?"""
    if expected == ANY or actual == expected:
        return True
    if actual == ANY:
        return False  # `any` never silently narrows into a concrete type
    if isinstance(expected, Ref):
        if actual == STR:
            return True                    # a name of an object (the engine resolves it)
        got = ref_inner(actual)
        if got is not None:
            return _obj_fits(ctx, got, expected.name)
        if isinstance(actual, Name) and _is_object_type(ctx, actual):
            return _obj_fits(ctx, actual.name, expected.name)
        return False
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
            if ia is None or ie is None:
                return True
            if isinstance(ia, Name) and ia.name == "":
                return True                # `[]` fits any table
            return is_subtype(ctx, ia, ie)
        # a class instance is a Lua table, but `list` holds objects, not `tbl[str]`
        return ie is None and _is_object_type(ctx, actual)
    if isinstance(expected, Fn):
        if not isinstance(actual, Fn):
            return str(actual) == "fn"        # a value of a `lua` block: nothing is known
        if len(actual.params) > len(expected.params):
            return False                      # a callback may ignore extra arguments
        if not all(is_subtype(ctx, ep, ap)    # params are contravariant
                   for ep, ap in zip(expected.params, actual.params)):
            return False
        if not actual.rets or not expected.rets:
            return True
        return all(is_subtype(ctx, ar, er)    # returns are covariant, extras ignored
                   for er, ar in zip(expected.rets, actual.rets))
    return False


def _obj_fits(ctx: Context, actual_name: str, expected_name: str) -> bool:
    """`actual` is an object class/name that must fit `expected` (`A|B`, a class)."""
    if not expected_name or expected_name == "obj":
        return True
    if not actual_name:                    # a bare `ref`: some object, but which one?
        return False
    actual_name = str(without_nil(types.parse(actual_name) if isinstance(actual_name, str)
                                 else actual_name))
    return any(a in ("obj", "") or a == actual_name or _inherits(ctx, actual_name, a)
               for a in (p.strip() for p in expected_name.split("|")))


def is_subtype(ctx: Context, actual: Type, expected: Type) -> bool:
    """Does every alternative of `actual` fit some alternative of `expected`?"""

    if expected == ANY or actual == expected:
        return True
    return all(any(_atom_fits(ctx, a, e) for e in parts(expected))
               for a in parts(actual))


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
    first = next((t for t in toks if _SLOT_OBJ_RE.search(t) or t in ("*", "~*")), "")
    acted = bool(_SLOT_OBJ_RE.search(first)) and not first.startswith("~")
    slots = [obj_type if _SLOT_OBJ_RE.search(t) else STR
             for t in toks if _SLOT_OBJ_RE.search(t) or t in ("*", "~*")]
    if len(ev_parts) > 1 and ev_parts[1] == "reverse" and len(slots) >= 2:
        slots[0], slots[1] = slots[1], slots[0]
    return ev_parts[0], slots, acted


# engine print helpers and plain Lua functions callable from game logic
def prescan(prog: Program) -> Context:
    ctx = Context(lang=prog.lang)
    base_evs, class_at = _collect_declarations(ctx, prog)
    _register_entities(ctx, prog, class_at)
    _resolve_verb_events(ctx, prog, base_evs)   # events from patterns are known after this
    _check_declared_refs(ctx, prog)
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
            _check_field_redeclared(item, p, prev_p)
            ctx.prop_decls[item.name][p.name] = p
            p.is_ref = _is_ref_type(ctx, p.typ)


def _check_field_redeclared(item: EntityDecl, p: Prop, prev: Optional[Prop]):
    """A class declaration of a field keeps its type: a game must not rewrite the
    engine's contract (`class obj / nam: num`). A *subclass* may narrow a field
    (`class talk / obj: tbl[choice]` is not a conflict with `class obj / obj`)."""
    if prev is not None and prev.typ is not None and prev.typ != p.typ:
        raise Error(f"class {item.name}: field {p.name!r} is already declared as "
                    f"{prev.typ}, here as {p.typ}", p.line)


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
                    if ev in ctx.fns:
                        raise Error(f"event {ev}: a fn has the same name "
                                    f"(a bare name would mean the event)", item.line)
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
            if item.name in ctx.event_names:
                raise Error(f"fn {item.name}: an event has the same name "
                            f"(a bare name would mean the event)", item.line)
            ctx.fns[item.name] = item
        elif isinstance(item, EntryDecl):
            ctx.entries[item.name] = list(item.params)
        elif isinstance(item, GlobalDecl):
            ctx.lua_globals[item.name] = item
        elif isinstance(item, VerbDecl):
            if item.mode == "verb":            # `extend` needs one of these to exist
                ctx.verb_tags.add(item.tag or (item.name if item.name.startswith("#")
                                               else f"#{item.name}"))
        elif isinstance(item, LuaDecl):
            for m in re.finditer(r"\bfunction\s+([A-Za-z_]\w*)", item.code):
                ctx.lua_funcs.add(m.group(1))
        elif isinstance(item, EntityDecl) and item.kind == "class" and item.name:
            _register_class_decl(ctx, item, idx, class_at)
    base_evs.update(decl_evs)
    base_evs.update(_apply_event_extends(decl_evs, ext_evs))
    return base_evs, class_at


def _declare_object(ctx: Context, name: str, kind: str, line: int):
    """One name, one role: an object/talk name is not a class, a global or another kind."""
    prev = ctx.objects.get(name)
    if prev is not None and prev != kind:
        raise Error(f"{name}: already declared as {prev}, here as {kind}", line)
    if name in ctx.classes:
        raise Error(f"{name}: an object cannot share the name of a class", line)
    ctx.objects[name] = kind

def _declare_event(decl_evs: Dict[str, List[str]], ev: str, ats: List[str], item: Any):
    """`event X: T` — a declaration; a different signature is a conflict."""
    prev = decl_evs.get(ev)
    if prev is not None and prev != list(ats):
        raise Error(f"event {ev}: declared with {_sig_text(prev)}, "
                    f"here with {_sig_text(list(ats))} "
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


def _no_duplicates(names: Any, what: str, line: int):
    """`fn f(a, a)`, `local a, a`, two parameters of one handler — a silent override."""
    seen: Set[str] = set()
    for n in names:
        if n in seen:
            raise Error(f"{what} {n!r}: declared twice", line)
        seen.add(n)


def _attr_values(ctx: Context) -> Set[str]:
    """The values of `type attr` — a trait may name a class, or one of them."""
    return ctx.enums.get("attr", (set(), False))[0]


def _check_parent(ctx: Context, ent: EntityDecl):
    """A class parent must name a declared class."""
    if ent.kind == "class" and ent.parent and ent.parent not in ctx.classes:
        raise Error(f"class {ent.name or ''}({ent.parent}): unknown parent class", ent.line)


def _register_entity(ctx: Context, ent: EntityDecl, idx: int,
                     class_at: Dict[str, int], instantiated_classes: Set[str]):
    _check_class_order(ent, idx, class_at)
    _check_parent(ctx, ent)
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
            _declare_object(ctx, ent.name, ent.kind, ent.line)
            ctx.entity_of[ent.name] = ent
    if ent.kind == "impl" and ent.name and ent.name not in ("game", "pl", "mp") \
            and not ent.name.startswith("@") and ent.name not in ctx.objects \
            and ent.name not in ctx.classes and ent.name not in ENGINE_OBJECTS:
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


def _check_verb(ctx: Context, item: VerbDecl):
    """A verb's `hint` is a handler-like value; `extend verb` needs an existing verb."""
    if item.mode == "extend":
        tag = item.tag or (item.name if item.name.startswith("#") else f"#{item.name}")
        base = tag.lstrip("#")
        if base not in ctx.event_names and tag not in ctx.verb_tags:
            raise Error(f"extend verb {tag}: unknown verb "
                        f"(declare it with `verb {base}` first)", item.line)
    hint = item.hint
    if hint is None:
        return
    where = f"verb {item.name.split('#')[-1]}: hint"
    fnsig = Fn((Name(_root(ctx)),), (STR,))
    if isinstance(hint, FnRef):
        _check_fn_target(ctx, hint)
        _check_fnref(ctx, hint, fnsig, where)
    elif isinstance(hint, list):
        rets: List[Type] = []
        _check_stmts(ctx, hint, {"s": Name(_root(ctx))}, None, rets)
        if rets and not any(is_subtype(ctx, t, STR) for t in rets):
            raise TypeCheckError(f"{where}: returns {'|'.join(str(t) for t in rets)}, "
                                 f"expected str", item.line)
    elif isinstance(hint, Expr):
        _check_expr(ctx, hint, {"s": Name(_root(ctx))}, None, _HANDLER_VALUE)


def _check_declared_refs(ctx: Context, prog: Program):
    """Names that must exist: a verb's target object and an object's `@` location."""
    for item in prog.items:
        if isinstance(item, VerbDecl):
            _check_verb(ctx, item)
        if isinstance(item, VerbDecl) and item.target \
                and item.target not in ("game", "pl", "mp") \
                and not item.target.startswith("@") \
                and item.target not in ctx.objects and item.target not in ctx.classes:
            raise Error(f"verb {item.name.split('#')[-1]}: unknown target {item.target!r}",
                        item.line)
        elif isinstance(item, EntityDecl):
            for loc in item.locations:
                if loc not in ctx.objects and loc not in ctx.classes:
                    raise Error(f"{item.name or item.kind}: unknown location {loc!r} "
                                f"(declare it above)", item.line)
            for tr in item.traits:
                base = tr.lstrip("~")       # `~light` — a negated attribute
                if base in ctx.classes or base in _attr_values(ctx):
                    continue
                if item.kind == "impl" and base in ctx.event_names:
                    continue                # `impl mp : Take` — the events it serves
                raise Error(f"{item.name or item.kind}: unknown trait {tr!r} (a class, "
                            f"a `type attr` value or, for `impl`, an event)", item.line)


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
                    ps = _verb_pat_sig(pat, Name(_root(ctx)))
                    if ps:
                        ctx.event_names.add(ps[0])
                        if ps[2]:
                            ctx.event_acted.add(ps[0])
                        contribs.append((ps[0], ps[1], item.line))

    ctx.event_args = {k: list(v) for k, v in base_evs.items()}
    for ev, sigs in base_evs.items():
        first = sigs[0] if sigs else None
        if first is not None and isinstance(without_nil(first), Name) \
                and (str(without_nil(first)).startswith("obj")
                     or str(without_nil(first)) in ctx.classes):
            ctx.event_acted.add(ev)
    for contribs in active_verbs.values():
        for ev, slots, line in contribs:
            if ev in base_evs:
                _check_pattern_fits(ctx, ev, slots, base_evs[ev], line)
                continue
            cur = ctx.event_args.get(ev)
            if cur is None:
                ctx.event_args[ev] = list(slots)
            else:                       # a slot only some patterns provide is `?`
                ctx.event_args[ev] = [union(a or NIL, b or NIL)
                                      for a, b in zip_longest(cur, slots)]


def _decl_scope(ctx: Context, ent: EntityDecl) -> List[str]:
    """The declarations an entity sees: its kind, its traits, and (for `impl`) the
    traits of the object it patches (`impl box` sees what `obj box : Box` declared)."""
    scopes = ([ent.name or "", ent.parent] if ent.kind == "class"
              else [_entity_kind(ctx, ent)]) + list(ent.traits)
    target = ctx.entity_of.get(ent.name or "")
    if ent.kind == "impl" and target is not None:
        scopes += [target.kind] + list(target.traits)
    return [s for s in scopes if s]


def _decl_of_holder(ctx: Context, holder: str, name: str) -> Optional[Prop]:
    """The declaration of a field seen through a holder: a class chain or an object."""
    if holder not in ctx.objects:
        return _decl_prop(ctx, holder, name)
    ent = ctx.entity_of.get(holder)
    scopes = _decl_scope(ctx, ent) if ent is not None else [ctx.objects[holder]]
    return _decl_of(ctx, scopes, name)


def _decl_of(ctx: Context, scopes: List[str], name: str) -> Optional[Prop]:
    """The declaration of a field among the scopes of an entity."""
    for cur in scopes:
        decl = _decl_prop(ctx, cur, name) if cur in ctx.classes else None
        if decl is not None:
            return decl
    return None


def _check_pattern_fits(ctx: Context, ev: str, slots: List[Type], declared: List[Type],
                        line: int):
    """The engine passes what the pattern captured: an event declared with another
    arity would hand the handler nil (or a value of the wrong type)."""
    if len(slots) != len(declared):
        raise Error(f"verb pattern for {ev}: {len(slots)} argument(s), "
                    f"the event declares {len(declared)}", line)
    for i, (got, want) in enumerate(zip(slots, declared)):
        if not is_subtype(ctx, got, want):
            raise Error(f"verb pattern for {ev}: argument {i + 1} is {got}, "
                        f"the event declares {want}", line)


def _declared_ref(ctx: Context, scopes: List[str], name: str) -> bool:
    """Is this field declared with a reference type by the class chain or a trait?"""
    decl = _decl_of(ctx, scopes, name)
    return bool(decl is not None and decl.typ is not None and _is_ref_type(ctx, decl.typ))


def _collect_entity_fields(ctx: Context, ent: EntityDecl):
    for p in ent.props:
        ctx.field_names.add(p.name)
    fmap = ctx.fields.setdefault(ent.name, {}) if ent.name else {}
    base = ent.parent if ent.kind == "class" else ent.kind
    for src in [base] + [tr for tr in ent.traits if tr in ctx.classes]:
        for k, v in ctx.fields.get(src, {}).items():
            fmap.setdefault(k, v)
    scopes = _decl_scope(ctx, ent)
    for p in ent.props:
        # `is_ref` is the declared contract: a field of the class chain (or a trait)
        # whose type says "reference". It decides whether the value is validated as
        # an object name and whether the emitter writes it bare or quoted.
        p.is_ref = bool(p.typ and _is_ref_type(ctx, p.typ)) \
            or _declared_ref(ctx, scopes, p.name)
        if p.value is not None and ent.name:
            vt, is_r = _lit_type(ctx, p.value) if isinstance(p.value, Expr) \
                else (Name("fn"), False)
            decl = _decl_of(ctx, scopes, p.name)
            if decl is not None and decl.typ is not None and _is_empty_collection(vt):
                vt, is_r = decl.typ, p.is_ref   # `items = []` keeps `items: tbl[T]`
            fmap[p.name] = (vt, is_r)
        elif p.typ and ent.name:
            fmap[p.name] = (p.typ, p.is_ref)
    for ch in ent.children:
        _collect_entity_fields(ctx, ch)


def _collect_fields_and_refs(ctx: Context, prog: Program):
    for item in prog.items:
        if isinstance(item, VarDecl):
            for vn, ve, _l in item.items:
                if vn in ctx.globals:
                    raise Error(f"global {vn}: declared twice", _l)
                if vn in ctx.objects or vn in ctx.classes:
                    raise Error(f"global {vn}: an object or a class has this name", _l)
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
        if falls_through and not types.is_optional(union(*item.ret_types)):
            raise Error(f"fn {item.name}: {', '.join(str(t) for t in item.ret_types)} is declared, but a "
                        f"path leaves the body without `return` (add `return` or `pass`, "
                        f"or declare `{without_nil(item.ret_types[0])}?`)", item.line)
    else:
        if rets and falls_through:
            rets.append(NIL)
        item.ret_types = [union(*rets)] if rets else [ANY]


def _typecheck_program(ctx: Context, prog: Program):
    for item in prog.items:
        if isinstance(item, FnDecl):
            _typecheck_fn(ctx, item)
    for item in prog.items:
        if isinstance(item, EntityDecl):
            _check_entity(ctx, item)
        elif isinstance(item, TalkDecl):
            _check_talk(ctx, item)


def _lit_type(ctx: Context, e: Expr) -> Tuple[Type, bool]:
    if isinstance(e, Lit):
        if e.kind == "table":            # `{ … }` — a Lua table
            return TBL, False
        return _KINDS.get(e.kind, ANY), False
    if isinstance(e, InterpStr):
        return STR, False
    if isinstance(e, Sym):
        if e.name in ctx.objects:
            e.rk = "obj"
            return Name(ctx.objects[e.name]), True
        if e.name in ctx.event_names:
            e.rk = "event"
            return EVENT, False
        enum = ctx.enum_owner.get(e.name.lstrip("~"))
        if enum:
            e.rk = "enum"
            return Name(enum), False
    if isinstance(e, ListLit):
        inner = union(*(_lit_type(ctx, it)[0] for it in e.items)) if e.items else Name("")
        return Tbl(inner), False
    return ANY, False


def _check_ref_prop(ctx: Context, ent_name: Optional[str], p: Prop):
    """A reference field holds a bare object name (or a list of them)."""
    if not p.is_ref or p.value is None or isinstance(p.value, (list, FnRef)):
        return
    where = f"{ent_name}.{p.name}" if ent_name else p.name
    val = p.value
    if isinstance(val, Lit) and val.kind == "str":
        raise Error(f"{where}: object reference must be a bare name, not a quoted string "
                    f"({val.val!r})", p.line)
    if isinstance(val, Lit) and val.kind in ("raw", "lua", "num", "bool", "nil"):
        return
    for it in (val.items if isinstance(val, ListLit) else [val]):
        if isinstance(it, Lit) and it.kind == "str" and isinstance(val, ListLit):
            name = it.val.strip()
        elif isinstance(it, Sym):
            name = it.name
        elif isinstance(it, (Lit, ListLit, FnRef)):
            continue                     # raw/nil/bool/number/tables and handlers
        else:
            raise Error(f"{where}: expected object reference, got expression", p.line)
        if name not in ctx.objects:
            raise Error(f"{where}: unknown object reference {name!r}", it.line or p.line)


def _check_var_ref(ctx: Context, name: str, val: Expr, line: int):
    """A bare name as an initial value must be a declared object, event or enum value."""
    if not isinstance(val, Sym):
        return
    n = val.name
    if n in ctx.objects or n in ctx.event_names or n.lstrip("~") in ctx.enum_owner:
        return
    raise Error(f"{name}: unknown name {n!r}", line)


def _is_ref_type(ctx: Context, typ: Type) -> bool:
    """Does this declared type hold object references (a name or an object)?"""
    for alt in parts(typ):
        if isinstance(alt, Ref) or _is_object_type(ctx, alt):
            return True
        inner = types.tbl_inner(alt)
        if inner is not None and (isinstance(inner, Ref) or _is_object_type(ctx, inner)):
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


def _prop_body_env(ctx: Context, kind: str, p: Prop) -> Dict[str, Type]:
    """Parameters of a prop body, taken from the declared `fn(...)` of the field."""
    decl = _decl_prop(ctx, kind, p.name)
    names: List[str] = list(decl.type_params) if decl and decl.type_params else []
    if p.params is None and names:
        p.params = list(names)
    env: Dict[str, Type] = {}
    one = types.fn_of(decl.typ) if decl is not None and decl.typ is not None else None
    if one is not None:
        for i, t in enumerate(one.params):
            env[names[i] if i < len(names) and names[i] else f"_{i}"] = t
    env.setdefault("s", Name(_root(ctx)))
    for pn in p.params or []:
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
    scopes = _decl_scope(ctx, ent)
    _no_duplicates((p.name for p in ent.props), f"{owner or kind}: field", ent.line)
    _no_duplicates((f"{h.phase} {','.join(h.events)}" for h in ent.handlers),
                   f"{owner or kind}: handler", ent.line)
    for p in ent.props:
        _check_ref_prop(ctx, owner, p)
        where = f"{owner}.{p.name}" if owner else p.name
        decl = _decl_of(ctx, scopes, p.name)
        declared = decl.typ if decl else None
        if isinstance(p.value, FnRef):
            _check_fn_target(ctx, p.value)
            ctx.used_refs.add(p.value.name)
            _check_fnref(ctx, p.value, declared, where)
        elif isinstance(p.value, list):
            env = _prop_body_env(ctx, kind, p)
            env["load"] = BOOL
            if declared is not None and types.fn_of(declared) is None:
                raise TypeCheckError(f"{where}: expected {declared}, got a block "
                                     f"(a block is a function)", p.line)
            rets: List[str] = []
            _check_stmts(ctx, p.value, env, owner, rets)
            want = types.fn_returns(declared) if declared else []
            for t in rets:
                if want and not any(is_subtype(ctx, t, w) for w in want):
                    raise TypeCheckError(f"{where}: return {t}, declared returns "
                                         f"{', '.join(str(w) for w in want)}", p.line)
        elif isinstance(p.value, Lit) and p.value.kind == "lua":
            _prop_body_env(ctx, kind, p)  # populates p.params if declared on the class
        elif isinstance(p.value, Expr):
            _check_expr(ctx, p.value, {"s": Name(_root(ctx))}, owner, declared)
        emit = decl.emit if decl else None
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
            sig = Fn(tuple(t for _n, t in params), ())
            _check_fnref(ctx, h.body, sig, f"{owner or kind}: {h.phase} {','.join(h.events)}")
        elif isinstance(h.body, list):
            _check_stmts(ctx, h.body, dict(params), owner, None, arg_names)
        elif isinstance(h.body, Expr):
            # a handler holds a string, a boolean or a function (as the engine allows)
            _check_expr(ctx, h.body, dict(params), owner, _HANDLER_VALUE)
    for ch in ent.children:
        _check_entity(ctx, ch)


# Names of a handler's parameters, in order: `s`, then the arguments.
HANDLER_PARAMS = ("s", "w", "wh", "w2", "w3")


def _handler_event_args(ctx: Context, h: Handler) -> List[Type]:
    """The event's arguments, merged over the handler's events."""
    per = [list(ctx.event_args.get(ev) or []) for ev in h.events]
    n = max((len(x) for x in per), default=0)
    out: List[Type] = []
    for i in range(n):
        ts = [x[i] for x in per if i < len(x)]
        t = union(*dict.fromkeys(ts))
        if any(i >= len(x) for x in per) and not types.is_optional(t):
            t = opt(t)              # only some of the events pass this argument
        out.append(t)
    return out


def _handler_params(ctx: Context, owner: Optional[str], kind: str, h: Handler
                    ) -> Tuple[List[Tuple[str, Type]], Dict[int, str]]:
    """What a handler receives, and which parameter name each event argument has.

    The engine calls a handler as `(receiver, *action_args)`; when the receiver is
    the acted object itself the object is stripped from the arguments, otherwise
    it is passed as the first argument (named `w`).
    """
    self_t = Name(kind) if (kind in ctx.classes or kind in ctx.objects) else Name(_root(ctx))
    params: List[Tuple[str, Type]] = [("s", self_t)]
    arg_names: Dict[int, str] = {}
    is_any = any(ev in ("Any", "Default") for ev in h.events)
    if is_any:                      # `before_Default(s, ev, w, wh)` and `before_Any(...)`
        params += [("ev", EVENT), ("w", Name(_root(ctx))), ("wh", Name(_root(ctx)))]
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
        params.append(("w", Name(_root(ctx))))
        arg_names[0] = "w"
    for i, st in enumerate(sigs[1:] if acted else sigs, start=1 if acted else 0):
        name = HANDLER_PARAMS[len(params)]
        params.append((name, st))
        arg_names[i] = name
    if h.params is not None:                      # the handler names its own
        _no_duplicates(iter(h.params), f"{h.phase} {','.join(h.events)}: parameter", h.line)
        if len(h.params) > len(params):
            raise Error(f"{h.phase} {','.join(h.events)}: the engine passes "
                        f"{len(params)} parameter(s) here, the handler declares {len(h.params)}",
                        h.line)
        params = [(h.params[i], params[i][1]) for i in range(len(h.params))]
    return params, arg_names


# the `choice` fields that are written as `name = …` in a choice (a condition is
# a truthiness test, like `if`, so it is not among them)
CHOICE_FIELDS = ("ask", "reply", "do", "onempty")


def _check_talk_body(ctx: Context, part: Any, env: Dict[str, Type], owner: str,
                     want: Optional[Type] = None, where: str = "", line: int = 0):
    """A `talk` field is a value, a block or a `&fn` — checked against its type."""
    if isinstance(part, FnRef):
        _check_fn_target(ctx, part)
        ctx.used_refs.add(part.name)
        _check_fnref(ctx, part, want, where)
    elif isinstance(part, list):
        rets: List[Type] = []
        _check_stmts(ctx, part, dict(env), owner, rets)
        returns = types.fn_returns(want) if want is not None else ()
        for t in rets if returns else ():
            expect(ctx, where, t, union(*returns), line)
    elif isinstance(part, Expr):
        _check_expr(ctx, part, dict(env), owner, want)


def _choice_type(ctx: Context, name: str) -> Optional[Type]:
    """The declared type of a `choice` field (`class choice` in core.mise)."""
    decl = _decl_prop(ctx, "choice", name)
    return decl.typ if decl else None


def _check_talk(ctx: Context, td: TalkDecl):
    env = {"s": Name("talk")}
    own = ctx.fields.setdefault(td.name, {})
    for p in td.props:                       # talk-level fields (a game may add its own)
        own[p.name] = _lit_type(ctx, p.value) if isinstance(p.value, Expr) else (Name("fn"), False)
    for name, spec in ctx.fields.get("talk", {}).items():   # what `class talk` declares
        own.setdefault(name, spec)
    _no_duplicates((p.name for p in td.props), f"talk {td.name}: field", td.line)
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
        members_ = [(c.cond, None, "when")] + [
            (getattr(c, f), _choice_type(ctx, f), f) for f in CHOICE_FIELDS
        ]
        for part, want, what in members_:
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
                if s.else_body is not None and _returns_all(s.else_body) \
                        and all(_returns_all(b) for _c, b, _l in s.branches):
                    return True
                return at(i + 1)          # no `else`: the path continues after the `if`
            if isinstance(s, MatchStmt):
                has_default = any(len(p) == 1 and isinstance(p[0], Sym) and p[0].name == "_" and not g
                                  for p, g, _b, _l in s.arms)
                if has_default and all(_returns_all(b) for _p, _g, b, _l in s.arms):
                    return True
                return at(i + 1)
            i += 1
        return False

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


def _narrow_event_args(ctx: Context, ev_names: List[str], res: Dict[str, Type],
                       arg_names: Optional[Dict[int, str]]):
    if not ev_names or not arg_names:
        return
    alts = [ctx.event_args.get(n) or [] for n in ev_names]
    for i in range(max((len(a) for a in alts), default=0)):
        types = [a[i] for a in alts if i < len(a)]
        name = arg_names.get(i)
        if types and name and name in res:
            res[name] = union(*set(types))


def _is_event_sym(e: Expr, env: Dict[str, Type]) -> bool:
    return isinstance(e, Sym) and (
        e.name in CURRENT_EVENT or without_nil(env.get(e.name, ANY)) == EVENT
    )


def _narrow(ctx: Context, cond: Expr, env: Dict[str, Type], truthy: bool,
            arg_names: Optional[Dict[int, str]] = None) -> Dict[str, Type]:
    """Refine optional types inside a branch of `if`/`when`/`match`.

    Handled conditions: `x`, `not x`, `x != nil` / `x == nil`, `a and b`,
    `a or b` (short circuit) and `ev == Event` (event argument narrowing).
    """
    res = dict(env)
    if isinstance(cond, Bind) and truthy:
        vt = cond.vtyp or ANY
        for n in cond.names:
            res[n] = without_nil(vt) if vt != ANY else ANY
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
                    plain = (cond.op == "!=") == truthy  # `!= nil` really means "not nil"
                    res[a.name] = without_nil(res[a.name]) if plain else NIL
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
        for t in vt:
            expect(ctx, f"'{s.op}'", t, NUM, s.line)
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
        if cur is not None and s.op in ("+=", "-=") and cur != ANY:
            expect(ctx, f"{name} ({s.op})", cur, NUM, s.line)
        if cur in (None, ANY) and vt and s.op == "=":
            env[name] = vt[0]
    else:
        _check_store(ctx, s.target, vt[0] if vt else ANY, env, owner, s.line, s.op)


def _check_return_stmt(ctx: Context, s: ReturnStmt, env: Dict[str, Type], owner: Optional[str],
                       rets: Optional[List[Type]], fn_decl: Optional[FnDecl]):
    vts = _value_types(ctx, s.values, env, owner)   # a trailing call expands its results
    for t in vts:
        if rets is not None and t != NIL:
            rets.append(t)
    if fn_decl is None or s.kind != "return" or not s.values:
        return
    expected = fn_decl.ret_types
    explicit, expanded = len(s.values), len(vts)
    if explicit == expanded:            # plain values: the count is written by the author
        bad = expanded != len(expected)
    else:                               # a trailing call expands: Lua may truncate it
        bad = expanded < len(expected)
    if bad:
        raise Error(f"fn {fn_decl.name}: returns {expanded} value(s), "
                    f"{len(expected)} declared", s.line)
    for i, v in enumerate(s.values[:len(expected)]):
        expect(ctx, f"return value {i + 1} of {fn_decl.name}", vts[i], expected[i], s.line)


def _check_stmts(ctx: Context, stmts: List[Stmt], env: Dict[str, Type],
                 owner: Optional[str] = None, rets: Optional[List[Type]] = None,
                 arg_names: Optional[Dict[int, str]] = None,
                 fn_decl: Optional[FnDecl] = None, in_loop: bool = False):
    for s in stmts:
        if isinstance(s, SayStmt):
            expect(ctx, "text to print", _check_expr(ctx, s.expr, env, owner, STR), STR, s.line)
        elif isinstance(s, ReturnStmt):
            if s.kind == "break" and not in_loop:
                raise Error("break: not inside a loop", s.line)
            _check_return_stmt(ctx, s, env, owner, rets, fn_decl)
        elif isinstance(s, LocalStmt):
            _no_duplicates((vn for vn, _t in s.names), "local", s.line)
            vts = _value_types(ctx, s.values, env, owner)
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
                    expect(ctx, f"for bound {what}", _check_expr(ctx, bound, env, owner, NUM), NUM, bound.line)
            benv = dict(env)
            benv[s.var] = s.var_type or NUM
            if s.var_type:
                expect(ctx, f"for variable {s.var}", NUM, s.var_type, s.line)
            _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl, in_loop=True)
        elif isinstance(s, ForInStmt):
            it = _check_expr(ctx, s.iter_expr, env, owner)
            base = _index_result(ctx, it)
            if s.is_of and base is None and not _is_object_type(ctx, it):
                raise TypeCheckError(f"for … of: expected tbl, got {it}", s.line)
            el = base if base is not None else (
                Name(_root(ctx)) if _is_object_type(ctx, it) else ANY)
            benv = dict(env)
            for i, (vn, vt) in enumerate(s.vars):
                elem = NUM if (s.is_of and len(s.vars) == 2 and i == 0) else el
                if vt is not None and elem != ANY:
                    expect(ctx, f"for variable {vn}", elem, vt, s.line)
                benv[vn] = vt or elem
            _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl, in_loop=True)


def _sig_ok(ctx: Context, fn: FnDecl, expected: Type) -> bool:
    """Can `fn` be passed where a callback of type `expected` is wanted?"""
    one = types.fn_of(expected)
    if one is None:
        return False
    aparams = [pt for _pn, pt in fn.params]
    if len(aparams) > len(one.params):
        return False
    for i, at in enumerate(aparams):
        et = one.params[i]
        if at == ANY or et == ANY:
            continue
        if not is_subtype(ctx, et, at):
            return False
    ar = fn.ret_types or [ANY]
    if not one.rets or ar == [ANY]:
        return True
    return any(is_subtype(ctx, a, r) for a in ar for r in one.rets)


def _sig_text(types: List[Type]) -> str:
    """`obj, str?` — a signature for a diagnostic."""
    return ", ".join(str(t) for t in types) if types else "no arguments"


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


def _check_fnref(ctx: Context, ref: FnRef, expected: Optional[Type], where: str):
    """Check a `&name` reference against the callback signature expected there."""
    fn = ctx.fns.get(ref.name)
    if fn is None or expected is None:
        return
    alts = [a for a in parts(expected) if isinstance(a, Fn)]
    if not alts:
        return
    if any(_sig_ok(ctx, fn, a) for a in alts):
        return
    got = Fn(tuple(pt for _pn, pt in fn.params), tuple(fn.ret_types))
    raise TypeCheckError(f"{where}: {ref.name} is {got}, expected "
                         f"{' | '.join(str(a) for a in alts)}", ref.line)


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


def _index_result(ctx: Context, t: Type) -> Optional[Type]:
    """The element type of an indexable value: `tbl[T]`, a list, or a union with one.

    `scope: ref | tbl[ref] | fn(…)` is a *write* type: the engine normalizes a
    single reference into a list at load (`mplib.lua: std.obj.__ini`), so reading
    the field and indexing it is safe even though one alternative is not a table.
    """
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
    """An engine list (`class list = std.list`): a table of objects, indexed by number."""
    one = types.single(t)
    return isinstance(one, Name) and any(ctx.ctors.get(cur) == "std.list"
                                         for cur in _walk_class_chain(ctx, one.name))


def _is_object_type(ctx: Context, t: Type) -> bool:
    """A declared class (or an instance of one) — the only things with fields."""
    one = types.single(t)
    return isinstance(one, Name) and (one.name in ctx.classes or one.name in ctx.objects)


def _objectish(ctx: Context, t: Type) -> bool:
    """Can a value of this type have fields (`x.field`)? Scalars cannot."""
    for alt in parts(t):
        if alt == ANY or isinstance(alt, (Ref, Tbl)) or _is_object_type(ctx, alt):
            return True          # dynamic values, references and collections
    return False


def _fields_of(ctx: Context, holder: str) -> Dict[str, Tuple[Type, bool]]:
    """Fields known for a holder: its own and inherited, plus (for a class) its
    instances and descendants. Conflicting declarations of one name collapse to
    `any` — that is the dynamic ("duck typing") case."""
    allowed = dict(ctx.fields.get(holder, {}))
    if holder not in ctx.classes:
        return allowed
    # the class also sees its instances/descendants: two declarations of one name
    # with different types mean "dynamic" (`any`), which is the duck-typing case
    for name, kind in list(ctx.objects.items()) + list(ctx.classes.items()):
        if not _inherits(ctx, kind if kind else name, holder):
            continue
        for k, v in ctx.fields.get(name, {}).items():
            if k not in allowed:
                allowed[k] = v
            elif allowed[k][0] != v[0]:
                if _is_empty_collection(allowed[k][0]):
                    allowed[k] = v              # `items = []` carries no element type
                elif not _is_empty_collection(v[0]):
                    allowed[k] = (ANY, False)   # two real types: dynamic (duck typing)
    return allowed


def _owner_of(ctx: Context, target: FieldAccess, env: Dict[str, Type], owner: Optional[str]) -> Optional[str]:
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
        t = str(without_nil(env[base.name]))
        return t if (t in ctx.classes or t in ctx.objects) else None
    return None


def _check_store(ctx: Context, target: Expr, vt: str, env: Dict[str, Type],
                 owner: Optional[str], line: int = 0, op: str = "="):
    """Validate a write: field type stability and declared field names."""
    if isinstance(target, IndexAccess):
        ot = _check_expr(ctx, target.obj, env, owner)
        need_value(ot, _kind_name(target.obj), line)
        inner = _index_result(ctx, ot)
        if inner is None:
            raise TypeCheckError(f"{_kind_name(target.obj)}: {ot} is not indexable "
                                 f"(only a `tbl`, a list or `any`)", line)
        _check_expr(ctx, target.index, env, owner, None)
        if inner is not None:
            expect(ctx, _kind_name(target), vt, inner, line)
        return
    if not isinstance(target, FieldAccess):
        _check_expr(ctx, target, env, owner, is_lhs=True)
        return
    need_value(_check_expr(ctx, target.obj, env, owner), _kind_name(target.obj), line)
    name = target.field
    if name in READONLY_FIELDS:
        raise Error(f"{name}: an engine field cannot be assigned", line)
    if name.startswith("__"):
        return
    holder = _owner_of(ctx, target, env, owner)
    spec = _fields_of(ctx, holder).get(name) if holder else None
    decl = _decl_of_holder(ctx, holder, name) if holder else None
    if decl is not None and decl.emit is not None:
        raise Error(f"{holder}.{name}: an emitted field is set by its declaration "
                    f"(`= method {decl.emit.method}(…)`), not by code", line)
    if spec is not None:
        ft, is_ref = spec
        if op in ("+=", "-="):                                # `+=`/`-=` are arithmetic
            if ft not in (ANY, NUM):
                raise Error(f"{name}: '{op}' needs a number field (it is {ft})", line)
            return
        if ft != ANY:
            expect(ctx, f"{name}", _root(ctx) if (is_ref and vt == "obj") else vt, ft, line)
        return
    if holder is not None and not name.startswith("__"):
        raise Error(f"{holder}.{name}: no such field "
                    f"(nothing declares it for {holder}; use __{name} for a dynamic value)", line)
    if name not in ctx.field_names:
        raise Error(f"unknown field {name!r} (use __{name} for dynamic values)", line)


def _check_expr(ctx: Context, e: Expr, env: Dict[str, Type], owner: Optional[str] = None,
                expected: Optional[str] = None, is_lhs: bool = False) -> str:
    t = _infer(ctx, e, env, owner, expected, is_lhs)
    if expected and not is_lhs:
        expect(ctx, _kind_name(e), t, expected, e.line)
    return t


def _infer_lambda(ctx: Context, e: Lambda, env: Dict[str, Type],
                  owner: Optional[str], expected: Optional[str]) -> str:
    one = types.fn_of(expected) if expected is not None else None
    eparams: Tuple[Type, ...] = one.params if one else ()
    erets: Tuple[Type, ...] = one.rets if one else ()
    if eparams and len(e.params) > len(eparams):
        raise TypeCheckError(f"&(…): the callback passes {len(eparams)} argument(s), "
                             f"the lambda takes {len(e.params)}", e.line)
    env2 = dict(env)
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
        for t in rets:                      # a lambda body may return anything
            if erets and not any(is_subtype(ctx, t, w) for w in erets):
                raise TypeCheckError(f"&(…): returns {t}, the callback declares "
                                     f"{union(*erets)}", e.line)
        if erets and not types.is_optional(union(*erets)) and not _returns_all(e.body):
            raise TypeCheckError(
                f"&(…): the callback returns {union(*erets)}, but some path leaves the body "
                f"without `return` (write an expression body or add `return`)", e.line)
    else:
        _check_expr(ctx, e.body, env2, owner, erets[0] if erets else None)
    e.typ = Fn(tuple(ptypes), tuple(erets))
    return e.typ


def _infer(ctx: Context, e: Expr, env: Dict[str, Type], owner: Optional[str] = None,
           expected: Optional[str] = None, is_lhs: bool = False) -> str:
    if isinstance(e, Lit):
        if e.kind == "table":
            e.typ = TBL
            return TBL
        if e.kind == "num" and expected is not None:
            for alt in parts(expected):
                if isinstance(alt, Name) and alt.name in ctx.enums \
                        and str(e.val) in ctx.enums[alt.name][0]:
                    e.typ = alt
                    return alt
        e.typ = _KINDS.get(e.kind, ANY)
        return e.typ
    if isinstance(e, InterpStr):
        for p in e.parts:
            if isinstance(p, Expr):
                t = _check_expr(ctx, p, env, owner)
                if not is_subtype(ctx, t, _PRINTABLE) and t != ANY:
                    raise TypeCheckError(f"interpolation: expected str, got {t}", p.line)
        e.typ = STR
        return STR
    if isinstance(e, Lambda):
        return _infer_lambda(ctx, e, env, owner, expected)
    if isinstance(e, Bind):
        vt = _value_types(ctx, [e.value], env, owner)
        e.vtyp = vt[0] if vt else ANY
        for n in e.names:
            if n in env:
                raise Error(f"{n}: already defined (choose another name for `:=`)", e.line)
        e.typ = BOOL
        return BOOL
    if isinstance(e, InOp):
        st = _check_expr(ctx, e.subject, env, owner)
        for a in e.alts:
            _check_expr(ctx, a, env, owner, st)
        e.typ = BOOL
        return BOOL
    if isinstance(e, FnRef):
        _check_fn_target(ctx, e)
        ctx.used_refs.add(e.name)
        _check_fnref(ctx, e, expected, _kind_name(e))
        decl = ctx.fns.get(e.name)
        e.typ = Fn(tuple(t for _n, t in decl.params), tuple(decl.ret_types)) \
            if decl is not None else Name("fn")
        return e.typ
    if isinstance(e, ListLit):
        in_exp = next((types.tbl_inner(alt) for alt in (parts(expected) if expected else [])
                       if types.tbl_inner(alt) is not None), None)
        its = [_check_expr(ctx, it, env, owner, in_exp) for it in e.items]
        e.typ = Tbl(union(*its) if its else Name(""))
        return e.typ
    if isinstance(e, Sym):
        return _infer_sym(ctx, e, env, expected, is_lhs)
    if isinstance(e, FieldAccess):
        return _infer_field(ctx, e, env, owner, is_lhs)
    if isinstance(e, IndexAccess):
        ot = _check_expr(ctx, e.obj, env, owner)
        base = _index_result(ctx, ot)
        if base is None:
            raise TypeCheckError(f"{_kind_name(e.obj)}: {ot} is not indexable "
                                 f"(only a `tbl`, a list or `any`)", e.line)
        _check_expr(ctx, e.index, env, owner, None)
        e.typ = base if base in (ANY, NIL) or types.is_optional(base) else opt(base)
        return e.typ
    if isinstance(e, UnaryOp):
        if e.op == "-" and isinstance(e.operand, Lit) and e.operand.kind == "str":
            e.typ = STR
            return STR
        _check_expr(ctx, e.operand, env, owner, None if e.op == "not" else NUM)
        e.typ = BOOL if e.op == "not" else NUM
        return e.typ
    if isinstance(e, BinOp):
        return _infer_binop(ctx, e, env, owner)
    if isinstance(e, Call):
        return _check_call(ctx, e, env, owner)
    return ANY


def _infer_sym(ctx: Context, e: Sym, env: Dict[str, Type],
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
            e.rk, e.typ = "var", ANY
            return ANY
        raise Error(f"unknown name {n!r} (declare it with `local` or `global`)", e.line)
    if n in env:
        e.rk, e.typ = "var", env[n]
        return e.typ
    if expected:
        exps = parts(expected)
        if any(isinstance(x, Name) and x.name == "event" for x in exps) \
                and n in ctx.event_names:
            e.rk, e.typ = "event", EVENT
            return EVENT
        if n in ctx.enum_owner:
            for ea in exps:
                if _enum_value(ctx, n, str(ea)):
                    e.rk, e.typ = "enum", Name(str(ea))
                    return e.typ
    if n in ctx.objects:
        e.rk, e.typ = "obj", Name(ctx.objects[n])
        return e.typ
    if n in ctx.globals:
        gt, is_r = ctx.globals[n]
        e.rk, e.typ = ("global_ref" if is_r else "global"), gt
        return gt
    if n in ctx.classes:
        e.rk, e.typ = "enum", STR
        return STR
    if n in ctx.event_names:
        e.rk, e.typ = "event", EVENT
        return EVENT
    enum = ctx.enum_owner.get(n.lstrip("~"))
    if enum:
        e.rk, e.typ = "enum", Name(enum)
        return e.typ
    if n in ctx.fns or n in ctx.lua_funcs:
        sig = ctx.fns.get(n)
        required = sum(1 for _pn, pt in (sig.params if sig is not None else [])
                       if not types.is_optional(pt))
        if required:
            raise Error(f"{n}: needs {required} argument(s) — call it or take `&{n}`", e.line)
        e.rk = "value" if (sig and sig.is_value) else "fn0"
        e.typ = sig.ret_types[0] if (sig and sig.ret_types) else ANY
        return e.typ
    if n in ctx.lua_globals:
        e.rk, e.typ = "lua_global", ctx.lua_globals[n].typ
        return e.typ
    if n.startswith("#"):
        raise Error(f"unknown tag {n!r}", e.line)
    raise Error(f"unknown name {n!r}{_enum_hint(ctx, n)}", e.line)


def _infer_field(ctx: Context, e: FieldAccess, env: Dict[str, Type],
                 owner: Optional[str], is_lhs: bool) -> str:
    base_t = _check_expr(ctx, e.obj, env, owner)
    if is_lhs:
        e.typ = base_t
        return base_t
    need_value(base_t, _kind_name(e.obj), e.line)
    if not _objectish(ctx, base_t):
        raise TypeCheckError(f"{_kind_name(e.obj)}: {base_t} has no fields "
                             f"(`.{e.field}`)", e.line)
    holder = _owner_of(ctx, e, env, owner)
    decl = _decl_of_holder(ctx, holder, e.field) if holder else None
    if decl is not None and decl.emit is not None:
        # `attr: … = method attr(join)` is not a field at all: the engine turns the
        # declaration into `:attr(…)`, so a read returns the method, not the value
        raise TypeCheckError(
            f"{_kind_name(e)}: {e.field!r} is write-only "
            f"(declared as `= method {decl.emit.method}(…)`); read it through the method",
            e.line)
    if holder and e.field in ctx.fields.get(holder, {}):
        ft, is_r = ctx.fields[holder][e.field]
        e.is_ref, e.typ = is_r, ft
        return ft
    if holder is not None and not e.field.startswith("__"):
        spec = _fields_of(ctx, holder).get(e.field)
        if spec is None:
            raise Error(f"{holder}.{e.field}: no such field "
                        f"(nothing declares it for {holder}; use __{e.field} for a dynamic value)",
                        e.line)
        e.is_ref, e.typ = spec[1], spec[0]
        return spec[0]
    if e.field in ctx.field_names:
        e.typ = ANY
        return ANY
    if e.field.startswith("__"):
        e.typ = ANY
        return ANY
    raise Error(f"unknown field {e.field!r} (use __{e.field} for dynamic values)", e.line)


def _both_sides(ctx: Context, e: BinOp, env: Dict[str, Type], owner: Optional[str],
                want: Type, label: str):
    """Check both operands of a binary operation against one type."""
    for side in (e.left, e.right):
        expect(ctx, label, _check_expr(ctx, side, env, owner, want), want, side.line)


def _infer_binop(ctx: Context, e: BinOp, env: Dict[str, Type], owner: Optional[str]) -> Type:
    lt = _check_expr(ctx, e.left, env, owner)
    if e.op in ("==", "!="):
        _infer(ctx, e.right, env, owner, lt)  # resolves bare names, comparing is not a type error
        e.typ = BOOL
        return BOOL
    if e.op in ("<", "<=", ">", ">="):
        _both_sides(ctx, e, env, owner, NUM, "comparison")
        e.typ = BOOL
        return BOOL
    if e.op == "..":
        for side in (e.left, e.right):
            t = _check_expr(ctx, side, env, owner)
            if not is_subtype(ctx, t, _CONCAT) and t != ANY:
                raise TypeCheckError(f"concatenation: expected str, got {t}", side.line)
        e.typ = STR
        return STR
    if e.op in ("+", "-", "*", "/", "%", "//"):
        _both_sides(ctx, e, env, owner, NUM, "arithmetic")
        e.typ = NUM
        return NUM
    rt = _check_expr(ctx, e.right, env, owner)
    if e.op == "and":
        e.typ = union(lt, rt)          # `a and b` is `a` itself when `a` is falsy
    elif e.op == "or":
        e.typ = union(without_nil(lt), rt)
    else:
        e.typ = rt
    return e.typ


def _check_value_use(ctx: Context, name: str, line: int):
    """`extern value` is an expression: using it as a statement is a mistake."""
    fn = ctx.fns.get(name)
    if fn is not None and fn.is_value:
        raise Error(f"{name}: an expression, not a statement (use its value)", line)


def _check_call(ctx: Context, c: Call, env: Dict[str, Type], owner: Optional[str] = None) -> str:
    """Type a call: `f a b`, `f(a, b)`, `obj:m a` and a call of a fn value."""
    is_method = c.receiver is not None
    all_args = ([c.receiver] + c.args) if is_method else list(c.args)
    label = f"{_kind_name(c.receiver)}:{c.func}" if is_method else c.func
    # a local or a parameter of function type shadows a global `fn` of that name
    shadowed = not is_method and isinstance(env.get(c.func), (Fn, type(None))) is False \
        and types.fn_of(env.get(c.func)) is not None
    fn = None if shadowed else ctx.fns.get(c.func)

    if is_method:
        need_value(_check_expr(ctx, c.receiver, env, owner), _kind_name(c.receiver), c.line)

    if fn is None:
        return _check_indirect_call(ctx, c, env, owner, is_method, all_args)

    params = fn.params
    required = sum(1 for _pn, pt in params if not types.is_optional(pt))
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
        if is_method and i == 0:           # `x:m …` passes `x` as the first argument
            if exp:
                expect(ctx, f"receiver of {label}", _check_expr(ctx, a, env, owner), exp, a.line)
            continue
        got = _check_expr(ctx, a, env, owner, exp)
        if exp:
            expect(ctx, f"argument {i + 1} of {label}", got, exp, a.line)

    c.typ = fn.ret_types[0] if fn.ret_types else ANY
    return c.typ


def _check_indirect_call(ctx: Context, c: Call, env: Dict[str, Type], owner: Optional[str],
                         is_method: bool, all_args: List[Expr]) -> str:
    """`x:m …` / `f …` where `f` is not a declared function.

    A method call is mise's "call this function with the receiver first" —
    `l:add(w)` is `add(l, w)` — so it needs a real function or extern. An
    engine object (`mp`, `std`, `game`, …) is typed `any`, and its surface is
    Lua, not mise: those calls stay unchecked.
    """
    ftype = env.get(c.func)
    body = types.without_nil(ftype) if ftype is not None else None
    one = body if isinstance(body, Fn) else None    # a union may hold a string
    known = c.func in ctx.lua_funcs or (not is_method and one is not None)
    if is_method and c.receiver.typ == ANY:
        known = True
    if not known:
        if is_method:
            raise Error(f"unknown method {c.func!r} "
                        f"(a method call needs a function or an extern)", c.line)
        if not is_method and ftype is not None:
            raise TypeCheckError(f"{c.func}: is {ftype}, not a function", c.line)
        raise Error(f"unknown function {c.func!r}", c.line)
    args = all_args[1:] if is_method else all_args
    if one is not None:
        required = sum(1 for t in one.params if not types.is_optional(t))
        if len(args) < required:
            raise TypeCheckError(f"{c.func}: expects {required} argument(s), "
                                 f"got {len(args)}", c.line)
    for i, a in enumerate(args):
        want = one.params[i] if (one is not None and i < len(one.params)) else None
        got = _check_expr(ctx, a, env, owner, want)
        if want is not None:
            expect(ctx, f"argument {i + 1} of {c.func}", got, want, a.line)
    c.typ = one.rets[0] if one is not None and one.rets else ANY
    return c.typ


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
    """A declared type must name known classes and primitives (`ref[C]`: C is a class)."""
    for alt in parts(typ):
        if _type_alt_ok(ctx, alt):
            continue
        raise Error(f"{where}: unknown {label} {str(alt)!r}", line)


def _check_signature(ctx: Context, fn: FnDecl):
    """Unknown types, duplicate names, or a required parameter after an optional one."""
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


def _is_empty_collection(t: Type) -> bool:
    """`[]` — a table literal with no element type of its own."""
    inner = types.tbl_inner(t)
    return isinstance(inner, Name) and inner.name == ""


def _value_types(ctx: Context, values: List[Expr], env: Dict[str, Type],
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
    import difflib
    for ev in h.events:
        if ev in ctx.event_names:
            continue
        near = difflib.get_close_matches(ev, sorted(ctx.event_names), 1, 0.7)
        hint = f" (did you mean {near[0]!r}?)" if near else ""
        raise Error(f"{where}: unknown event {ev!r}{hint}", h.line)
