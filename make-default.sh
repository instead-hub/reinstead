CFLAGS="`sdl2-config --cflags` -Isrc/lua -Isrc/instead -Dunix"
LDFLAGS="`sdl2-config --libs` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS $LDFLAGS -o reinstead
rm -f *.o
