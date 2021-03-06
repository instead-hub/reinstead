# Linux/BSD

Requirements:
- sdl2 (required);
- luajit (recommended).

## Without luajit

Look into simple make-default.sh script and try it.

```
$ ./make-default.sh
```

```
CFLAGS="`sdl2-config --cflags` -Isrc/lua -Isrc/instead -Dunix"
LDFLAGS="`sdl2-config --libs` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c src/lua/*.c $CFLAGS $LDFLAGS -o reinstead
```

Then run.

```
$ ./reinstead
```

## With luajit

Try simple make-luajit.sh script.

```
$ ./make-luajit.sh
```

```
CFLAGS="`pkg-config --cflags sdl2` `pkg-config --cflags luajit` -Isrc/instead -Dunix"
LDFLAGS="`pkg-config --libs sdl2` `pkg-config --libs luajit` -lm"
gcc -Wall -O3 src/*.c src/instead/*.c $CFLAGS $LDFLAGS -o reinstead
```

Also, you can check Makefile and try it.
```
$ make
```

Then run.

```
$ ./reinstead

```

## With freetype

You can build reinstead with freetype instead of stb_truetype.
```
$ make WITH_FREETYPE=1
```

## With libschrift

You can build reinstead with libschrift (bundled) instead of stb_truetype.
```
$ make WITH_SCHRIFT=1
```

## System-wide build and install

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

# Windows

Use binary releases or install mingw and try:

```
$ ./make-win.sh
```

# Android

Use binary releases or F-Droid or try build yourself:

```
$ cd contrib/android
$ ./gradlew downloadDependencies
$ ./gradlew installDebug
```
