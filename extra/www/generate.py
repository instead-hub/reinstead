#!/usr/bin/env python3
"""Minimal site generator for RE:INSTEAD games playable with metaparser-js.

The site is built from a directory of games (data/games by default). A game is
published when its directory contains main3.lua and icon.png:

    games/<name>/main3.lua     title, author and short info come from the
                               $Name, $Author and $Info header fields, the
                               (ru) variants win
    games/<name>/icon.png      card and page image
    games/<name>/dsc.txt       optional, long description, may contain simple
                               HTML

The result is a static site in build/: index.html with the game cards, a page
per game, games/<name>/<name>.zip archives (ready for metaparser-js) and a copy
of the metaparser-js distribution in mp/.

Usage:
    make -C extra/metaparser-js          # build metaparser-js first
    python3 extra/www/generate.py        # then generate the site
    python3 -m http.server -d extra/www/build
"""

import argparse
import html
import re
import shutil
import sys
import zipfile
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

SKIP_FILES = {"autoscript"}
SKIP_DIRS = {"saves"}

HEADER_TAGS = {"name": "Name", "author": "Author", "info": "Info", "version": "Version"}


def field_rx(field, ru=False):
    tag = HEADER_TAGS[field]
    suffix = r"\(ru\)" if ru else r"(?!\()"
    return re.compile(rf"\${tag}{suffix}\s*:\s*([^$]*?)\s*\$?\s*$")


def parse_header(path):
    """Title, author and info from the main3.lua header fields; the (ru)
    variants win."""
    meta = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines()[:50]:
        if not line.strip():
            continue
        if not line.lstrip().startswith("--"):
            break
        for field in HEADER_TAGS:
            for ru in (True, False):
                key = field + ("_ru" if ru else "")
                if key in meta:
                    continue
                m = field_rx(field, ru).search(line)
                if m:
                    meta[key] = m.group(1).strip()
    for field in HEADER_TAGS:
        value = meta.get(field + "_ru") or meta.get(field, "")
        if value:
            meta[field] = value.replace("\\n", "\n").replace("\\t", "\t")
    return meta


def read_optional(path, default=""):
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="replace").strip()
    return default


def make_zip(game_dir, zip_path, name):
    """Game archive with <name>/ as the top level directory, as metaparser-js
    expects for <name>.zip."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(game_dir.rglob("*")):
            rel = path.relative_to(game_dir)
            if rel.parts[0] in SKIP_DIRS or path.name in SKIP_FILES:
                continue
            if path.is_file():
                z.write(path, f"{name}/{rel.as_posix()}")


def esc(text):
    return html.escape(text, quote=True)


TEMPLATES = {}


def render(template, **kw):
    if template not in TEMPLATES:
        path = HERE / "templates" / template
        TEMPLATES[template] = Template(path.read_text(encoding="utf-8"))
    return TEMPLATES[template].substitute(**kw)


def text_html(text):
    """Paragraphs from a plain text description."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return "\n".join(f"<p>{esc(p)}</p>" for p in parts)


def page(title, body, depth):
    return render("page.html", title=esc(title), css="../" * depth + "style.css", body=body)


def card_html(game):
    return render("card.html",
                  name=esc(game["name"]),
                  title=esc(game["title"]),
                  author=esc(game["author"]),
                  info=esc(game["info"]))


def game_page(game):
    if game["dsc"]:
        about = f'<div class="dsc">\n{game["dsc"]}\n</div>'
    else:
        about = text_html(game["info"])
    body = render("game.html",
                  name=esc(game["name"]),
                  title=esc(game["title"]),
                  author=esc(game["author"]),
                  about=about)
    return page(f"Игра «{game['title']}»", body, 2)


def index_page(games):
    cards = "\n".join(card_html(g) for g in games)
    body = render("index.html", cards=cards)
    return page("МЕТАПАРСЕР: интерактивная литература", body, 0)


def load_games(games_dir):
    games = []
    for game_dir in sorted(games_dir.iterdir()):
        main = game_dir / "main3.lua"
        icon = game_dir / "icon.png"
        if not game_dir.is_dir() or not main.is_file() or not icon.is_file():
            continue
        meta = parse_header(main)
        title = meta.get("name") or game_dir.name
        dsc = read_optional(game_dir / "dsc.txt")
        games.append({
            "name": game_dir.name,
            "dir": game_dir,
            "meta": meta,
            "title": title,
            "author": meta.get("author", ""),
            "info": meta.get("info", ""),
            "dsc": dsc,
        })
    return games


def main():
    ap = argparse.ArgumentParser(description="Generate a minimal RE:INSTEAD games site.")
    ap.add_argument("--games", type=Path, default=ROOT / "data/games",
                    help="directory with the games (default: data/games)")
    ap.add_argument("--mp", type=Path, default=ROOT / "extra/metaparser-js/build/dist",
                    help="metaparser-js distribution (default: extra/metaparser-js/build/dist)")
    ap.add_argument("--out", type=Path, default=HERE / "build",
                    help="output directory (default: extra/www/build)")
    args = ap.parse_args()

    games_dir = args.games.resolve()
    mp_dir = args.mp.resolve()
    out = args.out.resolve()

    if not (mp_dir / "index.html").is_file():
        sys.exit(f"metaparser-js is not built: {mp_dir}\n"
                 f"run: make -C extra/metaparser-js")
    if not games_dir.is_dir():
        sys.exit(f"no games directory: {games_dir}")
    if out == Path("/") or out == ROOT:
        sys.exit(f"refusing to clean {out}")

    games = load_games(games_dir)
    if not games:
        sys.exit(f"no games with main3.lua and icon.png in {games_dir}")

    shutil.rmtree(out, ignore_errors=True)
    (out / "games").mkdir(parents=True)
    shutil.copytree(mp_dir, out / "mp")
    shutil.copyfile(HERE / "style.css", out / "style.css")
    shutil.copyfile(HERE / "compass-logo.png", out / "compass-logo.png")
    (out / "index.html").write_text(index_page(games), encoding="utf-8")

    for game in games:
        d = out / "games" / game["name"]
        d.mkdir(parents=True)
        shutil.copyfile(game["dir"] / "icon.png", d / "icon.png")
        make_zip(game["dir"], d / f"{game['name']}.zip", game["name"])
        (d / "index.html").write_text(game_page(game), encoding="utf-8")
        print(f"{game['name']}: {game['title']} — {game['author']}")

    print(f"\n{len(games)} game(s) in {out}")
    print(f"serve it with: python3 -m http.server -d {out}")


if __name__ == "__main__":
    main()
