import re

from . import state as S
from .common import *
from .typing import canon_type, split_types, type_error

PRESETS = {
    "obj": ("obj", []),
    "scenery": ("obj", ["scenery"]),
    "room": ("room", []),
    "door": ("door", []),
    "story": ("cutscene", []),
    "ending": ("gameover", []),
}

META_KEYS = ("name", "version", "author", "info")
SKIP_KEYS = ("lang", "fmt", "include")


def classify(key):
    """Return (kind, info) for a top-level key.

    kind: meta | skip | require | lua | setup | const | global | refs |
    class | fn | impl | verb | extend | talk | decl | unknown.
    info: class -> (name, parent), decl -> (kind, ident), others -> ident.
    """
    if key in META_KEYS:
        return "meta", None
    if key in SKIP_KEYS:
        return "skip", None
    if "'" in key or '"' in key:
        raise Error("quotes are not allowed in declarations: %s" % key)
    if key in ("require", "lua", "setup", "const", "global"):
        return key, None
    if key == "refs":
        return "refs", None
    if key == "extend refs":
        return "extend_refs", None
    if key == "props":
        return "props", None
    m = re.match(r"^class\s+([A-Z]\w*)\s*(?:\(([^)]*)\))?$", key)
    if m:
        return "class", (m.group(1), m.group(2))
    if re.match(r"^mixin\b", key):
        m = re.match(r"^mixin\s+([A-Z]\w*)$", key)
        if not m:
            raise Error("mixin needs a name: " + key)
        return "mixin", m.group(1)
    if re.match(r"^fn\s+", key):
        return "fn", key
    if re.match(r"^impl\b", key):
        m = re.match(r"^impl\s+([@\w.+-]+)$", key)
        if not m:
            raise Error("impl needs a bare target: %s" % key)
        return "impl", m.group(1)
    m = re.match(r"^event\s+([A-Z]\w*)$", key)
    if m:
        return "event_decl", m.group(1)
    m = re.match(r"^type\s+([a-z_]\w*)$", key)
    if m:
        return "type", m.group(1)
    m = re.match(r"^extend\s+type\s+([a-z_]\w*)$", key)
    if m:
        return "extend_type", m.group(1)
    if re.match(r"^extend\b", key):
        m = re.match(r"^extend\s+#([^\W\d]\w*)$", key, re.UNICODE)
        if not m:
            raise Error("extend needs a bare #Tag: %s" % key)
        return "extend", "#" + m.group(1)
    kind, ident = decl_key(key)
    if not kind:
        return "unknown", None
    if kind in ("verb", "talk"):
        return kind, ident
    if kind in PRESETS or re.fullmatch(r"[A-Z][\w]*", kind):
        return "decl", (kind, ident)
    return "unknown", (kind, ident)


def parse_fn_sig(key, types=None):
    m = re.match(r"^fn\s+([\w.+-]+)\s*", key)
    if not m:
        raise Error("bad fn: " + key)
    name = m.group(1)
    rest = key[m.end():].strip()
    params = None
    if rest.startswith("("):
        depth, end = 0, None
        for i, c in enumerate(rest):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            raise Error("bad fn: " + key)
        params = rest[1:end]
        rest = rest[end + 1:].strip()
    ret = "any"
    if rest:
        if not rest.startswith("->"):
            raise Error("bad fn: " + key)
        ret = rest[2:].strip()
        if not ret:
            raise Error("bad fn: " + key)
    known = S.TYPES | (types or set()) | {"nil"}

    def check_type(pt, what):
        msg = type_error(known, pt)
        if msg:
            raise Error("fn %s: %s for %s" % (name, msg, what))

    plist = []
    variadic = False
    if params is None:
        plist = [("s", "obj"), ("w", "obj"), ("wh", "obj")]
    elif params.strip():
        parts = split_types(params)
        for idx, p in enumerate(parts):
            if p == "...":
                if idx != len(parts) - 1:
                    raise Error("fn %s: ... must be the last parameter"
                                % name)
                variadic = True
                continue
            if ":" in p:
                pn, pt = p.split(":", 1)
                pn, pt = pn.strip(), pt.strip()
            else:
                pn, pt = p, "any"
            if not re.fullmatch(r"[^\W\d]\w*", pn, re.UNICODE):
                raise Error("fn %s: bad parameter %r" % (name, pn))
            check_type(pt, pn)
            plist.append((pn, canon_type(known, pt)))
    seen_optional = False
    for pn, pt in plist:
        if pt == "nil" or pt.endswith("?"):
            seen_optional = True
        elif seen_optional:
            raise Error("fn %s: required parameter %s after optional"
                        % (name, pn))
    check_type(ret, "return")
    if ret != "any":
        ret = canon_type(known, ret)
    return name, plist, ret, variadic


def check_ref_value(where, key, v, ids=None, allow_text=False, in_list=False):
    if isinstance(v, list):
        for r in v:
            check_ref_value(where, key, r, ids, allow_text, True)
        return
    if isinstance(v, Text):
        if not (allow_text and in_list):
            raise Error("%s.%s: object reference must be a bare name, not a "
                        "quoted string (%r)" % (where, key, v.s))
        name = v.s.strip()
    elif isinstance(v, Bare):
        if not re.fullmatch(r"[#@\w]+", v.s, re.UNICODE):
            raise Error("%s.%s: object name must be an identifier without "
                        "spaces/hyphens (%r)" % (where, key, v.s))
        name = v.s
    elif in_list:
        raise Error("%s.%s: expected object reference, got %s"
                    % (where, key, type(v).__name__.lower()))
    else:
        return
    if ids is not None and name not in ids:
        raise Error("%s.%s: unknown object reference %r" % (where, key, name))


def decl_key(key):
    m = re.match(r"^([A-Za-z][A-Za-z0-9_]*)(?:\s+([\w#.+-]+))?$", key)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def sym_text(v):
    if isinstance(v, (Bare, Text)):
        return v.s
    raise Error("expected expression")


def is_true(v):
    return isinstance(v, Bool) and v.s == "true"
