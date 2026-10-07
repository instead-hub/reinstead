import re

from .common import *

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
            branch_kw = "elseif" if style == "if" else "when"
            else_kw = "else" if style == "if" else "default"
            branches = [(m.group(2).strip(), None)]
            else_body = None
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j >= len(lines) or lines[j][1] <= ind:
                parse_error(lno, "empty %s" % style)
            body, j = parse_logic(lines, j, lines[j][1])
            branches[0] = (branches[0][0], body)
            i = j
            while i < len(lines):
                raw2, ind2, lno2 = lines[i]
                if not raw2.strip():
                    i += 1
                    continue
                t2 = strip_comment(raw2.strip())
                if ind2 != ind:
                    break
                if t2.startswith(branch_kw + " "):
                    cond = t2[len(branch_kw):].rstrip(":").strip()
                    j = i + 1
                    while j < len(lines) and not lines[j][0].strip():
                        j += 1
                    if j >= len(lines) or lines[j][1] <= ind:
                        parse_error(lno2, "empty %s" % branch_kw)
                    b2, j = parse_logic(lines, j, lines[j][1])
                    branches.append((cond, b2))
                    i = j
                elif t2 == else_kw + ":":
                    j = i + 1
                    while j < len(lines) and not lines[j][0].strip():
                        j += 1
                    if j >= len(lines) or lines[j][1] <= ind:
                        parse_error(lno2, "empty %s" % else_kw)
                    else_body, j = parse_logic(lines, j, lines[j][1])
                    i = j
                elif (t2.startswith("when ") or t2 == "default:"
                      or t2.startswith("elseif ") or t2 == "else:"):
                    seen = t2.split(" ", 1)[0].rstrip(":")
                    want = {"when": "elseif", "default": "else",
                            "elseif": "when", "else": "default"}[seen]
                    parse_error(lno2, "use %s: instead of %s: in %s %s-chain"
                                % (want, seen,
                                   "an" if style == "if" else "a", style))
                else:
                    break
            stmts.append(("if", branches, else_body, lno))
            continue
        m = re.match(r"^for\s+(.+):$", text, re.S)
        if m:
            header = dedent_rest(m.group(1).strip())
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j >= len(lines) or lines[j][1] <= ind:
                parse_error(lno, "empty for")
            body, j = parse_logic(lines, j, lines[j][1])
            stmts.append(("for", header, body, lno))
            i = j
            continue
        stmts.append(("stmt", text, lno))
        i += 1
    return stmts, i
