CFLAGS="-Isrc/instead -Iwindows/"
LDFLAGS="windows/libluajit.a -Lwindows/SDL2 -lSDL2 -lSDL2main"
i686-w64-mingw32-gcc -Wall -O3 src/*.c src/instead/*.c $CFLAGS $LDFLAGS -mwindows -lm -o reinstead.exe
rm -f *.o
