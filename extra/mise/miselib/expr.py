"""The public expression and statement API of the logic language."""
import re

from . import state as S
from .common import *
from .lex import lex_lua
from .typing import canon_type, type_error, type_ok
from .exprparse import Call, ExprEmit, Field, Index, Ref, check_arity, fn_call
from . import messages as M
from . import patterns as P


def expr_cont(s):
    c = s[0]
    if c == "#":
        return False
    if c == "~":
        return not (len(s) > 1 and (s[1].isalpha() or s[1] == "_"))
    if c == "-":
        return not (len(s) > 1 and s[1].isdigit())
    if c in "=<>~+*/%^.,)]}:":
        return True
    m = P.DSL_RE.match(s)
    return bool(m and m.group(0) in S.KEYWORDS)

def _no_paren_kind(plist, variadic, rest, env, ctx):
    """`"str"`, `"typed"` or None (not a one-argument no-paren call)."""
    if not plist:
        if expr_cont(rest):
            return None
        return "str" if not expr_like(rest, env, ctx) else "typed"
    if not variadic and plist[0][1] != "str":
        return None
    return "str" if not expr_like(rest, env, ctx) else "typed"


def _typed_arg_form(name, sig, rest, env, where, ctx, parse):
    plist, ret, variadic = sig
    try:
        code, types = parse(
            rest, env, where, plist[0][1] if plist else None, ctx)
    except LintError as e:
        if isinstance(e, TypeCheckError):
            raise
        if plist and plist[0][1] == "str":
            return fn_call(ctx, name, [lua_str(rest)]), ["str"]
        raise
    check_arity(name, plist, variadic, len(types))
    for (pn, pt), t in zip(plist, types):
        if not type_ok(ctx, t, pt):
            raise TypeCheckError(M.FN_ARGUMENT_EXPECTS_GOT
                                 % (name, pn, pt, t))
    return fn_call(ctx, name, [code]), [ret]


def no_paren_call(text, env, where, ctx):
    """Raw-text forms only; typed one-arg calls are parsed by ExprEmit."""
    m = re.match(r"^(" + P.DSL_NAME + r")\s+([^(\s].*)$", text.strip(), re.S)
    if not m or m.group(1) not in ctx.fn_sigs:
        return None
    name = m.group(1)
    plist, ret, variadic = ctx.fn_sigs[name]
    rest = m.group(2).strip()
    if not rest or not (len(plist) == 1 or variadic):
        return None
    kind = _no_paren_kind(plist, variadic, rest, env, ctx)
    if kind is None:
        return None
    if kind == "str":
        return fn_call(ctx, name, [lua_str(rest)]), ["str"]
    return _typed_arg_form(name, (plist, ret, variadic), rest, env, where,
                           ctx, transpile_exprlist)

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


def _values(p):
    codes = []
    types = []
    while True:
        p.expected = None
        node = p.expr()
        p.expected = None
        codes.append(node.code)
        types.append(node.t)
        if not p.accept(","):
            break
    return codes, types


def _local_values(p, names, types):
    codes, vals = _values(p)
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
    if not (isinstance(lhs, Field) and lhs.recv in ctx.fields
            and lhs.fname in ctx.fields[lhs.recv] and types):
        return
    old = ctx.fields[lhs.recv][lhs.fname][0]
    new = types[0]
    if old != "any" and new != "any" and not type_ok(ctx, new, old):
        raise LintError(M.METHOD_CANNOT_TAKE
                        % (where, lhs.recv, lhs.fname, old, new))


def _stmt_assign(p, lhs, op, env, where, ctx):
    codes, types = _values(p)
    p.expect_eof()
    _check_env_assign(lhs, types, env, ctx, where)
    _check_field_assign(lhs, types, ctx, where)
    lhs_code = lhs.raw if (isinstance(lhs, Field) and lhs.ref) else lhs.code
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
    if s in ctx.fn_sigs and not ctx.fn_sigs[s][0]:
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


def transpile_for(header, env, where, ctx):
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

def expr_like(s, env, ctx):
    c = s[0]
    if c in "'\"([{`_#":
        return True
    if c.isdigit():
        return True
    if c == "-" and len(s) > 1 and s[1].isdigit():
        return True
    m = P.DSL_RE.match(s)
    if not m:
        return False
    tok = m.group(0)
    return (tok in env or tok in ctx.vars or tok in ctx.ids or tok in ctx.fn_sigs
            or tok in ctx.funcs)
