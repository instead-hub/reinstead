CFLAGS="`pkg-config --cflags sdl2` `pkg-config --cflags luajit` -Isrc/instead -Dunix"
LDFLAGS="`pkg-config --libs sdl2` `pkg-config --libs luajit` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c $CFLAGS $LDFLAGS -o reinstead
rm -f *.o
