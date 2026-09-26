# Build metaparser-js: RE:INSTEAD as WebAssembly (plus a JS fallback) with Emscripten.
#
# Only Emscripten is required: Lua comes from ../lua, zlib is built by
# Emscripten itself (the USE_ZLIB port). If emcc is not in PATH, use
# ./build.sh — it activates emsdk and works around its bundled node on
# musl systems.
#
# Targets:
#   make          wasm + js fallback + publishable tree (build/dist)
#   make wasm     WebAssembly only
#   make js       JS fallback only (WASM=0, deprecated but working)
#   make dist     assemble the publishable tree
#   make fs       build the game virtual filesystem only
#   make smoke    quick check under node, no browser
#   make serve    serve build/dist locally
#   make clean    remove build/

EMCC  ?= emcc
NODE  ?= node
ENV   ?= web
PORT  ?= 8000

BUILD  := build
OUT    := $(BUILD)/dist
FS     := $(BUILD)/fs
OBJ    := $(BUILD)/obj
COMPAT := compat

ENGINE      := ../instead
ENGINE_ROOT := ..
LUA         := ../lua
DATA        := ../../data/stead3

# Demo game used by the smoke check.
SMOKE_GAME ?= ../../data/games/trial

# --- sources --------------------------------------------------------------

LUA_SRCS    := $(wildcard $(LUA)/*.c)
ENGINE_SRCS := $(wildcard $(ENGINE)/*.c)
MP_SRCS     := metaparser.c ioapi.c unzip.c unpack.c

LUA_OBJS    := $(patsubst $(LUA)/%.c,$(OBJ)/lua/%.o,$(LUA_SRCS))
ENGINE_OBJS := $(patsubst $(ENGINE)/%.c,$(OBJ)/engine/%.o,$(ENGINE_SRCS)) \
               $(OBJ)/engine/instead_lib.o
MP_OBJS     := $(patsubst %.c,$(OBJ)/mp/%.o,$(MP_SRCS))
OBJS        := $(LUA_OBJS) $(ENGINE_OBJS) $(MP_OBJS)

# --- flags ----------------------------------------------------------------

CFLAGS := -O2 -I$(COMPAT) -I$(LUA) -I$(ENGINE_ROOT) -I$(ENGINE)

CFLAGS_ENGINE := -Dunix
# -sUSE_ZLIB=1 is needed while compiling too: it makes Emscripten provide
# zlib.h from its port (a clean emsdk builds the port on demand).
CFLAGS_MP     := -Dunix -D_USE_UNPACK -DNOUNCRYPT -DGAMES_PATH='"/games"' -sUSE_ZLIB=1

EXPORTS := ['_parser_start','_parser_stop','_parser_cmd','_parser_restart', \
            '_parser_autoload','_parser_autosave','_parser_load','_parser_save', \
            '_parser_path','_parser_clear','_parser_savename']

RUNTIME_METHODS := ['ccall','cwrap','UTF8ToString']

LDFLAGS := -O2 -sUSE_ZLIB=1 -lidbfs.js \
           -sALLOW_MEMORY_GROWTH=1 -sFORCE_FILESYSTEM=1 \
           -sEXPORTED_FUNCTIONS="$(EXPORTS)" \
           -sEXPORTED_RUNTIME_METHODS="$(RUNTIME_METHODS)"

# --- virtual filesystem ---------------------------------------------------

# Nothing extra is wanted in the image: debug modules, the SDL-only
# gui/sound/sprites layers, and the full morphs.mrd dictionary (games ship
# their own dict.mrd).
FS_BLACKLIST := dbg.lua dbg-ru.lua ext/gui.lua ext/sandbox.lua ext/sound.lua \
                ext/sprites.lua ext/timer.lua finger.lua keys.lua click.lua \
                CMakeLists.txt morph/morphs.mrd

FS_STAMP   := $(BUILD)/.fs.stamp
FS_SOURCES := $(shell find $(DATA) -type f) mp.lua

# --- targets --------------------------------------------------------------

.PHONY: all wasm js dist fs smoke clean serve

all: dist

wasm: $(OUT)/metaparser-wasm.js
js:   $(OUT)/metaparser-js.js

dist: wasm js
	@mkdir -p $(OUT)
	cp index.html README $(OUT)/
	rm -rf $(OUT)/lib
	cp -R lib $(OUT)/lib

fs: $(FS_STAMP)

# --- compilation ----------------------------------------------------------

$(OBJ)/lua/%.o: $(LUA)/%.c
	@mkdir -p $(@D)
	$(EMCC) -c $(CFLAGS) $< -o $@

$(OBJ)/engine/%.o: $(ENGINE)/%.c
	@mkdir -p $(@D)
	$(EMCC) -c $(CFLAGS) $(CFLAGS_ENGINE) $< -o $@

$(OBJ)/engine/instead_lib.o: $(ENGINE_ROOT)/instead_lib.c
	@mkdir -p $(@D)
	$(EMCC) -c $(CFLAGS) $(CFLAGS_ENGINE) $< -o $@

$(OBJ)/mp/%.o: %.c
	@mkdir -p $(@D)
	$(EMCC) -c $(CFLAGS) $(CFLAGS_MP) $< -o $@

# --- filesystem -----------------------------------------------------------

$(FS_STAMP): $(FS_SOURCES)
	rm -rf $(FS)
	mkdir -p $(FS)/stead
	cp $(DATA)/tiny3.lua $(FS)/stead/tiny3.lua
	cp mp.lua $(FS)/stead/mp.lua
	cp -R $(DATA) $(FS)/stead/stead3
	rm -f $(addprefix $(FS)/stead/stead3/,$(FS_BLACKLIST))
	touch $@

# --- linking --------------------------------------------------------------

$(OUT)/metaparser-wasm.js: $(OBJS) $(FS_STAMP) mp-pre.js mp-post.js
	@mkdir -p $(OUT)
	$(EMCC) $(OBJS) $(LDFLAGS) -sENVIRONMENT=$(ENV) \
		--pre-js mp-pre.js --post-js mp-post.js --preload-file $(FS)@/ -o $@

$(OUT)/metaparser-js.js: $(OBJS) $(FS_STAMP) mp-pre.js mp-post.js
	@mkdir -p $(OUT)
	$(EMCC) $(OBJS) $(LDFLAGS) -sENVIRONMENT=$(ENV) -sWASM=0 \
		--pre-js mp-pre.js --post-js mp-post.js --preload-file $(FS)@/ -o $@

# --- checks and helpers ---------------------------------------------------

# Node build plus a demo game run: make sure the parser answers.
SMOKE_JS := $(BUILD)/smoke/mp.js

$(SMOKE_JS): $(OBJS) $(FS_STAMP) mp-post.js
	@mkdir -p $(@D)
	$(EMCC) $(OBJS) $(LDFLAGS) -sENVIRONMENT=node -sMODULARIZE=1 \
		-sEXPORT_NAME=createMP \
		--preload-file $(FS)@/ --preload-file $(SMOKE_GAME)@/game -o $@

smoke: $(SMOKE_JS)
	$(NODE) test/smoke.js

serve: dist
	@echo "http://localhost:$(PORT)/"
	cd $(OUT) && python3 -m http.server $(PORT)

clean:
	rm -rf $(BUILD)
