"""The expression parser of the logic (`|`) language: the node classes
and `ExprEmit`."""
import re

from . import state as S
from .common import *
from .typing import (base, canon_fn_sig, fn_type_parts, tbl_inner, type_ok,
                     type_value_error, union_parts)
from . import messages as M


def min_args(plist):
    """Number of required leading parameters (optional ones are trailing)."""
    return sum(1 for _pn, pt in plist
               if not (pt == "nil" or pt.endswith("?")))


def check_arity(name, plist, variadic, n):
    mn = min_args(plist)
    if variadic:
        if n < mn:
            raise LintError(M.FN_EXPECTS_AT_LEAST_ARGUMENT
                            % (name, mn, n))
    elif mn == len(plist):
        if n != len(plist):
            raise LintError(M.FN_ARGUMENT_COUNT
                            % (name, len(plist), n))
    elif not mn <= n <= len(plist):
        raise LintError(M.FN_ARGUMENT_RANGE
                        % (name, mn, len(plist), n))


def fn_name(name):
    return "fn_" + name


_SIMPLE_ARG = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|'[^']*'")

# the arithmetic and string levels of the expression parser: operators,
# the result type and whether both operands must be numbers
BIN_LEVELS = (
    (("..",), "str", False),
    (("+", "-"), "num", True),
    (("*", "/", "%", "//"), "num", True),
)

# the prefix operators: the code format and the result type
UNARY_OPS = {
    "not": ("not %s", "bool"),
    "-": ("-%s", "num"),
}

# the scalar expected types that never accept a quoted string
STR_ARG_ERRORS = {
    "num": "expected num, got str",
    "bool": "expected bool, got str",
}

# the primary token kinds and the ExprEmit methods they use
PRIMARY_FORMS = {
    "num": "_primary_num",
    "str": "_primary_str",
    "name": "_primary_name",
    "op": "_primary_op",
}

# the postfix operators and the ExprEmit methods they use
POSTFIX_OPS = {
    ".": "postfix_dot",
    "[": "postfix_index",
    ":": "postfix_method",
}

# the expected types with their own string-value handling
STR_ARG_FORMS = {
    "obj": "_str_arg_obj",
    "event": "_str_arg_event",
}


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
    if not desc:
        return "%s(%s)" % (fn_name(name), ", ".join(args))
    kind, payload = desc
    if kind == "wrap":
        return _wrap_params(payload[1], payload[0], args)
    if kind == "expr":
        return "(%s)" % _wrap_params(payload[1], payload[0], args)
    if kind == "meth":
        return "%s:%s(%s)" % (args[0], payload[0], ", ".join(args[1:]))
    return "%s(%s)" % (payload[0], ", ".join(args))


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
        self.code = code
        self.t = t
        self.val = None
        self.name = name
        self.obj = obj


class Field(Node):
    """`base.field`; recv/fname are set only for typed owners."""
    __slots__ = ("recv", "fname", "ref", "raw")

    def __init__(self, code, t, recv=None, fname=None, ref=False, raw=None):
        self.code = code
        self.t = t
        self.val = None
        self.recv = recv
        self.fname = fname
        self.ref = ref
        self.raw = raw


class Index(Node):
    pass


class Call(Node):
    pass


def _event_lit(val):
    return Lit("'%s'" % val, "event", val=val)


def _arg_call(kind, val):
    """A token that starts a call argument list (`"str"` or `(`)."""
    return kind == "str" or (kind == "op" and val == "(")


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
            self.err(M.EXPECTED_TOKEN % (val, v))

    def expect_eof(self):
        if self.peek()[0] != "eof":
            self.err(M.UNEXPECTED % self.peek()[1])

    def err(self, msg):
        raise LintError(M.IN_MESSAGE % (
            msg, self.where, " ".join(t[1] for t in self.toks[:-1])))

    def terr(self, msg):
        raise TypeCheckError(M.IN_MESSAGE % (
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
        self.terr(M.EXPECTED_GOT_CODE % (exp, t, code))

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
            self.terr(M.CALLBACK_PARAM_COUNT
                      % (name, n, len(eps)))
        for i, ap in enumerate(aps[:len(eps)]):
            if not type_ok(self.ctx, eps[i], ap):
                self.terr(M.CALLBACK_PARAM_TYPE % (name, i + 1, ap, eps[i]))
        if eret is not None and not type_ok(self.ctx, aret or "any", eret):
            self.terr(M.CALLBACK_RETURN
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
        alts = union_parts(exp) if exp else None
        if alts is not None:
            return self._union_str_arg(tok, exp, val, alts)
        return self._scalar_str_arg(tok, exp, val)

    def _union_str_arg(self, tok, exp, val, alts):
        if "str" in alts or "any" in alts:
            return tok
        for alt in alts:
            if alt in self.ctx.types:
                if not type_value_error(self.ctx, alt, val):
                    return tok
            elif alt == "event" and val in self.ctx.event_names:
                return tok
            elif alt == "obj" and val in self.ctx.ids:
                return "_'%s'" % val
        self.terr(M.EXPECTED_GOT_STR_VAL % (exp, val))

    def _str_arg_obj(self, _tok, val):
        if val in self.ctx.ids:
            return "_'%s'" % val
        self.terr(M.UNKNOWN_OBJECT_EXPECTED_OBJ % val)

    def _str_arg_event(self, tok, val):
        if val not in self.ctx.event_names:
            self.terr(M.UNKNOWN_EVENT_NAMED % val)
        return tok

    def _scalar_str_arg(self, tok, exp, val):
        handler = STR_ARG_FORMS.get(exp)
        if handler is not None:
            return getattr(self, handler)(tok, val)
        if exp in self.ctx.types:
            msg = type_value_error(self.ctx, exp, val)
            if msg:
                self.terr(msg)
            return tok
        err = STR_ARG_ERRORS.get(exp)
        if err is not None:
            self.terr(err)
        return tok

    def _str_arglist(self, expected_list):
        tok = self.next()
        exp = expected_list[0] if expected_list else None
        return [self.str_arg(tok[1], exp)], 1

    def arglist(self, expected_list):
        if self.peek()[0] == "str":
            return self._str_arglist(expected_list)
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

    def _call_args(self):
        codes, _n = self.arglist(None)
        return codes

    def call(self, name):
        if name == "_":
            if self.peek()[0] == "str":
                self.err(M.UNDERSCORE_QUOTED)
            return self._call_args(), "obj"
        if name in self.ctx.funcs or name in self.env:
            return self._call_args(), "any"
        self.err(M.UNKNOWN_FUNCTION % (name, name))

    def primary(self):
        kind, val = self.next()
        handler = PRIMARY_FORMS.get(kind)
        if handler is None:
            self.err(M.UNEXPECTED % val)
        return getattr(self, handler)(val)

    def _primary_num(self, val):
        return Lit(val, "num")

    def _primary_op(self, val):
        if val == "...":
            self.err(M.VARARGS_NOT_IN_LOGIC)
        if val == "(":
            return self._primary_paren()
        if val == "{":
            return self.list_literal()
        self.err(M.UNEXPECTED % val)

    def _primary_str(self, val):
        if self.expected == "obj":
            self.terr(M.STRINGS_NOT_OBJECTS
                      % self.strval(val))
        if self.expected == "event":
            self.err(M.EVENT_NAMES_BARE
                     % self.strval(val))
        if self.expected in self.ctx.types:
            msg = type_value_error(self.ctx, self.expected, self.strval(val))
            if msg:
                self.terr(msg)
        return Lit(val, "str", val=self.strval(val))

    def _primary_paren(self):
        self.expected = None
        node = self.expr()
        self.expect(")")
        return Node("(%s)" % node.code, node.t)

    def _primary_name(self, val):
        if val in ("nil", "true", "false"):
            return Lit(val, ("bool" if val != "nil" else "nil"))
        if val in S.KEYWORDS:
            if val == "function":
                self.err(M.ANONYMOUS_FN)
            self.err(M.UNEXPECTED_KEYWORD % val)
        node = self.name_ref(val, funcs=True)
        if node is not None:
            return node
        if self.expected == "event":
            return self._primary_event(val)
        if (self.expected in self.ctx.types
                and re.fullmatch(r"~?[A-Za-z_][\w-]*", val)):
            msg = type_value_error(self.ctx, self.expected, val)
            if msg:
                self.terr(msg)
            return Lit(lua_str(val), "str", val=val)
        if val in self.ctx.event_names:
            return _event_lit(val)
        owners = self.ctx.enum_values.get(val)
        if owners:
            return self._primary_enum(val, owners)
        self.err(M.UNKNOWN_NAME % val)

    def _primary_enum(self, val, owners):
        if len(owners) > 1:
            self.terr(M.AMBIGUOUS_VALUE_TYPES
                      % (val, ", ".join(sorted(owners))))
        return Lit(lua_str(val), next(iter(owners)), val=val)

    def _primary_event(self, val):
        if val in self.ctx.event_names:
            return _event_lit(val)
        self.err(M.UNKNOWN_EVENT_NAMED % val)

    def _list_elem(self):
        """Element type expected from `self.expected` (`tbl[T]`/`tbl`)."""
        exp = base(self.expected) if self.expected else None
        if not exp:
            return None
        for a in (union_parts(exp) or [exp]):
            inner = tbl_inner(a)
            if inner is not None:
                return inner
            if a == "tbl":
                return "any"
        return None

    def _list_num_enum(self, node, elem):
        """Retype a numeric literal declared as an enum value (`2` in gram)."""
        if not (elem and node.t == "num"
                and re.fullmatch(r"\d+(\.\d+)?", node.code or "")):
            return
        for a in (union_parts(elem) or [elem]):
            td = self.ctx.types.get(a)
            if td is not None and node.code in td["values"]:
                node.t = a
                return

    def _list_item(self, elem):
        self.expected = elem if elem else None
        node = self.expr()
        self.expected = None
        self._list_num_enum(node, elem)
        if elem and elem != "any":
            self.check(node.t, elem, node.code)
        return node

    def _list_type(self, types, elem):
        if types:
            return "tbl[%s]" % "|".join(sorted(types))
        if elem and elem != "any":
            return "tbl[%s]" % elem
        return "tbl" if elem == "any" else "tbl[]"

    def list_literal(self):
        """`{ e1, ... }` -> Lua table, type `tbl[elem types]`."""
        elem = self._list_elem()
        codes, types = [], []
        if not self.accept("}"):
            while True:
                node = self._list_item(elem)
                codes.append(node.code)
                if node.t not in types:
                    types.append(node.t)
                if not self.accept(","):
                    break
            self.expect("}")
        code = "({ %s })" % ", ".join(codes) if codes else "({})"
        return Node(code, self._list_type(types, elem))

    def _unary_op(self, fmt, t):
        self.next()
        node = self.unary()
        return Node(fmt % node.code, t)

    def unary(self):
        _k, v = self.peek()
        if v == "#":
            return self._unary_tag()
        if v == "&":
            return self._unary_fn_ref()
        spec = UNARY_OPS.get(v)
        if spec is None:
            return self.postfix(self.primary())
        return self._unary_op(spec[0], spec[1])

    def _unary_tag(self):
        nk, nv = self.peek(1)
        if nk == "name" and ("#" + nv) in self.ctx.ids:
            self.next()
            self.next()
            return self.postfix(Ref("_'#%s'" % nv, "obj", "#" + nv,
                                    obj=True))
        self.err(M.HASH_TAG_ONLY)

    def _fn_ref_parts(self, nv):
        if nv in self.ctx.fn_sigs:
            plist, ret, variadic = self.ctx.fn_sigs[nv]
            return canon_fn_sig(plist, ret, variadic), fn_name(nv)
        if nv in self.ctx.funcs:
            return "fn", nv
        self.err(M.UNKNOWN_FN_REF % nv)

    def _unary_fn_ref(self):
        self.next()
        nk, nv = self.next()
        if nk != "name":
            self.err(M.EXPECTED_FN_NAME)
        if nv in self.ctx.inline:
            self.err(M.INLINE_FN_AS_VALUE % nv)
        sig, code = self._fn_ref_parts(nv)
        if self.expected:
            self.check_fn_ref(nv, sig, self.expected)
        return Node(code, sig)

    def or_expr(self):
        return self.bin_expr(self.and_expr, ("or",), "any")

    def and_expr(self):
        return self.bin_expr(self.cmp_expr, ("and",), "any")

    def _cmp_expected(self, node, op):
        if op not in ("==", "~="):
            return None
        base_t = node.t[:-1] if node.t.endswith("?") else node.t
        if base_t in self.ctx.types:
            return base_t
        if base_t == "event":
            return "event"
        return None

    def cmp_expr(self):
        node = self.concat_expr()
        while self.peek()[1] in ("==", "~=", "<", ">", "<=", ">=", "^"):
            op = self.next()[1]
            if op == "^":
                self.err(M.CARET_FORBIDDEN)
            self.expected = self._cmp_expected(node, op)
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
        ops, t, check = BIN_LEVELS[0]
        return self.bin_expr(self.add_expr, ops, t, check)

    def add_expr(self):
        ops, t, check = BIN_LEVELS[1]
        return self.bin_expr(self.mul_expr, ops, t, check)

    def mul_expr(self):
        ops, t, check = BIN_LEVELS[2]
        return self.bin_expr(self.unary, ops, t, check)

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

    def _is_bare_call(self, node, k, v):
        if not (isinstance(node, Ref) and not node.obj):
            return False
        if k == "name" and v not in S.KEYWORDS:
            return True
        if k == "op" and v in ("#", "-"):
            return True
        return k == "num"

    def _postfix_step(self, node, k, v):
        if k == "op":
            handler = POSTFIX_OPS.get(v)
            if handler is not None:
                return getattr(self, handler)(node), False
        if self._is_bare_call(node, k, v):
            return self.postfix_bare_call(node), False
        if _arg_call(k, v):
            return self.postfix_arg_call(node), False
        return node, True

    def postfix(self, node):
        while True:
            k, v = self.peek()
            if not _arg_call(k, v):
                node = self.autocall(node)
            node, done = self._postfix_step(node, k, v)
            if done:
                return node

    def postfix_dot(self, node):
        self.next()
        nk, nv = self.next()
        if nk != "name":
            self.err(M.EXPECTED_FIELD_NAME)
        if node.t == "str":
            self.terr(M.STRINGS_NOT_OBJECTS
                      % (node.val,))
        if node.t == "obj?":
            self.check(node.t, "obj", node.code)
        recv = self._dot_recv(node)
        raw = "%s.%s" % (node.code, nv)
        info = (self.ctx.fields.get(recv, {}).get(nv)
                if recv is not None else None)
        t = info[0] if info else "any"
        if info and info[1]:
            return Field("_(%s)" % raw, t, recv=recv, fname=nv,
                         ref=True, raw=raw)
        return Field(raw, t, recv=recv if info else None,
                     fname=nv if info else None)

    def _dot_recv(self, node):
        if isinstance(node, Ref) and node.obj:
            return node.name
        if self.owner_ref(node) and self.ctx.current_owner:
            return self.ctx.current_owner
        return None

    def postfix_index(self, node):
        self.next()
        if node.t == "obj?":
            self.check(node.t, "obj", node.code)
        bt = base(node.t) if node.t else None
        if node.t and node.t.endswith("?"):
            self.check(node.t, bt, node.code)
        self.expected = None
        idx = self.expr()
        self.expect("]")
        ti = tbl_inner(bt) if bt else None
        t = ti if ti else "any"
        return Index("%s[%s]" % (node.code, idx.code), t)

    def postfix_method(self, node):
        self.next()
        nk, nv = self.next()
        if nk != "name":
            self.err(M.EXPECTED_METHOD_NAME)
        if nv not in self.ctx.fn_sigs:
            self.err(M.METHOD_NOT_FN % nv)
        plist, ret, variadic = self.ctx.fn_sigs[nv]
        if not plist:
            self.err(M.FN_NO_RECEIVER % nv)
        if node.t == "str":
            self.err(M.STRINGS_NOT_OBJECTS
                     % (node.val,))
        self.check(node.t, plist[0][1], node.code)
        if self._method_bare(plist, variadic):
            return Call(fn_call(self.ctx, nv, [node.code]), ret)
        if self._method_tail(plist, variadic):
            return self._method_tail_call(node, nv, plist, ret)
        codes, n = self.arglist([pt for _pn, pt in plist[1:]])
        self.check_arity(nv, plist[1:], variadic, n)
        return Call(fn_call(self.ctx, nv, [node.code] + codes), ret)

    def _method_bare(self, plist, variadic):
        nk, nv2 = self.peek()
        return (not variadic and len(plist) == 1
                and not _arg_call(nk, nv2))

    def _method_tail(self, plist, variadic):
        if variadic or len(plist) != 2:
            return False
        nk, nv2 = self.peek()
        return (nk == "name" and nv2 not in S.KEYWORDS
                and nv2 not in ("nil", "true", "false"))

    def _tail_value(self, nm, pt):
        if pt == "str":
            return Lit(lua_str(nm), "str", nm)
        if pt in self.ctx.types:
            msg = type_value_error(self.ctx, pt, nm)
            if msg:
                self.terr(msg)
            return Lit(lua_str(nm), "str", nm)
        if pt == "event" and nm in self.ctx.event_names:
            return _event_lit(nm)
        arg = self.name_ref(nm, zero_call=True)
        if arg is None:
            self.err(M.UNKNOWN_NAME % nm)
        return arg

    def _method_tail_call(self, node, nv, plist, ret):
        nm = self.next()[1]
        pt = plist[1][1]
        arg = self._tail_value(nm, pt)
        self.check(arg.t, pt, arg.code)
        return Call(fn_call(self.ctx, nv, [node.code, arg.code]), ret)

    def _bare_sig(self, name):
        if name not in self.ctx.fn_sigs:
            return None, "any", False
        plist, rt, variadic = self.ctx.fn_sigs[name]
        if not plist:
            self.err(M.FN_NO_ARGUMENTS % name)
        self.check_arity(name, plist, variadic, 1)
        return plist[0][1], rt, variadic

    def _bare_typed_arg(self, exp, save):
        arg = self.unary()
        if type_ok(self.ctx, arg.t, exp):
            return arg
        self.i = save
        self.expected = exp
        return self.expr()

    def _bare_arg(self, exp, variadic):
        save = self.i
        self.expected = exp
        arg = (self.expr() if exp == "str" or variadic
               else self._bare_typed_arg(exp, save))
        self.expected = None
        return arg

    def postfix_bare_call(self, node):
        name = node.name
        exp, rt, variadic = self._bare_sig(name)
        arg = self._bare_arg(exp, variadic)
        self.check(arg.t, exp, arg.code)
        return Call(fn_call(self.ctx, name, [arg.code]), rt)

    def _typed_arg_call(self, node, name, ft):
        params, ret = ft
        codes, n = self.arglist(params)
        if n != len(params):
            self.err(M.FN_ARGUMENT_COUNT
                     % (name, len(params), n))
        return "%s(%s)" % (node.code, ", ".join(codes)), ret or "any"

    def _sig_arg_call(self, name):
        plist, rt, variadic = self.ctx.fn_sigs[name]
        codes, n = self.arglist([pt for _pn, pt in plist])
        self.check_arity(name, plist, variadic, n)
        return fn_call(self.ctx, name, codes), rt

    def _arg_call_parts(self, node, name):
        ft = fn_type_parts(node.t) if node.t else None
        if ft is not None:
            return self._typed_arg_call(node, name, ft)
        if name in self.ctx.fn_sigs:
            return self._sig_arg_call(name)
        codes, rt = self.call(name)
        return "%s(%s)" % (node.code, ", ".join(codes)), rt

    def postfix_arg_call(self, node):
        if not (isinstance(node, Ref) and not node.obj):
            self.err(M.CALL_FIELD_IN_LOGIC)
        code, ret = self._arg_call_parts(node, node.name)
        return Call(code, ret)
