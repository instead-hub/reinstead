SDLV="${SDLV:-2}"
if [ "$SDLV" = "3" ]; then
	SDL_CFLAGS="-Iwindows/ -Iwindows/SDL3 -DUSE_SDL3"
	SDL_LDFLAGS="-Lwindows/SDL3 -lSDL3 -lm"
else
	SDL_CFLAGS="-Iwindows/ -Iwindows/SDL2"
	SDL_LDFLAGS="-Lwindows/SDL2 -lSDL2 -lSDL2main -lm"
fi
CFLAGS="-Isrc/instead $SDL_CFLAGS"
LDFLAGS="windows/libluajit.a $SDL_LDFLAGS"

i686-w64-mingw32-windres -i windows/resources.rc -o resources.o || exit 1
i686-w64-mingw32-gcc -Wall -O3 src/*.c src/instead/*.c resources.o $CFLAGS $LDFLAGS -mwindows -o reinstead.exe || exit 1
i686-w64-mingw32-strip reinstead.exe

rm -f *.o
