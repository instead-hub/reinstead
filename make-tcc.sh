SDLVER="${SDLVER:-sdl2}"
if [ "$SDLVER" = "sdl3" ]; then
	SDL_CFLAGS="`pkg-config --cflags sdl3` -DUSE_SDL3"
	SDL_LDFLAGS="`pkg-config --libs sdl3`"
else
	SDL_CFLAGS="`pkg-config --cflags sdl2`"
	SDL_LDFLAGS="`pkg-config --libs sdl2`"
fi
CFLAGS="$SDL_CFLAGS -Isrc/lua -Isrc/instead -Dunix -DSDL_DISABLE_IMMINTRIN_H -DSTBI_NO_SIMD"
LDFLAGS="$SDL_LDFLAGS -lm"
tcc -o reinstead src/*.c src/instead/*.c src/lua/*.c $CFLAGS $LDFLAGS
rm -f *.o
