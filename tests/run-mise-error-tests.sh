#!/bin/sh
# mise error tests: every tests/mise-errors/*.mise must fail to compile
# with exactly the stderr stored in the sibling .err file (pins line
# numbers and messages of the compile-time checks).
#
#   ./tests/run-mise-error-tests.sh
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PY=${PYTHON:-python3}

rc=0
ok=0
bad=0

pass() { ok=$((ok + 1)); echo "ok - $1"; }
fail() { bad=$((bad + 1)); rc=1; echo "FAIL - $1" >&2; }

for src in "$ROOT"/tests/mise-errors/*.mise; do
	[ -f "$src" ] || continue
	name=$(basename "$src" .mise)
	err="${src%.mise}.err"
	if [ ! -f "$err" ]; then
		fail "$name: missing .err"
		continue
	fi
	got=$("$PY" "$ROOT/extra/mise/mise.py" "$src" 2>&1 1>/dev/null)
	st=$?
	if [ "$st" -eq 0 ]; then
		fail "$name: compiled cleanly"
	elif [ "$got" != "$(cat "$err")" ]; then
		fail "$name: unexpected error"
		echo "  want: $(cat "$err")" >&2
		echo "  got:  $got" >&2
	else
		pass "$name"
	fi
done

echo "== mise-errors: ok=$ok failed=$bad =="
exit $rc
