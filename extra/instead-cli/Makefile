# instead-cli: Linux build.
#
# The client is built with the bundled Lua (../../src/lua), so no LuaJIT is
# required; only the C library and -lm.

CC ?= gcc

BUILD := build/linux

CFLAGS  += -Dunix -D_HAVE_ICONV
LDFLAGS += -lm

include Makefile.common
