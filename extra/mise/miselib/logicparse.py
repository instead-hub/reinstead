import re

from .common import *


def _skip_blanks(lines, i):
    while i < len(lines) and not lines[i][0].strip():
        i += 1
    return i


def _branch_body(lines, header, indent, what, recurse):
    """Parse the indented body of a branch or loop header."""
    j = _skip_blanks(lines, header + 1)
    if j >= len(lines) or lines[j][1] <= indent:
        parse_error(lines[header][2], "empty %s" % what)
    return recurse(lines, j, lines[j][1])


def _is_chain_kw(text):
    """True for any branch keyword of either chain style."""
    return (text.startswith("when ") or text == "default:"
            or text.startswith("elseif ") or text == "else:")


def _chain_error(text, lno, style):
    """Report a branch keyword that belongs to the other chain style."""
    seen = text.split(" ", 1)[0].rstrip(":")
    want = {"when": "elseif", "default": "else",
            "elseif": "when", "else": "default"}[seen]
    parse_error(lno, "use %s: instead of %s: in %s %s-chain"
                % (want, seen, "an" if style == "if" else "a", style))


def _parse_branches(lines, i, indent, style, branches, recurse):
    """Scan `elseif`/`when`/`else`/`default` continuations of a chain."""
    branch_kw = "elseif" if style == "if" else "when"
    else_kw = "else" if style == "if" else "default"
    else_bodies = []
    while i < len(lines):
        raw2, ind2, lno2 = lines[i]
        if not raw2.strip():
            i += 1
            continue
        t2 = strip_comment(raw2.strip())
        if ind2 != indent:
            break
        if t2.startswith(branch_kw + " "):
            cond = t2[len(branch_kw):].rstrip(":").strip()
            body, i = _branch_body(lines, i, indent, branch_kw, recurse)
            branches.append((cond, body))
        elif t2 == else_kw + ":":
            body2, i = _branch_body(lines, i, indent, else_kw, recurse)
            else_bodies.append(body2)
        elif _is_chain_kw(t2):
            _chain_error(t2, lno2, style)
        else:
            break
    return i, (else_bodies[-1] if else_bodies else None)


def _logic_stmt(lines, i, ind, text, lno, recurse):
    """Parse one logical line at `i`; returns (stmt, next_i)."""
    if text == "stop":
        return ("return", None, lno), i + 1
    if text == "pass":
        return ("return", "false", lno), i + 1
    m = re.match(r"^return\b\s*(.*)$", text, re.S)
    if m:
        return ("return", m.group(1) or None, lno), i + 1
    if text == "default:":
        parse_error(lno, "default: without when:")
    return _logic_block(lines, i, ind, text, lno, recurse)


def _logic_block(lines, i, ind, text, lno, recurse):
    """Parse an if/when chain or for loop; else a plain statement."""
    m_if = re.match(r"^(if|when)\s+(.+):$", text, re.S)
    if m_if:
        style = m_if.group(1)
        branches = [(m_if.group(2).strip(), None)]
        if_body, i = _branch_body(lines, i, ind, style, recurse)
        branches[0] = (branches[0][0], if_body)
        i, else_body = _parse_branches(lines, i, ind, style, branches,
                                       recurse)
        return ("if", branches, else_body, lno), i
    m_for = re.match(r"^for\s+(.+):$", text, re.S)
    if m_for:
        for_body, i = _branch_body(lines, i, ind, "for", recurse)
        return ("for", dedent_rest(m_for.group(1).strip()), for_body, lno), i
    return ("stmt", text, lno), i + 1


def parse_logic(lines, i, indent):
    stmts = []
    while i < len(lines):
        raw, ind, lno = lines[i]
        if not raw.strip():
            i += 1
            continue
        if ind < indent:
            break
        if ind > indent:
            parse_error(lno, "unexpected indent: %r" % raw)
        text = strip_comment(raw.strip())
        while not long_balanced(text) and i + 1 < len(lines):
            i += 1
            text += "\n" + lines[i][0]
        text = dedent_rest(text)
        if not text:
            i += 1
            continue
        stmt, i = _logic_stmt(lines, i, ind, text, lno, parse_logic)
        stmts.append(stmt)
    return stmts, i
