SDLVER="${SDLVER:-sdl2}"
if [ "$SDLVER" = "sdl3" ]; then
	SDL_CFLAGS="`pkg-config --cflags sdl3` -DUSE_SDL3"
	SDL_LDFLAGS="`pkg-config --libs sdl3`"
else
	SDL_CFLAGS="`sdl2-config --cflags`"
	SDL_LDFLAGS="`sdl2-config --libs`"
fi
CFLAGS="$SDL_CFLAGS -Isrc/lua -Isrc/instead -Dunix"
LDFLAGS="$SDL_LDFLAGS -lm"
gcc -Wall -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS $LDFLAGS -o reinstead
rm -f *.o
