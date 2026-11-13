"""Type checker for MISE 2 statements, expressions, entities and dialogues."""
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from . import types
from .ast_nodes import (
    AssignStmt, Bind, BinOp, Call, DictLit, Emit, EntityDecl, Error, Expr,
    ExternDecl, FieldAccess, FnDecl, FnRef, ForInStmt, ForNumStmt, Handler,
    IfStmt, InOp, IndexAccess, InterpStr, Lambda, ListLit, Lit, LocalStmt,
    MatchStmt, Program, Prop, ReturnStmt, SayStmt, Stmt, Sym, TalkChoice,
    TalkDecl, UnaryOp, VarDecl, VerbDecl, WhileStmt,
)
from .narrow import narrow, returns_all
from .symbols import (
    BOOL, CONCAT, EVENT, HANDLER_VALUE, KINDS, NUM, PRINTABLE, READONLY_FIELDS,
    STR, Context, TypeCheckError, attach_item_src, atom_fits, build_context,
    check_signature, close_hint, decl_of, entity_kind, enum_hint, enum_value,
    expect, index_result, inherits, is_empty_collection, is_object_type,
    is_scalar_ref, is_subtype, need_value, no_duplicates, objectish,
    resolve_global_sym, room_root, root_class,
)
from .types import ANY, NIL, Fn, Name, Ref, Tbl, Type, opt, parts, union, without_nil

HANDLER_PARAMS = ("s", "w", "wh", "w2", "w3")
CHOICE_FIELDS = ("ask", "reply", "act", "onempty")


def _kind_name(expr: Expr) -> str:
    match expr:
        case Sym():
            return expr.name
        case Lit(kind="raw"):
            return "`lua`"
        case Lit(kind="table"):
            return "{…}"
        case Lit():
            return str(expr.val)
        case FieldAccess():
            return f"{_kind_name(expr.obj)}.{expr.field}"
        case IndexAccess():
            return f"{_kind_name(expr.obj)}[…]"
        case Call():
            recv = f"{_kind_name(expr.receiver)}:" if expr.receiver is not None else ""
            return f"{recv}{expr.func or 'call'}()"
    return "expression"


# --- Fields & Stores --------------------------------------------------------

def _fields_of(ctx: Context, holder: str) -> Dict[str, Type]:
    allowed = dict(ctx.fields.get(holder, {}))
    if holder not in ctx.classes:
        return allowed
    for name, kind in list(ctx.objects.items()) + list(ctx.classes.items()):
        if not inherits(ctx, kind if kind else name, holder):
            continue
        for k, v in ctx.fields.get(name, {}).items():
            if k not in allowed or is_empty_collection(allowed[k]):
                allowed[k] = v
            elif allowed[k] != v and not is_empty_collection(v):
                allowed[k] = ANY
    return allowed


def _owner_of(ctx: Context, target: FieldAccess, base_t: Type,
              owner: Optional[str]) -> Optional[str]:
    if isinstance(target.obj, Sym):
        n = target.obj.name
        if n == "s" and owner:
            return owner
        if n in ctx.objects:
            return n if (n in ctx.fields or ctx.objects[n] == "class") else ctx.objects[n]
        if n in ctx.classes:
            return n
    one = types.single(base_t)
    if isinstance(one, Name) and (one.name in ctx.classes or one.name in ctx.objects):
        return one.name
    if isinstance(one, Ref) and isinstance(one.inner, Name) and one.inner.name in ctx.classes:
        return one.inner.name
    return None


def _resolve_index(ctx: Context, e: IndexAccess, env: Dict[str, Type],
                   owner: Optional[str], line: int) -> Tuple[Type, Type]:
    ot = _check_expr(ctx, e.obj, env, owner)
    base = index_result(ctx, ot)
    if base is None:
        raise TypeCheckError(f"{_kind_name(e.obj)}: {ot} is not indexable "
                             f"(only a `tbl`, a list or `any`)", line)
    _check_expr(ctx, e.index, env, owner, None)
    return ot, base


def _resolve_field(ctx: Context, e: FieldAccess, env: Dict[str, Type],
                   owner: Optional[str], writing: bool = False, line: int = 0) -> Type:
    base_t = _check_expr(ctx, e.obj, env, owner)
    need_value(base_t, _kind_name(e.obj), line)
    if not writing and not objectish(ctx, base_t):
        raise TypeCheckError(f"{_kind_name(e.obj)}: {base_t} has no fields (`.{e.field}`)", line)
    name = e.field
    if writing and name in READONLY_FIELDS:
        raise Error(f"{name}: an engine field cannot be assigned", line)
    if name.startswith("__"):
        return ANY
    holder = _owner_of(ctx, e, base_t, owner)
    decl = decl_of(ctx, holder, name) if holder else None
    if decl is not None and decl.emit is not None:
        if writing:
            raise Error(f"{holder}.{name}: an emitted field is set by its declaration "
                        f"(`= method {decl.emit.method}(…)`), not by code", line)
        raise TypeCheckError(
            f"{_kind_name(e)}: {name!r} is write-only "
            f"(declared as `= method {decl.emit.method}(…)`); read it through the method",
            line)
    if holder is not None:
        ft = (ctx.fields.get(holder, {}).get(name) if not writing else None) \
            or _fields_of(ctx, holder).get(name)
        if ft is None:
            raise Error(f"{holder}.{name}: no such field "
                        f"(nothing declares it for {holder}; use __{name} for a dynamic value)",
                        line)
        return ft
    if name not in ctx.field_names:
        raise Error(f"unknown field {name!r} (use __{name} for dynamic values)", line)
    return ANY


def _check_store(ctx: Context, target: Expr, vt: Type, env: Dict[str, Type],
                 owner: Optional[str], line: int = 0, op: str = "="):
    if isinstance(target, IndexAccess):
        ot, inner = _resolve_index(ctx, target, env, owner, line)
        need_value(ot, _kind_name(target.obj), line)
        expect(ctx, _kind_name(target), vt, inner, line)
        return
    if not isinstance(target, FieldAccess):
        _check_expr(ctx, target, env, owner)
        return
    ft = _resolve_field(ctx, target, env, owner, writing=True, line=line)
    if op in ("+=", "-=") and ft not in (ANY, NUM):
        raise Error(f"{target.field}: '{op}' needs a number field (it is {ft})", line)
    elif op not in ("+=", "-=") and ft != ANY:
        expect(ctx, target.field, vt, ft, line)


# --- Expressions ------------------------------------------------------------

def _check_expr(ctx: Context, e: Expr, env: Dict[str, Type], owner: Optional[str] = None,
                expected: Optional[Type] = None) -> Type:
    e.typ = t = _infer(ctx, e, env, owner, expected)
    if expected:
        expect(ctx, _kind_name(e), t, expected, e.line)
    return t


def _check_fnref(ctx: Context, ref: FnRef, expected: Optional[Type], where: str) -> Type:
    if ref.name in ctx.externs:
        raise Error(f"&{ref.name}: an extern is a macro, it has no function value "
                    f"(call it directly, or write a `fn` wrapper)", ref.line)
    fn = ctx.fns.get(ref.name)
    if fn is None:
        raise Error(f"&{ref.name}: unknown function (declare it with `fn`)", ref.line)
    got = Fn(tuple(pt for _pn, pt in fn.params), tuple(fn.ret_types))
    if expected is not None:
        alts = [a for a in parts(expected) if isinstance(a, Fn)]
        if alts and not any(atom_fits(ctx, got, a) for a in alts):
            raise TypeCheckError(f"{where}: {ref.name} is {got}, expected "
                                 f"{' | '.join(str(a) for a in alts)}", ref.line)
    return got


def _infer_lambda(ctx: Context, e: Lambda, env: Dict[str, Type],
                  owner: Optional[str], expected: Optional[Type]) -> Type:
    one = types.fn_of(expected) if expected is not None else None
    eparams: Tuple[Type, ...] = one.params if one else ()
    erets: Tuple[Type, ...] = one.rets if one else ()
    if eparams and len(e.params) > len(eparams):
        raise TypeCheckError(f"&(…): the callback passes {len(eparams)} argument(s), "
                             f"the lambda takes {len(e.params)}", e.line)
    env2 = dict(env)
    env2.pop("...", None)
    ptypes: List[Type] = []
    for i, (pn, pt) in enumerate(e.params):
        ept = eparams[i] if i < len(eparams) else None
        if pt is None:
            if not ept:
                raise TypeCheckError(
                    f"&({pn}): annotate the parameter type (`&({pn}: obj)`)", e.line)
            pt = ept
        elif ept and pt != ANY and not is_subtype(ctx, ept, pt):
            raise TypeCheckError(f"&({pn}): the callback passes {ept}, "
                                 f"the lambda declares {pt}", e.line)
        if pn != "_":
            env2[pn] = pt
        ptypes.append(pt)
    if isinstance(e.body, list):
        rets: List[Type] = []
        _check_stmts(ctx, e.body, env2, owner, rets)
        for t in rets:
            if erets and not any(is_subtype(ctx, t, w) for w in erets):
                raise TypeCheckError(f"&(…): returns {t}, the callback declares "
                                     f"{union(*erets)}", e.line)
        if erets and not types.is_optional(union(*erets)) and not returns_all(e.body):
            raise TypeCheckError(
                f"&(…): the callback returns {union(*erets)}, but some path leaves the body "
                f"without `return` (write an expression body or add `return`)", e.line)
    else:
        _check_expr(ctx, e.body, env2, owner, erets[0] if erets else None)
    return Fn(tuple(ptypes), tuple(erets))


def _infer_sym(ctx: Context, e: Sym, env: Dict[str, Type],
               expected: Optional[Type]) -> Type:
    n = e.name
    if n == "...":
        if "..." not in env:
            raise Error("cannot use '...' outside a variadic function", e.line)
        e.rk = "var"
        return env["..."]
    if n in env:
        e.rk = "var"
        return env[n]
    if expected:
        exps = parts(expected)
        if EVENT in exps and n in ctx.event_names:
            e.rk = "event"
            return EVENT
        if n in ctx.enum_owner:
            for ea in exps:
                if enum_value(ctx, n, str(ea)):
                    e.rk = "enum"
                    return Name(str(ea))
    found = resolve_global_sym(ctx, n, allow_class_str=True)
    if found is not None:
        e.rk, typ = found
        return typ
    decl = ctx.callable_decl(n)
    if decl is not None:
        required = sum(1 for _pn, pt in decl.params if not types.is_optional(pt))
        if required:
            raise Error(f"{n}: needs {required} argument(s) — call it or take `&{n}`", e.line)
        e.rk = "value" if (isinstance(decl, ExternDecl) and decl.kind in ("value", "lvalue")) else "fn0"
        return decl.ret_types[0] if decl.ret_types else ANY
    if n.startswith("#"):
        raise Error(f"unknown tag {n!r}{enum_hint(ctx, n)}", e.line)
    raise Error(f"unknown name {n!r}{enum_hint(ctx, n)}", e.line)


def _infer_binop(ctx: Context, e: BinOp, env: Dict[str, Type], owner: Optional[str]) -> Type:
    if e.op in ("<", "<=", ">", ">=", "+", "-", "*", "/", "%"):
        for side in (e.left, e.right):
            _check_expr(ctx, side, env, owner, NUM)
        return BOOL if e.op in ("<", "<=", ">", ">=") else NUM
    if e.op == "..":
        for side in (e.left, e.right):
            t = _check_expr(ctx, side, env, owner)
            if not is_subtype(ctx, t, CONCAT) and t != ANY:
                raise TypeCheckError(f"concatenation: expected str, got {t}", side.line)
        return STR
    lt = _check_expr(ctx, e.left, env, owner)
    if e.op in ("==", "!="):
        _infer(ctx, e.right, env, owner, lt)
        return BOOL
    rt = _check_expr(ctx, e.right, env, owner)
    return union(lt, rt) if e.op == "and" else (union(without_nil(lt), rt) if e.op == "or" else rt)


def _check_call(ctx: Context, c: Call, env: Dict[str, Type], owner: Optional[str] = None) -> Type:
    is_method = c.receiver is not None
    rt = _check_expr(ctx, c.receiver, env, owner) if is_method else None
    if is_method:
        need_value(rt, _kind_name(c.receiver), c.line)
    ftype = env.get(c.func)
    shadowed = not is_method and ftype is not None and types.fn_of(ftype) is not None
    decl = None if shadowed else ctx.callable_decl(c.func)
    if decl is not None:
        all_args = ([c.receiver] + c.args) if is_method else list(c.args)
        label = f"{_kind_name(c.receiver)}:{c.func}" if is_method else c.func
        params = decl.params
        required = sum(1 for _pn, pt in params if not types.is_optional(pt))
        given, variadic = len(all_args), bool(decl.variadic)
        if given < required or (not variadic and given > len(params)):
            want = f"{required}+" if variadic else (
                str(required) if required == len(params) else f"{required}..{len(params)}")
            raise Error(f"{label} expects {want} argument(s), got {given}", c.line)
        for i, a in enumerate(all_args):
            exp = params[i][1] if i < len(params) else (decl.variadic if variadic else None)
            if is_method and i == 0:
                expect(ctx, f"receiver of {label}", rt, exp, a.line)
            else:
                _check_expr(ctx, a, env, owner, exp)
        return decl.ret_types[0] if decl.ret_types else ANY

    body = without_nil(ftype) if ftype is not None else None
    one = body if isinstance(body, Fn) else None
    if not ((not is_method and one is not None) or (is_method and rt == ANY)):
        if is_method:
            raise Error(f"unknown method {c.func!r} "
                        f"(a method call needs a function or an extern)", c.line)
        if ftype is not None:
            raise TypeCheckError(f"{c.func}: is {ftype}, not a function", c.line)
        raise Error(f"unknown function {c.func!r}", c.line)
    if one is not None:
        required = sum(1 for t in one.params if not types.is_optional(t))
        if len(c.args) < required:
            raise TypeCheckError(f"{c.func}: expects {required} argument(s), "
                                 f"got {len(c.args)}", c.line)
    for i, a in enumerate(c.args):
        _check_expr(ctx, a, env, owner,
                    one.params[i] if (one is not None and i < len(one.params)) else None)
    return one.rets[0] if (one is not None and one.rets) else ANY


def _expected_tbl_inner(expected: Optional[Type]) -> Optional[Type]:
    return next((types.tbl_inner(alt) for alt in (parts(expected) if expected else [])
                 if types.tbl_inner(alt) is not None), None)


def _infer_dict(ctx: Context, e: DictLit, env: Dict[str, Type],
                owner: Optional[str], expected: Optional[Type]) -> Type:
    in_exp = _expected_tbl_inner(expected)
    vts = []
    for k, v in e.pairs:
        if isinstance(k, Expr):
            _check_expr(ctx, k, env, owner)
        vts.append(_check_expr(ctx, v, env, owner, in_exp))
    return Tbl(union(*vts) if vts else None)


def _infer(ctx: Context, e: Expr, env: Dict[str, Type], owner: Optional[str] = None,
           expected: Optional[Type] = None) -> Type:
    match e:
        case Lit():
            if e.kind == "num" and expected is not None:
                for alt in parts(expected):
                    if isinstance(alt, Name) and alt.name in ctx.enums \
                            and str(e.val) in ctx.enums[alt.name][0]:
                        return alt
            if e.kind == "raw" and expected is not None and expected != ANY:
                return expected
            return KINDS.get(e.kind, ANY)
        case InterpStr():
            for p in e.parts:
                if isinstance(p, Expr):
                    t = _check_expr(ctx, p, env, owner)
                    if not is_subtype(ctx, t, PRINTABLE) and t != ANY:
                        raise TypeCheckError(f"interpolation: expected str, got {t}", p.line)
            return STR
        case Lambda():
            return _infer_lambda(ctx, e, env, owner, expected)
        case Bind():
            vt = _value_types(ctx, [e.value], env, owner, len(e.names))
            e.vtyp = vt[0] if vt else ANY
            for n in e.names:
                if n != "_" and n in env:
                    raise Error(f"{n}: already defined (choose another name for `:=`)", e.line)
            return BOOL
        case InOp():
            st = _check_expr(ctx, e.subject, env, owner)
            for a in e.alts:
                _check_expr(ctx, a, env, owner, st)
            return BOOL
        case FnRef():
            return _check_fnref(ctx, e, expected, _kind_name(e))
        case ListLit():
            in_exp = _expected_tbl_inner(expected)
            its = [_check_expr(ctx, it, env, owner, in_exp) for it in e.items]
            return Tbl(union(*its) if its else Name(""))
        case DictLit():
            return _infer_dict(ctx, e, env, owner, expected)
        case Sym():
            return _infer_sym(ctx, e, env, expected)
        case FieldAccess():
            ft = _resolve_field(ctx, e, env, owner, writing=False, line=e.line)
            e.is_ref = is_scalar_ref(ctx, ft)
            return ft
        case IndexAccess():
            _ot, base = _resolve_index(ctx, e, env, owner, e.line)
            return base if base in (ANY, NIL) or types.is_optional(base) else opt(base)
        case UnaryOp():
            if e.op == "-" and isinstance(e.operand, Lit) and e.operand.kind == "str":
                return STR
            _check_expr(ctx, e.operand, env, owner, None if e.op == "not" else NUM)
            return BOOL if e.op == "not" else NUM
        case BinOp():
            return _infer_binop(ctx, e, env, owner)
        case Call():
            return _check_call(ctx, e, env, owner)
    return ANY


def _value_types(ctx: Context, values: List[Expr], env: Dict[str, Type],
                 owner: Optional[str], count: int = 1,
                 hints: Optional[List[Optional[Type]]] = None) -> List[Type]:
    res: List[Type] = []
    for i, v in enumerate(values):
        hint = hints[i] if (hints and i < len(hints)) else None
        if i == len(values) - 1 and isinstance(v, Sym) and v.name == "...":
            t = _check_expr(ctx, v, env, owner)
            el = opt(t) if t != ANY else ANY
            res.extend([el] * max(1, count - len(res)))
            continue
        v.typ = t = _infer(ctx, v, env, owner, hint)
        if i == len(values) - 1 and isinstance(v, Call) and v.receiver is None and v.func:
            decl = ctx.callable_decl(v.func)
            if decl and len(decl.ret_types) > 1:
                res.extend(decl.ret_types)
                continue
        res.append(t)
    return res


def _check_cond(ctx: Context, cond: Expr, env: Dict[str, Type], owner: Optional[str]):
    if isinstance(cond, UnaryOp) and cond.op == "not":
        return _check_cond(ctx, cond.operand, env, owner)
    if isinstance(cond, BinOp) and cond.op in ("and", "or"):
        _check_cond(ctx, cond.left, env, owner)
        return _check_cond(ctx, cond.right, narrow(ctx, cond.left, env, cond.op == "and"), owner)
    _check_expr(ctx, cond, env, owner)


# --- Statements -------------------------------------------------------------

def _check_assign_stmt(ctx: Context, s: AssignStmt, env: Dict[str, Type],
                       decl_env: Dict[str, Type], owner: Optional[str]):
    vt = _value_types(ctx, s.values, env, owner)
    if s.op in ("+=", "-="):
        for t in vt:
            expect(ctx, f"'{s.op}'", t, NUM, s.line)
    if not isinstance(s.target, Sym):
        _check_store(ctx, s.target, vt[0] if vt else ANY, env, owner, s.line, s.op)
        return
    name = s.target.name
    if name == "...":
        raise Error("cannot assign to '...'", s.line)
    local = name in env
    ext = ctx.externs.get(name)
    if local:
        s.target.rk = "var"
        cur: Optional[Type] = decl_env.get(name, env[name])
    elif name in ctx.consts:
        raise Error(f"{name}: a constant cannot be assigned", s.line)
    elif name in ctx.globals:
        s.target.rk = "var"
        cur = ctx.globals[name]
    elif ext is not None and ext.kind == "lvalue":
        s.target.rk = "lvalue"
        cur = ext.ret_types[0]
    elif name.startswith("__"):
        s.target.rk = "var"
        cur = None
    else:
        raise Error(f"unknown name {name!r} (declare it with `local` or `global`)", s.line)
    if cur is not None and cur != ANY and s.op == "=" and vt:
        expect(ctx, f"assignment to {name}", vt[0], cur, s.line)
    if cur is not None and cur != ANY and s.op in ("+=", "-="):
        expect(ctx, f"{name} ({s.op})", env[name] if local else cur, NUM, s.line)
    if local and vt and s.op == "=":
        if cur in (None, ANY):
            decl_env[name] = vt[0]
        env[name] = vt[0]


def _check_return_stmt(ctx: Context, s: ReturnStmt, env: Dict[str, Type], owner: Optional[str],
                       rets: Optional[List[Type]], fn_decl: Optional[FnDecl]):
    exp_rets = fn_decl.ret_types if (fn_decl is not None and s.kind == "return") else None
    vts = _value_types(ctx, s.values, env, owner, len(exp_rets) if exp_rets else 1, exp_rets)
    if fn_decl is not None and s.kind == "return" and s.values:
        expected = fn_decl.ret_types
        explicit, expanded = len(s.values), len(vts)
        bad = (expanded != len(expected)) if explicit == expanded else (expanded < len(expected))
        if bad:
            raise Error(f"fn {fn_decl.name}: returns {expanded} value(s), "
                        f"{len(expected)} declared", s.line)
        for i, exp in enumerate(expected[:len(vts)]):
            expect(ctx, f"return value {i + 1} of {fn_decl.name}", vts[i], exp, s.line)
    if rets is not None:
        rets.extend(t for t in vts if t != NIL)


def _check_local_stmt(ctx: Context, s: LocalStmt, env: Dict[str, Type],
                      decl_env: Dict[str, Type], owner: Optional[str]):
    no_duplicates((vn for vn, _t in s.names if vn != "_"), "local", s.line)
    vts = _value_types(ctx, s.values, env, owner, len(s.names), [dt for _vn, dt in s.names])
    for i, (vn, dt) in enumerate(s.names):
        got = vts[i] if i < len(vts) else None
        if dt is not None and got is not None:
            expect(ctx, f"local {vn}", got, dt, s.line)
        if vn != "_":
            decl_env[vn] = dt if dt is not None else (got if got is not None else ANY)
            env[vn] = (got if got is not None else ANY) if dt is None \
                else (opt(dt) if got is None else dt)


def _narrow_branch(ctx: Context, cond: Expr, env: Dict[str, Type],
                   decl_env: Dict[str, Type], arg_names: Optional[Dict[int, str]]
                   ) -> Tuple[Dict[str, Type], Dict[str, Type]]:
    benv = narrow(ctx, cond, env, True, arg_names)
    bdecl = dict(decl_env)
    if isinstance(cond, Bind):
        for n in cond.names:
            if n != "_":
                bdecl[n] = benv[n]
    return benv, bdecl


def _check_if_stmt(ctx: Context, s: IfStmt, env: Dict[str, Type], decl_env: Dict[str, Type],
                   owner: Optional[str], rets: Optional[List[Type]],
                   arg_names: Optional[Dict[int, str]], fn_decl: Optional[FnDecl], in_loop: bool):
    cenv = dict(env)
    for cond, body, _l in s.branches:
        _check_cond(ctx, cond, cenv, owner)
        benv, bdecl = _narrow_branch(ctx, cond, cenv, decl_env, arg_names)
        _check_stmts(ctx, body, benv, owner, rets, arg_names, fn_decl, in_loop, bdecl)
        cenv = narrow(ctx, cond, cenv, False, arg_names)
    if s.else_body is not None:
        _check_stmts(ctx, s.else_body, cenv, owner, rets, arg_names, fn_decl, in_loop, dict(decl_env))


def _check_while_stmt(ctx: Context, s: WhileStmt, env: Dict[str, Type], decl_env: Dict[str, Type],
                      owner: Optional[str], rets: Optional[List[Type]],
                      arg_names: Optional[Dict[int, str]], fn_decl: Optional[FnDecl]):
    wenv = dict(env)
    _check_cond(ctx, s.cond, wenv, owner)
    benv, bdecl = _narrow_branch(ctx, s.cond, wenv, decl_env, arg_names)
    _check_stmts(ctx, s.body, benv, owner, rets, arg_names, fn_decl, True, bdecl)


def _check_match_stmt(ctx: Context, s: MatchStmt, env: Dict[str, Type], decl_env: Dict[str, Type],
                      owner: Optional[str], rets: Optional[List[Type]],
                      arg_names: Optional[Dict[int, str]], fn_decl: Optional[FnDecl], in_loop: bool):
    st = _check_expr(ctx, s.subject, env, owner)
    for idx, (pats, guard, body, arm_line) in enumerate(s.arms):
        has_wild = any(isinstance(p, Sym) and p.name == "_" for p in pats)
        if has_wild and len(pats) > 1:
            raise Error("match: '_' cannot be combined with other patterns", arm_line)
        if has_wild and not guard and idx < len(s.arms) - 1:
            raise Error("match: '_' must be the last arm", arm_line)
        aenv = dict(env)
        for p in pats:
            if not (isinstance(p, Sym) and p.name == "_"):
                _check_expr(ctx, p, env, owner, st)
                aenv = narrow(ctx, BinOp(line=p.line, op="==", left=s.subject, right=p),
                              aenv, True, arg_names)
        if guard:
            _check_cond(ctx, guard, aenv, owner)
        _check_stmts(ctx, body, aenv, owner, rets, arg_names, fn_decl, in_loop, dict(decl_env))


def _check_for_in_stmt(ctx: Context, s: ForInStmt, env: Dict[str, Type], decl_env: Dict[str, Type],
                       owner: Optional[str], rets: Optional[List[Type]], fn_decl: Optional[FnDecl]):
    it = _check_expr(ctx, s.iter_expr, env, owner)
    if s.is_of:
        base = index_result(ctx, it)
        if base is None and not is_object_type(ctx, it):
            raise TypeCheckError(f"for … of: expected tbl, got {it}", s.line)
        el = base if base is not None else (Name(root_class(ctx)) if is_object_type(ctx, it) else ANY)
    else:
        ext = ctx.externs.get(s.iter_expr.func) if (isinstance(s.iter_expr, Call)
                                                    and s.iter_expr.receiver is None) else None
        void_ext = ext is not None and not ext.ret_types
        if void_ext or (it != ANY and not isinstance(it, Fn) and it != Name("fn")):
            raise TypeCheckError(f"for … in: expected an iterator, got {NIL if void_ext else it}",
                                 s.line)
        el = ANY
    benv = dict(env)
    bdecl = dict(decl_env)
    for i, (vn, vt) in enumerate(s.vars):
        if s.is_of:
            elem = NUM if (len(s.vars) == 2 and i == 0) else el
        elif isinstance(it, Fn) and i < len(it.rets):
            elem = without_nil(it.rets[i]) if i == 0 else it.rets[i]
        else:
            elem = el
        if vt is not None and elem != ANY:
            expect(ctx, f"for variable {vn}", elem, vt, s.line)
        if vn != "_":
            benv[vn] = bdecl[vn] = vt or elem
    _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl, in_loop=True, decl_env=bdecl)


def _check_stmts(ctx: Context, stmts: List[Stmt], env: Dict[str, Type],
                 owner: Optional[str] = None, rets: Optional[List[Type]] = None,
                 arg_names: Optional[Dict[int, str]] = None,
                 fn_decl: Optional[FnDecl] = None, in_loop: bool = False,
                 decl_env: Optional[Dict[str, Type]] = None):
    denv = dict(env) if decl_env is None else decl_env
    for s in stmts:
        match s:
            case SayStmt():
                _check_expr(ctx, s.expr, env, owner, STR)
            case ReturnStmt():
                if s.kind == "break" and not in_loop:
                    raise Error("break: not inside a loop", s.line)
                _check_return_stmt(ctx, s, env, owner, rets, fn_decl)
            case LocalStmt():
                _check_local_stmt(ctx, s, env, denv, owner)
            case AssignStmt():
                _check_assign_stmt(ctx, s, env, denv, owner)
            case Call():
                if s.receiver is None:
                    ext = ctx.externs.get(s.func)
                    if ext is not None and ext.kind in ("value", "lvalue"):
                        raise Error(f"{s.func}: an expression, not a statement (use its value)",
                                    s.line)
                _check_call(ctx, s, env, owner)
            case IfStmt():
                _check_if_stmt(ctx, s, env, denv, owner, rets, arg_names, fn_decl, in_loop)
            case WhileStmt():
                _check_while_stmt(ctx, s, env, denv, owner, rets, arg_names, fn_decl)
            case MatchStmt():
                _check_match_stmt(ctx, s, env, denv, owner, rets, arg_names, fn_decl, in_loop)
            case ForNumStmt():
                for bound in (s.start, s.stop, s.step):
                    if bound is not None:
                        _check_expr(ctx, bound, env, owner, NUM)
                benv = dict(env)
                bdecl = dict(denv)
                if s.var != "_":
                    benv[s.var] = bdecl[s.var] = s.var_type or NUM
                if s.var_type:
                    expect(ctx, f"for variable {s.var}", NUM, s.var_type, s.line)
                _check_stmts(ctx, s.body, benv, owner, rets, fn_decl=fn_decl,
                             in_loop=True, decl_env=bdecl)
            case ForInStmt():
                _check_for_in_stmt(ctx, s, env, denv, owner, rets, fn_decl)


# --- Functions, Entities, Verbs & Dialogues ---------------------------------

def _referenced_fns(body: Any, fn_names: Iterable[str]) -> List[str]:
    known = set(fn_names)
    out: List[str] = []
    seen: Set[str] = set()

    def walk(cur: Any):
        if isinstance(cur, (list, tuple)):
            for x in cur:
                walk(x)
            return
        if isinstance(cur, (Call, FnRef, Sym)):
            name = cur.func if isinstance(cur, Call) else cur.name
            if name in known and name not in seen:
                seen.add(name)
                out.append(name)
        if hasattr(cur, "__dataclass_fields__"):
            for k in cur.__dataclass_fields__:
                if k not in ("typ", "vtyp"):
                    walk(getattr(cur, k))

    walk(body)
    return out


def _order_fns_by_calls(fns: List[FnDecl]) -> List[FnDecl]:
    """Post-order DFS over the call graph so callees infer return types before callers."""
    by_name = {f.name: f for f in fns}
    visited: Set[str] = set()
    ordered: List[FnDecl] = []

    def dfs(name: str):
        if name in visited or name not in by_name:
            return
        visited.add(name)
        for dep in _referenced_fns(by_name[name].body, by_name):
            dfs(dep)
        ordered.append(by_name[name])

    for fn in fns:
        dfs(fn.name)
    return ordered


def _prepare_fn_signature(ctx: Context, item: FnDecl):
    if item.name in ctx.entries:
        want = ctx.entries[item.name]
        if len(item.params) != len(want):
            raise Error(f"entry {item.name}: the engine calls it with "
                        f"{len(want)} argument(s), declared {len(item.params)}", item.line)
        item.params = [(pn, wt if pt == ANY else pt)
                       for (pn, pt), (_wn, wt) in zip(item.params, want)]
        for (pn, pt), (_wn, wt) in zip(item.params, want):
            expect(ctx, f"entry {item.name}({pn})", wt, pt, item.line)
    check_signature(ctx, item)


def _typecheck_fn_body(ctx: Context, item: FnDecl):
    if not isinstance(item.body, list):
        return
    env = {pn: pt for pn, pt in item.params if pn != "_"}
    if item.variadic is not None:
        env["..."] = item.variadic
    first_t = item.params[0][1] if (item.params and item.params[0][0] == "s") else None
    owner = first_t.name if (isinstance(first_t, Name) and first_t.name in ctx.classes) else None
    rets: List[Type] = []
    _check_stmts(ctx, item.body, env, owner, rets, fn_decl=item if item.ret_types else None)
    falls_through = bool(item.body) and not returns_all(item.body)
    if item.ret_types:
        if falls_through and not types.is_optional(union(*item.ret_types)):
            raise Error(f"fn {item.name}: {', '.join(str(t) for t in item.ret_types)} is declared, but a "
                        f"path leaves the body without `return` (add `return` or `pass`, "
                        f"or declare `{without_nil(item.ret_types[0])}?`)", item.line)
    else:
        if rets and falls_through:
            rets.append(NIL)
        item.ret_types = [union(*rets)] if rets else [ANY]


def _check_callable_part(ctx: Context, part: Any, env: Dict[str, Type], owner: Optional[str],
                         want: Optional[Type], where: str, line: int,
                         arg_names: Optional[Dict[int, str]] = None):
    if isinstance(part, FnRef):
        _check_fnref(ctx, part, want, where)
    elif isinstance(part, list):
        rets: List[Type] = []
        _check_stmts(ctx, part, dict(env), owner, rets, arg_names)
        returns = types.fn_returns(want) if want is not None else ()
        for t in (rets if returns else ()):
            expect(ctx, where, t, union(*returns), line)
    elif isinstance(part, Expr):
        _check_expr(ctx, part, dict(env), owner, want)


def _check_ref_prop(ctx: Context, where: str, p: Prop):
    if not p.is_ref or p.value is None or isinstance(p.value, (list, FnRef, Lambda)):
        return
    val = p.value
    if isinstance(val, Lit) and val.kind == "str":
        raise Error(f"{where}: object reference must be a bare name, not a quoted string "
                    f"({val.val!r})", p.line)
    for it in (val.items if isinstance(val, ListLit) else [val]):
        if isinstance(it, Lit) and it.kind == "str" and isinstance(val, ListLit):
            name = it.val.strip()
            if name not in ctx.objects:
                raise Error(f"{where}: unknown object reference {name!r}", it.line or p.line)
        elif isinstance(it, Sym):
            name = it.name
            if name not in ctx.objects and name not in ctx.globals and ctx.callable_decl(name) is None:
                raise Error(f"{where}: unknown object reference {name!r}", it.line or p.line)
        elif isinstance(it, (UnaryOp, BinOp)) and getattr(it, "op", "") not in ("and", "or"):
            raise Error(f"{where}: expected object reference, got expression", p.line)


def _prop_body_env(ctx: Context, p: Prop) -> Dict[str, Type]:
    names = list(p.type_params or [])
    if p.params is None and names:
        p.params = names
    one = types.fn_of(p.typ) if p.typ is not None else None
    env = {(names[i] if i < len(names) and names[i] else f"_{i}"): t
           for i, t in enumerate(one.params if one else ())}
    env.setdefault("s", Name(root_class(ctx)))
    for pn in p.params or ():
        if pn != "_":
            env.setdefault(pn, ANY)
    return env


def _check_emit(where: str, emit: Emit, value: Any, line: int):
    if emit.form == "none":
        if not (isinstance(value, Lit) and value.kind == "bool"):
            raise TypeCheckError(f"{where}: `:{emit.method}()` takes a `true`/`false` value", line)
    elif emit.form == "table":
        if not isinstance(value, DictLit):
            raise TypeCheckError(f"{where}: `:{emit.method}{{...}}` takes a `{{ ... }}` table", line)


def _handler_event_args(ctx: Context, h: Handler) -> List[Type]:
    per = [list(ctx.event_args.get(ev) or []) for ev in h.events]
    out: List[Type] = []
    for i in range(max((len(x) for x in per), default=0)):
        t = union(*dict.fromkeys(x[i] for x in per if i < len(x)))
        out.append(opt(t) if any(i >= len(x) for x in per) and not types.is_optional(t) else t)
    return out


def _handler_params(ctx: Context, owner: Optional[str], kind: str, h: Handler
                    ) -> Tuple[List[Tuple[str, Type]], Dict[int, str]]:
    self_t = Name(kind if (kind in ctx.classes or kind in ctx.objects) else root_class(ctx))
    params: List[Tuple[str, Type]] = [("s", self_t)]
    room_like = inherits(ctx, kind, room_root(ctx)) or owner in ("game", "mp", None)
    if any(ev in ("Any", "Default") for ev in h.events):
        params += [("ev", EVENT), ("w", Name(root_class(ctx))), ("wh", Name(root_class(ctx)))]
        names = ("w", "wh", "w2", "w3")
        return params, ({i: names[i - 1] for i in range(1, len(names) + 1)}
                        if not room_like else {i: names[i] for i in range(len(names))})
    sigs = _handler_event_args(ctx, h)
    acted = bool(sigs) and any(ev in ctx.event_acted for ev in h.events)
    arg_names: Dict[int, str] = {}
    if acted and room_like:
        params.append(("w", Name(root_class(ctx))))
        arg_names[0] = "w"
    for i, st in enumerate(sigs[1:] if acted else sigs, start=1 if acted else 0):
        name = HANDLER_PARAMS[len(params)]
        params.append((name, st))
        arg_names[i] = name
    if h.params is not None:
        no_duplicates((pn for pn in h.params if pn != "_"),
                      f"{h.phase} {','.join(h.events)}: parameter", h.line)
        if len(h.params) > len(params):
            raise Error(f"{h.phase} {','.join(h.events)}: the engine passes "
                        f"{len(params)} parameter(s) here, the handler declares {len(h.params)}",
                        h.line)
        params = [(h.params[i], params[i][1]) for i in range(len(h.params))]
    return params, arg_names


def _check_entity(ctx: Context, ent: EntityDecl):
    owner = ent.name
    kind = entity_kind(ctx, ent)
    if ent.kind == "impl" and ent.children:
        raise Error(f"impl {owner}: cannot hold an object — declare it at the top level "
                    f"(or put it into another object with `with`/`found_in`)",
                    ent.children[0].line)
    no_duplicates((p.name for p in ent.props), f"{owner or kind}: field", ent.line)
    no_duplicates((f"{h.phase} {','.join(h.events)}" for h in ent.handlers),
                  f"{owner or kind}: handler", ent.line)
    for p in ent.props:
        try:
            where = f"{owner}.{p.name}" if owner else p.name
            _check_ref_prop(ctx, where, p)
            if isinstance(p.value, list):
                env = _prop_body_env(ctx, p)
                env["load"] = BOOL
                if p.typ is not None and types.fn_of(p.typ) is None:
                    raise TypeCheckError(f"{where}: expected {p.typ}, got a block "
                                         f"(a block is a function)", p.line)
                rets: List[Type] = []
                _check_stmts(ctx, p.value, env, owner, rets)
                want = types.fn_returns(p.typ) if p.typ else ()
                for t in rets:
                    if want and not any(is_subtype(ctx, t, w) for w in want):
                        raise TypeCheckError(f"{where}: return {t}, declared returns "
                                             f"{', '.join(str(w) for w in want)}", p.line)
            else:
                _check_callable_part(ctx, p.value, {"s": Name(root_class(ctx))}, owner, p.typ, where, p.line)
            if p.emit and p.value is not None:
                _check_emit(where, p.emit, p.value, p.line)
        except Error as e:
            raise attach_item_src(ctx, p, e) from None
    for h in ent.handlers:
        try:
            for ev in h.events:
                if ev not in ctx.event_names:
                    hint = close_hint(ev, ctx.event_names, lambda m: f" (did you mean {m!r}?)")
                    raise Error(f"{owner or kind}: unknown event {ev!r}{hint}", h.line)
            params, arg_names = _handler_params(ctx, owner, kind, h)
            h.params = [pn for pn, _t in params]
            where = f"{owner or kind}: {h.phase} {','.join(h.events)}"
            want = Fn(tuple(t for _n, t in params), ()) if isinstance(h.body, FnRef) else (
                None if isinstance(h.body, list) else HANDLER_VALUE)
            _check_callable_part(ctx, h.body, {pn: pt for pn, pt in params if pn != "_"},
                                 owner, want, where, h.line, arg_names)
        except Error as e:
            raise attach_item_src(ctx, h, e) from None
    for ch in ent.children:
        _check_entity(ctx, ch)


def _check_talk(ctx: Context, td: TalkDecl):
    env = {"s": Name("talk")}
    no_duplicates((p.name for p in td.props), f"talk {td.name}: field", td.line)
    labels = [ln for ln, _say, _ch in td.labels]
    for ln in labels:
        if labels.count(ln) > 1:
            raise Error(f"talk {td.name}: duplicate label {ln!r}", td.line)

    def chk_choice(ch: TalkChoice):
        if ch.next_label and ch.next_label not in labels:
            raise Error(f"talk {td.name}: unknown label {ch.next_label!r} in `next`/`->`", ch.line)
        for part, want, what in [(ch.cond, None, "when")] + [
            (getattr(ch, f), ctx.fields.get("choice", {}).get(f), f) for f in CHOICE_FIELDS
        ]:
            _check_callable_part(ctx, part, env, td.name, want, f"talk {td.name}: {what}", ch.line)
        for sub in ch.children:
            chk_choice(sub)

    _check_callable_part(ctx, td.intro, env, td.name, None, "", td.line)
    for c in td.choices:
        chk_choice(c)
    for _ln, lsay, lcs in td.labels:
        _check_callable_part(ctx, lsay, env, td.name, None, "", td.line)
        for c in lcs:
            chk_choice(c)


def check_program(prog: Program) -> Context:
    ctx = build_context(prog)
    fns: List[FnDecl] = []
    for item in prog.items:
        try:
            if isinstance(item, ExternDecl):
                check_signature(ctx, item)
            elif isinstance(item, FnDecl):
                _prepare_fn_signature(ctx, item)
                fns.append(item)
        except Error as e:
            raise attach_item_src(ctx, item, e) from None

    for fn in _order_fns_by_calls(fns):
        try:
            _typecheck_fn_body(ctx, fn)
        except Error as e:
            raise attach_item_src(ctx, fn, e) from None

    for item in prog.items:
        try:
            match item:
                case VerbDecl() if item.hint is not None:
                    where = f"verb {item.name.split('#')[-1]}: hint"
                    want = Fn((Name(root_class(ctx)),), (STR,)) \
                        if not isinstance(item.hint, Expr) else HANDLER_VALUE
                    _check_callable_part(ctx, item.hint, {"s": Name(root_class(ctx))},
                                         None, want, where, item.line)
                case VarDecl():
                    for vn, vt, ve, _vl in item.items:
                        if not (isinstance(ve, Sym) and ve.rk in ("obj", "event", "enum")):
                            got = _check_expr(ctx, ve, {}, None, vt)
                            if vt is None:
                                ctx.globals[vn] = got
                case EntityDecl():
                    _check_entity(ctx, item)
                case TalkDecl():
                    _check_talk(ctx, item)
        except Error as e:
            raise attach_item_src(ctx, item, e) from None
    return ctx
