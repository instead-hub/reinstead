from .common import *
from .expr import transpile_exprlist, transpile_stmt, transpile_for


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
            if ret and ret != "any" and rtype not in ("any", ret):
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
                code, _ = transpile_exprlist(cond, env, where, None, ctx=ctx)
                out.append("%s%s %s then" % (
                    indent, "if" if idx == 0 else "elseif", code))
                out.extend(emit_logic(body, indent + IND, dict(env), ret,
                                      ret_name, ctx=ctx))
            if else_body is not None:
                out.append(indent + "else")
                out.extend(emit_logic(else_body, indent + IND, dict(env),
                                      ret, ret_name, ctx=ctx))
            out.append(indent + "end")
    return out
