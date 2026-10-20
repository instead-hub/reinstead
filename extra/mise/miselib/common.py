import os
import re
import textwrap
from . import messages as M
from . import patterns as P

IND = "  "

_KEY_RE = re.compile(r"^(.*?)(?:\(([^)]*)\))?$")
_NUM_RE = re.compile(r"-?\d+(\.\d+)?")
_LOC_RE = re.compile(r"\S+:\d+")


def file_label(path):
    """Short source name for diagnostics."""
    return os.path.basename(path) if path else None


class Error(Exception):
    def __init__(self, msg):
        line = CURRENT_LINE[0]
        if line and "line " not in str(msg) and not _LOC_RE.search(str(msg)):
            label = file_label(CURRENT_FILE[0])
            msg = ("%s:%d: %s" % (label, line, msg) if label
                   else "line %d: %s" % (line, msg))
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

class FnRef(Val):
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
CURRENT_FILE = [None]
PARSING_FILE = [None]


class Block:
    def __init__(self):
        self.items = []
        self.lines = []
        self.srcs = []

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
    params = m.group(2)
    # `fn` headers carry types; handler keys must use bare names
    if params and ":" in params and not key.startswith("fn "):
        raise Error(M.PARAM_TYPES_NOT_ALLOWED % params)
    return m.group(1).strip(), params

def _skip_quoted(text, i, naive=False):
    """Return the index after the quoted section starting at `i`."""
    quote = text[i]
    i += 1
    while i < len(text):
        c = text[i]
        if not naive and c == "\\":
            i += 2
            continue
        if c == quote:
            return i + 1
        i += 1
    return i

def _scan_depth(s, i, opens, closes, naive=False):
    """Yield (index, char, depth) skipping quoted runs."""
    depth = 0
    while i < len(s):
        c = s[i]
        if c in "\"'":
            i = _skip_quoted(s, i, naive)
            continue
        if c in opens:
            depth += 1
        elif c in closes:
            depth -= 1
        yield i, c, depth
        i += 1

def split_key(text):
    for i, c, depth in _scan_depth(text, 0, "([{", ")]}"):
        if c == ":" and depth == 0:
            return text[:i], text[i + 1:]
    return None, None

def parse_error(line, msg):
    label = file_label(PARSING_FILE[0])
    if label:
        raise Error("%s:%d: %s" % (label, line, msg))
    raise Error(M.LINE_PREFIX % (line, msg))

def strip_comment(s):
    i = 0
    while i < len(s):
        c = s[i]
        if c in "\"'":
            i = _skip_quoted(s, i)
            continue
        if c == "#" and (i == 0 or s[i - 1] in " \t") and (
                i + 1 >= len(s) or s[i + 1] in " \t"):
            return s[:i].rstrip()
        i += 1
    return s.rstrip()

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

# keys whose block holds declarations or `key: value` fields; under any
# other key an indented block is logic and must start with `|`
STRUCT_KEYS = {
    "obj", "scenery", "room", "door", "story", "ending", "class", "mixin",
    "impl", "verb", "talk", "setup", "const", "global", "props", "refs",
    "extend", "with", "option", "label", "hero", "game",
}

def parse_scalar(s, line, textmode=False):
    s = s.strip()
    if s.startswith("`"):
        stop = s.find("`", 1)
        if stop == -1:
            parse_error(line, M.TRAILING_VALUE % s)
        junk = s[stop + 1:].strip()
        if junk:
            parse_error(line, M.TRAILING_VALUE % junk)
        return Raw(s[1:stop])
    if s.startswith(("'", '"')):
        val, end = parse_string(s, line)
        tail = s[end:].strip()
        if tail:
            parse_error(line, M.TRAILING_VALUE % tail)
        return Text(val)
    if s in ("true", "false"):
        return Bool(s)
    if s == "nil":
        return Nil()
    if _NUM_RE.fullmatch(s):
        return Num(s)
    return Text(s) if textmode else Bare(s)

def _list_cuts(s):
    """Indices of top-level commas in `s` (outside quotes/brackets)."""
    return [i for i, c, depth in _scan_depth(s, 0, "([{", ")]}", naive=True)
            if c == "," and depth == 0]

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

def _bracket_delta(c):
    """+1 for an opener, -1 for a closer, 0 otherwise."""
    if c in "{[(":
        return 1
    if c in "}])":
        return -1
    return 0

def _scan_brackets(text):
    """Scan `text`: (ends, depth, closed).

    `ends` holds the index after every bracket run closed back to zero,
    `depth` is the final depth, `closed` is False on an unterminated
    `[[...]]` or a closing bracket without an opener.
    """
    depth = 0
    ends = []
    i = 0
    while i < len(text):
        c = text[i]
        if c in "\"'":
            i = _skip_quoted(text, i)
            continue
        if text.startswith("[[", i):
            skip = _long_skip(text, i)
            if skip < 0:
                return ends, depth, False
            i += skip
            continue
        delta = _bracket_delta(c)
        depth += delta
        if depth < 0:
            return ends, depth, False
        if depth == 0 and delta < 0:
            ends.append(i + 1)
        i += 1
    return ends, depth, True

def read_bracket(lines, i, first, line_no):
    text = first
    while True:
        ends, depth, closed = _scan_brackets(text)
        if closed and depth == 0:
            break
        i += 1
        if i >= len(lines):
            parse_error(line_no, M.UNTERMINATED_BRACES)
        text += "\n" + lines[i][0]
    end = ends[0] if ends else None
    tail = text[end:].strip() if end is not None else ""
    if tail:
        parse_error(line_no + text[:end].count("\n"),
                    M.TRAILING_VALUE % tail)
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
        stop = content.index(close)
        junk = content[stop + len(close):].strip()
        if junk:
            parse_error(line_no, M.TRAILING_VALUE % junk)
        return Text(content[:stop]), i + 1
    body = [content] if content else [""]
    i += 1
    while i < len(lines):
        raw, _ind = lines[i]
        if close in raw:
            at = raw.index(close)
            extra = raw[at + len(close):].strip()
            if extra:
                parse_error(i + 1, M.TRAILING_VALUE % extra)
            body.append(raw[:at])
            first_line = body[0]
            rest = textwrap.dedent("\n".join(body[1:]))
            return Text(first_line + ("\n" + rest if rest else "")), i + 1
        body.append(raw)
        i += 1
    parse_error(line_no, M.UNTERMINATED_BRACKET_STRING)

def _long_bracket(s):
    """A long-bracket Lua string for `s`, else None (12 levels of `=`)."""
    for n in range(12):
        eq = "=" * n
        if "]" + eq + "]" not in s:
            return "[" + eq + "[" + s + "]" + eq + "]"
    return None


def lua_str(s):
    if "\n" not in s and "\r" not in s and "\\" not in s:
        if '"' not in s:
            return '"%s"' % s
        if "'" not in s:
            return "'%s'" % s
    long = _long_bracket(s)
    if long is None:
        raise Error(M.CANNOT_QUOTE_STRING_LUA)
    return long

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
