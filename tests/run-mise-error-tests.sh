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

for g in "$ROOT"/tests/mise-errors/*.mise; do
	[ -f "$g" ] || continue
	name=$(basename "$g" .mise)
	want="$(dirname "$g")/$name.err"
	[ -f "$want" ] || { fail "$name: missing $name.err"; continue; }
	# Run from the case directory so `line N` numbers are file-local.
	( cd "$(dirname "$g")" && python3 "$ROOT/extra/mise/mise.py" "$name.mise" -o /dev/null ) \
		>"$WORK/$name.out" 2>"$WORK/$name.err"
	if [ $? -eq 0 ]; then
		fail "$name: expected an error, transpile succeeded"
		continue
	fi
	if diff -u "$want" "$WORK/$name.err" > "$WORK/$name.diff"; then
		pass "$name: error"
	else
		fail "$name: stderr differs"
		head -20 "$WORK/$name.diff" >&2
	fi
done

echo "== mise-errors: ok=$ok failed=$bad =="
exit $rc
