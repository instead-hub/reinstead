"""Current source position (file and line) for diagnostics."""

from .common import CURRENT_FILE, CURRENT_LINE


def at(block, idx):
    """Remember the position of item `idx` of `block`, return its line."""
    line = block.line_at(idx)
    if line:
        CURRENT_LINE[0] = line
    if idx < len(block.srcs):
        CURRENT_FILE[0] = block.srcs[idx]
    return line


def use(block, key):
    """Remember the position of the first item named `key`."""
    for i, (k, _v) in enumerate(block.items):
        if k == key:
            return at(block, i)
    return None
