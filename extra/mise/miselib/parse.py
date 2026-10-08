import re

from .common import *
from .logicparse import parse_logic

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
        if rest.startswith(("'", '"')):
            parse_error(i + 1, "quotes are not allowed in list items")
        if rest:
            if re.match(r"\[(=*)\[", rest):
                item, i = read_long(lines, i, rest, i + 1)
                items.append(item)
            else:
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
        key, rest = split_key(text)
        if key is None:
            parse_error(i + 1, "expected 'key: value'")
        key, rest = key.strip(), rest.strip()
        line_no = i + 1
        if rest == "":
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j < len(lines) and re.match(
                    r"^-\s", lines[j][0].strip()) and lines[j][1] > indent:
                child, i = parse_list(lines, j, lines[j][1])
                blk.add(key, child, line_no)
            elif j < len(lines) and lines[j][1] > indent:
                child, i = parse_block(lines, j, lines[j][1],
                                       key in HANDLER_KEYS)
                blk.add(key, child, line_no)
            else:
                blk.add(key, Block(), line_no)
                i += 1
        elif rest in ("|", "|lua"):
            val, i = pipe_value(lines, i + 1, indent, rest)
            blk.add(key, val, line_no)
        elif rest.startswith("[["):
            val, i = read_long(lines, i, rest, line_no)
            blk.add(key, val, line_no)
        elif (rest.startswith(("{", "["))
              and not (text_values or key in TEXT_KEYS)):
            val, i = read_bracket(lines, i, rest, line_no)
            blk.add(key, val, line_no)
        else:
            tm = text_values or key in TEXT_KEYS
            parts = split_list(rest)
            if len(parts) > 1 and not tm:
                blk.add(key, [parse_scalar(p, line_no) for p in parts],
                        line_no)
            else:
                blk.add(key, parse_scalar(rest, line_no, tm), line_no)
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
