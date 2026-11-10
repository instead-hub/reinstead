"""Minimalist recursive-descent parser for MISE 2."""
from typing import Any, List, Optional, Tuple
from .ast_nodes import *
from .lexer import Token, tokenize

PHASES = frozenset({"on", "before", "after", "post", "life"})
META_KEYS = frozenset({"game", "name", "version", "author", "info"})
# Kind keywords are not known here: `obj`/`room`/`story` are classes declared in
# core.mise, and a declaration is recognised by its shape (`Kind name`).
STMT_KWS = frozenset({
    "if", "elseif", "else", "match", "for", "in", "of",
    "local", "return", "stop", "pass", "break", "and", "or", "not",
})
_BIN_PREC = {
    "or": 1, "and": 2,
    "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3,
    "..": 4, "+": 4, "-": 4,
    "*": 5, "/": 5, "%": 5, "//": 5,
}


class Parser:
    def __init__(self, tokens: List[Token], src_name: str = "", raw_src: str = ""):
        self.tokens, self.pos, self.src = tokens, 0, src_name
        self.raw_lines = raw_src.splitlines() if raw_src else []

    def cur(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, n: int = 1) -> Token:
        return self.tokens[min(self.pos + n, len(self.tokens) - 1)]

    def at(self, kind: str, val: Optional[str] = None) -> bool:
        t = self.cur()
        return t.kind == kind and (val is None or t.val == val)

    def eat(self, kind: str, val: Optional[str] = None) -> Token:
        t = self.cur()
        if t.kind != kind or (val is not None and t.val != val):
            raise Error(f"expected {val or kind}, got {t.val!r}", t.line, self.src)
        self.pos += 1
        return t

    def match(self, kind: str, val: Optional[str] = None) -> Optional[Token]:
        if self.at(kind, val):
            self.pos += 1
            return self.tokens[self.pos - 1]
        return None

    def skip_nl(self):
        while self.at("NEWLINE"):
            self.pos += 1

    def eat_nl(self):
        if not self.at("EOF") and not self.at("DEDENT"):
            self.eat("NEWLINE")
        self.skip_nl()

    def sym(self) -> str:
        t = self.cur()
        if t.kind in ("IDENT", "TAG", "TILDE_ID"):
            self.pos += 1
            return t.val
        raise Error(f"expected symbol, got {t.val!r}", t.line, self.src)

    def sym_list(self) -> List[str]:
        res = [self.sym()]
        while self.match("OP", ","):
            res.append(self.sym())
        return res

    # --- Top Level ---

    def parse_program(self) -> Program:
        prog = Program()
        self.skip_nl()
        while not self.at("EOF"):
            self._top_item(prog)
            self.skip_nl()
        return prog

    def _top_item(self, prog: Program):
        t = self.cur()
        kw = t.val
        if kw in META_KEYS and (self.peek().kind in ("STRING", "ISTRING") or self.peek().val == "="):
            self.pos += 1
            self.match("OP", "=")
            prog.meta.append(("name" if kw == "game" else kw, self.eat(self.cur().kind).val))
            return self.eat_nl()
        if kw == "lang":
            self.pos += 1
            self.match("OP", "=")
            prog.lang = self.eat("IDENT").val
            return self.eat_nl()
        if kw in ("include", "require", "fmt"):
            self.pos += 1
            self.match("OP", "=")
            getattr(prog, kw + ("s" if kw != "fmt" else "")).extend(self.sym_list())
            return self.eat_nl()
        if kw == "extend":
            self.pos += 1
            if self.match("IDENT", "type"):
                return prog.items.append(self._parse_type(extend=True))
            if self.match("IDENT", "event"):
                return prog.items.extend(self._parse_event(True, t.line))
            self.match("IDENT", "verb")
            return prog.items.append(self._parse_verb("extend", t.line))
        if kw == "remove":
            self.pos += 1
            self.match("IDENT", "verb")
            tag = self.eat("TAG").val
            self.eat_nl()
            return prog.items.append(VerbDecl(name=tag, mode="remove", line=t.line))
        if kw == "type":
            self.pos += 1
            return prog.items.append(self._parse_type(extend=False))
        if kw == "event":
            self.pos += 1
            prog.items.extend(self._parse_event(False, t.line))
            return
        if kw == "entry":
            self.pos += 1
            tok = self.eat("IDENT")
            line, name = tok.line, tok.val
            params = self._opt_params()
            self.eat_nl()
            prog.items.append(EntryDecl(name=name, params=params, line=line))
            return
        if kw == "extern":
            return prog.items.append(self._parse_fn(is_extern=True))
        if kw in ("global", "const"):
            return prog.items.append(self._parse_vars())
        if kw == "fn":
            return prog.items.append(self._parse_fn(is_extern=False))
        if kw == "verb":
            self.pos += 1
            return prog.items.append(self._parse_verb("verb", t.line))
        if kw == "event":
            return prog.items.append(self._parse_event(prog))
        if kw == "talk":
            return prog.items.append(self._parse_talk())
        if kw == "setup":
            return prog.items.extend(self._parse_setup(prog))
        if kw == "lua":
            return prog.items.append(self._parse_lua())
        prog.items.append(self._parse_entity())

    # --- Types, Vars, Fns ---

    def _parse_type_str(self, single: bool = False, names: Optional[List[str]] = None) -> str:
        """`single` stops the `->` return list at a comma: inside a parameter list
        `fn(a) -> b, c` means "a callback returning b, then a parameter c"."""
        res = [self._parse_type_atom(names, single)]
        while self.match("OP", "|"):
            res.append(self._parse_type_atom(names, single))
        return "|".join(res)

    def _parse_type_atom(self, names: Optional[List[str]], single: bool = False) -> str:
        t = self.cur()
        if t.val == "fn" and self.peek().val == "(":
            self.pos += 2
            pts = []
            if not self.at("OP", ")"):
                while True:
                    pname = None
                    if self.cur().kind == "IDENT" and self.peek().val == ":":
                        pname = self.cur().val
                        self.pos += 2
                    pts.append(self._parse_type_str(single=True))
                    if pname and names is not None:
                        names.append(pname)
                    if not self.match("OP", ","):
                        break
            self.eat("OP", ")")
            ret = ""
            if self.match("OP", "->"):
                rts = [self._parse_type_str(single)]
                while not single and self.match("OP", ","):
                    rts.append(self._parse_type_str())
                ret = "->" + ",".join(rts)
            return f"fn({','.join(pts)}){ret}{'?' if self.match('OP', '?') else ''}"
        if t.val == "tbl" and self.peek().val == "[":
            self.pos += 2
            inner = self._parse_type_str(single)
            self.eat("OP", "]")
            return f"tbl[{inner}]{'?' if self.match('OP', '?') else ''}"
        if t.val == "ref" and self.peek().val == "[":
            # `ref[C]` — a reference to an object of class C (`ref` is `ref[obj]`)
            self.pos += 2
            inner = self._parse_type_str(single)
            self.eat("OP", "]")
            return f"ref[{inner}]{'?' if self.match('OP', '?') else ''}"
        return self.eat("IDENT").val + ("?" if self.match("OP", "?") else "")

    def _parse_sig(self) -> List[str]:
        """`[`: `type, type]` after a name — the arguments an event passes.

        A bare `event X:` (the colon with nothing after it) means "no arguments",
        so a table of signatures can keep its colons aligned.
        """
        if not self.match("OP", ":") or self.at("NEWLINE"):
            return []
        args = [self._parse_type_str()]
        while self.match("OP", ","):
            args.append(self._parse_type_str())
        return args

    def _parse_type(self, extend: bool) -> TypeDecl:
        line = self.cur().line
        name = self.eat("IDENT").val
        self.match("OP", "=")
        neg, vals = False, []
        in_brackets = bool(self.match("OP", "["))
        while not self.at("EOF") and not (self.at("OP", "]") if in_brackets else self.at("NEWLINE")):
            if self.match("OP", "~"):
                neg = True
            elif not in_brackets or self.cur().kind in ("IDENT", "NUMBER", "TILDE_ID"):
                vals.append(self.cur().val)
                self.pos += 1
            else:
                raise Error(f"invalid enum value {self.cur().val!r}",
                            self.cur().line, self.src)
            if not self.match("OP", ",") and not in_brackets:
                break
        if in_brackets:
            self.eat("OP", "]")
        self.eat_nl()
        return TypeDecl(name=name, values=vals, negate=neg, extend=extend, line=line)

    def _parse_param_list(self, default_s: bool = False, typed: bool = True
                          ) -> Tuple[List[Tuple[str, Any]], Optional[str]]:
        """Parse `(a: T, b: U, ...: V)` parameter list."""
        params: List[Tuple[str, Any]] = []
        var: Optional[str] = None
        if not self.match("OP", "("):
            return params, var
        while not self.at("OP", ")") and not self.at("EOF"):
            if default_s and self.match("OP", "..."):
                var = self._parse_type_str(single=True) if self.match("OP", ":") else "any"
                break
            pn = self.eat("IDENT").val
            if self.match("OP", ":"):
                pt: Any = self._parse_type_str(single=True)
            else:
                pt = ("obj" if (default_s and pn == "s") else "any") if typed else None
            params.append((pn, pt))
            if not self.match("OP", ","):
                break
        self.eat("OP", ")")
        return params, var

    def _parse_fn(self, is_extern: bool) -> Any:
        line = self.eat("IDENT").line
        is_value = False
        if is_extern:
            kind = self.eat("IDENT")
            if kind.val == "global":
                name = self.eat("IDENT").val
                self.eat("OP", ":")
                typ = self._parse_type_str()
                self.eat("OP", "=")
                tmpl = self.eat(self.cur().kind).val
                self.eat_nl()
                return GlobalDecl(name=name, typ=typ, template=tmpl, line=kind.line)
            if kind.val not in ("fn", "value"):
                raise Error(f"extern {kind.val}: expected `fn`, `value` or `global`", kind.line, self.src)
            is_value = kind.val == "value"
        name = self.eat("IDENT").val
        params, var = self._parse_param_list(default_s=True, typed=True)
        rets = []
        if self.match("OP", "->"):
            rets.append(self._parse_type_str())
            while self.match("OP", ","):
                rets.append(self._parse_type_str())
        if is_extern or self.match("OP", "=") or self.at("RAW"):
            self.match("OP", "=")
            raw = self.eat(self.cur().kind).val
            self.eat_nl()
            return FnDecl(name=name, params=params, variadic=var, ret_types=rets, body=raw,
                          is_extern=is_extern, is_value=is_value, line=line)
        body = self._opt_lua_or_stmts()
        return FnDecl(name=name, params=params, variadic=var, ret_types=rets, body=body, line=line)

    def _opt_lua_or_stmts(self) -> Any:
        if self.at("NEWLINE") and self.peek().kind == "INDENT" and self.peek(2).val == "lua":
            self.eat_nl()
            self.eat("INDENT")
            code = self._parse_lua().code
            self.eat("DEDENT")
            return code
        return self.parse_stmt_block()

    def _parse_vars(self) -> VarDecl:
        kind = self.eat("IDENT").val
        items = []
        if self.match("NEWLINE"):
            self.skip_nl()
            self.eat("INDENT")
            while not self.at("DEDENT") and not self.at("EOF"):
                vn = self.eat("IDENT").val
                self.eat("OP", "=")
                items.append((vn, self.parse_expr(), self.cur().line))
                self.eat_nl()
            self.eat("DEDENT")
        else:
            vn = self.eat("IDENT").val
            self.eat("OP", "=")
            items.append((vn, self.parse_expr(), self.cur().line))
            self.eat_nl()
        return VarDecl(kind=kind, items=items)

    def _parse_lua(self) -> LuaDecl:
        line = self.eat("IDENT", "lua").line
        self.eat_nl()
        start_line = self.eat("INDENT").line
        depth = 1
        while depth > 0 and not self.at("EOF"):
            depth += (1 if self.at("INDENT") else -1 if self.at("DEDENT") else 0)
            if depth == 0:
                break
            self.pos += 1
        end_line = self.cur().line if not self.at("EOF") else len(self.raw_lines) + 1
        self.match("DEDENT")
        lines = self.raw_lines[start_line - 1:end_line - 1]
        ind = min((len(l) - len(l.lstrip(" \t")) for l in lines if l.strip()), default=0)
        return LuaDecl(code="\n".join(l[ind:] for l in lines).rstrip(), line=line)

    # --- Unified Entity (`class`, `obj`, `room`, `impl`, ...) ---

    def _parse_entity(self) -> EntityDecl:
        tok = self.eat("IDENT")
        kind = "class" if tok.val == "mixin" else tok.val
        name = self.sym() if (kind == "impl" or self.cur().kind in ("IDENT", "TAG")) else None
        parent = None
        if kind == "class" and self.match("OP", "("):
            parent = self.eat("IDENT").val
            self.eat("OP", ")")
        words = self._header_words()
        traits = self.sym_list() if (self.match("OP", ":") and not self.at("NEWLINE")) else []
        locs = self.sym_list() if self.match("OP", "@") else []
        ctor = None
        if kind == "class" and self.match("OP", "="):
            ctor = self.eat("IDENT").val
            while self.match("OP", "."):
                ctor += "." + self.eat("IDENT").val
        ent = EntityDecl(kind=kind, name=name, parent=parent, ctor=ctor, words=words, traits=traits,
                         locations=locs, line=tok.line, src=self.src)
        self.eat_nl()
        if self.match("INDENT"):
            self._parse_members(ent)
            self.eat("DEDENT")
        return ent

    def _parse_members(self, ent: EntityDecl):
        while not self.at("DEDENT") and not self.at("EOF"):
            t = self.cur()
            kw = t.val
            if (kw in PHASES and self.peek().kind == "IDENT") or (
                kw.startswith(("before_", "after_", "post_", "life_")) and self.peek().val != "="
            ):
                ent.handlers.append(self._parse_handler())
                continue
            if kw == "words":
                raise Error('words live in the header: write `obj name "слово|слово"` '
                            '(or `obj name [...]`) instead of a `words =` member',
                            t.line, self.src)
            if kw[:1].islower() and kw not in PHASES and self.peek().kind == "IDENT" \
                    and self.peek(2).val not in ("=", "(", "@", ","):
                import difflib
                near = difflib.get_close_matches(kw, sorted(PHASES), 1, 0.75)
                if near:
                    raise Error(f"bad field name {kw + ' ' + self.peek().val!r} "
                                f"(did you mean {near[0] + ' ' + self.peek().val!r}?)",
                                t.line, self.src)
            if self._is_nested_entity():
                ent.children.append(self._parse_entity())
                continue
            pname = self.eat("IDENT").val
            prms = self._opt_ident_parens()

            if ent.kind == "class" and self.match("OP", ":"):
                type_params: List[str] = []
                typ = self._parse_type_str(names=type_params)
                emit = self._field_emit()
                ent.props.append(Prop(name=pname, typ=typ, emit=emit,
                                      type_params=type_params, line=t.line))
                self.eat_nl()
                continue

            if not self.match("OP", "="):
                raise Error(f"{pname}: a member is written with '=' "
                            f"(`{pname} = value` or `{pname} =` and an indented body)",
                            t.line, self.src)
            val = self._value_after_eq()
            ent.props.append(Prop(name=pname, value=val, params=prms, line=t.line))

    def _opt_params(self) -> List[Tuple[str, str]]:
        """`(a, b: obj)` after a name."""
        params, _ = self._parse_param_list(default_s=False, typed=True)
        return params

    def _field_emit(self) -> Optional[Emit]:
        """`= method with(each)` — how a declared field's value reaches Lua."""
        if not self.match("OP", "="):
            return None
        kw = self.eat("IDENT")
        if kw.val != "method":
            raise Error(f"expected `method` after '=', got {kw.val!r}", kw.line, self.src)
        mname = self.eat("IDENT").val           # the engine method name
        form = "each"
        if self.match("OP", "("):
            if not self.at("OP", ")"):
                form = self.eat("IDENT").val
            self.eat("OP", ")")
        if form not in ("each", "join", "list", "table", "none"):
            raise Error(f"unknown method form {form!r} (each, join, list, table, none)",
                        self.cur().line, self.src)
        other = ""
        if self.match("IDENT", "else"):        # `= method disable(none) else enable`
            other = self.eat("IDENT").val
        return Emit(method=mname, form=form, other=other)

    def _header_words(self, allow_empty: bool = True) -> List[str]:
        """A single string or a `[...]` list of strings (`words`, `patterns`)."""
        if self.cur().kind in ("STRING", "ISTRING"):
            return [self.eat(self.cur().kind).val]
        if self.at("OP", "[") or not allow_empty:
            self.eat("OP", "[")
            res = []
            while not self.at("OP", "]") and not self.at("EOF"):
                res.append(self.eat(self.cur().kind).val)
                if not self.match("OP", ","):
                    break
            self.eat("OP", "]")
            return res
        return []

    def _str_or_list(self) -> List[str]:
        res = self._header_words(allow_empty=False)
        self.eat_nl()
        return res

    def _is_nested_entity(self) -> bool:
        """`Kind name` starts a nested declaration; a member is always `key = ...`."""
        return self.peek().kind in ("IDENT", "TAG")

    def _value_after_eq(self) -> Any:
        """After `=`: a value on the same line, or an indented body.

        A body is a block of statements (or a `lua` block); a `-` list is still
        read as a list value until lists become `[...]` literals everywhere.
        """
        if not self.at("NEWLINE"):
            val = self._parse_prop_val()
            self.eat_nl()
            return val
        self.eat_nl()
        self.eat("INDENT")
        if self.at("OP", "-"):
            raise Error("a `-` list is gone: write a `[...]` list after '=' "
                        "(`text = [\"page 1\", \"page 2\"]` or a multi-line `[` block)",
                        self.cur().line, self.src)
        if self.at("IDENT", "lua"):
            val = Lit(line=self.cur().line, kind="lua", val=self._parse_lua().code)
            self.eat("DEDENT")
            return val
        stmts = []
        while not self.at("DEDENT") and not self.at("EOF"):
            stmts.append(self.parse_stmt())
            self.skip_nl()
        self.eat("DEDENT")
        return stmts

    def _opt_ident_parens(self) -> Optional[List[str]]:
        if not self.match("OP", "("):
            return None
        prms = self.sym_list() if not self.at("OP", ")") else []
        self.eat("OP", ")")
        return prms

    def _parse_prop_val(self) -> Any:
        if self.at("OP", "{"):
            return self._raw_braces()
        if self.match("OP", "&"):
            return FnRef(line=self.cur().line, name=self.eat("IDENT").val)
        first = self.parse_expr()
        if self.at("OP", ","):
            items = [first]
            while self.match("OP", ","):
                items.append(self.parse_expr())
            return ListLit(line=first.line, items=items)
        return first

    def _raw_braces(self) -> Lit:
        line = self.eat("OP", "{").line
        depth, parts, pline = 1, ["{"], line
        while depth > 0 and not self.at("EOF"):
            t = self.cur()
            self.pos += 1
            parts.append("\n" if t.line > pline else (" " if t.spaced else ""))
            pline = t.line
            if t.kind == "OP" and t.val in "{}":
                depth += (1 if t.val == "{" else -1)
                parts.append(t.val)
            elif t.kind in ("STRING", "ISTRING"):
                parts.append('"' + t.val.replace("\\", "\\\\").replace('"', '\\"') + '"')
            else:
                parts.append("~=" if (t.kind == "OP" and t.val == "!=") else t.val)
        return Lit(line=line, kind="table", val="".join(parts))

    def _parse_handler(self) -> Handler:
        tok = self.eat("IDENT")
        if "_" in tok.val and tok.val.split("_", 1)[0] in PHASES:
            phase, first_ev = tok.val.split("_", 1)
            evs = [first_ev]
            while self.match("OP", ","):
                evs.append(self.eat("IDENT").val)
        else:
            phase = tok.val
            evs = self.sym_list()
        prms = self._opt_ident_parens()
        self.match("OP", "->")
        label = f"{phase} {','.join(evs)}"
        return Handler(phase=phase, events=evs, params=prms,
                       body=self._parse_handler_body(label), line=tok.line)

    def _parse_handler_body(self, label: str = "") -> Any:
        """A handler always takes `=`: a value on the line, or a body below it."""
        if self.match("OP", "="):
            if self.match("IDENT", "pass"):
                self.eat_nl()
                return "pass"
            if self.match("IDENT", "stop"):
                self.eat_nl()
                return "stop"
            return self._value_after_eq()
        t = self.cur()
        where = label or "a handler"
        raise Error(f"{where}: a handler is written with '=' (`{where} = …` or "
                    f"`{where} =` and an indented body)", t.line, self.src)

    def _parse_event(self, extend: bool, line: int) -> List[Any]:
        """`event A, B: obj, str` — a signature; a block adds handlers for one name.

        `extend event` replaces the arguments of an event that is declared already
        (the engine's own signatures live in `core.mise`). A block of phases needs a
        single name: with several names it would be unclear which one it belongs to.
        """
        names = self.sym_list()
        types = self._parse_sig()
        sig = EventsDecl(extend=extend, line=line, sigs=[(names, types)])
        self.eat_nl()
        handlers: List[Handler] = []
        has_block = bool(self.match("INDENT"))
        if has_block:
            if len(names) > 1:
                raise Error(f"event {', '.join(names)}: a handler block needs a single name",
                            line, self.src)
            handlers = self._parse_event_handlers(names[0])
            self.eat("DEDENT")
        out: List[Any] = [sig]
        if has_block:
            out.append(EntityDecl(kind="impl", name="mp", traits=list(names),
                                  handlers=handlers, line=line))
        return out

    def _parse_event_handlers(self, name: str) -> List[Handler]:
        """The phase lines of an `event` block: `on = …`, `before = …` (no name)."""
        handlers: List[Handler] = []
        while not self.at("DEDENT") and not self.at("EOF"):
            ptok = self.eat("IDENT")
            if ptok.val not in PHASES:
                raise Error(f"event {name}: unknown phase {ptok.val!r}", ptok.line, self.src)
            prms = self._opt_ident_parens()
            handlers.append(Handler(phase=ptok.val, events=[name], params=prms,
                                    body=self._parse_handler_body(), line=ptok.line))
        return handlers

    def _parse_setup(self, prog: Program) -> List[Any]:
        """`setup` is sugar: it expands into `impl game`/`impl pl`, `fn init`/`fn start`."""
        line = self.eat("IDENT", "setup").line
        game = EntityDecl(kind="impl", name="game", line=line)
        hero: Optional[EntityDecl] = None
        fns: dict = {}
        self.eat_nl()
        self.eat("INDENT")
        while not self.at("DEDENT") and not self.at("EOF"):
            t = self.cur()
            kw = t.val
            if kw in ("dsc", "fmt"):
                self.pos += 1
                self.eat("OP", "=")
                if kw == "fmt":
                    prog.fmt.extend(self.sym_list())
                else:
                    game.props.append(Prop(name="dsc", value=self._parse_str_tok(), line=t.line))
                self.eat_nl()
            elif kw in ("hero", "game"):
                self.pos += 1
                target = EntityDecl(kind="impl", name="pl", line=t.line) if kw == "hero" else game
                target.words.extend(self._header_words())
                self.eat("OP", "=")
                self.eat_nl()
                self.eat("INDENT")
                self._parse_members(target)
                self.eat("DEDENT")
                if kw == "hero":
                    hero = target
            elif kw in ("init", "start"):
                self.pos += 1
                self._opt_ident_parens()
                self.eat("OP", "=")
                prms = [("load", "bool")] if kw == "start" else []
                fns[kw] = FnDecl(name=kw, params=prms, body=self.parse_stmt_block(), line=line)
            elif kw in PHASES:
                game.handlers.append(self._parse_handler())
            else:
                hint = " (write `init =` and `take …` there)" if kw == "take" else ""
                raise Error(f"unknown setup field {kw!r}{hint}", t.line, self.src)
        self.eat("DEDENT")
        return [x for x in (game, hero, fns.get("init"), fns.get("start")) if x is not None]

    # --- Verbs & Talk (`*` / `+` Choice Syntax) ---

    def _parse_verb(self, mode: str, line: int) -> VerbDecl:
        name = self.eat("TAG").val if mode == "extend" else self.eat("IDENT").val
        target = self.sym() if self.match("IDENT", "for") else None
        vd = VerbDecl(name=name, mode=mode, target=target, line=line)
        self.eat_nl()
        self.eat("INDENT")
        while not self.at("DEDENT") and not self.at("EOF"):
            ktok = self.eat("IDENT")
            k = ktok.val
            if k == "hint":
                vd.hint = self._parse_handler_body()
                continue
            self.eat("OP", "=")
            if k == "tag":
                vd.tag = "" if self.match("IDENT", "false") else self.eat("TAG").val
                self.eat_nl()
            elif k == "target":
                vd.target = self.sym()
                self.eat_nl()
            elif k == "prio":
                vd.prio = int(self.eat("NUMBER").val)
                self.eat_nl()
            elif k in ("words", "patterns"):
                setattr(vd, k, self._str_or_list())
            else:
                raise Error(f"unknown verb field {k!r}", ktok.line, self.src)
        self.eat("DEDENT")
        return vd

    def _parse_talk(self) -> TalkDecl:
        line = self.eat("IDENT", "talk").line
        td = TalkDecl(name=self.sym(), line=line)
        self.eat_nl()
        self.eat("INDENT")
        while not self.at("DEDENT") and not self.at("EOF"):
            t = self.cur()
            if t.val == "intro":
                self.pos += 1
                td.intro = self._parse_handler_body()
            elif t.val == "label":
                self.pos += 1
                lname = self.eat("IDENT").val
                self.eat_nl()
                self.eat("INDENT")
                lsay, lchoices = None, []
                while not self.at("DEDENT") and not self.at("EOF"):
                    if self.at("OP", "*") or self.at("OP", "+"):
                        lchoices.append(self._parse_choice())
                    elif self.match("IDENT", "say"):
                        lsay = self._parse_handler_body()
                    else:
                        raise Error(f"unexpected item {self.cur().val!r} in talk label "
                                    f"(expected `say = …` or a `*`/`+` choice)",
                                    self.cur().line, self.src)
                self.eat("DEDENT")
                td.labels.append((lname, lsay, lchoices))
            elif t.kind == "OP" and t.val in ("*", "+"):
                td.choices.append(self._parse_choice())
            else:
                pn = self.eat("IDENT").val
                self.eat("OP", "=")
                td.props.append(Prop(name=pn, value=self.parse_expr(), line=t.line))
                self.eat_nl()
        self.eat("DEDENT")
        return td

    def _parse_choice(self) -> TalkChoice:
        mtok = self.eat("OP")
        c = TalkChoice(sticky=(mtok.val == "+"), flags=["always"] if mtok.val == "+" else [], line=mtok.line)
        if self.match("OP", "["):
            c.cond = self.parse_expr()
            self.eat("OP", "]")
        c.ask = FnRef(line=mtok.line, name=self.eat("IDENT").val) if self.match("OP", "&") else self._parse_str_tok()
        while not self.at("NEWLINE") and not self.at("EOF"):
            if self.cur().val in ("hidden", "only", "always"):
                c.flags.append(self.eat("IDENT").val)
            elif self.match("OP", "->"):
                c.next_label = self.eat("IDENT").val
        self.eat_nl()
        if self.match("INDENT"):
            first = True
            while not self.at("DEDENT") and not self.at("EOF"):
                if self.at("OP", "*") or self.at("OP", "+"):
                    c.children.append(self._parse_choice())
                elif self.cur().val in ("onempty", "when", "ask", "reply", "do"):
                    kw = self.eat("IDENT").val
                    setattr(c, {"when": "cond"}.get(kw, kw), self._parse_handler_body())
                elif self.match("OP", "->"):
                    c.next_label = self.eat("IDENT").val
                    self.eat_nl()
                else:
                    st = self.parse_stmt()
                    self.skip_nl()
                    if first and isinstance(st, SayStmt) and st.mode == "p":
                        c.reply = st.expr
                    else:
                        c.do.append(st)
                first = False
            self.eat("DEDENT")
        return c

    # --- Statements ---

    def parse_stmt_block(self) -> List[Stmt]:
        self.eat_nl()
        self.eat("INDENT")
        stmts = []
        while not self.at("DEDENT") and not self.at("EOF"):
            stmts.append(self.parse_stmt())
            self.skip_nl()
        self.eat("DEDENT")
        return stmts

    def parse_stmt(self) -> Stmt:
        t = self.cur()
        line = t.line
        if t.kind in ("STRING", "ISTRING"):
            e = self._parse_str_tok()
            mode = "pr" if self.match("OP", "~") else "p"
            self.eat_nl()
            return SayStmt(line=line, expr=e, mode=mode)
        if t.kind == "IDENT":
            kw = t.val
            if kw in ("stop", "pass", "break"):
                self.pos += 1
                self.eat_nl()
                return ReturnStmt(line=line, kind=kw)
            if kw == "return":
                self.pos += 1
                vals = self.parse_expr_list() if not (self.at("NEWLINE") or self.at("DEDENT")) else []
                self.eat_nl()
                return ReturnStmt(line=line, kind="return", values=vals)
            if kw == "local":
                self.pos += 1
                names = []
                while True:
                    vn = self.eat("IDENT").val
                    vt = self._parse_type_str() if self.match("OP", ":") else None
                    names.append((vn, vt))
                    if not self.match("OP", ","):
                        break
                vals = self.parse_expr_list() if self.match("OP", "=") else []
                self.skip_nl()      # a block-bodied lambda already consumed it
                return LocalStmt(line=line, names=names, values=vals)
            if kw == "if":
                return self._parse_if()
            if kw == "match":
                return self._parse_match()
            if kw == "for":
                return self._parse_for()

        lhs = self.parse_postfix()
        if self.cur().kind == "OP" and self.cur().val in ("=", "+=", "-="):
            op = self.eat("OP").val
            vals = self.parse_expr_list()
            self.skip_nl()          # a block-bodied lambda already consumed it
            return AssignStmt(line=line, target=lhs, op=op, values=vals)

        if self.match("OP", ":"):
            m = self.eat("IDENT").val
            args = self._app_args()
            self.skip_nl()          # a block-bodied lambda already consumed it
            return CallStmt(line=line, call=Call(line=line, func=m, receiver=lhs, args=args))
        if isinstance(lhs, Sym):
            args = self._app_args()
            self.skip_nl()
            return CallStmt(line=line, call=Call(line=line, func=lhs.name, args=args))
        raise Error("expected statement", line, self.src)

    def _parse_cond(self) -> Expr:
        """A condition: an expression, or `x := expr` / `a, b := expr`."""
        save = self.pos
        if self.cur().kind == "IDENT":
            line = self.cur().line
            names = [self.eat("IDENT").val]
            while self.match("OP", ","):
                if self.cur().kind != "IDENT":
                    names = []
                    break
                names.append(self.eat("IDENT").val)
            if names and self.match("OP", ":="):
                return Bind(line=line, names=names, value=self.parse_expr())
        self.pos = save
        return self.parse_expr()

    def _parse_if(self) -> IfStmt:
        line = self.eat("IDENT").line
        cond = self._parse_cond()
        branches = [(cond, self.parse_stmt_block(), line)]
        while self.at("IDENT", "elseif"):
            el = self.eat("IDENT").line
            ec = self._parse_cond()
            branches.append((ec, self.parse_stmt_block(), el))
        else_body = self.parse_stmt_block() if self.match("IDENT", "else") else None
        return IfStmt(line=line, branches=branches, else_body=else_body)

    def _parse_match(self) -> MatchStmt:
        line = self.eat("IDENT", "match").line
        subj = self.parse_expr()
        self.eat_nl()
        self.eat("INDENT")
        arms = []
        while not self.at("DEDENT") and not self.at("EOF"):
            al = self.cur().line
            pats = [Sym(line=al, name="_") if self.match("IDENT", "_") else self.parse_primary()]
            while self.match("OP", ","):
                pats.append(Sym(line=al, name="_") if self.match("IDENT", "_") else self.parse_primary())
            guard = self.parse_expr() if self.match("IDENT", "when") else None
            self.eat("OP", "->")
            body = self.parse_stmt_block() if self.at("NEWLINE") else [self.parse_stmt()]
            arms.append((pats, guard, body, al))
            self.skip_nl()
        self.eat("DEDENT")
        return MatchStmt(line=line, subject=subj, arms=arms)

    def _parse_for(self) -> Stmt:
        line = self.eat("IDENT", "for").line
        vn = self.eat("IDENT").val
        vt = self._parse_type_str() if self.match("OP", ":") else None
        if self.match("OP", "="):
            a = self.parse_expr()
            self.eat("OP", ",")
            b = self.parse_expr()
            step = self.parse_expr() if self.match("OP", ",") else None
            return ForNumStmt(line=line, var=vn, var_type=vt, start=a, stop=b, step=step, body=self.parse_stmt_block())
        vlist = [(vn, vt)]
        while self.match("OP", ","):
            n2 = self.eat("IDENT").val
            t2 = self._parse_type_str() if self.match("OP", ":") else None
            vlist.append((n2, t2))
        is_of = bool(self.match("IDENT", "of"))
        if not is_of:
            self.eat("IDENT", "in")
        return ForInStmt(line=line, vars=vlist, iter_expr=self.parse_expr(), is_of=is_of, body=self.parse_stmt_block())

    # --- Expressions (Pratt + ML Application) ---

    def parse_expr_list(self) -> List[Expr]:
        res = [self.parse_expr()]
        while self.match("OP", ","):
            res.append(self.parse_expr())
        return res

    def parse_expr(self, min_prec: int = 1) -> Expr:
        # `not` binds looser than comparisons (as in Python): `not x in a, b`
        if min_prec <= _BIN_PREC["=="] and self.match("IDENT", "not"):
            line = self.tokens[self.pos - 1].line
            left = UnaryOp(line=line, op="not", operand=self.parse_expr(_BIN_PREC["=="]))
        else:
            left = self.parse_unary()
        while True:
            t = self.cur()
            if t.kind == "IDENT" and min_prec <= _BIN_PREC["=="] and (
                t.val == "in" or (t.val == "not" and self.peek().val == "in")
            ):
                neg = self.match("IDENT", "not") is not None
                self.eat("IDENT", "in")
                alts = [self.parse_expr(_BIN_PREC["=="] + 1)]
                while self.match("OP", ","):
                    alts.append(self.parse_expr(_BIN_PREC["=="] + 1))
                in_op = InOp(line=t.line if neg else left.line, subject=left, alts=alts)
                left = UnaryOp(line=t.line, op="not", operand=in_op) if neg else in_op
                continue
            op = t.val if (t.kind == "OP" or (t.kind == "IDENT" and t.val in ("and", "or"))) else ""
            prec = _BIN_PREC.get(op, 0)
            if prec < min_prec:
                break
            self.pos += 1
            left = BinOp(line=left.line, op=op, left=left, right=self.parse_expr(prec + 1))
        return left

    def parse_unary(self) -> Expr:
        if self.match("IDENT", "not"):
            return UnaryOp(line=self.cur().line, op="not", operand=self.parse_unary())
        if self.match("OP", "-"):
            return UnaryOp(line=self.cur().line, op="-", operand=self.parse_unary())
        return self.parse_app()

    def parse_app(self) -> Expr:
        """Application by juxtaposition: `f a b`, `obj:m a`. Parentheses only group."""
        base = self.parse_postfix()
        while self.match("OP", ":"):
            m = self.eat("IDENT").val
            base = Call(line=base.line, func=m, receiver=base, args=self._app_args())
            base = self._postfix_tail(base)
        if isinstance(base, Sym) and self._can_start_arg():
            return Call(line=base.line, func=base.name, args=self._app_args())
        return base

    def _app_args(self) -> List[Expr]:
        """Arguments of one call: atoms up to the next operator or end of line."""
        args = []
        while self._can_start_arg():
            arg = self.parse_postfix()
            args.append(arg)
            if isinstance(arg, Lambda) and isinstance(arg.body, list):
                break               # a block-bodied lambda closes the argument list
        return args

    def _can_start_arg(self) -> bool:
        t = self.cur()
        if t.kind in ("NUMBER", "STRING", "ISTRING", "TAG", "TILDE_ID", "RAW"):
            return True
        if t.kind == "IDENT":
            return t.val not in STMT_KWS
        return t.kind == "OP" and t.val in ("(", "[", "{", "&")

    def parse_postfix(self) -> Expr:
        return self._postfix_tail(self.parse_primary())

    def _postfix_tail(self, atom: Expr) -> Expr:
        while True:
            if self.match("OP", "."):
                atom = FieldAccess(line=atom.line, obj=atom, field=self.eat("IDENT").val)
            elif self.at("OP", "[") and not self.cur().spaced:
                self.pos += 1
                idx = self.parse_expr()
                self.eat("OP", "]")
                atom = IndexAccess(line=atom.line, obj=atom, index=idx)
            else:
                break
        return atom

    def _parse_lambda(self) -> Expr:
        line = self.eat("OP", "&").line
        params, _ = self._parse_param_list(default_s=False, typed=False)
        body: Any = self.parse_stmt_block() if self.at("NEWLINE") else self.parse_expr()
        return Lambda(line=line, params=params, body=body)

    def parse_primary(self) -> Expr:
        t = self.cur()
        if t.kind == "NUMBER":
            self.pos += 1
            return Lit(line=t.line, kind="num", val=float(t.val) if "." in t.val else int(t.val))
        if t.kind in ("STRING", "ISTRING"):
            return self._parse_str_tok()
        if t.kind == "RAW":
            self.pos += 1
            return Lit(line=t.line, kind="raw", val=t.val)
        if t.kind == "IDENT":
            self.pos += 1
            if t.val in ("true", "false"):
                return Lit(line=t.line, kind="bool", val=(t.val == "true"))
            if t.val == "nil":
                return Lit(line=t.line, kind="nil")
            return Sym(line=t.line, name=t.val)
        if t.kind in ("TAG", "TILDE_ID"):
            self.pos += 1
            return Sym(line=t.line, name=t.val)
        if self.at("OP", "&") and self.peek().val == "(":
            return self._parse_lambda()
        if self.match("OP", "&"):
            return FnRef(line=t.line, name=self.eat("IDENT").val)
        if self.match("OP", "("):
            if self.at("OP", ")"):
                raise Error("empty parentheses are not a call: write the name alone "
                            "(`walkout`) or use a block", t.line, self.src)
            e = self.parse_expr()
            if self.at("OP", ","):
                raise Error("unexpected ',': arguments are separated by spaces "
                            "(`f a b`); a comma is only allowed in `[...]`/`{...}`",
                            self.cur().line, self.src)
            self.eat("OP", ")")
            return e
        if self.match("OP", "[") or self.match("OP", "{"):
            close = "]" if t.val == "[" else "}"
            items = []
            while not self.at("OP", close) and not self.at("EOF"):
                items.append(self.parse_expr())
                if not self.match("OP", ","):
                    break
            self.eat("OP", close)
            return ListLit(line=t.line, items=items)
        raise Error(f"unexpected token {t.val!r}", t.line, self.src)

    def _parse_str_tok(self) -> Expr:
        t = self.eat(self.cur().kind)
        if t.kind == "STRING":
            return Lit(line=t.line, kind="str", val=t.val)
        return _split_interp_str(t.val, t.line, self.src)


def _interp_end(s: str, start: int) -> int:
    """The `}` closing the `{` at `start`, counting nested braces (`{tbl[1]}`,
    `{ {1,2} }`) and skipping string literals inside the expression."""
    depth, i, n = 1, start + 1, len(s)
    while i < n:
        ch = s[i]
        if ch in "\"'":
            i += 1
            while i < n and s[i] != ch:
                i += 2 if s[i] == "\\" else 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_interp_str(s: str, line: int, src: str) -> Expr:
    parts: List[Any] = []
    i, n = 0, len(s)
    while i < n:
        j = s.find("{", i)
        if j == -1:
            parts.append(s[i:])
            break
        if j + 1 < n and s[j + 1] in "$#":     # `{$fmt …}` — the engine's own markup
            k = s.find("}", j + 1)
            end = (k + 1) if k != -1 else n
            parts.append(s[i:end])
            i = end
            continue
        k = _interp_end(s, j)
        if k == -1:
            parts.append(s[i:])
            break
        if j > i:
            parts.append(s[i:j])
        parts.append(Parser(tokenize(s[j + 1:k].strip(), src), src).parse_expr())
        i = k + 1
    if len(parts) == 1 and isinstance(parts[0], str):
        return Lit(line=line, kind="str", val=parts[0])
    return InterpStr(line=line, parts=parts)


def parse_source(src: str, src_name: str = "") -> Program:
    return Parser(tokenize(src, src_name), src_name, src).parse_program()
