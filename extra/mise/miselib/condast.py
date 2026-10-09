"""Condition trees for logic `if` heads.

The token stream is split structurally into an `and`/`or` tree; leaves
keep their tokens. Leaves are still parsed by the expression engine (via
their canonical text), so code and error text stay as before; narrowing
walks the tree instead of matching regexes on text.
"""
from .lex import lex_lua


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
    cuts = []
    depth = 0
    for i, t in enumerate(toks):
        if t in _OPEN:
            depth += 1
        elif t in _CLOSE:
            depth -= 1
        prev = cuts[-1] + 1 if cuts else 0
        if (depth == 0 and t == ("name", word) and i > prev
                and i + 1 < len(toks)):
            cuts.append(i)
    starts = [0] + [c + 1 for c in cuts]
    ends = cuts + [len(toks)]
    parts = [toks[a:b] for a, b in zip(starts, ends)]
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


def _narrow_simple(toks):
    """(name, want_nil) for `x`, `x == nil` or `not x`, else None."""
    if len(toks) == 1 and toks[0][0] == "name":
        return toks[0][1], False
    if (len(toks) == 3 and toks[0][0] == "name"
            and toks[2] == ("name", "nil")
            and toks[1] in (("op", "=="), ("op", "~="))):
        return toks[0][1], toks[1] == ("op", "==")
    if (len(toks) == 2 and toks[0] == ("name", "not")
            and toks[1][0] == "name"):
        return toks[1][1], True
    return None


def narrow_assume(node, env, negate):
    """Type narrowing implied by `node` being false (negate=True) / true."""
    if not isinstance(node, Leaf):
        return {}
    found = _narrow_simple(node.toks)
    if found is None:
        return {}
    name, want_nil = found
    t = env.get(name)
    if not t or not t.endswith("?"):
        return {}
    want = (not want_nil) if negate else want_nil
    return {name: "nil" if want else t[:-1]}


def narrow_cond(text, env, negate=False):
    """Narrowing from a whole condition being true/false (else branch)."""
    return narrow_assume(parse_cond(text), env, negate)
