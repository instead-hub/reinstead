"""Flow-sensitive type narrowing and control-flow return analysis for MISE 2."""
from typing import Dict, List, Optional

from .ast_nodes import (
    Bind, BinOp, DictLit, Expr, IfStmt, InOp, InterpStr, ListLit, Lit,
    MatchStmt, ReturnStmt, Stmt, Sym, UnaryOp,
)
from .symbols import CURRENT_EVENT, EVENT, Context, lit_type
from .types import ANY, NIL, Type, union, without_nil


def returns_all(stmts: List[Stmt]) -> bool:
    """Does every path through this body end with a value?"""
    for s in stmts:
        if isinstance(s, ReturnStmt):
            return s.kind == "pass" or (s.kind == "return" and bool(s.values))
        if isinstance(s, IfStmt) and s.else_body is not None \
                and returns_all(s.else_body) \
                and all(returns_all(b) for _c, b, _l in s.branches):
            return True
        if isinstance(s, MatchStmt) \
                and any(len(p) == 1 and isinstance(p[0], Sym) and p[0].name == "_" and not g
                        for p, g, _b, _l in s.arms) \
                and all(returns_all(b) for _p, _g, b, _l in s.arms):
            return True
    return False


def _nonnil(ctx: Context, e: Expr) -> bool:
    if isinstance(e, Lit):
        return e.kind != "nil"
    if isinstance(e, Sym):
        return lit_type(ctx, e) != ANY
    return isinstance(e, (ListLit, DictLit, InterpStr))


def _narrow_event_args(ctx: Context, ev_names: List[str], res: Dict[str, Type],
                       arg_names: Optional[Dict[int, str]]):
    if not ev_names or not arg_names:
        return
    alts = [ctx.event_args.get(n) or [] for n in ev_names]
    for i in range(max((len(a) for a in alts), default=0)):
        ts = [a[i] for a in alts if i < len(a)]
        name = arg_names.get(i)
        if ts and name and name in res:
            res[name] = union(*set(ts))


def _is_event_sym(e: Expr, env: Dict[str, Type]) -> bool:
    return isinstance(e, Sym) and (
        e.name in CURRENT_EVENT or without_nil(env.get(e.name, ANY)) == EVENT
    )


def _narrow_eq(ctx: Context, cond: BinOp, res: Dict[str, Type], truthy: bool,
               arg_names: Optional[Dict[int, str]]):
    for a, b in ((cond.left, cond.right), (cond.right, cond.left)):
        if not (isinstance(a, Sym) and a.name in res):
            continue
        if isinstance(b, Lit) and b.kind == "nil":
            res[a.name] = without_nil(res[a.name]) if ((cond.op == "!=") == truthy) else NIL
            return
        if _nonnil(ctx, b):
            if (cond.op == "==") == truthy:
                res[a.name] = without_nil(res[a.name])
            break
    if cond.op == "==" and truthy and _is_event_sym(cond.left, res) and isinstance(cond.right, Sym):
        _narrow_event_args(ctx, [cond.right.name], res, arg_names)


def narrow(ctx: Context, cond: Expr, env: Dict[str, Type], truthy: bool,
           arg_names: Optional[Dict[int, str]] = None) -> Dict[str, Type]:
    res = dict(env)
    match cond:
        case Bind() if truthy:
            vt = without_nil(cond.vtyp) if (cond.vtyp and cond.vtyp != ANY) else ANY
            for n in cond.names:
                res[n] = vt
        case Sym() if cond.name in res:
            res[cond.name] = without_nil(res[cond.name]) if truthy else NIL
        case UnaryOp(op="not"):
            return narrow(ctx, cond.operand, env, not truthy, arg_names)
        case InOp() if truthy and _is_event_sym(cond.subject, res):
            _narrow_event_args(ctx, [a.name for a in cond.alts if isinstance(a, Sym)], res, arg_names)
        case BinOp(op="and") if truthy:
            return narrow(ctx, cond.right, narrow(ctx, cond.left, env, True, arg_names),
                          True, arg_names)
        case BinOp(op="or") if not truthy:
            return narrow(ctx, cond.right, narrow(ctx, cond.left, env, False, arg_names),
                          False, arg_names)
        case BinOp() if cond.op in ("==", "!="):
            _narrow_eq(ctx, cond, res, truthy, arg_names)
    return res
