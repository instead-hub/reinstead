#!/bin/sh
# Headless run of parser tests (tests/parser-tests, tests/match-dump).
# Requires a built reinstead: make
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BIN=${BIN:-$ROOT/reinstead}
APPDATA=$(mktemp -d)
DUMP="$ROOT/tests/match-dump"

if [ ! -x "$BIN" ]; then
	echo "No binary $BIN — build it first: make" >&2
	exit 2
fi

cleanup() { rm -rf "$APPDATA"; }
trap cleanup EXIT INT TERM

rc=0

# timeout guards against hanging if tests never reach os.exit()
SDL_VIDEODRIVER=dummy timeout 120 "$BIN" -appdata "$APPDATA" -noautosave "$ROOT/tests/parser-tests" || rc=1

# golden snapshot of mp:match behavior on a deterministic corpus
SDL_VIDEODRIVER=dummy timeout 300 "$BIN" -appdata "$APPDATA" -noautosave "$DUMP" >/dev/null 2>&1 || rc=1
if diff -u "$DUMP/golden.txt" "$DUMP/out.txt"; then
	rm -f "$DUMP/out.txt"
else
	echo "match-dump: golden mismatch" >&2
	rc=1
fi

exit $rc
