#!/usr/bin/env python3
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
    "AskFor Answer Yes No Next Look Receive ThrownAt LetGo LetIn"
).split():
    EVENTS[_e.lower()] = _e

ATTRS = {
    "scenery", "static", "fixed", "container", "supporter", "transparent",
    "enterable", "light", "luminous", "animate", "clothing", "worn",
    "edible", "switchable", "concealed", "lockable", "locked", "open",
    "openable", "on",
}

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


class Sym:
    def __init__(self, s):
        self.s = s


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
        body.append((raw, ind))
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
        raw, ind = lines[i]
        if not raw.strip():
            i += 1
            continue
        if ind < indent:
            break
        if ind > indent:
            parse_error(i + 1, "unexpected indent: %r" % raw)
        text = strip_comment(raw.strip())
        while not long_balanced(text) and i + 1 < len(lines):
            i += 1
            text += "\n" + lines[i][0]
        text = dedent_rest(text)
        if not text:
            i += 1
            continue
        if text == "stop":
            stmts.append(("return", None))
            i += 1
            continue
        if text == "pass":
            stmts.append(("return", "false"))
            i += 1
            continue
        m = re.match(r"^return\b\s*(.*)$", text, re.S)
        if m:
            stmts.append(("return", m.group(1) or None))
            i += 1
            continue
        m = re.match(r"^(say|line|append)(?:\s+(.+))?$", text, re.S)
        if m:
            stmts.append((m.group(1), (m.group(2) or "").strip()))
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
                parse_error(i + 1, "empty if")
            body, j = parse_logic(lines, j, lines[j][1])
            branches[0] = (branches[0][0], body)
            i = j
            while i < len(lines):
                raw2, ind2 = lines[i]
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
                        parse_error(i + 1, "empty elseif")
                    b2, j = parse_logic(lines, j, lines[j][1])
                    branches.append((cond, b2))
                    i = j
                elif ind2 == ind and t2 == "else:":
                    j = i + 1
                    while j < len(lines) and not lines[j][0].strip():
                        j += 1
                    if j >= len(lines) or lines[j][1] <= ind:
                        parse_error(i + 1, "empty else")
                    else_body, j = parse_logic(lines, j, lines[j][1])
                    i = j
                else:
                    break
            stmts.append(("if", branches, else_body))
            continue
        m = re.match(r"^for\s+(.+):$", text, re.S)
        if m:
            header = dedent_rest(m.group(1).strip())
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j >= len(lines) or lines[j][1] <= ind:
                parse_error(i + 1, "empty for")
            body, j = parse_logic(lines, j, lines[j][1])
            stmts.append(("for", header, body))
            i = j
            continue
        m = re.match(r"^set\s+(.+?)\s*(\+=|-=|=)\s*(.+)$", text, re.S)
        if m:
            stmts.append(("set", m.group(1).strip(), m.group(2),
                          m.group(3).strip()))
            i += 1
            continue
        stmts.append(("stmt", text))
        i += 1
    return stmts, i


IDS = set()


KEYWORDS = {
    "return", "not", "and", "or", "if", "elseif", "while", "until", "in",
    "then", "else", "do", "local", "function", "end", "break", "repeat",
}

EXTRA_EVENTS = {}


def rewrite_expr(text):
    if not IDS:
        return text
    out = []
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
            out.append(text[i:j])
            i = j
            continue
        if c == "[" and i + 1 < n and text[i + 1] == "[":
            j = text.find("]]", i + 2)
            if j == -1:
                out.append(text[i:])
                break
            out.append(text[i:j + 2])
            i = j + 2
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            name = text[i:j]
            k = j
            while k < n and text[k] in " \t":
                k += 1
            if name in IDS:
                if k < n and text[k] == ":":
                    out.append("_'%s':" % name)
                    i = k + 1
                    continue
                wrapped = "_'%s'" % name
                prev = "".join(out).rstrip()
                if prev and (prev[-1].isalnum() or prev[-1] in "_'\")]"):
                    m2 = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", prev)
                    if not (m2 and m2.group(1) in KEYWORDS):
                        wrapped = "(%s)" % wrapped
                out.append(wrapped)
                i = j
                continue
            out.append(name)
            i = j
            continue
        out.append(c)
        i += 1
    res = "".join(out)
    res = re.sub(r"([A-Za-z0-9_]|\)|\]|'|\") \(_'", r"\1(_'", res)
    res = re.sub(r"(:has|:hasnt|:once|:hint)\s+(?![\[\"'])"
                 r"([^\s,()]+)", r"\1 '\2'", res)
    res = re.sub(r":attr\s+(?![\[\"'])([^\n]+?)\s*$",
                 lambda m: ":attr '%s'" % m.group(1).strip(), res)
    return res


def logic_arg(text):
    s = text.strip()
    if not s:
        return s
    if re.search(r"['\"(\[{}\]:#]", s) or re.search(r"\s\^\s", s):
        return rewrite_expr(s)
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return s
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*",
                    s):
        return rewrite_expr(s)
    return lua_str(s)


def emit_logic(stmts, indent):
    out = []
    for st in stmts:
        kind = st[0]
        if kind in ("say", "line", "append"):
            fn = {"say": "p", "line": "pn", "append": "pr"}[kind]
            out.append("%s%s(%s)" % (indent, fn, logic_arg(st[1])))
        elif kind == "return":
            out.append("%sreturn%s" % (
                indent, (" " + rewrite_expr(st[1])) if st[1] else ""))
        elif kind == "set":
            lhs, op, rhs = st[1], st[2], rewrite_expr(st[3])
            if op == "=":
                out.append("%s%s = %s" % (indent, lhs, rhs))
            else:
                sign = "+" if op == "+=" else "-"
                out.append("%s%s = %s %s (%s)" % (indent, lhs, lhs, sign, rhs))
        elif kind == "stmt":
            out.append(indent + rewrite_expr(st[1]))
        elif kind == "for":
            out.append("%sfor %s do" % (indent, rewrite_expr(st[1])))
            out.extend(emit_logic(st[2], indent + IND))
            out.append(indent + "end")
        elif kind == "if":
            branches, else_body = st[1], st[2]
            for idx, (cond, body) in enumerate(branches):
                out.append("%s%s %s then" % (indent,
                                             "if" if idx == 0 else "elseif",
                                             rewrite_expr(cond)))
                out.extend(emit_logic(body, indent + IND))
            if else_body is not None:
                out.append(indent + "else")
                out.extend(emit_logic(else_body, indent + IND))
            out.append(indent + "end")
    return out


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
    if tag in ("~~~lua", "```lua"):
        return Lua(reindent("\n".join(raw for raw, _ in body), "")), i
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
        m = re.match(r"^([^:]+):\s*(.*)$", text)
        if not m:
            parse_error(i + 1, "expected 'key: value'")
        key, rest = m.group(1).strip(), m.group(2).strip()
        line_no = i + 1
        if rest == "":
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j < len(lines) and lines[j][0].strip() in (
                    "~~~lua", "```lua", "~~~do", "```do", "~~~"):
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
        elif rest in ("~~~lua", "```lua", "~~~do", "```do", "~~~"):
            val, i = fence_value(rest, lines, i + 1, line_no)
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
    if "]]" not in s:
        return "[[%s]]" % s
    if "]==]" not in s:
        return "[==[%s]==]" % s
    return "[====[%s]====]" % s


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
    if isinstance(v, Sym):
        return "'%s'" % v.s
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


HANDLERS = set()
USE_RE = re.compile(r"^use\s+([\w.+-]+)$")


def use_name(v):
    if isinstance(v, (Text, Bare, Sym)):
        m = USE_RE.match(v.s.strip())
        if m:
            name = m.group(1)
            if name not in HANDLERS:
                raise Error("unknown handler in use: " + name)
            return name
    return None


def lua_body(v, key, indent=""):
    base, params = parse_key(key)
    prm = params or FIELD_PARAMS.get(base, "s")
    uname = use_name(v)
    if uname:
        return uname
    if isinstance(v, Lua):
        body = reindent(v.s, indent + IND)
        return "function(%s)\n%s\n%s" % (prm, body, indent + "end")
    if isinstance(v, Logic):
        body = "\n".join(emit_logic(v.stmts, indent + IND))
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
            if part in ("any", "default"):
                names.append((part.title(), "before_"))
            else:
                year = EVENTS.get(part.lower()) or EXTRA_EVENTS.get(
                    part.lower())
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
                src = uname
            elif isinstance(val, Lua):
                body = reindent(val.s, indent + IND)
                src = "function(%s)\n%s\n%s" % (prm, body, indent + "end")
            elif isinstance(val, Logic):
                body = "\n".join(emit_logic(val.stmts, indent + IND))
                src = "function(%s)\n%s\n%s" % (prm, body, indent + "end")
            elif (isinstance(val, (Text, Bare, Sym))
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


def emit_obj(block, ident, base, ctor, preset):
    fi = base + IND
    lines = ["%s%s {" % (base, ctor)]
    words = block.get("words")
    if words is not None:
        if not isinstance(words, Text):
            raise Error("words must be a quoted string")
        lines.append('%s-"%%s";' % fi % words.s)
    nam = block.get("nam")
    if nam is not None:
        lines.append("%snam = %s;" % (fi, lua_value(nam)))
    elif ident:
        lines.append("%snam = '%s';" % (fi, ident))
    attrs = list(preset)
    a = block.get("attrs")
    if a is not None:
        if isinstance(a, list):
            attrs += [x.s for x in a
                      if isinstance(x, (Sym, Bare, Text))]
        elif isinstance(a, Sym):
            attrs.append(a.s)
    obj_items = []
    nested = []
    texts = block.all("text")
    for key, val in block.items:
        if key in ("words", "nam", "on", "contains", "parts", "inside",
                   "with", "attrs", "disabled", "before", "after", "post"):
            continue
        if key == "text" and len(texts) > 1:
            continue
        fbase, _ = parse_key(key)
        if fbase in ("any", "default"):
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
                    if not isinstance(r, (Sym, Bare, Text)):
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
        extra.append("hint = %s" % lua_value(block.get("hint")))
    lines = ["%sVerb { %s%s }" % (base, ", ".join(fields),
                                  (", " + ", ".join(extra)) if extra else "")]
    ev_field = block.get("event")
    ev = ev_field.s if isinstance(ev_field, Sym) else (ident or "?")
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
            body = "\n".join(emit_logic(val.stmts, base + IND))
        lines.append("%s%s = function(%s)\n%s\n%s"
                     % (base, mpname, params or "s, w, wh", body, base + "end"))
    return "\n".join(lines)


PRESETS = {
    "obj": ("obj", []),
    "scenery": ("obj", ["scenery"]),
    "fixed": ("obj", ["fixed"]),
    "furniture": ("obj", ["static", "supporter"]),
    "box": ("obj", ["container", "open", "openable"]),
    "npc": ("obj", ["animate"]),
    "room": ("room", []),
    "door": ("door", []),
    "story": ("cutscene", []),
    "ending": ("gameover", []),
    "dlg": ("dlg", []),
}


def decl_key(key):
    m = re.match(
        r'^([a-z]+)(?:\s+(?:"([^"]+)"|\'([^\']+)\'|([\w#.+-]+)))?$', key)
    if not m:
        return None, None
    ident = m.group(2) or m.group(3) or m.group(4)
    return m.group(1), ident


def sym_text(v):
    if isinstance(v, (Sym, Bare, Text)):
        return v.s
    raise Error("expected expression")


def is_true(v):
    return isinstance(v, Bool) and v.s == "true"


def logic_lines(v, indent):
    if isinstance(v, Logic):
        return emit_logic(v.stmts, indent)
    if isinstance(v, Lua):
        return [reindent(v.s, indent)]
    raise Error("expected logic/lua block")


def talk_act(reply, do, indent):
    if do is None:
        return reply
    body = logic_lines(do, indent + IND)
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
                         % rewrite_expr(sym_text(val)))
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
        raise Error("unknown kind: " + kind)
    ctor, preset = PRESETS[kind]
    return emit_obj(block, ident, base, ctor, preset)


def emit_setup(block):
    lines = []
    fmt = block.get("fmt")
    if fmt:
        vals = fmt if isinstance(fmt, list) else [fmt]
        for v in vals:
            if isinstance(v, Sym):
                lines.append("fmt.%s = true" % v.s)
    take = block.get("take")
    takes = []
    if take:
        takes = take if isinstance(take, list) else [take]
        for t in takes:
            if not isinstance(t, (Sym, Bare, Text)):
                raise Error("take must list identifiers")
    for key, val in block.items:
        if key in ("take", "fmt", "init"):
            continue
        if key == "hero":
            for hk, hv in val.items:
                if hk == "on":
                    lines.extend(emit_on(hv, "", "pl."))
                elif hk == "words":
                    lines.append('pl.word = -"%s"' % hv.s)
                else:
                    lines.append("pl.%s = %s" % (hk, lua_body(hv, hk)))
            continue
        if key == "on":
            lines.extend(emit_on(val, "", "game."))
            continue
        if key == "game" and isinstance(val, Block):
            for gk, gv in val.items:
                if gk == "on":
                    lines.extend(emit_on(gv, "", "game."))
                else:
                    lines.append("game.%s = %s" % (gk, lua_body(gv, gk)))
            continue
        if key == "dsc":
            lines.append("game.dsc = %s" % lua_body(val, "dsc"))
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
        elif base in ("any", "default") or base in EVENTS or (
                base.lower() in EXTRA_EVENTS):
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
            if not kind or not ident or (kind not in PRESETS
                                         and kind != "talk"):
                continue
            if ident in ids:
                raise Error("duplicate declaration: " + ident)
            ids[ident] = kind
            for pkey in ("parts", "with"):
                sub = val.get(pkey) if isinstance(val, Block) else None
                if isinstance(sub, Block):
                    add_from(sub)

    add_from(root)
    return ids


def check_refs(root, ids):
    def walk(block, key):
        val = block.get(key) if isinstance(block, Block) else None
        if val is None:
            return
        refs = val if isinstance(val, list) else [val]
        for r in refs:
            if isinstance(r, (Sym, Bare)) and r.s not in ids:
                raise Error("unknown reference in %s: %s" % (key, r.s))
    for key, val in root.items:
        if not isinstance(val, Block):
            continue
        for k2 in ("with", "contains", "inside", "found_in"):
            walk(val, k2)
        for k2, v2 in val.items:
            if k2 in ("with", "parts") and isinstance(v2, Block):
                for nk, nv in v2.items:
                    for k3 in ("with", "contains", "inside", "found_in"):
                        walk(nv, k3)
    setup = root.get("setup")
    if isinstance(setup, Block):
        take = setup.get("take")
        if take:
            refs = take if isinstance(take, list) else [take]
            for r in refs:
                if isinstance(r, (Sym, Bare)) and r.s not in ids:
                    raise Error("unknown reference in take: " + r.s)


def transpile(src):
    global IDS, EXTRA_EVENTS, HANDLERS
    HANDLERS = set()
    root = parse_source(src)
    ids = collect_ids(root)
    IDS = set(ids)
    EXTRA_EVENTS = {}
    for key, val in root.items:
        kind, ident = decl_key(key)
        if kind == "verb" and ident and isinstance(val, Block):
            tag = val.get("tag")
            if not (isinstance(tag, Bool) and tag.s == "false"):
                EXTRA_EVENTS[ident.lower()] = ident
            event = val.get("event")
            if isinstance(event, Sym):
                EXTRA_EVENTS[event.s.lower()] = event.s
    check_refs(root, ids)
    header = []
    body = []
    reqs = []
    for key, val in root.items:
        if key in ("name", "version", "author", "info"):
            header.append("--$%s:%s$" % (key.title(), val.s))
        elif key in ("lang", "fmt"):
            continue
        elif key == "require":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                reqs.append(v.s if hasattr(v, "s") else str(v))
        elif key == "lua":
            body.append(val.s)
        elif re.match(r"^handler\s+[\w.+-]+", key):
            m = re.match(r"^handler\s+([\w.+-]+)\s*(?:\(([^)]*)\))?$",
                         key)
            if not m:
                raise Error("bad handler: " + key)
            name = m.group(1)
            prm = m.group(2) or "s, w, wh"
            if isinstance(val, Lua):
                hb = reindent(val.s, IND)
            elif isinstance(val, Logic):
                hb = "\n".join(emit_logic(val.stmts, IND))
            else:
                raise Error("handler %s must be a ~~~do/~~~lua block"
                            % name)
            HANDLERS.add(name)
            body.append("local function %s(%s)\n%s\nend"
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
    lang = root.get("lang")
    lang = lang.s if isinstance(lang, Sym) else "ru"
    pre = ["-- generated by mise.py; do not edit", ""] + header + [
        'require "fmt"', 'require "parser/mp-%s"' % lang]
    pre += ['require "%s"' % r for r in reqs]
    return "\n".join(pre) + "\n\n" + "\n\n".join(body) + "\n"


def main(argv):
    if len(argv) < 2:
        print("usage: mise.py <game.mise> [-o out.lua]", file=sys.stderr)
        return 2
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
