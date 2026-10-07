import re

from .common import *


def base(t):
    return t[:-1] if t and t.endswith("?") else t


def split_types(text):
    """Split a comma list at top-level parentheses."""
    parts, cur, depth = [], [], 0
    for c in text:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]


def canon_type(known, text):
    """Return the canonical form of a type or None: `fn(obj)->bool`."""
    text = text.strip()
    opt = text.endswith("?")
    if opt:
        text = text[:-1].strip()
    if text.startswith("fn("):
        depth, end = 0, None
        for i in range(2, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            return None
        inner, rest = text[3:end].strip(), text[end + 1:].strip()
        ps = []
        for part in split_types(inner):
            pn, _, pt = part.partition(":")
            if pn.strip() == "...":
                return None
            c = canon_type(known, pt if pt else pn)
            if c is None:
                return None
            ps.append(c)
        ret = None
        if rest:
            if not rest.startswith("->"):
                return None
            ret = canon_type(known, rest[2:].strip())
            if ret is None:
                return None
        s = "fn(%s)" % ",".join(ps)
        if ret and ret != "any":
            s += "->" + ret
        return s + ("?" if opt else "")
    if text == "nil":
        return None if opt else "nil"
    if text not in known:
        return None
    return text + ("?" if opt else "")


def type_error(known, text):
    """Return an error message for a bad type annotation, else None."""
    if canon_type(known, text) is None:
        if text.strip().endswith("?") and text.strip()[:-1] == "nil":
            return "unknown type %r" % text
        if "fn(" in text or "(" in text or "->" in text:
            return "bad type %r" % text
        return "unknown type %r" % text
    return None


def canon_fn_sig(plist, ret, variadic=False):
    """Canonical type of a declared fn (`fn(obj)->bool`)."""
    ps = [pt for _pn, pt in plist]
    if variadic:
        ps.append("...")
    s = "fn(%s)" % ",".join(ps)
    if ret and ret != "any":
        s += "->" + ret
    return s


def fn_type_parts(t):
    """Canonical `fn(...)->T` -> (params, ret|None), else None."""
    t = base(t)
    if not t.startswith("fn("):
        return None
    depth, end = 0, None
    for i in range(2, len(t)):
        if t[i] == "(":
            depth += 1
        elif t[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return None
    inner, rest = t[3:end], t[end + 1:]
    if rest and not rest.startswith("->"):
        return None
    return split_types(inner), (rest[2:] or None if rest else None)


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
    if exp in ctx.classes:
        return t == "obj" or t in ctx.classes
    if exp == "obj" and t in ctx.classes:
        return True
    if (exp == "fn" or exp.startswith("fn(")) and (
            t == "fn" or t.startswith("fn(")):
        return True
    return False


def class_le(ctx, t, exp):
    """Is class t the class exp or a descendant of it?"""
    seen = set()
    while t and t not in seen:
        if t == exp:
            return True
        seen.add(t)
        t = ctx.class_parents.get(t)
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
