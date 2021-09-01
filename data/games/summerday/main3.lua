--$Name:Один день лета
--$Version:1.2
--$Author:Пётр Косых$
--$Info:Игра на Инстедоз-6$

require "fmt"
if instead.tiny then
declare 'theme'({})
function theme.name()
	return 'default'
end
else
require "theme"
end
function pic_set()
end

if theme.name() and theme.name():find(".", 1, true) == 1 then
	require "autotheme"
	require "pic"
end

function game:before_Tie(s, wh)
	if not wh then
		p [[К чему?]]
		return
	end
	return false
end

fmt.dash = true
fmt.quotes = true

require 'parser/mp-ru'
pl.description = [[Тебя зовут Серёжа и тебе 8 лет. Это лето ты проводишь
в небольшом городке с бабушкой и дедушкой.]];

Verb {
	"#Wake2";
	"проснуться,просыпаться,просыпайся";
	"Wake";
}

-- уйти к дому
Verb {
	"#WalkOut";
	"уйти,вернуться,вернись,вернусь";
	"~ к {noun}/дт,scene,enterable: Walk";
	"~ на|в {noun}/вн,scene,enterable: Walk";
}

function game:before_Exam(w)
	return game:before_Walk(w)
end

function game:before_Walk(w)
	if have 'compass' then
		return false
	end
	local dir = mp:compass_dir(w)
	if not dir then
		return false
	end
	if dir == 'd_to' or dir == 'u_to' or dir == 'in_to' or dir == 'out_to' then
		return false
	end
	p [[Как ориентироваться по сторонам света без компаса? Ты думаешь, что играешь в текстовую приключенческую игру?]]
end

obj {
	-"компас";
	nam = 'compass';
	description = [[Компас в жёлтом пластиковом корпусе. Тебе купил его дедушка, когда вы гуляли по центру города. У него фосфорная стрелка, её видно в темноте!]];
}

obj {
	nam = '$dir';
	act = function(s, to)
		if not have 'compass' then
			return ''
		end
		return ' (на '..to..')'
	end;
}
-- чтоб можно было писать "на кухню" вместо "идти на кухню"

function mp:pre_input(str)
	local a = std.split(str)
	if #a <= 1 or #a > 3 then
		return str
	end
	if a[1] == 'в' or a[1] == 'на' or a[1] == 'во' or a[1] == "к" or a[1] == 'ко' then
		return "идти "..str
	end
	return str
end

Path = Class {
	['before_Walk,Enter'] = function(s) if mp:check_inside(std.ref(s.walk_to)) then return end; walk(s.walk_to) end;
	before_Default = function(s)
		if s.desc then
			p(s.desc)
			return
		end
		p ([[Ты можешь пойти в ]], std.ref(s.walk_to):noun('вн'), '.');
	end;
	default_Event = 'Walk';
}:attr'scenery,enterable';

Prop = Class {
	before_Default = function(s, ev)
		p ("Тебе нет дела до ", s:noun 'рд', ".")
	end;
}:attr 'scenery'

Careful = Class {
	before_Default = function(s, ev)
		p ("Лучше оставить ", s:it 'вн', " в покое.")
	end;
}:attr 'scenery'

Furniture = Class {
	['before_Push,Pull,Transfer,Take'] = "Пусть лучше стоит там, где {#if_hint/#first,plural,стоят,стоит}.";
}:attr 'static'

room {
	-"сон";
	nam = 'main';
	title = false;
	dsc = false;
	before_Look = [[^^{$fmt c|***}^^{$fmt b|{$fmt c|ОДИН ДЕНЬ ЛЕТА}}^^Во сне ты снова летал.
Раскинув руки, ты парил у самого потолка гостиной комнаты разглядывая
верхушки книжных шкафов и ковёр на полу. Ты был счастлив. Счастлив настолько,
что понял... Это всего лишь сон.^^Тебе пора просыпаться!]];
	before_Default = "Тебе пора просыпаться.";
	before_Wake = function() move(pl,  'bed') end;
	hint_verbs_only = { "#Wake2" };
}

obj {
	nam = 'arrow';
	matches = false;
	fire = false;
	dirty = false;
	-"стрела|рейка";
	each_turn = function(s)
		if s.fire and player_moved() and not here() ^ 'dark3' and not here() ^ 'dark4' then
			p [[Стрела, наконец, погасла.]]
			s.dirty = true
			s.fire = false
			s.matches = false
		end
	end;
	after_Burn = function(s)
		if s.fire then
			p [[Уже горит!]]
			return
		end
		if not s.matches then
			p [[Интересная мысль, но пламя со стрелы собьет поток набегающего воздуха.]]
			return
		end
		p [[Ты поджигаешь спички на конце стрелы и они вспыхивают, одна за другой, ярким голубоватым пламенем.]];
		s.fire = true
	end;
	description = function(s)
		p [[Стрела из деревянной рейки, которую ты смастерил для своего лука.]]
		if s.fire then
			p [[Её наконечник пылает огнём!]]
			return
		end
		if s.matches then
			p [[К её наконечнику привязаны охотничьи спички.]]
			return
		end
		if visited 'goodend1' or s.dirty then
			p [[Наконечник немного обуглился.]]
			return
		end
		if not have 'bow2' then
			p [[Жаль только что лук сломался,
когда Руслан проверял его на прочность.]];
		end
	end;
}

Furniture {
	-"кровать";
	nam = 'bed';
	found_in = 'bedroom';
	description = [[Кровать кажется тебе огромной.]];
	before_LookUnder = function(s)
		if s:once() then
			p [[Под кроватью ты нашёл свою старую стрелу от лука.]]
			take 'arrow'
		else
			return false
		end
	end;
}:attr 'scenery,supporter,enterable'

obj {
	-"одежда|шорты|майка";
	nam = 'clothes';
	init_dsc = [[На полу валяется твоя одежда.]];
	before_Disrobe = function(s)
		if s:hasnt 'worn' then
			return false
		end;
		p [[Зачем раздеваться? Ещё не время спать.]];
	end;
	found_in = 'bedroom';
}:attr 'clothing'

room {
	-"спальня,спальная комната,комната";
	nam = 'bedroom';
	title = 'спальня';
	out_to = '#livingroom';
	Smell = [[Ты чувствуешь запах свежей сдобы.]];
	before_Listen = [[Ты слышишь чириканье воробьёв за окном.]];
	w_to = '#livingroom';
	onexit = function(s)
		if _'clothes':hasnt 'worn' then
			p [[Тебе стоит надеть свою одежду.]]
			return false
		end
	end;
	before_Any = function(s, ev)
		if not pl:inside'bed' then
			return false
		end
		if ev == 'Look' or ev == 'Exam' or ev == 'Exit' or ev == 'GetOff' or ev == 'Sleep' or ev == 'Wake' or ev == 'Walk'
			or ev == 'Jump' or ev == 'JumpOn' then
			return false
		end
		p [[Сначала надо слезть с кровати.]]
	end;
	dsc = function(s)
		if s:once() then
			pn [[Ты открываешь глаза и видишь белые клубы облаков.
А под облаками -- ствол высокой сосны, уходящий прямиком в небо. Некоторое время ты смотришь на
неровную кору, длинные иголки, большие шишки и вспоминаешь...^^
Лето. Ты живёшь у бабушки и дедушки в одноэтажном доме. Прямо напротив окна спальни
растёт сосна, которую ты видишь каждое утро, когда просыпаешься в своей кровати.^]]
		end
		p [[В спальне светло. Широкая кровать занимает почти всё пространство комнаты. Белые гардины колышутся от легкого ветерка. Отсюда ты можешь пройти в гостиную{$dir|запад}.]];
	end;
}: with {
	Careful {
		-"окно|гардины";
		before_Open = "Здесь и так светло и свежо.";
		before_Close = "Лучше пусть будет так, как есть.";
		before_Exam = [[Ты можешь долго наблюдать, как колышутся гардины на сквозняке.]];
	}:attr 'scenery';
	obj {
		-"сосна|шишки/но|иголки|кора";
		before_Exam = [[Интересно, сколько лет этой сосне?]];
		before_Default = [[Сосна находится за окном.]]
	}:attr 'scenery';
	Path {
		nam = '#livingroom';
		-"гостиная";
		walk_to = 'livingroom';
		desc = [[Ты можешь пойти в гостиную.]];
	};
}

obj {
	nam = 'tv';
	-"телевизор";
	['before_Push,Pull,Take,Transfer'] = 'Телевизор слишком тяжёлый.';
	description = function(s)
		if s:has'on' then
			p [[По телевизору идут новости. Скучно.]]
		else
			p [[Черно-белый телевизор с красивым названием "Берёзка".]];
			return false
		end
	end;
	found_in = 'livingroom';
}:attr 'static,switchable'

obj {
	nam = 'wires';
	-"нитки|моток ниток";
	found_in = 'mirror';
	before_Tie = function(s, w)
		if w ^ 'bow' then
			p [[Из ниток не получится крепкая тетива.]]
			return
		end
		return false
	end;
	description = "Моток белых ниток. Незаменимая вещь, когда надо что-нибудь к чему-нибудь привязать.";
}:disable()

Verb {
	"#Tie2";
	"примота/ть",
	"~ {noun}/вн,held к {noun}/дт,held : Tie",
	"~ к {noun}/дт,held {noun}/вн,held : Tie reverse",
}

obj {
	-"зеркало";
	nam = 'mirror';
	description = function(s)
		p [[Зеркало стоит в углу комнаты. Оно очень большое и старинное. Ты любишь разглядывать в нём своё отражение и отражение гостиной.
Просто удивительно, что там всё наоборот. Почему лево и право меняется местами, а верх и низ -- нет?]];
		if disabled 'wires' then
			p [[^^Ты заметил на зеркале моток ниток.]]
			enable 'wires';
		end
	end;
	found_in = 'livingroom';
}:attr 'static,supporter';

Furniture {
	-"диван,щел*";
	found = false;
	description = [[Повидавший многое на своём веку диван стоит у стены напротив телевизора. Его пружины совсем ослабли, но он стал от этого ещё мягче. В щели между обивкой и ручками постоянно проваливаются разные предметы.]];
	found_in = 'livingroom';
	['before_Search,Consult'] = function(s)
		if s.found then
			p [[Больше ничего интересного не находится.]]
			return
		end
		s.found = true
		p [[Ты запустил руку внутрь дивана и пошарил в надежде найти что-нибудь интересное.
Скоро, твоя рука нащупала какой-то небольшой предмет. Ты достал из дивана компас!]];
		take 'compass'
	end;
}:attr 'static,supporter,enterable'

obj {
	nam = 'clock';
	-"часы|маятник";
	num = 1;
	description = [[Старинные часы висят рядом с входом в коридор. Ты любишь смотреть, как равномерно качается маятник и слушать
гулкий бой, который разносится по дому каждый час.]];
	found_in = 'livingroom';
	before_Exam = function(s)
		if s:once() then
			DaemonStart 'clock'
		end
		return false
	end;
	daemon = function(s)
		s.num = s.num + 1
		if s.num > 3 then
			if not here() ^ 'livingroom' then
				p [[Ты слышишь, как из гостиной доносится бой часов.]]
			else
				p [[Ты слышишь, как часы начинают бить.]]
			end
			p (fmt.em([[^Бам! Бам! Бам! Бам! Бам! Бам! Бам! Бам! Бам! ...]]))
			s:daemonStop()
		end
	end;
	before_Default = function(s, ev)
		p ("Лучше оставить ", s:it 'вн', " в покое.")
	end;
}:attr 'static';

obj {
	-"окно|окна|свет";
	nam = 'window';
	description = [[Сквозь окно льётся свет летнего утра.]];
	before_Open = [[Всё и так хорошо. Может быть просто выйти погулять?]];
}:attr 'scenery,openable';

room {
	-"гостиная";
	title = 'гостиная';
	nam = 'livingroom';
	w_to = '#corridor';
	e_to = '#bedroom';
	Smell = [[Ты чувствуешь запах пирожков.]];
	before_Listen = function(s)
		if _'tv':has'on' then
			p [[Ты слышишь голос диктора в телевизоре, но не понимаешь о чём он говорит.]]
		else
			p [[Ты слышишь ход часов.]];
		end
	end;
	dsc = [[Гостиная кажется тебе огромной. Ты можешь пройти в спальню{$dir|восток} или коридор{$dir|запад}.]];
}: with {
	Path {
		-"спальня,спальная";
		nam = '#bedroom';
		walk_to = 'bedroom';
	};
	Path {
		-"коридор";
		nam = '#corridor';
		walk_to = 'corridor';
	};
	'window';
}

room {
	-"коридор";
	title = 'коридор';
	nam = 'corridor';
	e_to = '#livingroom';
	n_to = '#grandroom';
	w_to = '#kitchenroom';
	Smell = [[Ты чувствуешь запах пирожков из кухни.]];
	dsc = [[Из узкого коридора можно попасть в гостиную{$dir|восток}, кухню{$dir|запад} и комнату дедушки{$dir|север}.]];
}: with {
	Path {
		-"гостиная";
		nam = '#livingroom';
		walk_to = 'livingroom'
	};
	Path {
		-"комната дедушки,комната";
		nam = '#grandroom';
		walk_to = 'grandroom';
	};
	Path {
		-"кухня";
		nam = '#kitchenroom';
		walk_to = 'kitchenroom';
		desc = [[Ты можешь пойти на кухню.]];
	};
}

Furniture {
	nam = 'ironbed';
	-"железная кровать,кровать";
	found_in = 'grandroom';
	description = [[Железная кровать дедушки хорошо пружинит. На ней очень здорово прыгать.]];
}:attr 'supporter,enterable';

obj {
	nam = 'news';
	-"газета|Правда";
	found_in = 'table';
	description = [[Газета "Правда" за 15 мая 1986 года.
Ты заметил, что название одной из статей выделено красной ручкой.
^^Выступление М. С. Горбачева по советскому телевидению.^^
"Добрый вечер, товарищи! Все вы знаете, недавно нас постигла беда - авария на Чернобыльской атомной электростанции... Она больно затронула советских людей, взволновала международную общественность. Мы впервые реально столкнулись с такой грозной силой, какой является ядерная энергия, вышедшая из-под контроля."^^Что это значит?]];
	before_Take = [[Не стоит забирать дедушкину газету.]];
}

Furniture {
	nam = 'table';
	-"стол";
	found_in = 'grandroom';
	description = [[Дедушкин стол занимает правую половину комнаты. Он очень старый. В столе есть выдвижной ящик.]];
	['before_Enter,Climb'] = [[Не стоит испытывать стол на прочность.]];
}:attr 'supporter';

Verb {
	"#Pull2";
	"[вы|за]двин/уть,выдви/нуть",
	"{noun}/вн,openable : Pull"
}

Verb {
	"#Push2";
	"задви/нуть",
	"{noun}/вн,openable : Push"
}

obj {
	nam = 'key';
	-"ключ";
	found_in = 'tablebox';
	description = "Это небольшой ключик, который уже начал ржаветь.";
}

obj {
	nam = 'wire';
	-"скрепка,проволока";
	found_in = 'tablebox';
	description = "Обычная канцелярская скрепка из хорошей, тугой проволоки.";
}

obj {
	nam = 'tablebox';
	-"ящик";
	found_in = 'grandroom';
	before_Transfer = function(s)
		if s:has'open' then
			mp:xaction("Close", s)
		else
			mp:xaction("Open", s)
		end
	end;
	before_Pull = function(s) mp:xaction("Open", s) end;
	before_Push = function(s) mp:xaction("Close", s) end;
	after_Open = function(s) p [[Ты выдвинул ящик стола.]]; mp:content(s) end;
	after_Close = [[Ты задвинул ящик стола.]];
	when_open = [[Ящик стола выдвинут.]];
	when_closed = [[Ящик стола задвинут.]];
}:attr'scenery,openable,container';

room {
	-"комната дедушки,комната";
	nam = 'grandroom';
	Smell = [[Ты чувствуешь запах пирожков.]];
	before_Listen = [[Ты слышишь чириканье воробьёв, доносящееся из окна.]];
	title = 'Комната дедушки';
	dsc = [[Дедушки в комнате нет. Наверное, он ушёл на рыбалку.]];
	s_to = '#corridor';
	out_to = '#corridor';
	['before_Jump,JumpOver'] = function(s)
		if pl:inside'ironbed' then
			p [[Ты подпрыгиваешь на пружинной кровати. Раз, два, три! Ух, как здорово! К самому потолку!]];
		else
			p [[На дедушкиной пружинной кровати очень здорово прыгать. Но сначала, нужно на неё залезть.]]
		end
	end;
}: with {
	Path {
		-"коридор";
		nam = '#corridor';
		walk_to = 'corridor';
	};
	'window';
}

Verb {
	"#Walk3";
	"сходи/ть";
	"в {noun}/вн,enterable : Walk";
}

-- идеи:
-- пирожок толстому мальчику за фонарик.
-- ключ -> сарай -> лук из удочки бамбука.
-- стрела -- рейка + целофан + огонь.
-- скрепка -> отмычка
-- в туалете - флакон от шампуня.
-- компас -> просто дают
-- спички нужны
-- враги: паук(огонь), крыса(лук)

global 'pie_nr' (0)

function pl:before_LetGo(s, w)
	if mp:thedark() then
		p [[Не стоит. В темноте не найти потом будет.]]
	else
		return false
	end
end

obj {
	nam = 'pie';
	-"пирожок";
	description = [[Выглядит аппетитно!]];
	before_Touch = "Ещё тёплый.";
	after_Eat = function(s)
		pie_nr = pie_nr - 1
		p "Ты с удовольствием умял бабушкин пирожок."
	end;
}:attr'edible'

obj {
	-"бабушка";
	found_in = 'kitchenroom';
	description = [[Бабушка делает пирожки. Это их запах заполняет весь дом.]];
	before_Kiss = [[-- Осторожно, внучик, мука!]];
	dsc = [[Ты видишь как бабушка делает пирожки.]];
	['before_Say,Ask,Tell'] = function(s, w)
		if w:find("пирож") then
			return s:before_Talk()
		end
		p [[Ты можешь просто {$fmt em|поговорить с бабушкой}.]]
	end;
	['before_Talk'] = function(s)
		if pie_nr == 0 then
			p [[-- Проголодался, наверное? Держи пирожок!]];
			pie_nr = pie_nr + 1
			take 'pie'
		else
			p [[-- Сначала съешь тот, что я тебе уже дала -- улыбается бабушка.]];
		end
	end;
}:attr'animate'

obj {
	-"стол";
	found_in = 'kitchenroom'
}:attr'scenery,supporter':with {
	obj {
		-"пирожки|пирожок";
		description = "Среди них наверняка есть с яйцом и луком -- твои любимые!";
		before_Smell = [[Как пахнет!]];
		['before_Touch,Take,Push,Pull,Transfer,Taste'] = [[Лучше попросить у бабушки.]];
	}:attr'edible';
}

room {
	-"кухня";
	nam = 'kitchenroom';
	Smell = [[Ты чувствуешь, как восхитительно пахнут пирожки.]];
	title = 'Кухня';
	e_to = '#corridor';
	w_to = '#street';
	n_to = '#toilet';
	dsc = function(s)
		if s:once() then
			p [[-- Доброе утро, внучик! -- приветствует тебя бабушка. Ты видишь перед ней на столе ряды свежеиспечённых пирожков.]]
			pn "^"
		end
		p [[На кухне пахнет свежими пирожками. Ты можешь пройти в коридор{$dir|восток}, туалет или выйти на улицу{$dir|запад}.]];
	end;
	out_to = 'street';
}:with {
	Path {
		-"коридор";
		nam = '#corridor';
		walk_to = 'corridor';
	};
	Path {
		-"улица";
		nam = '#street';
		walk_to = 'street';
		desc = [[Ты можешь пойти на улицу.]];
	};
	obj {
		-"туалет";
		nam = '#toilet';
		['before_Walk,Enter'] = function(s)
			if s:once() then
				p [[Ты воспользовался туалетом.]]
			else
				p [[Ты уже был в туалете.]]
			end
		end;
		before_Default = [[Ты можешь сходить в туалет, если хочешь.]];
	}:attr'scenery';
	'window';
}

obj {
	-"сарай";
	nam = 'whouse';
	dsc = [[Напротив дома расположен сарай.]];
	description = function(s)
		p [[В сарае дедушка хранит разный интересный хлам.]]
		if s:hasnt'open' then
			if s:has'locked' then
				p [[Сейчас сарай заперт на ключ.]]
			else
				p [[Сейчас сарай закрыт.]]
			end
		else
			p [[Сейчас сарай открыт.]]
		end
	end;
	with_key = 'key';
	after_Unlock = function(s) s:attr'open' p [[Ты открыл сарай с помощью ключа.]] end;
	after_Lock = function(s) s:attr'~open' p [[Ты запер сарай на ключ.]] end;
	before_Unlock = function(s, w)
		if w ^ 'wire' then
			p [[У дедушки есть ключ. Нет смысла взламывать сарай.]];
			return
		end
		return false
	end;
	found_in = 'street';
	['before_Enter,Climb'] = function(s)
		if s:hasnt'open' then
			if s:has'locked' then
				p [[Сарай заперт на ключ.]]
			else
				p [[Сарай закрыт.]]
			end
			return
		end
		walk 'warehouse'
	end;
}:attr 'static,enterable,openable,lockable,locked';

obj {
	-"цветы/мр|клумбы";
	found_in = 'street';
	description = [[Ты не разбираешься в цветах, но они очень красивые и хорошо пахнут.]];
	before_Take = [[Зачем зря рвать цветы?]];
}:attr'scenery':dict{
	["цветы/вн"] = "цветы";
}

room {
	-"улица";
	nam = 'street';
	title = "На улице";
	Smell = [[Запах цветов кружит тебе голову.]];
	n_to = '#houses';
	s_to = '#field';
	e_to = 'house';
	w_to = 'whouse';
	dsc = [[Ты стоишь на улице возле своего дома, утопающего в цветах. Отсюда ты можешь пойти на футбольное поле{$dir|юг}
или во двор к пятиэтажке{$dir|север}.]];
	in_to = 'house';
}: with {
	obj {
		nam = 'house';
		description = [[Одноэтажный кирпичный домик окрашенный в белый цвет. Он кажется тебе самым уютным домом на свете.]];
		-"дом|дверь";
		['before_Enter,Climb'] = function()
			walk 'kitchenroom'
		end;
	}:attr'scenery';
	Path {
		-"футбольное поле|поле";
		nam = '#field';
		walk_to = 'field';
		desc = [[Ты можешь пойти на футбольное поле.]];
	};
	Path {
		-"пятиэтажка|двор";
		nam = '#houses';
		walk_to = 'houses';
		desc = [[Ты можешь пойти к пятиэтажке.]];
	};
}

function mp:CutSaw(w, wh)
	if not wh and not have'saw' then
		p [[Тебе не чем пилить.]]
		return
	end
	if not wh then wh = _'saw' end
	if not have(wh) then
		p ([[Сначала нужно взять ]], wh:noun'вн', ".")
		return
	end
	if not have(w) and w ^ 'bow' then
		p ([[Сначала нужно взять ]], w:noun'вн', ".")
		return
	end
	if wh ~= _'saw' then
		p ([[Пилить ]], wh:noun 'тв', " не получится.")
		return
	end
	if w == wh or w == me() then
		p [[Интересно, как это получится?]];
		return
	end
	if mp:check_live(w) then
		return
	end
	return false
end

function mp:after_CutSaw(w, wh)
	if not wh then wh = _'saw' end
	p ([[У тебя не получилось запилить ]], w:noun'вн', " ", wh:noun'тв',".");
end

Verb {
	"#CutSaw";
	"[|рас|вы|за|от|с|пере]пили/ть,[|рас|вы|за|от|с|пере]пилю";
	"{noun}/вн : CutSaw";
	"{noun}/вн {noun}/тв,held : CutSaw";
}

obj {
	function(s)
		if s.short then
			pr (-"кусок удочки,кусок|")
		end
		pr (-"удочка|бамбук|")
		if s.short then
			pr (-"|удилище|заготовка|палка")
		end
	end;
	nam = 'bow';
	short = false;
	description = function(s)
		if s.short then
			p [[Это отличная заготовка для лука!]];
			return
		end
		p [[Старая удочка из гибкого и крепкого бамбука. Длина около двух с половиной метров. Здорово гнётся!]];
	end;
	found_in = 'junk';
	before_Cut = function(s, w)
		if not w and have 'saw' or w == _'saw' then
			mp:xaction("CutSaw", s)
			return
		end
		p [[Тебе не чем отрезать удочку.]]
	end;
	after_CutSaw = function(s)
		if s.short then
			p [[Больше пилить не нужно.]]
			return
		end
		p [[Ты отпилил от удочки кусок удилища. Получилась хорошая заготовка для лука!]]
		s.short = true
	end;
}:disable();

obj {
	-"лобзик|пила";
	nam = 'saw';
	description = [[Лобзик для выпиливания по дереву. Ещё почти не ржавый!]];
	found_in = 'junk';
}:disable();

obj {
	-"хлам";
	nam = 'junk';
	before_Take = [[Ты можешь поискать в хламе что-нибудь интересное.]];
	description = function(s)
		if not disabled'saw' and _'saw':inside(s) or
		not disabled'bow' and _'bow':inside(s) then
			mp:content(s)
		else
			p [[Тут, наверное, много всего интересного, если поискать.]];
		end
	end;
	['before_Search,LookUnder,Consult'] = function(s)
		if disabled'bow' then
			p [[Ты покопался в хламе и нашёл старую удочку.]];
			enable'bow'
			take 'bow'
		elseif disabled'saw' then
			p [[Ты покопался в хламе и нашёл лобзик.]];
			enable'saw'
			take 'saw'
		else
			p [[Вроде больше ничего интересного не находится.]];
		end
	end;
	found_in = 'warehouse';
}:attr'scenery,container,open':dict {
	["хлам/пр,2"] = "хламе";
};

room {
	-"сарай";
	title = "сарай";
	nam = 'warehouse';
	dsc = [[Сарай завален разным интересным хламом. Ты можешь выйти из сарая на улицу.]];
	Smell = [[Пахнет резиной и бензином.]];
	out_to = '#street';
	e_to = '#street';
	onexit = function(s)
		if have 'bow' and not _'bow'.short then
			p [[Длина удочки больше двух метров! Ты решил оставить её в сарае.]]
			drop 'bow'
		end
	end;
}: with {
	Path {
		-"улица";
		nam = '#street';
		walk_to = 'street';
		desc = [[Ты можешь пойти на улицу.]];
	};
}

obj {
	-"клевер/мр,но|цветы/мр";
	description = [[Сиреневые цветы растут то тут, то там на футбольном поле.]];
	before_Take = [[Собирать цветы не входит в твои планы.]];
	found_in = 'field';
}:attr'scenery':dict{
	["цветы/вн"] = "цветы";
	["клевер/пр"] = "клевере";
}

function mp:Burn(w, wh)
	if mp:check_touch() then
		return
	end
	if wh and mp:check_held(wh) then
		return
	end
	if not wh and not have 'matches' then
		p [[Чем поджечь?]]
		return
	end
	if w == _'matches' and _'arrow'.matches and have 'arrow' then
		mp:xaction("Burn", _'arrow')
		return
	end
	if not wh or wh == _'match' or wh == _'matches' then
		return false
	end
	p (mp.msg.Burn.BURN2)
end

function mp:after_Burn(w, wh)
	if w == _'match' or w == _'matches' then
		p [[Ты зажёг одну из спичек. Она горела долго, около 20 секунд.]]
		if here() ^ 'dark' or here() ^ 'dark2' then
			p [[Ты успел рассмотреть и запомнить всё вокруг.]]
			here():attr'light'
		end
		return
	end
	p (mp.msg.Burn.BURN)
end

obj {
	-"охотничьи спички,спички";
	nam = 'matches';
	before_Exam = [[Мечта любого мальчишки. Горят в любых условиях.]];
	before_Tie = function(s, w)
		return _'match'.before_Tie(s, w)
	end;
}: with {
	obj {
		nam = 'match';
		-"спичка";
		before_Default = [[Теперь ты можешь что-нибудь поджечь.]];
		before_Exam = [[Мечта любого мальчишки. Горят в любых условиях.]];
		before_Burn = function(s) return false end;
		before_Tie = function(s, w)
			if not w ^ 'arrow' then
				return false
			end
			if w.fire then
				p [[Стрела уже горит!]]
				return
			end
			if not have 'wires' and not have 'rope' then
				p ([[Тебе не чем примотать ]], s:noun'вн', ".")
				return
			end
			if not have 'wires' then
				p [[Верёвка слишком толстая для этого. Нужно найти что-то более подходящее.]]
				return
			end
			if w.matches then
				p [[Ты примотал к стреле ещё одну спичку.]]
			else
				p [[Ты примотал к наконечнику стрелы четыре охотничьих спички.]]
				w.matches = true
			end
		end;
	}
}

obj {
	nam = 'roma';
	-"Рома|мальчик|парень";
	feed = false;
	fires = false;
	description = function(s)
		if s.feed then
			p [[Рома с удовольствием ест пирожок. Похоже на то, что он счастлив.]]
			return
		end
		p [[Рома на несколько лет старше тебя и он кажется тебе совсем взрослым. Рома очень полный. Этим летом ты часто видишь его на
стадионе бегающим по беговой дорожке.]];
	end;
	dsc = function(s)
		if s.feed then
			p [[Рядом с тобой стоит Рома.]];
			return
		end
		p [[Ты видишь взмокшего Рому, который бежит по беговой дорожке.]];
	end;
	['life_Give,Show'] = function(s, w)
		pn [[Ты поравнялся с Ромой, бегущим легкой трусцой.]]
		if w ^ 'pie' then
			p [[Ни говоря лишних слов, ты показал ему пирожок. Рома пробежал с тобой ещё несколько метров, потом
остановился:^
-- Спасибо, мелкий!]];
			pie_nr = pie_nr - 1
			remove(w)
			s.feed = true
		else
			p ([[Ты показал ему ]], w:noun 'вн', ".");
			if w ^ 'matches' then
				pn()
				local ofeed = s.feed; s.feed = true
				s:talk_to()
				s.feed = ofeed
				return
			end
			p [[^-- Отстань, мелкий!]]
		end
	end;
	['before_Say,Ask,Tell'] = [[Ты можешь просто {$fmt em|поговорить с Ромой}.]];
	talk_to = function(s)
		if not s.feed then
			pn [[Ты поравнялся с Ромой, бегущим легкой трусцой и спросил:]]
			p [[-- Привет!^]]
			p [[-- Брысь, мелочь пузатая!]];
			return
		end
		if s.fires then
			if s:once 'fires' then
				pn [[-- Рома, я слышал у тебя спички есть, охотничьи....]]
				pn [[-- Ага, есть. Показать?]]
				pn [[-- Дай на время, очень нужно.]];
				pn [[-- Нет, и не проси.]];
				pn [[-- Мне чтобы Мурзика из подвала достать. А охотничьи спички горят долго...]]
				pn [[... -- Ладно, держи. Только много не трать!]]
				take 'matches'
			else
				pn [[-- Спички хочешь отдать?]]
				if visited 'goodend1' then
					if not have 'matches' then
						pn [[-- Да, только я их забыл принести...]]
					else
						pn [[-- Да, держи. Только тут их немного осталось, извини...]]
						remove 'matches'
					end
				else
					pn [[-- Ещё нет, но я скоро!]]
				end
				p [[...]]
			end
		else
			pn [[-- Спортом занимаешься? Здорово!]]
			pn [[-- Да, это непросто...]];
		end
	end;
	found_in = 'field';
}:attr'animate';

room {
	-"поле";
	nam = 'field';
	out_to = '#street';
	n_to = '#street';
	enter = function() _'roma'.feed = false; end;
	title = "футбольное поле";
	Smell = [[Пахнет душистым клевером.]];
	dsc = [[Футбольное поле заросло клевером. Ты можешь вернуться к своему дому{$dir|север}.]];
}: with {
	Path {
		-"дом";
		nam = '#street';
		walk_to = 'street';
		desc = [[Ты можешь пойти к своему дому.]];
	}
}

obj {
	-"пятиэтажка,кирпич*|пятиэтажный дом";
	found_in = 'houses';
	description = [[Пятиэтажка построена из красного кирпича.]];
}:attr'scenery';

obj {
	-"ребята";
	nam = 'boys';
	before_Default = "Здесь есть Света, Максим и Руслан.";
	dsc = [[Ребята стоят у входа в подвал.]];
};

obj {
	-"Света|девочка";
	nam = 'girl';
	talk_to = function(s)
		if escaped and visited 'goodend1' then
			walk 'happyend'
			return
		end
		if _'underground':hasnt'locked' then
			p [[-- Какой ты молодец! Ты спасёшь Мурзика? Правда?
Он залез в окно, а вылезти не может. Только всё время пищит.
Только бы его не съели крысы!]]
			return
		end
		p [[-- Бедный Мурзик! Говорят, в подвале много-много крыс! Что же делать? Может быть, ты что-нибудь придумаешь?]];
	end;
	description = [[Тебе кажется, что Света очень красивая.]];
	['before_Kiss,Touch,Taste,Smell,Take'] = "У тебя не хватает духу.";
}:attr'animate'

obj {
	-"Руслан";
	nam = 'ruslan';
	talk_to = function(s)
		if _'underground':hasnt'locked' then
			pn [[-- Ух ты! Обычной скрепкой! Но в подвале темно. Кстати, Ромке отец подарил охотничьи спички. Я его видел недавно, он шел на футбольное поле.]]
			if not _'roma'.fires then
				pn [[И ещё... Ты меня извини за то, что лук тебе тогда сломал. Я не специально.]]
				p [[-- Забыли.]]
			end
			_'roma'.fires = true
			return
		end
		p [[-- Он залез в окно, а вылезти не может. Только всё время пищит.]];
	end;
	['life_Give,Show'] = function(s, w)
		if w ^ 'bow2' then
			p [[-- Ух ты, у тебя новый лук? Можно я проверю его на прочность?^-- Нет!]];
		else
			return false
		end;
	end;
	description = [[Руслан носит толстые очки. Он увлекается шахматами.]];
	['before_Kiss,Touch,Taste,Smell'] = "Ну уж нет.";
}:attr'animate'

obj {
	-"Макс,Максим";
	nam = 'max';
	talk_to = function(s)
		if _'underground':hasnt'locked' then
			p [[-- В подвале темно и страшно! Я бы не рискнул спуститься туда.]]
			return
		end
		p [[-- Мурзик залез в подвал и не может выбраться! Наверное, его съедят крысы!]];
	end;
	description = [[Макс -- маленький юркий паренёк. Он младше тебя на год.]];
	['before_Kiss,Touch,Taste,Smell'] = "У тебя нет такого желания.";
}:attr'animate'

obj {
	nam = 'bow2';
	-"лук";
	description = [[Отличный получился лук, лучше старого!
Теперь ты можешь стрелять.]];
	after_Give = function(s, w)
		p [[Ты не хочешь расставаться со своим луком.]]
	end;
}

function mp:Fire(w)
	if not have 'bow2' then
		p [[Но тебе не из чего стрелять.]]
		return
	end
	if not have 'arrow' then
		p [[У тебя нет стрел.]]
		return
	end
	return false
end

function mp:after_Fire(w)
	p ([[Ты выстрелил из лука в ]], w:noun'вн', ".")
	if mp:animate(w) then
		p (w:It'дт'," это не понравилось.")
	else
		p ("Стрела отскочила и упала под ноги.");
	end
	drop 'arrow'
end

Verb {
	"#Fire";
	"стреля/ть,выстрел/ить,стрельн/уть";
	"в {noun}/вн,scene : Fire";
}

obj {
	nam = 'rope';
	-"верёвка,тетива";
	description = "Тонкая, но крепкая капроновая верёвка.";
	['before_Cut,CutSaw,Tear'] = "Длина верёвки тебя устраивает.";
	before_Tie = function(s, wh)
		if not have(s) then
			return false
		end
		if wh ^ 'bow' then
			if wh.short then
				p [[Ты привязал конец верёвки к бамбуку, согнул его и привзял
второй. Получился отличный лук!]]
				if not have 'arrow' then
					p [[Только стрелы нет. В доме где-то должна быть одна от старого
лука.]]
				end
				remove(s)
				replace(wh, 'bow2')
			else
				p [[Ты пытаешься сделать себе удочку? Зачем она тебе?]]
			end
		else
			return false
		end
	end;
}

obj {
	nam = 'ropes';
	-"бельё|столбы";
	description = "Обычное дело. Бельё сушится на натянутых между столбами верёвках.";
	before_Take = "Тебя не интересует чужое бельё. К тому же, за это могут и навалять.";
}:attr 'concealed':with {
	obj {
		-"верёвка|верёвки";
		description = function(s)
			if s.cut then
				p "Все верёвки заняты."
			else
				p "Одна из верёвок не занята.";
			end
		end;
		cut = false;
		before_Take = "Крепко привязано! У тебя не выходит отвязать верёвку.";
		before_Receive = "Не стоит этого делать.";
		['before_Attack,Tear'] = "Крепкая.";
		before_Cut = function(s, w)
			if not w and have 'saw' or w == _'saw' then
				mp:xaction("CutSaw", s)
				return
			end
			p [[Тебе не чем отрезать верёвку.]]
		end;
		after_CutSaw = function(s)
			if s:once() then
				p [[Ты отпилил кусок верёвки при помощи лобзика.]]
				take 'rope'
				mp.first_it = _'rope'
				s.cut = true
			else
				p [[Ты уже раздобыл верёвку.]]
			end
		end;
	}:attr'scenery,supporter'
}

local function u_listen()
	_'dark':daemon(true)
end

room {
	nam = 'dark';
	title = "В подвале";
	-"подвал";
	['u_to,out_to'] = 'houses';
	n_to = 'dark2';
	n_seen = false;
	before_Listen = u_listen;
	dsc = function(s)
		p [[Когда ты зажигал спичку, ты заметил проход.]]
		if have 'compass' or s.n_seen then
			p [[Он расположен в северной стороне.]]
			s.n_seen = true
		else
			p [[Но без компаса в темноте сложно ориентироваться.]]
		end
	end;
	dark_dsc = [[Здесь темно. Ты можешь уйти из подвала.]];
	daemon = function(s, force)
		if visited 'goodend1' then
			p [[Ты слышишь шорохи.]]
			return
		end
		if here() ^ 'dark3' then
			if disabled 'dark_door' then
				p [[Ты слышишь жалобное мяуканье.]]
			end
			return
		end
		if here() ^ 'dark4' then
			p [[Ты слышишь жалобное мяуканье Мурзика.]]
			return
		end
		local t = {
			"Ты слышишь жалобное мяуканье.";
			"Ты слышишь странные шорохи.";
			"Тебе кажется, что в подвале кто-то есть.";
			"Тебе кажется, что кто-то стоит за твоей спиной.";
			"Из глубины подвала доносится шелест.";
		}
		if force or rnd(100) < 20 then
			p(t[rnd(#t)])
		end
	end;
	enter = function(s, f)
		s:attr '~light'
		if f ^ 'houses' then
			p [[Ты спустился в подвал и оказался в полной темноте.]]
			if not visited 'goodend1' then
				s:daemonStart()
			end
		end
	end;
	exit = function(s, t)
		if t ^ 'houses' then
			s:daemonStop()
		end
	end;
	onexit = function(s, t)
		if t ^ 'houses' and visited 'goodend1' then
			if _'arrow'.fire then
				if have 'arrow' then
					p [[Стрела, наконец, погасла.]]
				end
				_'arrow'.matches = false
				_'arrow'.fire = false
			end
			if escaped and s:once 'final' then
				remove 'boys'
				remove 'ruslan'
				remove 'max'
				place ('cat', t)
			end
		end
	end;
	Smell = [[Здесь воняет.]];
}:attr '~light';

room {
	nam = 'dark2';
	title = "Развилка";
	-"подвал";
	['out_to'] = 'dark';
	s_to = 'dark';
	n_to = 'dark_n';
	w_to = 'dark_w';
	n_seen = false;
	before_Listen = u_listen;
	dsc = function(s)
		p [[Когда ты зажигал спичку, ты заметил два прохода.]]
		if have 'compass' or s.n_seen then
			p [[Они расположены на севере и на западе.]]
			p [[Выход находится на юге.]];
			s.n_seen = true
		else
			p [[Но без компаса в темноте сложно ориентироваться.]]
		end
	end;
	dark_dsc = [[Здесь темно.]];
	enter = function(s, f)
		s:attr '~light'
	end;
	Smell = [[Здесь воняет.]];
}
global ('escaped') (false)
obj {
	-"окно|окна";
	['before_Enter,Climb'] = "Слишком узко даже для тебя.";
	description = "Сквозь узкие прорези окон сюда проникает свет с улицы. Ты ему очень рад.";
	['before_Receive,ThrownAt'] = function(s, w)
		if not pl:where() ^ 'box' or not _'box':has'moved' then
			p [[Ты не достаёшь до окна.]]
			return
		end
		if not w ^ 'cat' then
			p [[Зачем это выбрасывать на улицу?]]
			return
		end
		p [[Ты протянул руки и просунул котёнка сквозь узкое окно. Он, радостно мяукнув, скрылся из виду.]]
		remove(w)
		escaped = true
	end;
	found_in = { 'dark_n', 'dark_w', 'dark3', 'dark4' };
}:attr'scenery';

obj {
	nam = 'box';
	-"ящик|коробка";
	init_dsc = function(s)
		p [[В дальнем углу помещения стоит деревянный ящик.]];
		mp:content(s)
	end;
	dsc = function(s) p [[Под окном стоит ящик.]]; mp:content(s); end;
	['before_Push,Transfer'] = function(s)
		if seen 'rat' then
			p [[Крыса не дает тебе подойти к ящику.]];
			return
		end
		if pl:where() == s then
			p [[Но ты же стоишь на нём!]]
			return
		end
		if s:once() then
			p [[Ты подвинул ящик к окну.]]
			s:attr'moved'
		else
			p [[Ящик уже подвинут к окну.]]
		end
	end;
	before_Take = function(s)
		if seen 'rat' then
			p [[Крыса не дает тебе подойти к ящику.]];
			return
		end
		p [[Тяжеленный!]];
	end;
	['before_Exam,Listen,Fire'] = function() return false end;
	description = [[Деревянный ящик зелёного цвета.]];
	before_Default = function(s)
		if seen 'rat' then
			p [[Крыса не дает тебе подойти к ящику.]];
		else
			return false
		end
	end;
	obj = { 'cat' };
}:attr 'static,supporter,enterable';

obj {
	nam = 'cat';
	-"котёнок,Мурзик|кот";
	['before_Exam,Listen,Fire'] = function() return false end;
	description = function(s)
		if seen 'rat' then
			p[[Мурзик такой маленький по сравнению с этой злой тварью.]];
		else
			p [[Мурзик, он спасён!]]
		end
	end;
	['before_Touch,Kiss'] = function()
		if seen 'rat' then
			p [[Пока рядом находится эта тварь, ты не можешь обнять котёнка.]];
		else
			p [[Милый Мурзик!]];
		end
	end;
	before_Take = function(s)
		if seen 'rat' then
			p [[Как ты себе это представляешь, когда рядом находится крыса?]]
			return
		end
		p [[Ты забрал Мурзика.]]
		take(s)
		s:attr 'moved'
	end;
	before_Default = function(s)
		if seen 'rat' then
			p [[Пока рядом находится эта тварь, ты ничего не можешь сделать.]];
		else
			return false
		end
	end;
	init_dsc = [[На ящике сидит котёнок и жалобно мяукает.]]
}:attr 'animate':dict {
	["Мурзик/мр,од,ед,С"] = {
		"Мурзик/им";
		"Мурзика/вн";
		"Мурзика/рд";
		"Мурзиком/тв";
		"Мурзике/пр";
		"Мурзику/дт";
	};
}

obj {
	nam = 'rat';
	-"крыса|тварь";
	description = function(s)
		p [[Ты никогда не видел таких огромных крыс.]]
		if not visited 'goodend1' then
			p [[К счастью, она не обращает на тебя внимания.]];
		end
	end;
	['before_Exam,Listen,Fire'] = function() return false; end;
	before_Default = function(s, ev)
		if ev == 'Burn' then
			if have 'bow2' and have 'arrow' then
				p [[Эта тварь опасная.]]
				if  _'arrow'.fire then
					p [[Но у тебя есть огненная стрела и лук. Ты можешь выстрелить в крысу.]]
				else
					p [[Вот если бы у тебя была огненная стрела...]]
				end
			else
				p [[Ты не представляешь себе, как можно это сделать.]]
			end
		elseif ev == 'Walk' then
			return false
		else
			p [[Эта тварь опасная. Лучше с голыми руками к ней не приближаться.]];
		end
	end;
	['life_Give,Show'] = [[Эта тварь опасная. Лучше с голыми руками к ней не приближаться.]];
	init_dsc = [[Прямо под ящиком ты видишь огромную крысу, которая встала на задние лапы, пытаясь достать до Мурзика.]];
	daemon = function(s)
		if not here() ^ 'dark3' then
			return
		end
		if have 'bow2' and have 'arrow' and _'arrow'.fire then
			p [[Ты видишь в конце коридора крысу. Она держится на приличном расстоянии, но ты видишь, как в её красных глазках пылает огонь твоей стрелы.]]
			p [[Она боится огня, но, все-таки, продолжает следить за тобой.]]
		else
			s:daemonStop()
			walk 'badend5'
		end
	end;
}:attr 'animate';

global 'target' (false)

cutscene {
	nam = 'badend1';
	title = "конец";
	text = function(s)
		if s.__num == 1 then
			pn ([[Ты выстрелил в ]], target:noun'вн', ".");
			if target ^ 'rat' then
				p [[Деревянная стрела не причинила крысе никакого вреда и не напугала её.]]
			end
			pn ("Крыса обернулась. Её маленькие и злые красные глазки полыхнули в полумраке. А потом она бросилась на тебя.")
			if target ^ 'rat' and have 'matches' then
				pn [[^Все животные боятся огня. Ты вспомнил об этом слишком поздно...]]
			end
			pn ("^{$fmt em|Но всё могло закончиться по-другому...}");
		end
	end;
	next_to = 'dark4';
}

cutscene {
	nam = 'badend2';
	title = "конец";
	text = [[Ты вышел в коридор, держа Мурзика на руках. Ты успел сделать
всего несколько шагов, когда из конца коридора на тебя бросилась жирная тварь.^^
Твои руки были заняты, чтобы успеть что-нибудь предпринять.^
^{$fmt em|Но всё могло закончиться по-другому...}]];
	next_to = 'dark4';
}

cutscene {
	nam = 'badend3';
	title = "конец";
	text = [[Ты вышел в коридор и успел сделать
всего несколько шагов, когда из конца коридора на тебя бросилась жирная тварь.^^
У тебя не было огненной стрелы, чтобы отпугнуть тварь, поэтому ты не мог ничего изменить...^
^{$fmt em|Но всё могло закончиться по-другому...}]];
	next_to = 'dark4';
}

cutscene {
	nam = 'badend4';
	title = "конец";
	text = [[Ты вышел в коридор и успел сделать
всего несколько шагов, когда из конца коридора на тебя бросилась жирная тварь.^^
У тебя не было лука, чтобы отпугнуть тварь, поэтому ты не мог ничего изменить...^
^{$fmt em|Но всё могло закончиться по-другому...}]];
	next_to = 'dark4';
}

cutscene {
	nam = 'badend5';
	title = "конец";
	text = [[Как только крыса поняла, что ты безоружен, она бросилась к тебе.
И ты не мог ничего изменить...^
^{$fmt em|Но всё могло закончиться по-другому...}]];
	next_to = 'dark3';
}

cutscene {
	nam = 'happyend';
	title = false;
	text = {
		[[-- А где все?^^
-- Кто? А, эти... Ушли обедать. Серёжка, ты такой молодец!^^
-- ...^^
-- Ты знаешь...^^
... Я должна сказать тебе...]];
	};
	next_to = 'titles';
}
room {
	nam = 'titles';
	title = fmt.c '"ТЫ -- МОЙ ГЕРОЙ!"';
	noparser = true;
	dsc = [[{$fmt c|Автор сюжета и кода: Косых Пётр^^
Специально на ИНСТЕДОЗ-6^^
Тестирование:^^
Zlobot^
Kerber^
Boris Timofeev^
goraph^^
Март -- 2019^^
Если вам понравилась игра,
^заходите на http://instead-games.ru
}
]]
}

cutscene {
	nam = 'goodend1';
	title = false;
	text = [[Ты натягиваешь тетиву лука до упора и посылаешь пылающую стрелу в крысу.^^
Стрела врезается в тварь и обдаёт её снопом искр.^^
Крыса подпрыгивает, вертится волчком и скрывается в дверном проёме.]];
	next_to = 'dark4';
}

room {
	nam = 'dark4';
	-"подвал|помещение";
	title = 'Квадратное помещение';
	out_to = 'dark_door';
	onexit = function(s, w)
		if have 'cat' then
			walk 'badend2'
			return false
		end
		if visited 'goodend1' and (not have 'bow2' or not have 'arrow' or not _'arrow'.fire) then
			if not have 'bow2' then
				walk 'badend4'
			else
				walk 'badend3'
			end
			return false
		end
		if _'arrow'.fire and seen 'rat' then
			p [[Ты не для того пришёл сюда, чтобы просто уйти.]]
			return false
		end
		if visited 'goodend1' then
			move('rat', 'dark3')
			_'rat':attr'concealed'
			DaemonStart 'rat'
		end
		return
	end;
	before_Listen = u_listen;
	after_Fire = function(s, w)
		if not seen 'rat' then
			return false
		end
		if not w ^ 'rat' or not _'arrow'.fire then
			target = w;
			walk 'badend1';
			return
		end
		drop 'arrow'
		_'arrow'.fire = false
		_'arrow'.matches = false
		remove 'rat'
		DaemonStop 'dark'
		walk 'goodend1'
	end;
	w_to = 'dark_door';
	dsc = function(s)
		p [[Ты находишься в подвальном помещении в котором есть узкое окно на улицу.]];
		if have 'compass' then
			p [[Выход находится на западе.]]
		end
	end;
}:with {
	'dark_door',
	'box', 'rat'
}

room {
	nam = 'dark_n';
	-"подвал|помещение";
	title = 'Квадратное помещение';
	out_to = 'dark2';
	before_Listen = u_listen;
	s_to = 'dark2';
	dsc = function(s)
		p [[Ты находишься в подвальном помещении в котором есть узкое окно на улицу.]];
		if have 'compass' then
			p [[Выход находится на юге.]]
		end
	end;
}

room {
	nam = 'dark_w';
	-"подвал|помещение";
	title = 'Поворот';
	out_to = 'dark2';
	before_Listen = u_listen;
	e_to = 'dark2';
	n_to = 'dark3';
	dsc = function()
		p [[Ты находишься в проходном подвальном помещении, в котором есть узкое окно на улицу.]];
		if have 'compass' then
			p [[Ты можешь пройти на восток и север.]]
		end
	end;
}

obj {
	nam = 'real_key';
}

room {
	nam = 'dark3';
	-"подвал|коридор";
	title = 'Помещения';
	out_to = 'dark_w';
	onenter = function(s, f)
		if f ^ 'badend5' then
			DaemonStart 'rat'
			take 'bow2'
			take 'arrow'
			_'arrow'.fire = true
			_'arrow'.matches = true
		end
	end;
	after_Fire = function(s, w)
		if w ^ 'rat' then
			p [[Крыса держится от тебя на приличной дистанции. Выстрелив в неё, ты лишишься оружия. Пока она не нападает, лучше поберечь стрелу.]]
			return
		end
	end;
	in_to = function(s)
		if not disabled 'dark_door' then return 'dark_door' end
		p [[Проходов очень много и они закрыты. Нужно как-то понять, в каком из них находится Мурзик.]];
	end;
	s_to = 'dark_w';
	e_to = function(s)
		return s:in_to()
	end;
	before_Listen = function(s)
		if s:once() then
			p [[Ты прошёлся вдоль коридора прислушиваясь к жалобному мяуканию и нашёл дверь из-за которого оно доносилось.]]
			enable'dark_door'
		else
			if not visited 'goodend1' then
				p [[Ты и так уже знаешь, за какой дверью находится Мурзик.]]
			else
				p [[Тихо, только какой-то странный шорох.]]
			end
		end
	end;
	dsc = function()
		p [[Ты находишься в длинном коридоре с одной стороны которого есть узкие окна на улицу, а с другой{$dir|восток} -- множество проходов в подвальные помещения. ]];
		if have 'compass' then
			p [[Ты можешь пройти на юг.]]
		end
	end;
}:with {
	obj {
		-"проходы|помещения";
		before_Default = [[Их очень много и они закрыты. Нужно как-то понять, в каком из них находится Мурзик.]];
	}:attr 'scenery';
	door {
		nam = 'dark_door';
		dsc = function(s)
			if s:has'locked' then
				p [[Здесь есть дверь, из-за которой доносится жалобное мяуканье.]];
			else
				p [[Здесь есть взломанная дверь.]]
			end
		end;
		with_key = 'real_key';
		door_to = function(s)
			if here() ^ 'dark3' then
				return 'dark4'
			else
				return 'dark3'
			end
		end;
		description = function(s)
			if s:hasnt'locked' then
				p [[Тебе повезло, дверной косяк прогнил и замок просто выломал гнездо для язычка. Ты можешь войти в дверь.]]
			else
				p [[Дверь не выглядит надёжной.]]
			end
		end;
		['before_Attack,Push'] = function(s)
			if s:once() then
				p [[Ты с силой навалился на дверь. Раздался треск, посыпались щепки и дверь открылась внутрь помещения.]]
				s:attr'~locked,open'
			else
				p [[Дверь уже незаперта.]]
			end
		end;
	}:attr"static,openable,lockable,locked":disable();
}

obj {
	-"подвал";
	nam = 'underground';
	with_key = 'wire';
	found_in = 'houses';
	['before_Enter,Climb'] = function(s)
		if s:hasnt'open' then
			if s:has'locked' then
				p [[Подвал заперт на замок.]]
			else
				p [[Подвал закрыт.]]
			end
			return
		end
		walk 'dark';
	end;
	description = function(s)
		if s:has'locked' then
			p [[Подвал закрыт на замок.]]
		else
			return false
		end
	end;
	before_Attack = function(s)
		mp:xaction("Attack", _'#guard')
	end;
	before_Lock = function(s)
		if s:hasnt'locked' then
			p [[Второй раз может не получиться.]]
		else
			return false
		end
	end;
	after_Unlock = function(s)
		pn [[Не надеясь на успех, ты всё-таки попробовал открыть замок скрепкой...]]
		p [[У тебя это {$fmt em|получилось}!]];
		s:attr'open'
	end;
}:attr 'scenery,openable,locked,lockable,enterable': with{
	obj {
		-"замок";
		nam = '#guard';
		description = [[Маленький стальной замок.]];
		before_Take = [[Это государственное имущество.]];
		before_Attack = [[Замок железный, так просто его не сломать.]];
		before_Open = function(s)
			if _'underground':has'locked' then
				p [[Но как?]]
			else
				p [[Уже открыт.]];
			end
		end;
		['before_Lock,Close'] = function(s, w)
			mp:xaction('Lock', _'underground', w)
		end;
		before_Unlock = function(s, w)
			mp:xaction('Unlock', _'underground', w)
		end;
		before_Receive = function(s, wh)
			if wh ^ 'wire' then
				mp:xaction("Unlock", _'underground', _'wire')
				return
			end
			return false
		end;
	}:attr'scenery';
}


room {
	nam = 'houses';
	-"двор";
	title = 'Во дворе пятиэтажки';
	['d_to,in_to'] = 'underground';
	['s_to,out_to'] = '#street';
	before_Listen = function(s, wh)
		if _'underground':hasnt'locked' or wh == _'underground' then
			if not visited 'goodend1' then
				p [[Из глубины подвала ты слышишь жалобный писк котёнка.]];
			else
				return false
			end
		end
		local txt = {
			[[-- Ему нужно как-то помочь!]];
			[[-- Там же темно!]];
			[[-- Я слышал, в подвале водятся крысы...]];
			[[-- Что, так и будем стоять?]];
			[[-- Бедный Мурзик!]];
		};
		p ("Ты слышишь оживлённый детский спор. Сложно разобрать, чем он вызван.")
		p "^"
		p (txt[rnd(#txt)], " -- говорит кто-то из ребят.")
	end;
	dsc = function(s)
		p [[У кирпичной пятиэтажки есть большой двор, где обычно играют дети из соседних домов.]];
		if s:once() then
			pn "^"
			pn [[Ты заметил Свету, Руслана и Макса. Они о чём-то спорят.]];
		end
		p [[Ты можешь уйти к своему дому{$dir|юг}.]];
		p [[Во дворе сушится бельё.]]
	end;
}: with {
	'ropes', 'boys', 'girl', 'max', 'ruslan',
	Path {
		-"дом";
		nam = '#street';
		walk_to = 'street';
		desc = [[Ты можешь пойти к своему дому.]];
	}
}

function init()
	mp.togglehelp = true
	mp.autohelp = false
	mp.autohelp_limit = 8
	mp.compl_thresh = 1
	if theme.name() == '.mobile' or theme.name() == '.mobile2' then
--		mp.autohelp = true
--		mp.compl_thresh = 0
--		mp.autohelp_limit = 2000
	else
		mp.togglehelp = false
	end
	pic_set '1-pan'
end

VerbHint (
	'#GetOff',
	function(s)
		return not pl:where():type'room'
	end
)

VerbHint (
	'#Wear',
	function(s)
		return _'clothes':hasnt 'worn' and have 'clothes'
	end
)

VerbHint (
	'#Jump',
	function(s)
		return here() ^ 'grandroom'
	end
)

VerbHint (
	'#Fire',
	function(s)
		return have 'bow2'
	end
)

VerbHint (
	'#Burn',
	function(s)
		return have 'matches'
	end
)

VerbHint (
	'#CutSaw',
	function(s)
		return have 'saw'
	end
)

Verb {
	"#Attack2",
	"ломать",
	"{noun}/вн : Attack"
}

Verb { "#ThrowAt2",
	"[про|за]сун/уть",
	"{noun}/вн,held в|во {noun}/вн : Insert",
}

VerbHint (
	"#ThrowAt2",
	function(s)
		return have 'cat' and here().nam:find('^dark')
	end
)

VerbHint (
	"#Tie",
	function(s)
		return have ('wires') or have ('rope')
	end
)

VerbHint (
	"#Exit",
	function(s)
		return here().out_to ~= nil
	end
)

game.hint_verbs = { "#Exam", "#Search", "#Drop", "#Walk", "#Take", "#Give", "#Talk", "#Open", "#Close", "#Push", "#Pull", "#Wait", "#Exit", "#Attack2", "#Inv" }

function mp:JumpOn(w)
	if w == me() then
		p [[Оригинально...]]
		return
	end
	if me():where() ~= w then
		p ([[Но ты сейчас не на ]], w:noun 'пр', '.')
		return
	end
	mp:xaction("Jump")
end

VerbExtend {
	"#Jump";
	"~ на {noun}/пр,scene : JumpOn"
}
