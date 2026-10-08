import re

from .common import *


def base(t):
    return t[:-1] if t and t.endswith("?") else t


def tbl_inner(t):
    """Inner type of canonical `tbl[T]`; `""` for `tbl[]`, None otherwise."""
    if t and t.startswith("tbl[") and t.endswith("]"):
        return t[4:-1]
    return None


def split_union(text):
    """Split a `|` list at top-level parentheses/brackets."""
    parts, cur, depth = [], [], 0
    for c in text:
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == "|" and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    if cur or parts:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]


def union_parts(t):
    """Alternatives of a canonical top-level union, else None."""
    if not t:
        return None
    parts = split_union(base(t))
    return parts if len(parts) > 1 else None


def split_types(text):
    """Split a comma list at top-level parentheses/brackets."""
    parts, cur, depth = [], [], 0
    for c in text:
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]


def _fn_split(t):
    """Split `fn(inner)rest`; returns (inner, rest) or None."""
    if not t.startswith("fn("):
        return None
    depth = 0
    for i in range(2, len(t)):
        if t[i] == "(":
            depth += 1
        elif t[i] == ")":
            depth -= 1
            if depth == 0:
                return t[3:i], t[i + 1:]
    return None


def _canon_union(known, alts, opt):
    """`a|b` -> (canonical body, optional flag) or (None, False)."""
    out = []
    for a in alts:
        c = canon_type(known, a)
        if c is None:
            return None, False
        if c.endswith("?"):
            opt = True
            c = c[:-1]
        if c == "nil":
            opt = True
            continue
        if c not in out:
            out.append(c)
    if not out:
        return None, False
    return "|".join(sorted(out)), opt


def _canon_tbl(known, text, opt):
    """`tbl[...]` -> (canonical body, optional flag) or (None, False)."""
    inner = text[4:].strip()[:-1].strip()
    if not inner:
        return "tbl[]", opt
    c = canon_type(known, inner)
    if c is None:
        return None, False
    if c == "any":
        return "tbl", opt
    return "tbl[%s]" % c, opt


def _canon_fn(known, parts, opt):
    """`fn(...) -> T` -> (canonical body, optional flag) or (None, False)."""
    inner, rest = parts[0].strip(), parts[1].strip()
    ps = []
    for part in split_types(inner):
        pn, _, pt = part.partition(":")
        if pn.strip() == "...":
            return None, False
        c = canon_type(known, pt if pt else pn)
        if c is None:
            return None, False
        ps.append(c)
    ret = None
    if rest:
        if not rest.startswith("->"):
            return None, False
        ret = canon_type(known, rest[2:].strip())
        if ret is None:
            return None, False
    s = "fn(%s)" % ",".join(ps)
    if ret and ret != "any":
        s += "->" + ret
    return s, opt


def canon_type(known, text):
    """Return the canonical form of a type or None: `fn(obj)->bool`."""
    text = text.strip()
    opt = text.endswith("?")
    if opt:
        text = text[:-1].strip()
    alts = split_union(text)
    parts = _fn_split(text)
    if len(alts) > 1:
        body, opt = _canon_union(known, alts, opt)
    elif text.startswith("tbl[") and text.endswith("]"):
        body, opt = _canon_tbl(known, text, opt)
    elif parts is not None:
        body, opt = _canon_fn(known, parts, opt)
    elif text == "nil":
        return None if opt else "nil"
    elif text in known:
        return text + ("?" if opt else "")
    else:
        return None
    if body is None:
        return None
    return body + ("?" if opt else "")


def type_error(known, text):
    """Return an error message for a bad type annotation, else None."""
    if canon_type(known, text) is not None:
        return None
    t = text.strip()
    if t.endswith("?"):
        t = t[:-1].strip()
    alts = split_union(t)
    if len(alts) > 1:
        for a in alts:
            msg = type_error(known, a)
            if msg:
                return msg
    if t == "nil":
        return "unknown type %r" % text
    if t.startswith("tbl[") and t.endswith("]"):
        inner = t[4:].strip()[:-1].strip()
        if inner:
            msg = type_error(known, inner)
            if msg:
                return msg
        return "bad type %r" % text
    if "(" in text or "[" in text or "]" in text or "->" in text:
        return "bad type %r" % text
    return "unknown type %r" % text


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
    parts = _fn_split(base(t) or "")
    if parts is None:
        return None
    inner, rest = parts
    if rest and not rest.startswith("->"):
        return None
    return split_types(inner), (rest[2:] or None if rest else None)


def body_type(t):
    """Prop value type as seen in a body: `ref`/`tbl[ref]` become obj forms."""
    if not t:
        return t
    opt = t.endswith("?")
    b = base(t)
    if b == "ref":
        return "obj" + ("?" if opt else "")
    if b == "tbl[ref]":
        return "tbl[obj]" + ("?" if opt else "")
    alts = union_parts(t)
    if alts is not None:
        out = sorted({body_type(a) for a in alts})
        return "|".join(out) + ("?" if opt else "")
    return t


def named_fn(text, known):
    """`fn(s: obj, ...) [-> ret]` -> ([(name|None, type)], ret|None)."""
    parts = _fn_split(text.strip())
    if parts is None:
        return [], None
    plist = []
    for part in split_types(parts[0]):
        pn, _, pt = part.partition(":")
        pn, pt = pn.strip(), pt.strip()
        plist.append((pn if pt else None,
                      canon_type(known, pt if pt else pn)))
    ret = None
    rest = parts[1].strip()
    if rest.startswith("->"):
        ret = canon_type(known, rest[2:].strip())
    return plist, ret


class Prop:
    """A typed engine property: `str`, `ref`, `tbl[ref]`, `fn(s: obj, ...)`."""

    def __init__(self, text, known):
        self.text = text.strip()
        self.alts = []
        self.has_ref = self.has_reflist = False
        self.has_str = self.has_num = self.has_bool = self.has_tbl = False
        self.has_event = False
        self.tbl_elem = None
        self.fn = None
        self.ret = None
        self.names = None
        self.env = None
        for alt in split_union(self.text):
            c = canon_type(known, alt)
            if c is None:
                raise Error("props: bad type %r in %r" % (alt, self.text))
            self.alts.append(c)
            if c == "ref":
                self.has_ref = True
            elif c == "tbl[ref]":
                self.has_reflist = True
            elif c == "str":
                self.has_str = True
            elif c == "num":
                self.has_num = True
            elif c == "bool":
                self.has_bool = True
            elif c == "tbl":
                self.has_tbl = True
            elif tbl_inner(base(c)):
                self.has_tbl = True
                self.tbl_elem = tbl_inner(base(c))
            elif c == "event":
                self.has_event = True
            elif c.startswith("fn(") and self.fn is None:
                self.fn = named_fn(alt, known)
        if self.fn is not None:
            names = [pn for pn, _pt in self.fn[0]]
            if not names or any(pn is None for pn in names):
                raise Error("props: fn parameters need names in %r"
                            % self.text)
            self.names = ", ".join(names)
            self.env = {pn: pt for pn, pt in self.fn[0]}
            self.ret = self.fn[1]


def type_ok(ctx, t, exp):
    """May a value of type t be used where type exp is expected?"""
    if exp in (None, "any") or t == exp:
        return True
    alts = union_parts(t)
    if alts is not None:
        if t.endswith("?") and not type_ok(ctx, "nil", exp):
            return False
        return all(type_ok(ctx, alt, exp) for alt in alts)
    if exp.endswith("?"):
        return t == "nil" or type_ok(ctx, t, exp[:-1])
    alts = union_parts(exp)
    if alts is not None:
        return any(type_ok(ctx, t, alt) for alt in alts)
    if exp == "tbl":
        return t == "tbl" or tbl_inner(t) is not None
    inner_exp = tbl_inner(exp)
    if inner_exp is not None:
        inner_t = tbl_inner(t)
        if inner_t is None:
            return False
        if inner_t == "":
            return True
        if inner_exp == "":
            return False
        return type_ok(ctx, inner_t, inner_exp)
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
