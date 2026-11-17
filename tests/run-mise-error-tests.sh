#!/bin/sh
# mise error tests: every tests/mise-errors/*.mise must fail with exactly
# the committed stderr from the sibling `.err` file.
#
#   ./tests/run-mise-error-tests.sh
#
# Regenerate one case: python3 extra/mise/mise.py <case>.mise 2> <case>.err
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
rc=0
ok=0
bad=0

pass() { ok=$((ok + 1)); echo "ok - $1"; }
fail() { bad=$((bad + 1)); rc=1; echo "FAIL - $1" >&2; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM

python3 "$ROOT/tests/mise-check.py" errors "$ROOT"
exit $?
