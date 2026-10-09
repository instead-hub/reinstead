"""Types, `props:` and reference fields: registration and value checks."""
import re

from . import state as S
from .common import *
from .decl import classify
from .typing import Prop, literal_type, type_ok
from . import messages as M


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
    if not re.fullmatch(r"\S+", x.s, re.UNICODE):
        raise Error(M.TYPE_BAD_VALUE % (name, x.s))
    return x.s


def _new_type(ctx, name, val):
    if name in ctx.types:
        raise Error(M.DUPLICATE_TYPE + name)
    if isinstance(val, Block):
        raise Error(M.TYPE_NO_VALUES % name)
    atoms = list(_type_atoms(val))
    negate = _is_negation(name, atoms)
    rest = atoms[1:] if negate else atoms
    vals = [_type_value(name, x) for x in rest]
    if not vals:
        raise Error(M.TYPE_NO_VALUES % name)
    ctx.types[name] = {"values": vals, "negate": negate}


def _extend_type(ctx, name, val):
    if name not in ctx.types:
        raise Error(M.EXTEND_TYPE_UNKNOWN_TYPE % name)
    if isinstance(val, Block):
        raise Error(M.EXTEND_TYPE_NO_VALUES % name)
    td = ctx.types[name]
    for x in _type_atoms(val):
        if (isinstance(x, Text) or not isinstance(x, (Bare, Num))
                or x.s == "~"):
            raise Error(M.EXTEND_TYPE_EXPECTED_BARE_VALUES % name)
        if not re.fullmatch(r"\S+", x.s, re.UNICODE):
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
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        kind, name = classify(key)
        form = TYPE_FORMS.get(kind)
        if form is not None:
            form(ctx, name, val)
    ctx.enum_values = {}
    for _tname, td in ctx.types.items():
        for _v in td["values"]:
            ctx.enum_values.setdefault(_v, set()).add(_tname)
    return ctx.types


def _register_prop(ctx, known, name, tval):
    """Validate and register one `props:` entry."""
    if not re.fullmatch(r"[^\W\d]\w*", name, re.UNICODE):
        raise Error(M.BAD_PROP_NAME % name)
    if name in ctx.props:
        raise Error(M.DUPLICATE_PROP + name)
    if not isinstance(tval, (Bare, Text)):
        raise Error(M.PROPS_NEEDS_TYPE % name)
    prop = Prop(tval.s, known)
    ctx.props[name] = prop
    if prop.names:
        ctx.prop_params[name] = prop.names
    if prop.has_ref or prop.has_reflist:
        ctx.ref_fields.add(name)


def register_props(root, ctx):
    """`props:` -> typed engine properties (refs, handlers, text/fn)."""
    ctx.props = {}
    ctx.prop_params = {}
    known = S.TYPES | set(ctx.types) | {"ref", "nil"}
    for i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(i)
        if classify(key)[0] != "props":
            continue
        if not isinstance(val, Block):
            raise Error(M.PROPS_MUST_BE_BLOCK)
        for j, (name, tval) in enumerate(val.items):
            CURRENT_LINE[0] = val.line_at(j) or CURRENT_LINE[0]
            _register_prop(ctx, known, name, tval)


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
            if not re.fullmatch(r"[#@\w]+", it.s, re.UNICODE):
                raise Error(M.OBJECT_NAME_IDENTIFIER % (where, it.s))
            _check_ref_name(ctx, where, it.s)
        else:
            raise Error(M.EXPECTED_OBJECT_REFERENCE
                        % (where, type(it).__name__.lower()))


def _prop_bare(prop, val, where, t):
    if S.USE_RE.match(val.s.strip()):
        if prop.fn is None:
            raise Error(M.EXPECTED_GOT_USE % (where, prop.text))
        return "any", False
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
    if prop.has_reflist:
        check_ref_list(ctx, where, val)
        return "tbl", False
    if prop.has_tbl:
        if prop.tbl_elem:
            for it in val:
                t = literal_type(ctx, it)
                if not type_ok(ctx, t, prop.tbl_elem):
                    raise Error(M.EXPECTED_GOT_IN_LIST
                                % (where, prop.tbl_elem, t))
        return "tbl", False
    raise Error(M.EXPECTED_GOT_LIST % (where, prop.text))


def _prop_scalar(prop, kind, flag, where):
    if getattr(prop, flag):
        return kind, False
    raise Error(M.EXPECTED_GOT % (where, prop.text, kind))


def check_prop_value(ctx, owner, base, prop, val, t):
    """Validate a prop field value; returns (type, is_ref)."""
    where = ("%s.%s" % (owner, base)) if owner else base
    if isinstance(val, Raw):
        return "any", False
    if isinstance(val, Nil):
        return "nil", False
    if isinstance(val, Data):
        return "tbl", False
    if isinstance(val, (Logic, Lua)):
        if prop.fn is None:
            raise Error(M.EXPECTED_GOT_FUNCTION % (where, prop.text))
        return "any", False
    if isinstance(val, Bare):
        return _prop_bare(prop, val, where, t)
    if isinstance(val, Text):
        return _prop_text(prop, val, where)
    if isinstance(val, list):
        return _prop_list(ctx, prop, val, where)
    if isinstance(val, Num):
        return _prop_scalar(prop, "num", "has_num", where)
    if isinstance(val, Bool):
        return _prop_scalar(prop, "bool", "has_bool", where)
    if prop.has_tbl:
        return "tbl", False
    raise Error(M.EXPECTED_GOT
                % (where, prop.text, type(val).__name__.lower()))


def register_refs(root, ctx):
    ctx.ref_fields = set()
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        kind, _info = classify(key)
        if kind not in ("refs", "extend_refs"):
            continue
        if isinstance(val, Block):
            raise Error(M.REFS_EXPECTED_LIST_NAMES)
        for x in _type_atoms(val):
            if isinstance(x, Text) or not isinstance(x, Bare) or x.s == "~":
                raise Error(M.REFS_EXPECTED_BARE_NAMES)
            if not re.fullmatch(r"\S+", x.s, re.UNICODE):
                raise Error(M.REFS_BAD_NAME % x.s)
            ctx.ref_fields.add(x.s)


def register_events(root, ctx):
    names = set(ctx.types.get("event", {}).get("values", []))
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        kind, ident = classify(key)
        if kind == "event_decl" and isinstance(val, Block):
            names.add(ident)
    ctx.event_names = names
