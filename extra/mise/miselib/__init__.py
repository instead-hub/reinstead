"""MISE 2 compiler package."""
from .ast_nodes import Error
from .checker import check_program
from .emitter import Emitter
from .loader import load_includes
from .parser import parse_source


def transpile(src: str, src_dir: str = "", src_name: str = "") -> str:
    prog = load_includes(parse_source(src, src_name), src_dir)
    return Emitter(prog, check_program(prog)).emit()


__all__ = ["transpile", "Error"]
