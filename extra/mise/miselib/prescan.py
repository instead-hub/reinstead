import os
import re

from .common import *
from .parse import parse_source
from .decl import classify, parse_fn_sig

def collect_ids(root):
    ids = {}

    def add_from(block):
        for key, val in block.items:
            kind, info = classify(key)
            if kind == "decl":
                ident = info[1]
            elif kind == "talk":
                ident = info
            else:
                continue
            if not ident:
                continue
            if ident not in ids:
                ids[ident] = kind
            elif not ident.startswith("#"):
                raise Error("duplicate declaration: " + ident)
            for pkey in ("with",):
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
            if key in ("with", "inside", "found_in"):
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

def scan_required(name, ctx):
    path = os.path.join(ctx.src_dir, name + ".lua")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None

def find_include(name, ctx):
    for base in (ctx.src_dir, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
        path = os.path.join(base, name + ".mise")
        if os.path.exists(path):
            return path
    raise Error("include not found: " + name)

def apply_includes(root, ctx, seen=None):
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
            sub = parse_source(open(find_include(name, ctx),
                                    encoding="utf-8").read())
            apply_includes(sub, ctx, seen)
            extra += sub.items
    if extra:
        root.items = extra + root.items
    return root

def prescan(root, ctx):
    ctx.fns = set()
    ids = collect_ids(root)
    ctx.ids = set(ids)
    ctx.extra_events = {}
    for key, val in root.items:
        kind, ident = classify(key)
        if kind == "verb" and ident and isinstance(val, Block):
            tag = val.get("tag")
            if not (isinstance(tag, Bool) and tag.s == "false"):
                ctx.extra_events[ident] = ident
            event = val.get("event")
            if isinstance(event, Bare):
                ctx.extra_events[event.s] = event.s
        elif key == "events":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                name = v.s if hasattr(v, "s") else str(v)
                ctx.extra_events[name] = name
    ctx.event_names = set(EVENTS) | set(ctx.extra_events.values())
    game_funcs, game_vars = collect_game_defs(root)
    ctx.fn_sigs = {}
    fn_names = set()
    for key, val in root.items:
        if classify(key)[0] == "fn":
            name, plist, ret, variadic = parse_fn_sig(key)
            if name in ctx.fn_sigs:
                raise Error("duplicate fn: " + name)
            ctx.fn_sigs[name] = (plist, ret, variadic)
            fn_names.add(name)
    for key, val in root.items:
        if classify(key)[0] == "require":
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                text = scan_required(v.s if hasattr(v, "s") else str(v), ctx)
                if text:
                    scan_lua_defs(text, game_funcs, game_vars)
    const_names = set()
    ctx.global_types = {}
    for key, val in root.items:
        if classify(key)[0] in ("const", "global") and isinstance(val, Block):
            for k, v in val.items:
                const_names.add(k)
                if isinstance(v, Num):
                    ctx.global_types[k] = "num"
                elif isinstance(v, Bool):
                    ctx.global_types[k] = "bool"
                elif isinstance(v, Text):
                    ctx.global_types[k] = "str"
                else:
                    ctx.global_types[k] = "any"
    ctx.vars = game_vars | const_names
    ctx.funcs = fn_names | game_funcs | {"_"}
    ctx.fns = fn_names
    check_refs(root, ids)
