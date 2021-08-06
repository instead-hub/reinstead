CFLAGS="`pkg-config --cflags sdl2` `pkg-config --cflags luajit` -Isrc/instead -D__linux__ -Dunix"
LDFLAGS="`pkg-config --libs sdl2` `pkg-config --libs luajit`"
gcc -Wall -c -O3 src/*.c src/instead/*.c $CFLAGS && \
gcc *.o $LDFLAGS -lm -o instead-lite
rm -f *.o

