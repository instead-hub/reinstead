import re

from . import state as S
from .common import *
from .typing import (base, canon_fn_sig, fn_type_parts, type_ok,
                     type_value_error)

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
        m = re.match(r"\.\.\.|\.\.|==|~=|<=|>=|\+=|-=|::|//|[+\-*/%^#<>=(){}\[\],;:.&]",
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


def fn_name(name):
    return "fn_" + name


_SIMPLE_ARG = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|'[^']*'")


def _wrap_params(template, plist, args):
    for i, ((pn, _pt), a) in enumerate(zip(plist, args)):
        ph = "\x00%d\x00" % i
        pat = re.compile(r"(?<![\w.])%s(?![\w])" % re.escape(pn))
        if _SIMPLE_ARG.fullmatch(a):
            template = pat.sub(ph, template)
            continue
        template = re.sub(r"^%s(?=:)" % re.escape(pn), ph, template)
        template = re.sub(r"(?<=[(,\s])%s(?=[,)\s]|$)" % re.escape(pn),
                          ph, template)
        template = pat.sub("(%s)" % ph, template)
    return re.sub(r"\x00(\d+)\x00", lambda m: args[int(m.group(1))],
                  template)


def fn_call(ctx, name, args):
    desc = ctx.inline.get(name)
    if desc:
        kind, payload = desc
        if kind == "wrap":
            plist, tmpl = payload
            return _wrap_params(tmpl, plist, args)
        if kind == "expr":
            plist, tmpl = payload
            return "(%s)" % _wrap_params(tmpl, plist, args)
        if kind == "meth":
            return "%s:%s(%s)" % (args[0], payload[0], ", ".join(args[1:]))
        return "%s(%s)" % (payload[0], ", ".join(args))
    return "%s(%s)" % (fn_name(name), ", ".join(args))


class Node:
    __slots__ = ("code", "t", "val")

    def __init__(self, code, t, val=None):
        self.code = code
        self.t = t
        self.val = val


class Lit(Node):
    pass


class Ref(Node):
    """Variable, global, fn name or object reference."""
    __slots__ = ("name", "obj")

    def __init__(self, code, t, name, obj=False):
        Node.__init__(self, code, t)
        self.name = name
        self.obj = obj


class Field(Node):
    """`base.field`; recv/fname are set only for typed owners."""
    __slots__ = ("recv", "fname", "ref", "raw")

    def __init__(self, code, t, recv=None, fname=None, ref=False, raw=None):
        Node.__init__(self, code, t)
        self.recv = recv
        self.fname = fname
        self.ref = ref
        self.raw = raw


class Index(Node):
    pass


class Call(Node):
    pass


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
        _, v = self.next()
        if v != val:
            self.err("expected %r, got %r" % (val, v))

    def err(self, msg):
        raise LintError("%s in %s: %s" % (
            msg, self.where, " ".join(t[1] for t in self.toks[:-1])))

    def terr(self, msg):
        raise TypeCheckError("%s in %s: %s" % (
            msg, self.where, " ".join(t[1] for t in self.toks[:-1])))

    def exprlist(self, expected=None):
        codes = []
        types = []
        while True:
            self.expected = expected
            node = self.expr()
            self.expected = None
            codes.append(node.code)
            types.append(node.t)
            if not self.accept(","):
                break
        return ", ".join(codes), types

    def check_arity(self, name, plist, variadic, n):
        try:
            check_arity(name, plist, variadic, n)
        except LintError as e:
            self.terr(str(e))

    def check(self, t, exp, code):
        if type_ok(self.ctx, t, exp):
            return
        self.terr("expected %s, got %s: %s" % (exp, t, code))

    def check_fn_ref(self, name, actual, expected):
        """Check a `&name` signature against an expected fn type."""
        expected = base(expected) or ""
        if expected == "fn" or actual == "fn":
            return
        act, exp = fn_type_parts(actual), fn_type_parts(expected)
        if act is None or exp is None:
            return
        aps, aret = act
        eps, eret = exp
        n = len([p for p in aps if p != "..."])
        if n > len(eps):
            self.terr("fn %s: callback takes %d parameter(s), expected %d"
                      % (name, n, len(eps)))
        for i, ap in enumerate(aps[:len(eps)]):
            if not type_ok(self.ctx, eps[i], ap):
                self.terr("fn %s: callback parameter %d is %s, but %s is "
                          "passed" % (name, i + 1, ap, eps[i]))
        if eret is not None and not type_ok(self.ctx, aret or "any", eret):
            self.terr("fn %s: callback returns %s, expected %s"
                      % (name, aret or "any", eret))

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
            self.terr("unknown object %r (expected obj)" % val)
        if exp == "event":
            if val not in self.ctx.event_names:
                self.terr("unknown event %r" % val)
            return tok
        if exp in self.ctx.types:
            msg = type_value_error(self.ctx, exp, val)
            if msg:
                self.terr(msg)
            return tok
        if exp == "num":
            self.terr("expected num, got str")
        if exp == "bool":
            self.terr("expected bool, got str")
        return tok

    def arglist(self, expected_list):
        if self.peek()[0] == "str":
            tok = self.next()
            exp = expected_list[0] if expected_list else None
            return [self.str_arg(tok[1], exp)], 1
        self.expect("(")
        codes = []
        n = 0
        if not self.accept(")"):
            while True:
                exp = (expected_list[n]
                       if expected_list and n < len(expected_list) else None)
                self.expected = exp
                node = self.expr()
                self.expected = None
                self.check(node.t, exp, node.code)
                codes.append(node.code)
                n += 1
                if not self.accept(","):
                    break
            self.expect(")")
        return codes, n

    def call(self, name):
        if name == "_":
            if self.peek()[0] == "str":
                self.err("_'...' is not allowed; use a bare name, #tag "
                         "or quoted name")
            codes, _ = self.arglist(None)
            return codes, "obj"
        if name in self.ctx.funcs or name in self.env:
            codes, _ = self.arglist(None)
            return codes, "any"
        self.err("unknown function %r (declare fn %s)" % (name, name))

    def primary(self):
        kind, val = self.next()
        if kind == "num":
            return Lit(val, "num")
        if kind == "str":
            if self.expected == "obj":
                self.terr("strings are not objects; use a bare name (%r)"
                          % self.strval(val))
            if self.expected == "event":
                self.err("event names are bare, not quoted (%r)"
                         % self.strval(val))
            if self.expected in self.ctx.types:
                msg = type_value_error(self.ctx, self.expected,
                                       self.strval(val))
                if msg:
                    self.terr(msg)
            return Lit(val, "str", val=self.strval(val))
        if kind == "op" and val == "...":
            self.err("... is not allowed in logic; use |lua for varargs")
        if kind == "name":
            if val in ("nil", "true", "false"):
                return Lit(val, ("bool" if val != "nil" else "nil"))
            if val in S.KEYWORDS:
                if val == "function":
                    self.err("anonymous functions are not allowed (use |lua)")
                self.err("unexpected keyword %r" % val)
            node = self.name_ref(val, funcs=True)
            if node is not None:
                return node
            if self.expected == "event" and val in self.ctx.event_names:
                return Lit("'%s'" % val, "event", val=val)
            if self.expected == "event":
                self.err("unknown event %r" % val)
            if (self.expected in self.ctx.types
                    and re.fullmatch(r"~?[A-Za-z_][\w-]*", val)):
                msg = type_value_error(self.ctx, self.expected, val)
                if msg:
                    self.terr(msg)
                return Lit(lua_str(val), "str", val=val)
            if val in self.ctx.event_names:
                return Lit("'%s'" % val, "event", val=val)
            owners = self.ctx.enum_values.get(val)
            if owners:
                if len(owners) > 1:
                    self.terr("ambiguous value %r (types: %s)"
                              % (val, ", ".join(sorted(owners))))
                return Lit(lua_str(val), next(iter(owners)), val=val)
            self.err("unknown name %r" % val)
        if kind == "op" and val == "(":
            self.expected = None
            node = self.expr()
            self.expect(")")
            return Node("(%s)" % node.code, node.t)
        if kind == "op" and val == "{":
            self.err("table constructors are not allowed in logic "
                     "(wrap it in fn)")
        self.err("unexpected %r" % val)

    def unary(self):
        _k, v = self.peek()
        if v == "not":
            self.next()
            node = self.unary()
            return Node("not %s" % node.code, "bool")
        if v == "-":
            self.next()
            node = self.unary()
            return Node("-%s" % node.code, "num")
        if v == "#":
            nk, nv = self.peek(1)
            if nk == "name" and ("#" + nv) in self.ctx.ids:
                self.next()
                self.next()
                return self.postfix(Ref("_'#%s'" % nv, "obj", "#" + nv,
                                        obj=True))
            self.err("# is only for declared #tags; the DSL has no tables "
                     "(wrap the length in a fn)")
        if v == "&":
            self.next()
            nk, nv = self.next()
            if nk != "name":
                self.err("expected fn name after &")
            if nv in self.ctx.inline:
                self.err("inline fn %s cannot be used as a value" % nv)
            if nv in self.ctx.fn_sigs:
                plist, ret, variadic = self.ctx.fn_sigs[nv]
                sig, code = canon_fn_sig(plist, ret, variadic), fn_name(nv)
            elif nv in self.ctx.funcs:
                sig, code = "fn", nv
            else:
                self.err("unknown fn %r in &-reference" % nv)
            if self.expected:
                self.check_fn_ref(nv, sig, self.expected)
            return Node(code, sig)
        return self.postfix(self.primary())

    def or_expr(self):
        return self.bin_expr(self.and_expr, ("or",), "any")

    def and_expr(self):
        return self.bin_expr(self.cmp_expr, ("and",), "any")

    def cmp_expr(self):
        node = self.concat_expr()
        while self.peek()[1] in ("==", "~=", "<", ">", "<=", ">=", "^"):
            op = self.next()[1]
            if op == "^":
                self.err("^ is forbidden; compare objects with ==")
            exp = None
            if op in ("==", "~="):
                base_t = node.t[:-1] if node.t.endswith("?") else node.t
                if base_t in self.ctx.types:
                    exp = base_t
                elif base_t == "event":
                    exp = "event"
            self.expected = exp
            rhs = self.concat_expr()
            self.expected = None
            if op in ("<", ">", "<=", ">="):
                self.check(node.t, "num", node.code)
                self.check(rhs.t, "num", rhs.code)
            node = Node("%s %s %s" % (node.code, op, rhs.code), "bool")
        return node

    def bin_expr(self, sub, ops, t, check_num=False):
        node = sub()
        while self.peek()[1] in ops:
            op = self.next()[1]
            rhs = sub()
            if check_num:
                self.check(node.t, "num", node.code)
                self.check(rhs.t, "num", rhs.code)
            node = Node("%s %s %s" % (node.code, op, rhs.code), t)
        return node

    def concat_expr(self):
        return self.bin_expr(self.add_expr, ("..",), "str")

    def add_expr(self):
        return self.bin_expr(self.mul_expr, ("+", "-"), "num", check_num=True)

    def mul_expr(self):
        return self.bin_expr(self.unary, ("*", "/", "%", "//"), "num",
                             check_num=True)

    def expr(self):
        return self.or_expr()

    def owner_ref(self, node):
        """`s` bound to obj or a class type (owner-typed field access)."""
        if not (isinstance(node, Ref) and not node.obj and node.name == "s"):
            return False
        st = self.env.get("s")
        return st == "obj" or st in self.ctx.classes

    def name_ref(self, name, zero_call=False, funcs=False):
        """Shared bare-name fallback: env, object, fn, game func, global.

        `zero_call` (method tail args) turns a no-arg fn into a call and
        leaves fns with parameters unresolved; `funcs` (primary) also
        resolves game `|lua` functions to their plain name.
        """
        if name in self.env:
            return Ref(name, self.env[name], name)
        if name in self.ctx.ids:
            return Ref("_'%s'" % name, "obj", name, obj=True)
        if name in self.ctx.fn_sigs:
            plist, ret, _v = self.ctx.fn_sigs[name]
            if not zero_call:
                return Ref(fn_name(name), "fn", name)
            if not plist:
                return Call(fn_call(self.ctx, name, []), ret)
        if funcs and name in self.ctx.funcs:
            return Ref(name, "fn", name)
        if name in self.ctx.vars:
            return Ref(name, self.ctx.global_types.get(name, "any"), name)
        return None

    def autocall(self, node):
        if (isinstance(node, Ref) and not node.obj
                and node.name in self.ctx.fn_sigs
                and not self.ctx.fn_sigs[node.name][0]):
            node = Call(fn_call(self.ctx, node.name, []),
                        self.ctx.fn_sigs[node.name][1])
        return node

    def postfix(self, node):
        while True:
            k, v = self.peek()
            if not (k == "str" or (k == "op" and v == "(")):
                node = self.autocall(node)
            if k == "op" and v == ".":
                node = self.postfix_dot(node)
            elif k == "op" and v == "[":
                node = self.postfix_index(node)
            elif k == "op" and v == ":":
                node = self.postfix_method(node)
            elif (isinstance(node, Ref) and not node.obj
                  and ((k == "name" and v not in S.KEYWORDS)
                       or (k == "op" and v in ("#", "-"))
                       or k == "num")):
                node = self.postfix_bare_call(node)
            elif k == "str" or (k == "op" and v == "("):
                node = self.postfix_arg_call(node)
            else:
                return node

    def postfix_dot(self, node):
        self.next()
        nk, nv = self.next()
        if nk != "name":
            self.err("expected field name")
        if node.t == "str":
            self.terr("strings are not objects; use a bare name (%r)"
                      % (node.val,))
        if node.t == "obj?":
            self.check(node.t, "obj", node.code)
        recv = None
        if isinstance(node, Ref) and node.obj:
            recv = node.name
        elif self.owner_ref(node) and self.ctx.current_owner:
            recv = self.ctx.current_owner
        raw = "%s.%s" % (node.code, nv)
        info = (self.ctx.fields.get(recv, {}).get(nv)
                if recv is not None else None)
        t = info[0] if info else "any"
        if info and info[1]:
            return Field("_(%s)" % raw, t, recv=recv, fname=nv,
                         ref=True, raw=raw)
        return Field(raw, t, recv=recv if info else None,
                     fname=nv if info else None)

    def postfix_index(self, node):
        self.next()
        if node.t == "obj?":
            self.check(node.t, "obj", node.code)
        self.expected = None
        idx = self.expr()
        self.expect("]")
        return Index("%s[%s]" % (node.code, idx.code), "any")

    def postfix_method(self, node):
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
        if node.t == "str":
            self.err("strings are not objects; use a bare name (%r)"
                     % (node.val,))
        self.check(node.t, plist[0][1], node.code)
        nk, nv2 = self.peek()
        if (not variadic and len(plist) == 1
                and not (nk == "str"
                         or (nk == "op" and nv2 == "("))):
            return Call(fn_call(self.ctx, nv, [node.code]), ret)
        if (not variadic and len(plist) == 2
                and self.peek()[0] == "name"
                and self.peek()[1] not in S.KEYWORDS
                and self.peek()[1] not in ("nil", "true", "false")):
            nm = self.next()[1]
            pt = plist[1][1]
            if pt == "str":
                arg = Lit(lua_str(nm), "str", nm)
            elif pt in self.ctx.types:
                msg = type_value_error(self.ctx, pt, nm)
                if msg:
                    self.terr(msg)
                arg = Lit(lua_str(nm), "str", nm)
            elif pt == "event" and nm in self.ctx.event_names:
                arg = Lit("'%s'" % nm, "event", nm)
            else:
                arg = self.name_ref(nm, zero_call=True)
                if arg is None:
                    self.err("unknown name %r" % nm)
            self.check(arg.t, pt, arg.code)
            return Call(fn_call(self.ctx, nv, [node.code, arg.code]), ret)
        codes, n = self.arglist([pt for _pn, pt in plist[1:]])
        self.check_arity(nv, plist[1:], variadic, n)
        return Call(fn_call(self.ctx, nv, [node.code] + codes), ret)

    def postfix_bare_call(self, node):
        name = node.name
        exp = None
        rt = "any"
        variadic = False
        if name in self.ctx.fn_sigs:
            plist, rt, variadic = self.ctx.fn_sigs[name]
            if not plist:
                self.err("fn %s takes no arguments" % name)
            self.check_arity(name, plist, variadic, 1)
            exp = plist[0][1]
        save = self.i
        self.expected = exp
        if exp == "str" or variadic:
            arg = self.expr()
        else:
            arg = self.unary()
            if not type_ok(self.ctx, arg.t, exp):
                self.i = save
                self.expected = exp
                arg = self.expr()
        self.expected = None
        self.check(arg.t, exp, arg.code)
        return Call(fn_call(self.ctx, name, [arg.code]), rt)

    def postfix_arg_call(self, node):
        if isinstance(node, Ref) and not node.obj:
            name = node.name
            ft = fn_type_parts(node.t) if node.t else None
            if ft is not None:
                params, ret = ft
                codes, n = self.arglist(params)
                if n != len(params):
                    self.err("fn %s expects %d argument(s), got %d"
                             % (name, len(params), n))
                return Call("%s(%s)" % (node.code, ", ".join(codes)),
                            ret or "any")
            if name in self.ctx.fn_sigs:
                plist, rt, variadic = self.ctx.fn_sigs[name]
                codes, n = self.arglist([pt for _pn, pt in plist])
                self.check_arity(name, plist, variadic, n)
                return Call(fn_call(self.ctx, name, codes), rt)
            codes, rt = self.call(name)
            return Call("%s(%s)" % (node.code, ", ".join(codes)), rt)
        self.err("call of field/expression is not allowed in "
                 "logic (wrap it in fn)")

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
        if not expr_like(rest, env, ctx):
            return fn_call(ctx, name, [lua_str(rest)]), ["str"]
    elif not variadic and plist[0][1] != "str":
        return None
    elif not expr_like(rest, env, ctx):
        return fn_call(ctx, name, [lua_str(rest)]), ["str"]
    try:
        code, types = transpile_exprlist(
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
            raise TypeCheckError("fn %s: argument %s expects %s, got %s"
                                 % (name, pn, pt, t))
    return fn_call(ctx, name, [code]), [ret]

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

def _stmt_local(p, env):
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
            node = p.expr()
            p.expected = None
            codes.append(node.code)
            if idx < len(types):
                types[idx] = node.t
            idx += 1
            if not p.accept(","):
                break
        code = "local %s = %s" % (", ".join(names), ", ".join(codes))
    else:
        code = "local " + ", ".join(names)
    if p.peek()[0] != "eof":
        p.err("unexpected %r" % p.peek()[1])
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


def _stmt_assign(p, lhs, op, env, where, ctx):
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
    if p.peek()[0] != "eof":
        p.err("unexpected %r" % p.peek()[1])
    if isinstance(lhs, Ref) and not lhs.obj and lhs.name in env and types:
        old, new = env[lhs.name], types[0]
        if old == "any":
            env[lhs.name] = new
        elif new != "any" and not type_ok(ctx, new, old):
            raise LintError("%s: %s (%s) cannot take %s"
                            % (where, lhs.name, old, new))
    if (isinstance(lhs, Field) and lhs.recv in ctx.fields
            and lhs.fname in ctx.fields[lhs.recv] and types):
        old = ctx.fields[lhs.recv][lhs.fname][0]
        new = types[0]
        if old != "any" and new != "any" and not type_ok(ctx, new, old):
            raise LintError("%s: %s.%s (%s) cannot take %s"
                            % (where, lhs.recv, lhs.fname, old, new))
    lhs_code = lhs.raw if (isinstance(lhs, Field) and lhs.ref) else lhs.code
    if op == "=":
        return "%s = %s" % (lhs_code, ", ".join(codes))
    sign = "+" if op == "+=" else "-"
    return "%s = %s %s (%s)" % (lhs_code, lhs_code, sign, ", ".join(codes))


def transpile_stmt(text, env, where, ctx):
    s = text.strip()
    if s in ctx.fn_sigs and not ctx.fn_sigs[s][0]:
        return fn_call(ctx, s, [])
    raw = no_paren_call(text, env, where, ctx)
    if raw is not None:
        return raw[0]
    p = ExprEmit(lex_lua(text), env, where, ctx)
    kind, val = p.peek()
    if kind == "name" and val == "local":
        return _stmt_local(p, env)
    if kind == "name" and val == "break":
        p.next()
        if p.peek()[0] != "eof":
            p.err("unexpected %r" % p.peek()[1])
        return "break"
    p.expected = None
    lhs = p.expr()
    op = _stmt_op(p)
    if op is not None:
        return _stmt_assign(p, lhs, op, env, where, ctx)
    if p.peek()[0] != "eof":
        p.err("unexpected %r" % p.peek()[1])
    if isinstance(lhs, Ref) and not lhs.obj and lhs.name in ctx.fn_sigs:
        p.err("fn %s must be called with ()" % lhs.name)
    if not isinstance(lhs, (Call, Field, Index)) \
            and not (isinstance(lhs, Ref) and not lhs.obj):
        p.err("unsupported statement")
    return lhs.code

def transpile_for(header, env, where, ctx):
    if re.search(r"\bin\b", header):
        names, iterable = re.split(r"\bin\b", header, 1)
        vars_ = [v.strip() for v in names.split(",") if v.strip()]
        for v in vars_:
            if not re.fullmatch(r"[^\W\d]\w*", v, re.UNICODE):
                raise LintError("bad loop variable %r in %s" % (v, where))
        code, _ = transpile_exprlist(iterable, env, where, None, ctx)
        return ("%s in %s" % (", ".join(vars_), code),
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
    return ("%s = %s" % (m.group(1), ", ".join(codes)),
            {m.group(1): "num"})

def expr_like(s, env, ctx):
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
