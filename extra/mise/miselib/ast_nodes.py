"""AST nodes and Error for minimal MISE 2."""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from .types import Type


class Error(Exception):
    def __init__(self, msg: str, line: int = 0, src: str = ""):
        super().__init__(msg)
        self.msg, self.line, self.src = msg, line, src

    def format(self) -> str:
        loc = f"{self.src}:{self.line}: " if self.src and self.line else (f"line {self.line}: " if self.line else "")
        return f"mise: {loc}{self.msg}"


# --- Expressions ---

@dataclass
class Expr:
    line: int = 0
    typ: Optional[Type] = None     # filled by the checker

@dataclass
class Lit(Expr):
    kind: str = "nil"          # "num", "bool", "str", "nil", "raw" (backtick), "lua" (block), "table" ({...})
    val: Any = None

@dataclass
class InterpStr(Expr):
    parts: List[Any] = field(default_factory=list)  # str or Expr

@dataclass
class Sym(Expr):
    name: str = ""
    # how the name is emitted; filled by the checker:
    #   "var" | "obj" | "enum" | "event" | "global" | "global_ref" | "lua_global" | "fn0" (call) | "value"
    rk: str = ""

@dataclass
class FnRef(Expr):
    name: str = ""

@dataclass
class ListLit(Expr):
    items: List[Expr] = field(default_factory=list)

@dataclass
class FieldAccess(Expr):
    obj: Expr = field(default_factory=Expr)
    field: str = ""
    is_ref: bool = False

@dataclass
class IndexAccess(Expr):
    obj: Expr = field(default_factory=Expr)
    index: Expr = field(default_factory=Expr)

@dataclass
class UnaryOp(Expr):
    op: str = ""
    operand: Expr = field(default_factory=Expr)

@dataclass
class BinOp(Expr):
    op: str = ""
    left: Expr = field(default_factory=Expr)
    right: Expr = field(default_factory=Expr)

@dataclass
class Lambda(Expr):
    """`&(w) expr` / `&(w) <block>` — an anonymous function."""
    params: List[Tuple[str, Optional[Type]]] = field(default_factory=list)
    body: Any = None                       # Expr or List[Stmt]

@dataclass
class Bind(Expr):
    """`x := expr` / `a, b := expr` — a binding condition (`if`/`elseif`)."""
    names: List[str] = field(default_factory=list)
    value: Expr = field(default_factory=Expr)
    vtyp: Optional[Type] = None    # type of the value, filled by the checker

@dataclass
class InOp(Expr):
    """`x in a, b` — is x equal to any of the alternatives."""
    subject: Expr = field(default_factory=Expr)
    alts: List[Expr] = field(default_factory=list)

@dataclass
class Call(Expr):
    func: str = ""
    args: List[Expr] = field(default_factory=list)
    receiver: Optional[Expr] = None


# --- Statements ---

@dataclass
class Stmt:
    line: int = 0

@dataclass
class SayStmt(Stmt):
    expr: Expr = field(default_factory=Expr)
    mode: str = "p"            # "p", "pr", "pn"

@dataclass
class ReturnStmt(Stmt):
    kind: str = "return"       # "return", "stop", "pass", "break"
    values: List[Expr] = field(default_factory=list)

@dataclass
class LocalStmt(Stmt):
    names: List[Tuple[str, Optional[Type]]] = field(default_factory=list)
    values: List[Expr] = field(default_factory=list)

@dataclass
class AssignStmt(Stmt):
    target: Expr = field(default_factory=Expr)
    op: str = "="
    values: List[Expr] = field(default_factory=list)

@dataclass
class CallStmt(Stmt):
    call: Call = field(default_factory=Call)

@dataclass
class IfStmt(Stmt):
    branches: List[Tuple[Expr, List[Stmt], int]] = field(default_factory=list)
    else_body: Optional[List[Stmt]] = None

@dataclass
class MatchStmt(Stmt):
    subject: Expr = field(default_factory=Expr)
    arms: List[Tuple[List[Expr], Optional[Expr], List[Stmt], int]] = field(default_factory=list)

@dataclass
class ForNumStmt(Stmt):
    var: str = ""
    var_type: Optional[Type] = None
    start: Expr = field(default_factory=Expr)
    stop: Expr = field(default_factory=Expr)
    step: Optional[Expr] = None
    body: List[Stmt] = field(default_factory=list)

@dataclass
class ForInStmt(Stmt):
    vars: List[Tuple[str, Optional[Type]]] = field(default_factory=list)
    iter_expr: Expr = field(default_factory=Expr)
    is_of: bool = False
    body: List[Stmt] = field(default_factory=list)


# --- Declarations (Unified Entity Model) ---

@dataclass
class Handler:
    phase: str                 # "on", "before", "after", "post", "life"
    events: List[str]
    params: Optional[List[str]]
    body: Any                  # List[Stmt], Expr, FnRef, "pass", "stop"
    line: int = 0

@dataclass
class Emit:
    """How a declared field reaches Lua (`= method attr(join)` in core)."""
    method: str
    form: str = "each"         # "each" | "join" | "list" | "table" | "none"
    other: str = ""            # the method for `false` (`disable` -> `enable`)


@dataclass
class Prop:
    name: str
    value: Any = None          # Expr, List[Stmt], FnRef, None (type-only field in class)
    typ: Optional[Type] = None  # declared type in `class` (`n_to: room?`)
    params: Optional[List[str]] = None
    type_params: Optional[List[str]] = None   # names of `fn(s: obj, w: list)`
    emit: Optional[Emit] = None   # a method call instead of a plain field
    is_ref: bool = False          # the declared type says "reference" (filled by the checker)
    line: int = 0

@dataclass
class EntityDecl:
    """Unified node for `class`, `obj`, `room`, `door`, `story`, `ending`, `impl`, and class instances."""
    kind: str                  # "class", "impl", or class name ("obj", "room", "Door", ...)
    name: Optional[str] = None
    parent: Optional[str] = None
    ctor: Optional[str] = None       # engine constructor, e.g. `class story(room) = cutscene`
    words: List[str] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)   # classes/mixins or attributes
    locations: List[str] = field(default_factory=list)
    props: List[Prop] = field(default_factory=list)
    handlers: List[Handler] = field(default_factory=list)
    children: List["EntityDecl"] = field(default_factory=list)
    line: int = 0
    src: str = ""

@dataclass
class FnDecl:
    name: str
    params: List[Tuple[str, Type]]
    variadic: Optional[Type] = None
    ret_types: List[Type] = field(default_factory=list)
    body: Any = None           # List[Stmt] or str (template / raw lua)
    is_extern: bool = False
    is_value: bool = False          # `extern value` — an expression, not a callable
    line: int = 0

@dataclass
class EventsDecl:
    """`event A, B: obj, str` — names and the action arguments each one takes."""
    sigs: List[Tuple[List[str], List[Type]]] = field(default_factory=list)
    extend: bool = False
    line: int = 0


@dataclass
class EntryDecl:
    """`entry init()` — a global the engine calls itself."""
    name: str
    params: List[Tuple[str, Type]] = field(default_factory=list)
    line: int = 0


@dataclass
class GlobalDecl:
    """`extern global mp: any = "mp"` — a Lua global reachable from expressions."""
    name: str
    typ: Type
    template: str
    line: int = 0


@dataclass
class TypeDecl:
    name: str
    values: List[str] = field(default_factory=list)
    negate: bool = False
    extend: bool = False
    line: int = 0

@dataclass
class VerbDecl:
    name: str
    mode: str = "verb"         # "verb", "extend", "remove"
    tag: Optional[str] = None
    target: Optional[str] = None
    words: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    prio: Optional[int] = None
    hint: Any = None
    line: int = 0

@dataclass
class TalkChoice:
    sticky: bool = False
    cond: Any = None
    ask: Any = None
    reply: Any = None
    do: Any = field(default_factory=list)
    onempty: Any = None
    children: List["TalkChoice"] = field(default_factory=list)
    next_label: Optional[str] = None
    flags: List[str] = field(default_factory=list)   # "always", "hidden", "only"
    line: int = 0

@dataclass
class TalkDecl:
    name: str
    intro: Any = None
    props: List[Prop] = field(default_factory=list)
    choices: List[TalkChoice] = field(default_factory=list)
    labels: List[Tuple[str, Any, List[TalkChoice]]] = field(default_factory=list)
    line: int = 0

@dataclass
class VarDecl:
    kind: str                  # "global" or "const"
    items: List[Tuple[str, Expr, int]] = field(default_factory=list)

@dataclass
class LuaDecl:
    code: str
    line: int = 0

@dataclass
class Program:
    meta: List[Tuple[str, str]] = field(default_factory=list)
    lang: str = "ru"
    fmt: List[str] = field(default_factory=list)
    includes: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    items: List[Any] = field(default_factory=list)
