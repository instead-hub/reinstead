# AGENTS.md

RE:INSTEAD: minimal INSTEAD parser-game player. C engine (`src/`, SDL2/SDL3), game logic and parser in Lua (`data/`). Games live in `data/games/<name>/`, entry file `main3.lua` (archive/urzi use `main3-ru.lua` / `main3-en.lua` selected via `@lang`).

## Build

- `make` — default (LuaJIT + SDL2 via pkg-config). SDL3: `make SDLVER=sdl3` (pkg-config `sdl3`).
- `./make-default.sh` — bundled Lua (`src/lua`), no LuaJIT; `SDLVER=sdl3 ./make-default.sh` for SDL3. Also `./make-tcc.sh`, `make WITH_FREETYPE=1`, `make WITH_SCHRIFT=1`.
- Platform: `src/platform_sdl.c` holds the SDL-shared part and includes `src/sdl2/platform.c` or `src/sdl3/platform.c` (`-DUSE_SDL3` selects SDL3). `src/platform.h` is the only platform header. Plan9 (`src/plan9/platform.c`) is standalone.
- `./clean.sh` or `make clean`; binary is `./reinstead`.
- Build artifacts (`*.o`, `reinstead`, `data/settings`) are untracked — never commit them.
- CI (`.github/workflows/CI.yml`) only builds variants; it does not run tests.

## Tests (headless)

- `./tests/run-parser-tests.sh` (needs a built `./reinstead`; override with `BIN=...`). Runs parser unit checks (`tests/parser-tests`) and golden diffs (`tests/match-dump/golden.txt` = `mp:match` snapshots, `golden-compl.txt` = `mp:compl`; `tests/noun-forms/golden.txt` = noun declension forms).
- Single test game directly:
  `SDL_VIDEODRIVER=dummy ./reinstead -appdata "$(mktemp -d)" -noautosave "$PWD/tests/parser-tests"`
- Golden regeneration is only for intentional parser behavior changes: run the dump game directly (it writes `out.txt` / `out-compl.txt` next to `tests/match-dump/main3.lua`), then copy them to `golden*.txt`. The noun forms golden is regenerated the same way (`tests/noun-forms/out.txt` → `golden.txt`). To validate a refactor, compare against a previous `mp.lua`: `git show <rev>:data/stead3/parser/mp.lua` swapped in, run the dump, `diff`.

## Running games / autoscripts

- Pass the game directory as an absolute path; relative `games/trial` fails with "Can not detect game format":
  `SDL_VIDEODRIVER=dummy ./reinstead -appdata /tmp/x -noautosave /work/data/games/trial -i /work/data/games/trial/autoscript`
- `-i` script is opened relative to CWD (use an absolute path). CLI options are parsed in `data/core/core.lua`: positional = game dir, plus `-i`, `-appdata`, `-noautosave`, `-debug`, `-scale`, `-tts`, `-noautoload`.
- Autoscript = one player command per line; lines starting with `!`/`/` are system commands (`!game`, `!script`, `!restart`, `!font`, `!quit`, ...). `data/games/autoscript` is an orchestrator over all games, not a game.
- `dict.mrd` beside a game is a generated, tracked cache; the engine regenerates it when sources change, so it can appear modified after runs.

## Parser (`data/stead3/parser/`)

- `mp.lua` (core: input, tokens, match, completion, actions), `mplib.lua` (standard verbs, scope/visibility), `mp-ru.lua` / `mp-en.lua` (language layer: messages, `Verb{...}`, morphology). Games `require "parser/mp-ru"` (or `mp-en`).
- `mp:match` is decomposed into helpers (`find_alternative`, `disambiguate`, `slot_hit/varg/missing/optional`, `accept_descriptor`, `rank_matches`, `drop_extra`, `finalize`). `mp:debug_match` prints match details; its call is commented out inside `mp:match`.
- `Verb{ ..., prio = N }` sets verb priority; patterns are compiled at registration into `d.compiled`; `{token}` slots still expand at parse time.
- Hot-path invariants — preserve unless you have a golden + benchmark: `mp:noun_forms` caches per-object word forms (invalidated by `ob.word` change; dynamic `word`/`raw_word` functions are not cached); `first_char` memo + first-char prefilters in `find_alternative` / `lookup_verb` / `lookup_noun` / `disambiguate` (exact mode only — fuzzy matching needs all candidates); `std.obj:has` memoizes attribute parsing; `mp:trace` / `mp:traceinside` use one growing list; `visible()` / `access()` are inlined without closures. Do not cache results keyed on mutable scene state (e.g. darkness) without invalidating on move/attr.
- Tests run inside the engine: `init()` is global context (`std.game` is nil, `p()` raises "Call from global context"). Use `std.mod_start` for game logic or stub side effects with `std.rawset(mp, 'xaction', ...)`.

## Game DSL gotchas

- Words: `obj { -"камень,валун"; ... }` — comma = aliases, `|` = separate names, `/` = grammatical hints (`-"пёс,собака/мр,од,жив"`).
- Attributes are set with `:attr 'container,open'`; a plain field `container = true` does NOT set an attribute.
- Rooms are lit by default; `:attr '~light'` makes a room dark.

## Workflow

- Work on branch `opencode`, commits authored as `opencode <opencode@localhost>`; do not commit without explicit confirmation.
- Comments in `data/stead3/parser/` are English.
