export WORKSPACE="/home/peter/Devel/emsdk/env"
. /home/peter/Devel/emsdk/emsdk_env.sh
emcc -O2 -o reinstead.html src/*.c src/lua/*.c src/instead/*.c -Isrc/lua -Isrc/instead -Dunix -s USE_SDL=2 -DDATADIR=\"/data\" \
-lidbfs.js -s WASM=1 -s SAFE_HEAP=0  -s ALLOW_MEMORY_GROWTH=1 \
--preload-file data/
