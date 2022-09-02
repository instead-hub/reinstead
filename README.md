![Build status](https://github.com/instead-hub/reinstead/actions/workflows/CI.yml/badge.svg)

# RE:INSTEAD

Минималистичный плеер парсерных игр INSTEAD для Linux, Windows, Plan9 и Android.

- [МАНИФЕСТ](MANIFEST.md)
- [INSTALL](INSTALL.md)
- [INSTEAD](https://instead.hugeping.ru)
- [МЕТАПАРСЕР](https://instead.hugeping.ru/page/metaparser/)

[<img src="https://fdroid.gitlab.io/artwork/badge/get-it-on.png"
	alt="Get it on F-Droid" height="80">](https://f-droid.org/en/packages/ru.hugeping.reinstead/)

# Параметры

- [путь к каталогу с игрой] -- запустить игру;
- [-debug] -- запуск в режиме разработки игры (отладочная информация);
- [-scale f] -- задать масштаб;
- [-i autoscript] -- выполнять команды из файла;
- [-tts] -- запуск с tts.

# Клавиатура

- esc - краткая помощь;
- ctrl-+/-/0 - изменить размер шрифта;
- ctrl-a/home - в начало строки;
- ctrl-e/end - конец строки;
- ctrl-u/k - очистить строку;
- ctrl-w - удалить последнее слово;
- ctrl-n/pagedown - страница вперёд;
- ctrl-p/pageup - страница назад;
- пробел - листание многостраничного вывода;
- вверх/вниз - история команд;
- влево/вправо - навигация по строке ввода.

# Некоторые внутриигровые команды

- заново;
- сохранить/загрузить [необязательное имя];
- помощь.

# Системные команды

- !info - информация;
- !restart - перезапустить;
- !save [необязательное имя] - сохранить;
- !load [необязательное имя] - загрузить;
- !saves - список сохранений;
- !rm [необязательное имя] - удалить сохранение;
- !font <размер> - размер шрифта;
- !tts - включить/выключить TTS;
- !quit - выход.

Обратите внимание на восклицательный знак в начале системных команд!

# Конфигурация

См. файл data/core/config.lua.

# Расширения для программ экранного доступа (Windows)

Пользователи программ экранного доступа могут установить расширения,
которые повышают удобство использования RE:INSTEAD:

* [Дополнение для NVDA](https://tseykovets.ru/download/nvda/reinstead.nvda-addon)

* [Скрипты для JAWS](https://tseykovets.ru/download/jaws/reinstead.zip)

------

<img src="scr/archive.png" width="50%">

<img src="scr/moon9.png" width="50%">

<img src="scr/list.png" width="50%">

<img src="scr/plan9.png" width="50%">
