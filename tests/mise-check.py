#!/usr/bin/env python3
"""Batch transpile checks for the mise test suite.

One process for everything: `import miselib` costs ~0.1 s, so 156 separate
`mise.py` runs cost more than the work itself.

    mise-check.py goldens <root>   # tests/mise-*/game.mise == main3.lua
    mise-check.py errors <root>    # tests/mise-errors/*.mise -> .err
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extra", "mise"))

from miselib import Error, transpile  # noqa: E402

ok = bad = 0


def report(name: str, good: bool, detail: str = ""):
    global ok, bad
    if good:
        ok += 1
        print(f"ok - {name}")
    else:
        bad += 1
        print(f"FAIL - {name}", file=sys.stderr)
        if detail:
            sys.stderr.write(detail if detail.endswith("\n") else detail + "\n")


def run(path: str) -> str:
    """Transpile one file; raise Error with the message as the CLI prints it."""
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    return transpile(src, os.path.dirname(os.path.abspath(path)), os.path.basename(path))


def goldens(root: str):
    import glob
    for game in sorted(glob.glob(os.path.join(root, "tests", "mise-*", "game.mise"))):
        d = os.path.dirname(game)
        name = os.path.basename(d)
        want = os.path.join(d, "main3.lua")
        try:
            out = run(game)
        except Error as e:
            report(f"{name}: transpile", False, e.format())
            continue
        if not os.path.exists(want):
            report(f"{name}: lua", False, f"no {want}")
            continue
        with open(want, "r", encoding="utf-8") as f:
            expected = f.read()
        ok_ = out == expected
        detail = ""
        if not ok_:
            import difflib
            detail = "".join(list(difflib.unified_diff(
                expected.splitlines(True), out.splitlines(True),
                fromfile=want, tofile="(generated)", n=2))[:40])
        report(f"{name}: lua", ok_, detail)


def errors(root: str):
    import glob
    for case in sorted(glob.glob(os.path.join(root, "tests", "mise-errors", "*.mise"))):
        name = os.path.basename(case)[:-len(".mise")]
        want = os.path.join(os.path.dirname(case), name + ".err")
        if not os.path.exists(want):
            report(f"{name}: missing {name}.err", True)
            continue
        try:
            run(case)
        except Error as e:
            got = e.format() + "\n"
        else:
            report(f"{name}: expected an error, transpile succeeded", False)
            continue
        with open(want, "r", encoding="utf-8") as f:
            expected = f.read()
        report(f"{name}: error", got == expected,
               f"-{expected}+{got}" if got != expected else "")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("goldens", "errors"):
        sys.exit(__doc__)
    mode = sys.argv[1]
    {"goldens": goldens, "errors": errors}[mode](sys.argv[2])
    if mode == "errors":       # the shell prints the aggregate for goldens
        print(f"== mise-errors: ok={ok} failed={bad} ==")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
