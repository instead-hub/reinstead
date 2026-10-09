import os
import re

from . import state as S
from .common import *
from .parse import parse_source
from .decl import classify, mixin_bodies, parse_fn_sig
from .inline import _inline_fn
from .proptypes import (check_prop_value, collect_types,
                       register_events, register_props,
                       register_refs)
from .typing import literal_type
from . import messages as M

def _decl_id(key):
    """(ident, kind) of a declaration or talk key, else None."""
    kind, info = classify(key)
    if kind == "decl":
        return info[1], info[0]
    if kind == "talk":
        return info, kind
    return None


def _register_id(ids, ident, ikind):
    """Record one declared id; returns False for an empty ident."""
    if not ident:
        return False
    if ident not in ids:
        ids[ident] = ikind
    elif not ident.startswith("#"):
        raise Error(M.DUPLICATE_DECLARATION + ident)
    return True


def _with_subblocks(val):
    """`with` sub-blocks of a declaration value."""
    sub = val.get("with") if isinstance(val, Block) else None
    return [sub] if isinstance(sub, Block) else []


def collect_ids(root):
    ids = {}

    def add_from(block):
        for i, (key, val) in enumerate(block.items):
            CURRENT_LINE[0] = block.line_at(i)
            hit = _decl_id(key)
            if hit is None:
                continue
            if not _register_id(ids, hit[0], hit[1]):
                continue
            for sub in _with_subblocks(val):
                add_from(sub)

    add_from(root)
    return ids

def _sub_blocks(val):
    """Nested Blocks of a value (the block itself or list items)."""
    if isinstance(val, Block):
        return [val]
    if isinstance(val, list):
        return [x for x in val if isinstance(x, Block)]
    return []


def _nested_decls(val):
    """Yield (kind, ident, block) of declarations inside with/inside."""
    for nk, nv in val.items:
        k2, info = classify(nk)
        if k2 == "decl" and info[1] and isinstance(nv, Block):
            yield info[0], info[1], nv


def check_refs(root, ids):
    def refs(key, val):
        if isinstance(val, Block):
            return
        for r in (val if isinstance(val, list) else [val]):
            if isinstance(r, Bare) and r.s not in ids:
                raise Error(M.UNKNOWN_REFERENCE % (key, r.s))

    def _walk_refs(block):
        for i, (key, val) in enumerate(block.items):
            if key == "props":
                continue
            if key in ("with", "inside", "found_in"):
                CURRENT_LINE[0] = block.line_at(i)
                refs(key, val)
            for sub in _sub_blocks(val):
                _walk_refs(sub)

    _walk_refs(root)
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

FIELD_SKIP = {"words", "on", "inside", "with", "attrs", "disabled",
              "dict", "nam", "patterns", "pattern", "tag", "prio",
              "hint", "mixin"}

ENGINE_TARGETS = {"game", "player", "pl", "mp", "std", "main"}


def _check_impl_target(target, ctx):
    """A declared object/class, or an engine module (`game`, `@compass`)."""
    if target in ctx.ids or target in ctx.classes:
        return
    if target.startswith("@") or "." in target or target in ENGINE_TARGETS:
        return
    raise Error(M.UNKNOWN_IMPL_TARGET + target)


def field_base(key, val, ctx):
    """Return the field name of a regular object-like key, else None.

    Handlers (`before X`, `Any`/`Default`/`life_*`, event keys), blocks
    and reserved keys are not fields. Shared by field typing and
    bare-name validation so both follow one rule.
    """
    base, params = parse_key(key)
    parts = [p.strip() for p in base.split(",")]
    if (params is not None or isinstance(val, Block)
            or base in FIELD_SKIP or base in ("Any", "Default")
            or re.match(r"^(on|life|before|after|post)\s", base)
            or any(p in ctx.event_names or p.startswith("life_")
                   or p in ("Any", "Default") for p in parts)):
        return None
    return base


def attach_mixins(block, ctx, into, collect):
    """Merge attached mixins' fields first (own keys override)."""
    val = block.get("mixin")
    if val is None:
        return
    seen = {}
    for name, bdef in mixin_bodies(ctx, val, block.line("mixin")):
        for k, _bv in bdef.items:
            if k in seen:
                raise Error(M.MIXIN_KEY_CONFLICT
                            % (k, seen[k], name))
            seen[k] = name
        collect(bdef, ctx, into)


def _reject_bare_str(base, val, t):
    """A bare string field value must be a declared name or a `use`."""
    if (base is not None and isinstance(val, Bare) and t == "str"
            and not S.USE_RE.match(val.s.strip())):
        raise Error(M.FIELD_STRING_VALUES_QUOTED % (val.s, base))


def _collect_field(ctx, into, owner, key, val):
    """Store the typed value of one regular field."""
    base = field_base(key, val, ctx)
    if base is None:
        return
    t = literal_type(ctx, val, refs=True)
    _reject_bare_str(base, val, t)
    prop = ctx.props.get(base)
    if prop is not None:
        into[base] = check_prop_value(ctx, owner, base, prop, val, t)
        return
    into[base] = (t, t == "obj" and isinstance(val, Bare))


def collect_block_fields(block, ctx, into, owner=None):
    attach_mixins(block, ctx, into, collect_block_fields)
    for i, (key, val) in enumerate(block.items):
        CURRENT_LINE[0] = block.line_at(i)
        if key in ("with", "inside") and isinstance(val, Block):
            _collect_nested(val, ctx, collect_block_fields)
            continue
        _collect_field(ctx, into, owner, key, val)


def _collect_nested(block, ctx, collect):
    """Field maps of declarations inside a with/inside block."""
    for kind, ident, nv in _nested_decls(block):
        fields = dict(ctx.fields.get(kind, {}))
        collect(nv, ctx, fields, ident)
        ctx.fields[ident] = fields


def _collect_class(info, val, class_defs, _mixin_defs):
    class_defs[info[0]] = (info[1], val)


def _collect_mixin(info, val, _class_defs, mixin_defs):
    _add_mixin(info, val, mixin_defs)


# the top-level definitions that build the field maps
DEFS_FORMS = {
    "class": _collect_class,
    "mixin": _collect_mixin,
}


def _collect_defs(root, class_defs, mixin_defs):
    """Scan top-level class and mixin definitions."""
    for i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(i)
        kind, info = classify(key)
        if not isinstance(val, Block):
            continue
        form = DEFS_FORMS.get(kind)
        if form is not None:
            form(info, val, class_defs, mixin_defs)


def _add_mixin(info, val, mixin_defs):
    """Register one mixin body, rejecting duplicates and nesting."""
    if info in mixin_defs:
        raise Error(M.DUPLICATE_MIXIN + info)
    if any(re.match(r"^mixins?\b", k2) for k2, _ in val.items):
        raise Error(M.MIXIN_CANNOT_INCLUDE_MIXIN % info)
    mixin_defs[info] = val


def _collect_mixin_fields(ctx, mixin_defs):
    """Field maps of mixin bodies."""
    for name, blk in mixin_defs.items():
        fields = {}
        collect_block_fields(blk, ctx, fields, name)
        ctx.fields[name] = fields


def _collect_decl_fields(root, ctx):
    """Field maps of declared objects/classes."""
    for key, val in root.items:
        kind, info = classify(key)
        if kind == "decl" and info[1] and isinstance(val, Block):
            fields = dict(ctx.fields.get(info[0], {}))
            collect_block_fields(val, ctx, fields, info[1])
            ctx.fields[info[1]] = fields


def collect_field_types(root, ctx):
    ctx.fields = {}
    class_defs = {}
    mixin_defs = {}
    _collect_defs(root, class_defs, mixin_defs)
    ctx.mixin_defs = mixin_defs
    ctx.class_parents = {n: info[0] for n, info in class_defs.items()}
    ctx.classes = set(class_defs)
    _collect_mixin_fields(ctx, mixin_defs)
    done = set()

    def resolve(cls_name):
        if cls_name in done or cls_name not in class_defs:
            return dict(ctx.fields.get(cls_name, {}))
        done.add(cls_name)
        parent, body = class_defs[cls_name]
        own = resolve(parent) if parent else {}
        collect_block_fields(body, ctx, own, cls_name)
        ctx.fields[cls_name] = own
        return own

    for name in class_defs:
        resolve(name)
    _collect_decl_fields(root, ctx)


def _check_mixin_names(ctx, value):
    """Validate the mixin names of a `mixin` field value."""
    for item in (value if isinstance(value, list) else [value]):
        name = item.s if hasattr(item, "s") else str(item)
        if name not in ctx.mixin_defs:
            raise Error(M.UNKNOWN_MIXIN + name)


def _check_bare_field(ctx, use_props, owner, key, val):
    """Validate one non-mixin field of an impl/setup/hero block."""
    base = field_base(key, val, ctx)
    t = literal_type(ctx, val, refs=True)
    _reject_bare_str(base, val, t)
    prop = ctx.props.get(base) if (use_props and base) else None
    if prop is not None:
        check_prop_value(ctx, owner, base, prop, val, t)


def _walk_fields(ctx, block, use_props=False, owner=None):
    """Validate the fields of one impl/setup/hero/const block."""
    for n, (field_key, field_val) in enumerate(block.items):
        CURRENT_LINE[0] = block.line_at(n)
        if field_key == "mixin":
            _check_mixin_names(ctx, field_val)
            continue
        _check_bare_field(ctx, use_props, owner, field_key, field_val)


def _walk_setup_fields(setup, ctx):
    """Validate hero/game blocks inside a setup block."""
    for j, (skey, sval) in enumerate(setup.items):
        CURRENT_LINE[0] = setup.line_at(j)
        if skey in ("hero", "game") and isinstance(sval, Block):
            _walk_fields(ctx, sval, True, skey)


def _bare_mixin(ctx, info, val, _key):
    _walk_fields(ctx, val, True, info)


def _bare_impl(ctx, info, val, _key):
    _check_impl_target(info, ctx)
    _walk_fields(ctx, val, True, info)


def _bare_setup(ctx, _info, val, _key):
    _walk_setup_fields(val, ctx)


def _bare_vars(ctx, _info, val, _key):
    _walk_fields(ctx, val)


# the top-level blocks whose bare names are validated
BARE_FORMS = {
    "mixin": _bare_mixin,
    "impl": _bare_impl,
    "setup": _bare_setup,
    "const": _bare_vars,
    "global": _bare_vars,
}


def _check_bare_block(key, val, ctx):
    """Dispatch bare-name validation by top-level block kind."""
    kind, info = classify(key)
    form = BARE_FORMS.get(kind)
    if form is not None:
        form(ctx, info, val, key)


def check_bare_names(root, ctx):
    """Validate bare field values in impl/setup/hero/const/global.

    Same rule as object/class fields: a bare name must resolve to an
    object, event or enum value; strings have to be quoted.
    """
    for i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(i)
        if not isinstance(val, Block):
            continue
        _check_bare_block(key, val, ctx)


def collect_game_defs(root):
    funcs = set()
    vars_ = set()

    def _walk_defs(block):
        for _key, val in block.items:
            if isinstance(val, Lua):
                scan_lua_defs(val.s, funcs, vars_)
            for sub in _sub_blocks(val):
                _walk_defs(sub)

    _walk_defs(root)
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
    raise Error(M.INCLUDE_NOT_FOUND + name)

def _include_one(name, ctx, seen, extra, extra_lines, recurse):
    """Parse one included file; append its items and lines."""
    if name in seen:
        return
    seen.add(name)
    sub = parse_source(open(find_include(name, ctx),
                            encoding="utf-8").read())
    recurse(sub, ctx, seen)
    extra.extend(sub.items)
    extra_lines.extend(sub.lines)


def apply_includes(root, ctx, seen=None):
    seen = seen or set()
    extra = []
    extra_lines = []
    for key, val in root.items:
        if key != "include":
            continue
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            name = v.s if hasattr(v, "s") else str(v)
            _include_one(name, ctx, seen, extra, extra_lines, apply_includes)
    if extra:
        root.items = extra + root.items
        root.lines = extra_lines + root.lines
    return root

def _register_fns(root, ctx):
    ctx.fn_sigs = {}
    names = set()
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        if classify(key)[0] != "fn":
            continue
        name, plist, ret, variadic = parse_fn_sig(
            key, set(ctx.types) | ctx.classes)
        if name in ctx.fn_sigs:
            raise Error(M.DUPLICATE_FN + name)
        ctx.fn_sigs[name] = (plist, ret, variadic)
        names.add(name)
        _inline_fn(ctx, name, val, plist, variadic)
    return names


def _register_requires(root, ctx, game_funcs, game_vars):
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        if classify(key)[0] != "require":
            continue
        for v in (val if isinstance(val, list) else [val]):
            text = scan_required(v.s if hasattr(v, "s") else str(v), ctx)
            if text:
                scan_lua_defs(text, game_funcs, game_vars)


def _register_globals(root, ctx):
    names = set()
    ctx.global_types = {}
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        if classify(key)[0] in ("const", "global") and isinstance(val, Block):
            for k, v in val.items:
                names.add(k)
                ctx.global_types[k] = literal_type(ctx, v)
    return names


def _use_refs(root):
    refs = set()

    def _walk_use(block):
        for _k, v in block.items:
            if isinstance(v, (Text, Bare)):
                m = re.match(r"^use\s+([\w.+-]+)$", v.s.strip())
                if m:
                    refs.add(m.group(1))
            for sub in _sub_blocks(v):
                _walk_use(sub)

    _walk_use(root)
    return refs


def prescan(root, ctx):
    ctx.fns = set()
    collect_types(root, ctx)
    ids = collect_ids(root)
    ctx.ids = set(ids)
    ctx.id_kind = ids
    register_refs(root, ctx)
    register_events(root, ctx)
    register_props(root, ctx)
    collect_field_types(root, ctx)
    check_bare_names(root, ctx)
    game_funcs, game_vars = collect_game_defs(root)
    fn_names = _register_fns(root, ctx)
    _register_requires(root, ctx, game_funcs, game_vars)
    const_names = _register_globals(root, ctx)
    ctx.vars = game_vars | const_names
    ctx.funcs = fn_names | game_funcs | {"_"}
    ctx.fns = fn_names
    for n in _use_refs(root):
        desc = ctx.inline.get(n)
        if desc and desc[0] != "expr":
            del ctx.inline[n]
    check_refs(root, ids)
