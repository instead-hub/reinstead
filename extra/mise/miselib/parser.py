"""Minimalist recursive-descent parser for MISE 2."""
from typing import Any, List, Optional, Tuple
from .ast_nodes import *
from .lexer import Token, tokenize

PHASES = frozenset({"on", "before", "after", "post", "life"})
META_KEYS = frozenset({"game", "name", "version", "author", "info"})
TOP_KINDS = frozenset({"obj", "room", "door", "story", "ending", "class"})
STMT_KWS = frozenset({
    "if", "elseif", "else", "when", "default", "match", "for", "in", "of",
    "local", "return", "stop", "pass", "break", "and", "or", "not", "then",
})
_BIN_PREC = {
    "or": 1, "and": 2,
    "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3,
    "..": 4, "+": 4, "-": 4,
    "*": 5, "/": 5, "%": 5, "//": 5,
}


def _looks_like_kind(kw: str) -> bool:
    """A member head that may start a nested declaration (`obj`, a class, ...)."""
    return kw in TOP_KINDS or kw == "mixin" or kw[:1].isupper()


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

    def _parse_type_str(self) -> str:
        res = [self._parse_type_atom()]
        while self.match("OP", "|"):
            res.append(self._parse_type_atom())
        return "|".join(res)

    def _parse_type_atom(self) -> str:
        t = self.cur()
        if t.val == "fn" and self.peek().val == "(":
            self.pos += 2
            pts = []
            if not self.at("OP", ")"):
                while True:
                    if self.cur().kind == "IDENT" and self.peek().val == ":":
                        self.pos += 2
                    pts.append(self._parse_type_str())
                    if not self.match("OP", ","):
                        break
            self.eat("OP", ")")
            ret = ""
            if self.match("OP", "->"):
                rts = [self._parse_type_str()]
                while self.match("OP", ","):
                    rts.append(self._parse_type_str())
                ret = "->" + ",".join(rts)
            return f"fn({','.join(pts)}){ret}{'?' if self.match('OP', '?') else ''}"
        if t.val == "tbl" and self.peek().val == "[":
            self.pos += 2
            inner = self._parse_type_str()
            self.eat("OP", "]")
            return f"tbl[{inner}]{'?' if self.match('OP', '?') else ''}"
        return self.eat("IDENT").val + ("?" if self.match("OP", "?") else "")

    def _parse_type(self, extend: bool) -> TypeDecl:
        line = self.cur().line
        name = self.eat("IDENT").val
        if name == "event":
            self.match("OP", "=")
            self.eat_nl()
            self.eat("INDENT")
            sigs = []
            while not self.at("DEDENT") and not self.at("EOF"):
                life = bool(self.match("IDENT", "life"))
                evs = self.sym_list()
                ats = []
                if self.match("OP", ":") or self.match("OP", "="):
                    if not self.at("NEWLINE"):
                        ats.append(self._parse_type_str())
                        while self.match("OP", ","):
                            ats.append(self._parse_type_str())
                sigs.append((life, evs, ats))
                self.eat_nl()
            self.eat("DEDENT")
            return TypeDecl(name="event", extend=extend, event_sigs=sigs, line=line)

        self.match("OP", "=")
        neg, vals = False, []

        def read_vals():
            nonlocal neg
            while not self.at("NEWLINE") and not self.at("EOF"):
                if self.match("OP", "~"):
                    neg = True
                else:
                    vals.append(self.cur().val)
                    self.pos += 1
                if not self.match("OP", ","):
                    break

        if self.match("OP", "["):
            while not self.at("OP", "]") and not self.at("EOF"):
                if self.match("OP", "~"):
                    neg = True
                elif self.cur().kind in ("IDENT", "NUMBER", "TILDE_ID"):
                    vals.append(self.cur().val)
                    self.pos += 1
                else:
                    raise Error(f"invalid enum value {self.cur().val!r}",
                                self.cur().line, self.src)
                self.match("OP", ",")
            self.eat("OP", "]")
            self.eat_nl()
        else:
            read_vals()
            self.eat_nl()
        return TypeDecl(name=name, values=vals, negate=neg, extend=extend, line=line)

    def _parse_fn(self, is_extern: bool) -> FnDecl:
        line = self.eat("IDENT").line
        if is_extern:
            kind = self.eat("IDENT")
            if kind.val != "fn":
                raise Error(f"extern {kind.val}: expected `fn`", kind.line, self.src)
        name = self.eat("IDENT").val
        params, var = [], None
        if self.match("OP", "("):
            if not self.at("OP", ")"):
                while True:
                    if self.match("OP", "..."):
                        var = self._parse_type_str() if self.match("OP", ":") else "any"
                        break
                    pn = self.eat("IDENT").val
                    pt = self._parse_type_str() if self.match("OP", ":") else ("obj" if pn == "s" else "any")
                    params.append((pn, pt))
                    if not self.match("OP", ","):
                        break
            self.eat("OP", ")")
        rets = []
        if self.match("OP", "->"):
            rets.append(self._parse_type_str())
            while self.match("OP", ","):
                rets.append(self._parse_type_str())
        if is_extern or self.match("OP", "=") or self.at("RAW"):
            self.match("OP", "=")
            raw = self.eat(self.cur().kind).val
            self.eat_nl()
            return FnDecl(name=name, params=params, variadic=var, ret_types=rets, body=raw, is_extern=is_extern, line=line)
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
        ent = EntityDecl(kind=kind, name=name, parent=parent, words=words, traits=traits,
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
            if kw in ("attr", "attrs", "mixin") and self.peek().val != ":":
                self.pos += 1
                self.eat("OP", "=")
                ent.traits.extend(self.sym_list())
                self.eat_nl()
                continue
            if kw == "with":
                self.pos += 1
                if self.match("OP", "="):
                    ent.with_refs.extend(self.sym_list())
                    self.eat_nl()
                    continue
                if self.match("NEWLINE"):
                    self.skip_nl()
                    self.eat("INDENT")
                    while not self.at("DEDENT") and not self.at("EOF"):
                        if self.match("OP", "-"):
                            ent.with_refs.extend(self.sym_list())
                            self.eat_nl()
                        else:
                            ent.children.append(self._parse_entity())
                    self.eat("DEDENT")
                else:
                    raise Error("with: expected '=' before reference names or an indented block "
                                "of nested declarations", t.line, self.src)
                continue
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

            if kw == "var" and self.peek().kind == "IDENT":
                self.pos += 1
            pname = self.eat("IDENT").val
            prms = self._opt_ident_parens()

            if ent.kind == "class" and self.match("OP", ":"):
                ent.props.append(Prop(name=pname, typ=self._parse_type_str(), line=t.line))
                self.eat_nl()
                continue

            if self.match("OP", "="):
                val = self._value_after_eq()
                ent.props.append(Prop(name=pname, value=val, params=prms, line=t.line))
            elif self.at("NEWLINE") and self.peek().kind == "INDENT":
                self.eat_nl()
                self.eat("INDENT")
                if self.at("IDENT", "lua"):
                    val = Lit(line=t.line, kind="raw", val=self._parse_lua().code)
                elif self.at("OP", "-"):
                    raise Error(f"{pname}: expected '=' before a `-` list value "
                                f"(write `{pname} =` and indent the list)", t.line, self.src)
                else:
                    val = []
                    while not self.at("DEDENT") and not self.at("EOF"):
                        val.append(self.parse_stmt())
                        self.skip_nl()
                self.eat("DEDENT")
                ent.props.append(Prop(name=pname, value=val, params=prms, line=t.line))
            else:
                raise Error(f"{pname}: expected '=' before a value "
                            f"(write `{pname} = …`) or an indented block for a body",
                            t.line, self.src)

    def _header_words(self) -> List[str]:
        """Words of a declaration live in its header: `obj hook "крючок|вешалка"`."""
        if self.cur().kind in ("STRING", "ISTRING"):
            return [self.eat(self.cur().kind).val]
        if self.at("OP", "["):
            self.pos += 1
            res = []
            while not self.at("OP", "]") and not self.at("EOF"):
                res.append(self.eat(self.cur().kind).val)
                if not self.match("OP", ","):
                    break
            self.eat("OP", "]")
            return res
        return []

    def _is_nested_entity(self) -> bool:
        """`Kind name` starts a nested declaration; a property always has `=` or a body."""
        t, nxt = self.cur(), self.peek()
        if t.val in TOP_KINDS or t.val == "mixin":
            return nxt.val != "="
        return nxt.kind in ("IDENT", "TAG") and self.peek(2).val not in ("=", "(", ":")

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
            val = Lit(line=self.cur().line, kind="raw", val=self._parse_lua().code)
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

    def _str_or_list(self) -> List[str]:
        """A single string or a `[...]` list of strings (`words`, `patterns`)."""
        if self.cur().kind in ("STRING", "ISTRING"):
            s = self.eat(self.cur().kind).val
            self.eat_nl()
            return [s]
        self.eat("OP", "[")
        res = []
        while not self.at("OP", "]") and not self.at("EOF"):
            res.append(self.eat(self.cur().kind).val)
            if not self.match("OP", ","):
                break
        self.eat("OP", "]")
        self.eat_nl()
        return res

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
        return Handler(phase=phase, events=evs, params=prms, body=self._parse_handler_body(), line=tok.line)

    def _parse_handler_body(self) -> Any:
        """A handler value (`=` + value) or its body (indented block, `pass`/`stop`)."""
        if self.match("OP", "="):
            return self._value_after_eq()
        if self.match("IDENT", "pass"):
            self.eat_nl()
            return "pass"
        if self.match("IDENT", "stop"):
            self.eat_nl()
            return "stop"
        t = self.cur()
        if t.kind in ("STRING", "ISTRING", "RAW", "NUMBER") or (t.kind == "OP" and t.val in ("&", "{")):
            raise Error("a handler value needs '=' (write `before Take = "
                        + ("&fn" if t.val == "&" else "\"…\"") + "`); an indented block is a body",
                        t.line, self.src)
        res = self._opt_lua_or_stmts()
        return Lit(line=self.cur().line, kind="raw", val=res) if isinstance(res, str) else res

    def _parse_event(self, prog: Program) -> EntityDecl:
        """`event X` registers an event and is sugar for `impl mp : X`."""
        line = self.eat("IDENT", "event").line
        name = self.eat("IDENT").val
        ent = EntityDecl(kind="impl", name="mp", traits=[name], line=line)
        self.eat_nl()
        if self.match("INDENT"):
            while not self.at("DEDENT") and not self.at("EOF"):
                ptok = self.eat("IDENT")
                if ptok.val not in ("on", "before", "after", "post"):
                    raise Error(f"event {name}: unknown phase {ptok.val!r}", ptok.line, self.src)
                prms = self._opt_ident_parens()
                ent.handlers.append(Handler(phase=ptok.val, events=[name], params=prms,
                                            body=self._parse_handler_body(), line=ptok.line))
            self.eat("DEDENT")
        return ent

    def _parse_setup(self, prog: Program) -> List[Any]:
        """`setup` is sugar: it expands into `impl game`/`impl pl`, `fn init`/`fn start`."""
        line = self.eat("IDENT", "setup").line
        game = EntityDecl(kind="impl", name="game", line=line)
        hero = None
        init_body: Optional[List[Stmt]] = None
        start_body: Optional[List[Stmt]] = None
        init_head: List[Stmt] = []
        self.eat_nl()
        self.eat("INDENT")
        while not self.at("DEDENT") and not self.at("EOF"):
            t = self.cur()
            kw = t.val
            if kw in ("dsc", "fmt", "take"):
                self.pos += 1
                self.eat("OP", "=")
                if kw == "fmt":
                    prog.fmt.extend(self.sym_list())
                    self.eat_nl()
                elif kw == "dsc":
                    val = self._parse_str_tok()
                    game.props.append(Prop(name="dsc", value=val, line=t.line))
                    self.eat_nl()
                else:
                    for name in self.sym_list():
                        init_head.append(CallStmt(line=t.line, call=Call(
                            line=t.line, func="take", args=[Sym(line=t.line, name=name)])))
                    self.eat_nl()
            elif kw in ("hero", "game"):
                self.pos += 1
                sub = EntityDecl(kind="impl", name="pl" if kw == "hero" else "game", line=t.line)
                sub.words.extend(self._header_words())
                self.eat("OP", "=")
                self.eat_nl()
                self.eat("INDENT")
                self._parse_members(sub)
                self.eat("DEDENT")
                if kw == "hero":
                    hero = sub
                else:
                    game.props.extend(sub.props)
                    game.handlers.extend(sub.handlers)
            elif kw in ("init", "start"):
                self.pos += 1
                prms = self._opt_ident_parens()
                self.eat("OP", "=")
                body = self.parse_stmt_block()
                fn = FnDecl(name=kw, params=[(pn, "bool" if pn == "load" else "any") for pn in (prms or [])],
                            body=body, line=t.line)
                if kw == "init":
                    init_body = body
                else:
                    start_body = body
            elif kw in PHASES:
                game.handlers.append(self._parse_handler())
            else:
                raise Error(f"unknown setup field {kw!r}", t.line, self.src)
        self.eat("DEDENT")
        out: List[Any] = [game]
        if hero is not None:
            out.append(hero)
        if init_body is not None or init_head:
            out.append(FnDecl(name="init", params=[], body=init_head + (init_body or []), line=line))
        if start_body is not None:
            out.append(FnDecl(name="start", params=[("load", "bool")], body=start_body, line=line))
        return out

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
                    setattr(c, {"when": "cond", "do": "do_body"}.get(kw, kw), self._parse_handler_body())
                elif self.match("OP", "->"):
                    c.next_label = self.eat("IDENT").val
                    self.eat_nl()
                else:
                    st = self.parse_stmt()
                    self.skip_nl()
                    if first and isinstance(st, SayStmt) and st.mode == "p":
                        c.reply = st.expr
                    else:
                        c.do_body.append(st)
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
                self.eat_nl()
                return LocalStmt(line=line, names=names, values=vals)
            if kw in ("if", "when"):
                return self._parse_if(kw)
            if kw == "match":
                return self._parse_match()
            if kw == "for":
                return self._parse_for()

        lhs = self.parse_postfix()
        if self.cur().kind == "OP" and self.cur().val in ("=", "+=", "-="):
            op = self.eat("OP").val
            vals = self.parse_expr_list()
            self.eat_nl()
            return AssignStmt(line=line, target=lhs, op=op, values=vals)

        if self.match("OP", ":"):
            m = self.eat("IDENT").val
            args = self._app_args()
            self.eat_nl()
            return CallStmt(line=line, call=Call(line=line, func=m, receiver=lhs, args=args))
        if isinstance(lhs, Sym):
            args = self._app_args()
            self.eat_nl()
            return CallStmt(line=line, call=Call(line=line, func=lhs.name, args=args))
        raise Error("expected statement", line, self.src)

    def _parse_if(self, style: str) -> IfStmt:
        line = self.eat("IDENT").line
        cond = self.parse_expr()
        self.match("IDENT", "then")
        branches = [(cond, self.parse_stmt_block(), line)]
        cont_kw = "when" if style == "when" else "elseif"
        else_kw = "default" if style == "when" else "else"
        while self.at("IDENT", cont_kw):
            el = self.eat("IDENT").line
            ec = self.parse_expr()
            self.match("IDENT", "then")
            branches.append((ec, self.parse_stmt_block(), el))
        else_body = self.parse_stmt_block() if self.match("IDENT", else_kw) else None
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
        left = self.parse_unary()
        while True:
            t = self.cur()
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
            args.append(self.parse_postfix())
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
        parts, s, i, n = [], t.val, 0, len(t.val)
        while i < n:
            j = s.find("{", i)
            if j == -1:
                parts.append(s[i:])
                break
            k = s.find("}", j + 1)
            if k == -1 or (j + 1 < n and s[j + 1] in "$#"):
                end = (k + 1) if k != -1 else n
                parts.append(s[i:end])
                i = end
                continue
            if j > i:
                parts.append(s[i:j])
            parts.append(Parser(tokenize(s[j + 1:k].strip(), self.src), self.src).parse_expr())
            i = k + 1
        if len(parts) == 1 and isinstance(parts[0], str):
            return Lit(line=t.line, kind="str", val=parts[0])
        return InterpStr(line=t.line, parts=parts)


def parse_source(src: str, src_name: str = "") -> Program:
    return Parser(tokenize(src, src_name), src_name, src).parse_program()
