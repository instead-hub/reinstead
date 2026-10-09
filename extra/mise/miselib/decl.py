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
    simple = _classify_simple(key)
    if simple is not None:
        return simple
    tagged = _classify_tagged(key)
    if tagged is not None:
        return tagged
    return _classify_decl(key)


SIMPLE_KINDS = {
    "require": "require",
    "lua": "lua",
    "setup": "setup",
    "const": "const",
    "global": "global",
    "refs": "refs",
    "extend refs": "extend_refs",
    "props": "props",
}


def _classify_simple(key):
    """Plain keyword and reserved-tag kinds, else None."""
    kind = SIMPLE_KINDS.get(key)
    if kind is None:
        return None
    return kind, None


def _class_kind(_key, m):
    return "class", (m.group(1), m.group(2))


def _mixin_kind(_key, m):
    return "mixin", m.group(1)


def _fn_kind(key, _m):
    return "fn", key


def _impl_kind(_key, m):
    return "impl", m.group(1)


def _event_kind(_key, m):
    return "event_decl", m.group(1)


def _type_kind(_key, m):
    return "type", m.group(1)


def _extend_type_kind(_key, m):
    return "extend_type", m.group(1)


def _extend_kind(_key, m):
    return "extend", "#" + m.group(1)


# the tagged top-level forms in lookup order: a compiled pattern and the
# builder of its (kind, info)
TAGGED_FORMS = (
    (re.compile(r"^class\s+([A-Z]\w*)\s*(?:\(([^)]*)\))?$"), _class_kind),
    (re.compile(r"^mixin\s+([A-Z]\w*)$"), _mixin_kind),
    (re.compile(r"^fn\s+"), _fn_kind),
    (re.compile(r"^impl\s+([@\w.+-]+)$"), _impl_kind),
    (re.compile(r"^event\s+([A-Z]\w*)$"), _event_kind),
    (re.compile(r"^type\s+([a-z_]\w*)$"), _type_kind),
    (re.compile(r"^extend\s+type\s+([a-z_]\w*)$"), _extend_type_kind),
    (re.compile(r"^extend\s+#([^\W\d]\w*)$", re.UNICODE), _extend_kind),
)

# the prefixes of those forms that must carry a name
TAGGED_NAMES = (
    (re.compile(r"^mixin\b"), "mixin needs a name: %s"),
    (re.compile(r"^impl\b"), "impl needs a bare target: %s"),
    (re.compile(r"^extend\b"), "extend needs a bare #Tag: %s"),
)


def _need_tagged_name(key):
    for pat, msg in TAGGED_NAMES:
        if pat.match(key):
            raise Error(msg % key)


def _classify_tagged(key):
    """class/mixin/fn/impl tags, event/type/extend tags, else None."""
    for pat, build in TAGGED_FORMS:
        m = pat.match(key)
        if m:
            return build(key, m)
    _need_tagged_name(key)
    return None


def _classify_decl(key):
    """Object/verb/talk declarations, else unknown."""
    kind, ident = decl_key(key)
    if not kind:
        return "unknown", None
    if kind in ("verb", "talk"):
        return kind, ident
    if kind in PRESETS or re.fullmatch(r"[A-Z][\w]*", kind):
        return "decl", (kind, ident)
    return "unknown", (kind, ident)


def _fn_header(key):
    """`fn name(params) -> ret` -> (name, params|None, ret|None)."""
    m = re.match(r"^fn\s+([\w.+-]+)\s*", key)
    if not m:
        raise Error("bad fn: " + key)
    name = m.group(1)
    rest = key[m.end():].strip()
    if not rest.startswith("("):
        return _fn_tail(key, name, None, rest)
    end = _paren_end(rest)
    if end is None:
        raise Error("bad fn: " + key)
    return _fn_tail(key, name, rest[1:end], rest[end + 1:].strip())


def _paren_end(rest):
    """Index of the `)` closing the leading `(` of rest, or None."""
    depth = 0
    for i, c in enumerate(rest):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _fn_tail(key, name, params, rest):
    """Parse the optional `-> type` part of an `fn` header."""
    if not rest:
        return name, params, None
    if not rest.startswith("->") or not rest[2:].strip():
        raise Error("bad fn: " + key)
    return name, params, rest[2:].strip()


def _check_type(name, known, pt, what):
    msg = type_error(known, pt)
    if msg:
        raise Error("fn %s: %s for %s" % (name, msg, what))


def _split_param(p):
    """Split `name: type` or a bare parameter name."""
    if ":" in p:
        pn, pt = p.split(":", 1)
        return pn.strip(), pt.strip()
    return p, "any"


def _fn_params(name, params, known):
    """`(a: T, ...)` text -> (plist, variadic)."""
    if params is None:
        return [("s", "obj"), ("w", "obj"), ("wh", "obj")], False
    plist = []
    if not params.strip():
        return plist, False
    parts = split_types(params)
    for idx, p in enumerate(parts):
        if p == "...":
            if idx != len(parts) - 1:
                raise Error("fn %s: ... must be the last parameter" % name)
            return plist, True
        pn, pt = _split_param(p)
        if not re.fullmatch(r"[^\W\d]\w*", pn, re.UNICODE):
            raise Error("fn %s: bad parameter %r" % (name, pn))
        _check_type(name, known, pt, pn)
        plist.append((pn, canon_type(known, pt)))
    return plist, False


def _is_optional(pt):
    return pt == "nil" or pt.endswith("?")


def _check_optional_order(name, plist):
    first_opt = next((i for i, (_pn, pt) in enumerate(plist)
                      if _is_optional(pt)), None)
    if first_opt is None:
        return
    for pn, pt in plist[first_opt + 1:]:
        if not _is_optional(pt):
            raise Error("fn %s: required parameter %s after optional"
                        % (name, pn))


def parse_fn_sig(key, types=None):
    name, params, ret_text = _fn_header(key)
    known = S.TYPES | (types or set()) | {"nil"}
    plist, variadic = _fn_params(name, params, known)
    _check_optional_order(name, plist)
    if ret_text is None:
        return name, plist, "any", variadic
    _check_type(name, known, ret_text, "return")
    return name, plist, canon_type(known, ret_text), variadic


def check_ref_value(where, key, v, ids=None, allow_text=False, in_list=False):
    if isinstance(v, list):
        for r in v:
            check_ref_value(where, key, r, ids, allow_text, True)
        return
    if isinstance(v, Text):
        if not (allow_text and in_list):
            raise Error("%s.%s: object reference must be a bare name, not a "
                        "quoted string (%r)" % (where, key, v.s))
        return _check_ref_name(where, key, v.s.strip(), ids)
    if isinstance(v, Bare):
        if not re.fullmatch(r"[#@\w]+", v.s, re.UNICODE):
            raise Error("%s.%s: object name must be an identifier without "
                        "spaces/hyphens (%r)" % (where, key, v.s))
        return _check_ref_name(where, key, v.s, ids)
    if in_list:
        raise Error("%s.%s: expected object reference, got %s"
                    % (where, key, type(v).__name__.lower()))


def _check_ref_name(where, key, name, ids):
    """Reject a reference name that is not among the declared ids."""
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
