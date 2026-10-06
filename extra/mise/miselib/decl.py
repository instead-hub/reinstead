import re

from . import state as S
from .common import *
from .typing import base

REF_FIELDS = {
    "n_to", "s_to", "e_to", "w_to", "nw_to", "ne_to", "sw_to", "se_to",
    "in_to", "out_to", "u_to", "d_to", "door_to", "walk_to", "next_to",
    "prev_to", "found_in", "talk_to",
}

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

    kind: meta | skip | require | lua | setup | const | global |
    class | fn | patch | verb | extend | talk | decl | unknown.
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
    m = re.match(r"^class\s+([A-Z]\w*)\s*(?:\(([^)]*)\))?$", key)
    if m:
        return "class", (m.group(1), m.group(2))
    if re.match(r"^fn\s+", key):
        return "fn", key
    if re.match(r"^patch\b", key):
        m = re.match(r"^patch\s+([@\w.+-]+)$", key)
        if not m:
            raise Error("patch needs a bare target: %s" % key)
        return "patch", m.group(1)
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
    m = re.match(r"^fn\s+([\w.+-]+)\s*(?:\(([^)]*)\))?\s*"
                 r"(?:->\s*([A-Za-z_]\w*\??))?$", key)
    if not m:
        raise Error("bad fn: " + key)
    name, params, ret = m.group(1), m.group(2), m.group(3) or "any"
    known = S.TYPES | (types or set()) | {"nil"}

    def check_type(pt, what):
        if base(pt) not in known or pt == "nil?":
            raise Error("fn %s: unknown type %r for %s"
                        % (name, pt, what))

    check_type(ret, "return")
    plist = []
    variadic = False
    if params is None:
        plist = [("s", "obj"), ("w", "obj"), ("wh", "obj")]
    elif params.strip():
        parts = [p.strip() for p in params.split(",") if p.strip()]
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
            plist.append((pn, pt))
    return name, plist, ret, variadic


def check_ref_value(where, key, v, ids=None):
    if isinstance(v, Text):
        raise Error("%s.%s: object reference must be a bare name, not a "
                    "quoted string (%r)" % (where, key, v.s))
    if isinstance(v, Bare):
        if not re.fullmatch(r"[#@\w]+", v.s, re.UNICODE):
            raise Error("%s.%s: object name must be an identifier without "
                        "spaces/hyphens (%r)" % (where, key, v.s))
        if ids is not None and v.s not in ids:
            raise Error("%s.%s: unknown object reference %r"
                        % (where, key, v.s))
        return
    if isinstance(v, list):
        for r in v:
            check_ref_value(where, key, r, ids)
        return


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
