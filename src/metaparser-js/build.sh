#!/usr/bin/env bash
#
# Build metaparser-js (RE:INSTEAD -> WebAssembly) with Emscripten.
#
# Usage:
#   ./build.sh            # everything: wasm, js fallback and build/dist
#   ./build.sh wasm       # wasm only
#   ./build.sh smoke      # check under node, no browser
#   ./build.sh clean
#   EMSDK=/path/to/emsdk ./build.sh
#
# The script looks for emcc in PATH. If it is missing, it activates emsdk
# from $EMSDK, ~/emsdk, /opt/emsdk or /usr/local/emsdk and then runs make.

set -euo pipefail
cd "$(dirname "$0")"

find_emsdk() {
	local dir
	for dir in "${EMSDK:-}" "$HOME/emsdk" /opt/emsdk /usr/local/emsdk; do
		if [ -n "$dir" ] && [ -r "$dir/emsdk_env.sh" ]; then
			printf '%s\n' "$dir"
			return 0
		fi
	done
	return 1
}

if ! command -v "${EMCC:-emcc}" >/dev/null 2>&1; then
	if emsdk_dir=$(find_emsdk); then
		# shellcheck disable=SC1091
		. "$emsdk_dir/emsdk_env.sh" >/dev/null 2>&1 || true
	fi
fi

if ! command -v "${EMCC:-emcc}" >/dev/null 2>&1; then
	echo "error: emcc not found; install emsdk and set EMSDK=/path/to/emsdk" >&2
	exit 1
fi

# The node bundled with emsdk is built against glibc and does not run on
# musl (Alpine). Fall back to the system node in that case.
if [ -n "${EMSDK_NODE:-}" ] && ! "$EMSDK_NODE" --version >/dev/null 2>&1; then
	if command -v node >/dev/null 2>&1; then
		export EM_NODE_JS
		EM_NODE_JS=$(command -v node)
		echo "note: emsdk node does not run, using $EM_NODE_JS" >&2
	fi
fi

exec make "$@"
