import re
import textwrap

IND = "  "

FIELD_PARAMS = {
    "daemon": "s", "description": "s", "dsc": "s", "title": "s", "inv": "s",
    "inside_dsc": "s", "init_dsc": "s", "dark_dsc": "s", "cant_go": "s, to",
    "compass_look": "s, to",
    "onenter": "s, w", "onexit": "s, w", "enter": "s, w", "exit": "s, w",
    "each_turn": "s", "found_in": "s", "door_to": "s", "scope": "s, w",
    "when_open": "s", "when_closed": "s", "when_on": "s", "when_off": "s",
}

class Error(Exception):
    def __init__(self, msg):
        line = CURRENT_LINE[0]
        if line and "line " not in str(msg) and "logic:" not in str(msg):
            msg = "line %d: %s" % (line, msg)
        super().__init__(msg)

class Val:
    def __init__(self, s=""):
        self.s = s

class Text(Val):
    pass

class Lua(Val):
    pass

class Logic:
    def __init__(self, stmts):
        self.stmts = stmts

class Bare(Val):
    pass

class Num(Val):
    pass

class Bool(Val):
    pass

class Nil(Val):
    pass

class Data(Val):
    pass

class Raw(Val):
    pass

CURRENT_LINE = [None]


class Block:
    def __init__(self):
        self.items = []
        self.lines = []

    def add(self, key, val, line):
        self.items.append((key, val))
        self.lines.append(line)

    def line_at(self, idx):
        return self.lines[idx] if idx < len(self.lines) else None

    def line(self, key):
        for i, (k, _v) in enumerate(self.items):
            if k == key:
                return self.line_at(i)
        return None

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

class LintError(Error):
    pass


class TypeCheckError(LintError):
    pass

def read_long(lines, i, first, line_no):
    opener = re.match(r"^\[(=*)\[", first)
    close = "]" + opener.group(1) + "]"
    content = first[opener.end():]
    if close in content:
        return Text(content[:content.index(close)]), i + 1
    body = [content] if content else [""]
    i += 1
    while i < len(lines):
        raw, _ind = lines[i]
        if close in raw:
            body.append(raw[:raw.index(close)])
            first_line = body[0]
            rest = textwrap.dedent("\n".join(body[1:]))
            return Text(first_line + ("\n" + rest if rest else "")), i + 1
        body.append(raw)
        i += 1
    parse_error(line_no, "unterminated [[ string")

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
