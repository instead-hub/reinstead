--$Name: Doomsday / Судный день$
--$Name(ru): Судный день$
--$Version:0.1$
--$Author:Peter Kosyh$
--$Author(ru):Пётр Косых$
--$Info:A short sketch about a lone cosmonaut.$
--$Info(ru):Короткая зарисовка об одиноком космонавте.$

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
