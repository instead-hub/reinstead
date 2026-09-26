--$Name: Urzi / Урзи$
--$Name(ru): Урзи$
--$Version: 1.05$
--$Author: Антон Жучков (fireton)$
--$Info:Маленькая кошачья история.$

require "fmt"
obj {
	nam = '@lang';
	act = function(s, t)
		gamefile('main3-'..t..'.lua', true)
	end;
}
room {
	nam = 'main';
	title = function(s)
		if std.rawget(_G, 'LANG') == 'ru' then
			p [[Выбор языка]]
		else
			p [[Select language]]
		end
	end;
	decor = [[- {@lang ru|Русский}^
	- {@lang en|English}]];
}
