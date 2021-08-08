CFLAGS="`pkg-config --cflags sdl2` -Isrc/lua -Isrc/instead -Dunix -DSDL_DISABLE_IMMINTRIN_H -DSTBI_NO_SIMD"
LDFLAGS="`pkg-config --libs sdl2`"
tcc -Wall -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS $LDFLAGS -lm -o reinstead
rm -f *.o
