import re

from .common import *


def base(t):
    return t[:-1] if t and t.endswith("?") else t


def type_ok(ctx, t, exp):
    """May a value of type t be used where type exp is expected?"""
    if exp in (None, "any") or t == exp:
        return True
    if exp.endswith("?"):
        return t == "nil" or type_ok(ctx, t, exp[:-1])
    if exp in ctx.types and t in ("str", exp):
        return True
    if t in ctx.types and exp == "str":
        return True
    return False


def type_value_error(ctx, typ, value):
    """Return an error message if value is not valid for enum type typ."""
    import difflib
    td = ctx.types.get(typ)
    if td is None:
        return None
    vals, negate = td["values"], td["negate"]
    neg = value.startswith("~")
    b = value[1:] if neg else value
    if value in vals:
        return None
    if neg:
        if not negate:
            return "type %s does not allow '~' negation (%r)" % (typ, value)
        if b in vals:
            return None
    near = difflib.get_close_matches(b, sorted(vals), 1, 0.6)
    hint = " (did you mean %r?)" % near[0] if near else ""
    return "unknown %s %r%s" % (typ, value, hint)


def literal_type(ctx, node, refs=False):
    if isinstance(node, list):
        return "tbl"
    if isinstance(node, Num):
        return "num"
    if isinstance(node, Bool):
        return "bool"
    if isinstance(node, Nil):
        return "nil"
    if isinstance(node, Text):
        return "str"
    if isinstance(node, Bare):
        if refs:
            if node.s in ctx.ids:
                return "obj"
            if node.s in ctx.event_names:
                return "event"
            owners = ctx.enum_values.get(node.s)
            if owners:
                if len(owners) > 1:
                    raise Error("ambiguous value %r (types: %s)"
                                % (node.s, ", ".join(sorted(owners))))
                return next(iter(owners))
        return "str"
    if isinstance(node, Data):
        return "tbl"
    if isinstance(node, Raw) and re.fullmatch(r"_'[^']+'", node.s.strip()):
        return "obj"
    return "any"
