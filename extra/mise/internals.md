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
`when/default` (сахар в тот же `if`-AST), `for`, прочие `stmt`.

## Состояние (`state.py:Ctx`)

| поле | смысл |
|---|---|
| `ids` | имена объявленных объектов/тегов (`_'имя'`) |
| `vars` | доступные имена (globals/const + Lua-локали из `require`) |
| `funcs` | вызываемые имена: `fns` + игровые Lua-функции + `_` |
| `fns`, `fn_sigs` | объявленные `fn`: имена и `(plist, ret, variadic)` |
| `global_types` | типы `const:`/`global:` (выводятся `literal_type`) |
| `event_names` | значения `type event` (stdlib) + `event X:` |
| `inline` | inline-функции: `name -> (kind, payload)` (см. ниже) |
| `types` | типы-перечисления: `name -> {values, negate}` |
| `fields` | `obj/класс -> {поле: (тип, is_ref)}` |
| `current_owner` | класс/именованный объект, чьё тело сейчас эмитится (для `s.field`) |
| `src_dir` | каталог игры (для `include`/`require`) |

Константы: `TYPES` (примитивы: obj/str/num/bool/any/event/tbl),
`PARAM_TYPES` (типы обработчиков по имени параметра: `s/w/wh` → obj и
т.п.), `KEYWORDS`, `USE_RE`.

## Prescan (`prescan.py`, `proptypes.py`, `inline.py`)

Порядок вызовов из `prescan()`:

1. `collect_types` — `type`/`extend_type` → `ctx.types` (значения и
   `~`-отрицание); `_register_props` — `props:` → `ctx.props`/`prop_params`
   (+ref-поля); значения полей проверяются по типам, имена fn-параметров
   дают env тел, `ref`/`tbl[ref]` — ref-проверки.
2. `collect_ids` — декларации и теги, включая вложенные `with`;
   `ctx.id_kind` (имя → вид/класс).
3. `collect_field_types` — `ctx.fields`; `collect_block_fields` рекурсивно
   по `with`; у классов поля наследуются; тип поля — `literal_type`
   (`typing.py`), у голого имени-объекта — `obj` + флаг `is_ref`;
   `ctx.mixins` — именованные наборы, `attach_mixins` вливает их
   поля в цель до собственных; `check_bare_names` проверяет и цель
   `impl` (объект/класс/`game`/`@…`);
   затем `check_bare_names` сверяет голые значения тем же правилом в
   `impl`, `setup`/`hero`/`game` и `const`/`global` (без типизации).
4. `ctx.ref_fields` — `refs:`/`extend refs:`; `event_names` —
   значения типа `event` (stdlib) + `event X:`.
5. `collect_game_defs`/`scan_required` — поиск функций/переменных в
   `|lua` и подключаемых Lua-файлах (чтобы `fn` и `use` не конфликтовали
   с игровым кодом).
6. Цикл по `fn`:
   - `parse_fn_sig(key, set(ctx.types) | ctx.classes)` — сигнатура
     (типы, классы, `T?`, `...`);
   - inline-эвристики: `Raw`-тело → expr; вариадическое Lua-тело и
     `adapter_callee` → call/meth; одиночный вызов (`wrapper_template`) →
     wrap. Повторное использование параметра, `...`, `fn_` и `use`
     запрещают инлайн.
7. `const`/`global` → `global_types` через `literal_type`.
8. `walk_use` — имена из `use ...` выкидываются из `inline`, кроме
   `expr` (expr-функцию нельзя использовать как обработчик).
9. `check_refs` — `with`/`inside`/`found_in` сверяются с `ctx.ids`;
   прочие поля-ссылки (`ctx.ref_fields` из `refs:`) проверяет
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

Функции с хвостовыми optional-параметрами инлайнятся только как адаптер
(`call`/`meth`, `adapter_callee(..., full=True)` — тело пересылает все
параметры позиционно); вызов разворачивается с фактическим числом
аргументов (`w:noun()` → `w:noun()`). `wrap`/`expr` для них отключены
(`_wrap_params` не умеет пропускать аргументы); non-adapter тело эмитится
обычной `fn_`-функцией, отсутствующие аргументы — `nil`.

## Типы (`typing.py`)

- `Prop`/`named_fn` — разбор типов свойств (`ref`, `tbl[ref]`, `fn(s: obj)
  -> T`) и env тел; `Prop.ret` уходит в `emit_logic` через `body_type`
  (`ref`→`obj`, `tbl[ref]`→`tbl[obj]`); `base(t)` — база `T?`;
  `tbl_inner(t)` — внутренний тип `tbl[T]`
  (`""` у `tbl[]`, None у `tbl`); `split_union`/`union_parts` —
  альтернативы `T|U` верхнего уровня (вне `fn(...)`/`tbl[...]`), канон —
  сортировка + один `?`.
- `type_ok(ctx, t, exp)` — совместимость: `any` только с `any`/без
  ожидания; `T?` принимает `T` и `nil`; union — любая альтернатива
  ожидания и все альтернативы значения; перечисления совместимы с `str`;
  `tbl[A]`→`tbl[B]` поэлементно, `tbl[A]`→`tbl` да, `tbl`→`tbl[A]` нет,
  `tbl[]` (пустой) совместим с любым `tbl[B]`; `tbl[any]` ≡ `tbl`.
- `check_ref_list` (`proptypes`) — элементы `tbl[ref]`-props: `Bare`/`Text`
  сверяются с `ctx.ids`; `check_ref_value(..., allow_text=True)` — тот же
  backstop на эмиссии для безымянных объектов (`-`-список даёт `Text`).
- `type_value_error` — проверка значений перечислений (`values`,
  `~`-отрицание при `negate`, подсказки `difflib`).
- `canon_type`/`type_error` — канонизация и валидация аннотаций
  (в т.ч. `fn(...) -> T`); `canon_fn_sig` — подпись объявленной `fn`,
  `fn_type_parts` — разбор подписи для проверок и вызовов значений.
- `literal_type(ctx, node, refs=False)` — AST-литерал → тип; при
  `refs=True` голое имя резолвится как объект (`ctx.ids`), событие
   (`ctx.event_names`) или значение перечисления (`ctx.enum_values`);
   нерезолвнутое голое имя в поле (`obj`/класс, `impl`, `setup`,
   `const`/`global`) — ошибка (строки — `Text`).

`obj`-значения: явное `_'имя'` (бэкtick) резолвится при загрузке;
поле-ссылка (`other_kitten: none`) хранит строку-имя, а **чтения**
оборачиваются в `_(...)` — движок резолвит имя в рантайме (forward
ссылки безопасны). Тип переменных стабилен: первое конкретное
присваивание фиксирует тип, дальше — только совместимое.

## Компиляция выражений (`exprparse.py`, API `expr.py`, лексер `lex.py`)

- `lex.py:lex_lua` — токены логики (`LEX_FORMS` — таблица сканеров).
- `_wrap_params` — подстановка аргументов в шаблон через плейсхолдеры
  (простые аргументы без скобок, сложные — в скобках).
- `ExprEmit` — рекурсивный разбор в узлы `Node`/`Lit`/`Ref`/`Field`/
  `Index`/`Call` (`code` + тип `t`; у `Ref` — имя и признак объекта, у
  `Field` — владелец/имя/признак ссылки и сырой lhs для распаковки);
  голое имя резолвит единый `name_ref` (env → объект → fn → игровая fn
  → глобал; политики `zero_call` для хвостового аргумента метода и
  `funcs` для primary);
  `primary` (литералы, имена, `_'id'`, `fn`, переменные, ожидаемые
  `event`/перечисления; голые значения enum/событий — по уникальности;
  `return`/`stop` без значения и `false`/`nil` не проверяются по типу
  возврата (`emit_logic`);
  `{ e1, e2 }` — список: элементы под ожидаемый `tbl[T]`, тип
  `tbl[T1|T2...]`, пустой — `tbl[]`/`tbl[T]`; числовой литерал,
  объявленный значением enum-альтернативы (`2` ∈ `gram`), типизируется
  ею, если `num` не принимается),
  `postfix` (`.поле` с типами из `ctx.fields` и
  `_(...)`-обёрткой, `[индекс]` — тип элемента `tbl[T]`, `:метод`,
  вызовы; у `obj?`-приёмника без сужения — ошибка), `&имя` — fn-значение для колбэков; операторы
  (`+ - * / .. and or not ==`, `^` запрещён, `#` — только `#тег`),
  автовызовы нуль-арных `fn`.
- `arglist`/`check` — проверка арности и типов; несовместимость —
  `TypeCheckError`.
- `no_paren_call` — «сырой текст» аргументов (`say привет`): фолбэк в
  текстовый литерал **только на ошибках разбора**; типовые ошибки
  пробрасываются.
- `transpile_exprlist`, `transpile_stmt` (`local`, присваивания и
  стабильность типов, `+=`/`-=`, разворачивание lhs для полей-ссылок),
  `transpile_for` (аннотации переменных цикла — `for _, w: obj in …`).

## Логика (`emitlogic.py`)

`emit_logic` обходит `Logic`: `return` (проверка возврата через
`type_ok`), `stmt`, `for`, `if`. Условие разбирается `condast.py` в
дерево `and`/`or` с листьями-срезами исходного текста (глубина,
кавычки, `[[...]]`); `transpile_cond` обходит дерево: листья уходят в
обычный парсер выражений, а `narrow_assume` по токенам листа сужает
типы простых имён (`if o:`, `== nil`, `~= nil`, `not o`). `and` даёт
истинное сужение следующим частям, `or` — ложное (короткое
замыкание); `else` одиночного `if` получает обратное сужение.

## Эмиссия (`emit.py:Emitter`)

- `expand_mixins` — ключи привязанных `mixins` вливаются до
  собственных ключей (свои перекрывают); конфликт двух mixins — ошибка.
- `value`/`body`/`handler`/`on` — значения, тела, обработчики
  (в т.ч. составные ключи `before A, B`; фаза обязательна: `on X` —
  метод события (`X = function…`), `before/after/post/life X` — с префиксом;
  `Any`/`Default` — обычные события с параметрами `s, ev, w`;
  `CURRENT_LINE` — по строке ключа).
- `obj`/`decl` — объекты и классы-экземпляры: `words`, `attrs`
  (с проверкой enum `attr`), `dict` → `:dict {...}` в tail, вложенные
  `with`/`inside`, пресеты (`PRESETS`), `:attr`/`:disable()`.
- `cls`/`obj` — owner-контекст `ctx.current_owner` (класс или именованный
  объект) на время эмиссии тела: даёт типизацию `s.field` в
  обработчиках.
- `verb` — только `Verb {...}`: `tag/words/patterns/prio/hint`;
  `on`/`before`/`after` внутри `verb` — ошибка (действия в `event`).
- `event` — `on:` → `mp.Имя`, `before`/`after` → `mp.before_/after_Имя`;
  у `Any`/`Default` параметры по умолчанию `s, ev, w, wh`.
- `impl` — обработчики/поля существующего объекта; плоские
  `before/after/post/life X` как у объекта; owner-контекст, если цель есть в
  `ctx.fields` (тогда `s.field` типизируется); `dict:` особый.
- `setup` — `dsc`, `hero`, `init`, `start`, `game`, `take`, `fmt`.
- `const`/`glob`, `talk`, `verb_extend`.

## Основной цикл (`transpile.py`)

`header` (meta), `type`/`extend_type` пропускаются, `require` → префикс
`require`, `lua` → как есть, `class`/`fn` (тела `fn` собираются и
вставляются перед остальным; inline пропускаются), `impl`/`setup`/
`const`/`global`/`event_decl`/`decl`/`verb`/`extend`/`talk` → эмиттеры.
В конце — `require "parser/mp-<lang>"` и `require` из `require:`.

## Реестры (точки расширения)

Ветвления «по виду» сведены в таблицы: новый вид — это запись в таблице
плюс маленький обработчик, а не правка цепочки `if`.

| Что | Таблица | Файл |
|---|---|---|
| вид значения → форма | `VALUE_FORMS` | emit.py |
| форма `key: value` (предикат + reader) | `VALUE_FORMS` | parse.py |
| вид объявления → эмиттер | `DECL_FORMS`, `NAMED_DECLS` | emit.py, transpile.py |
| ключи `setup` | `SETUP_FORMS`, `SETUP_BLOCKS` | emit.py |
| поля `talk` | `TALK_FORMS` | emit.py |
| ключи объекта, эмитящиеся отдельно | `OBJ_SKIP_KEYS` | emit.py |
| вид декларации в `classify` | `SIMPLE_KINDS`, `TAGGED_FORMS`+`TAGGED_NAMES` | decl.py |
| пресеты объявлений | `PRESETS` | decl.py |
| регистрация `type`/`extend_type` | `TYPE_FORMS` | proptypes.py |
| сбор class/mixin | `DEFS_FORMS` | prescan.py |
| проверка bare-имён | `BARE_FORMS` | prescan.py |
| операторы и приоритеты выражений | `BIN_LEVELS`, `UNARY_OPS`, `STR_ARG_ERRORS` | exprparse.py |
| формы токенов | `LEX_FORMS` | lex.py |
| операторы и виды операторов логики | `LOGIC_CONSTS`, `LOGIC_FORMS` | logicparse.py, emitlogic.py |
| формы типов | `CANON_FORMS`, `BODY_TYPES` | typing.py |
| правила совместимости типов | `SCALAR_RULES` | typing.py |
| тип литерального класса | `LITERAL_TYPES` | typing.py |

## Инварианты и грабли

- Байт-идентичность Lua при рефакторингах — главный сторож
  (`tests/run-mise-tests.sh`, фаза A).
- Голые имена в объявлениях — **строки**; менять на `_'имя'` нельзя
  (forward-ссылки: `_'bar'` вычисляется при загрузке, комнаты ещё нет).
- `{...}` в логике — типизированные литералы `tbl[...]` (элементы под
  ожидание); массивы props можно писать и `-`-списками (элемент может быть
  Long: `- [[...]]`); таблицы также из `fn ... |lua` (`tbl`/`tbl[T]`) или
  полей-`Data`; длина — `len()` (`#` — только тег).
- `events:` удалён: `event Имя:` регистрирует событие (при необходимости
  с действием); `verb` без обработчиков.
- `say`-фолбэк не должен глотать типовые ошибки (см. `TypeCheckError`).
- Class-scoped типизация `s.field` работает только для приёмника с
  именем `s`.
- При добавлении новой конструкции: `classify`
  (`SIMPLE_KINDS`/`TAGGED_FORMS`) → `prescan`
  (`TYPE_FORMS`/`DEFS_FORMS`/`BARE_FORMS`) → `Emitter`/`transpile`
  (`DECL_FORMS`, `SETUP_FORMS`, `TALK_FORMS`, …) → `SPEC.md`/`gram.bnf`.

## Тесты

`tests/run-mise-tests.sh` — транспиляция всех `tests/mise-*` и `cmp` с
закоммиченным `main3.lua`; `--engine` дополнительно гоняет оригинал и
конверсию на одном автоскрипте и сравнивает транскрипты (у wtell учтена
известная строка финала, у alice — случайность демонов/порядок
перечисления). `tests/run-parser-tests.sh` проверяет движок и в mise не
заглядывает.
