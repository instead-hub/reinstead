import re

from . import state as S
from .common import *

def lex_lua(text):
    toks = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c in "\"'":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == c:
                    j += 1
                    break
                j += 1
            else:
                raise LintError("unterminated string: %s" % text)
            toks.append(("str", text[i:j]))
            i = j
            continue
        if text.startswith("[[", i):
            j = text.find("]]", i + 2)
            if j < 0:
                raise LintError("unterminated long string: %s" % text)
            toks.append(("str", text[i:j + 2]))
            i = j + 2
            continue
        if c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            m = re.match(r"(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", text[i:])
            toks.append(("num", m.group(0)))
            i += m.end()
            continue
        if c.isalpha() or c == "_":
            m = re.match(r"[^\W\d]\w*", text[i:], re.UNICODE)
            toks.append(("name", m.group(0)))
            i += m.end()
            continue
        if c == "~" and i + 1 < n and (text[i + 1].isalpha()
                                       or text[i + 1] == "_"):
            m = re.match(r"~[^\W\d]\w*", text[i:], re.UNICODE)
            toks.append(("name", m.group(0)))
            i += m.end()
            continue
        m = re.match(r"\.\.\.|\.\.|==|~=|<=|>=|::|//|[+\-*/%^#<>=(){}\[\],;:.]",
                     text[i:])
        if m:
            toks.append(("op", m.group(0)))
            i += m.end()
            continue
        raise LintError("bad character %r in logic: %s" % (c, text))
    toks.append(("eof", ""))
    return toks

def check_arity(name, plist, variadic, n):
    if variadic:
        if n < len(plist):
            raise LintError("fn %s expects at least %d argument(s), got %d"
                            % (name, len(plist), n))
    elif n != len(plist):
        raise LintError("fn %s expects %d argument(s), got %d"
                        % (name, len(plist), n))

class ExprEmit:
    def __init__(self, toks, env, where, ctx):
        self.toks = toks
        self.i = 0
        self.env = env
        self.where = where
        self.ctx = ctx
        self.expected = None

    def peek(self, k=0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else ("eof", "")

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, val):
        if self.peek()[1] == val:
            self.i += 1
            return True
        return False

    def expect(self, val):
        k, v = self.next()
        if v != val:
            self.err("expected %r, got %r" % (val, v))

    def err(self, msg):
        raise LintError("%s in %s: %s" % (
            msg, self.where, " ".join(t[1] for t in self.toks[:-1])))

    def exprlist(self, expected=None):
        codes = []
        types = []
        while True:
            self.expected = expected
            c, t, _k, _v = self.expr()
            self.expected = None
            codes.append(c)
            types.append(t)
            if not self.accept(","):
                break
        return ", ".join(codes), types

    def check(self, t, exp, code):
        if exp in (None, "any") or t in ("any", exp):
            return
        self.err("expected %s, got %s: %s" % (exp, t, code))

    def strval(self, tok):
        if tok.startswith("["):
            m = re.match(r"\[(=*)\[", tok)
            close = "]" + m.group(1) + "]"
            return tok[m.end():len(tok) - len(close)]
        val, _ = parse_string(tok, 0)
        return val

    def str_arg(self, tok, exp):
        val = self.strval(tok)
        if exp == "obj":
            if val in self.ctx.ids:
                return "_'%s'" % val
            self.err("unknown object %r (expected obj)" % val)
        if exp == "event":
            if val not in self.ctx.event_names:
                self.err("unknown event %r" % val)
            return tok
        if exp == "num":
            self.err("expected num, got str")
        if exp == "bool":
            self.err("expected bool, got str")
        return tok

    def arglist(self, expected_list):
        if self.peek()[0] == "str":
            tok = self.next()
            exp = expected_list[0] if expected_list else None
            return self.str_arg(tok[1], exp), 1
        self.expect("(")
        codes = []
        n = 0
        if not self.accept(")"):
            while True:
                exp = (expected_list[n]
                       if expected_list and n < len(expected_list) else None)
                self.expected = exp
                c, t, _k, _v = self.expr()
                self.expected = None
                self.check(t, exp, c)
                codes.append(c)
                n += 1
                if not self.accept(","):
                    break
            self.expect(")")
        return ", ".join(codes), n

    def call(self, name):
        if name in self.ctx.fn_sigs:
            plist, ret, variadic = self.ctx.fn_sigs[name]
            args, n = self.arglist([pt for _pn, pt in plist])
            try:
                check_arity(name, plist, variadic, n)
            except LintError as e:
                self.err(str(e))
            return args, ret
        if name == "_":
            if self.peek()[0] == "str":
                self.err("_'...' is not allowed; use a bare name, #tag "
                         "or quoted name")
            args, _ = self.arglist(None)
            return args, "obj"
        if name in self.ctx.funcs or name in self.env:
            args, _ = self.arglist(None)
            return args, "any"
        self.err("unknown function %r (declare fn %s)" % (name, name))

    def primary(self):
        kind, val = self.next()
        if kind == "num":
            return val, "num", "lit", None
        if kind == "str":
            if self.expected == "obj":
                self.err("strings are not objects; use a bare name (%r)"
                         % self.strval(val))
            if self.expected == "event":
                if self.strval(val) not in self.ctx.event_names:
                    self.err("unknown event %r" % self.strval(val))
                return val, "event", "lit", self.strval(val)
            return val, "str", "lit", self.strval(val)
        if kind == "op" and val == "...":
            return val, "any", "lit", None
        if kind == "name":
            if val in ("nil", "true", "false"):
                return val, "bool" if val != "nil" else "any", "lit", None
            if val in S.KEYWORDS:
                if val == "function":
                    self.err("anonymous functions are not allowed (use |lua)")
                self.err("unexpected keyword %r" % val)
            if val in self.env:
                return val, self.env[val], "name", val
            if val in self.ctx.ids:
                return "_'%s'" % val, "obj", "objref", None
            if val in self.ctx.fn_sigs:
                return "fn_" + val, "fn", "name", val
            if val in self.ctx.funcs:
                return val, "fn", "name", val
            if val in self.ctx.vars:
                return val, self.ctx.global_types.get(val, "any"), "name", val
            if self.expected == "event" and val in self.ctx.event_names:
                return "'%s'" % val, "event", "lit", val
            if self.expected == "event":
                self.err("unknown event %r" % val)
            self.err("unknown name %r" % val)
        if kind == "op" and val == "(":
            self.expected = None
            c, t, _k, _v = self.expr()
            self.expect(")")
            return "(%s)" % c, t, "expr", None
        if kind == "op" and val == "{":
            self.err("table constructors are not allowed in logic "
                     "(wrap it in fn)")
        self.err("unexpected %r" % val)

    def unary(self):
        _k, v = self.peek()
        if v == "not":
            self.next()
            c, _t, _k2, _v2 = self.unary()
            return "not %s" % c, "bool", "expr", None
        if v == "-":
            self.next()
            c, _t, _k2, _v2 = self.unary()
            return "-%s" % c, "num", "expr", None
        if v == "#":
            nk, nv = self.peek(1)
            if nk == "name" and ("#" + nv) in self.ctx.ids:
                self.next()
                self.next()
                return self.postfix("_'#%s'" % nv, "obj", "objref", None)
            self.next()
            c, _t, _k2, _v2 = self.unary()
            return "#%s" % c, "num", "expr", None
        return self.postfix(*self.primary())

    def or_expr(self):
        code, t, k, v = self.and_expr()
        while self.peek()[1] == "or":
            self.next()
            c2, _t2, _k2, _v2 = self.and_expr()
            code = "%s or %s" % (code, c2)
            t, k, v = "any", "expr", None
        return code, t, k, v

    def and_expr(self):
        code, t, k, v = self.cmp_expr()
        while self.peek()[1] == "and":
            self.next()
            c2, _t2, _k2, _v2 = self.cmp_expr()
            code = "%s and %s" % (code, c2)
            t, k, v = "any", "expr", None
        return code, t, k, v

    def cmp_expr(self):
        code, t, k, v = self.concat_expr()
        while self.peek()[1] in ("==", "~=", "<", ">", "<=", ">=", "^"):
            op = self.next()[1]
            if op == "^":
                self.err("^ is forbidden; compare objects with ==")
            self.expected = ("event"
                             if t == "event" and op in ("==", "~=") else None)
            c2, _t2, _k2, _v2 = self.concat_expr()
            self.expected = None
            code = "%s %s %s" % (code, op, c2)
            t, k, v = "bool", "expr", None
        return code, t, k, v

    def concat_expr(self):
        code, t, k, v = self.add_expr()
        while self.peek()[1] == "..":
            self.next()
            c2, _t2, _k2, _v2 = self.add_expr()
            code = "%s .. %s" % (code, c2)
            t, k, v = "str", "expr", None
        return code, t, k, v

    def add_expr(self):
        code, t, k, v = self.mul_expr()
        while self.peek()[1] in ("+", "-"):
            op = self.next()[1]
            c2, t2, _k2, _v2 = self.mul_expr()
            self.check(t, "num", code)
            self.check(t2, "num", c2)
            code = "%s %s %s" % (code, op, c2)
            t, k, v = "num", "expr", None
        return code, t, k, v

    def mul_expr(self):
        code, t, k, v = self.unary()
        while self.peek()[1] in ("*", "/", "%", "//"):
            op = self.next()[1]
            c2, t2, _k2, _v2 = self.unary()
            self.check(t, "num", code)
            self.check(t2, "num", c2)
            code = "%s %s %s" % (code, op, c2)
            t, k, v = "num", "expr", None
        return code, t, k, v

    def expr(self):
        return self.or_expr()

    def autocall(self, code, t, kind, val):
        if (kind == "name" and val in self.ctx.fn_sigs
                and not self.ctx.fn_sigs[val][0]):
            code = "%s()" % code
            t = self.ctx.fn_sigs[val][1]
            kind = "call"
            val = None
        return code, t, kind, val

    def postfix(self, code, t, kind, val):
        while True:
            k, v = self.peek()
            if not (k == "str" or (k == "op" and v == "(")):
                code, t, kind, val = self.autocall(code, t, kind, val)
            if k == "op" and v == ".":
                self.next()
                nk, nv = self.next()
                if nk != "name":
                    self.err("expected field name")
                if t == "str":
                    self.err("strings are not objects; use a bare name (%r)"
                             % (val,))
                code = "%s.%s" % (code, nv)
                kind = "field"
                t = "any"
                val = None
            elif k == "op" and v == "[":
                self.next()
                self.expected = None
                ic, _it, _ik, _iv = self.expr()
                self.expect("]")
                code = "%s[%s]" % (code, ic)
                kind = "field"
                t = "any"
                val = None
            elif k == "op" and v == ":":
                self.next()
                nk, nv = self.next()
                if nk != "name":
                    self.err("expected method name")
                if nv not in self.ctx.fn_sigs:
                    self.err("method %r is not a fn (engine methods are "
                             "not allowed in logic)" % nv)
                plist, ret, variadic = self.ctx.fn_sigs[nv]
                if not plist:
                    self.err("fn %s takes no receiver" % nv)
                if t == "str":
                    self.err("strings are not objects; use a bare name (%r)"
                             % (val,))
                self.check(t, plist[0][1], code)
                nk, nv2 = self.peek()
                if (not variadic and len(plist) == 1
                        and not (nk == "str"
                                 or (nk == "op" and nv2 == "("))):
                    code = "fn_%s(%s)" % (nv, code)
                    t = ret
                    kind = "call"
                    val = None
                    continue
                if (not variadic and len(plist) == 2
                        and self.peek()[0] == "name"
                        and self.peek()[1] not in S.KEYWORDS
                        and self.peek()[1] not in ("nil", "true", "false")):
                    nm = self.next()[1]
                    pt = plist[1][1]
                    if pt == "str":
                        arg, at = lua_str(nm), "str"
                    elif pt == "event" and nm in self.ctx.event_names:
                        arg, at = "'%s'" % nm, "event"
                    elif nm in self.env:
                        arg, at = nm, self.env[nm]
                    elif nm in self.ctx.ids:
                        arg, at = "_'%s'" % nm, "obj"
                    elif nm in self.ctx.fn_sigs and not self.ctx.fn_sigs[nm][0]:
                        arg, at = "fn_%s()" % nm, self.ctx.fn_sigs[nm][1]
                    elif nm in self.ctx.vars:
                        arg, at = nm, self.ctx.global_types.get(nm, "any")
                    else:
                        self.err("unknown name %r" % nm)
                    self.check(at, pt, arg)
                    code = "fn_%s(%s, %s)" % (nv, code, arg)
                    t = ret
                    kind = "call"
                    val = None
                    continue
                args, n = self.arglist([pt for _pn, pt in plist[1:]])
                try:
                    check_arity(nv, plist[1:], variadic, n)
                except LintError as e:
                    self.err(str(e))
                if args:
                    code = "fn_%s(%s, %s)" % (nv, code, args)
                else:
                    code = "fn_%s(%s)" % (nv, code)
                t = ret
                kind = "call"
                val = None
            elif (kind == "name"
                  and ((k == "name" and v not in S.KEYWORDS)
                       or (k == "op" and v in ("#", "-"))
                       or k == "num")):
                exp = None
                rt = "any"
                variadic = False
                if val in self.ctx.fn_sigs:
                    plist, rt, variadic = self.ctx.fn_sigs[val]
                    if not plist:
                        self.err("fn %s takes no arguments" % val)
                    try:
                        check_arity(val, plist, variadic, 1)
                    except LintError as e:
                        self.err(str(e))
                    exp = plist[0][1]
                save = self.i
                self.expected = exp
                if exp == "str" or variadic:
                    c, t, _k2, _v2 = self.expr()
                else:
                    c, t, _k2, _v2 = self.unary()
                    if exp not in (None, "any") and t not in ("any", exp):
                        self.i = save
                        self.expected = exp
                        c, t, _k2, _v2 = self.expr()
                self.expected = None
                self.check(t, exp, c)
                code = "%s(%s)" % (code, c)
                t = rt
                kind = "call"
                val = None
            elif (k == "str" or (k == "op" and v == "(")):
                if kind == "name":
                    args, rt = self.call(val)
                    code = "%s(%s)" % (code, args)
                    t = rt
                    kind = "call"
                    val = None
                else:
                    self.err("call of field/expression is not allowed in "
                             "logic (wrap it in fn)")
            else:
                return code, t, kind, val

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
    m = re.match(r"[^\W\d]\w*", s, re.UNICODE)
    return bool(m and m.group(0) in S.KEYWORDS)

def no_paren_call(text, env, where, ctx):
    """Raw-text forms only; typed one-arg calls are parsed by ExprEmit."""
    m = re.match(r"^([^\W\d]\w*)\s+([^(\s].*)$", text.strip(), re.S)
    if not m or m.group(1) not in ctx.fn_sigs:
        return None
    name = m.group(1)
    plist, ret, variadic = ctx.fn_sigs[name]
    rest = m.group(2).strip()
    if not rest or not (len(plist) == 1 or variadic):
        return None
    if not plist:
        if expr_cont(rest):
            return None
        if not say_expr_start(rest, env, ctx):
            return "fn_%s(%s)" % (name, lua_str(rest)), ["str"]
    elif not variadic and plist[0][1] != "str":
        return None
    elif not say_expr_start(rest, env, ctx):
        return "fn_%s(%s)" % (name, lua_str(rest)), ["str"]
    try:
        code, types = transpile_exprlist(
            rest, env, where, plist[0][1] if plist else None, ctx)
    except LintError:
        if plist and plist[0][1] == "str":
            return "fn_%s(%s)" % (name, lua_str(rest)), ["str"]
        raise
    check_arity(name, plist, variadic, len(types))
    for (pn, pt), t in zip(plist, types):
        if pt != "any" and t not in ("any", pt):
            raise LintError("fn %s: argument %s expects %s, got %s"
                            % (name, pn, pt, t))
    return "fn_%s(%s)" % (name, code), [ret]

def transpile_exprlist(text, env, where, expected=None, ctx=None):
    raw = no_paren_call(text, env, where, ctx)
    if raw is not None:
        return raw
    p = ExprEmit(lex_lua(text), env, where, ctx)
    code, types = p.exprlist(expected)
    if p.peek()[0] != "eof":
        p.err("unexpected %r" % p.peek()[1])
    if expected and types:
        p.check(types[0], expected, code)
    return code, types

def transpile_stmt(text, env, where, ctx):
    s = text.strip()
    if s in ctx.fn_sigs and not ctx.fn_sigs[s][0]:
        return "fn_%s()" % s
    raw = no_paren_call(text, env, where, ctx)
    if raw is not None:
        return raw[0]
    p = ExprEmit(lex_lua(text), env, where, ctx)
    kind, val = p.peek()
    if kind == "name" and val == "local":
        p.next()
        names = []
        while True:
            nk, nv = p.next()
            if nk != "name":
                p.err("expected local name")
            names.append(nv)
            if not p.accept(","):
                break
        types = ["any"] * len(names)
        if p.accept("="):
            codes = []
            idx = 0
            while True:
                p.expected = None
                c, t, _k, _v = p.expr()
                p.expected = None
                codes.append(c)
                if idx < len(types):
                    types[idx] = t
                idx += 1
                if not p.accept(","):
                    break
            code = "local %s = %s" % (", ".join(names), ", ".join(codes))
        else:
            code = "local " + ", ".join(names)
        if p.peek()[0] != "eof":
            p.err("unexpected %r" % p.peek()[1])
        for n, t in zip(names, types):
            env[n] = t
        return code
    if kind == "name" and val == "break":
        p.next()
        if p.peek()[0] != "eof":
            p.err("unexpected %r" % p.peek()[1])
        return "break"
    p.expected = None
    lhs, _lt, lk, lv = p.expr()
    if p.accept("="):
        codes = []
        types = []
        while True:
            p.expected = None
            c, t, _k, _v = p.expr()
            p.expected = None
            codes.append(c)
            types.append(t)
            if not p.accept(","):
                break
        if p.peek()[0] != "eof":
            p.err("unexpected %r" % p.peek()[1])
        if lk == "name" and lv in env and types:
            env[lv] = types[0]
        return "%s = %s" % (lhs, ", ".join(codes))
    if p.peek()[0] != "eof":
        p.err("unexpected %r" % p.peek()[1])
    if lk == "name" and lv in ctx.fn_sigs:
        p.err("fn %s must be called with ()" % lv)
    if lk not in ("name", "field", "call"):
        p.err("unsupported statement")
    return lhs

def transpile_for(header, env, where, ctx):
    if re.search(r"\bin\b", header):
        names, iterable = re.split(r"\bin\b", header, 1)
        vars_ = [v.strip() for v in names.split(",") if v.strip()]
        for v in vars_:
            if not re.fullmatch(r"[^\W\d]\w*", v, re.UNICODE):
                raise LintError("bad loop variable %r in %s" % (v, where))
        code, _ = transpile_exprlist(iterable, env, where, None, ctx)
        return ("for %s in %s" % (", ".join(vars_), code),
                {v: "any" for v in vars_})
    parts = split_list(header)
    m = re.match(r"^([^\W\d]\w*)\s*=\s*(.*)$", parts[0], re.UNICODE)
    if not m:
        raise LintError("bad for header in %s: %s" % (where, header))
    start, st = transpile_exprlist(m.group(2), env, where, None, ctx)
    if st and st[0] not in ("num", "any"):
        raise LintError("%s: for bound must be num, got %s" % (where, st[0]))
    codes = [start]
    for p in parts[1:]:
        c, ct = transpile_exprlist(p, env, where, None, ctx)
        if ct and ct[0] not in ("num", "any"):
            raise LintError("%s: for bound must be num, got %s"
                            % (where, ct[0]))
        codes.append(c)
    return ("for %s = %s" % (m.group(1), ", ".join(codes)),
            {m.group(1): "num"})

def say_expr_start(s, env, ctx):
    c = s[0]
    if c in "'\"([{`_#":
        return True
    if c.isdigit():
        return True
    if c == "-" and len(s) > 1 and s[1].isdigit():
        return True
    m = re.match(r"[^\W\d]\w*", s, re.UNICODE)
    if not m:
        return False
    tok = m.group(0)
    return (tok in env or tok in ctx.vars or tok in ctx.ids or tok in ctx.fn_sigs
            or tok in ctx.funcs)
