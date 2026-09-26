#/bin/bash
set -e

test -d dist/metaparser || mkdir -p dist/metaparser

for d in parser morph; do 
	cp -r ../../data/stead3/"$d" dist/metaparser
done

for d in theme modules games main3.lua theme.ini README COPYING; do 
	cp -r $d dist/metaparser
done

#cd doc && make && cd ..

#mkdir -p release/metaparser/doc

#cp doc/*.pdf doc/*.md release/metaparser/doc
