import re

from . import state as S
from .common import *

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

    kind: meta | skip | require | events | lua | setup | const | global |
    class | fn | patch | verb | extend | talk | decl | unknown.
    info: class -> (name, parent), decl -> (kind, ident), others -> ident.
    """
    if key in META_KEYS:
        return "meta", None
    if key in SKIP_KEYS:
        return "skip", None
    if key in ("require", "events", "lua", "setup", "const", "global"):
        return key, None
    m = re.match(r"^class\s+([A-Z]\w*)\s*(?:\(([^)]*)\))?$", key)
    if m:
        return "class", (m.group(1), m.group(2))
    if re.match(r"^fn\s+", key):
        return "fn", key
    m = re.match(r"^patch\s+(.+)$", key)
    if m:
        return "patch", m.group(1).strip()
    kind, ident = decl_key(key)
    if not kind:
        return "unknown", None
    if kind in ("verb", "extend", "talk"):
        return kind, ident
    if kind in PRESETS or re.fullmatch(r"[A-Z][\w]*", kind):
        return "decl", (kind, ident)
    return "unknown", (kind, ident)


def parse_fn_sig(key):
    m = re.match(r"^fn\s+([\w.+-]+)\s*(?:\(([^)]*)\))?\s*"
                 r"(?:->\s*([A-Za-z_]\w*))?$", key)
    if not m:
        raise Error("bad fn: " + key)
    name, params, ret = m.group(1), m.group(2), m.group(3) or "any"
    if ret not in S.TYPES:
        raise Error("fn %s: unknown return type %r" % (name, ret))
    plist = []
    variadic = False
    if params is None:
        plist = [("s", "obj"), ("w", "obj"), ("wh", "obj")]
    elif params.strip():
        for p in params.split(","):
            p = p.strip()
            if not p:
                continue
            if p == "...":
                variadic = True
                continue
            if ":" in p:
                pn, pt = p.split(":", 1)
                pn, pt = pn.strip(), pt.strip()
            else:
                pn, pt = p, "any"
            if not re.fullmatch(r"[^\W\d]\w*", pn, re.UNICODE):
                raise Error("fn %s: bad parameter %r" % (name, pn))
            if pt not in S.TYPES:
                raise Error("fn %s: unknown type %r for %s" % (name, pt, pn))
            plist.append((pn, pt))
    return name, plist, ret, variadic


def check_ref_value(where, key, v):
    if isinstance(v, Text):
        raise Error("%s.%s: object reference must be a bare name, not a "
                    "quoted string (%r)" % (where, key, v.s))
    if isinstance(v, Bare):
        if not re.fullmatch(r"[#@\w]+", v.s, re.UNICODE):
            raise Error("%s.%s: object name must be an identifier without "
                        "spaces/hyphens (%r)" % (where, key, v.s))
        return
    if isinstance(v, list):
        for r in v:
            check_ref_value(where, key, r)
        return


def decl_key(key):
    m = re.match(
        r'^([A-Za-z][A-Za-z0-9_]*)(?:\s+(?:"([^"]+)"|\'([^\']+)\'|([\w#.+-]+)))?$',
        key)
    if not m:
        return None, None
    ident = m.group(2) or m.group(3) or m.group(4)
    return m.group(1), ident


def sym_text(v):
    if isinstance(v, (Bare, Text)):
        return v.s
    raise Error("expected expression")


def is_true(v):
    return isinstance(v, Bool) and v.s == "true"
