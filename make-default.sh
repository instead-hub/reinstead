CFLAGS="`pkg-config --cflags sdl2` -Isrc/lua -Isrc/instead -D__linux__ -Dunix"
LDFLAGS="`pkg-config --libs sdl2`"
gcc -Wall -c -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS && \
gcc *.o $LDFLAGS -lm -o instead9
rm -f *.o
