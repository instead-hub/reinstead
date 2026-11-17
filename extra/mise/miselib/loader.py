"""Include DAG loader for MISE 2."""
import os
from typing import List, Set

from .ast_nodes import EntityDecl, Error, Program
from .parser import parse_source


def _stamp_src(items: list, src_name: str):
    for it in items:
        if hasattr(it, "src") and not it.src:
            it.src = src_name
        if isinstance(it, EntityDecl):
            for p in it.props:
                if not p.src:
                    p.src = src_name
            for h in it.handlers:
                if not h.src:
                    h.src = src_name
            if it.children:
                _stamp_src(it.children, src_name)


def _resolve_include_paths(inc: str, lang: str, src_dir: str, std_dir: str) -> List[str]:
    for d in (src_dir, std_dir):
        if d and os.path.isfile(os.path.join(d, f"{inc}.mise")):
            paths = [os.path.join(d, f"{inc}.mise")]
            lp = os.path.join(d, f"{inc}-{lang}.mise")
            if os.path.isfile(lp):
                paths.append(lp)
            return paths
    raise Error(f"include file not found: {inc!r}")


def _merge_unique(dst: List[str], extra: List[str]) -> List[str]:
    out = list(dst)
    for x in extra:
        if x not in out:
            out.append(x)
    return out


def _load_into(prog: Program, src_dir: str, std_dir: str, lang: str,
               loaded: Set[str], stack: List[str]) -> Program:
    _stamp_src(prog.items, prog.root_src)
    if not prog.includes:
        return prog
    merged_items: list = []
    merged_reqs: List[str] = []
    merged_fmt: List[str] = []
    for inc in prog.includes:
        for p in _resolve_include_paths(inc, lang, src_dir, std_dir):
            rp = os.path.realpath(p)
            if rp in stack:
                cycle = " -> ".join(os.path.basename(s) for s in stack[stack.index(rp):] + [rp])
                raise Error(f"circular include: {cycle}")
            if rp in loaded:
                continue
            loaded.add(rp)
            name = os.path.basename(p)
            with open(p, "r", encoding="utf-8") as f:
                sub = parse_source(f.read(), name)
            _load_into(sub, os.path.dirname(p), std_dir, lang, loaded, stack + [rp])
            merged_items.extend(sub.items)
            merged_reqs = _merge_unique(merged_reqs, sub.requires)
            merged_fmt = _merge_unique(merged_fmt, sub.fmt)
    prog.items = merged_items + prog.items
    prog.requires = _merge_unique(merged_reqs, prog.requires)
    prog.fmt = _merge_unique(merged_fmt, prog.fmt)
    return prog


def load_includes(prog: Program, src_dir: str) -> Program:
    std_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    loaded: Set[str] = set()
    stack: List[str] = []
    if src_dir and prog.root_src:
        root_file = os.path.join(src_dir, prog.root_src)
        if os.path.isfile(root_file):
            rp = os.path.realpath(root_file)
            loaded.add(rp)
            stack.append(rp)
    return _load_into(prog, src_dir, std_dir, prog.lang, loaded, stack)
