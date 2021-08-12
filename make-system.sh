PFX="/usr/local"
CFLAGS="`pkg-config --cflags sdl2` `pkg-config --cflags luajit` -Isrc/instead -Dunix"
LDFLAGS="`pkg-config --libs sdl2` `pkg-config --libs luajit` -lm"

gcc -Wall -O3 src/*.c src/instead/*.c $CFLAGS $LDFLAGS -DDATADIR=\"$PFX/share/reinstead\" -o reinstead || exit 1

echo "Success!"
echo "Make from root to install:"
echo "# cp reinstead $PFX/bin && cp -R data/ $PFX/share/reinstead"

rm -f *.o
