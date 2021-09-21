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
- [-i autoscript] -- выполнять команды из файла.

# Клавиатура

- ctrl-a/home - в начало строки;
- ctrl-e/end - конец строки;
- ctrl-u - очистить строку;
- esc - краткая помощь;
- ctrl-n/pagedown - страница вперёд;
- ctrl-p/pageup - страница назад;
- ctrl-+/- - изменить размер шрифта;
- пробел - листание многостраничного вывода;
- вверх/вниз - история команд;
- влево/вправо - навигация по строке ввода.

# Некоторые команды

- сохранить/загрузить [необязательное имя];
- помощь;
- !restart - перезапустить;
- !font <размер> - размер шрифта;
- !quit - выход.

# Конфигурация

См. файл data/core/config.lua.

------

<img src="scr/archive.png" width="50%">

<img src="scr/moon9.png" width="50%">

<img src="scr/list.png" width="50%">

<img src="scr/plan9.png" width="50%">
