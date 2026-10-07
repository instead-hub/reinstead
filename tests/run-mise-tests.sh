#!/bin/sh
# mise tests: transpile tests/mise-* and compare with the committed
# main3.lua. With --engine also run the original game and the converted
# one on the same autoscript and compare transcripts (needs ./reinstead).
#
#   ./tests/run-mise-tests.sh            # transpile + compare only
#   ./tests/run-mise-tests.sh --engine   # plus runtime transcript checks
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BIN=${BIN:-$ROOT/reinstead}
ENGINE=0
[ "${1:-}" = "--engine" ] && ENGINE=1

if [ "$ENGINE" = 1 ] && [ ! -x "$BIN" ]; then
	echo "No binary $BIN — build it first: make" >&2
	exit 2
fi

WORK=$(mktemp -d)
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT INT TERM

rc=0
ok=0
bad=0

pass() { ok=$((ok + 1)); echo "ok - $1"; }
fail() { bad=$((bad + 1)); rc=1; echo "FAIL - $1" >&2; }

# --- transpile and compare ---------------------------------------------
for g in "$ROOT"/tests/mise-*/game.mise; do
	[ -f "$g" ] || continue
	dir=$(dirname "$g")
	name=$(basename "$dir")
	out="$WORK/$name.lua"
	if ! python3 "$ROOT/extra/mise/mise.py" "$g" -o "$out" 2>"$WORK/$name.err"; then
		fail "$name: transpile"
		cat "$WORK/$name.err" >&2
		continue
	fi
	if cmp -s "$out" "$dir/main3.lua"; then
		pass "$name: lua"
	else
		fail "$name: lua differs"
		diff -u "$dir/main3.lua" "$out" | head -40 >&2
	fi
done

# --- engine transcripts -------------------------------------------------
prep_script() {
	_m=транскрипт
	grep -qE '^lang:[[:space:]]*en' "$(dirname "$1")/game.mise" && _m=transcript
	if grep -qx "$_m" "$1"; then
		cat "$1" > "$2"
	else
		{ echo "$_m"; cat "$1"; } > "$2"
	fi
	tail -n 1 "$2" | grep -qx '!quit' || echo '!quit' >> "$2"
}

run_game() {
	_d=$1
	_s=$2
	_o=$3
	rm -f "$_d"/log*.txt
	_appdata=$(mktemp -d)
	SDL_VIDEODRIVER=dummy timeout 120 "$BIN" -appdata "$_appdata" \
		-noautosave "$_d" -i "$_s" >/dev/null 2>&1
	_r=$?
	_last=$(ls -t "$_d"/log*.txt 2>/dev/null | head -1)
	if [ -z "$_last" ]; then
		rm -rf "$_appdata"
		return 1
	fi
	cp "$_last" "$_o"
	rm -f "$_d"/log*.txt
	rm -rf "$_appdata"
	return "$_r"
}

strip_head() { tail -n +2 "$1"; }
alice_flt() {
	tail -n +2 "$1" | grep -vE '^(Белый|Чёрный) котёнок |^Тут есть |^$'
}

if [ "$ENGINE" = 1 ]; then
	for g in "$ROOT"/tests/mise-*/game.mise; do
		[ -f "$g" ] || continue
		dir=$(dirname "$g")
		name=$(basename "$dir")
		base=${name#mise-}
		orig="$ROOT/extra/metaparser-instead/games/$base"
		[ -d "$orig" ] || continue
		script="$WORK/$name.script"
		prep_script "$dir/autoscript" "$script"
		if ! run_game "$orig" "$script" "$WORK/$name.orig"; then
			fail "$name: original run"
			continue
		fi
		if ! run_game "$dir" "$script" "$WORK/$name.new"; then
			fail "$name: converted run"
			continue
		fi
		case "$base" in
		alice)
			alice_flt "$WORK/$name.orig" > "$WORK/$name.o"
			alice_flt "$WORK/$name.new" > "$WORK/$name.n"
			;;
		cloak-en)
			# the gameover finale answers the trailing empty input that
			# noparser originally swallowed (mp-en quits one turn later)
			flt() {
				tail -n +2 "$1" | grep -vE '^> $|^<i>\(examine\)</i>$|^Use restart to restart game\.$|^$'
			}
			flt "$WORK/$name.orig" > "$WORK/$name.o"
			flt "$WORK/$name.new" > "$WORK/$name.n"
			;;
		wtell)
			# the expected delta is one extra score line at the finale:
			# ignore score lines for the diff, but count them
			score='<i>(Счёт увеличился на 1)</i>'
			strip_head "$WORK/$name.orig" | grep -v "$score" > "$WORK/$name.o"
			strip_head "$WORK/$name.new" | grep -v "$score" > "$WORK/$name.n"
			co=$(grep -c "$score" "$WORK/$name.orig")
			cn=$(grep -c "$score" "$WORK/$name.new")
			if [ "$cn" -ne "$((co + 1))" ]; then
				fail "$name: score lines $co -> $cn (want +1)"
			fi
			;;
		*)
			strip_head "$WORK/$name.orig" > "$WORK/$name.o"
			strip_head "$WORK/$name.new" > "$WORK/$name.n"
			;;
		esac
		# converted dirs carry a generated dict.mrd; drop it
		rm -f "$dir/dict.mrd"
		if diff -u "$WORK/$name.o" "$WORK/$name.n" > "$WORK/$name.diff"; then
			pass "$name: transcript"
		else
			fail "$name: transcript differs"
			head -40 "$WORK/$name.diff" >&2
		fi
	done

	# Games without an original run against a committed golden transcript.
	for g in "$ROOT"/tests/mise-*/game.mise; do
		[ -f "$g" ] || continue
		dir=$(dirname "$g")
		name=$(basename "$dir")
		base=${name#mise-}
		[ -f "$dir/transcript.golden" ] || continue
		[ -d "$ROOT/extra/metaparser-instead/games/$base" ] && continue
		[ -f "$dir/autoscript" ] || continue
		script="$WORK/$name.script"
		prep_script "$dir/autoscript" "$script"
		if ! run_game "$dir" "$script" "$WORK/$name.new"; then
			fail "$name: run"
			continue
		fi
		rm -f "$dir/dict.mrd"
		tail -n +2 "$WORK/$name.new" > "$WORK/$name.n"
		if diff -u "$dir/transcript.golden" "$WORK/$name.n" \
				> "$WORK/$name.diff"; then
			pass "$name: transcript (golden)"
		else
			fail "$name: transcript golden differs"
			head -40 "$WORK/$name.diff" >&2
		fi
	done
fi

echo "== mise: ok=$ok failed=$bad =="
exit $rc
