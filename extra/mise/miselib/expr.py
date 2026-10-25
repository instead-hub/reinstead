"""The public expression and statement API of the logic language."""
import re

from . import state as S
from .common import *
from .common import _scan_depth
from .lex import lex_lua
from .constructs import ENGINE_FIELDS
from .typing import canon_type, tbl_inner, type_error, type_ok
from .exprparse import (Call, ExprEmit, Field, Index, Ref, check_arity,
                        expr_list, fn_call, min_args)
from . import messages as M
from . import patterns as P


def _expects_str(ctx, pt):
    """Does a parameter type accept a string value? `any` is not text."""
    return bool(pt) and pt != "any" and type_ok(ctx, "str", pt)


def _tail_type(sig):
    """Type of the only no-paren argument, or None."""
    plist, _rets, variadic = sig
    if len(plist) == 1:
        return plist[0][1]
    if not plist and variadic:
        return variadic
    return None


def _text_tail(sig, rest, ctx):
    """Is the no-paren tail of this call a raw text argument?"""
    pt = _tail_type(sig)
    if not pt or not rest or rest.startswith("(") \
            or rest[0] in "\"'" or P.LONG_OPEN_RE.match(rest):
        return False
    return _expects_str(ctx, pt)


_TEXT_CALLS = ("p", "pn", "pr")


def _text_arg(name, text, ctx):
    """One-string call with a `p "..."`/`pn`/`pr` adapter when possible."""
    desc = ctx.inline.get(name)
    if desc is not None and desc[0] == "call" and desc[1][0] in _TEXT_CALLS:
        return desc[1][0] + " " + lua_str(text), ["str"]
    return fn_call(ctx, name, [lua_str(text)]), ["str"]


def _typed_arg_form(name, sig, rest, env, where, ctx, parse):
    plist, rets, variadic = sig
    code, types = parse(
        rest, env, where, plist[0][1] if plist else None, ctx)
    check_arity(name, plist, variadic, len(types))
    for (pn, pt), t in zip(plist, types):
        if not type_ok(ctx, t, pt):
            raise TypeCheckError(M.FN_ARGUMENT_EXPECTS_GOT
                                 % (name, pn, pt, t))
    for i, t in enumerate(types[len(plist):], len(plist) + 1):
        if not type_ok(ctx, t, variadic or "any"):
            raise TypeCheckError(M.FN_ARGUMENT_EXPECTS_GOT
                                 % (name, i, variadic, t))
    return fn_call(ctx, name, [code]), list(rets)


def no_paren_call(text, env, where, ctx):
    """Raw-text forms only; typed one-arg calls are parsed by ExprEmit."""
    m = re.match(r"^(" + P.DSL_NAME + r")\s+([^(\s].*)$", text.strip(), re.S)
    if not m or m.group(1) not in ctx.fn_sigs:
        return None
    name = m.group(1)
    plist, rets, variadic = ctx.fn_sigs[name]
    rest = m.group(2).strip()
    if not rest or not (len(plist) == 1 or variadic):
        return None
    sig = (plist, rets, variadic)
    if _text_tail(sig, rest, ctx):
        return _text_arg(name, rest, ctx)
    pt = _tail_type(sig)
    if not _expects_str(ctx, pt):
        return None
    return _typed_arg_form(name, sig, rest, env, where, ctx,
                           transpile_exprlist)

def transpile_exprlist(text, env, where, expected=None, ctx=None):
    raw = no_paren_call(text, env, where, ctx)
    if raw is not None:
        return raw
    p = ExprEmit(lex_lua(text), env, where, ctx)
    code, types = p.exprlist(expected)
    p.expect_eof()
    if expected and types:
        p.check(types[0], expected, code)
    return code, types

def _local_names(p):
    names = []
    while True:
        nk, nv = p.next()
        if nk != "name":
            p.err(M.EXPECTED_LOCAL_NAME)
        names.append(nv)
        if not p.accept(","):
            break
    return names


def _local_values(p, names, types):
    codes, vals = expr_list(p)
    for i, t in enumerate(vals):
        if i < len(types):
            types[i] = t
    return "local %s = %s" % (", ".join(names), ", ".join(codes))


def _stmt_local(p, env):
    p.next()
    names = _local_names(p)
    types = ["any"] * len(names)
    code = (_local_values(p, names, types) if p.accept("=")
            else "local " + ", ".join(names))
    p.expect_eof()
    for n, t in zip(names, types):
        env[n] = "any" if t == "nil" else t
    return code


def _stmt_op(p):
    k1, v1 = p.peek()
    if k1 == "op" and v1 in ("=", "+=", "-="):
        return p.next()[1]
    if k1 == "op" and v1 in ("+", "-") and p.peek(1)[1] == "=":
        p.next()
        p.next()
        return v1 + "="
    return None


def _check_env_assign(lhs, types, env, ctx, where):
    if not (isinstance(lhs, Ref) and not lhs.obj and lhs.name in env and types):
        return
    old, new = env[lhs.name], types[0]
    if old == "any":
        env[lhs.name] = new
    elif new != "any" and not type_ok(ctx, new, old):
        raise LintError(M.FN_CANNOT_TAKE
                        % (where, lhs.name, old, new))


def _check_field_assign(lhs, types, ctx, where):
    if not (isinstance(lhs, Field) and lhs.fname):
        return
    if lhs.fname in ENGINE_FIELDS:
        raise LintError(M.ENGINE_FIELD_READONLY % (where, lhs.fname))
    if not lhs.fname.startswith("__") and lhs.fname not in ctx.field_names:
        raise LintError(M.UNKNOWN_FIELD % (where, lhs.fname, lhs.fname))
    if not types or lhs.recv not in ctx.fields:
        return
    info = ctx.fields[lhs.recv].get(lhs.fname)
    if info is None:
        return
    old = info[0]
    new = types[0]
    if old != "any" and new != "any" and not type_ok(ctx, new, old):
        raise LintError(M.METHOD_CANNOT_TAKE
                        % (where, lhs.recv, lhs.fname, old, new))


def _stmt_assign(p, lhs, op, env, where, ctx):
    codes, types = expr_list(p)
    p.expect_eof()
    _check_env_assign(lhs, types, env, ctx, where)
    _check_field_assign(lhs, types, ctx, where)
    lhs_code = (lhs.name if isinstance(lhs, Ref) and lhs.var else
                lhs.raw if isinstance(lhs, Field) and lhs.ref else lhs.code)
    if op == "=":
        return "%s = %s" % (lhs_code, ", ".join(codes))
    sign = "+" if op == "+=" else "-"
    return "%s = %s %s (%s)" % (lhs_code, lhs_code, sign, ", ".join(codes))


def _stmt_break(p, _env):
    p.next()
    p.expect_eof()
    return "break"


# the logic statements with their own parsers
STMT_FORMS = {
    "local": _stmt_local,
    "break": _stmt_break,
}


def _check_stmt_lhs(lhs, ctx, p):
    if isinstance(lhs, Ref) and not lhs.obj and lhs.name in ctx.fn_sigs:
        p.err(M.FN_MUST_BE_CALLED % lhs.name)
    if not isinstance(lhs, (Call, Field, Index)) \
            and not (isinstance(lhs, Ref) and not lhs.obj):
        p.err(M.UNSUPPORTED_STATEMENT)


def _stmt_expr(p, env, where, ctx):
    p.expected = None
    lhs = p.expr()
    op = _stmt_op(p)
    if op is not None:
        return _stmt_assign(p, lhs, op, env, where, ctx)
    p.expect_eof()
    _check_stmt_lhs(lhs, ctx, p)
    return lhs.code


def transpile_stmt(text, env, where, ctx):
    s = text.strip()
    if s in ctx.fn_sigs and min_args(ctx.fn_sigs[s][0]) == 0:
        return fn_call(ctx, s, [])
    raw = no_paren_call(text, env, where, ctx)
    if raw is not None:
        return raw[0]
    p = ExprEmit(lex_lua(text), env, where, ctx)
    kind, val = p.peek()
    form = STMT_FORMS.get(val) if kind == "name" else None
    if form is not None:
        return form(p, env)
    return _stmt_expr(p, env, where, ctx)

def _loop_var(spec, where, ctx):
    """`name` or `name: T` -> (name, canonical type or None)."""
    name, sep, pt = spec.partition(":")
    name = name.strip()
    if not P.DSL_RE.fullmatch(name):
        raise LintError(M.BAD_LOOP_VARIABLE % (spec.strip(), where))
    if not sep:
        return name, None
    pt = pt.strip()
    known = S.TYPES | set(ctx.types) | ctx.classes | {"nil"}
    msg = type_error(known, pt)
    if msg:
        raise LintError(M.FOR_MESSAGE % (where, name, msg))
    return name, canon_type(known, pt)


def _for_in(header, env, where, ctx):
    names, iterable = P.IN_RE.split(header, 1)
    vars_ = {}
    for spec in names.split(","):
        if not spec.strip():
            continue
        name, pt = _loop_var(spec, where, ctx)
        vars_[name] = pt or "any"
    code, _ = transpile_exprlist(iterable, env, where, None, ctx)
    return ("%s in %s" % (", ".join(vars_), code), vars_)


def _check_for_var(name, pt, where, ctx):
    if pt is None:
        return
    _, canon = _loop_var("%s: %s" % (name, pt), where, ctx)
    if not type_ok(ctx, "num", canon):
        raise LintError(M.FOR_VARIABLE_EXPECTED_NUM
                        % (where, name, canon))


def _for_bound(p, env, where, ctx):
    code, t = transpile_exprlist(p, env, where, None, ctx)
    if t and t[0] not in ("num", "any"):
        raise LintError(M.FOR_BOUND_MUST_BE_NUM % (where, t[0]))
    return code


def _split_for_of(header):
    """Split `vars of expr` outside strings/brackets."""
    for i, _, depth in _scan_depth(header, 0, "([{", ")]}", naive=True):
        if depth or not header.startswith("of", i):
            continue
        if i and not header[i - 1].isspace():
            continue
        j = i + 2
        if j < len(header) and not header[j].isspace():
            continue
        return header[:i].strip(), header[j:].strip()
    return None


def _for_of(parts, env, where, ctx):
    names_text, iterable = parts
    pairs = [(spec, _loop_var(spec, where, ctx))
             for spec in names_text.split(",") if spec.strip()]
    vars_ = {name: pt or "any" for _spec, (name, pt) in pairs}
    names = list(vars_)
    if len(names) not in (1, 2):
        raise LintError(M.BAD_FOR_HEADER % (where, header))
    code, types = transpile_exprlist(iterable, env, where, None, ctx)
    iter_t = types[0] if types else "any"
    elem = "obj" if iter_t == "list" else (tbl_inner(iter_t) or "any")
    if len(names) == 1:
        name = names[0]
        kind = vars_[name] if vars_[name] != "any" else elem
        return "_, %s in ipairs(%s)" % (name, code), {**vars_, name: kind}
    first, second = names
    return "%s in ipairs(%s)" % (", ".join(names), code), {
        **vars_,
        first: "num" if vars_[first] == "any" else vars_[first],
        second: elem if vars_[second] == "any" else vars_[second],
    }


def transpile_for(header, env, where, ctx):
    of = _split_for_of(header)
    if of is not None:
        return _for_of(of, env, where, ctx)
    if P.IN_RE.search(header):
        return _for_in(header, env, where, ctx)
    parts = split_list(header)
    m = re.match(r"^(" + P.DSL_NAME + r")\s*(?::\s*([^=]+?))?\s*=\s*(.*)$",
                 parts[0], re.UNICODE)
    if not m:
        raise LintError(M.BAD_FOR_HEADER % (where, header))
    name, pt, start_expr = m.group(1), m.group(2), m.group(3)
    _check_for_var(name, pt, where, ctx)
    start = _for_bound(start_expr, env, where, ctx)
    codes = [start] + [_for_bound(p, env, where, ctx) for p in parts[1:]]
    return ("%s = %s" % (name, ", ".join(codes)), {name: "num"})
