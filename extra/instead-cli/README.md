# instead-cli

Trivial INSTEAD interpreter for developers. It lives in the reinstead
tree and is built with the bundled Lua (src/lua), so no external LuaJIT
is required.

## Build and run

Linux:

```
$ make
$ make run GAME=../../data/games/trial
```

Windows (mingw-w64, static):

```
$ make -f Makefile.mingw
```

`make dist` builds both clients and assembles the runnable tree in
`build/dist` (the Windows cross build needs mingw-w64):

```
build/dist/instead-cli       Linux client
build/dist/instead-cli.exe   Windows client
build/dist/stead/            runtime tree
```

The clients look for `stead/` next to the executable on Windows and in the
current directory elsewhere, so run them from `build/dist`.

`make stead` assembles the runtime tree into `stead/`: `tiny.lua` plus the
stead3 layer taken from `../../data/stead3`. `make run` builds the binary
and the tree and starts the given game.

iconv is used for codepage conversion when available. It comes with the C
library on Linux; mingw-w64 has none, so the Windows client works in UTF-8
(`-cp65001`) unless built with `make -f Makefile.mingw ICONV=1`.

System wide setup (changing STEADPATH needs a rebuild):

```
$ make clean
$ make STEADPATH=/usr/local/share/instead-cli/
$ sudo make install DESTDIR=/ BIN=/usr/local/bin STEADPATH=/usr/local/share/instead-cli/
```

### 9front (Plan9) build

```
% mk
% mk install
```

`mkfile` builds the client from the same tree sources, `mk install` copies
the runtime to `/sys/games/lib/instead` and the client to `/$objtype/bin`.
The bundled Lua is built in place with `mkfile.lua`, the mkfile of the
9front Lua port.

## Run

./instead-cli <gamedir path>

To pass internal command to STEAD use '/' prefix. Some internal commands:

* /save filename
* /load filename
* /quit
* /inv
* /look

Options:

* -d - debug mode;
* -dfile - debug mode + write stderr to file;
* -wnum - line width is num symbols (70 by default);
* -iscript - read script line by line and use it as commands;
* -lfile - write all input commands to file;
* -cpCODEPAGE - Win only (1251 by default), use 65001 for UTF-8;
* -a - autosave on exit and autoload on start (autosave file);
* -x - execute lua script;
* -e - echo input command;
* -m - enable multimedia output;
* -mcmd - enable run cmd on multimedia. Examples: -m/usr/bin/xdg-open (Linux), -m/bin/plumb (Plan9), -m"start\"\"" (Windows).

## Links

* https://instead.hugeping.ru
* https://parser.hugeping.ru
* http://instead-games.ru
