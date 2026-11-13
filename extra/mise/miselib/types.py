"""The type algebra of MISE 2.

A type used to be a string ("str|num?", "tbl[ref]|nil", "fn(obj,str)->bool")
that every consumer re-parsed; this module holds one representation instead:

    Name("str")                 a primitive, a class, an enum
    Tbl(inner)                  tbl / tbl[T]
    Ref(name)                   ref / ref[C]
    Fn(params, rets)            fn(T1,T2) -> R1,R2
    Union(parts, nil=True)      `A|B?`

`str()` prints the source spelling (`ref[talk]|fn(obj)->ref`, `obj?`), which is
what diagnostics and `.err` tests pin.
"""
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple


class Type:
    """Common base: a value that can appear in a type."""

    def __str__(self) -> str:                       # pragma: no cover - overridden
        raise NotImplementedError


@dataclass(frozen=True)
class Name(Type):
    """A primitive (`str`, `any`), a class (`obj`, `Path`) or an enum (`attr`)."""

    name: str = "any"

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Tbl(Type):
    """`tbl` (inner is None) or `tbl[T]`."""

    inner: Optional[Type] = None

    def __str__(self) -> str:
        return "tbl" if self.inner is None else f"tbl[{self.inner}]"


@dataclass(frozen=True)
class Ref(Type):
    """`ref` (inner is None: any object) or `ref[C]`."""

    inner: Optional[Type] = None

    def __str__(self) -> str:
        return "ref" if self.inner is None else f"ref[{self.inner}]"


@dataclass(frozen=True)
class Fn(Type):
    """`fn(T1,T2) -> R1,R2` — `rets` may be empty."""

    params: Tuple[Type, ...] = ()
    rets: Tuple[Type, ...] = ()

    def __str__(self) -> str:
        head = "fn(" + ",".join(str(p) for p in self.params) + ")"
        return head + ("->" + ",".join(str(r) for r in self.rets) if self.rets else "")


@dataclass(frozen=True)
class Union(Type):
    """`A|B`, optionally `?` (nil is a member)."""

    parts: Tuple[Type, ...] = ()
    nil: bool = False

    def __str__(self) -> str:
        body = "|".join(str(p) for p in self.parts) if self.parts else "nil"
        if self.nil and self.parts:
            return body + "?"
        return body


NIL = Name("nil")
ANY = Name("any")
EVENT = Name("event")


def union(*types: Iterable[Type]) -> Type:
    """A canonical union: flattened, without duplicates and without nil."""
    parts, nil = [], False
    for t in types:
        for one in (t.parts if isinstance(t, Union) else (t,)):
            if isinstance(one, Name) and one.name == "nil":
                nil = True
            elif one not in parts:
                parts.append(one)
        if isinstance(t, Union) and t.nil:
            nil = True
    if not parts:
        return NIL
    if len(parts) == 1 and not nil:
        return parts[0]
    return Union(tuple(parts), nil)


def opt(t: Type) -> Type:
    """`T?` — the value may be nil."""
    if isinstance(t, Union):
        return t if t.nil else Union(t.parts, True)
    if isinstance(t, Name) and t.name == "nil":
        return t
    return Union((t,), True)


def parts(t: Type) -> Tuple[Type, ...]:
    """The union members, nil included (as `Name("nil")`)."""
    if isinstance(t, Union):
        return t.parts + ((NIL,) if t.nil else ())
    return (NIL,) if isinstance(t, Name) and t.name == "nil" else (t,)


def is_optional(t: Type) -> bool:
    return (isinstance(t, Union) and t.nil) or (isinstance(t, Name) and t.name == "nil")


def without_nil(t: Type) -> Type:
    """`T?` -> `T`; anything without nil is returned as is."""
    if isinstance(t, Name):
        return ANY if t.name == "nil" else t
    if not isinstance(t, Union):
        return t
    if len(t.parts) == 1:
        return t.parts[0]
    return Union(t.parts, False) if t.parts else NIL


def single(t: Type) -> Optional[Type]:
    """The only member of a union that is not nil, or None when ambiguous."""
    body = without_nil(t)
    return body if not isinstance(body, Union) else None


def is_tbl(t: Type) -> bool:
    """`tbl` / `tbl[T]` — but not a class instance (that is an object, not a table)."""
    return isinstance(single(t), Tbl)


def tbl_inner(t: Type) -> Optional[Type]:
    """The element type of `tbl[T]` (None for a bare `tbl` or a non-table)."""
    one = single(t)
    return one.inner if isinstance(one, Tbl) else None


def fn_returns(t: Optional[Type]) -> Tuple[Type, ...]:
    """Return types of the `fn(...) -> T` alternatives of a type."""
    return tuple(r for one in parts(t) if isinstance(one, Fn) for r in one.rets) \
        if t is not None else ()


def fn_of(t: Type) -> Optional[Fn]:
    """The first `fn(...)` member of a type (`str | fn(obj) -> str` -> the fn)."""
    for one in parts(t):
        if isinstance(one, Fn):
            return one
    return None
