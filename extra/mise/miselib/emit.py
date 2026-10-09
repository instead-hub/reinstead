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


def _group_years(names):
    """Group `(event, prefix)` pairs into runs sharing a prefix."""
    groups = []
    for year, pfx in names:
        if groups and groups[-1][0] == pfx:
            groups[-1][1].append(year)
        else:
            groups.append((pfx, [year]))
    return groups


# the non-object declarations and the Emitter methods they use
DECL_FORMS = {
    "verb": "verb",
    "extend": "verb_extend",
    "talk": "talk",
}

# the declarations whose name is required
NAMED_DECLS = ("verb", "talk")

# the setup keys and the Emitter methods they use
SETUP_FORMS = {
    "hero": "_setup_nested",
    "game": "_setup_nested",
    "on": "_setup_game_on",
    "dsc": "_setup_dsc_line",
    "start": "_setup_start_lines",
}

# the setup keys that expect a nested block
SETUP_BLOCKS = ("hero", "game")

# the talk phrase fields and the Emitter methods they use
TALK_FORMS = {
    "ask": "_talk_dsc",
    "say": "_talk_dsc",
    "reply": "_talk_reply",
    "do": "_talk_do",
    "when": "_talk_when",
    "goto": "_talk_goto",
    "always": "_talk_flag",
    "hidden": "_talk_flag",
    "only": "_talk_flag",
    "option": "_talk_option",
}

# the object keys emitted by their own helpers or nested constructs
OBJ_SKIP_KEYS = ("words", "inside", "with", "attrs",
                 "disabled", "dict", "before", "after", "post")


def _value_text(v, _mode, _ctx):
    return lua_str(v.s)


def _value_lua(v, mode, ctx):
    return "function(%s)\n%s\nend" % (ctx.prop_params.get(mode, "s"), v.s)


def _value_bare(v, _mode, ctx):
    return "'%s'" % v.s if v.s in ctx.ids else lua_str(v.s)


def _value_raw(v, _mode, _ctx):
    return v.s


def _value_nil(_v, _mode, _ctx):
    return "nil"


VALUE_FORMS = {
    Text: _value_text,
    Lua: _value_lua,
    Bare: _value_bare,
    Num: _value_raw,
    Bool: _value_raw,
    Raw: _value_raw,
    Data: _value_raw,
    Nil: _value_nil,
}


def _emit_event(em, name, block):
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
        lines.append("%s = %s" % (mpname, em.handler(val, prm, "")))
    return "\n".join(lines)


class Emitter:
    def __init__(self, ctx):
        self.ctx = ctx

    def value(self, v, mode="s"):
        if isinstance(v, list):
            return "{ %s }" % ", ".join(self.value(x, mode) for x in v)
        form = VALUE_FORMS.get(type(v))
        if form is None:
            raise Error("unsupported value: %r (ctx=%s)" % (v, mode))
        return form(v, mode, self.ctx)

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
            return self._lua_body(v, prm, indent)
        if isinstance(v, Logic):
            return self._logic_body(v, prm, indent, env, ret, ret_name)
        return self.value(v)

    def _lua_body(self, v, prm, indent):
        return "function(%s)\n%s\n%s" % (prm, reindent(v.s, indent + IND),
                                         indent + "end")

    def _logic_body(self, v, prm, indent, env, ret, ret_name):
        senv = self.param_env(prm) if env is None else env
        body = "\n".join(emit_logic(v.stmts, indent + IND, senv, ret,
                                    ret_name, ctx=self.ctx))
        return "function(%s)\n%s\n%s" % (prm, body, indent + "end")

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
            params, names = self._on_parts(key)
            for pfx, years in _group_years(names):
                prm = params or ("s, ev, w, wh"
                                 if years[0] in ("Any", "Default")
                                 else "s, w, wh")
                src = self.handler(val, prm, indent)
                if len(years) > 1 and not target:
                    out.append('%s["%s%s"] = %s;'
                               % (indent, pfx, ",".join(years), src))
                else:
                    out.extend("%s%s%s%s = %s;"
                               % (indent, target, pfx, year, src)
                               for year in years)
        return out

    def _on_parts(self, key):
        base, params = parse_key(key)
        parts = [p.strip() for p in base.split(",")]
        first = self._event_prefix(parts[0])
        inherited = first[0] if first is not None else None
        return params, [self._on_name(part, inherited) for part in parts]

    def _event_prefix(self, part):
        m = re.match(r"^(on|life|before|after|post)\s+(.+)$", part)
        if not m:
            return None
        return _pfx(m.group(1)), m.group(2)

    def _on_name(self, part, inherited):
        found = self._event_prefix(part)
        pfx, name = found if found is not None else (inherited, part)
        if name not in self.ctx.event_names:
            raise Error("unknown event: " + name)
        if pfx is None:
            raise Error("event %s needs an on/life/before/after/post "
                        "prefix" % name)
        return name, pfx

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
            self._merge_mixin(merged, seen, own, bdef, name)
        self._merge_own(merged, block)
        return merged

    def _merge_mixin(self, merged, seen, own, bdef, name):
        for i, (k, bv) in enumerate(bdef.items):
            if k in seen:
                raise Error("mixin key conflict: %s (%s and %s)"
                            % (k, seen[k], name))
            seen[k] = name
            if k in own:
                continue
            merged.items.append((k, bv))
            merged.lines.append(bdef.line_at(i))

    def _merge_own(self, merged, block):
        for i, (k, bv) in enumerate(block.items):
            if k == "mixin":
                continue
            merged.items.append((k, bv))
            merged.lines.append(block.line_at(i))

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
        attrs.extend(self._extra_attrs(block, ident))
        if attrs and "attr" in self.ctx.types:
            CURRENT_LINE[0] = block.line("attrs")
            for an in attrs:
                msg = type_value_error(self.ctx, "attr", an)
                if msg:
                    raise Error("%s.attrs: %s" % (ident or "?", msg))
        return attrs

    def _extra_attrs(self, block, ident):
        a = block.get("attrs")
        if a is None:
            return []
        if isinstance(a, list):
            return self._attrs_items(a, ident)
        if isinstance(a, Bare):
            return [a.s]
        if isinstance(a, Text):
            raise Error("%s.attrs: quotes are not allowed" % (ident or "?"))
        return []

    def _attrs_items(self, items, ident):
        out = []
        for x in items:
            if isinstance(x, Text):
                raise Error("%s.attrs: quotes are not allowed"
                            % (ident or "?"))
            if isinstance(x, Bare):
                out.append(x.s)
        return out

    def _obj_fields(self, block, ident, fi, lines):
        for _i, (key, val) in enumerate(block.items):
            CURRENT_LINE[0] = block.line_at(_i)
            lines.extend(self._obj_field(key, val, ident, fi))

    def _obj_field(self, key, val, ident, fi):
        if key in OBJ_SKIP_KEYS:
            return []
        if re.match(r"^(on|life|before|after|post)\s+\S", key):
            one = Block()
            one.items = [(key, val)]
            return self.on(one, fi)
        fbase, params = parse_key(key)
        if fbase == "on":
            raise Error("on: must name an event (on Take:)")
        self._check_event_prefix(fbase)
        if not params:
            self._check_ref_value(ident, key, val, fbase)
        try:
            rendered = self.body(val, key, fi)
        except Error as e:
            raise Error("%s.%s: %s" % (ident, key, e))
        if "," in fbase:
            return ['%s["%s"] = %s;' % (fi, fbase, rendered)]
        return ["%s%s = %s;" % (fi, fbase, rendered)]

    def _check_event_prefix(self, fbase):
        if re.match(r"^[a-z]+_", fbase):
            return
        for part in (p.strip() for p in fbase.split(",")):
            if part in self.ctx.event_names:
                raise Error("event %s needs an on/life/before/after/"
                            "post prefix" % part)

    def _check_ref_value(self, ident, key, val, fbase):
        prop = self.ctx.props.get(fbase)
        for part in (p.strip() for p in fbase.split(",")):
            if part in self.ctx.ref_fields:
                check_ref_value(ident or "?", key, val, self.ctx.ids,
                                allow_text=bool(prop and prop.has_reflist))
                break

    def _obj_nested(self, block, fi, lines):
        blobs = self._nested_blobs(block, fi)
        if not blobs:
            return
        lines.append("%sobj = {" % fi)
        for k, b in enumerate(blobs):
            if k:
                lines.append("")
            lines.extend(b.split("\n"))
        lines.append("%s};" % fi)

    def _nested_blobs(self, block, fi):
        obj_items = []
        nested = []
        for key, val in block.items:
            if key not in ("inside", "with"):
                continue
            if isinstance(val, Block):
                nested.extend(self._nested_decls(val, fi + IND))
            else:
                obj_items.extend(self._nested_refs(key, val, fi + IND))
        blobs = ["\n".join(obj_items)] if obj_items else []
        return blobs + nested

    def _nested_decls(self, val, ind):
        return [self.decl(nk, nv, ind) + ";" for nk, nv in val.items]

    def _nested_refs(self, key, val, ind):
        refs = val if isinstance(val, list) else [val]
        out = []
        for r in refs:
            if not isinstance(r, Bare):
                raise Error("%s must list bare identifiers, not quoted "
                            "strings (%s)" % (key, key))
            if not re.fullmatch(r"[#@\w]+", r.s, re.UNICODE):
                raise Error("%s: object name must be an identifier without "
                            "spaces/hyphens (%r)" % (key, r.s))
            out.append("%s'%s';" % (ind, r.s))
        return out

    def _obj_tail(self, block, ident, base, parent, attrs):
        tail = "%s}, %s)" % (base, parent) if parent else "%s}" % base
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
        return _emit_event(self, name, block)

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
        body = self._talk_body(do, indent)
        if reply is None:
            return ["%sfunction(s)" % indent] + body + ["%send" % indent]
        act = ["%sfunction(s)" % indent, "%sp(%s)" % (indent + IND, reply)]
        return act + body + ["%send" % indent]

    def _talk_body(self, do, indent):
        if isinstance(do, Logic):
            return emit_logic(do.stmts, indent + IND, {"s": "obj"},
                              ctx=self.ctx)
        if isinstance(do, Lua):
            return [reindent(do.s, indent + IND)]
        raise Error("expected logic/lua block")

    def talk_table(self, oblock, indent, labels, tag=None):
        named = []
        children = []
        specials = {"dsc": None, "reply": None, "do": None}
        for key, val in oblock.items:
            self._talk_item(key, val, indent, labels, named, children,
                            specials)
        lines = ["%s{" % indent]
        if tag:
            lines.append("%s'%s';" % (indent + IND, tag))
        if specials["dsc"] is not None:
            lines.append("%s%s;" % (indent + IND, specials["dsc"]))
        act = self.talk_act(specials["reply"], specials["do"], indent + IND)
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

    def _talk_dsc(self, _base, _key, val, _indent, _labels, _named, _children,
                  specials):
        specials["dsc"] = self.value(val)

    def _talk_reply(self, _base, _key, val, _indent, _labels, _named,
                    _children, specials):
        specials["reply"] = self.value(val)

    def _talk_do(self, _base, _key, val, _indent, _labels, _named, _children,
                 specials):
        specials["do"] = val

    def _talk_when(self, _base, _key, val, _indent, _labels, named, _children,
                   _specials):
        named.append("cond = function() return %s end"
                     % transpile_exprlist(sym_text(val), {}, "talk when",
                                          ctx=self.ctx)[0])

    def _talk_goto(self, _base, _key, val, _indent, _labels, named, _children,
                   _specials):
        named.append("next = '#%s'" % sym_text(val).lstrip('#'))

    def _talk_flag(self, base, _key, val, _indent, _labels, named, _children,
                   _specials):
        if is_true(val):
            named.append("%s = true" % base)

    def _talk_option(self, _base, _key, val, indent, labels, _named,
                     children, _specials):
        children.append(self.talk_table(val, indent + IND, labels))

    def _talk_item(self, key, val, indent, labels, named, children, specials):
        base, _ = parse_key(key)
        handler = TALK_FORMS.get(base)
        if handler is not None:
            getattr(self, handler)(base, key, val, indent, labels, named,
                                   children, specials)
        elif key.startswith("label ") and isinstance(val, Block):
            labels.append((key[6:].strip(), val))
        else:
            named.append("%s = %s" % (base, self.body(val, key, indent + IND)))

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
        handler = DECL_FORMS.get(kind)
        if handler is not None:
            if not ident and kind in NAMED_DECLS:
                raise Error("%s needs a name" % kind)
            return getattr(self, handler)(block, ident, base)
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
        sb = self._start_body(val)
        return ["function start(load)", sb, "end"]

    def _start_body(self, val):
        if isinstance(val, Lua):
            return reindent(val.s, IND)
        if isinstance(val, Logic):
            return "\n".join(emit_logic(val.stmts, IND, {"load": "bool"},
                                        ctx=self.ctx))
        raise Error("start must be a | block")

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

    def _setup_game_on(self, _key, val):
        return self.on(val, "", "game.")

    def _setup_dsc_line(self, _key, val):
        return ["game.dsc = %s" % self.body(val, "dsc")]

    def _setup_start_lines(self, _key, val):
        return self._setup_start(val)

    def setup(self, block):
        lines = self._setup_fmt(block)
        takes = self._setup_take(block)
        for key, val in block.items:
            if key in ("take", "fmt", "init"):
                continue
            if key in SETUP_BLOCKS and not isinstance(val, Block):
                raise Error("unknown setup key: " + key)
            handler = SETUP_FORMS.get(key)
            if handler is None:
                raise Error("unknown setup key: " + key)
            lines.extend(getattr(self, handler)(key, val))
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
        ref = (t if t in self.ctx.fields and t not in self.ctx.ids
               else "_'%s'" % t)
        prev = self.ctx.current_owner
        if t in self.ctx.fields:
            self.ctx.current_owner = t
        try:
            lines = []
            for i, (key, val) in enumerate(block.items):
                CURRENT_LINE[0] = block.line_at(i)
                lines.extend(self._impl_item(key, val, ref, t))
        finally:
            self.ctx.current_owner = prev
        return "\n".join(lines)

    def _impl_item(self, key, val, ref, t):
        base, _ = parse_key(key)
        if base == "on":
            raise Error("on: must name an event (on Take:)")
        if re.match(r"^(on|life|before|after|post)\s+\S", key):
            one = Block()
            one.items = [(key, val)]
            return self.on(one, "", ref + ".")
        self._check_impl_prefix(base)
        if base == "dict":
            if not isinstance(val, (Data, Raw)):
                raise Error("impl %s.dict: must be a table literal "
                            "{ ... }" % t)
            return ["%s:dict %s" % (ref, self.value(val))]
        if key.startswith("var "):
            name = parse_key(key[4:])[0]
            return ["%s.%s = %s" % (ref, name, self.body(val, name))]
        if "," in base:
            raise Error("comma key needs a phase "
                        "(on/life/before/after/post)")
        return ["%s.%s = %s" % (ref, base, self.body(val, key))]

    def _check_impl_prefix(self, base):
        if re.match(r"^[a-z]+_", base):
            return
        if any(p.strip() in self.ctx.event_names for p in base.split(",")):
            raise Error("event %s needs an on/life/before/after/post prefix"
                        % base)

    def const(self, block):
        return ["const '%s' (%s)" % (key, self.value(val))
                for key, val in block.items]

    def glob(self, block):
        return ["global '%s' (%s)" % (key, self.value(val))
                for key, val in block.items]
