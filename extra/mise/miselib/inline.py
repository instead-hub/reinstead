"""The inline-`fn` heuristics: wrappers, adapters and expression bodies."""
import re

from .common import *
from . import messages as M
from . import patterns as P

_CALLEE = P.LUA_NAME + r"(?:\." + P.LUA_NAME + r")*(?::" + P.LUA_NAME + r")?"


def _skip_string(text, i):
    """Index after the quoted run starting at text[i]."""
    quote = text[i]
    i += 1
    while i < len(text) and text[i] != quote:
        if text[i] == "\\":
            i += 1
        i += 1
    return i + 1


def _call_end(text):
    """Index of the `)` closing the call at the first `(`, or None."""
    depth = 0
    i = text.index("(")
    while i < len(text):
        c = text[i]
        if c in "\"'":
            i = _skip_string(text, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def wrapper_template(text):
    """Return the inner call if body is a single call/return-call, else None."""
    b = text.strip()
    if not b or "\n" in b or "..." in b or ";" in b:
        return None
    if b.startswith("return "):
        b = b[7:].strip()
    if not re.match(r"^" + _CALLEE + r"\s*\(", b):
        return None
    end = _call_end(b)
    if end is None:
        return None
    return b if b[end + 1:].strip() == "" else None


def _method_adapter(callee, pnames, got, tails):
    """Forwarded method call; returns (handled, result)."""
    if ":" not in callee:
        return False, None
    recv, meth = callee.split(":", 1)
    if not (pnames and recv == pnames[0]
            and any(got == t[1:] for t in tails)):
        return False, None
    if "fn_" in meth:
        return True, None
    return True, ("method", meth)


def adapter_callee(text, plist, full=False):
    """Return callee if body forwards parameters to it.

    Body must be a single call with `(params..., ...)`; with `full=True`
    the plain `(params...)` form is accepted too (fns with optional
    trailing parameters). Method form (recv:meth(...)) is allowed when
    recv is the first parameter; then ("method", meth) is returned and
    calls emit args[0]:meth(args[1:]).
    """
    b = text.strip()
    if not b or "\n" in b:
        return None
    if b.startswith("return "):
        b = b[7:].strip()
    m = re.match(r"^(" + _CALLEE + r")\s*\(([^()]*)\)$", b)
    if not m:
        return None
    callee, raw = m.group(1), m.group(2)
    got = [a.strip() for a in raw.split(",") if a.strip()]
    pnames = [pn for pn, _pt in plist]
    tails = [pnames + ["..."]]
    if full:
        tails.append(pnames)
    handled, method = _method_adapter(callee, pnames, got, tails)
    if handled:
        return method
    if got in tails:
        return None if "fn_" in callee else callee
    return None


def _params_used_once(plist, text):
    """True if no parameter occurs in text more than once."""
    return all(len(re.findall(P.PARAM_REF % re.escape(pn), text)) <= 1
               for pn, _pt in plist)


def _inline_expr(ctx, name, val, plist, has_optional):
    e = val.s.strip()
    if not e or ";" in e or "..." in e or "fn_" in e:
        raise Error(M.FN_BAD_EXPRESSION_BODY % name)
    if not _params_used_once(plist, e):
        raise Error(M.FN_EXPRESSION_BODY_USES_PARAMETER % name)
    if has_optional:
        for pn, pt in plist:
            if ((pt == "nil" or pt.endswith("?"))
                    and re.search(P.PARAM_REF % re.escape(pn), e)):
                raise Error(M.FN_EXPRESSION_BODY_CANNOT_OPTIONAL % (name, pn))
    ctx.inline[name] = ("expr", (plist, e))


def _set_adapter(ctx, name, callee):
    """Register a `call`/`meth` adapter if the body matched one."""
    if not callee:
        return
    if isinstance(callee, tuple):
        ctx.inline[name] = ("meth", (callee[1],))
    else:
        ctx.inline[name] = ("call", (callee,))


def _inline_fn(ctx, name, val, plist, variadic):
    has_optional = any(pt == "nil" or pt.endswith("?") for _pn, pt in plist)
    if isinstance(val, Raw):
        if variadic:
            raise Error(M.FN_EXPRESSION_BODY_VARIADIC % name)
        _inline_expr(ctx, name, val, plist, has_optional)
        return
    if not isinstance(val, Lua):
        return
    if variadic:
        _set_adapter(ctx, name, adapter_callee(val.s, plist))
        return
    if has_optional:
        _set_adapter(ctx, name, adapter_callee(val.s, plist, full=True))
        return
    t = wrapper_template(val.s)
    if t and ("fn_" in t or not _params_used_once(plist, t)):
        return
    if t:
        ctx.inline[name] = ("wrap", (plist, t))
