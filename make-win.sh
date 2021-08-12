CFLAGS="-Isrc/instead -Iwindows/"
LDFLAGS="windows/libluajit.a -Lwindows/SDL2 -lSDL2 -lSDL2main -lm"
i686-w64-mingw32-gcc -Wall -O3 src/*.c src/instead/*.c $CFLAGS $LDFLAGS -mwindows -o reinstead.exe
rm -f *.o
