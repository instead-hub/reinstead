</$objtype/mkfile

# Build file for the bundled Lua (../../src/lua): the instead-cli mkfile
# copies it there as mkfile and runs mk. It is the mkfile of the 9front
# Lua port, so the feature defines below are the ones used there; the
# library is built in place as liblua.a.

LIB=liblua.a

OFILES=\
     lzio.$O\
     lctype.$O\
     lopcodes.$O\
     lmem.$O\
     lundump.$O\
     ldump.$O\
     lstate.$O\
     lgc.$O\
     llex.$O\
     lcode.$O\
     lparser.$O\
     ldebug.$O\
     lfunc.$O\
     lobject.$O\
     ltm.$O\
     lstring.$O\
     ltable.$O\
     ldo.$O\
     lvm.$O\
     lapi.$O\
     lauxlib.$O\
     lbaselib.$O\
     lcorolib.$O\
     ldblib.$O\
     liolib.$O\
     lmathlib.$O\
     loadlib.$O\
     loslib.$O\
     lstrlib.$O\
     ltablib.$O\
     lutf8lib.$O\
     linit.$O\
    

UPDATE=\
    mkfile\
    $HFILES\
    ${OFILES:%.$O=%.c}\
    ${LIB:/$objtype/%=/386/%}\

</sys/src/cmd/mksyslib

CC=pcc
LD=pcc
CFLAGS= -c -I. -D_C99_SNPRINTF_EXTENSION -D_POSIX_SOURCE \
        -D_SUSV2_SOURCE -DLUA_POSIX -DENABLE_CJSON_GLOBAL \
        -DMAKE_LIB -DPlan9

%.$O: %.c
    $CC $CFLAGS $stem.c

install:V:
    cp liblua.a /$objtype/lib/ape/liblua.a
    cp lauxlib.h /sys/include/ape/lauxlib.h
    cp lua.h /sys/include/ape/lua.h
    cp luaconf.h /sys/include/ape/luaconf.h
    cp lualib.h /sys/include/ape/lualib.h 
    @{
        mk -f mkfile_bin install
    }

clean:V:
    rm -f *.[$OS]

nuke:V:
    rm -f $LIB
    rm -f /$objtype/lib/ape/liblua.a
    rm -f $HFILES
    @{
        mk -f mkfile_bin nuke
    }
