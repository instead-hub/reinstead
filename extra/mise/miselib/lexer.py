"""Compact lexer for MISE 2."""
import re
from dataclasses import dataclass
from typing import List
from .ast_nodes import Error


@dataclass
class Token:
    kind: str
    val: str
    line: int
    spaced: bool = False


_IDENT_RE = re.compile(r"@?[A-Za-z_А-Яа-яЁё][A-Za-z0-9_А-Яа-яЁё]*")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_LONG_RE = re.compile(r"\[(=*)\[")
_LUA_SPAN_RE = re.compile(
    r"--\[(=*)\[[\s\S]*?\]\1\]|--[^\n]*|\[(=*)\[[\s\S]*?\]\2\]"
    r'|"(?:\\[\s\S]|[^"\\\n])*"|\'(?:\\[\s\S]|[^\'\\\n])*\''
)
_MULTI_OPS = ("...", "->", ":=", "+=", "-=", "==", "!=", "~=", "<=", ">=", "..", "//")
_SINGLE_OPS = set("()[]{}:,.;=+-*/%<>@&*+?~|")


def lua_lines(text: str) -> List[str]:
    """Split Lua code on newlines outside string literals and long comments."""
    if text.endswith("\n"):
        text = text[:-1]
    if not text:
        return []
    out: List[str] = []
    cur, pos = "", 0
    for m in _LUA_SPAN_RE.finditer(text):
        head, *rest = text[pos:m.start()].split("\n")
        cur += head
        if rest:
            out.append(cur)
            out.extend(rest[:-1])
            cur = rest[-1]
        cur += m.group(0)
        pos = m.end()
    head, *rest = text[pos:].split("\n")
    out.append(cur + head)
    out.extend(rest)
    return out


def _scan_str(src: str, pos: int, line: int, src_name: str):
    n = len(src)
    triple = src.startswith(('"""', "'''"), pos)
    delim = src[pos:pos + 3] if triple else src[pos]
    i = pos + len(delim)
    if triple and i < n and src[i] == "\n":
        i += 1
        line += 1
    buf = []
    while i < n:
        if src.startswith(delim, i):
            val = "".join(buf)
            kind = "ISTRING" if (delim[0] == '"' and "{" in val and "}" in val) else "STRING"
            return Token(kind, val.replace("\x00{", "{").replace("\x00}", "}"), line), i + len(delim), line
        ch = src[i]
        if ch == "\n":
            line += 1
        if ch == "\\" and i + 1 < n:
            nxt = src[i + 1]
            if nxt == "\n":
                # a trailing backslash joins the next line: the newline and the
                # indentation of the next line are not part of the value
                i += 2
                line += 1
                while i < n and src[i] in " \t":
                    i += 1
                continue
            buf.append("\n" if nxt == "n" else "\t" if nxt == "t" else ("\x00" + nxt if nxt in "{}" else nxt))
            i += 2
            continue
        buf.append(ch)
        i += 1
    raise Error("unterminated string literal", line, src_name)


def tokenize(src: str, src_name: str = "") -> List[Token]:
    src = src.replace("\r\n", "\n").replace("\r", "\n")
    tokens: List[Token] = []
    indents = [0]
    pdepth = 0
    n, pos, line = len(src), 0, 1
    line_start = True

    while pos < n:
        if line_start and pdepth == 0:
            ls = pos
            while pos < n and src[pos] in " \t":
                pos += 1
            if pos >= n or src[pos] == "\n":
                pos += 1
                line += 1
                continue
            if (src[pos] == "#" or src.startswith("--", pos)) and not src.startswith('--"', pos):
                while pos < n and src[pos] != "\n":
                    pos += 1
                continue
            ind = sum(3 if c == "\t" else 1 for c in src[ls:pos])
            if ind > indents[-1]:
                indents.append(ind)
                tokens.append(Token("INDENT", "", line))
            else:
                while ind < indents[-1]:
                    indents.pop()
                    tokens.append(Token("DEDENT", "", line))
                if ind != indents[-1]:
                    raise Error(f"inconsistent indentation ({ind})", line, src_name)
            line_start = False

        spaced = False
        while pos < n and src[pos] in " \t":
            pos += 1
            spaced = True
        if pos >= n:
            break
        ch = src[pos]

        if ch == "\n":
            line += 1
            pos += 1
            if pdepth == 0:
                if tokens and tokens[-1].kind not in ("NEWLINE", "INDENT"):
                    tokens.append(Token("NEWLINE", "\n", line - 1))
                line_start = True
            continue

        if (src.startswith("--", pos) and not src.startswith('--"', pos)) or (
            ch == "#" and (pos + 1 >= n or not _IDENT_RE.match(src, pos + 1))
        ):
            while pos < n and src[pos] != "\n":
                pos += 1
            continue

        m = _LONG_RE.match(src, pos)
        if m:
            close = "]" + m.group(1) + "]"
            start = pos + len(m.group(0))
            end = src.find(close, start)
            if end == -1:
                raise Error("unterminated [[...]] string", line, src_name)
            raw = src[start:end]
            val = raw[1:] if raw.startswith("\n") else raw
            tokens.append(Token("STRING", val, line, spaced))
            line += raw.count("\n")
            pos = end + len(close)
            continue

        if ch in ('"', "'"):
            tok, pos, line = _scan_str(src, pos, line, src_name)
            tok.spaced = spaced
            tokens.append(tok)
            continue

        if ch == "`":
            end = src.find("`", pos + 1)
            if end == -1:
                raise Error("unterminated `...`", line, src_name)
            tokens.append(Token("RAW", src[pos + 1:end], line, spaced))
            pos = end + 1
            continue

        if ch in ("#", "~") and pos + 1 < n and src[pos + 1] != "=":
            m = _IDENT_RE.match(src, pos + 1)
            if m:
                kind = "TAG" if ch == "#" else "TILDE_ID"
                tokens.append(Token(kind, ch + m.group(0), line, spaced))
                pos = m.end()
                continue

        if (ch == "-" and pos + 1 < n and src[pos + 1].isdigit()
                and (spaced or not tokens or tokens[-1].kind in ("NEWLINE", "INDENT", "OP"))) or ch.isdigit():
            sign = "-" if ch == "-" else ""
            m = _NUM_RE.match(src, pos + len(sign))
            tokens.append(Token("NUMBER", sign + m.group(0), line, spaced))
            pos = m.end()
            continue

        m = _IDENT_RE.match(src, pos)
        if m:
            tokens.append(Token("IDENT", m.group(0), line, spaced))
            pos = m.end()
            continue

        op = next((o for o in _MULTI_OPS if src.startswith(o, pos)), None)
        if op:
            tokens.append(Token("OP", "!=" if op == "~=" else op, line, spaced))
            pos += len(op)
            continue

        if ch in _SINGLE_OPS:
            pdepth += (1 if ch in "([{" else -1 if ch in ")]}" else 0)
            tokens.append(Token("OP", ch, line, spaced))
            pos += 1
            continue

        raise Error(f"unexpected character {ch!r}", line, src_name)

    if tokens and tokens[-1].kind != "NEWLINE":
        tokens.append(Token("NEWLINE", "\n", line))
    while len(indents) > 1:
        indents.pop()
        tokens.append(Token("DEDENT", "", line))
    tokens.append(Token("EOF", "", line))
    return tokens
