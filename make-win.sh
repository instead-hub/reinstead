CFLAGS="-Isrc/instead -Iwindows/"
LDFLAGS="windows/libluajit.a -Lwindows/SDL2 -lSDL2 -lSDL2main -lm"

i686-w64-mingw32-windres -i windows/resources.rc -o resources.o || exit 1
i686-w64-mingw32-gcc -Wall -O3 src/*.c src/instead/*.c resources.o $CFLAGS $LDFLAGS -mwindows -o reinstead.exe || exit 1
i686-w64-mingw32-strip reinstead.exe

rm -f *.o
