set -eu
sdl_ver="${sdl_ver:-3.4.16}"
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
	3.4.16) sdl_sum="7322236cd12090c3eb40b9728be4d49c76f66ad17d04369584d4ecad5cf77c68" ;;
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

sdl_subsystems="-DSDL_AUDIO=OFF -DSDL_CAMERA=OFF -DSDL_JOYSTICK=OFF -DSDL_HAPTIC=OFF -DSDL_HIDAPI=OFF -DSDL_POWER=OFF -DSDL_SENSOR=OFF"

if [ ! -f external/.stamp_SDL3 ] || [ ! -f external/include/SDL3/SDL.h ] || [ ! -f external/windows/include/SDL3/SDL.h ]; then
	fetch https://github.com/libsdl-org/SDL/releases/download/release-${sdl_ver}/SDL3-${sdl_ver}.tar.gz SDL3-${sdl_ver}.tar.gz "$sdl_sum"
	rm -rf SDL3-${sdl_ver} sdl3-linux sdl3-win

	tar xf SDL3-${sdl_ver}.tar.gz

	cmake -S SDL3-${sdl_ver} -B sdl3-linux \
		-DCMAKE_BUILD_TYPE=Release \
		-DCMAKE_INSTALL_PREFIX=`pwd`/external \
		-DSDL_SHARED=OFF -DSDL_STATIC=ON \
		-DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF -DSDL_INSTALL_TESTS=OFF \
		$sdl_subsystems
	cmake --build sdl3-linux -j"$(nproc)"
	cmake --install sdl3-linux

	cmake -S SDL3-${sdl_ver} -B sdl3-win \
		-DCMAKE_SYSTEM_NAME=Windows \
		-DCMAKE_C_COMPILER=i686-w64-mingw32-gcc \
		-DCMAKE_CXX_COMPILER=i686-w64-mingw32-g++ \
		-DCMAKE_RC_COMPILER=i686-w64-mingw32-windres \
		-DCMAKE_FIND_ROOT_PATH=/usr/i686-w64-mingw32 \
		-DCMAKE_FIND_ROOT_PATH_MODE_PROGRAM=NEVER \
		-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=ONLY \
		-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY \
		-DCMAKE_BUILD_TYPE=Release \
		-DCMAKE_INSTALL_PREFIX=`pwd`/external/windows \
		-DSDL_SHARED=OFF -DSDL_STATIC=ON \
		-DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF -DSDL_INSTALL_TESTS=OFF \
		$sdl_subsystems
	cmake --build sdl3-win -j"$(nproc)"
	cmake --install sdl3-win

	rm -rf SDL3-${sdl_ver} sdl3-linux sdl3-win
	touch external/.stamp_SDL3
fi

if [ ! -f external/.stamp_freetype2 ] || [ ! -f external/include/freetype2/ft2build.h ] || [ ! -f external/windows/include/freetype2/ft2build.h ]; then
	fetch https://downloads.sourceforge.net/project/freetype/freetype2/${freetype_ver}/freetype-${freetype_ver}.tar.gz freetype-${freetype_ver}.tar.gz "$freetype_sum"
	rm -rf freetype-${freetype_ver}

	tar xf freetype-${freetype_ver}.tar.gz
	cd freetype-${freetype_ver}
	./configure --prefix=`pwd`/../external/  --disable-shared --enable-static --without-brotli --without-harfbuzz --without-png --without-bzip2 --without-zlib --without-pthread
	make -j"$(nproc)"
	make install
	cd ..
	rm -rf freetype-${freetype_ver}
	tar xf freetype-${freetype_ver}.tar.gz
	cd freetype-${freetype_ver}

	./configure --prefix=`pwd`/../external/windows/ --host=i686-w64-mingw32 --disable-shared --enable-static --without-brotli --without-harfbuzz --without-png --without-bzip2 --without-zlib
	make -j"$(nproc)"
	make install
	cd ..
	rm -rf freetype-${freetype_ver}
	touch external/.stamp_freetype2
fi

if [ ! -f external/.stamp_luajit ] || [ ! -f external/lib/libluajit.a ] || [ ! -f external/windows/lib/libluajit.a ]; then
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
-Isrc/instead \
-DUSE_SDL3 \
src/*.c src/instead/*.c src/freetype/*.c \
-Lexternal/lib/ \
-D_REENTRANT -Dunix -Wl,--no-undefined \
-lSDL3 \
-lluajit \
-lfreetype \
-Wl,-Bdynamic \
-lm -ldl -lc -lpthread \
-o reinstead
strip reinstead

## Windows version

CFLAGS="-Isrc/instead -Iexternal/windows/include -Iexternal/windows/include/freetype2 -DUSE_SDL3"
# static SDL3 pulls in the windows system libraries, see sdl3.pc
LDFLAGS="-Lexternal/windows/lib -lSDL3 -lm -lluajit -lfreetype -lkernel32 -luser32 -lgdi32 -lwinmm -limm32 -lole32 -loleaut32 -lversion -luuid -ladvapi32 -lsetupapi -lshell32"

i686-w64-mingw32-windres -i windows/resources.rc -o resources.o || exit 1

i686-w64-mingw32-gcc -Wall -static -O3 $CFLAGS src/*.c src/instead/*.c src/freetype/*.c resources.o $LDFLAGS -mwindows -o reinstead.exe || exit 1
i686-w64-mingw32-strip reinstead.exe
rm -f *.o

## make release

rm -rf release
mkdir release

cp reinstead release/reinstead.x86-64.linux
cp -r reinstead.exe data/ COPYING ChangeLog windows/Tolk/*.dll release/

mkdir release/doc
cp doc/*.md MANIFEST.md README.md release/doc

mkdir release/licenses
cp windows/Tolk/*.txt release/licenses
cp COPYING release/licenses
