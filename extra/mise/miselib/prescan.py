import os
import re

from . import state as S
from .common import *
from .parse import parse_source
from .emit import *

def collect_ids(root):
    ids = {}

    def add_from(block):
        for key, val in block.items:
            kind, ident = decl_key(key)
            if not kind or not ident:
                continue
            if kind not in PRESETS and kind != "talk" and not re.fullmatch(
                    r"[A-Z][\w]*", kind):
                continue
            if ident not in ids:
                ids[ident] = kind
            elif not ident.startswith("#"):
                raise Error("duplicate declaration: " + ident)
            for pkey in ("parts", "with"):
                sub = val.get(pkey) if isinstance(val, Block) else None
                if isinstance(sub, Block):
                    add_from(sub)

    add_from(root)
    return ids

def check_refs(root, ids):
    def refs(key, val):
        if isinstance(val, Block):
            return
        for r in (val if isinstance(val, list) else [val]):
            if isinstance(r, Bare) and r.s not in ids:
                raise Error("unknown reference in %s: %s" % (key, r.s))

    def walk(block):
        for key, val in block.items:
            if key in ("with", "contains", "inside", "found_in"):
                refs(key, val)
            if isinstance(val, Block):
                walk(val)
            elif isinstance(val, list):
                for x in val:
                    if isinstance(x, Block):
                        walk(x)

    walk(root)
    setup = root.get("setup")
    if isinstance(setup, Block):
        take = setup.get("take")
        if take:
            refs("take", take)

def scan_lua_defs(text, funcs, vars_):
    for m in re.finditer(r"function\s+([A-Za-z_]\w*)\s*\(", text):
        funcs.add(m.group(1))
    for m in re.finditer(r"([A-Za-z_]\w*)\s*=\s*function\s*\(", text):
        funcs.add(m.group(1))
    for m in re.finditer(r"^\s*local\s+([A-Za-z_]\w*)", text, re.M):
        vars_.add(m.group(1))
    for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s*=", text, re.M):
        vars_.add(m.group(1))

def collect_game_defs(root):
    funcs = set()
    vars_ = set()

    def walk(block):
        for key, val in block.items:
            if isinstance(val, Lua):
                scan_lua_defs(val.s, funcs, vars_)
            elif isinstance(val, Block):
                walk(val)

    walk(root)
    return funcs, vars_

def scan_required(name):
    path = os.path.join(S.SRC_DIR, name + ".lua")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None

def find_include(name):
    for base in (S.SRC_DIR, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
        path = os.path.join(base, name + ".mise")
        if os.path.exists(path):
            return path
    raise Error("include not found: " + name)

def apply_includes(root, seen=None):
    seen = seen or set()
    extra = []
    for key, val in root.items:
        if key != "include":
            continue
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            name = v.s if hasattr(v, "s") else str(v)
            if name in seen:
                continue
            seen.add(name)
            sub = parse_source(open(find_include(name),
                                    encoding="utf-8").read())
            apply_includes(sub, seen)
            extra += sub.items
    if extra:
        root.items = extra + root.items
    return root

def prescan(root):
    S.FNS = set()
    ids = collect_ids(root)
    S.IDS = set(ids)
    S.EXTRA_EVENTS = {}
    for key, val in root.items:
        kind, ident = decl_key(key)
        if kind == "verb" and ident and isinstance(val, Block):
            tag = val.get("tag")
            if not (isinstance(tag, Bool) and tag.s == "false"):
                S.EXTRA_EVENTS[ident] = ident
            event = val.get("event")
            if isinstance(event, Bare):
                S.EXTRA_EVENTS[event.s] = event.s
        elif key == "events":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                name = v.s if hasattr(v, "s") else str(v)
                S.EXTRA_EVENTS[name] = name
    S.EVENT_NAMES = set(EVENTS) | set(S.EXTRA_EVENTS.values())
    game_funcs, game_vars = collect_game_defs(root)
    S.FN_SIGS = {}
    fn_names = set()
    for key, val in root.items:
        if re.match(r"^fn\s+", key):
            name, plist, ret, variadic = parse_fn_sig(key)
            if name in S.FN_SIGS:
                raise Error("duplicate fn: " + name)
            S.FN_SIGS[name] = (plist, ret, variadic)
            fn_names.add(name)
    for key, val in root.items:
        if key == "require":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                text = scan_required(v.s if hasattr(v, "s") else str(v))
                if text:
                    scan_lua_defs(text, game_funcs, game_vars)
    const_names = set()
    S.GLOBAL_TYPES = {}
    for key, val in root.items:
        if key in ("const", "global") and isinstance(val, Block):
            for k, v in val.items:
                const_names.add(k)
                if isinstance(v, Num):
                    S.GLOBAL_TYPES[k] = "num"
                elif isinstance(v, Bool):
                    S.GLOBAL_TYPES[k] = "bool"
                elif isinstance(v, Text):
                    S.GLOBAL_TYPES[k] = "str"
                else:
                    S.GLOBAL_TYPES[k] = "any"
    S.VARS = game_vars | const_names
    S.FUNCS = fn_names | game_funcs | {"_"}
    S.FNS = fn_names
    check_refs(root, ids)
