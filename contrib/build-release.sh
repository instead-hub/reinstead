set -e
test -z "$sdl_ver" && sdl_ver="2.24.0"
test -z "$freetype_ver" && freetype_ver="2.12.1"
test -z "$luajit_ver" && luajit_ver="2.0.5"

test -d external || mkdir external

if [ ! -f external/.stamp_SDL2 ]; then
	test -f SDL2-${sdl_ver}.tar.gz || wget https://github.com/libsdl-org/SDL/releases/download/release-${sdl_ver}/SDL2-${sdl_ver}.tar.gz
	rm -rf SDL2-${sdl_ver}

	tar xvf SDL2-${sdl_ver}.tar.gz
	cd SDL2-${sdl_ver}
	./configure --prefix=`pwd`/../external/ --disable-shared --enable-static --disable-audio --disable-pthreads --disable-threads --disable-joystick --disable-sensor --disable-power --disable-haptic --disable-filesystem --disable-file --disable-video-vulkan --disable-video-opengl --disable-video-opengles2 --disable-video-vivante --disable-video-cocoa --disable-video-metal --disable-render-metal --disable-video-kmsdrm --disable-video-opengles --disable-video-opengles1 --disable-video-opengles2 --disable-video-vulkan --disable-render-d3d --disable-sdl2-config
	make && make install
	cd ..

	rm -rf SDL2-${sdl_ver}

	tar xvf SDL2-${sdl_ver}.tar.gz
	cd SDL2-${sdl_ver}
	./configure --prefix=`pwd`/../external/windows/ --host=i686-w64-mingw32 --enable-shared --enable-static --disable-audio --disable-pthreads --disable-threads --disable-joystick --disable-sensor --disable-power --disable-haptic --disable-filesystem --disable-file --disable-video-vulkan --disable-video-opengl --disable-video-opengles2 --disable-video-vivante --disable-video-cocoa --disable-video-metal --disable-render-metal --disable-video-kmsdrm --disable-video-opengles --disable-video-opengles1 --disable-video-opengles2 --disable-video-vulkan --disable-render-d3d --disable-sdl2-config
	make && make install
	cd ..
	touch external/.stamp_SDL2
fi

if [ ! -f external/.stamp_freetype2 ]; then
	test -f freetype-${freetype_ver}.tar.gz || wget https://download.savannah.gnu.org/releases/freetype/freetype-${freetype_ver}.tar.gz
	rm -rf freetype-${freetype_ver}

	tar xvf freetype-${freetype_ver}.tar.gz
	cd freetype-${freetype_ver}
	./configure --prefix=`pwd`/../external/  --disable-shared --enable-static --without-brotli --without-harfbuzz --without-png --without-bzip2 --without-zlib --without-pthread
	make && make install
	cd ..
	rm -rf freetype-${freetype_ver} && tar xvf freetype-${freetype_ver}.tar.gz && cd freetype-${freetype_ver}
	# CC=i686-w64-mingw32-gcc AR=i686-w64-mingw32-ar LD=i686-w64-mingw32-ld HOSTCC=gcc 
	./configure --prefix=`pwd`/../external/windows/ --host=i686-w64-mingw32 --disable-shared --enable-static --without-brotli --without-harfbuzz --without-png --without-bzip2 --without-zlib
	make && make install
	cd ..
	touch external/.stamp_freetype2
fi

if [ ! -f external/.stamp_luajit ]; then
	test -f LuaJIT-${luajit_ver}.tar.gz || wget https://luajit.org/download/LuaJIT-${luajit_ver}.tar.gz
	rm -rf LuaJIT-${luajit_ver}

	tar xf LuaJIT-${luajit_ver}.tar.gz
	cd LuaJIT-${luajit_ver}
	make DEFAULT_CC="gcc" BUILDMODE=static V=1
	cp src/libluajit.a ../external/lib/
	for f in lua.h luaconf.h lualib.h lauxlib.h; do
		cp src/$f ../external/include/
	done
	make clean
	make CROSS=i686-w64-mingw32- HOST_CC="gcc -m32" TARGET_SYS=Windows BUILDMODE=static
	for f in lua.h luaconf.h lualib.h lauxlib.h; do
		cp src/$f ../external/windows/include/
	done
	cp src/libluajit.a ../external/windows/lib/
	cd ..
	touch external/.stamp_luajit
fi

rm -f src/gfx_font.c # build with freetype

## linux version

gcc -Wall -O3 -Wl,-Bstatic \
-Iexternal/include \
-Iexternal/include/freetype2 \
-Iexternal/include/SDL2 \
src/*.c src/instead/*.c src/freetype/*.c \
-Lexternal/lib/ \
-D_REENTRANT -I/usr/include/luajit-2.1 -Isrc/instead -Dunix -Wl,--no-undefined \
-lSDL2 \
-lluajit \
-lfreetype \
-Wl,-Bdynamic \
-lm -ldl -lc \
-o reinstead
strip reinstead

## Windows version

CFLAGS="-Isrc/instead -Iexternal/windows/include -Iexternal/windows/include/SDL2 -Iexternal/windows/include/freetype2"
LDFLAGS="-Lexternal/windows/lib -lSDL2.dll -lSDL2main -lm -lluajit -lfreetype"

i686-w64-mingw32-windres -i windows/resources.rc -o resources.o || exit 1

i686-w64-mingw32-gcc -Wall -static -O3 $CFLAGS src/*.c src/instead/*.c src/freetype/*.c resources.o $LDFLAGS -mwindows -o reinstead.exe || exit 1
i686-w64-mingw32-strip reinstead.exe
rm -f *.o

## make release

rm -rf release
mkdir release

cp reinstead release/reinstead.x86-64.linux
cp -r reinstead.exe data/ doc/ COPYING ChangeLog windows/Tolk/*.dll external/windows/bin/*.dll release/
i686-w64-mingw32-strip release/SDL2.dll
mkdir release/licenses
cp windows/Tolk/*.txt release/licenses
cp COPYING release/licenses
