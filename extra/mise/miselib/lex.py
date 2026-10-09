"""The lexer of the logic (`|`) expression language."""
import re

from .common import LintError
from . import messages as M
from . import patterns as P

_NUMBER_RE = re.compile(r"(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")
_OP_RE = re.compile(r"\.\.\.|\.\.|==|~=|<=|>=|\+=|-=|::|//|[+\-*/%^#<>=(){}\[\],;:.&]")
_IDENT_RE = re.compile(P.DSL_NAME)
_TILDE_IDENT_RE = re.compile("~" + P.DSL_NAME)


def _lex_skip(text, i, n):
    """Whitespace and `--` comments; the next index or None."""
    c = text[i]
    if c in " \t\r\n":
        return i + 1
    if text.startswith("--", i):
        j = text.find("\n", i)
        return n if j < 0 else j + 1
    return None


def _lex_quoted(text, i, n):
    quote = text[i]
    j = i + 1
    while j < n:
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == quote:
            j += 1
            break
        j += 1
    else:
        raise LintError(M.UNTERMINATED_STRING % text)
    return ("str", text[i:j]), j


def _lex_long_string(text, i, _n):
    j = text.find("]]", i + 2)
    if j < 0:
        raise LintError(M.UNTERMINATED_LONG_STRING % text)
    return ("str", text[i:j + 2]), j + 2


def _lex_number(text, i, _n):
    m = _NUMBER_RE.match(text, i)
    return ("num", m.group(0)), m.end()


def _lex_ident(text, i, pattern):
    m = pattern.match(text, i)
    return ("name", m.group(0)), m.end()


def _lex_name(text, i, _n):
    if text[i] == "~":
        return _lex_ident(text, i, _TILDE_IDENT_RE)
    return _lex_ident(text, i, _IDENT_RE)


def _lex_op(text, i):
    m = _OP_RE.match(text, i)
    if m:
        return ("op", m.group(0)), m.end()
    return None


def _is_quote(text, i, _n):
    return text[i] in "\"'"


def _is_long(text, i, _n):
    return text.startswith("[[", i)


def _is_number(text, i, n):
    c = text[i]
    return c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit())


def _is_name(text, i, n):
    c = text[i]
    return (c.isalpha() or c == "_" or (
        c == "~" and i + 1 < n and (text[i + 1].isalpha()
                                    or text[i + 1] == "_")))


# the token scanners, tried in order
LEX_FORMS = (
    (_is_quote, _lex_quoted),
    (_is_long, _lex_long_string),
    (_is_number, _lex_number),
    (_is_name, _lex_name),
)


def _lex_one(text, i, n):
    """The token at `i` and the index after it."""
    for matches, scan in LEX_FORMS:
        if matches(text, i, n):
            return scan(text, i, n)
    op = _lex_op(text, i)
    if op is None:
        c = text[i]
        raise LintError(M.BAD_CHARACTER_LOGIC % (c, text))
    return op


def _lex_step(toks, text, i, n):
    """Append one token (skipping whitespace/comments) and return the next i."""
    skipped = _lex_skip(text, i, n)
    if skipped is not None:
        return skipped
    tok, j = _lex_one(text, i, n)
    toks.append(tok)
    return j


def lex_lua(text):
    toks = []
    i = 0
    n = len(text)
    while i < n:
        i = _lex_step(toks, text, i, n)
    toks.append(("eof", ""))
    return toks
