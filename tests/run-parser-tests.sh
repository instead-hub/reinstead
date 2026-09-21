#!/bin/sh
# Headless-запуск парсерных тестов (tests/parser-tests).
# Требует собранный reinstead: make
set -u

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BIN=${BIN:-$ROOT/reinstead}
APPDATA=$(mktemp -d)

if [ ! -x "$BIN" ]; then
	echo "Нет бинарника $BIN — сначала соберите: make" >&2
	exit 2
fi

cleanup() { rm -rf "$APPDATA"; }
trap cleanup EXIT INT TERM

# timeout защищает от зависания, если тесты не дошли до os.exit()
SDL_VIDEODRIVER=dummy timeout 120 "$BIN" -appdata "$APPDATA" -noautosave "$ROOT/tests/parser-tests"
exit $?
