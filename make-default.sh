CFLAGS="`pkg-config --cflags sdl2` -Isrc/lua -Isrc/instead -Dunix"
LDFLAGS="`pkg-config --libs sdl2` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS $LDFLAGS -o reinstead
rm -f *.o
