# Открытые баги и дыры MISE 2

Только то, что осталось. Исправленное — в истории git и в `SPEC.md`.
Как проверять: `python3 extra/mise/mise.py x.mise -o dir/main3.lua`, затем
`luajit -e "assert(loadfile('dir/main3.lua'))"` и прогон с автокриптом
(`транскрипт` + команда + `!quit`, результат в `dir/log*.txt`).

Тесты на сейчас: `run-mise-tests.sh` 32/32, `run-mise-error-tests.sh` 191/191,
`--engine` 66/66 — всё ниже этими наборами **не** покрыто.

## 1. `lua` не работает в обработчике и в середине тела

Эмиттер умеет тело-`lua` для обработчика (`emitter.py:303`), но чекер требует
`str|bool|fn` (`_HANDLER_VALUE`, `checker.py:64,790`):

```mise
impl game
  before Pull =
    lua
      p("pulled " .. w.nam)
```
→ `p("pulled " .. w.nam): expected str|bool|fn, got any`

Хватает 3 строк в чекере (`is_lua` → `want = None`) — проверено: обработчик
эмиттится как `function(s, w)` и работает, `w` виден.

`lua` не первым в теле — дыра в парсере (`lua` не инструкция, только «всё тело»):

```mise
before Pull =
  say "до"
  lua
    p("x")
  say "после"
```
→ `unexpected token ''`; если `lua` первый, но за ним инструкция —
`expected DEDENT, got 'say'`. То же в обычной `fn`. Нужен узел `LuaStmt`
(`ast_nodes`), ветка в `parse_stmt`, `return s.code` в `emitter._stmt`, `pass` в
`checker._check_stmts` — ~10 строк.

Работает сегодня: `lua` как всё тело `fn`, `before X = &fn`, `lua` на верхнем
уровне. Локальные из `lua` чекеру не видны — так и останется.

## 2. `lua`-блок теряет ведущие комментарии

```mise
fn f() -> num
  lua
    -- этот комментарий пропадёт
    return 1
```
→ в `main3.lua` только `return 1`. `_parse_lua` (`parser.py:299`) режет
`raw_lines` от строки токена `INDENT`, а комментарии токенов не дают. Начинать
от `line + 1` (~3–4 строки).

---

## Что сознательно не делаем

- `extern global` — удалён (был бесполезен, `extern value` покрывает).
  Lua-функции: `extern fn max(a: num, b: num) -> num = "math.max($1, $2)"`.
- Обёртки `floor`/`upper`/`insert`… в `stdlib.mise` — отложены, автор объявляет
  сам одной строкой.
- Порядок объявлений — **не важен**: эмиттер сам выстраивает файл (классы
  топосортом, `impl` последними, `verb` до `extend`/`remove`); цикл
  наследования — ошибка `inheritance cycle`. Тест `tests/mise-order`.
- Невидимые вызовы для полей `T | fn(obj) -> T` — **убраны**. Чтение поля
  отдаёт union как есть: `local d = s.dsc` — поле, `p s.dsc` — что там лежит
  (может быть функция), `local t: str = s.dsc` и `s.dsc .. "!"` — ошибка
  `expected str, got str|bool|fn(obj)->str`. Значение достаётся явно, обёрткой
  в игре (в `stdlib.mise` пока не кладём):

  ```mise
  fn expect_str(s: obj, f: str) -> str?
    lua
      local v = s[f]
      if type(v) == 'function' then v = v(s) end
      if type(v) == 'string' then return v end
      return nil

  fn expect_num(s: obj, f: str) -> num?
    lua
      local v = s[f]
      if type(v) == 'function' then v = v(s) end
      if type(v) == 'number' then return v end
      return nil
  ```

  `if d := expect_str s 'dsc'` → `d: str`. Имя поля здесь — строка, поэтому
  опечатку чекер не поймает; вариант без этого — отдельная обёртка на поле
  (`fn dsc_of(s: obj) -> str?` с `s.dsc` внутри). Работает и через `std.call`
  (короче, но падает на числах). Обёртка вида `expect_val(w: any)` **не**
  вызовет функцию: в неё приходит само значение, без объекта.
