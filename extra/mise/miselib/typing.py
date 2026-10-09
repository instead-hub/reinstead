import re

from .common import *
from . import messages as M


def base(t):
    return t[:-1] if t and t.endswith("?") else t


def tbl_inner(t):
    """Inner type of canonical `tbl[T]`; `""` for `tbl[]`, None otherwise."""
    if t and t.startswith("tbl[") and t.endswith("]"):
        return t[4:-1]
    return None


def _split_top(text, sep):
    """Split `text` on top-level `sep` characters, trimming the parts."""
    cuts = []
    depth = 0
    for i, c in enumerate(text):
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == sep and depth == 0:
            cuts.append(i)
    starts = [0] + [c + 1 for c in cuts]
    ends = cuts + [len(text)]
    return [text[a:b].strip() for a, b in zip(starts, ends)]


def split_union(text):
    """Split a `|` list at top-level parentheses/brackets."""
    return [p for p in _split_top(text, "|") if p]


def union_parts(t):
    """Alternatives of a canonical top-level union, else None."""
    if not t:
        return None
    parts = split_union(base(t))
    return parts if len(parts) > 1 else None


def split_types(text):
    """Split a comma list at top-level parentheses/brackets."""
    return [p for p in _split_top(text, ",") if p]


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


def _canon_alt(known, a, opt, recurse):
    """Canonical body of one union alternative and its optional flag."""
    c = recurse(known, a)
    if c is None:
        return None, opt
    if c == "nil":
        return "", True
    if c.endswith("?"):
        return c[:-1], True
    return c, opt


def _canon_union(known, alts, opt, recurse):
    """`a|b` -> (canonical body, optional flag) or (None, False)."""
    out = []
    for a in alts:
        c, opt = _canon_alt(known, a, opt, recurse)
        if c is None:
            return None, False
        if c and c not in out:
            out.append(c)
    if not out:
        return None, False
    return "|".join(sorted(out)), opt


def _canon_tbl(known, text, opt, recurse):
    """`tbl[...]` -> (canonical body, optional flag) or (None, False)."""
    inner = text[4:].strip()[:-1].strip()
    if not inner:
        return "tbl[]", opt
    c = recurse(known, inner)
    if c is None:
        return None, False
    if c == "any":
        return "tbl", opt
    return "tbl[%s]" % c, opt


def _canon_ret(known, rest, recurse):
    """Canonical return type of an `fn` type; False for a bad arrow."""
    if not rest:
        return None
    if not rest.startswith("->"):
        return False
    ret = recurse(known, rest[2:].strip())
    return False if ret is None else ret


def _canon_fn(known, parts, opt, recurse):
    """`fn(...) -> T` -> (canonical body, optional flag) or (None, False)."""
    inner, rest = parts[0].strip(), parts[1].strip()
    ps = []
    for part in split_types(inner):
        pn, _, pt = part.partition(":")
        if pn.strip() == "...":
            return None, False
        c = recurse(known, pt if pt else pn)
        if c is None:
            return None, False
        ps.append(c)
    ret = _canon_ret(known, rest, recurse)
    if ret is False:
        return None, False
    s = "fn(%s)" % ",".join(ps)
    if ret and ret != "any":
        s += "->" + ret
    return s, opt


def _is_union(text):
    return len(split_union(text)) > 1


def _is_tbl(text):
    return text.startswith("tbl[") and text.endswith("]")


def _is_fn(text):
    return _fn_split(text) is not None


def _is_nil(text):
    return text == "nil"


def _union_form(known, text, opt, recurse):
    return _canon_union(known, split_union(text), opt, recurse)


def _tbl_form(known, text, opt, recurse):
    return _canon_tbl(known, text, opt, recurse)


def _fn_form(known, text, opt, recurse):
    return _canon_fn(known, _fn_split(text), opt, recurse)


def _nil_form(_known, _text, opt, _recurse):
    return (None, False) if opt else ("nil", opt)


# the type-expression forms, tried in order
CANON_FORMS = (
    (_is_union, _union_form),
    (_is_tbl, _tbl_form),
    (_is_fn, _fn_form),
    (_is_nil, _nil_form),
)


def _canon_dispatch(known, text, opt, recurse):
    """Canonical body and optional flag for one type expression."""
    for matches, build in CANON_FORMS:
        if matches(text):
            return build(known, text, opt, recurse)
    if text in known:
        return text, opt
    return None, False


def canon_type(known, text):
    """Return the canonical form of a type or None: `fn(obj)->bool`."""
    text = text.strip()
    opt = text.endswith("?")
    if opt:
        text = text[:-1].strip()
    body, opt = _canon_dispatch(known, text, opt, canon_type)
    if body is None:
        return None
    return body + ("?" if opt else "")


def _alt_error(known, alts, recurse):
    for a in alts:
        msg = recurse(known, a)
        if msg:
            return msg
    return None


def _tbl_error(known, text, t, recurse):
    inner = t[4:].strip()[:-1].strip()
    if inner:
        msg = recurse(known, inner)
        if msg:
            return msg
    return M.BAD_TYPE % text


def _bad_type(text):
    if "(" in text or "[" in text or "]" in text or "->" in text:
        return M.BAD_TYPE % text
    return M.UNKNOWN_TYPE % text


def type_error(known, text):
    """Return an error message for a bad type annotation, else None."""
    if canon_type(known, text) is not None:
        return None
    t = text.strip()
    if t.endswith("?"):
        t = t[:-1].strip()
    alts = split_union(t)
    if len(alts) > 1:
        msg = _alt_error(known, alts, type_error)
        if msg:
            return msg
    if t == "nil":
        return M.UNKNOWN_TYPE % text
    if t.startswith("tbl[") and t.endswith("]"):
        return _tbl_error(known, text, t, type_error)
    return _bad_type(text)


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


# the body view of the reference property types
BODY_TYPES = {
    "ref": "obj",
    "tbl[ref]": "tbl[obj]",
}


def body_type(t):
    """Prop value type as seen in a body: `ref`/`tbl[ref]` become obj forms."""
    if not t:
        return t
    opt = t.endswith("?")
    mapped = BODY_TYPES.get(base(t))
    if mapped is not None:
        return mapped + ("?" if opt else "")
    alts = union_parts(t)
    if alts is not None:
        out = sorted({body_type(a) for a in alts})
        return "|".join(out) + ("?" if opt else "")
    return t


def _named_params(known, inner):
    plist = []
    for part in split_types(inner):
        pn, _, pt = part.partition(":")
        pn, pt = pn.strip(), pt.strip()
        plist.append((pn if pt else None,
                      canon_type(known, pt if pt else pn)))
    return plist


def _named_ret(known, rest):
    if rest.startswith("->"):
        return canon_type(known, rest[2:].strip())
    return None


def named_fn(text, known):
    """`fn(s: obj, ...) [-> ret]` -> ([(name|None, type)], ret|None)."""
    parts = _fn_split(text.strip())
    if parts is None:
        return [], None
    return _named_params(known, parts[0]), _named_ret(known, parts[1].strip())


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
            self._add_alt(known, alt)
        self._init_fn()

    def _add_alt(self, known, alt):
        c = canon_type(known, alt)
        if c is None:
            raise Error(M.PROPS_BAD_TYPE % (alt, self.text))
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

    def _init_fn(self):
        if self.fn is None:
            return
        names = [pn for pn, _pt in self.fn[0]]
        if not names or any(pn is None for pn in names):
            raise Error(M.PROPS_FN_PARAMETERS_NEED_NAMES % self.text)
        self.names = ", ".join(names)
        self.env = {pn: pt for pn, pt in self.fn[0]}
        self.ret = self.fn[1]


def _union_ok(ctx, t, exp, alts, recurse):
    """All alternatives of a `t` union fit `exp`."""
    if t.endswith("?") and not recurse(ctx, "nil", exp):
        return False
    return all(recurse(ctx, alt, exp) for alt in alts)


def _tbl_ok(ctx, t, inner_exp, recurse):
    """Content rules when `exp` is a `tbl[...]` type."""
    inner_t = tbl_inner(t)
    if inner_t is None:
        return False
    if inner_t == "":
        return True
    if inner_exp == "":
        return False
    return recurse(ctx, inner_t, inner_exp)


def _rule_enum_str(ctx, t, exp):
    """An enum or `str` value where an enum or `str` is expected."""
    return exp in ctx.types and t in ("str", exp)


def _rule_str_enum(ctx, t, exp):
    """An enum value where a string is expected."""
    return t in ctx.types and exp == "str"


def _rule_class(ctx, t, exp):
    """An object or class value where a class is expected."""
    return exp in ctx.classes and (t == "obj" or t in ctx.classes)


def _rule_obj_class(ctx, t, exp):
    """A class value where an object is expected."""
    return exp == "obj" and t in ctx.classes


def _rule_fn(_ctx, t, exp):
    """A function value where a function signature is expected."""
    return (exp == "fn" or exp.startswith("fn(")) and (
        t == "fn" or t.startswith("fn("))


# the named-type compatibility rules, tried in order
SCALAR_RULES = (
    _rule_enum_str,
    _rule_str_enum,
    _rule_class,
    _rule_obj_class,
    _rule_fn,
)


def _scalar_ok(ctx, t, exp):
    """Named type, class and fn compatibility rules; None when unmatched."""
    for rule in SCALAR_RULES:
        if rule(ctx, t, exp):
            return True
    return None


def type_ok(ctx, t, exp):
    """May a value of type t be used where type exp is expected?"""
    if exp in (None, "any") or t == exp:
        return True
    t_alts = union_parts(t)
    if t_alts is not None:
        return _union_ok(ctx, t, exp, t_alts, type_ok)
    if exp.endswith("?"):
        return t == "nil" or type_ok(ctx, t, exp[:-1])
    exp_alts = union_parts(exp)
    if exp_alts is not None:
        return any(type_ok(ctx, t, alt) for alt in exp_alts)
    if exp == "tbl":
        return t == "tbl" or tbl_inner(t) is not None
    inner_exp = tbl_inner(exp)
    if inner_exp is not None:
        return _tbl_ok(ctx, t, inner_exp, type_ok)
    return _scalar_ok(ctx, t, exp) is True


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
            return M.NEGATION_NOT_ALLOWED % (typ, value)
        if b in vals:
            return None
    near = difflib.get_close_matches(b, sorted(vals), 1, 0.6)
    hint = " (did you mean %r?)" % near[0] if near else ""
    return M.UNKNOWN_ENUM_VALUE % (typ, value, hint)


def _bare_type(ctx, node, refs):
    """Type of a bare word; refs resolve to obj/event/enum names."""
    if not refs:
        return "str"
    if node.s in ctx.ids:
        return "obj"
    if node.s in ctx.event_names:
        return "event"
    owners = ctx.enum_values.get(node.s)
    if not owners:
        return "str"
    if len(owners) > 1:
        raise Error(M.AMBIGUOUS_VALUE_TYPES
                    % (node.s, ", ".join(sorted(owners))))
    return next(iter(owners))


def _raw_type(_ctx, node, _refs):
    return "obj" if re.fullmatch(r"_'[^']+'", node.s.strip()) else "any"


# the type of each literal class: a name or a (ctx, node, refs) function
LITERAL_TYPES = {
    Num: "num",
    Bool: "bool",
    Nil: "nil",
    Text: "str",
    Data: "tbl",
    Bare: _bare_type,
    Raw: _raw_type,
}


def literal_type(ctx, node, refs=False):
    if isinstance(node, list):
        return "tbl"
    form = LITERAL_TYPES.get(type(node))
    if form is None:
        return "any"
    if isinstance(form, str):
        return form
    return form(ctx, node, refs)
