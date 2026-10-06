# mise: внутреннее устройство транспилятора

Документ для разработчиков компилятора `.mise` → `main3.lua`.
Пользовательский синтаксис — в `SPEC.md`, здесь — как всё устроено внутри.

## Конвейер

```
parse_source          текст .mise → Block (AST)
apply_includes        prepend include-файлов (stdlib)
prescan               ids, типы, поля, сигнатуры, inline-функции, события
transpile (main loop) обход корневых элементов → Emitter → Lua
```

Вход — `extra/mise/mise.py` (тонкий CLI) → `miselib/transpile.py:transpile()`.
Ключевое требование: при рефакторингах компилятора сгенерированный Lua
остаётся **байт-идентичным** (проверяется `tests/run-mise-tests.sh`).

## AST (`common.py`)

- `Text` — строка (`"..."`, `[[...]]`); `Bare` — голое значение;
  `Num`, `Bool`, `Nil` — литералы;
- `Lua` — сырое тело `|lua`; `Logic` — разобранное тело `|`;
- `Data` — сырое `{...}`/`[...]` (табличные значения полей);
- `Raw` — `` `выражение` `` (сырой Lua);
- `Block.items: [(key, value)]` — блок; `Block.get/all`.

Хелперы: `parse_key` (ключ + `(параметры)`), `split_key` (разделение по
первому `:`), `split_list` (список верхнего уровня), `parse_scalar`,
`read_bracket`, `read_long`, `strip_comment`, `reindent`, `lua_str`.
Ошибки: `Error` — общая, `LintError` — ошибка разбора/логики,
`TypeCheckError(LintError)` — несовместимость типов (важно для `say`,
см. ниже).

## Разбор (`parse.py`, `logicparse.py`)

`parse_source` → `parse_block` (отступы; `key: value`, `-`-списки,
`|`-блоки, `{...}`) → `pipe_value` для `|`/`|lua` и
`parse_logic` для тел `|`: `return`/`pass`/`stop`, `if/elseif/else`,
`for`, прочие `stmt`.

## Состояние (`state.py:Ctx`)

| поле | смысл |
|---|---|
| `ids` | имена объявленных объектов/тегов (`_'имя'`) |
| `vars` | доступные имена (globals/const + Lua-локали из `require`) |
| `funcs` | вызываемые имена: `fns` + игровые Lua-функции + `_` |
| `fns`, `fn_sigs` | объявленные `fn`: имена и `(plist, ret, variadic)` |
| `global_types` | типы `const:`/`global:` (выводятся `literal_type`) |
| `event_names`, `extra_events` | стандартные + объявленные события |
| `inline` | inline-функции: `name -> (kind, payload)` (см. ниже) |
| `types` | типы-перечисления: `name -> {values, negate}` |
| `fields` | `obj/класс -> {поле: (тип, is_ref)}` |
| `current_owner` | класс/именованный объект, чьё тело сейчас эмитится (для `s.field`) |
| `src_dir` | каталог игры (для `include`/`require`) |

Константы: `TYPES` (примитивы: obj/str/num/bool/any/event/tbl),
`PARAM_TYPES` (типы обработчиков по имени параметра: `s/w/wh` → obj и
т.п.), `KEYWORDS`, `USE_RE`.

## Prescan (`prescan.py`)

Порядок вызовов из `prescan()`:

1. `collect_types` — `type`/`extend_type` → `ctx.types` (значения и
   `~`-отрицание).
2. `collect_ids` — декларации и теги, включая вложенные `with`.
3. `collect_field_types` — `ctx.fields`; `collect_block_fields` рекурсивно
   по `with`; у классов поля наследуются; тип поля — `literal_type`
   (`typing.py`), у голого имени-объекта — `obj` + флаг `is_ref`;
   затем `check_bare_names` сверяет голые значения тем же правилом в
   `patch`, `setup`/`hero`/`game` и `const`/`global` (без типизации).
4. Регистрация `event_decl` в `extra_events`.
5. `collect_game_defs`/`scan_required` — поиск функций/переменных в
   `|lua` и подключаемых Lua-файлах (чтобы `fn` и `use` не конфликтовали
   с игровым кодом).
6. Цикл по `fn`:
   - `parse_fn_sig(key, set(ctx.types))` — сигнатура (типы, `T?`, `...`);
   - inline-эвристики: `Raw`-тело → expr; вариадическое Lua-тело и
     `adapter_callee` → call/meth; одиночный вызов (`wrapper_template`) →
     wrap. Повторное использование параметра, `...`, `fn_` и `use`
     запрещают инлайн.
7. `const`/`global` → `global_types` через `literal_type`.
8. `walk_use` — имена из `use ...` выкидываются из `inline`, кроме
   `expr` (expr-функцию нельзя использовать как обработчик).
9. `check_refs` — `with`/`inside`/`found_in` сверяются с `ctx.ids`;
   прочие поля-ссылки (`REF_FIELDS`: `n_to`, `door_to`, …) проверяет
   `Emitter.obj` через `check_ref_value(..., ctx.ids)`.

## Inline-функции

`ctx.inline[name] = (kind, payload)`:

| kind | тело `|lua` | вызов превращается в |
|---|---|---|
| `wrap` | один вызов/`return вызов` | подстановка шаблона (`_wrap_params`) |
| `expr` | одно выражение (`fn len(v: tbl) -> num:` `` `#v` ``) | `(подставленное выражение)` |
| `call` | `return f(a, b, ...)` (вариадическая) | `f(args)` |
| `meth` | `return s:m(a, ...)` (первый параметр — приёмник) | `args[0]:m(остальные)` |

Всё инлайнится на месте вызова и **не эмитится**; `fn_call` — единая
точка диспатча. Проверки аргументов идут по `fn_sigs` до подстановки.
Если inline-функцию упомянули в `use`, её вызовы не инлайнятся, а тело
эмитится как обычная `fn_`-функция (кроме `expr` — ошибка).

## Типы (`typing.py`)

- `base(t)` — база `T?`.
- `type_ok(ctx, t, exp)` — совместимость: `any` только с `any`/без
  ожидания; `T?` принимает `T` и `nil`; перечисления совместимы с `str`.
- `type_value_error` — проверка значений перечислений (`values`,
  `~`-отрицание при `negate`, подсказки `difflib`).
- `literal_type(ctx, node, refs=False)` — AST-литерал → тип; при
  `refs=True` голое имя резолвится как объект (`ctx.ids`), событие
   (`ctx.event_names`) или значение перечисления (`ctx.enum_values`);
   нерезолвнутое голое имя в поле (`obj`/класс, `patch`, `setup`,
   `const`/`global`) — ошибка (строки — `Text`).

`obj`-значения: явное `_'имя'` (бэкtick) резолвится при загрузке;
поле-ссылка (`other_kitten: none`) хранит строку-имя, а **чтения**
оборачиваются в `_(...)` — движок резолвит имя в рантайме (forward
ссылки безопасны). Тип переменных стабилен: первое конкретное
присваивание фиксирует тип, дальше — только совместимое.

## Компиляция выражений (`expr.py`)

- `lex_lua` — токены логики.
- `_wrap_params` — подстановка аргументов в шаблон через плейсхолдеры
  (простые аргументы без скобок, сложные — в скобках).
- `ExprEmit` — рекурсивный разбор: `primary` (литералы, имена,
  `_'id'`, `fn`, переменные, ожидаемые `event`/перечисления), `postfix`
  (`.поле` с типами из `ctx.fields` и `_(...)`-обёрткой, `[индекс]`,
  `:метод`, вызовы; у `obj?`-приёмника без сужения — ошибка), операторы
  (`+ - * / .. and or not ==`, `^`
  запрещён, `#` — только `#тег`), автовызовы нуль-арных `fn`.
- `arglist`/`check` — проверка арности и типов; несовместимость —
  `TypeCheckError`.
- `no_paren_call` — «сырой текст» аргументов (`say привет`): фолбэк в
  текстовый литерал **только на ошибках разбора**; типовые ошибки
  пробрасываются.
- `transpile_exprlist`, `transpile_stmt` (`local`, присваивания и
  стабильность типов, `+=`/`-=`, разворачивание lhs для полей-ссылок),
  `transpile_for`.

## Логика (`emitlogic.py`)

`emit_logic` обходит `Logic`: `return` (проверка возврата через
`type_ok`), `stmt`, `for`, `if`. Условия компилируются
`transpile_cond`: цепочки `and` режутся `split_and`, `or` — `split_or`
(короткое замыкание: части после `X or` видят сужение от «X ложно»),
а `cond_narrow` сужает типы простых имён (`if o:`, `== nil`, `~= nil`,
`not o`); `else` одиночного `if` получает обратное сужение.

## Эмиссия (`emit.py:Emitter`)

- `value`/`body`/`handler`/`on` — значения, тела, обработчики
  (в т.ч. составные ключи `before A, B`).
- `obj`/`decl` — объекты и классы-экземпляры: `words`, `attrs`
  (с проверкой enum `attr`), `dict` → `:dict {...}` в tail, вложенные
  `with`/`inside`, пресеты (`PRESETS`), `:attr`/`:disable()`.
- `cls`/`obj` — owner-контекст `ctx.current_owner` (класс или именованный
  объект) на время эмиссии тела: даёт типизацию `s.field` в
  обработчиках.
- `verb` — только `Verb {...}`: `tag/words/patterns/prio/hint`;
  `on`/`before`/`after` внутри `verb` — ошибка (действия в `event`).
- `event` — `on:` → `mp.Имя`, `before`/`after` → `mp.before_/after_Имя`.
- `patch` — обработчики/поля существующего объекта; `dict:` особый.
- `setup` — `dsc`, `hero`, `init`, `start`, `game`, `take`, `fmt`.
- `const`/`glob`, `talk`, `verb_extend`.

## Основной цикл (`transpile.py`)

`header` (meta), `type`/`extend_type` пропускаются, `require` → префикс
`require`, `lua` → как есть, `class`/`fn` (тела `fn` собираются и
вставляются перед остальным; inline пропускаются), `patch`/`setup`/
`const`/`global`/`event_decl`/`decl`/`verb`/`extend`/`talk` → эмиттеры.
В конце — `require "parser/mp-<lang>"` и `require` из `require:`.

## Инварианты и грабли

- Байт-идентичность Lua при рефакторингах — главный сторож
  (`tests/run-mise-tests.sh`, фаза A).
- Голые имена в объявлениях — **строки**; менять на `_'имя'` нельзя
  (forward-ссылки: `_'bar'` вычисляется при загрузке, комнаты ещё нет).
- `{...}` в логике запрещены; таблицы — из `fn ... |lua` (`tbl`) или
  полей-`Data`; длина — `len()` (`#` — только тег).
- `events:` удалён: `event Имя:` регистрирует событие (при необходимости
  с действием); `verb` без обработчиков.
- `say`-фолбэк не должен глотать типовые ошибки (см. `TypeCheckError`).
- Class-scoped типизация `s.field` работает только для приёмника с
  именем `s`.
- При добавлении новой конструкции: `classify` → `prescan`
  (сбор) → `Emitter` → ветка в `transpile` → `SPEC.md`/`gram.bnf`.

## Тесты

`tests/run-mise-tests.sh` — транспиляция всех `tests/mise-*` и `cmp` с
закоммиченным `main3.lua`; `--engine` дополнительно гоняет оригинал и
конверсию на одном автоскрипте и сравнивает транскрипты (у wtell учтена
известная строка финала, у alice — случайность демонов/порядок
перечисления). `tests/run-parser-tests.sh` проверяет движок и в mise не
заглядывает.
