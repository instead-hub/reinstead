#!/usr/bin/env python3
"""CLI entry point for the MISE 2 transpiler."""
import argparse
import os
import sys

from miselib import Error, transpile


def main():
    ap = argparse.ArgumentParser(description="Transpile .mise to INSTEAD main3.lua")
    ap.add_argument("input", help="Input .mise file")
    ap.add_argument("-o", "--output", help="Output .lua file (default: stdout)")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            src = f.read()
        src_dir = os.path.dirname(os.path.abspath(args.input))
        out = transpile(src, src_dir, os.path.basename(args.input))
    except Error as e:
        sys.stderr.write(e.format() + "\n")
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
