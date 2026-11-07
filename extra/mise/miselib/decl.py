import re

from . import state as S
from .common import *
from .typing import canon_type, split_params, split_types, type_error
from . import messages as M
from . import patterns as P

_FN_HEAD_RE = re.compile(r"^fn\s+([\w.+-]+)\s*")


def _fn_header(key):
    """`fn name(params) -> ret` -> (name, params|None, ret|None)."""
    m = _FN_HEAD_RE.match(key)
    if not m:
        raise Error(M.BAD_FN + key)
    name = m.group(1)
    rest = key[m.end():].strip()
    if not rest.startswith("("):
        return _fn_tail(key, name, None, rest)
    end = _paren_end(rest)
    if end is None:
        raise Error(M.BAD_FN + key)
    return _fn_tail(key, name, rest[1:end], rest[end + 1:].strip())


def _paren_end(rest):
    """Index of the `)` closing the leading `(` of rest, or None."""
    depth = 0
    for i, c in enumerate(rest):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _fn_tail(key, name, params, rest):
    """Parse the optional `-> type` part of an `fn` header."""
    if not rest:
        return name, params, None
    if not rest.startswith("->") or not rest[2:].strip():
        raise Error(M.BAD_FN + key)
    return name, params, rest[2:].strip()


def _check_type(name, known, pt, what):
    c = canon_type(known, pt)
    if c is None:
        raise Error(M.FN_MESSAGE % (name, type_error(known, pt), what))
    return c


def _split_param(p):
    """Split `name: type` or a bare parameter name."""
    if ":" in p:
        pn, pt = p.split(":", 1)
        return pn.strip(), pt.strip()
    return p, "any"


def _repeat_type(name, p, known):
    """Canonical type of a `...: T` tail; `any` when untyped."""
    tail = p[3:].lstrip()
    if tail.startswith(":"):
        tail = tail[1:].strip()
    if not tail:
        return "any"
    return _check_type(name, known, tail, "...")


def _fn_params(name, params, known):
    """`(a: T, ...: T)` text -> (plist, variadic type)."""
    if params is None:
        return [("s", "obj"), ("w", "obj"), ("wh", "obj")], False
    plist = []
    if not params.strip():
        return plist, False
    parts = split_params(params)
    for idx, p in enumerate(parts):
        if p.startswith("..."):
            if idx != len(parts) - 1:
                raise Error(M.FN_MUST_BE_LAST_PARAMETER % name)
            return plist, _repeat_type(name, p, known)
        pn, pt = _split_param(p)
        if not P.DSL_RE.fullmatch(pn):
            raise Error(M.FN_BAD_PARAMETER % (name, pn))
        plist.append((pn, _check_type(name, known, pt, pn)))
    return plist, False


def _is_optional(pt):
    return pt == "nil" or pt.endswith("?")


def _check_optional_order(name, plist):
    first_opt = next((i for i, (_pn, pt) in enumerate(plist)
                      if _is_optional(pt)), None)
    if first_opt is None:
        return
    for pn, pt in plist[first_opt + 1:]:
        if not _is_optional(pt):
            raise Error(M.FN_REQUIRED_PARAMETER_AFTER_OPTIONAL
                        % (name, pn))


def parse_fn_sig(key, types=None):
    name, params, ret_text = _fn_header(key)
    known = S.TYPES | (types or set()) | {"nil"}
    plist, variadic = _fn_params(name, params, known)
    _check_optional_order(name, plist)
    if ret_text is None:
        return name, plist, ("any",), variadic
    rets = [_check_type(name, known, rt, "return")
            for rt in split_types(ret_text)]
    return name, plist, tuple(rets), variadic


def sym_text(v):
    if isinstance(v, (Bare, Text)):
        return v.s
    raise Error(M.EXPECTED_EXPRESSION)


def is_true(v):
    return isinstance(v, Bool) and v.s == "true"
