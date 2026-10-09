from .common import *
from .condast import Leaf, leaf_text, narrow_assume, narrow_cond, parse_cond
from .typing import type_ok
from .expr import transpile_exprlist, transpile_stmt, transpile_for
from . import templates as T
from . import messages as M

_QUOTED_LIT_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")


def _emit_and(parts, cur, where, ctx, emit):
    codes = []
    for part in parts:
        code, cur = emit(part, cur, where, ctx)
        codes.append(code)
    return " and ".join(codes), cur


def _emit_or(parts, env, where, ctx, emit):
    codes = []
    cur = dict(env)
    for part in parts:
        code, _ = emit(part, dict(cur), where, ctx)
        codes.append(code)
        cur.update(narrow_assume(part, cur, True) or {})
    return " or ".join(codes), dict(env)


def cond_emit(node, env, where, ctx):
    if isinstance(node, Leaf):
        code, _ = transpile_exprlist(leaf_text(node), env, where, None, ctx=ctx)
        out = dict(env)
        out.update(narrow_assume(node, env, False) or {})
        return code, out
    if node.op == "and":
        return _emit_and(node.parts, dict(env), where, ctx, cond_emit)
    return _emit_or(node.parts, env, where, ctx, cond_emit)


def transpile_cond(cond, env, where, ctx):
    return cond_emit(parse_cond(cond), dict(env), where, ctx)


def _return_expr(st, env, where, ctx):
    if not st[1]:
        return "", "nil"
    code, types = transpile_exprlist(st[1], env, where, None, ctx=ctx)
    rtype = types[0] if types else "any"
    m = _QUOTED_LIT_RE.fullmatch(code)
    if m and (m.group(1) or m.group(2)) in ctx.ids:
        raise LintError(M.RETURN_OBJECT_NAME_WITHOUT_QUOTES % (where,
                        m.group(1) or m.group(2)))
    return code, rtype


def _emit_return(st, indent, env, ret, ret_name, where, ctx):
    code, rtype = _return_expr(st, env, where, ctx)
    src = (st[1] or "").strip()
    if (ret and ret != "any" and src not in ("", "false", "nil")
            and not type_ok(ctx, rtype, ret)):
        c = ("fn %s" % ret_name) if ret_name else "logic"
        raise LintError(M.RETURN_TYPE_EXPECTED
                        % (c, rtype, ret))
    return [T.RETURN % (indent, (" " + code) if code else "")]


def _emit_stmt(st, indent, env, _ret, _ret_name, where, ctx):
    return [indent + transpile_stmt(st[1], env, where, ctx=ctx)]


def _emit_for(st, indent, env, ret, ret_name, where, ctx):
    header, vars_ = transpile_for(st[1], env, where, ctx=ctx)
    out = [T.FOR % (indent, header)]
    child = dict(env)
    child.update(vars_)
    out.extend(emit_logic(st[2], indent + IND, child, ret, ret_name, ctx=ctx))
    out.append(indent + "end")
    return out


def _emit_branches(branches, indent, env, ret, ret_name, where, ctx):
    out = []
    for idx, (cond, body) in enumerate(branches):
        code, eenv = transpile_cond(cond, env, where, ctx)
        out.append(T.THEN % (
            indent, "if" if idx == 0 else "elseif", code))
        out.extend(emit_logic(body, indent + IND, eenv, ret,
                              ret_name, ctx=ctx))
    return out


def _else_env(branches, env):
    eenv = dict(env)
    if len(branches) == 1:
        eenv.update(narrow_cond(branches[0][0], env, negate=True))
    return eenv


def _emit_if(st, indent, env, ret, ret_name, where, ctx):
    branches, else_body = st[1], st[2]
    out = _emit_branches(branches, indent, env, ret, ret_name, where, ctx)
    if else_body is not None:
        out.append(indent + "else")
        out.extend(emit_logic(else_body, indent + IND,
                              _else_env(branches, env), ret, ret_name,
                              ctx=ctx))
    out.append(indent + "end")
    return out


# the emitters of the logic statements
LOGIC_FORMS = {
    "return": _emit_return,
    "stmt": _emit_stmt,
    "for": _emit_for,
    "if": _emit_if,
}


def emit_logic(stmts, indent, env=None, ret=None, ret_name=None, ctx=None):
    env = dict(env or {})
    out = []
    for st in stmts:
        kind = st[0]
        lno = st[-1] if isinstance(st[-1], int) else None
        where = ("logic:%d" % lno) if lno else "logic"
        form = LOGIC_FORMS.get(kind)
        if form is not None:
            out.extend(form(st, indent, env, ret, ret_name, where, ctx))
    return out
