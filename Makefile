all:	reinstead
	
CFLAGS=$(shell pkg-config --cflags sdl2) $(shell pkg-config --cflags luajit) -Isrc/instead -Dunix -Wall -O3
LDFLAGS=$(shell pkg-config --libs sdl2) $(shell pkg-config --libs luajit) -lm

# uncomment for system-wide install
# PREFIX=/usr/local

ifneq ($(PREFIX),)
DATADIR=-DDATADIR=\"$(PREFIX)/share/reinstead\"
install: reinstead
	install -d -m 0755 $(DESTDIR)$(PREFIX)/bin
	install -d -m 0755 $(DESTDIR)$(PREFIX)/share/reinstead
	install -m 0755 reinstead $(DESTDIR)$(PREFIX)/bin
	cp -r data/* $(DESTDIR)$(PREFIX)/share/reinstead
endif

CFILES= \
	src/platform.c \
	src/stb_image.c \
	src/lua-compat.c \
	src/stb_image_resize.c \
	src/stb_truetype.c \
	src/main.c \
	src/gfx.c \
	src/system.c \
	src/instead/idf.c \
	src/instead/lfs.c \
	src/instead/util.c \
	src/instead/cache.c \
	src/instead/instead.c \
	src/instead/tinymt32.c \
	src/instead/list.c \
	src/instead_lib.c

OFILES  := $(patsubst %.c, %.o, $(CFILES))

$(OFILES): %.o : %.c
	$(CC) -c $(<) $(I) $(CFLAGS) $(DATADIR) -o $(@)

reinstead:  $(OFILES)
	$(CC) $(CFLAGS) $(^) $(LDFLAGS) -o $(@)

clean:
	$(RM) -f src/lua/*.o src/*.o src/instead/*.o reinstead
