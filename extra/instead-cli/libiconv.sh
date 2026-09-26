#!/bin/sh
# Build GNU libiconv for mingw-w64 as a static library in external/.
#
# mingw-w64 itself ships no iconv, so instead-cli uses its own static copy:
# external/include/iconv.h and external/lib/libiconv.a (see Makefile.mingw).
# The external/.stamp file marks a good build, the tarball is kept for reuse.
set -eu

ver="${libiconv_ver:-1.19}"
dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$dir"

tarball="libiconv-$ver.tar.gz"
sum="88dd96a8c0464eca144fc791ae60cd31cd8ee78321e67397e25fc095c4a19aa6"

if [ ! -f "$tarball" ]; then
	wget -q "https://ftp.gnu.org/pub/gnu/libiconv/$tarball" -O "$tarball"
fi
echo "$sum  $tarball" | sha256sum -c - || {
	echo "Checksum mismatch: $tarball" >&2
	rm -f "$tarball"
	exit 1
}

rm -rf "libiconv-$ver"
tar xf "$tarball"
cd "libiconv-$ver"

./configure --host=i686-w64-mingw32 --prefix="$dir/external" \
	--enable-static --disable-shared --disable-nls
make -j"$(nproc)"
make install

cd ..
rm -rf "libiconv-$ver"
touch external/.stamp
echo "libiconv $ver installed into external/"
