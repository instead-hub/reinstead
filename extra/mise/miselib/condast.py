"""Condition trees for logic `if` heads.

The token stream is split structurally into an `and`/`or` tree; leaves
keep their tokens. Leaves are still parsed by the expression engine (via
their canonical text), so code and error text stay as before; narrowing
walks the tree instead of matching regexes on text.
"""
from .expr import lex_lua


class Leaf:
    def __init__(self, toks):
        self.toks = toks


class Op:
    def __init__(self, op, parts):
        self.op = op
        self.parts = parts


_OPEN = (("op", "("), ("op", "["), ("op", "{"))
_CLOSE = (("op", ")"), ("op", "]"), ("op", "}"))


def _split(toks, word):
    """Split tokens on top-level `word`; a trailing operator is kept."""
    parts, cur = [], []
    depth = 0
    for i, t in enumerate(toks):
        if t in _OPEN:
            depth += 1
        elif t in _CLOSE:
            depth -= 1
        if (depth == 0 and t == ("name", word) and cur
                and i + 1 < len(toks)):
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    parts.append(cur)
    return [p for p in parts if p] or [toks]


def _and(toks):
    parts = _split(toks, "and")
    if len(parts) > 1:
        return Op("and", [Leaf(p) for p in parts])
    return Leaf(parts[0])


def parse_cond(text):
    parts = _split([t for t in lex_lua(text) if t[0] != "eof"], "or")
    if len(parts) > 1:
        return Op("or", [_and(p) for p in parts])
    return _and(parts[0])


def leaf_text(node):
    return " ".join(t[1] for t in node.toks)


def narrow_assume(node, env, negate):
    """Type narrowing implied by `node` being false (negate=True) / true."""
    if not isinstance(node, Leaf):
        return {}
    toks = node.toks
    name = want_nil = None
    if len(toks) == 1 and toks[0][0] == "name":
        name, want_nil = toks[0][1], False
    elif (len(toks) == 3 and toks[0][0] == "name"
          and toks[2] == ("name", "nil")
          and toks[1] in (("op", "=="), ("op", "~="))):
        name, want_nil = toks[0][1], toks[1] == ("op", "==")
    elif (len(toks) == 2 and toks[0] == ("name", "not")
          and toks[1][0] == "name"):
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
    return narrow_assume(parse_cond(text), env, negate)
