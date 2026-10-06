from .common import *
from .typing import type_ok
from .expr import transpile_exprlist, transpile_stmt, transpile_for


def split_top(text, word):
    parts, cur, depth, quote = [], [], 0, None
    tok = " %s " % word
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            cur.append(c)
            i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if depth == 0 and text.startswith(tok, i):
            parts.append("".join(cur).strip())
            cur = []
            i += len(tok)
            continue
        cur.append(c)
        i += 1
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


def split_and(text):
    return split_top(text, "and")


def split_or(text):
    return split_top(text, "or")


def cond_narrow(cond, env, negate=False):
    c = cond.strip()
    forms = ((r"([A-Za-z_]\w*)", False),
             (r"([A-Za-z_]\w*)\s*~=\s*nil", False),
             (r"([A-Za-z_]\w*)\s*==\s*nil", True),
             (r"not\s+([A-Za-z_]\w*)", True))
    for pat, want_nil in forms:
        m = re.fullmatch(pat, c, re.UNICODE)
        if not m:
            continue
        if negate:
            want_nil = not want_nil
        t = env.get(m.group(1))
        if not t or not t.endswith("?"):
            return {}
        return {m.group(1): "nil" if want_nil else t[:-1]}
    return {}


def transpile_cond(cond, env, where, ctx):
    codes = []
    eenv = dict(env)
    for part in split_and(cond):
        ors = split_or(part)
        if len(ors) == 1:
            code, _ = transpile_exprlist(part, eenv, where, None, ctx=ctx)
            codes.append(code)
        else:
            oenv = dict(eenv)
            ocodes = []
            for op in ors:
                code, _ = transpile_exprlist(op, oenv, where, None, ctx=ctx)
                ocodes.append(code)
                oenv.update(cond_narrow(op, oenv, negate=True))
            codes.append(" or ".join(ocodes))
        eenv.update(cond_narrow(part, eenv))
    return " and ".join(codes), eenv


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
                    eenv.update(cond_narrow(branches[0][0], env, negate=True))
                out.append(indent + "else")
                out.extend(emit_logic(else_body, indent + IND, eenv,
                                      ret, ret_name, ctx=ctx))
            out.append(indent + "end")
    return out
