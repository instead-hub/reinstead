#!/usr/bin/env python3
import os
import re
import sys
import textwrap

IND = "  "

EVENTS = {}
for _e in (
    "Walk Enter Exit Exam Search LookUnder Consult Open Close Unlock Lock Inv "
    "Take Drop PutOn Insert Remove ThrowAt Wear Disrobe SwitchOn SwitchOff Eat "
    "Taste Drink Push Pull Transfer Turn Wait Rub Sing Touch Give Show Burn "
    "Wake WakeOther Kiss Think Smell Listen Dig Cut Tear Tie Blow Attack Sleep "
    "Swim Fill Jump JumpOver WaveHands Wave Climb GetOff Buy Talk Tell Ask "
    "AskFor Answer Yes No Next Look Receive ThrownAt LetGo LetIn "
    "Any Default"
).split():
    EVENTS[_e] = _e

FIELD_PARAMS = {
    "daemon": "s", "description": "s", "dsc": "s", "title": "s", "inv": "s",
    "inside_dsc": "s", "init_dsc": "s", "dark_dsc": "s", "cant_go": "s, to",
    "onenter": "s, f", "onexit": "s, f",
}


class Error(Exception):
    pass


class Text:
    def __init__(self, s):
        self.s = s


class Lua:
    def __init__(self, s):
        self.s = s


class Logic:
    def __init__(self, stmts):
        self.stmts = stmts


class Bare:
    def __init__(self, s):
        self.s = s


class Num:
    def __init__(self, s):
        self.s = s


class Bool:
    def __init__(self, s):
        self.s = s


class Nil:
    pass


class Data:
    def __init__(self, s):
        self.s = s


class Raw:
    def __init__(self, s):
        self.s = s


class Block:
    def __init__(self):
        self.items = []

    def get(self, key):
        for k, v in self.items:
            if k == key:
                return v
        return None

    def all(self, key):
        return [v for k, v in self.items if k == key]


def parse_key(key):
    m = re.match(r"^(.*?)(?:\(([^)]*)\))?$", key)
    return m.group(1).strip(), m.group(2)


def split_key(text):
    depth = 0
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ":" and depth == 0:
            return text[:i], text[i + 1:]
        i += 1
    return None, None


def parse_error(line, msg):
    raise Error("line %d: %s" % (line, msg))


def strip_comment(s):
    out = []
    quote = None
    i = 0
    while i < len(s):
        c = s[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < len(s):
                out.append(s[i + 1])
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
            out.append(c)
        elif c == "#" and (i == 0 or s[i - 1] in " \t") and (
                i + 1 >= len(s) or s[i + 1] in " \t"):
            break
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def parse_string(s, line):
    quote = s[0]
    out = []
    i = 1
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "'": "'",
                        "\\": "\\"}.get(n, n))
            i += 2
            continue
        if c == quote:
            return "".join(out), i + 1
        out.append(c)
        i += 1
    parse_error(line, "unterminated string")


TEXT_KEYS = {
    "name", "version", "author", "info", "description", "dsc", "title",
    "inv", "inside_dsc", "init_dsc", "dark_dsc", "cant_go", "when_open",
    "when_closed", "when_on", "when_off", "text", "words",
    "ask", "reply", "say", "intro",
}

HANDLER_KEYS = ("on", "before", "after", "post")


def parse_scalar(s, line, textmode=False):
    s = s.strip()
    if s.startswith("`") and s.endswith("`") and len(s) > 1:
        return Raw(s[1:-1])
    if s.startswith(("'", '"')):
        val, _ = parse_string(s, line)
        return Text(val)
    if s in ("true", "false"):
        return Bool(s)
    if s == "nil":
        return Nil()
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return Num(s)
    return Text(s) if textmode else Bare(s)


def split_list(s):
    parts = []
    depth = 0
    quote = None
    cur = []
    for c in s:
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
            continue
        if c in "\"'":
            quote = c
            cur.append(c)
        elif c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def read_fence(lines, i, line_no):
    body = []
    while i < len(lines):
        raw, ind = lines[i]
        if raw.strip() == "~~~":
            return body, i + 1
        body.append((raw, ind, i + 1))
        i += 1
    parse_error(line_no, "unterminated fence ~~~")


def balanced_expr(text):
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
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
            i = j
            continue
        m = re.match(r"\[(=*)\[", text[i:]) if text.startswith("[[", i) else None
        if m:
            close = "]" + m.group(1) + "]"
            j = text.find(close, i + m.end())
            if j == -1:
                return False
            i = j + len(close)
            continue
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


def read_bracket(lines, i, first, line_no):
    text = first
    while not balanced_expr(text):
        i += 1
        if i >= len(lines):
            parse_error(line_no, "unterminated {...}")
        text += "\n" + lines[i][0]
    return Data(text), i + 1


def long_balanced(text):
    i = 0
    while i < len(text):
        if text[i] == "[":
            m = re.match(r"\[(=*)\[", text[i:])
            if m:
                close = "]" + m.group(1) + "]"
                j = text.find(close, i + m.end())
                if j == -1:
                    return False
                i = j + len(close)
                continue
        i += 1
    return True


def dedent_rest(text):
    lines = text.split("\n")
    if len(lines) < 2:
        return text
    rest = lines[1:]
    indents = [len(l) - len(l.lstrip()) for l in rest if l.strip()]
    m = min(indents) if indents else 0
    return lines[0] + "\n" + "\n".join(l[m:] for l in rest)


def parse_logic(lines, i, indent):
    stmts = []
    while i < len(lines):
        raw, ind, lno = lines[i]
        if not raw.strip():
            i += 1
            continue
        if ind < indent:
            break
        if ind > indent:
            parse_error(lno, "unexpected indent: %r" % raw)
        text = strip_comment(raw.strip())
        while not long_balanced(text) and i + 1 < len(lines):
            i += 1
            text += "\n" + lines[i][0]
        text = dedent_rest(text)
        if not text:
            i += 1
            continue
        if text == "stop":
            stmts.append(("return", None, lno))
            i += 1
            continue
        if text == "pass":
            stmts.append(("return", "false", lno))
            i += 1
            continue
        m = re.match(r"^return\b\s*(.*)$", text, re.S)
        if m:
            stmts.append(("return", m.group(1) or None, lno))
            i += 1
            continue
        m = re.match(r"^if\s+(.+):$", text, re.S)
        if m:
            branches = [(m.group(1).strip(), None)]
            else_body = None
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j >= len(lines) or lines[j][1] <= ind:
                parse_error(lno, "empty if")
            body, j = parse_logic(lines, j, lines[j][1])
            branches[0] = (branches[0][0], body)
            i = j
            while i < len(lines):
                raw2, ind2, _lno2 = lines[i]
                if not raw2.strip():
                    i += 1
                    continue
                t2 = strip_comment(raw2.strip())
                if ind2 == ind and t2.startswith("elseif "):
                    cond = t2[7:].rstrip(":").strip()
                    j = i + 1
                    while j < len(lines) and not lines[j][0].strip():
                        j += 1
                    if j >= len(lines) or lines[j][1] <= ind:
                        parse_error(lines[i][2], "empty elseif")
                    b2, j = parse_logic(lines, j, lines[j][1])
                    branches.append((cond, b2))
                    i = j
                elif ind2 == ind and t2 == "else:":
                    j = i + 1
                    while j < len(lines) and not lines[j][0].strip():
                        j += 1
                    if j >= len(lines) or lines[j][1] <= ind:
                        parse_error(lines[i][2], "empty else")
                    else_body, j = parse_logic(lines, j, lines[j][1])
                    i = j
                else:
                    break
            stmts.append(("if", branches, else_body, lno))
            continue
        m = re.match(r"^for\s+(.+):$", text, re.S)
        if m:
            header = dedent_rest(m.group(1).strip())
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j >= len(lines) or lines[j][1] <= ind:
                parse_error(lno, "empty for")
            body, j = parse_logic(lines, j, lines[j][1])
            stmts.append(("for", header, body, lno))
            i = j
            continue
        m = re.match(r"^set\s+(.+?)\s*(\+=|-=|=)\s*(.+)$", text, re.S)
        if m:
            stmts.append(("set", m.group(1).strip(), m.group(2),
                          m.group(3).strip(), lno))
            i += 1
            continue
        stmts.append(("stmt", text, lno))
        i += 1
    return stmts, i


IDS = set()


KEYWORDS = {
    "return", "not", "and", "or", "if", "elseif", "while", "until", "in",
    "then", "else", "do", "local", "function", "end", "break", "repeat",
}

VARS = set()
FUNCS = set()
EVENT_NAMES = set()
SRC_DIR = ""


class LintError(Error):
    pass


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
        raise LintError("bad character %r in ~~~do: %s" % (c, text))
    toks.append(("eof", ""))
    return toks


TYPES = {"obj", "str", "num", "bool", "any", "event"}

FN_SIGS = {}
GLOBAL_TYPES = {}
PARAM_TYPES = {
    "s": "obj", "w": "obj", "wh": "obj", "ev": "event", "to": "any",
    "f": "any", "load": "bool",
}
def check_arity(name, plist, variadic, n):
    if variadic:
        if n < len(plist):
            raise LintError("fn %s expects at least %d argument(s), got %d"
                            % (name, len(plist), n))
    elif n != len(plist):
        raise LintError("fn %s expects %d argument(s), got %d"
                        % (name, len(plist), n))


class ExprEmit:
    def __init__(self, toks, env, where):
        self.toks = toks
        self.i = 0
        self.env = env
        self.where = where
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
            if val in IDS:
                return "_'%s'" % val
            self.err("unknown object %r (expected obj)" % val)
        if exp == "event":
            if val not in EVENT_NAMES:
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
        if name in FN_SIGS:
            plist, ret, variadic = FN_SIGS[name]
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
        if name in FUNCS or name in self.env:
            args, _ = self.arglist(None)
            return args, "any"
        self.err("unknown function %r (declare fn %s)" % (name, name))

    def primary(self):
        kind, val = self.next()
        if kind == "num":
            return val, "num", "lit", None
        if kind == "str":
            if self.expected == "obj" and self.strval(val) in IDS:
                return "_'%s'" % self.strval(val), "obj", "objref", None
            if self.expected == "event":
                if self.strval(val) not in EVENT_NAMES:
                    self.err("unknown event %r" % self.strval(val))
                return val, "event", "lit", self.strval(val)
            return val, "str", "lit", self.strval(val)
        if kind == "op" and val == "...":
            return val, "any", "lit", None
        if kind == "name":
            if val in ("nil", "true", "false"):
                return val, "bool" if val != "nil" else "any", "lit", None
            if val in KEYWORDS:
                if val == "function":
                    self.err("anonymous functions are not allowed (use ~~~lua)")
                self.err("unexpected keyword %r" % val)
            if val in self.env:
                return val, self.env[val], "name", val
            if val in IDS:
                return "_'%s'" % val, "obj", "objref", None
            if val in FN_SIGS:
                return "fn_" + val, "fn", "name", val
            if val in FUNCS:
                return val, "fn", "name", val
            if val in VARS:
                return val, GLOBAL_TYPES.get(val, "any"), "name", val
            if self.expected == "event" and val in EVENT_NAMES:
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
            self.err("table constructors are not allowed in ~~~do "
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
            if nk == "name" and ("#" + nv) in IDS:
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
        if (kind == "name" and val in FN_SIGS
                and not FN_SIGS[val][0]):
            code = "%s()" % code
            t = FN_SIGS[val][1]
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
                if t == "str" and val in IDS:
                    code = "_'%s'" % val
                    t = "obj"
                    val = None
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
                if nv not in FN_SIGS:
                    self.err("method %r is not a fn (engine methods are "
                             "not allowed in ~~~do)" % nv)
                plist, ret, variadic = FN_SIGS[nv]
                if not plist:
                    self.err("fn %s takes no receiver" % nv)
                if t == "str" and val in IDS:
                    code = "_'%s'" % val
                    t = "obj"
                    val = None
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
                        and self.peek()[1] not in KEYWORDS
                        and self.peek()[1] not in ("nil", "true", "false")):
                    nm = self.next()[1]
                    pt = plist[1][1]
                    if pt == "str":
                        arg, at = lua_str(nm), "str"
                    elif pt == "event" and nm in EVENT_NAMES:
                        arg, at = "'%s'" % nm, "event"
                    elif nm in self.env:
                        arg, at = nm, self.env[nm]
                    elif nm in IDS:
                        arg, at = "_'%s'" % nm, "obj"
                    elif nm in FN_SIGS and not FN_SIGS[nm][0]:
                        arg, at = "fn_%s()" % nm, FN_SIGS[nm][1]
                    elif nm in VARS:
                        arg, at = nm, GLOBAL_TYPES.get(nm, "any")
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
            elif (k == "name" and kind == "name"
                  and v not in KEYWORDS
                  and v not in ("nil", "true", "false")):
                exp = None
                rt = "any"
                if val in FN_SIGS:
                    plist, rt, variadic = FN_SIGS[val]
                    if not plist:
                        self.err("fn %s takes no arguments" % val)
                    try:
                        check_arity(val, plist, variadic, 1)
                    except LintError as e:
                        self.err(str(e))
                    exp = plist[0][1]
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
                             "~~~do (wrap it in fn)")
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
    return bool(m and m.group(0) in KEYWORDS)


TOP_OPS = (" and ", " or ", " == ", " ~= ", " <= ", " >= ", " < ",
           " > ", " .. ", " + ", " - ", " * ", " / ", " % ", " ^ ")


def split_top_op(text):
    depth = 0
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            i += 1
            continue
        if c in "([{":
            depth += 1
            i += 1
            continue
        if c in ")]}":
            depth -= 1
            i += 1
            continue
        if depth == 0:
            for op in TOP_OPS:
                if text.startswith(op, i):
                    return text[:i], op.strip(), text[i + len(op):]
        i += 1
    return None


def no_paren_call(text, env, where):
    m = re.match(r"^([^\W\d]\w*)\s+([^(\s].*)$", text.strip(), re.S)
    if not m or m.group(1) not in FN_SIGS:
        return None
    name = m.group(1)
    plist, ret, variadic = FN_SIGS[name]
    rest = m.group(2).strip()
    if not rest or not (len(plist) == 1 or variadic):
        return None
    if not plist:
        if expr_cont(rest):
            return None
        if not say_expr_start(rest, env):
            return "fn_%s(%s)" % (name, lua_str(rest)), ["str"]
    elif plist[0][1] == "str" and not say_expr_start(rest, env):
        return "fn_%s(%s)" % (name, lua_str(rest)), ["str"]
    exp = plist[0][1] if len(plist) == 1 else None
    if len(plist) == 1 and exp != "str":
        cut = split_top_op(rest)
        if cut:
            head, op, after = cut
            code, types = transpile_exprlist(head, env, where, exp)
            check_arity(name, plist, variadic, len(types))
            for (pn, pt), t in zip(plist, types):
                if pt != "any" and t not in ("any", pt):
                    raise LintError("fn %s: argument %s expects %s, got %s"
                                    % (name, pn, pt, t))
            tcode, _ = transpile_exprlist(after, env, where)
            rtype = ("bool" if op in ("==", "~=", "<", ">", "<=", ">=", "^")
                     else "any")
            return ("fn_%s(%s) %s %s" % (name, code, op, tcode), [rtype])
    try:
        code, types = transpile_exprlist(rest, env, where, exp)
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


def transpile_exprlist(text, env, where, expected=None):
    raw = no_paren_call(text, env, where)
    if raw is not None:
        return raw
    p = ExprEmit(lex_lua(text), env, where)
    code, types = p.exprlist(expected)
    if p.peek()[0] != "eof":
        p.err("unexpected %r" % p.peek()[1])
    if expected and types:
        p.check(types[0], expected, code)
    return code, types


def transpile_stmt(text, env, where):
    s = text.strip()
    if s in FN_SIGS and not FN_SIGS[s][0]:
        return "fn_%s()" % s
    raw = no_paren_call(text, env, where)
    if raw is not None:
        return raw[0]
    p = ExprEmit(lex_lua(text), env, where)
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
    if lk == "name" and lv in FN_SIGS:
        p.err("fn %s must be called with ()" % lv)
    if lk not in ("name", "field", "call"):
        p.err("unsupported statement")
    return lhs


def transpile_for(header, env, where):
    if re.search(r"\bin\b", header):
        names, iterable = re.split(r"\bin\b", header, 1)
        vars_ = [v.strip() for v in names.split(",") if v.strip()]
        for v in vars_:
            if not re.fullmatch(r"[^\W\d]\w*", v, re.UNICODE):
                raise LintError("bad loop variable %r in %s" % (v, where))
        code, _ = transpile_exprlist(iterable, env, where)
        return ("for %s in %s" % (", ".join(vars_), code),
                {v: "any" for v in vars_})
    parts = split_list(header)
    m = re.match(r"^([^\W\d]\w*)\s*=\s*(.*)$", parts[0], re.UNICODE)
    if not m:
        raise LintError("bad for header in %s: %s" % (where, header))
    start, st = transpile_exprlist(m.group(2), env, where)
    if st and st[0] not in ("num", "any"):
        raise LintError("%s: for bound must be num, got %s" % (where, st[0]))
    codes = [start]
    for p in parts[1:]:
        c, ct = transpile_exprlist(p, env, where)
        if ct and ct[0] not in ("num", "any"):
            raise LintError("%s: for bound must be num, got %s"
                            % (where, ct[0]))
        codes.append(c)
    return ("for %s = %s" % (m.group(1), ", ".join(codes)),
            {m.group(1): "num"})


def emit_logic(stmts, indent, env=None, ret=None, ret_name=None):
    env = dict(env or {})
    out = []
    for st in stmts:
        kind = st[0]
        lno = st[-1] if isinstance(st[-1], int) else None
        where = ("~~~do:%d" % lno) if lno else "~~~do"
        if kind == "return":
            code = ""
            rtype = "nil"
            if st[1]:
                code, types = transpile_exprlist(st[1], env, where)
                rtype = types[0] if types else "any"
            if ret and ret != "any" and rtype not in ("any", ret):
                ctx = ("fn %s" % ret_name) if ret_name else "~~~do"
                raise LintError("%s: return type is %s, expected %s"
                                % (ctx, rtype, ret))
            out.append("%sreturn%s" % (indent, (" " + code) if code else ""))
        elif kind == "set":
            lcode, _ = transpile_exprlist(st[1], env, where)
            rcode, _ = transpile_exprlist(st[3], env, where)
            if st[2] == "=":
                out.append("%s%s = %s" % (indent, lcode, rcode))
            else:
                sign = "+" if st[2] == "+=" else "-"
                out.append("%s%s = %s %s (%s)"
                           % (indent, lcode, lcode, sign, rcode))
        elif kind == "stmt":
            out.append(indent + transpile_stmt(st[1], env, where))
        elif kind == "for":
            header, vars_ = transpile_for(st[1], env, where)
            out.append("%sfor %s do" % (indent, header))
            child = dict(env)
            child.update(vars_)
            out.extend(emit_logic(st[2], indent + IND, child, ret, ret_name))
            out.append(indent + "end")
        elif kind == "if":
            branches, else_body = st[1], st[2]
            for idx, (cond, body) in enumerate(branches):
                code, _ = transpile_exprlist(cond, env, where)
                out.append("%s%s %s then" % (
                    indent, "if" if idx == 0 else "elseif", code))
                out.extend(emit_logic(body, indent + IND, dict(env),
                                      ret, ret_name))
            if else_body is not None:
                out.append(indent + "else")
                out.extend(emit_logic(else_body, indent + IND, dict(env),
                                      ret, ret_name))
            out.append(indent + "end")
    return out


def say_expr_start(s, env):
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
    return (tok in env or tok in VARS or tok in IDS or tok in FN_SIGS
            or tok in FUNCS)


EXTRA_EVENTS = {}


def read_long(lines, i, first, line_no):
    opener = re.match(r"^\[(=*)\[", first)
    close = "]" + opener.group(1) + "]"
    content = first[opener.end():]
    if close in content:
        return Text(content[:content.index(close)]), i + 1
    body = [content] if content else [""]
    i += 1
    while i < len(lines):
        raw, ind = lines[i]
        if close in raw:
            body.append(raw[:raw.index(close)])
            first_line = body[0]
            rest = textwrap.dedent("\n".join(body[1:]))
            return Text(first_line + ("\n" + rest if rest else "")), i + 1
        body.append(raw)
        i += 1
    parse_error(line_no, "unterminated [[ string")


def fence_value(tag, lines, start, line_no):
    body, i = read_fence(lines, start, line_no)
    if tag == "~~~lua":
        return Lua(reindent("\n".join(raw for raw, _ind, _lno in body),
                            "")), i
    j = 0
    while j < len(body) and not body[j][0].strip():
        j += 1
    base = body[j][1] if j < len(body) else 0
    stmts, k = parse_logic(body, j, base)
    if k != len(body):
        parse_error(line_no, "trailing logic")
    return Logic(stmts), i


def parse_list(lines, i, indent):
    items = []
    while i < len(lines):
        raw, ind = lines[i]
        if not raw.strip():
            i += 1
            continue
        if ind < indent:
            break
        if ind > indent:
            parse_error(i + 1, "unexpected indent: %r" % raw)
        text = strip_comment(raw.strip())
        if not re.match(r"^-(\s|$)", text):
            break
        rest = text[1:].strip()
        if rest:
            items.append(parse_scalar(rest, i + 1, textmode=True))
            i += 1
        else:
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j < len(lines) and lines[j][1] > ind and re.match(
                    r"^-\s", lines[j][0].strip()):
                sub, i = parse_list(lines, j, lines[j][1])
                items.append(sub)
            else:
                parse_error(i + 1, "empty list item")
    return items, i


def pipe_value(lines, i, indent, tag):
    body = []
    j = i
    while j < len(lines):
        raw, ind = lines[j]
        if (raw.strip() and ind <= indent
                and long_balanced("\n".join(r for r, _i, _l in body))):
            break
        body.append((raw, ind, j + 1))
        j += 1
    while body and not body[-1][0].strip():
        body.pop()
    if tag == "|lua":
        return Lua(reindent("\n".join(r for r, _ind, _lno in body),
                            "")), j
    k = 0
    while k < len(body) and not body[k][0].strip():
        k += 1
    if k >= len(body):
        return Logic([]), j
    stmts, m = parse_logic(body, k, body[k][1])
    if m != len(body):
        parse_error(body[m][2], "trailing logic")
    return Logic(stmts), j


def parse_block(lines, i, indent, text_values=False):
    blk = Block()
    while i < len(lines):
        raw, ind = lines[i]
        if ind < indent:
            break
        if ind > indent:
            parse_error(i + 1, "unexpected indent: %r" % raw)
        text = strip_comment(raw.strip())
        if not text:
            i += 1
            continue
        key, rest = split_key(text)
        if key is None:
            parse_error(i + 1, "expected 'key: value'")
        key, rest = key.strip(), rest.strip()
        line_no = i + 1
        if rest == "":
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j < len(lines) and lines[j][0].strip() in (
                    "~~~lua", "~~~do"):
                tag = lines[j][0].strip()
                val, i = fence_value(tag, lines, j + 1, line_no)
                blk.items.append((key, val))
            elif j < len(lines) and re.match(
                    r"^-\s", lines[j][0].strip()) and lines[j][1] > indent:
                child, i = parse_list(lines, j, lines[j][1])
                blk.items.append((key, child))
            elif j < len(lines) and lines[j][1] > indent:
                child, i = parse_block(lines, j, lines[j][1],
                                       key in HANDLER_KEYS)
                blk.items.append((key, child))
            else:
                blk.items.append((key, Block()))
                i += 1
        elif rest in ("~~~lua", "~~~do"):
            val, i = fence_value(rest, lines, i + 1, line_no)
            blk.items.append((key, val))
        elif rest in ("|", "|lua"):
            val, i = pipe_value(lines, i + 1, indent, rest)
            blk.items.append((key, val))
        elif rest.startswith("[["):
            val, i = read_long(lines, i, rest, line_no)
            blk.items.append((key, val))
        elif (rest.startswith(("{", "["))
              and not (text_values or key in TEXT_KEYS)):
            val, i = read_bracket(lines, i, rest, line_no)
            blk.items.append((key, val))
        else:
            tm = text_values or key in TEXT_KEYS
            parts = split_list(rest)
            if len(parts) > 1 and not tm:
                blk.items.append((key, [parse_scalar(p, line_no) for p in parts]))
            else:
                blk.items.append((key, parse_scalar(rest, line_no, tm)))
            i += 1
    return blk, i


def parse_source(src):
    lines = []
    for raw in src.splitlines():
        lead = len(raw) - len(raw.lstrip(" \t"))
        ind = lead + raw[:lead].count("\t") * 3
        lines.append((raw, ind))
    blk, i = parse_block(lines, 0, 0)
    if i != len(lines):
        parse_error(i + 1, "trailing content")
    return blk


def lua_str(s):
    if "\n" not in s and "\r" not in s and "\\" not in s:
        if '"' not in s:
            return '"%s"' % s
        if "'" not in s:
            return "'%s'" % s
    for n in range(12):
        eq = "=" * n
        if "]" + eq + "]" not in s:
            return "[" + eq + "[" + s + "]" + eq + "]"
    raise Error("cannot quote string for Lua")


def reindent(text, prefix):
    lines = text.split("\n")
    base = 0
    for l in lines:
        if l.strip():
            base = len(l) - len(l.lstrip())
            break
    out = []
    for l in lines:
        if not l.strip():
            out.append(l)
            continue
        ind = len(l) - len(l.lstrip())
        out.append(prefix + l[base:] if ind >= base else l)
    return "\n".join(out)


def lua_value(v, ctx="s"):
    if isinstance(v, list):
        return "{ %s }" % ", ".join(lua_value(x, ctx) for x in v)
    if isinstance(v, Text):
        return lua_str(v.s)
    if isinstance(v, Lua):
        return "function(%s)\n%s\nend" % (FIELD_PARAMS.get(ctx, "s"), v.s)
    if isinstance(v, Bare):
        return "'%s'" % v.s if v.s in IDS else lua_str(v.s)
    if isinstance(v, (Num, Bool)):
        return v.s
    if isinstance(v, Raw):
        return v.s
    if isinstance(v, Data):
        return v.s
    if isinstance(v, Nil):
        return "nil"
    raise Error("unsupported value: %r (ctx=%s)" % (v, ctx))


FNS = set()
USE_RE = re.compile(r"^use\s+([\w.+-]+)$")


def check_use(name, prm):
    if name not in FN_SIGS or not prm:
        return
    plist, _ret, variadic = FN_SIGS[name]
    n = len(param_env(prm))
    if not variadic and len(plist) > n:
        raise Error("fn %s takes %d parameter(s), event provides %d"
                    % (name, len(plist), n))


def use_name(v):
    if isinstance(v, (Text, Bare)):
        m = USE_RE.match(v.s.strip())
        if m:
            name = m.group(1)
            if name not in FNS:
                raise Error("unknown fn in use: " + name)
            return name
    return None


def parse_fn_sig(key):
    m = re.match(r"^fn\s+([\w.+-]+)\s*(?:\(([^)]*)\))?\s*"
                 r"(?:->\s*([A-Za-z_]\w*))?$", key)
    if not m:
        raise Error("bad fn: " + key)
    name, params, ret = m.group(1), m.group(2), m.group(3) or "any"
    if ret not in TYPES:
        raise Error("fn %s: unknown return type %r" % (name, ret))
    plist = []
    variadic = False
    if params is None:
        plist = [("s", "obj"), ("w", "obj"), ("wh", "obj")]
    elif params.strip():
        for p in params.split(","):
            p = p.strip()
            if not p:
                continue
            if p == "...":
                variadic = True
                continue
            if ":" in p:
                pn, pt = p.split(":", 1)
                pn, pt = pn.strip(), pt.strip()
            else:
                pn, pt = p, "any"
            if not re.fullmatch(r"[^\W\d]\w*", pn, re.UNICODE):
                raise Error("fn %s: bad parameter %r" % (name, pn))
            if pt not in TYPES:
                raise Error("fn %s: unknown type %r for %s" % (name, pt, pn))
            plist.append((pn, pt))
    return name, plist, ret, variadic


def param_env(params, name=None):
    if name and name in FN_SIGS:
        return {pn: pt for pn, pt in FN_SIGS[name][0]}
    env = {}
    for p in (params or "").split(","):
        p = p.strip()
        if not p or p == "...":
            continue
        pn = p.split(":")[0].strip()
        if not re.fullmatch(r"[^\W\d]\w*", pn, re.UNICODE):
            continue
        env[pn] = PARAM_TYPES.get(pn, "any")
    return env


def lua_body(v, key, indent=""):
    base, params = parse_key(key)
    prm = params or FIELD_PARAMS.get(base, "s")
    uname = use_name(v)
    if uname:
        check_use(uname, prm)
        return "fn_" + uname
    if isinstance(v, Lua):
        body = reindent(v.s, indent + IND)
        return "function(%s)\n%s\n%s" % (prm, body, indent + "end")
    if isinstance(v, Logic):
        body = "\n".join(emit_logic(v.stmts, indent + IND, param_env(prm)))
        return "function(%s)\n%s\n%s" % (prm, body, indent + "end")
    return lua_value(v)


def emit_on(block, indent, target=""):
    out = []
    for key, val in block.items:
        base, params = parse_key(key)
        parts = [p.strip() for p in base.split(",")]
        inherited = None
        m0 = re.match(r"^(before|after|post)\s+(.+)$", parts[0])
        if m0:
            inherited = m0.group(1) + "_"
            parts[0] = m0.group(2)
        names = []
        for part in parts:
            pfx = inherited or "before_"
            m = re.match(r"^(before|after|post)\s+(.+)$", part)
            if m:
                pfx = m.group(1) + "_"
                part = m.group(2)
            if part in ("Any", "Default"):
                names.append((part, "before_"))
            else:
                year = EVENTS.get(part) or EXTRA_EVENTS.get(part)
                if not year:
                    raise Error("unknown event: " + part)
                names.append((year, pfx))
        groups = []
        for year, pfx in names:
            if groups and groups[-1][0] == pfx:
                groups[-1][1].append(year)
            else:
                groups.append((pfx, [year]))
        uname = use_name(val)
        for pfx, years in groups:
            prm = params or ("s, ev, w" if years[0] in ("Any", "Default")
                             else "s, w, wh")
            if uname:
                check_use(uname, prm)
                src = "fn_" + uname
            elif isinstance(val, Lua):
                body = reindent(val.s, indent + IND)
                src = "function(%s)\n%s\n%s" % (prm, body, indent + "end")
            elif isinstance(val, Logic):
                body = "\n".join(emit_logic(val.stmts, indent + IND,
                                            param_env(prm)))
                src = "function(%s)\n%s\n%s" % (prm, body, indent + "end")
            elif (isinstance(val, (Text, Bare))
                  and val.s.strip() == "pass"):
                src = "function() return false end"
            else:
                src = lua_value(val)
            if len(years) > 1 and not target:
                out.append('%s["%s%s"] = %s;'
                           % (indent, pfx, ",".join(years), src))
            else:
                for year in years:
                    out.append("%s%s%s%s = %s;"
                               % (indent, target, pfx, year, src))
    return out


def emit_obj(block, ident, base, ctor, preset, parent=None):
    fi = base + IND
    if parent:
        lines = ["%s%s({" % (base, ctor)]
    else:
        lines = ["%s%s {" % (base, ctor)]
    words = block.get("words")
    if words is not None:
        if isinstance(words, Text):
            lines.append('%s-"%%s";' % fi % words.s)
        elif isinstance(words, Raw):
            lines.append("%s%s;" % (fi, words.s))
        else:
            raise Error("words must be a quoted string")
    nam = block.get("nam")
    if nam is not None:
        raise Error("nam: is not supported; the declaration name is the "
                    "object name")
    if ident:
        lines.append("%snam = %s;" % (fi, lua_str(ident)))
    attrs = list(preset)
    a = block.get("attrs")
    if a is not None:
        if isinstance(a, list):
            attrs += [x.s for x in a
                      if isinstance(x, (Bare, Text))]
        elif isinstance(a, (Bare, Text)):
            attrs.append(a.s)
    obj_items = []
    nested = []
    texts = block.all("text")
    for key, val in block.items:
        if key in ("words", "on", "contains", "parts", "inside",
                   "with", "attrs", "disabled", "before", "after", "post"):
            continue
        if key == "text" and len(texts) > 1:
            continue
        if re.match(r"^(before|after|post)\s+\S", key):
            one = Block()
            one.items = [(key, val)]
            lines.extend(emit_on(one, fi))
            continue
        fbase, _ = parse_key(key)
        if fbase in ("Any", "Default"):
            one = Block()
            one.items = [(key, val)]
            lines.extend(emit_on(one, fi))
            continue
        if key.startswith("var "):
            name = parse_key(key[4:])[0]
            lines.append("%s%s = %s;" % (fi, name, lua_body(val, name, fi)))
            continue
        try:
            rendered = lua_body(val, key, fi)
        except Error as e:
            raise Error("%s.%s: %s" % (ident, key, e))
        if "," in fbase:
            lines.append('%s["%s"] = %s;' % (fi, fbase, rendered))
        else:
            lines.append("%s%s = %s;" % (fi, fbase, rendered))
    on = block.get("on")
    if on:
        lines.extend(emit_on(on, fi))
    for pfx in ("before", "after", "post"):
        blk = block.get(pfx)
        if isinstance(blk, Block):
            tmp = Block()
            tmp.items = [("%s %s" % (pfx, k), v) for k, v in blk.items]
            lines.extend(emit_on(tmp, fi))
    if len(texts) > 1:
        lines.append("%stext = {" % fi)
        for t in texts:
            lines.append("%s%s%s;" % (fi, IND, lua_value(t)))
        lines.append("%s};" % fi)
    for key, val in block.items:
        if key in ("contains", "inside", "parts", "with"):
            if isinstance(val, Block):
                for nk, nv in val.items:
                    nested.append(emit_decl(nk, nv, fi + IND) + ";")
            else:
                refs = val if isinstance(val, list) else [val]
                for r in refs:
                    if not isinstance(r, (Bare, Text)):
                        raise Error("%s must list identifiers" % key)
                    obj_items.append("%s'%s';" % (fi + IND, r.s))
    blobs = []
    if obj_items:
        blobs.append("\n".join(obj_items))
    blobs += nested
    if blobs:
        lines.append("%sobj = {" % fi)
        for k, b in enumerate(blobs):
            if k:
                lines.append("")
            lines.extend(b.split("\n"))
        lines.append("%s};" % fi)
    if parent:
        tail = "%s}, %s)" % (base, parent)
    else:
        tail = "%s}" % base
    if attrs:
        tail += ":attr '%s'" % ",".join(attrs)
    if block.get("disabled"):
        tail += ":disable()"
    lines.append(tail)
    return "\n".join(lines)


def emit_verb(block, ident, base):
    fields = []
    tag = block.get("tag")
    if tag is None:
        fields.append("'#%s'" % ident)
    elif not (isinstance(tag, Bool) and tag.s == "false"):
        fields.append(lua_value(tag))
    words = block.get("words")
    if not isinstance(words, Text):
        raise Error("verb words must be a quoted string")
    fields.append(lua_str(words.s))
    pats = block.get("patterns")
    if pats is not None:
        if not isinstance(pats, list):
            pats = [pats]
        for p in pats:
            fields.append(lua_value(p))
    extra = []
    if block.get("prio") is not None:
        extra.append("prio = %s" % lua_value(block.get("prio")))
    if block.get("hint") is not None:
        extra.append("hint = %s" % lua_body(block.get("hint"), "hint"))
    lines = ["%sVerb { %s%s }" % (base, ", ".join(fields),
                                  (", " + ", ".join(extra)) if extra else "")]
    ev_field = block.get("event")
    ev = ev_field.s if isinstance(ev_field, Bare) else (ident or "?")
    for key, val in block.items:
        base_key, params = parse_key(key)
        if base_key not in ("on", "before", "after"):
            continue
        if not isinstance(val, (Lua, Logic)):
            continue
        mpname = {"on": "mp.", "before": "mp.before_",
                  "after": "mp.after_"}[base_key] + ev
        if isinstance(val, Lua):
            body = reindent(val.s, base + IND)
        else:
            body = "\n".join(emit_logic(val.stmts, base + IND,
                                        param_env(params or "s, w, wh")))
        lines.append("%s%s = function(%s)\n%s\n%s"
                     % (base, mpname, params or "s, w, wh", body, base + "end"))
    return "\n".join(lines)


PRESETS = {
    "obj": ("obj", []),
    "scenery": ("obj", ["scenery"]),
    "room": ("room", []),
    "door": ("door", []),
    "story": ("cutscene", []),
    "ending": ("gameover", []),
    "dlg": ("dlg", []),
}


def decl_key(key):
    m = re.match(
        r'^([A-Za-z][A-Za-z0-9_]*)(?:\s+(?:"([^"]+)"|\'([^\']+)\'|([\w#.+-]+)))?$',
        key)
    if not m:
        return None, None
    ident = m.group(2) or m.group(3) or m.group(4)
    return m.group(1), ident


def sym_text(v):
    if isinstance(v, (Bare, Text)):
        return v.s
    raise Error("expected expression")


def is_true(v):
    return isinstance(v, Bool) and v.s == "true"


def talk_act(reply, do, indent):
    if do is None:
        return reply
    if isinstance(do, Logic):
        body = emit_logic(do.stmts, indent + IND, {"s": "obj"})
    elif isinstance(do, Lua):
        body = [reindent(do.s, indent + IND)]
    else:
        raise Error("expected logic/lua block")
    if reply is not None:
        body = ["%sp(%s)" % (indent + IND, reply)] + body
    return ["%sfunction(s)" % indent] + body + ["%send" % indent]


def talk_table(oblock, indent, labels, tag=None):
    dsc = None
    reply = None
    do = None
    named = []
    children = []
    for key, val in oblock.items:
        base, _ = parse_key(key)
        if base in ("ask", "say"):
            dsc = lua_value(val)
        elif base == "reply":
            reply = lua_value(val)
        elif base == "do":
            do = val
        elif base == "when":
            named.append("cond = function() return %s end"
                         % transpile_exprlist(sym_text(val), {},
                                              "talk when")[0])
        elif base == "goto":
            named.append("next = '#%s'" % sym_text(val).lstrip('#'))
        elif base in ("always", "hidden", "only"):
            if is_true(val):
                named.append("%s = true" % base)
        elif base == "option":
            children.append(talk_table(val, indent + IND, labels))
        elif key.startswith("label ") and isinstance(val, Block):
            labels.append((key[6:].strip(), val))
        else:
            named.append("%s = %s" % (base, lua_body(val, key, indent + IND)))
    lines = ["%s{" % indent]
    if tag:
        lines.append("%s'%s';" % (indent + IND, tag))
    if dsc is not None:
        lines.append("%s%s;" % (indent + IND, dsc))
    act = talk_act(reply, do, indent + IND)
    if isinstance(act, list):
        lines.extend(act)
        lines[-1] += ";"
    elif act is not None:
        lines.append("%s%s;" % (indent + IND, act))
    for ch in children:
        lines.extend(ch)
        lines[-1] += ";"
    for n in named:
        lines.append("%s%s;" % (indent + IND, n))
    lines.append("%s}" % indent)
    return lines


def emit_talk(block, name, base):
    fi = base + IND
    labels = []
    root = []
    fields = []
    for key, val in block.items:
        b, _ = parse_key(key)
        if key == "intro":
            root.append(lua_value(val))
        elif b == "option":
            root.append(talk_table(val, fi + IND, labels))
        elif key.startswith("label ") and isinstance(val, Block):
            labels.append((key[6:].strip(), val))
        else:
            fields.append((key, val))
    lines = ["%sdlg {" % base, "%snam = '%s';" % (fi, name)]
    for key, val in fields:
        lines.append("%s%s = %s;" % (fi, key, lua_body(val, key, fi)))
    lines.append("%sphr = {" % fi)
    for r in root:
        if isinstance(r, list):
            lines.extend(r)
            lines[-1] += ";"
        else:
            lines.append("%s%s;" % (fi + IND, r))
    lines.append("%s};" % fi)
    if labels:
        lines.append("%sobj = {" % fi)
        for lname, lblock in labels:
            lines.extend(talk_table(lblock, fi + IND, labels,
                                    tag="#" + lname))
            lines[-1] += ";"
        lines.append("%s};" % fi)
    lines.append("%s}" % base)
    return "\n".join(lines)


def emit_class(block, name, parent):
    body = emit_obj(block, None, "", "Class", [], parent)
    return "%s = %s" % (name, body)


def emit_decl(key, block, base):
    kind, ident = decl_key(key)
    if not kind:
        raise Error("bad declaration: " + key)
    if kind == "verb":
        if not ident:
            raise Error("verb needs a name")
        return emit_verb(block, ident, base)
    if kind == "talk":
        if not ident:
            raise Error("talk needs a name")
        return emit_talk(block, ident, base)
    if kind not in PRESETS:
        if re.fullmatch(r"[A-Z][\w]*", kind):
            return emit_obj(block, ident, base, kind, [])
        raise Error("unknown kind: " + kind)
    ctor, preset = PRESETS[kind]
    return emit_obj(block, ident, base, ctor, preset)


def emit_setup(block):
    lines = []
    fmt = block.get("fmt")
    if fmt:
        vals = fmt if isinstance(fmt, list) else [fmt]
        for v in vals:
            if isinstance(v, (Bare, Text)):
                lines.append("fmt.%s = true" % v.s)
    take = block.get("take")
    takes = []
    if take:
        takes = take if isinstance(take, list) else [take]
        for t in takes:
            if not isinstance(t, (Bare, Text)):
                raise Error("take must list identifiers")
    for key, val in block.items:
        if key in ("take", "fmt", "init"):
            continue
        if key in ("hero", "game") and isinstance(val, Block):
            target = "pl." if key == "hero" else "game."
            for hk, hv in val.items:
                if hk == "on":
                    lines.extend(emit_on(hv, "", target))
                elif key == "hero" and hk == "words":
                    lines.append('pl.word = -"%s"' % hv.s)
                else:
                    lines.append("%s%s = %s" % (target, hk,
                                                lua_body(hv, hk)))
            continue
        if key == "on":
            lines.extend(emit_on(val, "", "game."))
            continue
        if key == "dsc":
            lines.append("game.dsc = %s" % lua_body(val, "dsc"))
            continue
        if key == "start":
            if isinstance(val, Lua):
                sb = reindent(val.s, IND)
            elif isinstance(val, Logic):
                sb = "\n".join(emit_logic(val.stmts, IND, {"load": "bool"}))
            else:
                raise Error("start must be a ~~~do/~~~lua block")
            lines.append("function start(load)")
            lines.append(sb)
            lines.append("end")
            continue
        raise Error("unknown setup key: " + key)
    lines.append("function init()")
    for t in takes:
        lines.append("%stake('%s')" % (IND, t.s))
    init = block.get("init")
    if isinstance(init, Lua):
        lines.append(reindent(init.s, IND))
    elif isinstance(init, Logic):
        lines.extend(emit_logic(init.stmts, IND))
    lines.append("end")
    return lines


def emit_patch(target, block):
    t = target.strip()
    if (t.startswith("'") and t.endswith("'")) or (
            t.startswith('"') and t.endswith('"')):
        t = t[1:-1]
    ref = "_'%s'" % t
    lines = []
    for key, val in block.items:
        base, _ = parse_key(key)
        if base in ("on", "before", "after", "post") and isinstance(val, Block):
            lines.extend(emit_on(val, "", ref + "."))
        elif base in ("Any", "Default") or base in EVENTS or (
                base in EXTRA_EVENTS):
            one = Block()
            one.items = [(key, val)]
            lines.extend(emit_on(one, "", ref + "."))
        elif key.startswith("var "):
            name = parse_key(key[4:])[0]
            lines.append("%s.%s = %s" % (ref, name, lua_body(val, name)))
        else:
            lines.append("%s.%s = %s" % (ref, base, lua_body(val, key)))
    return "\n".join(lines)


def emit_const(block):
    out = []
    for key, val in block.items:
        out.append("const '%s' (%s)" % (key, lua_value(val)))
    return out


def emit_global(block):
    out = []
    for key, val in block.items:
        out.append("global '%s' (%s)" % (key, lua_value(val)))
    return out


def collect_ids(root):
    ids = {}

    def add_from(block):
        for key, val in block.items:
            kind, ident = decl_key(key)
            if not kind or not ident:
                continue
            if kind not in PRESETS and kind != "talk" and not re.fullmatch(
                    r"[A-Z][\w]*", kind):
                continue
            if ident not in ids:
                ids[ident] = kind
            elif not ident.startswith("#"):
                raise Error("duplicate declaration: " + ident)
            for pkey in ("parts", "with"):
                sub = val.get(pkey) if isinstance(val, Block) else None
                if isinstance(sub, Block):
                    add_from(sub)

    add_from(root)
    return ids


def check_refs(root, ids):
    def refs(key, val):
        if isinstance(val, Block):
            return
        for r in (val if isinstance(val, list) else [val]):
            if isinstance(r, Bare) and r.s not in ids:
                raise Error("unknown reference in %s: %s" % (key, r.s))

    def walk(block):
        for key, val in block.items:
            if key in ("with", "contains", "inside", "found_in"):
                refs(key, val)
            if isinstance(val, Block):
                walk(val)
            elif isinstance(val, list):
                for x in val:
                    if isinstance(x, Block):
                        walk(x)

    walk(root)
    setup = root.get("setup")
    if isinstance(setup, Block):
        take = setup.get("take")
        if take:
            refs("take", take)


def scan_lua_defs(text, funcs, vars_):
    for m in re.finditer(r"function\s+([A-Za-z_]\w*)\s*\(", text):
        funcs.add(m.group(1))
    for m in re.finditer(r"([A-Za-z_]\w*)\s*=\s*function\s*\(", text):
        funcs.add(m.group(1))
    for m in re.finditer(r"^\s*local\s+([A-Za-z_]\w*)", text, re.M):
        vars_.add(m.group(1))
    for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s*=", text, re.M):
        vars_.add(m.group(1))


def collect_game_defs(root):
    funcs = set()
    vars_ = set()

    def walk(block):
        for key, val in block.items:
            if isinstance(val, Lua):
                scan_lua_defs(val.s, funcs, vars_)
            elif isinstance(val, Block):
                walk(val)

    walk(root)
    return funcs, vars_


def scan_required(name):
    path = os.path.join(SRC_DIR, name + ".lua")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def find_include(name):
    for base in (SRC_DIR, os.path.dirname(os.path.abspath(__file__))):
        path = os.path.join(base, name + ".mise")
        if os.path.exists(path):
            return path
    raise Error("include not found: " + name)


def apply_includes(root, seen=None):
    seen = seen or set()
    extra = []
    for key, val in root.items:
        if key != "include":
            continue
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            name = v.s if hasattr(v, "s") else str(v)
            if name in seen:
                continue
            seen.add(name)
            sub = parse_source(open(find_include(name),
                                    encoding="utf-8").read())
            apply_includes(sub, seen)
            extra += sub.items
    if extra:
        root.items = extra + root.items
    return root


def prescan(root):
    global IDS, EXTRA_EVENTS, FNS, VARS, FUNCS, FN_SIGS, GLOBAL_TYPES, EVENT_NAMES
    FNS = set()
    ids = collect_ids(root)
    IDS = set(ids)
    EXTRA_EVENTS = {}
    for key, val in root.items:
        kind, ident = decl_key(key)
        if kind == "verb" and ident and isinstance(val, Block):
            tag = val.get("tag")
            if not (isinstance(tag, Bool) and tag.s == "false"):
                EXTRA_EVENTS[ident] = ident
            event = val.get("event")
            if isinstance(event, Bare):
                EXTRA_EVENTS[event.s] = event.s
        elif key == "events":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                name = v.s if hasattr(v, "s") else str(v)
                EXTRA_EVENTS[name] = name
    EVENT_NAMES = set(EVENTS) | set(EXTRA_EVENTS.values())
    game_funcs, game_vars = collect_game_defs(root)
    FN_SIGS = {}
    fn_names = set()
    for key, val in root.items:
        if re.match(r"^fn\s+", key):
            name, plist, ret, variadic = parse_fn_sig(key)
            if name in FN_SIGS:
                raise Error("duplicate fn: " + name)
            FN_SIGS[name] = (plist, ret, variadic)
            fn_names.add(name)
    for key, val in root.items:
        if key == "require":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                text = scan_required(v.s if hasattr(v, "s") else str(v))
                if text:
                    scan_lua_defs(text, game_funcs, game_vars)
    const_names = set()
    GLOBAL_TYPES = {}
    for key, val in root.items:
        if key in ("const", "global") and isinstance(val, Block):
            for k, v in val.items:
                const_names.add(k)
                if isinstance(v, Num):
                    GLOBAL_TYPES[k] = "num"
                elif isinstance(v, Bool):
                    GLOBAL_TYPES[k] = "bool"
                elif isinstance(v, Text):
                    GLOBAL_TYPES[k] = "str"
                else:
                    GLOBAL_TYPES[k] = "any"
    VARS = game_vars | const_names
    FUNCS = fn_names | game_funcs | {"_"}
    FNS = fn_names
    check_refs(root, ids)


def transpile(src):
    root = parse_source(src)
    apply_includes(root)
    prescan(root)
    header = []
    body = []
    fn_body = []
    reqs = []
    for key, val in root.items:
        if key in ("name", "version", "author", "info"):
            header.append("--$%s:%s$" % (key.title(), val.s))
        elif key in ("lang", "fmt", "include"):
            continue
        elif key == "require":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                reqs.append(v.s if hasattr(v, "s") else str(v))
        elif key == "events":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                name = v.s if hasattr(v, "s") else str(v)
                EXTRA_EVENTS[name] = name
        elif key == "lua":
            body.append(val.s)
        elif re.match(r"^class\s+[A-Z]", key):
            m = re.match(r"^class\s+([A-Z][\w]*)\s*(?:\(([^)]*)\))?$",
                         key)
            if not m:
                raise Error("bad class: " + key)
            body.append(emit_class(val, m.group(1), m.group(2)))
        elif re.match(r"^fn\s+[\w.+-]+", key):
            name, plist, ret, variadic = parse_fn_sig(key)
            prm = ", ".join(pn for pn, _pt in plist)
            if variadic:
                prm = (prm + ", ...") if prm else "..."
            if isinstance(val, Lua):
                hb = reindent(val.s, IND)
            elif isinstance(val, Logic):
                hb = "\n".join(emit_logic(val.stmts, IND,
                                          param_env(prm, name), ret, name))
            else:
                raise Error("fn %s must be a ~~~do/~~~lua block"
                            % name)
            FNS.add(name)
            fn_body.append("local function fn_%s(%s)\n%s\nend"
                           % (name, prm, hb))
        elif re.match(r"^patch\s+.+$", key):
            body.append(emit_patch(key[6:].strip(), val))
        elif key == "setup":
            body.append("\n".join(emit_setup(val)))
        elif key == "const":
            body.append("\n".join(emit_const(val)))
        elif key == "global":
            body.append("\n".join(emit_global(val)))
        else:
            body.append(emit_decl(key, val, ""))
    body = fn_body + body
    lang = root.get("lang")
    lang = lang.s if isinstance(lang, Bare) else "ru"
    pre = ["-- generated by mise.py; do not edit", ""] + header + [
        'require "fmt"']
    root_fmt = root.get("fmt")
    if root_fmt:
        vals = root_fmt if isinstance(root_fmt, list) else [root_fmt]
        for v in vals:
            if isinstance(v, (Bare, Text)):
                pre.append("fmt.%s = true" % v.s)
    pre.append('require "parser/mp-%s"' % lang)
    pre += ['require "%s"' % r for r in reqs]
    return "\n".join(pre) + "\n\n" + "\n\n".join(body) + "\n"


def main(argv):
    global SRC_DIR
    if len(argv) < 2:
        print("usage: mise.py <game.mise> [-o out.lua]", file=sys.stderr)
        return 2
    SRC_DIR = os.path.dirname(os.path.abspath(argv[1]))
    with open(argv[1], encoding="utf-8") as f:
        src = f.read()
    out = transpile(src)
    if "-o" in argv:
        with open(argv[argv.index("-o") + 1], "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Error as e:
        print("mise: error: %s" % e, file=sys.stderr)
        sys.exit(1)
