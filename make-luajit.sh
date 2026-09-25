SDLVER="${SDLVER:-sdl2}"
if [ "$SDLVER" = "sdl3" ]; then
	SDL_CFLAGS="`pkg-config --cflags sdl3` -DUSE_SDL3"
	SDL_LDFLAGS="`pkg-config --libs sdl3`"
else
	SDL_CFLAGS="`pkg-config --cflags sdl2`"
	SDL_LDFLAGS="`pkg-config --libs sdl2`"
fi
CFLAGS="$SDL_CFLAGS `pkg-config --cflags luajit` -Isrc/instead -Dunix"
LDFLAGS="$SDL_LDFLAGS `pkg-config --libs luajit` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c $CFLAGS $LDFLAGS -o reinstead
rm -f *.o
