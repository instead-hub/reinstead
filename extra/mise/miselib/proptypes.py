"""Types, `props:` and reference fields: registration and value checks."""
from . import state as S
from .common import *
from .cursor import at
from .constructs import prop_scopes, top_items
from .typing import (Prop, canon_type, fn_type_parts, literal_type,
                     type_error, type_ok)
from . import messages as M
from . import patterns as P


def _type_atoms(val):
    """Bare value strings of a type: inline scalars or `-` list items."""
    if not isinstance(val, list):
        yield val
        return
    for x in val:
        if isinstance(x, Text):
            for part in x.s.split(","):
                part = part.strip()
                if part:
                    yield Bare(part)
        else:
            yield x


def _is_negation(name, atoms):
    """True if the type starts with the `~` negation marker."""
    if not atoms:
        return False
    first = atoms[0]
    if isinstance(first, Text):
        raise Error(M.TYPE_QUOTES_ARE_NOT_ALLOWED % name)
    if not isinstance(first, (Bare, Num)):
        raise Error(M.TYPE_EXPECTED_BARE_VALUES % name)
    return first.s == "~"


def _type_value(name, x):
    """Validate one type atom and return its string."""
    if isinstance(x, Text):
        raise Error(M.TYPE_QUOTES_ARE_NOT_ALLOWED % name)
    if not isinstance(x, (Bare, Num)):
        raise Error(M.TYPE_EXPECTED_BARE_VALUES % name)
    if not P.NONSPACE_RE.fullmatch(x.s) or ":" in x.s:
        raise Error(M.TYPE_BAD_VALUE % (name, x.s))
    return x.s


def _event_arg_types(ctx, name, val):
    """Argument types of one `type event:` group (empty value = none)."""
    if isinstance(val, Block):
        return ()
    known = S.TYPES | set(ctx.types) | ctx.classes | {"nil"}
    text = ",".join(v.s for v in _type_atoms(val))
    sig = canon_type(known, "fn(%s)" % text)
    if sig is None:
        raise Error(M.TYPE_ARGS_MESSAGE % (name, text,
                                           type_error(known, text)))
    return tuple(fn_type_parts(sig)[0])


def _event_groups(ctx, name, block, td):
    """`type event:` block -> values, event args and `life` args.

    A `life Names: types` group gives the life-phase arguments; its
    names must be declared before it (earlier in the block or in the
    base type).
    """
    if not block.items:
        raise Error(M.TYPE_NO_VALUES % name)
    if name != "event":
        raise Error(M.TYPE_ARGS_ONLY_EVENT % name)
    for i, (group, types) in enumerate(block.items):
        at(block, i)
        life = group.startswith("life ")
        group = group.removeprefix("life ")
        args = _event_arg_types(ctx, name, types)
        target = (td["args"], td["life_args"])[life]
        for ev in group.split(","):
            ev = ev.strip()
            if ev in target:
                raise Error(M.TYPE_ARGS_DUPLICATE % (name, ev))
            if life and ev not in td["values"]:
                raise Error(M.TYPE_ARGS_UNKNOWN % (name, ev))
            td["values"].append(ev)
            target[ev] = args
    td["values"] = list(dict.fromkeys(td["values"]))


def _new_type(ctx, name, val):
    if name in ctx.types:
        raise Error(M.DUPLICATE_TYPE + name)
    td = {"values": [], "negate": False, "args": {}, "life_args": {}}
    if isinstance(val, Block):
        _event_groups(ctx, name, val, td)
    elif name == "event":
        raise Error(M.TYPE_EVENT_BLOCK)
    else:
        atoms = list(_type_atoms(val))
        negate = _is_negation(name, atoms)
        rest = atoms[1:] if negate else atoms
        td["values"] = [_type_value(name, x) for x in rest]
        td["negate"] = negate
    if not td["values"]:
        raise Error(M.TYPE_NO_VALUES % name)
    ctx.types[name] = td


def _extend_type(ctx, name, val):
    if name not in ctx.types:
        raise Error(M.EXTEND_TYPE_UNKNOWN_TYPE % name)
    td = ctx.types[name]
    if isinstance(val, Block):
        _event_groups(ctx, name, val, td)
        return
    if name == "event":
        raise Error(M.TYPE_EVENT_BLOCK)
    for x in _type_atoms(val):
        if (isinstance(x, Text) or not isinstance(x, (Bare, Num))
                or x.s == "~"):
            raise Error(M.EXTEND_TYPE_EXPECTED_BARE_VALUES % name)
        if not P.NONSPACE_RE.fullmatch(x.s) or ":" in x.s:
            raise Error(M.EXTEND_TYPE_BAD_VALUE % (name, x.s))
        if x.s not in td["values"]:
            td["values"].append(x.s)


# the enumeration declarations and their registrars
TYPE_FORMS = {
    "type": _new_type,
    "extend_type": _extend_type,
}


def collect_types(root, ctx):
    ctx.types = {}
    for i, kind, name, _key, val in top_items(root, ("type", "extend_type")):
        at(root, i)
        TYPE_FORMS[kind](ctx, name, val)
    ctx.enum_values = {}
    for _tname, td in ctx.types.items():
        for _v in td["values"]:
            ctx.enum_values.setdefault(_v, set()).add(_tname)
    return ctx.types


# scopes of `props <scope>:` -> direct engine parent (see constructs.py)
PROP_SCOPES = prop_scopes()


def _scope_parent(ctx, kind):
    """The next scope up: an engine or class parent, else None."""
    if kind in PROP_SCOPES:
        parents = PROP_SCOPES[kind]
        return parents[0] if parents else None
    if kind in ctx.class_parents:
        return ctx.class_parents[kind] or "obj"
    return None


def scope_chain(ctx, scope):
    """A scope and its engine/class parents, most specific first."""
    chain = []
    kind = scope
    while kind and kind not in chain:
        chain.append(kind)
        kind = _scope_parent(ctx, kind)
    return chain


def prop_scope(ctx, owner):
    """The props scope of an owner name (declaration id or kind)."""
    if not owner:
        return None
    kind = ctx.id_kind.get(owner, owner)
    if kind in PROP_SCOPES or kind in ctx.class_parents:
        return kind
    return None


def prop_of(ctx, scope, name):
    """Prop of a scope (then its parents), else the global one."""
    if scope is None:
        return ctx.props.get(name)
    for kind in scope_chain(ctx, scope):
        prop = ctx.scoped.get(kind, {}).get(name)
        if prop is not None:
            return prop
    return ctx.props.get(name)


def _register_prop(ctx, known, name, tval, into):
    """Validate and register one `props:` entry."""
    if not P.DSL_RE.fullmatch(name):
        raise Error(M.BAD_PROP_NAME % name)
    if name in into:
        raise Error(M.DUPLICATE_PROP + name)
    if not isinstance(tval, (Bare, Text)):
        raise Error(M.PROPS_NEEDS_TYPE % name)
    prop = Prop(tval.s, known)
    into[name] = prop
    if prop.names:
        ctx.prop_params[name] = prop.names
    if prop.has_ref or prop.has_reflist:
        ctx.ref_fields.add(name)


def _scope_map(ctx, scope):
    if scope not in PROP_SCOPES and scope not in ctx.classes:
        raise Error(M.PROPS_SCOPE_UNSUPPORTED % scope)
    return ctx.scoped.setdefault(scope, {})


def register_props(root, ctx):
    """`props:`/`props <scope>:` -> typed engine properties."""
    ctx.props = {}
    ctx.scoped = {}
    ctx.prop_params = {}
    known = S.TYPES | set(ctx.types) | ctx.classes | {"ref", "nil"}
    for i, _kind, info, _key, val in top_items(root, ("props",)):
        at(root, i)
        if not isinstance(val, Block):
            raise Error(M.PROPS_MUST_BE_BLOCK)
        scopes = [None] if info is None else info
        into = [ctx.props if s is None else _scope_map(ctx, s)
                for s in scopes]
        for j, (name, tval) in enumerate(val.items):
            at(val, j)
            for target in into:
                _register_prop(ctx, known, name, tval, target)


def _check_ref_name(ctx, where, name):
    """Object reference name must be a declared id."""
    if name not in ctx.ids:
        raise Error(M.UNKNOWN_OBJECT_REFERENCE % (where, name))


def check_ref_list(ctx, where, val):
    """`tbl[ref]` list items: bare names or `-`-list strings."""
    for it in val:
        if isinstance(it, Text):
            _check_ref_name(ctx, where, it.s.strip())
        elif isinstance(it, Bare):
            if not P.REF_RE.fullmatch(it.s):
                raise Error(M.OBJECT_NAME_IDENTIFIER % (where, it.s))
            _check_ref_name(ctx, where, it.s)
        else:
            raise Error(M.EXPECTED_OBJECT_REFERENCE
                        % (where, type(it).__name__.lower()))


def _prop_table(ctx, owner, base, prop, val):
    """A `{ ... }` literal: raw Lua for tbl, name strings for list/tbl[ref]."""
    where = ("%s.%s" % (owner, base)) if owner else base
    if prop.has_list or prop.has_reflist:
        val.s = _ref_table(ctx, where, val.s)
        return ("list" if prop.has_list else "tbl"), False
    if prop.has_tbl:
        return "tbl", False
    raise Error(M.EXPECTED_GOT % (where, prop.text, "table"))


def _ref_table(ctx, where, text):
    """Canonical `{ "name", ... }` of a list/tbl[ref] table literal."""
    s = text.strip()
    inner = s[1:-1] if s.startswith("{") and s.endswith("}") else s
    items = [parse_scalar(p, CURRENT_LINE[0] or 0) for p in split_list(inner)]
    check_ref_list(ctx, where, items)
    names = ", ".join(lua_str(it.s.strip()) for it in items)
    return "{ %s }" % names if names else "{}"


def _prop_bare(prop, where, t):
    if prop.has_event and t == "event":
        return "event", False
    if prop.has_ref and t == "obj":
        return "obj", True
    raise Error(M.EXPECTED_GOT % (where, prop.text, t))


def _prop_text(prop, val, where):
    if prop.has_str:
        return "str", False
    if prop.has_ref:
        raise Error(M.OBJECT_REFERENCE % (where, val.s))
    raise Error(M.EXPECTED_GOT_STR % (where, prop.text))


def _prop_list(ctx, prop, val, where):
    if prop.has_reflist or prop.has_list:
        check_ref_list(ctx, where, val)
        return ("list" if prop.has_list else "tbl"), False
    if prop.has_tbl:
        if prop.tbl_elem:
            for it in val:
                t = literal_type(ctx, it)
                if not type_ok(ctx, t, prop.tbl_elem):
                    raise Error(M.EXPECTED_GOT_IN_LIST
                                % (where, prop.tbl_elem, t))
        return "tbl", False
    raise Error(M.EXPECTED_GOT_LIST % (where, prop.text))


# prop values with a constant result and the scalar ones: type -> spec
PROP_CONSTS = {Raw: ("any", False), Nil: ("nil", False)}
PROP_SCALARS = {Num: ("num", "has_num"), Bool: ("bool", "has_bool")}


def _prop_scalar(prop, kind, flag, where):
    if getattr(prop, flag):
        return kind, False
    raise Error(M.EXPECTED_GOT % (where, prop.text, kind))


def check_prop_value(ctx, owner, base, prop, val, t):
    """Validate a prop field value; returns (type, is_ref)."""
    where = ("%s.%s" % (owner, base)) if owner else base
    const = PROP_CONSTS.get(type(val))
    if const is not None:
        return const
    if isinstance(val, Data):
        return _prop_table(ctx, owner, base, prop, val)
    if isinstance(val, (Logic, Lua, FnRef)):
        if prop.fn is None:
            raise Error(M.EXPECTED_GOT_FUNCTION % (where, prop.text))
        return prop.fn_type, False
    if isinstance(val, Bare):
        return _prop_bare(prop, where, t)
    if isinstance(val, Text):
        return _prop_text(prop, val, where)
    if isinstance(val, list):
        return _prop_list(ctx, prop, val, where)
    scalar = PROP_SCALARS.get(type(val))
    if scalar is not None:
        return _prop_scalar(prop, scalar[0], scalar[1], where)
    if prop.has_tbl:
        return "tbl", False
    raise Error(M.EXPECTED_GOT
                % (where, prop.text, type(val).__name__.lower()))


def register_refs(root, ctx):
    ctx.ref_fields = set()
    for i, _kind, _info, _key, val in top_items(root, ("refs", "extend_refs")):
        at(root, i)
        if isinstance(val, Block):
            raise Error(M.REFS_EXPECTED_LIST_NAMES)
        for x in _type_atoms(val):
            if isinstance(x, Text) or not isinstance(x, Bare) or x.s == "~":
                raise Error(M.REFS_EXPECTED_BARE_NAMES)
            if not P.NONSPACE_RE.fullmatch(x.s):
                raise Error(M.REFS_BAD_NAME % x.s)
            ctx.ref_fields.add(x.s)


def _tail_maps(args):
    """(plain, shifted) maps: event -> {param: type} for narrowing."""
    plain = {}
    shifted = {}
    for ev, a in args.items():
        plain[ev] = dict(zip(("w", "wh"), a))
        shifted[ev] = dict(zip(("w", "wh"), a[1:]))
    return plain, shifted


def _verb_sig(text):
    """(event, args) of one engine pattern, else (None, None)."""
    pat, sep, ev = text.rpartition(":")
    if not sep:
        return None, None
    ev = ev.strip()
    if ev.endswith(" reverse"):
        ev = ev[:-8].strip()
    if not P.DSL_RE.fullmatch(ev):
        return None, None
    toks = [t.lstrip("~+?") for t in pat.split()]
    nouns = sum(1 for t in toks
                if t.startswith(("{noun}", "{noun_obj}", "{compass")))
    return ev, ["obj"] * nouns + (["str"] if "*" in toks else [])


def _add_verb_sig(sigs, ev, args):
    """Fold one pattern signature: the longest types, the minimal length."""
    cur = sigs.get(ev)
    if cur is None:
        sigs[ev] = [args, len(args)]
        return
    types, mn = cur
    long = args if len(args) > len(types) else types
    if any(t != long[i] for i, t in enumerate(args[:len(long)])):
        del sigs[ev]
        return
    sigs[ev] = [long, min(mn, len(args))]


def _add_verb_patterns(sigs, pats):
    """Fold the `patterns` value of one `verb`/`extend` into `sigs`."""
    for p in (pats if isinstance(pats, list) else [pats]):
        if isinstance(p, (Text, Bare)):
            ev, args = _verb_sig(p.s)
            if ev is not None:
                _add_verb_sig(sigs, ev, args)


def register_verbs(root):
    """Event signatures derived from `verb`/`extend` patterns."""
    sigs = {}
    for _i, _kind, _info, _key, val in top_items(root, ("verb", "extend")):
        pats = val.get("patterns") if isinstance(val, Block) else None
        if pats is not None:
            _add_verb_patterns(sigs, pats)
    return {ev: tuple(t + "?" if i >= mn else t
                      for i, t in enumerate(types))
            for ev, (types, mn) in sigs.items()}


def _union_type(a, b):
    """Union of two positional types; None means the argument is absent."""
    opt = a is None or b is None or "?" in (a or "") or "?" in (b or "")
    alts = sorted({(a or "").rstrip("?"), (b or "").rstrip("?")} - {""})
    return "|".join(alts) + ("?" if opt else "")


def _merge_args(derived, table):
    """Widen `type event:` signatures with the verb-derived ones."""
    out = dict(table)
    for ev, args in derived.items():
        if ev not in table:
            out[ev] = args
            continue
        old = table[ev]
        out[ev] = tuple(_union_type(args[i] if i < len(args) else None,
                                    old[i] if i < len(old) else None)
                        for i in range(max(len(args), len(old))))
    return out


def register_events(root, ctx):
    """Event names and the `type event:` handler signatures."""
    td = ctx.types.get("event", {})
    derived = register_verbs(root)
    names = set(td.get("values", [])) | set(derived)
    for i, _kind, ident, _key, val in top_items(root, ("event_decl",)):
        at(root, i)
        if isinstance(val, Block):
            names.add(ident)
    ctx.event_names = names
    ctx.event_args = _merge_args(derived, td.get("args", {}))
    ctx.life_args = dict(td.get("life_args", {}))
    ctx.event_tails = _tail_maps(ctx.event_args)
    ctx.life_tails = _tail_maps(ctx.life_args)
