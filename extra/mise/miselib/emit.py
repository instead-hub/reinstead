import re

from . import state as S
from .common import *
from .emitlogic import emit_logic
from .expr import transpile_exprlist

def lua_value(v, ctx, mode="s"):
    if isinstance(v, list):
        return "{ %s }" % ", ".join(lua_value(x, ctx, mode) for x in v)
    if isinstance(v, Text):
        return lua_str(v.s)
    if isinstance(v, Lua):
        return "function(%s)\n%s\nend" % (FIELD_PARAMS.get(mode, "s"), v.s)
    if isinstance(v, Bare):
        return "'%s'" % v.s if v.s in ctx.ids else lua_str(v.s)
    if isinstance(v, (Num, Bool)):
        return v.s
    if isinstance(v, Raw):
        return v.s
    if isinstance(v, Data):
        return v.s
    if isinstance(v, Nil):
        return "nil"
    raise Error("unsupported value: %r (ctx=%s)" % (v, mode))

def check_use(name, prm, ctx):
    if name not in ctx.fn_sigs or not prm:
        return
    plist, _ret, variadic = ctx.fn_sigs[name]
    n = len(param_env(prm, ctx=ctx))
    if not variadic and len(plist) > n:
        raise Error("fn %s takes %d parameter(s), event provides %d"
                    % (name, len(plist), n))

def use_name(v, ctx):
    if isinstance(v, (Text, Bare)):
        m = S.USE_RE.match(v.s.strip())
        if m:
            name = m.group(1)
            if name not in ctx.fns:
                raise Error("unknown fn in use: " + name)
            return name
    return None

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

def param_env(params, name=None, ctx=None):
    if name and name in ctx.fn_sigs:
        return {pn: pt for pn, pt in ctx.fn_sigs[name][0]}
    env = {}
    for p in (params or "").split(","):
        p = p.strip()
        if not p or p == "...":
            continue
        pn = p.split(":")[0].strip()
        if not re.fullmatch(r"[^\W\d]\w*", pn, re.UNICODE):
            continue
        env[pn] = S.PARAM_TYPES.get(pn, "any")
    return env

def lua_body(v, key, indent="", ctx=None):
    base, params = parse_key(key)
    prm = params or FIELD_PARAMS.get(base, "s")
    uname = use_name(v, ctx=ctx)
    if uname:
        check_use(uname, prm, ctx=ctx)
        return "fn_" + uname
    if isinstance(v, Lua):
        body = reindent(v.s, indent + IND)
        return "function(%s)\n%s\n%s" % (prm, body, indent + "end")
    if isinstance(v, Logic):
        body = "\n".join(emit_logic(v.stmts, indent + IND, param_env(prm, ctx=ctx), ctx=ctx))
        return "function(%s)\n%s\n%s" % (prm, body, indent + "end")
    return lua_value(v, ctx=ctx)

def emit_on(block, indent, target="", ctx=None):
    out = []
    for key, val in block.items:
        base, params = parse_key(key)
        parts = [p.strip() for p in base.split(",")]
        inherited = None
        m0 = re.match(r"^(before|after|post)\s+(.+)$", parts[0])
        if m0:
            inherited = m0.group(1) + "_"
            parts[0] = m0.group(2)
        names = []
        for part in parts:
            pfx = inherited or "before_"
            m = re.match(r"^(before|after|post)\s+(.+)$", part)
            if m:
                pfx = m.group(1) + "_"
                part = m.group(2)
            if part in ("Any", "Default"):
                names.append((part, "before_"))
            else:
                year = EVENTS.get(part) or ctx.extra_events.get(part)
                if not year:
                    raise Error("unknown event: " + part)
                names.append((year, pfx))
        groups = []
        for year, pfx in names:
            if groups and groups[-1][0] == pfx:
                groups[-1][1].append(year)
            else:
                groups.append((pfx, [year]))
        uname = use_name(val, ctx=ctx)
        for pfx, years in groups:
            prm = params or ("s, ev, w" if years[0] in ("Any", "Default")
                             else "s, w, wh")
            if uname:
                check_use(uname, prm, ctx=ctx)
                src = "fn_" + uname
            elif isinstance(val, Lua):
                body = reindent(val.s, indent + IND)
                src = "function(%s)\n%s\n%s" % (prm, body, indent + "end")
            elif isinstance(val, Logic):
                body = "\n".join(emit_logic(val.stmts, indent + IND,
                                            param_env(prm, ctx=ctx), ctx=ctx))
                src = "function(%s)\n%s\n%s" % (prm, body, indent + "end")
            elif (isinstance(val, (Text, Bare))
                  and val.s.strip() == "pass"):
                src = "function() return false end"
            else:
                src = lua_value(val, ctx=ctx)
            if len(years) > 1 and not target:
                out.append('%s["%s%s"] = %s;'
                           % (indent, pfx, ",".join(years), src))
            else:
                for year in years:
                    out.append("%s%s%s%s = %s;"
                               % (indent, target, pfx, year, src))
    return out

def emit_obj(block, ident, base, ctor, preset, parent=None, ctx=None):
    fi = base + IND
    if parent:
        lines = ["%s%s({" % (base, ctor)]
    else:
        lines = ["%s%s {" % (base, ctor)]
    words = block.get("words")
    if words is not None:
        if isinstance(words, Text):
            lines.append('%s-"%%s";' % fi % words.s)
        elif isinstance(words, Raw):
            lines.append("%s%s;" % (fi, words.s))
        elif isinstance(words, list):
            items = []
            for it in words:
                if not isinstance(it, Text):
                    raise Error("words list items must be strings")
                items.append(it.s.strip())
            lines.append('%s-"%%s";' % fi % "|".join(items))
        else:
            raise Error("words must be a quoted string or list")
    nam = block.get("nam")
    if nam is not None:
        raise Error("nam: is not supported; the declaration name is the "
                    "object name")
    if ident:
        lines.append("%snam = %s;" % (fi, lua_str(ident)))
    attrs = list(preset)
    a = block.get("attrs")
    if a is not None:
        if isinstance(a, list):
            attrs += [x.s for x in a
                      if isinstance(x, (Bare, Text))]
        elif isinstance(a, (Bare, Text)):
            attrs.append(a.s)
    obj_items = []
    nested = []
    texts = block.all("text")
    for key, val in block.items:
        if key in ("words", "on", "contains", "parts", "inside",
                   "with", "attrs", "disabled", "before", "after", "post"):
            continue
        if key == "text" and len(texts) > 1:
            continue
        if re.match(r"^(before|after|post)\s+\S", key):
            one = Block()
            one.items = [(key, val)]
            lines.extend(emit_on(one, fi, ctx=ctx))
            continue
        fbase, _ = parse_key(key)
        if fbase in ("Any", "Default"):
            one = Block()
            one.items = [(key, val)]
            lines.extend(emit_on(one, fi, ctx=ctx))
            continue
        if key.startswith("var "):
            name = parse_key(key[4:])[0]
            lines.append("%s%s = %s;" % (fi, name, lua_body(val, name, fi, ctx=ctx)))
            continue
        if not parse_key(key)[1]:
            for part in fbase.split(","):
                if part in REF_FIELDS:
                    check_ref_value(ident or "?", key, val)
                    break
        try:
            rendered = lua_body(val, key, fi, ctx=ctx)
        except Error as e:
            raise Error("%s.%s: %s" % (ident, key, e))
        if "," in fbase:
            lines.append('%s["%s"] = %s;' % (fi, fbase, rendered))
        else:
            lines.append("%s%s = %s;" % (fi, fbase, rendered))
    on = block.get("on")
    if on:
        lines.extend(emit_on(on, fi, ctx=ctx))
    for pfx in ("before", "after", "post"):
        blk = block.get(pfx)
        if isinstance(blk, Block):
            tmp = Block()
            tmp.items = [("%s %s" % (pfx, k), v) for k, v in blk.items]
            lines.extend(emit_on(tmp, fi, ctx=ctx))
    if len(texts) > 1:
        lines.append("%stext = {" % fi)
        for t in texts:
            lines.append("%s%s%s;" % (fi, IND, lua_value(t, ctx=ctx)))
        lines.append("%s};" % fi)
    for key, val in block.items:
        if key in ("contains", "inside", "parts", "with"):
            if isinstance(val, Block):
                for nk, nv in val.items:
                    nested.append(emit_decl(nk, nv, fi + IND, ctx=ctx) + ";")
            else:
                refs = val if isinstance(val, list) else [val]
                for r in refs:
                    if not isinstance(r, Bare):
                        raise Error("%s must list bare identifiers, not "
                                    "quoted strings (%s)" % (key, key))
                    if not re.fullmatch(r"[#@\w]+", r.s, re.UNICODE):
                        raise Error("%s: object name must be an identifier "
                                    "without spaces/hyphens (%r)"
                                    % (key, r.s))
                    obj_items.append("%s'%s';" % (fi + IND, r.s))
    blobs = []
    if obj_items:
        blobs.append("\n".join(obj_items))
    blobs += nested
    if blobs:
        lines.append("%sobj = {" % fi)
        for k, b in enumerate(blobs):
            if k:
                lines.append("")
            lines.extend(b.split("\n"))
        lines.append("%s};" % fi)
    if parent:
        tail = "%s}, %s)" % (base, parent)
    else:
        tail = "%s}" % base
    if attrs:
        tail += ":attr '%s'" % ",".join(attrs)
    if block.get("disabled"):
        tail += ":disable()"
    lines.append(tail)
    return "\n".join(lines)

def emit_verb(block, ident, base, ctx):
    fields = []
    tag = block.get("tag")
    if tag is None:
        fields.append("'#%s'" % ident)
    elif not (isinstance(tag, Bool) and tag.s == "false"):
        fields.append(lua_value(tag, ctx=ctx))
    words = block.get("words")
    if not isinstance(words, Text):
        raise Error("verb words must be a quoted string")
    fields.append(lua_str(words.s))
    pats = block.get("patterns")
    if pats is not None:
        if not isinstance(pats, list):
            pats = [pats]
        for p in pats:
            fields.append(lua_value(p, ctx=ctx))
    extra = []
    if block.get("prio") is not None:
        extra.append("prio = %s" % lua_value(block.get("prio"), ctx=ctx))
    if block.get("hint") is not None:
        extra.append("hint = %s" % lua_body(block.get("hint"), "hint", ctx=ctx))
    lines = ["%sVerb { %s%s }" % (base, ", ".join(fields),
                                  (", " + ", ".join(extra)) if extra else "")]
    ev_field = block.get("event")
    ev = ev_field.s if isinstance(ev_field, Bare) else (ident or "?")
    for key, val in block.items:
        base_key, params = parse_key(key)
        if base_key not in ("on", "before", "after"):
            continue
        if not isinstance(val, (Lua, Logic)):
            continue
        mpname = {"on": "mp.", "before": "mp.before_",
                  "after": "mp.after_"}[base_key] + ev
        if isinstance(val, Lua):
            body = reindent(val.s, base + IND)
        else:
            body = "\n".join(emit_logic(val.stmts, base + IND,
                                        param_env(params or "s, w, wh", ctx=ctx), ctx=ctx))
        lines.append("%s%s = function(%s)\n%s\n%s"
                     % (base, mpname, params or "s, w, wh", body, base + "end"))
    return "\n".join(lines)

def emit_verb_extend(block, ident, base, ctx):
    if not ident:
        raise Error("extend needs a verb tag")
    fields = [lua_str(ident)]
    words = block.get("words")
    if words is not None:
        if not isinstance(words, Text):
            raise Error("extend words must be a quoted string")
        fields.append(lua_str(words.s))
    pats = block.get("patterns")
    if pats is not None:
        if not isinstance(pats, list):
            pats = [pats]
        for p in pats:
            fields.append(lua_value(p, ctx=ctx))
    if len(fields) == 1:
        raise Error("extend needs words or patterns")
    extra = []
    if block.get("prio") is not None:
        extra.append("prio = %s" % lua_value(block.get("prio"), ctx=ctx))
    if block.get("hint") is not None:
        extra.append("hint = %s" % lua_body(block.get("hint"), "hint", ctx=ctx))
    ctor = "VerbExtendWord" if words is not None else "VerbExtend"
    return "%s%s { %s%s }" % (base, ctor, ", ".join(fields),
                              (", " + ", ".join(extra)) if extra else "")

REF_FIELDS = {
    "n_to", "s_to", "e_to", "w_to", "nw_to", "ne_to", "sw_to", "se_to",
    "in_to", "out_to", "u_to", "d_to", "door_to", "walk_to", "next_to",
    "prev_to", "found_in", "talk_to",
}

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

PRESETS = {
    "obj": ("obj", []),
    "scenery": ("obj", ["scenery"]),
    "room": ("room", []),
    "door": ("door", []),
    "story": ("cutscene", []),
    "ending": ("gameover", []),
}

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

def talk_act(reply, do, indent, ctx):
    if do is None:
        return reply
    if isinstance(do, Logic):
        body = emit_logic(do.stmts, indent + IND, {"s": "obj"}, ctx=ctx)
    elif isinstance(do, Lua):
        body = [reindent(do.s, indent + IND)]
    else:
        raise Error("expected logic/lua block")
    if reply is not None:
        body = ["%sp(%s)" % (indent + IND, reply)] + body
    return ["%sfunction(s)" % indent] + body + ["%send" % indent]

def talk_table(oblock, indent, labels, tag=None, ctx=None):
    dsc = None
    reply = None
    do = None
    named = []
    children = []
    for key, val in oblock.items:
        base, _ = parse_key(key)
        if base in ("ask", "say"):
            dsc = lua_value(val, ctx=ctx)
        elif base == "reply":
            reply = lua_value(val, ctx=ctx)
        elif base == "do":
            do = val
        elif base == "when":
            named.append("cond = function() return %s end"
                         % transpile_exprlist(sym_text(val), {},
                                              "talk when", ctx=ctx)[0])
        elif base == "goto":
            named.append("next = '#%s'" % sym_text(val).lstrip('#'))
        elif base in ("always", "hidden", "only"):
            if is_true(val):
                named.append("%s = true" % base)
        elif base == "option":
            children.append(talk_table(val, indent + IND, labels, ctx=ctx))
        elif key.startswith("label ") and isinstance(val, Block):
            labels.append((key[6:].strip(), val))
        else:
            named.append("%s = %s" % (base, lua_body(val, key, indent + IND, ctx=ctx)))
    lines = ["%s{" % indent]
    if tag:
        lines.append("%s'%s';" % (indent + IND, tag))
    if dsc is not None:
        lines.append("%s%s;" % (indent + IND, dsc))
    act = talk_act(reply, do, indent + IND, ctx=ctx)
    if isinstance(act, list):
        lines.extend(act)
        lines[-1] += ";"
    elif act is not None:
        lines.append("%s%s;" % (indent + IND, act))
    for ch in children:
        lines.extend(ch)
        lines[-1] += ";"
    for n in named:
        lines.append("%s%s;" % (indent + IND, n))
    lines.append("%s}" % indent)
    return lines

def emit_talk(block, name, base, ctx):
    fi = base + IND
    labels = []
    root = []
    fields = []
    for key, val in block.items:
        b, _ = parse_key(key)
        if key == "intro":
            root.append(lua_value(val, ctx=ctx))
        elif b == "option":
            root.append(talk_table(val, fi + IND, labels, ctx=ctx))
        elif key.startswith("label ") and isinstance(val, Block):
            labels.append((key[6:].strip(), val))
        else:
            fields.append((key, val))
    lines = ["%sdlg {" % base, "%snam = '%s';" % (fi, name)]
    for key, val in fields:
        lines.append("%s%s = %s;" % (fi, key, lua_body(val, key, fi, ctx=ctx)))
    lines.append("%sphr = {" % fi)
    for r in root:
        if isinstance(r, list):
            lines.extend(r)
            lines[-1] += ";"
        else:
            lines.append("%s%s;" % (fi + IND, r))
    lines.append("%s};" % fi)
    if labels:
        lines.append("%sobj = {" % fi)
        for lname, lblock in labels:
            lines.extend(talk_table(lblock, fi + IND, labels,
                                    tag="#" + lname, ctx=ctx))
            lines[-1] += ";"
        lines.append("%s};" % fi)
    lines.append("%s}" % base)
    return "\n".join(lines)

def emit_class(block, name, parent, ctx):
    body = emit_obj(block, None, "", "Class", [], parent, ctx=ctx)
    return "%s = %s" % (name, body)

def emit_decl(key, block, base, ctx):
    kind, ident = decl_key(key)
    if not kind:
        raise Error("bad declaration: " + key)
    if ident and kind != "verb" and kind != "extend" and not re.fullmatch(
            r"[#\w]+", ident, re.UNICODE):
        raise Error("object names must be identifiers, no spaces/hyphens: %s"
                    % ident)
    if kind == "verb":
        if not ident:
            raise Error("verb needs a name")
        return emit_verb(block, ident, base, ctx=ctx)
    if kind == "extend":
        return emit_verb_extend(block, ident, base, ctx=ctx)
    if kind == "talk":
        if not ident:
            raise Error("talk needs a name")
        return emit_talk(block, ident, base, ctx=ctx)
    if kind not in PRESETS:
        if re.fullmatch(r"[A-Z][\w]*", kind):
            return emit_obj(block, ident, base, kind, [], ctx=ctx)
        raise Error("unknown kind: " + kind)
    ctor, preset = PRESETS[kind]
    return emit_obj(block, ident, base, ctor, preset, ctx=ctx)

def emit_setup(block, ctx):
    lines = []
    fmt = block.get("fmt")
    if fmt:
        vals = fmt if isinstance(fmt, list) else [fmt]
        for v in vals:
            if isinstance(v, (Bare, Text)):
                lines.append("fmt.%s = true" % v.s)
    take = block.get("take")
    takes = []
    if take:
        takes = take if isinstance(take, list) else [take]
        for t in takes:
            if not isinstance(t, (Bare, Text)):
                raise Error("take must list identifiers")
    for key, val in block.items:
        if key in ("take", "fmt", "init"):
            continue
        if key in ("hero", "game") and isinstance(val, Block):
            target = "pl." if key == "hero" else "game."
            for hk, hv in val.items:
                if hk == "on":
                    lines.extend(emit_on(hv, "", target, ctx=ctx))
                elif key == "hero" and hk == "words":
                    lines.append('pl.word = -"%s"' % hv.s)
                else:
                    lines.append("%s%s = %s" % (target, hk,
                                                lua_body(hv, hk, ctx=ctx)))
            continue
        if key == "on":
            lines.extend(emit_on(val, "", "game.", ctx=ctx))
            continue
        if key == "dsc":
            lines.append("game.dsc = %s" % lua_body(val, "dsc", ctx=ctx))
            continue
        if key == "start":
            if isinstance(val, Lua):
                sb = reindent(val.s, IND)
            elif isinstance(val, Logic):
                sb = "\n".join(emit_logic(val.stmts, IND, {"load": "bool"}, ctx=ctx))
            else:
                raise Error("start must be a | block")
            lines.append("function start(load)")
            lines.append(sb)
            lines.append("end")
            continue
        raise Error("unknown setup key: " + key)
    lines.append("function init()")
    for t in takes:
        lines.append("%stake('%s')" % (IND, t.s))
    init = block.get("init")
    if isinstance(init, Lua):
        lines.append(reindent(init.s, IND))
    elif isinstance(init, Logic):
        lines.extend(emit_logic(init.stmts, IND, ctx=ctx))
    lines.append("end")
    return lines

def emit_patch(target, block, ctx):
    t = target.strip()
    if (t.startswith("'") and t.endswith("'")) or (
            t.startswith('"') and t.endswith('"')):
        t = t[1:-1]
    ref = "_'%s'" % t
    lines = []
    for key, val in block.items:
        base, _ = parse_key(key)
        if base in ("on", "before", "after", "post") and isinstance(val, Block):
            lines.extend(emit_on(val, "", ref + ".", ctx=ctx))
        elif base in ("Any", "Default") or base in EVENTS or (
                base in ctx.extra_events):
            one = Block()
            one.items = [(key, val)]
            lines.extend(emit_on(one, "", ref + ".", ctx=ctx))
        elif key.startswith("var "):
            name = parse_key(key[4:])[0]
            lines.append("%s.%s = %s" % (ref, name, lua_body(val, name, ctx=ctx)))
        else:
            lines.append("%s.%s = %s" % (ref, base, lua_body(val, key, ctx=ctx)))
    return "\n".join(lines)

def emit_const(block, ctx):
    out = []
    for key, val in block.items:
        out.append("const '%s' (%s)" % (key, lua_value(val, ctx=ctx)))
    return out

def emit_global(block, ctx):
    out = []
    for key, val in block.items:
        out.append("global '%s' (%s)" % (key, lua_value(val, ctx=ctx)))
    return out
