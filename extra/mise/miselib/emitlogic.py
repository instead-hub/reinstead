from .common import *
from .condast import Leaf, leaf_text, narrow_assume, narrow_cond, parse_cond
from .typing import type_ok
from .expr import transpile_exprlist, transpile_stmt, transpile_for


def cond_emit(node, env, where, ctx):
    if isinstance(node, Leaf):
        code, _ = transpile_exprlist(leaf_text(node), env, where, None, ctx=ctx)
        out = dict(env)
        out.update(narrow_assume(node, env, False) or {})
        return code, out
    if node.op == "and":
        codes, cur = [], dict(env)
        for part in node.parts:
            code, cur = cond_emit(part, cur, where, ctx)
            codes.append(code)
        return " and ".join(codes), cur
    codes, cur = [], dict(env)
    for part in node.parts:
        code, _ = cond_emit(part, dict(cur), where, ctx)
        codes.append(code)
        cur.update(narrow_assume(part, cur, True) or {})
    return " or ".join(codes), dict(env)


def transpile_cond(cond, env, where, ctx):
    return cond_emit(parse_cond(cond), dict(env), where, ctx)


def emit_logic(stmts, indent, env=None, ret=None, ret_name=None, ctx=None):
    env = dict(env or {})
    out = []
    for st in stmts:
        kind = st[0]
        lno = st[-1] if isinstance(st[-1], int) else None
        where = ("logic:%d" % lno) if lno else "logic"
        if kind == "return":
            code = ""
            rtype = "nil"
            if st[1]:
                code, types = transpile_exprlist(st[1], env, where, None, ctx=ctx)
                rtype = types[0] if types else "any"
                m = re.fullmatch(r"'([^']*)'|\"([^\"]*)\"", code)
                if m and (m.group(1) or m.group(2)) in ctx.ids:
                    raise LintError("%s: %r is an object name; return it "
                                    "without quotes" % (where,
                                    m.group(1) or m.group(2)))
            if ret and ret != "any" and not type_ok(ctx, rtype, ret):
                c = ("fn %s" % ret_name) if ret_name else "logic"
                raise LintError("%s: return type is %s, expected %s"
                                % (c, rtype, ret))
            out.append("%sreturn%s" % (indent, (" " + code) if code else ""))
        elif kind == "stmt":
            out.append(indent + transpile_stmt(st[1], env, where, ctx=ctx))
        elif kind == "for":
            header, vars_ = transpile_for(st[1], env, where, ctx=ctx)
            out.append("%sfor %s do" % (indent, header))
            child = dict(env)
            child.update(vars_)
            out.extend(emit_logic(st[2], indent + IND, child, ret, ret_name,
                                  ctx=ctx))
            out.append(indent + "end")
        elif kind == "if":
            branches, else_body = st[1], st[2]
            for idx, (cond, body) in enumerate(branches):
                code, eenv = transpile_cond(cond, env, where, ctx)
                out.append("%s%s %s then" % (
                    indent, "if" if idx == 0 else "elseif", code))
                out.extend(emit_logic(body, indent + IND, eenv, ret,
                                      ret_name, ctx=ctx))
            if else_body is not None:
                eenv = dict(env)
                if len(branches) == 1:
                    eenv.update(narrow_cond(branches[0][0], env, negate=True))
                out.append(indent + "else")
                out.extend(emit_logic(else_body, indent + IND, eenv,
                                      ret, ret_name, ctx=ctx))
            out.append(indent + "end")
    return out
