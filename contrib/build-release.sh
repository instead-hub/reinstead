set -eu
sdl_ver="${sdl_ver:-2.24.0}"
freetype_ver="${freetype_ver:-2.12.1}"
luajit_ver="${luajit_ver:-2.0.5}"

# fetch <url> <file> [sha256]
fetch() {
	url="$1"
	file="$2"
	sum="${3:-}"
	if [ ! -f "$file" ]; then
		wget -q "$url" -O "$file"
	fi
	if [ -n "$sum" ]; then
		echo "$sum  $file" | sha256sum -c - || {
			echo "Checksum mismatch: $file" >&2
			rm -f "$file"
			exit 1
		}
	fi
}

# checksums of the pinned tarballs (update when versions change)
case "$sdl_ver" in
	2.24.0) sdl_sum="91e4c34b1768f92d399b078e171448c6af18cafda743987ed2064a28954d6d97" ;;
	*) sdl_sum="" ;;
esac
case "$freetype_ver" in
	2.12.1) freetype_sum="efe71fd4b8246f1b0b1b9bfca13cfff1c9ad85930340c27df469733bbb620938" ;;
	*) freetype_sum="" ;;
esac
case "$luajit_ver" in
	2.0.5) luajit_commit="0bf80b07b0672ce874feedcc777afe1b791ccb5a" ;; # RELEASE LuaJIT-2.0.5
	*) luajit_commit="" ;;
esac

test -d external || mkdir external

if [ ! -f external/.stamp_SDL2 ]; then
	fetch https://github.com/libsdl-org/SDL/releases/download/release-${sdl_ver}/SDL2-${sdl_ver}.tar.gz SDL2-${sdl_ver}.tar.gz "$sdl_sum"
	rm -rf SDL2-${sdl_ver}

	tar xf SDL2-${sdl_ver}.tar.gz
	cd SDL2-${sdl_ver}
	./configure --prefix=`pwd`/../external/ --disable-shared --enable-static --disable-audio --disable-pthreads --disable-threads --disable-joystick --disable-sensor --disable-power --disable-haptic --disable-filesystem --disable-file --disable-video-vulkan --disable-video-opengl --disable-video-opengles2 --disable-video-vivante --disable-video-cocoa --disable-video-metal --disable-render-metal --disable-video-kmsdrm --disable-video-opengles --disable-video-opengles1 --disable-video-opengles2 --disable-video-vulkan --disable-render-d3d --disable-sdl2-config
	make -j"$(nproc)" && make install
	cd ..

	rm -rf SDL2-${sdl_ver}

	tar xf SDL2-${sdl_ver}.tar.gz
	cd SDL2-${sdl_ver}
	./configure --prefix=`pwd`/../external/windows/ --host=i686-w64-mingw32 --enable-shared --enable-static --disable-audio --disable-pthreads --disable-threads --disable-joystick --disable-sensor --disable-power --disable-haptic --disable-filesystem --disable-file --disable-video-vulkan --disable-video-opengl --disable-video-opengles2 --disable-video-vivante --disable-video-cocoa --disable-video-metal --disable-render-metal --disable-video-kmsdrm --disable-video-opengles --disable-video-opengles1 --disable-video-opengles2 --disable-video-vulkan --disable-render-d3d --disable-sdl2-config
	make -j"$(nproc)" && make install
	cd ..
	rm -rf SDL2-${sdl_ver}
	touch external/.stamp_SDL2
fi

if [ ! -f external/.stamp_freetype2 ]; then
	fetch https://download.savannah.gnu.org/releases/freetype/freetype-${freetype_ver}.tar.gz freetype-${freetype_ver}.tar.gz "$freetype_sum"
	rm -rf freetype-${freetype_ver}

	tar xf freetype-${freetype_ver}.tar.gz
	cd freetype-${freetype_ver}
	./configure --prefix=`pwd`/../external/  --disable-shared --enable-static --without-brotli --without-harfbuzz --without-png --without-bzip2 --without-zlib --without-pthread
	make -j"$(nproc)" && make install
	cd ..
	rm -rf freetype-${freetype_ver}
	tar xf freetype-${freetype_ver}.tar.gz
	cd freetype-${freetype_ver}

	./configure --prefix=`pwd`/../external/windows/ --host=i686-w64-mingw32 --disable-shared --enable-static --without-brotli --without-harfbuzz --without-png --without-bzip2 --without-zlib
	make -j"$(nproc)" && make install
	cd ..
	rm -rf freetype-${freetype_ver}
	touch external/.stamp_freetype2
fi

if [ ! -f external/.stamp_luajit ]; then
	rm -rf LuaJIT-${luajit_ver}
	git clone -q --single-branch --branch v2.0 https://github.com/LuaJIT/LuaJIT.git LuaJIT-${luajit_ver}
	cd LuaJIT-${luajit_ver}
	if [ -n "$luajit_commit" ]; then
		git checkout -q "$luajit_commit"
		test "$(git rev-parse HEAD)" = "$luajit_commit" || {
			echo "LuaJIT commit mismatch" >&2
			exit 1
		}
	fi
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
	rm -rf LuaJIT-${luajit_ver}
	touch external/.stamp_luajit
fi

# ls -laR external

rm -f src/gfx_font.c # build with freetype

## linux version

gcc -Wall -O3 -Wl,-Bstatic \
-Iexternal/include \
-Iexternal/include/freetype2 \
-Iexternal/include/SDL2 \
-Isrc/instead \
src/*.c src/instead/*.c src/freetype/*.c \
-Lexternal/lib/ \
-D_REENTRANT -Dunix -Wl,--no-undefined \
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
cp -r reinstead.exe data/ COPYING ChangeLog windows/Tolk/*.dll external/windows/bin/*.dll release/

mkdir release/doc
cp doc/*.md MANIFEST.md README.md release/doc

i686-w64-mingw32-strip release/SDL2.dll
mkdir release/licenses
cp windows/Tolk/*.txt release/licenses
cp COPYING release/licenses
