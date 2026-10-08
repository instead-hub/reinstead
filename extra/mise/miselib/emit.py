import re

from . import state as S
from .common import *
from .emitlogic import emit_logic
from .decl import (PRESETS, check_ref_value, decl_key,
                   is_true, sym_text)
from .typing import body_type, class_le, type_ok, type_value_error
from .expr import fn_name, min_args, transpile_exprlist








def _pfx(kw):
    """Prefix for a handler keyword: `on` is the main-phase method."""
    return "" if kw == "on" else kw + "_"


class Emitter:
    def __init__(self, ctx):
        self.ctx = ctx

    def value(self, v, mode="s"):
        if isinstance(v, list):
            return "{ %s }" % ", ".join(self.value(x, mode) for x in v)
        if isinstance(v, Text):
            return lua_str(v.s)
        if isinstance(v, Lua):
            return "function(%s)\n%s\nend" % (
                self.ctx.prop_params.get(mode, "s"), v.s)
        if isinstance(v, Bare):
            return "'%s'" % v.s if v.s in self.ctx.ids else lua_str(v.s)
        if isinstance(v, (Num, Bool)):
            return v.s
        if isinstance(v, Raw):
            return v.s
        if isinstance(v, Data):
            return v.s
        if isinstance(v, Nil):
            return "nil"
        raise Error("unsupported value: %r (ctx=%s)" % (v, mode))

    def check_use(self, name, prm, ret=None):
        if name not in self.ctx.fn_sigs or not prm:
            return
        plist, fret, _v = self.ctx.fn_sigs[name]
        n = len(self.param_env(prm))
        pt = plist[0][1] if plist else None
        if pt in self.ctx.classes:
            owner = self.ctx.current_owner
            kind = self.ctx.id_kind.get(owner, owner)
            if not kind or not class_le(self.ctx, kind, pt):
                raise Error("fn %s expects %s, not %s"
                            % (name, pt, kind or owner or "?"))
        mn = min_args(plist)
        if n < mn:
            if mn == len(plist):
                raise Error("fn %s takes %d parameter(s), event provides %d"
                            % (name, len(plist), n))
            raise Error("fn %s takes at least %d parameter(s), event "
                        "provides %d" % (name, mn, n))
        if ret and fret and fret != "any" and not type_ok(self.ctx, fret, ret):
            raise Error("fn %s: return type is %s, expected %s"
                        % (name, fret, ret))

    def use_name(self, v):
        if isinstance(v, (Text, Bare)):
            m = S.USE_RE.match(v.s.strip())
            if m:
                name = m.group(1)
                if name not in self.ctx.fns:
                    raise Error("unknown fn in use: " + name)
                if name in self.ctx.inline:
                    raise Error("inline fn %s cannot be used with use"
                                % name)
                return name
        return None

    def param_env(self, params, name=None):
        if name and name in self.ctx.fn_sigs:
            return {pn: pt for pn, pt in self.ctx.fn_sigs[name][0]}
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

    def make_body(self, v, prm, indent, env=None, ret=None, ret_name=None):
        uname = self.use_name(v)
        if uname:
            self.check_use(uname, prm, ret)
            return fn_name(uname)
        if isinstance(v, Lua):
            body = reindent(v.s, indent + IND)
            return "function(%s)\n%s\n%s" % (prm, body, indent + "end")
        if isinstance(v, Logic):
            if env is None:
                env = self.param_env(prm)
            body = "\n".join(emit_logic(v.stmts, indent + IND, env, ret,
                                        ret_name, ctx=self.ctx))
            return "function(%s)\n%s\n%s" % (prm, body, indent + "end")
        return self.value(v)

    def body(self, v, key, indent=""):
        base, params = parse_key(key)
        prop = self.ctx.props.get(base)
        prm = params or (prop.names if prop else None) or "s"
        env = None if params else (prop.env if prop else None)
        ret = None
        if prop is not None and not params and prop.ret:
            ret = body_type(prop.ret)
        return self.make_body(v, prm, indent, env, ret, base)

    def handler(self, val, prm, indent):
        if isinstance(val, (Text, Bare)) and val.s.strip() == "pass":
            return "function() return false end"
        return self.make_body(val, prm, indent)

    def on(self, block, indent, target=""):
        out = []
        for i, (key, val) in enumerate(block.items):
            CURRENT_LINE[0] = block.line_at(i) or CURRENT_LINE[0]
            base, params = parse_key(key)
            parts = [p.strip() for p in base.split(",")]
            inherited = None
            m0 = re.match(r"^(on|life|before|after|post)\s+(.+)$", parts[0])
            if m0:
                inherited = _pfx(m0.group(1))
                parts[0] = m0.group(2)
            names = []
            for part in parts:
                pfx = inherited
                m = re.match(r"^(on|life|before|after|post)\s+(.+)$", part)
                if m:
                    pfx = _pfx(m.group(1))
                    part = m.group(2)
                if part not in self.ctx.event_names:
                    raise Error("unknown event: " + part)
                if pfx is None:
                    raise Error("event %s needs an on/life/before/after/post "
                                "prefix" % part)
                names.append((part, pfx))
            groups = []
            for year, pfx in names:
                if groups and groups[-1][0] == pfx:
                    groups[-1][1].append(year)
                else:
                    groups.append((pfx, [year]))
            for pfx, years in groups:
                prm = params or ("s, ev, w, wh"
                                 if years[0] in ("Any", "Default")
                                 else "s, w, wh")
                src = self.handler(val, prm, indent)
                if len(years) > 1 and not target:
                    out.append('%s["%s%s"] = %s;'
                               % (indent, pfx, ",".join(years), src))
                else:
                    for year in years:
                        out.append("%s%s%s%s = %s;"
                                   % (indent, target, pfx, year, src))
        return out

    def obj(self, block, ident, base, ctor, preset, parent=None):
        prev = self.ctx.current_owner
        if ident:
            self.ctx.current_owner = ident
        try:
            return self._obj(block, ident, base, ctor, preset, parent)
        finally:
            self.ctx.current_owner = prev

    def expand_mixins(self, block):
        """Merge attached mixins' keys (own keys win)."""
        val = block.get("mixin")
        if val is None:
            return block
        CURRENT_LINE[0] = block.line("mixin") or CURRENT_LINE[0]
        own = {k for k, _ in block.items if k != "mixin"}
        merged = Block()
        seen = {}
        for v in (val if isinstance(val, list) else [val]):
            name = v.s if hasattr(v, "s") else str(v)
            bdef = self.ctx.mixin_defs.get(name)
            if bdef is None:
                raise Error("unknown mixin: " + name)
            for i, (k, bv) in enumerate(bdef.items):
                if k in seen:
                    raise Error("mixin key conflict: %s (%s and %s)"
                                % (k, seen[k], name))
                seen[k] = name
                if k in own:
                    continue
                merged.items.append((k, bv))
                merged.lines.append(bdef.line_at(i))
        for i, (k, bv) in enumerate(block.items):
            if k == "mixin":
                continue
            merged.items.append((k, bv))
            merged.lines.append(block.line_at(i))
        return merged

    def _obj(self, block, ident, base, ctor, preset, parent=None):
        block = self.expand_mixins(block)
        fi = base + IND
        lines = ["%s%s({" % (base, ctor) if parent
                 else "%s%s {" % (base, ctor)]
        self._obj_words(block, fi, lines)
        self._obj_nam(block, ident, fi, lines)
        attrs = self._obj_attrs(block, ident, preset)
        ntext = sum(1 for k, _v in block.items if k == "text")
        if ntext > 1:
            CURRENT_LINE[0] = block.line("text")
            raise Error("%s.text: set once; use a - list for pages"
                        % (self.ctx.current_owner or ident or "?"))
        self._obj_fields(block, ident, fi, lines)
        self._obj_nested(block, fi, lines)
        lines.append(self._obj_tail(block, ident, base, parent, attrs))
        return "\n".join(lines)

    def _obj_words(self, block, fi, lines):
        words = block.get("words")
        if words is None:
            return
        CURRENT_LINE[0] = block.line("words") or block.line("word")
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

    def _obj_nam(self, block, ident, fi, lines):
        if block.get("nam") is not None:
            CURRENT_LINE[0] = block.line("nam")
            raise Error("nam: is not supported; the declaration name is the "
                        "object name")
        if ident:
            lines.append("%snam = %s;" % (fi, lua_str(ident)))

    def _obj_attrs(self, block, ident, preset):
        attrs = list(preset)
        a = block.get("attrs")
        if a is not None:
            if isinstance(a, list):
                for x in a:
                    if isinstance(x, Text):
                        raise Error("%s.attrs: quotes are not allowed"
                                    % (ident or "?"))
                    if isinstance(x, Bare):
                        attrs.append(x.s)
            elif isinstance(a, Bare):
                attrs.append(a.s)
            elif isinstance(a, Text):
                raise Error("%s.attrs: quotes are not allowed"
                            % (ident or "?"))
        if attrs and "attr" in self.ctx.types:
            CURRENT_LINE[0] = block.line("attrs")
            for an in attrs:
                msg = type_value_error(self.ctx, "attr", an)
                if msg:
                    raise Error("%s.attrs: %s" % (ident or "?", msg))
        return attrs

    def _obj_fields(self, block, ident, fi, lines):
        for _i, (key, val) in enumerate(block.items):
            CURRENT_LINE[0] = block.line_at(_i)
            if key in ("words", "inside", "with", "attrs",
                       "disabled", "dict", "before", "after", "post"):
                continue
            if re.match(r"^(on|life|before|after|post)\s+\S", key):
                one = Block()
                one.items = [(key, val)]
                lines.extend(self.on(one, fi))
                continue
            fbase, params = parse_key(key)
            if fbase == "on":
                raise Error("on: must name an event (on Take:)")
            parts = [p.strip() for p in fbase.split(",")]
            if not re.match(r"^[a-z]+_", fbase):
                for part in parts:
                    if part in self.ctx.event_names:
                        raise Error("event %s needs an on/life/before/after/"
                                    "post prefix" % part)
            if not params:
                prop = self.ctx.props.get(fbase)
                for part in parts:
                    if part in self.ctx.ref_fields:
                        check_ref_value(ident or "?", key, val,
                                        self.ctx.ids,
                                        allow_text=bool(prop
                                                       and prop.has_reflist))
                        break
            try:
                rendered = self.body(val, key, fi)
            except Error as e:
                raise Error("%s.%s: %s" % (ident, key, e))
            if "," in fbase:
                lines.append('%s["%s"] = %s;' % (fi, fbase, rendered))
            else:
                lines.append("%s%s = %s;" % (fi, fbase, rendered))

    def _obj_nested(self, block, fi, lines):
        obj_items = []
        nested = []
        for key, val in block.items:
            if key in ("inside", "with"):
                if isinstance(val, Block):
                    for nk, nv in val.items:
                        nested.append(self.decl(nk, nv, fi + IND) + ";")
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

    def _obj_tail(self, block, ident, base, parent, attrs):
        if parent:
            tail = "%s}, %s)" % (base, parent)
        else:
            tail = "%s}" % base
        if attrs:
            tail += ":attr '%s'" % ",".join(attrs)
        d = block.get("dict")
        if d is not None:
            CURRENT_LINE[0] = block.line("dict")
            if not isinstance(d, (Data, Raw)):
                raise Error("%s.dict: must be a table literal { ... }"
                            % (ident or "?"))
            tail += ":dict %s" % self.value(d)
        if block.get("disabled"):
            tail += ":disable()"
        return tail

    def event(self, name, block):
        if not isinstance(block, Block):
            raise Error("event %s must be a block" % name)
        lines = []
        for key, val in block.items:
            base, params = parse_key(key)
            if base not in ("on", "before", "after"):
                raise Error("event %s: unknown field %r" % (name, key))
            if not isinstance(val, (Lua, Logic, Text, Bare)):
                raise Error("event %s.%s must be logic or lua" % (name, key))
            mpname = {"on": "mp.", "before": "mp.before_",
                      "after": "mp.after_"}[base] + name
            prm = params or ("s, ev, w, wh" if name in ("Any", "Default")
                             else "s, w, wh")
            lines.append("%s = %s" % (mpname, self.handler(val, prm, "")))
        return "\n".join(lines)

    def verb_fields(self, block, required):
        """Shared `words`/`patterns` fields of verb and extend verb."""
        label = "verb" if required else "extend"
        fields = []
        words = block.get("words")
        if words is None and required:
            raise Error("verb words must be a quoted string")
        if words is not None:
            if not isinstance(words, Text):
                raise Error("%s words must be a quoted string" % label)
            fields.append(lua_str(words.s))
        pats = block.get("patterns")
        if pats is not None:
            if not isinstance(pats, list):
                pats = [pats]
            for p in pats:
                fields.append(self.value(p))
        return fields

    def verb_extra(self, block):
        extra = []
        if block.get("prio") is not None:
            extra.append("prio = %s" % self.value(block.get("prio")))
        if block.get("hint") is not None:
            extra.append("hint = %s" % self.body(block.get("hint"), "hint"))
        return extra

    def verb(self, block, ident, base):
        fields = []
        tag = block.get("tag")
        if tag is None:
            fields.append("'#%s'" % ident)
        elif not (isinstance(tag, Bool) and tag.s == "false"):
            fields.append(self.value(tag))
        fields += self.verb_fields(block, required=True)
        for key, _val in block.items:
            base_key, _params = parse_key(key)
            if re.match(r"^(on|before|after)(\s|$)", base_key):
                raise Error("verb %s: %s is declared in 'event %s:' now"
                            % (ident or "?", base_key, ident or "?"))
        extra = self.verb_extra(block)
        return "%sVerb { %s%s }" % (base, ", ".join(fields),
                                    (", " + ", ".join(extra)) if extra else "")

    def verb_extend(self, block, ident, base):
        if not ident:
            raise Error("extend needs a verb tag")
        fields = [lua_str(ident)] + self.verb_fields(block, required=False)
        if len(fields) == 1:
            raise Error("extend needs words or patterns")
        for key, _val in block.items:
            base_key, _params = parse_key(key)
            if re.match(r"^(on|before|after)(\s|$)", base_key):
                raise Error("extend %s: %s is declared in 'event %s:' now"
                            % (ident, base_key, ident.lstrip("#")))
        extra = self.verb_extra(block)
        ctor = "VerbExtendWord" if block.get("words") is not None \
            else "VerbExtend"
        return "%s%s { %s%s }" % (base, ctor, ", ".join(fields),
                                  (", " + ", ".join(extra)) if extra else "")

    def talk_act(self, reply, do, indent):
        if do is None:
            return reply
        if isinstance(do, Logic):
            body = emit_logic(do.stmts, indent + IND, {"s": "obj"}, ctx=self.ctx)
        elif isinstance(do, Lua):
            body = [reindent(do.s, indent + IND)]
        else:
            raise Error("expected logic/lua block")
        if reply is not None:
            body = ["%sp(%s)" % (indent + IND, reply)] + body
        return ["%sfunction(s)" % indent] + body + ["%send" % indent]

    def talk_table(self, oblock, indent, labels, tag=None):
        dsc = None
        reply = None
        do = None
        named = []
        children = []
        for key, val in oblock.items:
            base, _ = parse_key(key)
            if base in ("ask", "say"):
                dsc = self.value(val)
            elif base == "reply":
                reply = self.value(val)
            elif base == "do":
                do = val
            elif base == "when":
                named.append("cond = function() return %s end"
                             % transpile_exprlist(sym_text(val), {},
                                                  "talk when", ctx=self.ctx)[0])
            elif base == "goto":
                named.append("next = '#%s'" % sym_text(val).lstrip('#'))
            elif base in ("always", "hidden", "only"):
                if is_true(val):
                    named.append("%s = true" % base)
            elif base == "option":
                children.append(self.talk_table(val, indent + IND, labels))
            elif key.startswith("label ") and isinstance(val, Block):
                labels.append((key[6:].strip(), val))
            else:
                named.append("%s = %s" % (base, self.body(val, key, indent + IND)))
        lines = ["%s{" % indent]
        if tag:
            lines.append("%s'%s';" % (indent + IND, tag))
        if dsc is not None:
            lines.append("%s%s;" % (indent + IND, dsc))
        act = self.talk_act(reply, do, indent + IND)
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

    def talk(self, block, name, base):
        fi = base + IND
        labels = []
        root = []
        fields = []
        for key, val in block.items:
            b, _ = parse_key(key)
            if key == "intro":
                root.append(self.value(val))
            elif b == "option":
                root.append(self.talk_table(val, fi + IND, labels))
            elif key.startswith("label ") and isinstance(val, Block):
                labels.append((key[6:].strip(), val))
            else:
                fields.append((key, val))
        lines = ["%sdlg {" % base, "%snam = '%s';" % (fi, name)]
        for key, val in fields:
            lines.append("%s%s = %s;" % (fi, key, self.body(val, key, fi)))
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
                lines.extend(self.talk_table(lblock, fi + IND, labels,
                                        tag="#" + lname))
                lines[-1] += ";"
            lines.append("%s};" % fi)
        lines.append("%s}" % base)
        return "\n".join(lines)

    def cls(self, block, name, parent):
        prev = self.ctx.current_owner
        self.ctx.current_owner = name
        try:
            body = self.obj(block, None, "", "Class", [], parent)
        finally:
            self.ctx.current_owner = prev
        return "%s = %s" % (name, body)

    def decl(self, key, block, base):
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
            return self.verb(block, ident, base)
        if kind == "extend":
            return self.verb_extend(block, ident, base)
        if kind == "talk":
            if not ident:
                raise Error("talk needs a name")
            return self.talk(block, ident, base)
        if kind not in PRESETS:
            if re.fullmatch(r"[A-Z][\w]*", kind):
                return self.obj(block, ident, base, kind, [])
            raise Error("unknown kind: " + kind)
        ctor, preset = PRESETS[kind]
        return self.obj(block, ident, base, ctor, preset)

    def _setup_fmt(self, block):
        fmt = block.get("fmt")
        out = []
        if fmt:
            vals = fmt if isinstance(fmt, list) else [fmt]
            for v in vals:
                if isinstance(v, (Bare, Text)):
                    out.append("fmt.%s = true" % v.s)
        return out

    def _setup_take(self, block):
        take = block.get("take")
        if not take:
            return []
        takes = take if isinstance(take, list) else [take]
        for t in takes:
            if not isinstance(t, (Bare, Text)):
                raise Error("take must list identifiers")
        return takes

    def _setup_nested(self, key, val):
        target = "pl." if key == "hero" else "game."
        out = []
        for hk, hv in val.items:
            if hk == "on":
                out.extend(self.on(hv, "", target))
            elif key == "hero" and hk == "words":
                out.append('pl.word = -"%s"' % hv.s)
            else:
                out.append("%s%s = %s" % (target, hk, self.body(hv, hk)))
        return out

    def _setup_start(self, val):
        if isinstance(val, Lua):
            sb = reindent(val.s, IND)
        elif isinstance(val, Logic):
            sb = "\n".join(emit_logic(val.stmts, IND, {"load": "bool"},
                                      ctx=self.ctx))
        else:
            raise Error("start must be a | block")
        return ["function start(load)", sb, "end"]

    def _setup_init(self, takes, block):
        out = ["function init()"]
        for t in takes:
            out.append("%stake('%s')" % (IND, t.s))
        init = block.get("init")
        if isinstance(init, Lua):
            out.append(reindent(init.s, IND))
        elif isinstance(init, Logic):
            out.extend(emit_logic(init.stmts, IND, ctx=self.ctx))
        out.append("end")
        return out

    def setup(self, block):
        lines = self._setup_fmt(block)
        takes = self._setup_take(block)
        for key, val in block.items:
            if key in ("take", "fmt", "init"):
                continue
            if key in ("hero", "game") and isinstance(val, Block):
                lines.extend(self._setup_nested(key, val))
                continue
            if key == "on":
                lines.extend(self.on(val, "", "game."))
                continue
            if key == "dsc":
                lines.append("game.dsc = %s" % self.body(val, "dsc"))
                continue
            if key == "start":
                lines.extend(self._setup_start(val))
                continue
            raise Error("unknown setup key: " + key)
        lines.extend(self._setup_init(takes, block))
        return lines

    def impl(self, target, block):
        block = self.expand_mixins(block)
        t = target.strip()
        if (t.startswith("'") and t.endswith("'")) or (
                t.startswith('"') and t.endswith('"')):
            t = t[1:-1]
        # objects/instances/modules are looked up by name; a class
        # (`Kitten`) is a plain global variable
        if t in self.ctx.fields and t not in self.ctx.ids:
            ref = t
        else:
            ref = "_'%s'" % t
        prev = self.ctx.current_owner
        if t in self.ctx.fields:
            self.ctx.current_owner = t
        try:
            lines = []
            for i, (key, val) in enumerate(block.items):
                CURRENT_LINE[0] = block.line_at(i)
                base, _ = parse_key(key)
                if base == "on":
                    raise Error("on: must name an event (on Take:)")
                if re.match(r"^(on|life|before|after|post)\s+\S", key):
                    one = Block()
                    one.items = [(key, val)]
                    lines.extend(self.on(one, "", ref + "."))
                elif not re.match(r"^[a-z]+_", base) and any(
                        p.strip() in self.ctx.event_names
                        for p in base.split(",")):
                    raise Error("event %s needs an on/life/before/after/post "
                                "prefix" % base)
                elif base == "dict":
                    if not isinstance(val, (Data, Raw)):
                        raise Error("impl %s.dict: must be a table literal "
                                    "{ ... }" % t)
                    lines.append("%s:dict %s" % (ref, self.value(val)))
                elif key.startswith("var "):
                    name = parse_key(key[4:])[0]
                    lines.append("%s.%s = %s"
                                 % (ref, name, self.body(val, name)))
                else:
                    if "," in base:
                        raise Error("comma key needs a phase "
                                    "(on/life/before/after/post)")
                    lines.append("%s.%s = %s"
                                 % (ref, base, self.body(val, key)))
        finally:
            self.ctx.current_owner = prev
        return "\n".join(lines)

    def pragma(self, block, kw):
        return ["%s '%s' (%s)" % (kw, key, self.value(val))
                for key, val in block.items]

    def const(self, block):
        return self.pragma(block, "const")

    def glob(self, block):
        return self.pragma(block, "global")
