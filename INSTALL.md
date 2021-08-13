# Linux/BSD

Requirements:
- sdl2 (required);
- luajit (recommended).

## Without luajit

Look into make-default.sh script and try it: $ ./make-default.sh

```
CFLAGS="`pkg-config --cflags sdl2` -Isrc/lua -Isrc/instead -Dunix"
LDFLAGS="`pkg-config --libs sdl2` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS $LDFLAGS -o reinstead
```

Then run: ./reinstead

## With luajit

Try: $ ./make-luajit.sh

```
CFLAGS="`pkg-config --cflags sdl2` `pkg-config --cflags luajit` -Isrc/instead -Dunix"
LDFLAGS="`pkg-config --libs sdl2` `pkg-config --libs luajit` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c $CFLAGS $LDFLAGS -o reinstead
```

Also, you can check Makefile and try: $ make

Then run: ./reinstead

## System-wide install

For simplicity RE:INSTESAD is designed to be run from it's own subdirectory. But
you can define DATADIR to select data directory. Check Makefile PREFIX
commented line.


```
$ make PREFIX=/usr/local
$ make PREFIX=/usr/local DESTDIR=/ install
```

# Plan9/9front

```
$ mk
$ reinstead
```
