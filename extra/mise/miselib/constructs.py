"""One registry of the DSL constructs.

Every construct is described in one place: how its key is recognized
(`classify`), its props scope, the engine constructor it generates
(`PRESETS`) and its top-level emission route (`EMIT_ROUTES`). The
pipeline reads these tables — classify -> prescan -> emit — so adding a
construct is one entry here plus an emitter for a new route.
"""
import re

from . import messages as M
from . import patterns as P
from .common import Error

# --- recognition ------------------------------------------------------

META_KEYS = ("name", "version", "author", "info")
SKIP_KEYS = ("lang", "fmt", "include")

_DECL_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)(?:\s+([\w#.+-]+))?$")

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


def _props_kind(_key, m):
    return "props", [s.strip() for s in m.group(1).split(",")]


# the tagged top-level forms in lookup order: a compiled pattern and the
# builder of its (kind, info)
TAGGED_FORMS = (
    (re.compile(r"^class\s+(" + P.CLASS_NAME + r")\s*(?:\(([^)]*)\))?$"), _class_kind),
    (re.compile(r"^mixin\s+(" + P.CLASS_NAME + r")$"), _mixin_kind),
    (re.compile(r"^fn\s+"), _fn_kind),
    (re.compile(r"^impl\s+([@\w.+-]+)$"), _impl_kind),
    (re.compile(r"^event\s+(" + P.CLASS_NAME + r")$"), _event_kind),
    (re.compile(r"^type\s+([a-z_]\w*)$"), _type_kind),
    (re.compile(r"^extend\s+type\s+([a-z_]\w*)$"), _extend_type_kind),
    (re.compile(r"^extend\s+#(" + P.DSL_NAME + r")$", re.UNICODE), _extend_kind),
    (re.compile(r"^props\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)$"),
     _props_kind),
)

# the prefixes of those forms that must carry a name
TAGGED_NAMES = (
    (re.compile(r"^mixin\b"), M.MIXIN_NEEDS_NAME),
    (re.compile(r"^impl\b"), M.IMPL_NEEDS_TARGET),
    (re.compile(r"^extend\b"), M.EXTEND_NEEDS_TAG),
)


def decl_key(key):
    m = _DECL_KEY_RE.match(key)
    if not m:
        return None, None
    return m.group(1), m.group(2)


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
    if PRESETS.get(kind) or P.CLASS_RE.fullmatch(kind):
        return "decl", (kind, ident)
    return "unknown", (kind, ident)


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
        raise Error(M.QUOTES_ARE_NOT_ALLOWED_DECLARATIONS % key)
    if key in SIMPLE_KINDS:
        return SIMPLE_KINDS[key], None
    tagged = _classify_tagged(key)
    if tagged is not None:
        return tagged
    return _classify_decl(key)


# --- object kinds -----------------------------------------------------

class Preset:
    """An object kind: engine constructor, fixed attrs, props scope."""

    __slots__ = ("ctor", "attrs", "scope", "parent")

    def __init__(self, ctor, scope, attrs=(), parent=None):
        self.ctor = ctor
        self.attrs = tuple(attrs)
        self.scope = scope
        self.parent = parent


PRESETS = {
    "obj": Preset("obj", "obj"),
    "room": Preset("room", "room", parent="obj"),
    "door": Preset("door", "door", parent="obj"),
    "story": Preset("cutscene", "story", parent="room"),
    "ending": Preset("gameover", "ending", parent="room"),
}

# names a class cannot take: they already name a construct or a meta key
RESERVED_KINDS = (frozenset(PRESETS) | frozenset(SIMPLE_KINDS)
                  | frozenset(META_KEYS) | frozenset(SKIP_KEYS)
                  | {"verb", "talk", "extend"})

# structural props scopes (not object kinds): their engine parent only
STRUCT_SCOPES = {
    "talk": "room",
    "option": "obj",
    "hero": "obj",
    "game": "obj",
}


def prop_scopes():
    """Props scope -> its direct engine parent."""
    scopes = {name: (parent,) for name, parent in STRUCT_SCOPES.items()}
    for preset in PRESETS.values():
        scopes[preset.scope] = (preset.parent,) if preset.parent else ()
    return scopes


# --- emission ---------------------------------------------------------

# kind -> the top-level emitter; meta/skip/require/fn are handled by the
# pipeline itself, the rest name an Emitter route
EMIT_ROUTES = {
    "meta": "meta",
    "skip": "skip",
    "require": "require",
    "fn": "fn",
    "lua": "lua",
    "class": "class",
    "impl": "impl",
    "setup": "setup",
    "const": "const",
    "global": "global",
    "event_decl": "event",
    "decl": "decl",
    "verb": "decl",
    "extend": "decl",
    "talk": "decl",
    "props": "skip",
    "type": "skip",
    "extend_type": "skip",
    "mixin": "skip",
    "refs": "skip",
    "extend_refs": "skip",
}
