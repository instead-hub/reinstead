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
        m = re.match(r"^if\s+(.+):$", text, re.S)
        if m:
            branches = [(m.group(1).strip(), None)]
            else_body = None
            j = i + 1
            while j < len(lines) and not lines[j][0].strip():
                j += 1
            if j >= len(lines) or lines[j][1] <= ind:
                parse_error(lno, "empty if")
            body, j = parse_logic(lines, j, lines[j][1])
            branches[0] = (branches[0][0], body)
            i = j
            while i < len(lines):
                raw2, ind2, _lno2 = lines[i]
                if not raw2.strip():
                    i += 1
                    continue
                t2 = strip_comment(raw2.strip())
                if ind2 == ind and t2.startswith("elseif "):
                    cond = t2[7:].rstrip(":").strip()
                    j = i + 1
                    while j < len(lines) and not lines[j][0].strip():
                        j += 1
                    if j >= len(lines) or lines[j][1] <= ind:
                        parse_error(lines[i][2], "empty elseif")
                    b2, j = parse_logic(lines, j, lines[j][1])
                    branches.append((cond, b2))
                    i = j
                elif ind2 == ind and t2 == "else:":
                    j = i + 1
                    while j < len(lines) and not lines[j][0].strip():
                        j += 1
                    if j >= len(lines) or lines[j][1] <= ind:
                        parse_error(lines[i][2], "empty else")
                    else_body, j = parse_logic(lines, j, lines[j][1])
                    i = j
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
