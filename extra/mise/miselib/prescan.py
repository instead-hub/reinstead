import os
import re

from . import state as S
from .common import *
from .parse import parse_source
from .decl import classify, parse_fn_sig
from .typing import Prop, literal_type, type_ok

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
        raise Error("duplicate declaration: " + ident)
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
                raise Error("unknown reference in %s: %s" % (key, r.s))

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

def _type_atoms(val):
    """Bare value strings of a type: inline scalars or `-` list items."""
    if not isinstance(val, list):
        yield val
        return
    for x in val:
        if isinstance(x, Text):
            for part in x.s.split(","):
                part = part.strip()
                if part:
                    yield Bare(part)
        else:
            yield x


def _is_negation(name, atoms):
    """True if the type starts with the `~` negation marker."""
    if not atoms:
        return False
    first = atoms[0]
    if isinstance(first, Text):
        raise Error("type %s: quotes are not allowed" % name)
    if not isinstance(first, (Bare, Num)):
        raise Error("type %s: expected bare values" % name)
    return first.s == "~"


def _type_value(name, x):
    """Validate one type atom and return its string."""
    if isinstance(x, Text):
        raise Error("type %s: quotes are not allowed" % name)
    if not isinstance(x, (Bare, Num)):
        raise Error("type %s: expected bare values" % name)
    if not re.fullmatch(r"\S+", x.s, re.UNICODE):
        raise Error("type %s: bad value %r" % (name, x.s))
    return x.s


def _new_type(ctx, name, val):
    if name in ctx.types:
        raise Error("duplicate type: " + name)
    if isinstance(val, Block):
        raise Error("type %s: no values" % name)
    atoms = list(_type_atoms(val))
    negate = _is_negation(name, atoms)
    rest = atoms[1:] if negate else atoms
    vals = [_type_value(name, x) for x in rest]
    if not vals:
        raise Error("type %s: no values" % name)
    ctx.types[name] = {"values": vals, "negate": negate}


def _extend_type(ctx, name, val):
    if name not in ctx.types:
        raise Error("extend type: unknown type %r" % name)
    if isinstance(val, Block):
        raise Error("extend type %s: no values" % name)
    td = ctx.types[name]
    for x in _type_atoms(val):
        if (isinstance(x, Text) or not isinstance(x, (Bare, Num))
                or x.s == "~"):
            raise Error("extend type %s: expected bare values" % name)
        if not re.fullmatch(r"\S+", x.s, re.UNICODE):
            raise Error("extend type %s: bad value %r" % (name, x.s))
        if x.s not in td["values"]:
            td["values"].append(x.s)


# the enumeration declarations and their registrars
TYPE_FORMS = {
    "type": _new_type,
    "extend_type": _extend_type,
}


def collect_types(root, ctx):
    ctx.types = {}
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        kind, name = classify(key)
        form = TYPE_FORMS.get(kind)
        if form is not None:
            form(ctx, name, val)
    ctx.enum_values = {}
    for _tname, td in ctx.types.items():
        for _v in td["values"]:
            ctx.enum_values.setdefault(_v, set()).add(_tname)
    return ctx.types


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
    raise Error("unknown impl target: " + target)


def _register_prop(ctx, known, name, tval):
    """Validate and register one `props:` entry."""
    if not re.fullmatch(r"[^\W\d]\w*", name, re.UNICODE):
        raise Error("bad prop name %r" % name)
    if name in ctx.props:
        raise Error("duplicate prop: " + name)
    if not isinstance(tval, (Bare, Text)):
        raise Error("props: %s needs a type" % name)
    prop = Prop(tval.s, known)
    ctx.props[name] = prop
    if prop.names:
        ctx.prop_params[name] = prop.names
    if prop.has_ref or prop.has_reflist:
        ctx.ref_fields.add(name)


def _register_props(root, ctx):
    """`props:` -> typed engine properties (refs, handlers, text/fn)."""
    ctx.props = {}
    ctx.prop_params = {}
    known = S.TYPES | set(ctx.types) | {"ref", "nil"}
    for i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(i)
        if classify(key)[0] != "props":
            continue
        if not isinstance(val, Block):
            raise Error("props must be a block")
        for j, (name, tval) in enumerate(val.items):
            CURRENT_LINE[0] = val.line_at(j) or CURRENT_LINE[0]
            _register_prop(ctx, known, name, tval)


def _check_ref_name(ctx, where, name):
    """Object reference name must be a declared id."""
    if name not in ctx.ids:
        raise Error("%s: unknown object reference %r" % (where, name))


def check_ref_list(ctx, where, val):
    """`tbl[ref]` list items: bare names or `-`-list strings."""
    for it in val:
        if isinstance(it, Text):
            _check_ref_name(ctx, where, it.s.strip())
        elif isinstance(it, Bare):
            if not re.fullmatch(r"[#@\w]+", it.s, re.UNICODE):
                raise Error("%s: object name must be an identifier without "
                            "spaces/hyphens (%r)" % (where, it.s))
            _check_ref_name(ctx, where, it.s)
        else:
            raise Error("%s: expected object reference, got %s"
                        % (where, type(it).__name__.lower()))


def _prop_bare(prop, val, where, t):
    if S.USE_RE.match(val.s.strip()):
        if prop.fn is None:
            raise Error("%s: expected %s, got use" % (where, prop.text))
        return "any", False
    if prop.has_event and t == "event":
        return "event", False
    if prop.has_ref and t == "obj":
        return "obj", True
    raise Error("%s: expected %s, got %s" % (where, prop.text, t))


def _prop_text(prop, val, where):
    if prop.has_str:
        return "str", False
    if prop.has_ref:
        raise Error("%s: object reference must be a bare name, not a "
                    "quoted string (%r)" % (where, val.s))
    raise Error("%s: expected %s, got str" % (where, prop.text))


def _prop_list(ctx, prop, val, where):
    if prop.has_reflist:
        check_ref_list(ctx, where, val)
        return "tbl", False
    if prop.has_tbl:
        if prop.tbl_elem:
            for it in val:
                t = literal_type(ctx, it)
                if not type_ok(ctx, t, prop.tbl_elem):
                    raise Error("%s: expected %s in list, got %s"
                                % (where, prop.tbl_elem, t))
        return "tbl", False
    raise Error("%s: expected %s, got list" % (where, prop.text))


def _prop_scalar(prop, kind, flag, where):
    if getattr(prop, flag):
        return kind, False
    raise Error("%s: expected %s, got %s" % (where, prop.text, kind))


def check_prop_value(ctx, owner, base, prop, val, t):
    """Validate a prop field value; returns (type, is_ref)."""
    where = ("%s.%s" % (owner, base)) if owner else base
    if isinstance(val, Raw):
        return "any", False
    if isinstance(val, Nil):
        return "nil", False
    if isinstance(val, Data):
        return "tbl", False
    if isinstance(val, (Logic, Lua)):
        if prop.fn is None:
            raise Error("%s: expected %s, got function" % (where, prop.text))
        return "any", False
    if isinstance(val, Bare):
        return _prop_bare(prop, val, where, t)
    if isinstance(val, Text):
        return _prop_text(prop, val, where)
    if isinstance(val, list):
        return _prop_list(ctx, prop, val, where)
    if isinstance(val, Num):
        return _prop_scalar(prop, "num", "has_num", where)
    if isinstance(val, Bool):
        return _prop_scalar(prop, "bool", "has_bool", where)
    if prop.has_tbl:
        return "tbl", False
    raise Error("%s: expected %s, got %s"
                % (where, prop.text, type(val).__name__.lower()))


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
    CURRENT_LINE[0] = block.line("mixin") or CURRENT_LINE[0]
    seen = {}
    for v in (val if isinstance(val, list) else [val]):
        CURRENT_LINE[0] = block.line("mixin") or CURRENT_LINE[0]
        name = v.s if hasattr(v, "s") else str(v)
        bdef = ctx.mixin_defs.get(name)
        if bdef is None:
            raise Error("unknown mixin: " + name)
        for k, _bv in bdef.items:
            if k in seen:
                raise Error("mixin key conflict: %s (%s and %s)"
                            % (k, seen[k], name))
            seen[k] = name
        collect(bdef, ctx, into)


def _collect_nested(block, ctx, collect):
    """Field maps of declarations inside a with/inside block."""
    for kind, ident, nv in _nested_decls(block):
        fields = dict(ctx.fields.get(kind, {}))
        collect(nv, ctx, fields, ident)
        ctx.fields[ident] = fields


def _collect_field(ctx, into, owner, key, val):
    """Store the typed value of one regular field."""
    base = field_base(key, val, ctx)
    if base is None:
        return
    t = literal_type(ctx, val, refs=True)
    if (isinstance(val, Bare) and t == "str"
            and not S.USE_RE.match(val.s.strip())):
        raise Error("unknown name %r in field %s (quote string "
                    "values: [[...]]/\"...\")" % (val.s, base))
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
        raise Error("duplicate mixin: " + info)
    if any(re.match(r"^mixins?\b", k2) for k2, _ in val.items):
        raise Error("mixin %s cannot include mixin" % info)
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
            raise Error("unknown mixin: " + name)


def _check_bare_field(ctx, use_props, owner, key, val):
    """Validate one non-mixin field of an impl/setup/hero block."""
    base = field_base(key, val, ctx)
    t = literal_type(ctx, val, refs=True)
    if (base is not None and isinstance(val, Bare) and t == "str"
            and not S.USE_RE.match(val.s.strip())):
        raise Error("unknown name %r in field %s (quote string "
                    "values: [[...]]/\"...\")" % (val.s, base))
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
    raise Error("include not found: " + name)

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

def _skip_string(text, i):
    """Index after the quoted run starting at text[i]."""
    quote = text[i]
    i += 1
    while i < len(text) and text[i] != quote:
        if text[i] == "\\":
            i += 1
        i += 1
    return i + 1


def _call_end(text):
    """Index of the `)` closing the call at the first `(`, or None."""
    depth = 0
    i = text.index("(")
    while i < len(text):
        c = text[i]
        if c in "\"'":
            i = _skip_string(text, i)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def wrapper_template(text):
    """Return the inner call if body is a single call/return-call, else None."""
    b = text.strip()
    if not b or "\n" in b or "..." in b or ";" in b:
        return None
    if b.startswith("return "):
        b = b[7:].strip()
    if not re.match(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?::[A-Za-z_]\w*)?\s*\(",
                    b):
        return None
    end = _call_end(b)
    if end is None:
        return None
    return b if b[end + 1:].strip() == "" else None


def _method_adapter(callee, pnames, got, tails):
    """Forwarded method call; returns (handled, result)."""
    if ":" not in callee:
        return False, None
    recv, meth = callee.split(":", 1)
    if not (pnames and recv == pnames[0]
            and any(got == t[1:] for t in tails)):
        return False, None
    if "fn_" in meth:
        return True, None
    return True, ("method", meth)


def adapter_callee(text, plist, full=False):
    """Return callee if body forwards parameters to it.

    Body must be a single call with `(params..., ...)`; with `full=True`
    the plain `(params...)` form is accepted too (fns with optional
    trailing parameters). Method form (recv:meth(...)) is allowed when
    recv is the first parameter; then ("method", meth) is returned and
    calls emit args[0]:meth(args[1:]).
    """
    b = text.strip()
    if not b or "\n" in b:
        return None
    if b.startswith("return "):
        b = b[7:].strip()
    m = re.match(r"^([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*"
                 r"(?::[A-Za-z_]\w*)?)\s*\(([^()]*)\)$", b)
    if not m:
        return None
    callee, raw = m.group(1), m.group(2)
    got = [a.strip() for a in raw.split(",") if a.strip()]
    pnames = [pn for pn, _pt in plist]
    tails = [pnames + ["..."]]
    if full:
        tails.append(pnames)
    handled, method = _method_adapter(callee, pnames, got, tails)
    if handled:
        return method
    if got in tails:
        return None if "fn_" in callee else callee
    return None


def _register_refs(root, ctx):
    ctx.ref_fields = set()
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        kind, _info = classify(key)
        if kind not in ("refs", "extend_refs"):
            continue
        if isinstance(val, Block):
            raise Error("refs: expected a list of names")
        for x in _type_atoms(val):
            if isinstance(x, Text) or not isinstance(x, Bare) or x.s == "~":
                raise Error("refs: expected bare names")
            if not re.fullmatch(r"\S+", x.s, re.UNICODE):
                raise Error("refs: bad name %r" % x.s)
            ctx.ref_fields.add(x.s)


def _register_events(root, ctx):
    names = set(ctx.types.get("event", {}).get("values", []))
    for _i, (key, val) in enumerate(root.items):
        CURRENT_LINE[0] = root.line_at(_i)
        kind, ident = classify(key)
        if kind == "event_decl" and isinstance(val, Block):
            names.add(ident)
    ctx.event_names = names


def _params_used_once(plist, text):
    """True if no parameter occurs in text more than once."""
    return all(len(re.findall(r"(?<![\w.])%s(?![\w])" % re.escape(pn),
                              text)) <= 1
               for pn, _pt in plist)


def _inline_expr(ctx, name, val, plist, has_optional):
    e = val.s.strip()
    if not e or ";" in e or "..." in e or "fn_" in e:
        raise Error("fn %s: bad expression body" % name)
    if not _params_used_once(plist, e):
        raise Error("fn %s: expression body uses a parameter "
                    "more than once" % name)
    if has_optional:
        for pn, pt in plist:
            if ((pt == "nil" or pt.endswith("?"))
                    and re.search(r"(?<![\w.])%s(?![\w])"
                                  % re.escape(pn), e)):
                raise Error("fn %s: expression body cannot use optional "
                            "parameter %s" % (name, pn))
    ctx.inline[name] = ("expr", (plist, e))


def _set_adapter(ctx, name, callee):
    """Register a `call`/`meth` adapter if the body matched one."""
    if not callee:
        return
    if isinstance(callee, tuple):
        ctx.inline[name] = ("meth", (callee[1],))
    else:
        ctx.inline[name] = ("call", (callee,))


def _inline_fn(ctx, name, val, plist, variadic):
    has_optional = any(pt == "nil" or pt.endswith("?") for _pn, pt in plist)
    if isinstance(val, Raw):
        if variadic:
            raise Error("fn %s: expression body cannot be variadic" % name)
        _inline_expr(ctx, name, val, plist, has_optional)
        return
    if not isinstance(val, Lua):
        return
    if variadic:
        _set_adapter(ctx, name, adapter_callee(val.s, plist))
        return
    if has_optional:
        _set_adapter(ctx, name, adapter_callee(val.s, plist, full=True))
        return
    t = wrapper_template(val.s)
    if t and ("fn_" in t or not _params_used_once(plist, t)):
        return
    if t:
        ctx.inline[name] = ("wrap", (plist, t))


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
            raise Error("duplicate fn: " + name)
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
    _register_refs(root, ctx)
    _register_events(root, ctx)
    _register_props(root, ctx)
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
