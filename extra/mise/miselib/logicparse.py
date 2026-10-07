import re

from .common import *


def _skip_blanks(lines, i):
    while i < len(lines) and not lines[i][0].strip():
        i += 1
    return i


def _branch_body(lines, header, indent, what):
    """Parse the indented body of a branch or loop header."""
    j = _skip_blanks(lines, header + 1)
    if j >= len(lines) or lines[j][1] <= indent:
        parse_error(lines[header][2], "empty %s" % what)
    return parse_logic(lines, j, lines[j][1])


def _parse_branches(lines, i, indent, style, branches):
    """Scan `elseif`/`when`/`else`/`default` continuations of a chain."""
    branch_kw = "elseif" if style == "if" else "when"
    else_kw = "else" if style == "if" else "default"
    else_body = None
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
            body, i = _branch_body(lines, i, indent, branch_kw)
            branches.append((cond, body))
        elif t2 == else_kw + ":":
            else_body, i = _branch_body(lines, i, indent, else_kw)
        elif (t2.startswith("when ") or t2 == "default:"
              or t2.startswith("elseif ") or t2 == "else:"):
            seen = t2.split(" ", 1)[0].rstrip(":")
            want = {"when": "elseif", "default": "else",
                    "elseif": "when", "else": "default"}[seen]
            parse_error(lno2, "use %s: instead of %s: in %s %s-chain"
                        % (want, seen, "an" if style == "if" else "a", style))
        else:
            break
    return i, else_body


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
        if text == "stop":
            stmts.append(("return", None, lno))
            i += 1
            continue
        if text == "pass":
            stmts.append(("return", "false", lno))
            i += 1
            continue
        m = re.match(r"^return\b\s*(.*)$", text, re.S)
        if m:
            stmts.append(("return", m.group(1) or None, lno))
            i += 1
            continue
        if text == "default:":
            parse_error(lno, "default: without when:")
        m = re.match(r"^(if|when)\s+(.+):$", text, re.S)
        if m:
            style = m.group(1)
            branches = [(m.group(2).strip(), None)]
            body, i = _branch_body(lines, i, ind, style)
            branches[0] = (branches[0][0], body)
            i, else_body = _parse_branches(lines, i, ind, style, branches)
            stmts.append(("if", branches, else_body, lno))
            continue
        m = re.match(r"^for\s+(.+):$", text, re.S)
        if m:
            body, i = _branch_body(lines, i, ind, "for")
            stmts.append(("for", dedent_rest(m.group(1).strip()), body, lno))
            continue
        stmts.append(("stmt", text, lno))
        i += 1
    return stmts, i
