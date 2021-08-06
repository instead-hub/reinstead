CFLAGS="-Isrc/instead -Iwindows/"
LDFLAGS="windows/libluajit.a -Lwindows/SDL2 -lSDL2 -lSDL2main"

i686-w64-mingw32-gcc -Wall -c -O3 src/*.c src/instead/*.c $CFLAGS && \
i686-w64-mingw32-gcc *.o $LDFLAGS -mwindows -lm -o instead-lite.exe
rm -f *.o
