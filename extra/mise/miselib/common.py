import re
import textwrap
from . import messages as M
from . import patterns as P

IND = "  "

_KEY_RE = re.compile(r"^(.*?)(?:\(([^)]*)\))?$")
_NUM_RE = re.compile(r"-?\d+(\.\d+)?")

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

def parse_key(key):
    m = _KEY_RE.match(key)
    return m.group(1).strip(), m.group(2)

def _skip_quoted(text, i):
    """Return the index after the quoted section starting at `i`."""
    quote = text[i]
    i += 1
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return i + 1
        i += 1
    return i

def split_key(text):
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c in "\"'":
            i = _skip_quoted(text, i)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ":" and depth == 0:
            return text[:i], text[i + 1:]
        i += 1
    return None, None

def parse_error(line, msg):
    raise Error(M.LINE_PREFIX % (line, msg))

def _copy_quoted(s, i, out):
    """Append the quoted section starting at `i` to `out`; return its end."""
    quote = s[i]
    out.append(quote)
    i += 1
    while i < len(s):
        c = s[i]
        out.append(c)
        if c == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 1
        elif c == quote:
            return i + 1
        i += 1
    return i

def strip_comment(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in "\"'":
            i = _copy_quoted(s, i, out)
            continue
        if c == "#" and (i == 0 or s[i - 1] in " \t") and (
                i + 1 >= len(s) or s[i + 1] in " \t"):
            break
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
    parse_error(line, M.UNTERMINATED_STRING_PLAIN)

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
    if _NUM_RE.fullmatch(s):
        return Num(s)
    return Text(s) if textmode else Bare(s)

def _skip_quoted_naive(s, i):
    """Return the index after a quoted section, ignoring backslashes."""
    quote = s[i]
    i += 1
    while i < len(s):
        if s[i] == quote:
            return i + 1
        i += 1
    return i

def _list_cuts(s):
    """Indices of top-level commas in `s` (outside quotes/brackets)."""
    cuts = []
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c in "\"'":
            i = _skip_quoted_naive(s, i)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            cuts.append(i)
        i += 1
    return cuts

def split_list(s):
    cuts = _list_cuts(s)
    starts = [0] + [c + 1 for c in cuts]
    ends = cuts + [len(s)]
    parts = [s[a:b] for a, b in zip(starts, ends)]
    return [p.strip() for p in parts if p.strip()]

def skip_blank(lines, i):
    """Index of the first non-blank line at or after `i`."""
    while i < len(lines) and not lines[i][0].strip():
        i += 1
    return i

def _long_skip(text, i):
    """Length of a `[[...]]` section at `i`: -1 unterminated, None no opener."""
    m = P.LONG_OPEN_RE.match(text[i:])
    if m is None:
        return None
    close = "]" + m.group(1) + "]"
    j = text.find(close, i + m.end())
    if j == -1:
        return -1
    return j + len(close) - i

def balanced_expr(text):
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            i = _skip_quoted(text, i)
            continue
        if text.startswith("[[", i):
            skip = _long_skip(text, i)
            if skip == -1:
                return False
            i += skip
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
            parse_error(line_no, M.UNTERMINATED_BRACES)
        text += "\n" + lines[i][0]
    return Data(text), i + 1

def long_balanced(text):
    i = 0
    while i < len(text):
        if text[i] == "[":
            skip = _long_skip(text, i)
            if skip == -1:
                return False
            if skip is not None:
                i += skip
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
    opener = P.LONG_OPEN_RE.match(first)
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
    parse_error(line_no, M.UNTERMINATED_BRACKET_STRING)

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
    raise Error(M.CANNOT_QUOTE_STRING_LUA)

def _first_indent(lines):
    for l in lines:
        if l.strip():
            return len(l) - len(l.lstrip())
    return 0

def reindent(text, prefix):
    lines = text.split("\n")
    base = _first_indent(lines)
    out = []
    for l in lines:
        if not l.strip():
            out.append(l)
            continue
        ind = len(l) - len(l.lstrip())
        out.append(prefix + l[base:] if ind >= base else l)
    return "\n".join(out)
