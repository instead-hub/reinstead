"""Condition trees for logic `if` heads.

The condition text is split structurally (depth- and string-aware) into
an `and`/`or` tree with source-slice leaves. Leaves are still parsed by
the expression engine, so code and error text stay exactly as before;
narrowing now walks the tree instead of matching regexes on text.
"""
import re

from .common import LintError
from .expr import lex_lua


class Leaf:
    def __init__(self, text):
        self.text = text


class Op:
    def __init__(self, op, parts):
        self.op = op
        self.parts = parts


def _find_top(text, word):
    """Return (start, end) spans of top-level ` word ` separators."""
    sep = " %s " % word
    spans = []
    i, n = 0, len(text)
    depth = 0
    while i < n:
        c = text[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n and text[i] != q:
                if text[i] == "\\":
                    i += 1
                i += 1
            i += 1
            continue
        if c == "[":
            m = re.match(r"\[(=*)\[", text[i:])
            if m:
                close = "]" + m.group(1) + "]"
                j = text.find(close, i + m.end())
                if j < 0:
                    raise LintError("unterminated long string: %s" % text)
                i = j + len(close)
                continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and text.startswith(sep, i):
            spans.append((i, i + len(sep)))
            i += len(sep)
            continue
        i += 1
    return spans


def _split(text, spans):
    parts, last = [], 0
    for a, b in spans:
        parts.append(text[last:a].strip())
        last = b
    parts.append(text[last:].strip())
    return [p for p in parts if p]


def _parse_and(text):
    parts = _split(text, _find_top(text, "and"))
    if len(parts) > 1:
        return Op("and", [Leaf(p) for p in parts])
    return Leaf(parts[0] if parts else text.strip())


def parse_cond(text):
    parts = _split(text, _find_top(text, "or"))
    if len(parts) > 1:
        return Op("or", [_parse_and(p) for p in parts])
    return _parse_and(parts[0] if parts else text.strip())


def _toks(text):
    try:
        return [t for t in lex_lua(text) if t[0] != "eof"]
    except LintError:
        return None


def narrow_assume(node, env, negate):
    """Type narrowing implied by `node` being false (negate=True) / true."""
    if not isinstance(node, Leaf):
        return {}
    toks = _toks(node.text)
    if not toks:
        return None
    name = want_nil = None
    if len(toks) == 1 and toks[0][0] == "name":
        name, want_nil = toks[0][1], False
    elif len(toks) == 3 and toks[0][0] == "name" \
            and toks[2] == ("name", "nil"):
        if toks[1] == ("op", "~="):
            name, want_nil = toks[0][1], False
        elif toks[1] == ("op", "=="):
            name, want_nil = toks[0][1], True
    elif len(toks) == 2 and toks[0] == ("name", "not") \
            and toks[1][0] == "name":
        name, want_nil = toks[1][1], True
    if name is None:
        return {}
    if negate:
        want_nil = not want_nil
    t = env.get(name)
    if not t or not t.endswith("?"):
        return {}
    return {name: "nil" if want_nil else t[:-1]}


def narrow_cond(text, env, negate=False):
    """Narrowing from a whole condition being true/false (else branch)."""
    d = narrow_assume(parse_cond(text), env, negate)
    return d or {}
