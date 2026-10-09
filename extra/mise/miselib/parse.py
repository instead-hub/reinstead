import re

from .common import *
from .logicparse import parse_logic

def _skip_blank(lines, i):
    while i < len(lines) and not lines[i][0].strip():
        i += 1
    return i

def _list_value(lines, pos, ind, text, recurse):
    """Parse one list item; return `(item, consumed)`."""
    rest = text[1:].strip()
    if rest.startswith(("'", '"')):
        parse_error(pos + 1, "quotes are not allowed in list items")
    if rest:
        if re.match(r"\[(=*)\[", rest):
            item, lnxt = read_long(lines, pos, rest, pos + 1)
            return item, lnxt - pos
        return parse_scalar(rest, pos + 1, textmode=True), 1
    j = _skip_blank(lines, pos + 1)
    if j < len(lines) and lines[j][1] > ind and re.match(
            r"^-\s", lines[j][0].strip()):
        sub, snxt = recurse(lines, j, lines[j][1])
        return sub, snxt - pos
    parse_error(pos + 1, "empty list item")

def parse_list(lines, i, indent):
    items = []
    pos = i
    while pos < len(lines):
        raw, ind = lines[pos]
        if not raw.strip():
            pos += 1
            continue
        if ind < indent:
            break
        if ind > indent:
            parse_error(pos + 1, "unexpected indent: %r" % raw)
        text = strip_comment(raw.strip())
        if not re.match(r"^-(\s|$)", text):
            break
        item, consumed = _list_value(lines, pos, ind, text, parse_list)
        items.append(item)
        pos += consumed
    return items, pos

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

def _block_child(lines, pos, indent, key, recurse):
    j = _skip_blank(lines, pos + 1)
    if (j < len(lines) and re.match(r"^-\s", lines[j][0].strip())
            and lines[j][1] > indent):
        sub, cnxt = parse_list(lines, j, lines[j][1])
        return sub, cnxt - pos
    if j < len(lines) and lines[j][1] > indent:
        node, bnxt = recurse(lines, j, lines[j][1], key in HANDLER_KEYS)
        return node, bnxt - pos
    return Block(), 1

def _is_pipe(rest, _tm):
    return rest in ("|", "|lua")


def _is_long(rest, _tm):
    return rest.startswith("[[")


def _is_bracket(rest, tm):
    return rest.startswith(("{", "[")) and not tm


def _read_pipe(lines, pos, indent, rest, _tm):
    val, nxt = pipe_value(lines, pos + 1, indent, rest)
    return val, nxt - pos


def _read_long(lines, pos, _indent, rest, _tm):
    val, nxt = read_long(lines, pos, rest, pos + 1)
    return val, nxt - pos


def _read_bracket(lines, pos, _indent, rest, _tm):
    val, nxt = read_bracket(lines, pos, rest, pos + 1)
    return val, nxt - pos


# the special value forms of `key: value`, tried in order
VALUE_FORMS = (
    (_is_pipe, _read_pipe),
    (_is_long, _read_long),
    (_is_bracket, _read_bracket),
)


def _block_value(lines, pos, indent, rest, text_values, key):
    tm = text_values or key in TEXT_KEYS
    for matches, read in VALUE_FORMS:
        if matches(rest, tm):
            return read(lines, pos, indent, rest, tm)
    parts = split_list(rest)
    if len(parts) > 1 and not tm:
        return [parse_scalar(p, pos + 1) for p in parts], 1
    return parse_scalar(rest, pos + 1, tm), 1

def parse_block(lines, i, indent, text_values=False):
    blk = Block()
    pos = i
    while pos < len(lines):
        raw, ind = lines[pos]
        if ind < indent:
            break
        if ind > indent:
            parse_error(pos + 1, "unexpected indent: %r" % raw)
        text = strip_comment(raw.strip())
        if not text:
            pos += 1
            continue
        key, rest = split_key(text)
        if key is None:
            parse_error(pos + 1, "expected 'key: value'")
        key, rest = key.strip(), rest.strip()
        line_no = pos + 1
        parsed = (_block_child(lines, pos, indent, key, parse_block)
                  if rest == ""
                  else _block_value(lines, pos, indent, rest, text_values,
                                    key))
        val, consumed = parsed
        blk.add(key, val, line_no)
        pos += consumed
    return blk, pos

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
