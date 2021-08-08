CFLAGS="`pkg-config --cflags sdl2` -Isrc/lua -Isrc/instead -Dunix"
LDFLAGS="`pkg-config --libs sdl2`"
gcc -Wall -c -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS && \
gcc *.o $LDFLAGS -lm -o reinstead
rm -f *.o
