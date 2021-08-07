--$Name: Луна-9$
--$Version: 1.1$
--$Author: Пётр Косых$
--$Info: Интерактивная новелла\nЯнварь 2021$
xact.walk = walk
require "snd"
require "fmt"
if not instead.tiny then
require "fading"
require "theme"
require "autotheme"
end
require "link"

fmt.dash = true
fmt.quotes = true
require 'parser/mp-ru'
require 'snapshots'

if not instead.tiny then
mp:pager_mode(true)
end
global 'pics' ({})

function eph_event(ev)
	return ev == 'Exam' or ev == 'Smell' or ev == 'Listen' or ev == 'Look' or ev == 'Search' or ev == 'Talk'
		or ev == 'Wait' or ev == 'Ring' or ev == 'Think' or ev == 'Wake'
end

function pic_add(v)
	for _, it in pairs(pics) do
		if it == v then
			return
		end
	end
	table.insert(pics, v)
	if #pics > 3 then
		table.remove(pics, 1)
	end
end
function pic_set(v)
	pics = {v}
end

function game:pic()
	local pix = 'box:192x576,#ffffe8'
	local len = #pics
	if not instead.tiny and theme.name() == '.mobile' then
		pix = 'box:576x192,#ffffe8'
		for i = 1, len do
			pix = pix ..';'.. ('gfx/'..pics[i]..'.png') ..'@'..tostring((i-1)*192)..",0"
		end
	else
		for i = 1, len do
			pix = pix ..';'.. ('gfx/'..pics[i]..'.png') ..'@0,'..tostring((i-1)*192)
		end
	end
	return pix
end

if not instead.tiny then
	require "sprite"
	local scale = sprite.font_scaled_size(100)
	if scale > 100 then
		mp.cursor = fmt.img(sprite.new('gfx/cursor.png'):scale(scale/100))
	else
		mp.cursor = fmt.img 'gfx/cursor.png'
	end
end

mp.msg.Enter.EXITBEFORE = function()
	if me():where() ^'place' then
		p [[Но ты пристёгнут ремнями!]]
		return
	end
	p "Сначала нужно {#if_has/#where,supporter,слезть с {#where/рд}.,покинуть {#where/вн}.}"
end

mp.msg.UNKNOWN_OBJ = function(w)
	if not w then
		p "Об этом предмете ничего не сказано."
	else
		p "Об этом предмете ничего не сказано "
		p ("(",w,").")
	end
end
game.dsc = [[{$fmt b|ЛУНА-9}^^Интерактивная новелла для выполнения на средствах вычислительной техники.^Игра разработана с помощью ОС Plan9.^^Для получения справки по игре, наберите {$fmt em|помощь} и нажмите "ввод".]];

VerbExtend {
	"#Talk",
	"по {noun}/дт : Ring",
	"по {noun}/дт с {noun}/тв,scene : Ring",
	"~ с {noun}/тв,scene по {noun}/дт : Ring reverse",
	":Talk"
}

VerbExtendWord {
	"#Exit",
	"вернуться"
}
VerbExtend {
	"#Exit",
	"к {noun}/дт,scene : Walk"
}

Verb {
	"сверл/ить,просверл/ить",
	"{noun}/вн : Screw",
}
function game:before_Screw(w)
	if not have'screw' then
		p [[Но у тебя нет дрели!]]
		return
	end
	mp:xaction("Attack", w, _'screw')
end

Verb {
	"покин/уть",
	"{noun}/вн,scene : Exit",
}

Verb {
	"#Ring",
	"[по|]звон/ить",
	":Ring"
}

VerbExtend {
	"#Wave",
	"{noun}/тв,held : Wave",
	"{noun}/дт,scene,live : WaveOther"
}

function mp:WaveOther(w)
	if mp:check_touch() then
		return
	end
	return false
end

function mp:after_WaveOther()
	p [[Ты глупо помахал {#first/дт}.]]
end

VerbExtend {
	"#Push",
	"{noun}/вн вперёд : Push",
	"{noun}/вн от себя : Push",
	"{noun}/вн назад : Pull",
	"{noun}/вн на себя : Pull",
	"{noun}/вн направо|вправо : PushRight",
	"{noun}/вн налево|влево : PushLeft",
}
VerbExtend {
	"#Pull",
	"{noun}/вн вперёд: Push",
	"{noun}/вн от себя : Push",
	"{noun}/вн назад : Pull",
	"{noun}/вн на себя : Pull",
	"{noun}/вн направо|вправо : PushRight",
	"{noun}/вн налево|влево : PushLeft",
}
function mp:PushRight(w)
	mp:xaction("Push", w)
end

function mp:PushLeft(w)
	mp:xaction("Push", w)
end

function mp.token.ring()
	return "{noun_obj}/телефон,вн|звонок|вызов"
end

Verb {
	"#Answer",
	"ответ/ить,отвеч/ать",
	":Answer",
	"{noun}/дт : Answer",
	"на {ring} : Answer",
	"по {noun}/дт : Ring",
}

VerbExtend {
	"#Attack",
	"{noun}/вн {noun}/тв,held : Attack",
	"~ {noun}/тв,held {noun}/вн : Attack reverse",
}

Verb {
	"разобрать,разбер/и",
	"{noun}/вн : Attack",
	"{noun}/вн {noun}/тв,held : Attack",
	"~ {noun}/тв,held {noun}/вн : Attack reverse",
}
game:dict {
	["шуруповёрт/мр,С,но"] = {
		"шуруповёрт/им",
		"шуруповёрт/вн",
		"шуруповёрта/рд",
		"шуруповёрту/дт",
		"шуруповёртом/тв",
		"шуруповёрте/пр",
	};
	["пеленгатор/мр,С,но"] = {
		"пеленгатор/им",
		"пеленгатор/вн",
		"пеленгатора/рд",
		"пеленгатору/дт",
		"пеленгатором/тв",
		"пеленгаторе/пр",
	};
	["Ливей/мр,од"] = {
		"Ливей/им",
		"Ливея/вн",
		"Ливея/рд",
		"Ливею/дт",
		"Ливеем/тв",
		"Ливее/пр",
	};
	["Чжан/мр,од"] = {
		"Чжан/им";
		"Чжана/вн";
		"Чжана/рд";
		"Чжану/дт";
		"Чжаном/тв";
		"Чжане/пр";
	};
	["Ян/мр,од"] = {
		"Ян/им",
		"Яна/вн",
		"Яна/рд",
		"Яну/дт",
		"Яном/тв",
		"Яне/пр",
	};
}
global 'last_talk' (false)
function game:before_Ring(w)
	if (not w or w^'телефон') and not have 'телефон' then
		p [[У тебя нет с собой телефона.]]
		return
	end
	return false
end
function game:after_Ring(w)
	if not w or w^'телефон' then
		p [[Тебе некому сейчас звонить.]]
		return
	end
	p (w:Noun(), " не телефон и не радио, чтобы говорить c ", w:it 'вн', " помощью.");
end

-- ответить
function game:before_Answer(w)
	if not w then
		return false
	end
	mp:xaction("Talk", w)
end

function game:after_Answer(w)
	mp:xaction("Talk", w)
end
global 'gravity' ('earh')
function game:before_Any(ev, w)
	if ev == 'Jump' or ev == 'JumpOver' then
		if gravity then
			p [[Ты делаешь несколько неуверенных прыжков.]]
			return
		end
		p [[В невесомости?]]
		return
	end
	if _'скафандр':has'worn' and (ev == 'Taste' or
		ev == 'Eat' or
		ev == 'Kiss' or
		ev == 'Talk' or ev == 'Smell') then
		if ev == 'Talk' and _'скафандр'.radio then
			if not w then
				return false
			end
			if w ^ 'Беркут' or w ^ 'Арго' or w ^ 'Заря' or w ^ 'принцесса' then
				return false
			end
			if w ^ 'alex' then
				if _'alex'.suit then
					p [[Чтобы говорить с Александром по радио, нужно {$fmt em|говорить с Беркутом}.]]
				else
					mp:xaction('Talk', _'Беркут')
				end
				return
			end
		end
		p [[В скафандре неудобно это делать.]];
		return
	end
	if ev == "Ask" or ev == "Say" or ev == "Tell" or ev == "AskFor" or ev == "AskTo" then
		if w then
			p ([[Просто попробуйте поговорить с ]], w:noun'тв', ".")
		else
			p [[Попробуйте просто поговорить.]]
		end
		return
	end
	return false
end
-- говорить без указания объекта
function game:before_Talk(w)
	if w then
		last_talk = w
		if (w ^ 'Заря' or w ^ 'Беркут' or w ^ 'Арго') and
			(_'скафандр':hasnt'worn') then
			p [[Радио встроено в скафандр, а скафандр сейчас не на тебе.]]
			return
		end
		return false
	end
	if not last_talk or not seen(last_talk) then
		last_talk = false
		for _, v in ipairs(objs()) do
			if v:has'animate' then
				if last_talk then
					last_talk = false
					break
				end
				last_talk = v
			end
		end
		if not last_talk then
			p [[Говорить с кем? Нужно дополнить предложение.]]
			return
		end
	end
	mp:xaction("Talk", last_talk)
	return
end
-- чтобы можно было писать к чему-то -- трансляция в идти.

function mp:pre_input(str)
	local a = std.split(str)
	if #a <= 1 or #a > 3 then
		return str
	end
	if a[1] == 'в' or a[1] == 'на' or a[1] == 'во' or
		a[1] == "к" or a[1] == 'ко' then
		return "идти "..str
	end
	return str
end

-- класс для переходов
Path = Class {
	['before_Walk,Enter'] = function(s)
		if mp:check_inside(std.ref(s.walk_to)) then
			return
		end
		if _(s.walk_to):has 'door' then
			mp:xaction("Enter", _(s.walk_to))
			return
		end
		walk(s.walk_to)
	end;
	before_Default = function(s)
		if s.desc then
			if type(s.desc) == 'function' then
				s:desc()
			else
				p(s.desc)
			end
			return
		end
		p ([[Ты можешь пойти в ]], std.ref(s.walk_to):noun('вн'), '.');
	end;
	default_Event = 'Walk';
}:attr'scenery,enterable';

Careful = Class {
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" or
	ev == 'Listen' or ev == 'Smell' then
			return false
		end
		p ("Лучше быть с ", s:noun 'тв', " поосторожнее.")
	end;
}:attr 'scenery'

Distance = Class {
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" then
			return false
		end
		p ("Но ", s:noun(), " очень далеко.");
	end;
}:attr 'scenery'

Ephe = Class {
	description = "Это не предмет.";
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" then
			return false
		end
		p ("Но ", s:noun(), " не предмет.");
	end;
}:attr 'scenery'

Furniture = Class {
	['before_Push,Pull,Transfer,Take'] = [[Пусть лучше
	{#if_hint/#first,plural,стоят,стоит} там, где
	{#if_hint/#first,plural,стоят,стоит}.]];
}:attr 'static'

Prop = Class {
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" then
			p ("Тебе нет дела до ", s:noun 'рд', ".")
			return
		end
		p ("Лучше оставить ", s:noun 'вн', " в покое.")
	end;
}:attr 'scenery'

Useless= Class {
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" then
			return false
		end
		p ("Лучше оставить ", s:noun 'вн', " в покое.")
	end;
}:attr 'scenery'

function init()
	mp.togglehelp = true
	mp.autohelp = false
	mp.autohelp_limit = 8
	mp.compl_thresh = 1
	pic_add '1'
	walk 'home'
end
function start()
	local t = _'comp'.time
	if t ~= 0 then
		_'comp'.time = os.time()
	end
end
-- https://kosmolenta.com/index.php/488-2015-01-15-moon-seven
pl.description = function(s)
	if here() ^ 'flowers' then
		p [[Тебя зовут Борис. Это всё, что ты помнишь.]]
		return
	end
	p [[Тебя зовут Борис Громов.]]
	if not here() ^ 'home' then
		if mission then
			p [[Твоя миссия, перенести {$fmt em|их} на Землю с помощью трансмиттера.]]
		else
			p [[Тебе 43 года и ты -- космонавт.]];
		end
	end
	if _'скафандр':has'worn' then
		p [[На тебе надет скафандр.]]
	end
	if here() ^ 'home' then
		p [[Ты очень напряжён и эмоционально измотан.]]
	end
end
pl.scope = std.list {}

function clamp(v, l)
	if v > l then v = l end
	return v
end
function inc_clamp(v, l)
	v = v + 1
	return clamp(v, l)
end
function inc(v)
	return v + 1
end
function in_t(v, t)
	for _, vv in ipairs(t) do
		if v == vv then return true end
	end
	return false
end
obj {
	-"Лариса,жена";
	nam = 'жена';
	{
		talk = {
			[1] = [[-- Так не может продолжаться вечно. Нужно решать нашу проблему... -- начинаешь ты.^
			Лариса молча смотрит куда-то в сторону.]];
			[2] = [[-- Только нужно делать это вместе. Я и ты. Не молчи, пожалуйста...^
			Лариса пожимает плечами.]];
			[3] = [[-- Ты обещала поговорить. Так давай разговаривать! Не молчи, прошу!^
			Лариса с осторожностью бросает на тебя взгляд, затем снова отводит его в сторону.]];
			[4] = [[-- Я не могу так больше. Если это конец -- давай честно признаем это... Но нельзя оставаться в этом тупике. Я с ума схожу от безысходности!^
			-- Я, я, я... Ты думаешь только о себе! Ты никогда не думал о том, что чувствую я!? -- взрывается Лариса.]];
			[5] = [[-- Хорошо, давай поговорим об этом. Что с тобой? Почему мы становимся чужими людьми? Что я делаю не так?^
			-- Ты опять о себе... -- в голосе Ларисы чувствуется горечь.]];
			[6] = [[-- А как ты хотела? Я чувствую, что я живу в пустоте. В абсолютном вакууме! В чём смысл такой жизни? Ну, что ты молчишь?^
			-- А ты не думал, чем живу я? Ты только используешь меня. Для своего комфорта. Я -- просто твоя служанка и всегда ей была! -- Лариса вот-вот расплачется.]];
			[7] = [[-- Это какое-то дерьмо! Дело не во мне, я такой-же, каким был 17 лет назад. Это в тебе что-то изменилось! Я привык решать проблемы, решу и эту! -- ты почти теряешь контроль над собой.^
			-- Как всегда, силой? Сломать всё? Давай, ты это умеешь! -- от хлёстких слов Ларисы тебя заливает волнами обиды.]];
			[8] = [[-- Если наши отношения мертвы, то их лучше закончить, чем жить в аду! Артур уже взрослый, он поймёт... Я отдам вам квартиру и уеду, всем будет легче... -- ты почти сам веришь своим словам. Но тебе кажется, что их произносит кто-то другой.^
			-- Ты предал нашу любовь! Растоптал всё! Космонавт! -- в последних словах Ларисы слышится издёвка.]];
			[9] = [[-- Да что ты от меня хочешь, чёрт возьми?!!^
			-- Я уже больше ничего не хочу...]];
			[10] = [[-- Хорошо, выскажись ты, я выслушаю. Пойму. Главное, не молчи!^
			-- Приказываешь, как у себя, там? -- Лариса в первый раз подняла свой взгляд и тебе стало мучительно больно.]];
			[11] = [[-- Я не приказываю, я просто устал. Посмотри на меня? Мой полёт на Луну будет последним.^
			-- Я тоже устала. Давай просто пойдём спать... -- с мольбой в голосе говорит Лариса.]];
			[12] = [[-- И снова оставим проблему нерешённой? Тебя устраивает это?^
			-- Я -- мертва. Мне уже всё-равно. Просто оставь меня в покое.]];
			[13] = [[-- Я хотел бы исправить всё. Но мне нужно понимать, что происходит.^
			-- Ты должен чувствовать. В этом проблема. Ты больше не чувствуешь.]],
			[14] = [[-- Я такой же, каким был всегда! А вот ты...^
			-- Я тоже больше ничего не чувствую... -- почти шёпотом произносит Лариса.]];
			[15] = [[-- Всё это повторялось тысячу раз. Я больше не могу, извини. Когда я вернусь...^
			Звук телефонного вызова прервал тебя.^
			-- Ну, возьми трубку, ответь. Что же ты. -- с этими словами Лариса вышла из комнаты.
			]];
		};
	};
	talk_step = 0;
	description = function(s)
		if last_chance then
			p [[Ты смотришь на испуганное лицо Ларисы и понимаешь, что между вами -- пропасть. В её глазах
			читается боль и мольба. {$fmt em|Её глаза}. Они жгут твою совесть.]]
			enable 'глаза'
		else
			p [[Тебе кажется, что Лариса
	почти не изменилась за все эти 17 лет. Но в последние годы ваш брак трещит по швам.
	Раздражение, затаённые обиды и ссоры. Ты задыхаешься от отсутствия любви, как и она. Что стало причиной разлада? Твоя работа? Её усталость? Можно ли вырваться из этой западни?]];
		end
	end;
	found_in = 'home';
	talk2 = false;
	before_Attack = function(s)
		if mission then
			p [[Ты чувствуешь, как {$fmt em|они} подталкивают тебя к последней черте, убеждая тебя, что это единственный выход. Ты едва сдерживаешься.]]
		else
			p [[Тебя захлёстывает волна болезненной агрессии, но ты не поддаёшься ей.]];
		end
	end;
	before_Talk = function(s)
		if s.talk2 then
			if isDaemon'телефон' then
				p [[-- Какая-то пелена. Не понимаю, что на меня нашло...^
				-- Телефон звонит. Наверное, это по работе. -- говорит Лариса. -- Ответишь?]]
				return
			end
			p [[-- Давай попробуем ещё раз? С чистого листа. -- произносишь ты. И сразу же ощущаешь как будто вязкая тёмная пелена вдруг спала с твоего сердца.^
			Лариса ничего не ответила, но только крепче прижалась к тебе.^
			-- Прости меня...]];
			DaemonStart'телефон'
			return
		end
		s.talk_step = inc_clamp(s.talk_step, #s.talk)
		if s.talk_step == #s.talk then
			if not last_chance then
				DaemonStart'телефон'
			end
			remove(s)
		end
		if s.talk_step == #s.talk and mission then
			place(s, here())
			if last_chance then
				p [[-- Мне нужна помощь.^-- О чём ты говоришь?^-- Сам не знаю. Это кошмар. Кажется, я схожу с ума.]]
			elseif s:once'ringq' then
				p [[-- Всё это повторялось тысячу раз. Я больше не могу, извини. Когда я вернусь...^
			Звук телефонного вызова прервал тебя.^
			-- Ну, возьми трубку, ответь. Что же ты. -- с этими словами Лариса направилась к выходу.^
			-- Стой, чёрт возьми! Нам не помешает проклятый телефон, чтобы расставить все точки над i!]]

			else
				p [[-- Это наверняка по работе. Ответь.]]
			end
		else
			p(s.talk[s.talk_step])
		end
	end;
	before_Smell = [[Едва уловимый запах духов.]];
	['before_Touch,Kiss,Taste'] = function(s)
		if s.talk2 then
			p [[Ты поглаживаешь Ларису по волосам.]]
			return
		end
		if in_t(s.talk_step, {3, 10, 11, 13, 14}) then
			p [[Внезапно, поддавшись интуиции, ты подходишь к Ларисе и обнимаешь её. Она делает неуверенное движение, пытаясь отстраниться, но затем прижимается к тебе.]]
			s.talk2 = true
		else
			p [[Ты пытаешься обнять жену, но она отстраняется от тебя. Как всегда, ты выбрал неудачный момент.]]
		end
	end;
}:attr'scenery,animate':with {
	Careful {
		-"глаза";
		nam = 'глаза';
		before_Kiss = function(s)
			mp:xaction("Kiss", _'жена')
		end;
		description = [[В глазах Ларисы ты видишь своё {$fmt em|отражение}.]];
	}:disable():with {
		Ephe {
			-"отражение";
			description = function(s)
				walkin 'stage9'
			end;
		}
	}
}
cutscene {
	nam = 'stage9';
	title = 'Луна-9';
	text = {
		[[Ты смотришь в глаза Ларисы. Время постепенно замедляется, а затем останавливается. В глазах твоей жены -- ты сам. Тебе становится страшно. На короткий миг ты видишь себя таким, каким ты есть на самом деле. Но и этого
		оказывается достаточно...]];
		[[Достаточно для того, чтобы вселенная внутри тебя взорвалась вся разом. В твоих глазах -- слёзы. В твоём подсознании нет уголка, в котором бы не таилась смерть. Тебе кажется, что твоя психика не может выдержать такого напряжения.]];
		[[Где ты? Существуешь ли ты или это чей-то ужасный сон? Сон лунной принцессы? Ты снова смотришь в глаза Ларисы. Они заполняют весь мир.]];
	};
	next_to = 'flowers';
}

room {
	nam = 'flowers';
	req = false;
	-"поляна,трава";
	enter = function(s)
		s:daemonStart()
		pic_set '14'
	end;
	daemon = function(s)
		local t = {
			"Мимо тебя порхает бабочка.";
			"Мимо пролетают стрекозы.";
			"Ты слышишь, как заливаются птицы.";
			"Ты видишь, как рядом с Ларисой села бабочка.";
			"Ты слышишь гудение шмеля.";
			"Ты видишь в небе белого голубя.";
			"Ты видишь, как ветер шевелит пшеничные локоны Ларисы.";
			"Ты слышишь стрекотание кузнечиков.";
		}
		if time() % 4 == 1 then
			p(t[rnd(#t)])
		end
	end;
	before_Wake = [[Если это и сон, то тебе не хочется просыпаться.]];
	['before_Walk,Enter'] = function(s, w)
		if w ^ 'лариса' then
			return false
		end
		p [[Тебе не хочется уходить.]]
	end;
	title = [[Цветочная поляна.]];
	dsc = [[Вы сидите с Ларисой в траве на поляне, окружённые цветами. По весеннему небу плывут кучевые облака.
	Недалеко от вас находится зелёная роща. Солнце ещё не поднялось высоко над горизонтом и ты чувствуешь приятную прохладу утра.]];
	before_Smell = [[Ты чувствуешь душистый запах цветов.]];
	before_Listen = function(s)
		if s.req then
			DaemonStop(here())
			walkin 'reality'
		else
			p [[Ты слышишь гул насекомых и пение птиц.]];
		end
	end;
}:attr'supporter':with {

	Distance { -"облака", description = [[Кучевые облака, словно парусные корабли медленно плывут в лазурном небе.]] };
	Distance { -"небо", description = [[Как же ты соскучился по настоящему небу!]] };
	Distance { -"солнце", description = [[Солнце своим тёплым светом ласкает вас с Ларисой.]] };
	Distance { -"роща", description = [[Ты видишь, как ветер шелестит зелёной листвой.]]; };
	Distance { -"бабочка", description = [[Здесь много бабочек. Они похожи на летающие цветы.]] };
	Distance { -"шмель|кузнечик|стрекозы|стрекоза", description = [[Насекомые повсюду. Тебе нравится слышать звуки насекомых.]] };
	Distance { -"голубь", description = [[Ты видишь белого голубя. Какой он красивый!]] };
	obj {
		-"цветы|цветок";
		description = [[Цветы повсюду! Вы просто окружены цветами: красными, синими, зелёными, жёлтыми, белыми. Им нет числа!]];
		['before_Take,Pull,Tear'] = function(s)
			if not have'цветок' then
				p [[Ты сорвал цветок.]]
				take 'цветок'
			else
				p [[У тебя уже есть один.]]
			end
		end;
	}:attr'scenery';
	obj {
		nam = 'лариса';
		-"Лариса,жена";
		["before_Attack,Push"] = [[Странная мысль, которая уплыла из твоей головы словно облако.]];
		before_Smell = [[Лариса пахнет цветами.]];
		["before_Kiss,Touch,Taste,Pull"] = [[Лариса тихонько смеётся. Её смех похож на журчание прохладного ручейка.]];
		talk = 0;
		before_Talk = function(s)
			local t = {
			[[-- Это сон?^
			-- Наверное, это сон. Немного грустно, да?]];
			[[-- Я где-то слышал, что сон -- это такая же реальность. Только с другими законами.^
			-- Какая ерунда! -- смеётся Лариса.]];
			[[-- Ты такая красивая. А где Артур? -- внезапно вспоминаешь ты имя сына.^
			-- Он играет там. -- Лариса показала тебе место, где играет Артур и ты услышал радостный детский смех.]];
			[[-- Мне так хорошо здесь. Я бы хотел остаться с тобой и с Артуром здесь навечно.^
			-- К сожалению, сны заканчиваются -- в голосе Ларисы чувствуется грусть.]];
			[[-- Только не этот! Ты будешь ждать меня? Я вернусь!^
			-- Да. Только знаешь. Приходи ты, сам. Пусть тот, другой... Другие... Пусть {$fmt em|они} никогда не возвращаются.]];
			[[-- Я обещаю. -- Не вполне понимая о чём ты говоришь, но чувствуя искренность собственных слов, произносишь ты твёрдо.^
			-- Я буду ждать. Ну вот... Тебя зовут... Слышишь?]];
			}
			if here().req then
				p [[-- Я хочу остаться здесь навсегда.^
				-- Прислушайся, ты ничего не слышишь? Кажется тебя зовут!]];
				return
			end
			s.talk = s.talk + 1
			p(t[s.talk])
			if s.talk == #t then
				here().req = true
			end
		end;
		description = function(s)
			p [[Лариса смотрит на тебя с улыбкой. В её глазах играют озорные искорки.
			Пшеничные волосы собраны в хвост с помощью заколки в виде бабочки.^^
			Лариса одета в белую рубашку и голубую юбку, украшенную узором в виде маков. Она так молода!
			Ты пытаешься вспомнить сколько тебе лет и не можешь этого сделать.]]
		end;
	}:attr'scenery';
}
obj {
	nam = 'цветок';
	-"цветок";
	before_Smell = [[Цветок пахнет чудесно!]];
	description = [[Какой красивый. Тебе немного жаль, что ты решил его сорвать.]];
	before_Give = function(s, w)
		if w ^ 'лариса' then
			p [[Ты протягиваешь цветок Ларисе и она бережно берёт его. Её руки кажутся такими хрупкими!]]
			remove(s)
		else
			return false
		end
	end;
}
cutscene {
	nam = 'reality2';
	enter = function()
		if not instead.tiny then
			fading.set { 'fadewhite', delay = 60, max = 64 }
		end
		pic_set'7'
	end;
	title = [[Выписка из заключения комиссии по инциденту на "Луна-9"]];
	text = {
		[[Комиссия, изучив предоставленные материалы, сделала следующие {$fmt em|выводы}:^^
1) Происшедшее на базе {$fmt em|следует} считать следствием {$fmt em|изменённого сознания космонавтов}, находящихся на базе во время инцидента;^
2) Изменённое сознание было вызвано газом, выбросы которого сопровождали деятельность космонавтов во время инцидента;^^

В связи с этим, комиссия единогласно {$fmt em|рекомендует} отстранить от полётов:^^
1) Громова Бориса Петровича;^
2) Катаева Александра Сергеевича;^
3) Чжан Яна;^
4) Лю Ливея.^^
Кроме того, комиссия считает целесообразным пересмотреть правила техники безопасности при работе на станции "Луна-9".]]
	};
	next_to = 'reality3';
}

cutscene {
	nam = 'reality3';
	enter = function()
		if not instead.tiny then
			fading.set { 'fadewhite', delay = 60, max = 64 }
		end
		pic_set'7'
	end;
	title = false;
	text = {
		[[-- Знаешь, когда ты был {$fmt em|там}, и мне сказали, что связь потеряна, я ...^
		-- Не надо, милая.  Больше я никуда не полечу.^
		-- Я не о том. Послушай. Я видела такой сон... Там были я и ты -- молодые! И Артур. А ещё, представляешь, целое поле цветов!]];
		[[-- ... Боря, ты что?^]];
	};
	next_to = 'theend';
}

cutscene {
	nam = 'reality';
	enter = function(s)
		pic_add '8'
	end;
	title = 'Луна-9';
	text = {
		[[-- Командир, командир, очнись! -- слышишь ты сквозь сон знакомый голос.^
		... -- Где я?]];
		[[-- На базе "Луна-9", командир...]];
	};
	next_to = 'reality2';
}

cutscene {
	title = false;
	noparser = true;
	nam = 'theend';
	enter = function()
		snd.music'mus/end.ogg'
		if not instead.tiny then
			fading.set { 'fadewhite', delay = 60, max = 64 }
		end
		pic_set'14'
	end;
	dsc = fmt.c[[{$fmt b|Луна-9}^^
{$fmt em|Пётр Косых / Январь 2021}^
{$fmt em|Графика: Пётр Косых, фотография из НАСА}^
{$fmt em|Трек: Novus Initium by Alexander Nakarada}^
{$fmt em|Тестирование: Oleg Bosh, Khaelenmore Thaal, Zlobot, Excelenter, V.V., Kerber, PholaX}.^^
Спасибо вам за прохождение игры!^
Если вам понравилось, вы можете найти похожие игры на:^^
{$link|http://instead-games.ru}^
{$link|https://instead.itch.io}^^
А если хотите написать свою историю, добро пожаловать на:^
{$link|https://instead3.syscall.ru}^^
{$fmt b|КОНЕЦ}^^
{@ walk галерея|Галерея}
]];
}

cutscene {
	nam = 'галерея';
	title = false;
	text = function(s, n)
		mp:clear()
		if n == 17 then
			return false
		end
		instead.need_fading(true)
		if n == 1 then
			pic_set(tostring(n))
			pic_add('2')
			pic_add('3')
		elseif n > 2 and n < 14 then
			pic_add(tostring(n + 1))
		end
		local t = {
			'Окно',
			'Звонок',
			'Прибытие',
			'Арго-3 и лунный модуль',
			'На Луне',
			'Луноход',
			'Лунное явление',
			'Луна-9',
			'Электростанция',
			'Китайский лунный модуль',
			'Трансмиттер',
			'Лунная принцесса',
			'Во дворце лунной принцессы',
			'Цветочная поляна',
			'Разработка игры',
		}
		pn(fmt.c(fmt.b(t[n])))
		p(fmt.c(fmt.img('gfx/big/'..tostring(n).. '.png')))
	end;
	next_to = 'theend';
}

global 'last_chance' (false)
room {
	nam = 'home';
	title = "гостиная";
	-"гостиная,комната";
	out_to = function()
		if isDaemon 'телефон' then
			p [[Нужно ответить на звонок. Это с работы.]]
			return
		end
		p [[Ты хочешь решить проблему, а не бежать от неё.]];
	end;
	before_Wake = function(s)
		if mission then
			p [[Не получается!]]
		else
			return false
		end
	end;
	dsc = function(s)
		p [[Ты находишься в гостиной.]]
		if _'#win':has'open' then
			p [[Сквозь окна ты видишь ночную тьму.]]
		else
			p [[Сквозь закрытые окна ты видишь ночную тьму.]];
		end
		if seen 'жена' then
			p [[В комнате только ты и твоя жена Лариса.]]
			if _'жена'.talk_step == 0 then
				p [[Ты собираешься с духом, чтобы поговорить с Ларисой о ваших отношениях.^^]]
				p [[В комнате царит напряжённая тишина.]]
			end
		end
	end;
	before_Listen = function(s, w)
		if isDaemon 'телефон' then
			p [[Ты слышишь мелодию вызова.]]
			return
		end
		if w and w ^ 'жена' then
			p [[Лариса молчит.]]
		else
			p [[Стоит звенящая тишина.]]
		end
	end;
	["before_Ring,Answer"] = function(s)
		if isDaemon 'телефон' then
			pic_add '2'
			DaemonStop 'телефон'
			if mission then
				p [[-- Да!^-- Что же ты медлишь.  Или ты забыл меня? -- ты с ужасом слышишь знакомый глубокий голос.^-- Сколько ещё нужно тебе страданий чтобы понять, что я твоя принцесса? К делу! {$fmt em|Мы} устали ждать! Скорее! Я не откажу тебе ни в чём и никогда!^
				Лариса испуганно смотрит на тебя.^
				-- Кто это? По работе?]]
				last_chance = true
				_'жена'.talk2 = false
				_'жена'.talk_step = #_'жена'.talk
			else
				walk 'разговор'
			end
			return
		end
		return false
	end;
}: with {
	Ephe { -"тьма,ночь"; description = [[Уже совсем поздно.]] };
	Ephe { -"тишина"; before_Listen = [[Ты слушаешь тишину или тишина слушает тебя?]] };
	obj {
		nam = '#win';
		-"окна|окно";
		description = "За окнами -- тьма.";
		before_LetIn = "Неуместная мысль.";
	}:attr 'static,concealed,openable,enterable';
	Furniture {
		nam ='столик';
		-"столик,стеклянный столик,стол";
		description = [[Стеклянный столик стоит посреди гостиной.]];
		before_Enter = [[Столик хрупкий, лучше этого не делать.]];
	}:attr 'supporter':with {
		obj {
			-"телефон,мобильный|трубка";
			nam = 'телефон';
			init_dsc = "На столике лежит телефон.";
			description = [[Твой мобильный телефон.]];
			before_Take = function(s)
				if isDaemon(s) then
					here():before_Answer()
					return
				end
				return false
			end;
			before_SwitchOff = [[Ты должен оставаться на связи.]];
			daemon = function(s)
				p [[Ты слышишь как звонит твой мобильный.]];
			end;
		}:attr 'switchable,on'
	};
}

cutscene {
	nam = "разговор";
	enter = function(s)
		remove 'телефон'
	end;
	text = {
		[[-- Да, слушаю!^
		-- Борис, извини, что так поздно. Но тут такое дело... Старт переносится. Тебе нужно завтра приехать.]];
		[[-- Завтра? Что произошло?^
		-- Я понимаю, выходные... Но у нас ситуация... Потеряна связь с лунной вахтой. Была надежда, что это временные проблемы, но они не выходят на связь уже два дня. Никаких сигналов от них.]];
		[[-- Что это может означать? Метеорит?^
		-- Неизвестно. Принято решение перенести старт. Китайцы настаивают, да и мы хотим помочь ребятам, если... Если они ещё живы.]];
		[[-- Когда?^
		-- Приезжай, всё узнаешь. И.. Передай Ларисе мои извинения... У тебя всё в порядке? Голос какой-то...]];
		[[-- Всё в порядке, Саша, завтра буду.^
		-- Хорошо, до встречи.]],
		[[Ты смотришь в ночное окно. В затянутом дымкой осеннем небе не видно звёзд.]];
	};
	next_to = 'title'
}
cutscene {
	nam = 'badend1';
	title = 'Луна-9';
	text = [[Экипаж "Арго-3" не сумел выйти на лунную орбиту за время облёта обратной
	стороны Луны. Корабль продолжил своё движение и направился обратно к Земле...^^
	Но всё могло быть по-другому.]];
	onexit = function(s)
		snapshots:restore()
		mp:clear()
	end;
}
-- mp.msg.TITLE_INSIDE = "{#if_has/#where,container,в,на} {#where/пр,2}";
cutscene {
	nam = 'title';
	title = "Луна-9";
	enter = function(s)
		pic_add '3'
	end;
	text = [[15 ноября 2043 года пилотируемый космический корабль "Арго-3" успешно достиг орбиты Луны. На 17 дней раньше запланированного срока.^^
	Командир: Борис Громов^
	Пилот командного модуля: Сергей Чернов^
	Пилот лунного модуля: Александр Катаев^^
	Миссия: cмена вахты на российско-китайской лунной базе "Луна-9". Выяснение причины пропажи связи, спасение экипажа.
	]];
	next_to = 'кресло';
	exit = function()
		p [[Ты медленно пробуждаешься. Пристёгнутый к креслу в довольно неудобной для сна позе, ты несколько секунд смотришь сквозь носовые иллюминаторы. Часть обзора загораживает посадочный модуль. А на фоне его ты видишь яркую, заполняющую всё Луну.^^
	Слева и справа от тебя, к своим креслам пристёгнуты Александр и Сергей. Они ещё спят.]];
		DaemonStart 'comp'
		snapshots:make()
		gravity = false
	end
}

Verb {
	'#ClipOff',
	'[рас|от]стегн/уть',
	'{noun}/вн : ClipOff';
	':ClipOff';
}

Verb {
	'#ClipOn',
	'[за|при]стегн/уть',
	'{noun}/вн : ClipOn';
	':ClipOn';
}

function mp:ClipOff(w)
	if not w or w == me() then
		if not _'belts':visible() then
			p [[Ты не видишь здесь ремней.]]
			return
		end
		p [[Попробуй расстегнуть или застегнуть ремни.]]
		return
	end
	p (w:Noun 'вн', " нельзя расстегнуть.");
end

function mp:ClipOn(w)
	if not w or w == me() then
		mp:ClipOff()
		return
	end
	p (w:Noun 'вн', " нельзя застегнуть.");
end
obj {
	nam = 'belts';
	-"ремни|ремень";
	["Worn,ClipOn"] = function(s)
		if me():inside('кресло') or me():inside('place') then
			p [[Ты уже пристёгнут.]]
			return
		end
		if here()^'moonmod' then
			mp:xaction("Enter", _'place')
		else
			mp:xaction("Enter", _'кресло')
		end
	end;
	["Disrobe,ClipOff"] = function(s)
		if not me():inside('кресло') and not me():inside('place') then
			p [[Но ты не пристёгнут!]]
			return
		end
		if here()^'moonmod' then
			p [[Ты расстёгиваешь ремни и покидаешь стойку.]]
			walkout 'moonmod'
		else
			p [[Ты расстёгиваешь ремни и выплываешь из кресла.]]
			walkout 'модуль'
		end
	end;
	description = function(s)
		p [[Крепкие надёжные ремни, с помощью которых космонавты фиксируют своё положение во время полёта.]]
		if where(me()) ^ 'кресло' or where(me()) ^ 'place' then
			p [[Ремни застёгнуты.]]
		else
			p [[Ремни расстёгнуты.]]
		end
	end;
}:attr 'concealed,static';
VerbExtend {
	'#GetOff',
	'из {noun}/рд,scene: GetOff'
}
local start_time = 11 + 32*60 + 67*60*60;
function dark_side()
	return _'comp'.dist < 532 and (math.floor(_'comp'.otime / (33 * 60)) % 2 == 0)
end

door {
	-"люк";
	nam = 'люк';
	found_in = { 'модуль', 'sect2' };
	door_to = function(s)
		if here() ^ 'модуль' then
			return 'sect2';
		end
		return 'модуль'
	end;
	description = [[Этот люк связывает командный и служебный отсеки.]];
	before_Open = function(s)
		if not _'модуль'.engine then
			p [[Что ты забыл в служебном отсеке?]]
			return
		end
		if here()^'sect2' and _'#дверь':has'open' and s:hasnt'open' then
			p [[Нужно закрыть дверь в агрегатный отсек!]]
			return
		end
		return false
	end;
	dsc = function(s)
		if here() ^'модуль' then
			return
		else
			p 'Люк в командный отсек '
		end
		if s:has'open' then
			p 'открыт.'
		else
			p 'закрыт.'
		end
	end;
}:attr 'static,openable';

room {
	nam = 'модуль';
	-"командный отсек,корабль";
	title = "Командный отсек";
	rot = true;
	reverse = false;
	marsh = false;
	engine = false;
	A = false;
	B = false;
	dsc = function(s)
		if not dark_side() then
			p [[В командном отсеке светло.]];
		else
			p [[Неяркий свет звёзд и пепельный свет Луны освещают командный отсек.]]
		end
		if s.rot then
			p [[Корабль медленно вращается вокруг своей оси.]]
		end
		if not dark_side() then
			pr [[Ты видишь, как яркие солнечные лучи проникают сквозь иллюминаторы]];
			if s.rot then
				p " и скользят по стенам."
			else
				p "."
			end
		end
		p [[Позади кресел расположен люк, ведущий в служебный отсек.]]
	end;
	['before_Open,Close'] = function(s, w)
		if w^'люк' and me():where() ^ 'кресло' then
			p [[Из кресла ты не можешь сделать это.]]
			return
		end
		return false
	end;
	before_Answer = function(s)
		if _'#radio'.ack then
			mp:xaction("Ring", _'#radio')
			return
		end
		return false
	end;
	before_Listen = function(s)
		if s.engine and not _'модуль'.B then
			p [[Ты слышишь звуковой сигнал о неполадках, который издаёт бортовой компьютер.]]
			return
		end
		return false
	end;
	before_Wait = function(s)
		if dark_side() and _'comp'.speed > 2.0 then
			p(string.format("Скорость Арго-3 составляет %.02f км/с. Если не снизить скорость, то после того как корабль обогнёт обратную сторону Луны, он направится обратно к Земле. Не время ждать -- время действовать!", _'comp'.speed))
			return
		end
		update_comp(5 * 60) -- 5 min
		return false
	end;
}:with {
	Ephe { nam = '#лучи', -"лучи,Солнц*",
		description = function(s)
			if dark_side() then
				p "Сейчас корабль находится в тени Луны, поэтому Солнца не видно."
			else
				p "Солнечные лучи очень яркие. Корабль вращается, чтобы не допустить перегрева."	end
		end
	};
	Careful { nam = '#win', -"иллюминаторы/но|иллюминатор/но",
		description = function(s)
			p [[Иллюминаторы, как всегда, сильно запотевают.]]
			if not dark_side() then
				p [[При ярком освещении звёзды едва различимы. А вот вид необычно громадной Луны поражает своей грандиозностью.]];
			else
				p [[Сейчас, когда корабль находится в тени Луны, звёзды выглядят необычно ярко.]]
			end
		end
	};
	Careful {
		nam = '#radio';
		ack = false;
		-"радио,ЦУП|Заря";
		description = [[Радио невозможно увидеть. Оно встроено в корабль.]];
		before_SwitchOff = [[Не стоит этого делать.]];
		["before_SwitchOn,Talk"] = function(s)
			mp:xaction("Ring", s)
		end;
		before_Ring = function(s)
			if dark_side() then
				p [[Пока корабль плывёт над обратной стороной Луны связь с ЦУП невозможна.]]
				return
			end
			if s.ack and _'comp'.speed < 2 then s.ack = false end
			if not s.ack then
				if _'comp'.speed < 2 then
					s:daemonStop()
					walk 'stage2'
					return
				end
				p [[Сейчас нет необходимости связываться с ЦУП.]]
				return
			end
			if me():where() ~= _'кресло' then
				p [[Сначала нужно вернуться в кресло.]]
				return
			end
			pn [[-- Заря, Арго-3. Обстановка нормальная. Всё штатно. Готовимся к манёвру.]]
			p [[-- Вас понял, Арго-3. Приступайте.]]
			s.ack = false
			-- s:daemonStop()
			return
		end;
		daemon = function(s)
			if not here() ^ 'модуль' then
				return
			end
			if s:once 'ack' then
				p [["Перемен, требуют наши сердца!..."^^]]
				pn [[-- Арго-3, Заря. Как слышно? Приём? Доложите обстановку.]]
				p [[Ты видишь, что Александр и Сергей проснулись и потягиваются на своих креслах, разминая мышцы.]]
				_'Александр'.sleep = false
				_'Сергей'.sleep = false
				s.ack = true
				return
			end
			if dark_side() then
				return
			end
			if time() % 3 ~= 1 or not me():inroom()^'модуль' then
				return
			end
			if s.ack then
				pn [[-- Арго-3, Заря. Как слышно? Почему не выходите на связь?]]
				p [[-- Командир, надо {$fmt em|ответить}! -- беспокоится Александр.]]
				return
			end
			if _'comp'.speed < 2 then
				if s:once 'stage2' then
					pn [[Вдруг, радио оживает и пространство отсека наполняется звуком позывных с ЦУП.]]
				end
				pn [[-- Арго-3, Заря! Ответьте!]]
			end
		end;
	};
	Distance { -"Луна,кратер*,морщи*,рисун*",
		description = function(s)
			if not dark_side() then
				p [[Изрытая кратерами поверхность завораживает. Луна -- всегда такая привычная, сейчас выглядит угрожающе чужой. Некоторое время ты отрешённо следишь за причудливым рисунком её морщин.]]
			else
				p [[Даже находясь в тени, лунная поверхность отражает достаточно звёздного света, чтобы ты мог различить грубый рисунок её поверхности.]]
			end
		end
	};
	Distance { -"звёзды/но,мн",
		description = function(s)
			if not dark_side() then
				p [[Звёзды там, только их не видно. Мешает яркий свет.]]
			else
				p [[Яркие россыпи звёзд. И каждая звезда -- свой мир. Такой близкий и такой бесконечно далёкий.]]
			end
		end
	};
	Distance { -"посадочный модуль", desciption = [[Это лунный модуль. Он должен доставить вас на базу "Луна-9", а затем вернуть обратно. ]] };
	Prop { nam = 'wall', -"стены/но,жр|стена" };
	Ephe { -"свет",
		description = function()
			if not dark_side() then
				p [[Солнце светит в боковые иллюминаторы. А сквозь носовые в корабль проникает серебряный свет Луны.]]
			else
				p [[Сейчас корабль освещается только светом звёзд и пепельным светом Луны.]]
			end
		end
	};
	Prop {
		-"кресла/мн,ср|левое кресло|правое кресло";
		description = [[В командном отсеке установлены три кресла. Твоё кресло командира -- среднее.]];
	};
	obj {
		title = 'в кресле';
		nam = 'кресло';
		-"кресло";
		inside_dsc = 'Ты пристёгнут ремнями к креслу командира экипажа.';
		description = [[Кресло командира экипажа.]];
		before_LetIn = function(s)
			p [[Ты подлетаешь к креслу командира и пристёгиваешься.]]
			place(me(), s)
		end;
		before_LetGo = function(s)
			p [[Тебе мешают ремни.]]
		--	mp:xaction("ClipOff", _'belts')
		end;
		obj = { 'belts' };
	}:attr 'supporter,open,concealed,enterable,static';
	obj {
		nam = 'Сергей';
		-"Сергей,Серёжа";
		sleep = true;
		description = function(s)
			p [[Сергей Чернов -- пилот командного модуля. Занимает кресло слева от командирского.]]
			if s.sleep then
				 p [[Сергей спит.]];
			end
		end;
		['before_WakeOther,Attack,Touch,Talk'] = function(s)
			if s.sleep then
				p [[Пусть поспит ещё немного. ЦУП скоро разбудит его и Сашу по радио. Пока ты можешь просто {$fmt em|подождать}.]];
				return
			elseif mp.event == 'Talk' then
				if _'comp'.prog then
					pn [[-- Программа активирована?]]
					p [[-- Да, всё готово.]]
					return
				end
				if s:where().rot and _'comp'.speed > 2 then
					pn [[-- Сережа, активируй программу стабилизации корабля.]]
					p [[-- Понял. Активирую. -- Сергей быстро вбил код программы в компьютер.]];
					_'comp'.prog = 1;
					return
				end
				if not s:where().reverse then
					pn [[-- Сергей, теперь программу разворота на 180 градусов.]]
					p [[-- Сделано, командир.]]
					_'comp'.prog = 2
					return
				end
				if not s:where().marsh then
					pn [[-- Программу включения маршевого двигателя на торможение.]]
					pn [[-- Программу включения маршевого двигателя на 17 секунд ввёл.]];
					_'comp'.prog = 3
					return
				end
				if s:where().engine then
					if _'comp'.speed < 2 then
						p [[-- Успели!^
						-- Я тоже рад, командир! Надеюсь, ЦУП даст добро на продолжение миссии, хотя мне и придётся торчать здесь одному на орбите присматривая за "Арго".]];
						if not s:where().rot then
							p [[^-- Активируй программу пассивного термального контроля.^
							-- Сделано!]];
							_'comp'.prog = 4
						end
						return
					end
					if not s:where().A then
						p [[-- Сергей, что происходит?^-- Какая-то проблема. Что на компьютере?^-- Сейчас посмотрю!]];
					elseif _'клапан'.on then
						p [[-- Предохранительный клапан закрыт.^
						-- Хорошо, я переключился на топливный контур B и скорректировал программу.^
						-- Активировал?^
						-- Нет ещё. Выполнять?^
						-- Да.^
						-- Программа включения маршевого двигателя активирована!]];
						_'comp'.prog = 3
					else
						p [[-- Проблема с клапаном подачи топлива!^
						-- Возможно, короткое замыкание в контуре! Я могу переключиться на контур B, только...^
						-- Что?^
						-- Нет гарантий, что при включении двигателя не откроется и клапан контура A, а тогда...^
						-- Что делать?^
						-- Можно перекрыть предохранительный клапан контура A. В агрегатном отсеке к ним предусмотрен доступ.]]
					end
					return
				end
			end
			return false
		end;
	}:attr 'animate';
	obj {
		nam = 'Александр';
		-"Александр,Саша";
		sleep = true;
		['before_WakeOther,Attack,Touch,Talk'] = function(s)
			if s.sleep then
				p [[Пусть поспит ещё немного. ЦУП всё-равно скоро его разбудит. Пока ты можешь просто {$fmt em|подождать}.]];
				return
			elseif mp.event == 'Talk' then
				if _'модуль'.engine then
					p [[-- Саша, что с орбитой?^]]
					if _'comp'.speed < 2 then
						p [[-- Выходим! Уверен, "Заря" одобрит высадку, даже не смотря на неполадки с топливной системой и мы оставим свои следы на Луне! Ты уже {$fmt em|разговаривал с ЦУП}, командир?]]
					else
						p [[-- Почти 2-я космическая... Будем болтаться как в цирке на батуте.]]
					end
					return
				end
				p [[-- Как настрой, Саша?^
				-- Всё в порядке, командир.]]
				return
			end;
			return false
		end;
		description = function(s)
			p [[Александр Катаев -- пилот лунного модуля. Занимает правое кресло от командира.]]
			if s.sleep then
				p [[Пока он спит.]];
			end
		end;
	}:attr 'animate';
	obj {
		nam = 'comp';
		time = 0;
		badend = false;
		dist = 2570;
		speed = 2.536;
		otime = 0;
		prog = false;
		start = start_time;
		fltime = start_time;
		-"компьютер,бортовой компьютер";
		dsc = function(s)
			if _'модуль'.engine == 1 and not _'модуль'.B then
				p [[Бортовой компьютер издаёт звуковой сигнал.]]
			else
				p [[Бортовой компьютер помигивает неяркими огоньками.]];
			end
		end;
		description = function(s)
			if s.time == 0 then
				s.time = os.time()
			end
			show_stats()
		end;
		daemon = function(s)
			if not here() ^ 'модуль' then
				return
			end
			update_comp()
			if s.dist < 2200 and s:once'wake' then
				DaemonStart '#radio'
				p [[Внезапно, тишину командного отсека нарушает звук радио.^^
				"Вместо тепла зелень стекла^
				Вместо огня дым!"...^^
				Интересно, кто в ЦУП поставил эту песню?]]
			end
			if s.badend then
				walk 'badend1'
			end
		end;
	}:attr'static':with {
		Careful {
			-"кнопка";
			description = [[Заметная красная кнопка прямоугольной формы.]];
			before_Push = function(s)
				local prog = _'comp'.prog
				if prog == 1 then
					if not dark_side() then
						p [[Для начала манёвра выхода на лунную орбиту, нужно подождать, пока корабль не начнёт огибать обратную сторону Луны.]]
					else
						_'comp'.prog = false
						p [[Ты нажал на кнопку. Послышался гул -- это ненадолго включились маневровые двигатели. Корабль замедлил, а затем совсем прекратил продольное вращение.]]
						_'модуль'.rot = false
					end
				elseif prog == 2 then
					_'comp'.prog = false
					_'модуль'.reverse = true
					p [[Ты нажал на кнопку выполнения программы и снова услышал работу маневровых двигателей. Корабль развернулся так, чтобы сопло маршевого двигателя было направлено по ходу движения. Всё готово для того, чтобы начать торможение и переход на лунную орбиту.]]
				elseif prog == 3 then
					if not me():where() ^ 'кресло' then
						p [[Перед торможением надо сесть в кресло.]]
						return
					end
					if _'модуль'.B then
						_'comp'.speed = 1.6
						p [[Не без опаски ты нажал на кнопку активации. Послышался низкий гул маршевого двигателя. Все, затаив дыхание, ждали. Наконец, отработав положенное время, двигатель отключился и вновь наступила тишина.]]
						_'comp'.prog = false
						return
					end
					if _'модуль'.marsh then
						p [[Не стоит включать маршевый двигатель, пока не перекрыт предохранительный клапан.]]
						return
					end
					_'comp'.prog = false
					_'модуль'.marsh = true
					p [[Корабль вздрогнул. Со стороны служебного отсека послышался сильный и низкий гул. Это запустился маршевый двигатель. 1, 2, 3, 4, 5... секунд. Вдруг, гул прекратился так же внезапно, как и начался. Что-то пошло не так! Двигатель должен был проработать 17 секунд!]]
					_'comp'.speed = 2.398
					_'модуль'.engine = 1
				elseif _'comp'.prog == 4 then
					_'модуль'.rot = true
						p [[Ты нажал на кнопку выполнения программы и услышал, как на короткое время включились маневровые двигатели. Корабль снова начал медленно вращаться вокруг своей оси.]]
					_'comp'.prog = false
				else
					p [[На космическом корабле стоит быть более осторожным.]]
				end
			end;
		}
	};
	Ephe { -"огоньки,огни", description = function(s)
			if _'модуль'.engine then
				p [[Похоже, у нас проблемы!]]
				return
			end
			p [[Похоже, всё в порядке.]]
		end
	};
	Path {
		-"служебный отсек";
		desc = [[Ты можешь пойти в служебный отсек.]];
		walk_to = 'люк';
	};
}

stick_transfer = function(s, w)
	if w == me() or w ^ '@out_to' then
		mp:xaction("Pull", s)
	elseif w ^ '@u_to' then
		mp:xaction("Push", s)
	elseif w ^ '@d_to' then
		mp:xaction("Pull", s)
	else
		return false
	end
end;


room {
	nam = 'sect2';
	title = "служебный отсек";
	-"служебный отсек";
	dsc = function(s)
		p [[В служебном отсеке почти всё пространство занято различным оборудованием.]];
	end;
	out_to = '#дверь';
	in_to = 'люк';
	onexit = function(s, w)
		if w ^ 'агрегатный отсек' and _'люк':has'open' then
			p [[Агрегатный отсек не герметичен. Сначала следует закрыть люк командного отсека.]]
			return false
		end;
		if w ^ 'модуль' and _'#дверь':has'open' then
			p [[Следует сначала закрыть дверь в агрегатный отсек.]];
			return false
		end
	end
}: with {
	Prop { -"оборудование" };
	door {
		-"дверь";
		nam = '#дверь';
		["before_Open,Close"] = function(s)
			if _'#lever'.on then
				p [[Дверь заблокирована рычагом.]]
				return
			end
			if mp.event == "Open" and _'люк':has'open' and s:hasnt 'open' then
				p [[Агрегатный отсек не герметичен. Сначала нужно закрыть люк в командный отсек.]]
				return
			end
			if _'скафандр':hasnt'worn' then
				p [[Агрегатный отсек не герметичен!]]
				return
			end
			return false
		end;
		description = function()
			p [[Тяжёлая межотсечная дверь покрашена в желто-чёрные цвета. Это напоминает тебе об опасности. Агрегатный отсек не герметичен!]]
			return false
		end;
		door_to = 'агрегатный отсек';
	}:attr'static,scenery,openable';
	Careful {
		-"рычаг";
		nam = '#lever';
		on = true;
		dsc = [[В стену встроен рычаг, блокирующий дверь в агрегатный отсек.]];
		description = [[Рычаг покрашен в красный цвет, чтобы напоминать экипаж об опасности выхода в негерметичный агрегатный отсек.]];
		before_Transfer = stick_transfer;
		['before_Push,Pull'] = function(s)
			if _'#дверь':has 'open' then
				p [[Сначала нужно закрыть дверь.]]
				return
			end
			s.on = not s.on
			if s.on then
				p [[Ты заблокировал межотсечную дверь рычагом.]]
			else
				p [[Ты разблокировал межотсечную дверь рычагом.]]
			end
		end;
	}:attr 'static,~scenery';
	Path { -"агрегатный отсек",
		desc = function(s)
			p "Ты можешь выйти в агрегатный отсек.";
		end;
		walk_to = '#дверь';
	};
	Path { -"командный отсек",
		desc = function(s)
			p "Ты можешь вернуться в командный отсек.";
		end;
		walk_to = 'люк';
	};
	obj {
		-"скафандр";
		nam = 'скафандр';
		radio = false;
		scope = { };
		dsc = function(s)
			if s:inroom() ^ 'sect2' then
				return
			end
			return false
		end;
		description = function(s)
			if s:has'worn' then
				p [[Скафандр в полном порядке.]]
				return
			end
			p [[Ослепительно белый скафандр для выхода в открытый космос.]]
		end;
		after_Wear = function(s)
			enable 'радио'
			return false
		end;
		before_Disrobe = function(s)
			if here() ^ 'sect2' and _'#дверь':has'open'
				or here() ^ 'агрегатный отсек' or
				here() ^ 'sect1' and _'gate':has'open'
				or here().vacuum then
				p [[Без скафандра ты умрёшь!]]
				return
			end
			if (here() ^ 'moonmod' or here() ^'moontech') and _'alex'.state >= 3 then
				p [[Не стоит сейчас снимать скафандр. Это опасно для жизни.]]
				return
			end
			return false
		end;
		after_Disrobe = function()
			disable 'радио'
			return false
		end;
	}:attr'clothing':with {
		Careful { -"радио"; nam = 'радио';
			req = false;
			description = "Радио встроено в скафандр.";
			before_Ring = function(s, w)
				if not w then
					last_talk = false
				end
				mp:xaction("Talk", w)
			end;
			before_SwitchOff = function(s)
				if mission then
					return false
				end
				p [[Не стоит оставаться без радиосвязи.]]
			end;
			daemon = function(s)
				if disabled(s) or s:hasnt'on' then return end
				if time() % 3 == 2 then
					if _'Заря'.req then
						pn(_'Заря'.req)
						return
					end
				end
				if visited'liv' and not disabled 'пар' then
					pn [[-- ... Ястреб, я Заря. Мы больше не наблюдаем преходящее лунное явление. Всё чисто.]]
					pn [[-- Заря, Ястреб. Вас понял. Спасибо за информацию.]];
					disable 'пар'
				end
			end;
			}:attr'switchable,on':disable();
	};

	Careful {
		-"скафандры";
		description = [[Скафандры для выхода в открытый космос.]];
		before_Take = "Зачем тебе все скафандры?";
	}:attr'clothing,~scenery';
}
room {
	-"отсек";
	title = 'агрегатный отсек';
	nam = 'агрегатный отсек';
	dsc = [[В агрегатном отсеке работает дежурное тусклое освещение. Ты видишь здесь: топливные баки, батареи, бачки с водородом, топливные элементы и клапаны.]];
	out_to = 'sect2';
}:with {
	Ephe { -"освещение|свет"; };
	Path {
		-"служебный отсек";
		desc = [[Ты можешь вернуться в служебный отсек.]];
		walk_to = 'sect2';
	};
	Careful {
		-"топливные баки,баки";
		description = [[С ними всё в порядке.]];
	};
	Careful {
		-"бачки";
		description = [[Не похоже, что проблема связана с утечкой водорода.]];
	};
	Careful {
		-"батареи";
		description = [[С электричеством порядок.]];
	};
	Careful {
		-"топливные элементы,элементы";
		description = [[Проблема с маршевым двигателем не связана с топливными элементами.]];
	};
	Careful {
		nam = 'клапан';
		-"предохранительный клапан,клапан";
		on = false;
		before_Turn = function(s)
			s.on = not s.on
			p [[Ты с трудом поворачиваешь ручку клапана.]]
			if s.on then
				p [[Теперь он перекрыт.]]
				_'модуль'.B = true
			else
				p [[Теперь он открыт.]]
				_'модуль'.B = false
			end
		end;
		description = function(s)
			if not s.on then
				p [[Чтобы перекрыть клапан, достаточно его повернуть.]];
			else
			 	p [[Клапан перекрыт.]]
			end
		end;
	}:disable();
	Careful {
		-"клапаны";
		description = function()
			p [[Предохранительные клапаны подачи топлива.]];
			if _'модуль'.A then
				p [[Ты видишь предохранительный клапан контура A.]]
				_"клапан":enable()
			end
		end;
	};
}
function update_comp(delta)
	local side = dark_side()
	if _'comp'.time == 0 then
		_'comp'.time = os.time()
	end
	local flt = _'comp'.fltime
	if delta then
		flt = flt + delta
	else
		local cur = os.time()
		delta = cur - _'comp'.time
		if delta < 0 then
			delta = 0
		end
		if delta > 2*60 then
			delta = 2*60
		end
		flt = flt + delta
		_'comp'.time = cur
	end
	if _'comp'.otime > 0 then
		_'comp'.otime = _'comp'.otime + delta
	end
	-- print(_'comp'.dist, delta)
	_'comp'.fltime = flt
	local dist = _'comp'.dist - (delta*_'comp'.speed)
	if dist < 532 and _'comp'.otime == 0 then
		_'comp'.otime = 1
	end
	if dist < 110 then
		dist = 110
	end
	_'comp'.dist = dist
	if dist > 110 then
		_'comp'.speed = _'comp'.speed + 0.00001 * delta
	end
	if dark_side() ~= side then
		if dark_side() then
			p [[Корабль вошёл в тень Луны. Яркий солнечный свет перестал проникать сквозь иллюминаторы.]]
		else
			p [[Корабль вышел из тени Луны. Яркий солнечный свет залил всё вокруг.]];
			if _'comp'.speed > 2.0 then
				_'comp'.badend = true
			end
		end
	end
end
function get_time(flt)
	local flt = _'comp'.fltime
	local sec = flt % 60
	local min = math.floor(flt / 60 % 60)
	local hh = math.floor(flt / 60 / 60)
	return  string.format("%d  час. %d мин. %d сек.", hh, min, sec)
end
function show_stats()
	pn ([[Время полёта: ]], get_time())
	pn ([[Расстояние: ]], string.format("%.2f", _'comp'.dist), ' км');
	pn ([[Скорость: ]], string.format("%.3f", _'comp'.speed), ' км/с');
	if _'модуль'.engine then
		_'модуль'.A = true
		if _'модуль'.B then
			pn [[Подача топлива: через контур B]];
		else
			pn [[Клапан подачи топлива, контур A: ошибка]]
		end
	end
	if _'comp'.prog then
		local progs = {
			"стабилизация";
			"разворот на 180";
			"вкл. маршевый двигатель";
			"термальный контроль";
		}
		pn ("Программа: ", progs[_'comp'.prog])
		pn [[Ты видишь, что кнопка "выполнить" подсвечена красным.]]
	end
end
global 'stage' (false)
cutscene {
	nam = 'stage2';
	title = 'Командный отсек';
	text = {
	[[-- Заря, Арго на связи!]],
	[[-- Ох, ребята! До чего же мы рады вас слышать!]],
	[[...]],
	};
	next_to = 'moonmod';
	exit = function()
		_'comp'.time = _'comp'.time + 167*60
		pn [[Прошло 2 часа 47 минут...]]
		p ([[Полётное время: ]], get_time())
		take 'скафандр'
		_'скафандр':attr'worn'
		_'alex'.suit = true
		enable 'радио'
		pic_add '4'
	end;
}
door {
	-"дверь";
	nam = 'door1';
	["before_Open,Close"] = [[Дверь управляется с помощью рычага.]];
	description = function(s)
		if here() ^ 'moon1' then
			p [[Эта прямоугольная массивная дверь ведёт внутрь модуля. Возле двери установлен красный рычаг.]]
			return false
		end
		p [[Эта прямоугольная массивная дверь ведёт наружу.]]
		if s:hasnt'open' then
			p [[В лунном модуле нет шлюза, поэтому открытие двери означает разгерметизацию.]]
		else
			p [[В дверном проёме ты видишь Луну.]]
		end
		p [[Возле двери установлен красный рычаг.]];
		return false
	end;
	door_to = function(s)
		if here() ^ 'moon1' then
			if _'buggy'.indoor then
				p [[Тебе мешает пройти луноход.]]
				return
			end
			return 'moontech'
		else
			return 'moon1'
		end
	end
}:attr 'static,openable,scenery':with {
	obj {
		-"рычаг,красный рычаг";
		description = [[С помощью рычага можно управлять выходной дверью.]];
		before_Transfer = stick_transfer;
		["before_Push,Pull"] = function(s)
			if not gravity then
				p [[В твоих планах на сегодня не было выхода в открытый космос.]]
				return
			elseif _'alex'.state == 5 then
				p [[Не стоит открывать дверь, пока модуль не сел на поверхность.]]
				return
			end
			if here() ^ 'moon1' and (_'buggy'.indoor or _'buggy':inroom() ^ 'moontech') then
				p [[Сейчас Александр готовит луноход к выгрузке. Не стоит ему мешать.]]
				return
			end
			if _'door1':hasnt 'open' then
				_'door1':attr 'open'
				p [[Ты открываешь дверь.]]
				return
			else
				_'door1':attr '~open'
				p [[Ты закрываешь дверь.]]
				return
			end
			return false
		end;
	}:attr 'static';
};
global 'know_malapert' (false)
room {
	-"отсек,модуль,корабль";
	nam = 'moontech';
	title = "лунный модуль (технический отсек)";
	u_to = 'moonmod';
	out_to = 'door1';
	dsc = [[В техническом отсеке работает только дежурное освещение. В стене расположена выходная дверь. Путь наверх ведёт в кабину. На потолке установлены блоки для спуска лунохода.]];
}:with {
	Prop { -"потолок" };
	Useless { -"блоки", description = [[Система блоков и тросов используется для ручного спуска лунохода.]] };
	Ephe { -"свет|освещение", description = "Неяркий свет синего спектра." };
	Ephe { -"Луна", description = "Луна там, снаружи модуля."; };
	'door1',
	Path {
		-"кабина",
		desc = "Ты можешь подняться в кабину.";
		walk_to = 'moonmod';
	};
	obj {
		nam = 'buggy';
		-"луноход";
		assembled = false;
		indoor = false;
		before_Attack = function(s)
			if know_parts and not _'запчасти'.got then
				p [[Здесь нет нужных деталей. Нужно что-то более сложное.]]
				return
			end
			return false
		end;
		before_SwitchOn = function(s)
			if me():inside(s) then
				p [[Ты можешь просто ехать в нужном тебе направлении.]]
			else
				p [[Но ты сейчас находишься не в луноходе.]]
			end
		end;
		inside_dsc = function(s)
			p [[Ты сидишь на месте водителя лунохода.]]
			 if _'alex':inside(s) then p [[Рядом сидит Александр.]] end
		end;
		['before_Pull,Push,Take,Transfer'] = function(s, w)
			if not here()^'moon1' then
				if mp.event == 'Take' then p [[Собрался носить луноход с собой?]] return end
				return false
			end
			if not s.indoor and not s.assembled and
					(mp.event == 'Pull' or mp.event == 'Take' or w == me()) then
				s.assembled = true
				p [[Ты крепко хватаешься за луноход и вместе с Александром вам удаётся разложить раму.
				Через несколько минут луноход полностью разложен! Осталось только закрутить крепёжные болты.]]
				enable 'болты'
				enable 'пеленгатор'
				pic_add '6'
				return
			end
			if not s.indoor then
				if mp.event == 'Take' then p [[Собрался носить луноход с собой?]] return end
				return false
			end
			p [[Ты поддерживаешь сложенный луноход. На Луне он весит не больше 30 килограмм. Александр осторожно стравливает тросы и постепенно луноход опускается на лунную поверхность.]]
			s.indoor = false
			disable 'тросы'
		end;
		description = function(s)
			if not s.assembled then
				if s.indoor then
					p [[Александр спускает сложенный луноход на тросах. Тебе нужно помочь ему.]]
				else
					p [[Сейчас луноход находится в сложенном состоянии.]]
				end
			else
				if _'болты'.screw then
					p [[Луноход позволяет передвигаться по Луне со скоростью 20 километров в час.]]
					p [[Луноход оборудован пеленгатором.]];
				else
					p [[Луноход почти готов! Осталось закрутить болты.]]
				end
			end
			return false
		end;
		dsc = function(s)
			if s.indoor then
				p [[Ты видишь в проёме двери сложенный луноход.]]
				return
			end
			return false
		end;
		before_Enter = function(s)
			if here() ^ 'moontech' then
				p [[Кататься в луноходе ты будешь на Луне.]]
				return
			end
			if not s.assembled then
				p [[Но луноход находится в сложенном состоянии.]]
				return
			end
			if not _'болты'.screw then
				p [[Луноход собран не до конца. Нужно закрутить болты.]]
				return
			end
			if not _'болтик'.screw then
				p [[Нужно закрепить переднее крыло. Иначе пыль будет сильно мешать.]]
				return
			end
			if have 'spaceman1' then
				p [[Управлять луноходом с космонавтом в руках?]]
				return
			end
			return false
		end;
		before_Receive = function(s)
			if not s.assembled then
				p [[Но луноход находится в сложенном состоянии!]]
				return
			end
			return false
		end;
	}:attr 'container,open,transparent,enterable,~scenery':with {
		Useless { nam = 'тросы', -"тросы/мн|трос", description = [[Тонкие, но достаточно крепкие.]] }:disable();
		Careful { nam = 'крыло', -"крыло",
			description = function(s)
				p "Крыло лунохода."
				if not _'болтик'.screw then
					p [[Чтобы его закрепить нужен ещё один болтик]]
				else
					p [[Надёжно закреплено!]]
				end
			end;
			before_Receive = function(s, w)
				if w ^ 'болтик' then
					p [[Ты вставил болтик в крыло.]]
					move(w, s)
					return
				end
				p [[В крыло можно вставить только болтик.]]
			end;
		}:attr'static':disable();
		obj { nam = 'пеленгатор',
			-"пеленгатор/но|антенна",
			before_Attack = function(s)
				if know_parts then
					if 	not _'запчасти'.got then
						p [[В пеленгаторе нет нужных лунной принцессе деталей.]]
					else
						p [[Ты уже достал нужные детали.]]
					end
					return
				end
				return false
			end;
			description = function(s)
				p [[Пеленгатор, благодаря узконаправленной антенне, позволяет двигаться на сигналы навигационных маяков.]];
				if s:has 'on' then
					if here()^'base' then
						p [[Лунный модуль находится на востоке.]]
						if know_malapert then
							p [[Пик Малаперта находится на западе.]]
						end
					elseif here() ^ 'malapert' or here() ^ 'device' then
						p [["Луна-9" находится на востоке.]]
					elseif here() ^ 'moon1' then
						p [["Луна-9" находится на западе.]]
					end
					return
				end
				return false
			end;
		}:attr'switchable,static,concealed':disable();
		Useless { nam = 'болты';
			-"болты,крепёжные болты",
			screw = false;
			description = function(s)
				if s.screw then
					p [[Все крепёжные болты закручены!]]
				else
					p [[Болты уже вставлены, осталось только закрутить их.]];
				end
			end;
			["before_Turn,Close"] = function(s)
				if not have 'screw' then
					p [[Но у тебя нет отвёртки!]]
					return
				end
				if s.screw then
					p [[Тут главное -- не переборщить!]]
				else
					p [[Ты затянул крепёжные болты. Заканчивая работу, ты заметил, что переднее правое крыло
					лунохода едва держится на единственном болтике. Нужно найти ещё один!]];
					enable 'крыло'
					s.screw = true
				end
			end;
		}:disable();
	};
	Careful {
		-"оборудование";
		description = function(s)
			if know_station and not controller then
				p [[Твоё внимание привлекает контроллер заряда. Ты берёшь его с собой.]]
				take 'контроллер'
				controller = true
				return
			end
			if know_parts and not _'запчасти'.got then
				p [[Здесь нет нужных для лунной принцессы запчастей.]]
--				take'запчасти'
--				_'запчасти'.got = true
				return
			end
			if s:once'screw' then
				p [[Твоё внимание привлекает универсальная дрель.]]
				enable 'screw'
			else
				p [[С оборудованием всё в порядке.]]
			end
		end;
	}:attr'~scenery,static';
	obj {
		nam = 'screw';
		-"дрель|шуруповёрт|отвёртка";
		init_dsc = [[На стене закреплена дрель.]];
		before_SwitchOn = [[Дрель-шуруповёрт включается во время работы. Не стоит тратить заряд просто так.]];
		description = [[Многофункциональная ручная дрель-шуруповёрт. Выполнена в форме пистолета.]];
	}:attr'switchable':disable();
	'wall',
}


Distance { nam = 'moonsky', -"небо|звёзды/но,мн", description = [[Яркий солнечный свет, отражённый от поверхности Луны, мешает тебе наблюдать звёзды.]]; }:with {
	Distance { -"Земля|серп", description = function(s)
			p [[Голубой серп Земли едва заметен в чёрном небе.]]
			if mission then
				p [[Скоро всё будет кончено. Но лунная принцесса просит тебя не беспокоиться об этом.]]
			end
		end
	};
	Distance { -"Солнце", description = [[Солнце ярко горит в чёрном небе.]] };
}
function before_buggy(s, e, w)
	if eph_event(e) then
		return false
	end
	if w and w:inside 'buggy' then
		return false
	end
	if e == 'Enter' or e == 'Walk' or e == 'Exit' or e == 'GetOff' then
		return false
	end
	if not me():inside'buggy' then
		return false
	end
	return "Лучше сначала слезть с лунохода."
end
cutscene {
	nam = 'stage5';
	title = 'Луна-9';
	text = {
		[[-- Заря, я Ястреб. Китайский космонавт доставлен на базу. Это Лю Ливей. Второго космонавта пока не нашли.^
		-- ... Ястреб, Заря. Он жив?]];
		[[-- Он не пришёл в себя, и мы не понимаем что происходит. Он вроде бы находится в состоянии глубокого сна.^
		-- ... Ястреб, повторите. Мы вас не понимаем.^
		-- Он не приходит в себя! Очень низкие пульс и давление. Как будто находится в коме или глубоком сне. Не знаю, на что это похоже...]];
		[[-- ... Ястреб, Заря. В лаборатории должен быть гидротат норадреналина. Попробуйте вколоть.^
		-- Уже пробовали. Без результатов. Заря, мы выходим на связь через радио в наших скафандрах с ретрансляцией через лунный модуль, но мы не можем таскать скафандры вечно. Нужно время на заправку скафандров и отдых.]];
		[[-- ... Ястреб, Заря. Разрешается двухчасовой отдых. При любых изменениях обстановки, докладывайте немедленно!^-- Заря, Ястреб. Вас понял.]];
	};
	exit = function(s)
		move('buggy', 'base')
		move('spaceman1', 'кровать')
		_'spaceman1'.suit = false
		move('alex', 'liv')
		_'alex'.suit = false
		move(me(), 'liv')
		_'скафандр':attr'~worn'
		move('скафандр', 'suitbox')
		_'скафандр':attr'concealed'
		_'gate':attr'~open'
	end;
}
room {
	nam = 'device';
	vacuum = true;
	title = function(s)
		if mission then
			p "трансмиттер"
		else
			p "Пик Малаперта (запад)";
		end
	end;
	before_Any = before_buggy;
	["before_Walk,Enter"] = function(s, w)
		if w ^ '@e_to' then
			if not me():inside'buggy' then
				return false
			end
			if _'spaceman1':inside'buggy' then
				walkin 'stage5'
			else
				p [[И бросить здесь космонавта?]]
			end
			return
		end
		return false
	end;
	enter = function(s)
		pic_add '11'
		if s:once() then
			p [[Вместе с Александром вы медленно шли по направлению к антенне, которая постепенно открывалась из-за холма,
			ожидая увидеть установленный здесь подвижный модуль радиотелескопа с двухметровым рефрактором.^^
			Однако, добравшись до места вы обнаружили нечто совсем иное...]];
		elseif have'запчасти' then
			_'dev'.fixed = true
			p [[Ты принёс все необходимые запчасти к трансмиттеру. Некоторое время {$fmt em|они} управляли
			тобой, чтобы ты мог восстановить повреждённые узлы. Наконец, всё было готово, чтобы начать процесс переноса.]];
			-- _'Заря'.req = [[-- Ястреб, Беркут. Ответьте! Почему не выходите на связь!]]
			remove'запчасти'
		end
	end;
	out_to = 'malapert';
	onexit = function(s)
		if have'spaceman1' then
			p [[Слишком тяжело ходить с космонавтом в руках.]]
			return false
		end
	end;
	e_to = 'malapert';
	dsc = function(s)
		p [[Ты находишься рядом со странным сооружением, построенным из радиотелескопа. Двухметровый рефрактор обращён на Землю. Рама собрана из рамы радиотелескопа и лунохода. В переплетении проводов ты видишь фрагменты оборудования с лунной станции. В раму встроено кресло. Рядом валяются запчасти лунохода.^^
		Ты можешь вернуться назад на восток.]];
	end;
	e_to = 'malapert';
}:with {
	'moonsky',
	'пыль',
	'грунт',
	Careful {
		-"кресло";
		nam = 'dev';
		fixed = false;
		dsc = function(s)
			mp:content(s)
		end;
		before_LetGo = function(s, w)
			if not w ^ 'spaceman1' then
				return false
			end
			pn [[Ты вытаскиваешь космонавта из кресла и кладёшь на грунт.]]
			pn [[-- Я сейчас подгоню луноход, командир! -- говорит Александр по радио.]]
			pn [[-- Да, надо спешить!]]
			pn [[Александр скрывается за холмом и через пару минут возвращается на луноходе.]]
			move(w, here())
			move('alex', 'buggy')
			move('buggy', here())
		end;
		description = function(s)
			p [[Похоже на кресло пилота.]]
			if visited 'drag_cab' then
				p [[Вероятно, это кресло из кабины "Дракона".]]
			else
				p [[Откуда оно?]]
			end
			return false;
		end;
		before_Enter = function(s)
			if not mission then
				p [[Странная мысль. Тебе совсем не хочется испытывать на себе эту штуку.]]
				return
			end
			if not s.fixed then
				know_parts = true
				p [[Ты знаешь, что во время последнего запуска трансмиттера произошёл сбой. Чтобы отремонтировать трансмиттер нужны запчасти. Лунная принцесса хочет, чтобы ты достал их из лунного модуля.]]
			else
				walkin 'stage8'
			end
		end;
	}:attr'~scenery,static,container,open':with {
		obj {
			suit = true;
			nam = 'spaceman1';
			-"космонавт,астронавт,Лю,Ливей";
			before_Pull = function(s)
				mp:xaction("Take", s)
			end;
			before_Take = function(s)
				if not mission then
					return false
				end
				p [[Тебе он не нужен.]]
			end;
			before_Talk = [[Он не в том состоянии, чтобы разговаривать.]];
			description = function(s)
				p [[Это китайский космонавт.]]
				if s.suit then
					p [[Лю Ливей -- читаешь ты бирку на его скафандре.]]
					p [[Глаза закрыты. Мёртв или нет? Ты не знаешь сколько он пролежал тут в этом кресле. Судя по индикатору, запасов кислорода почти не осталось!]]
				end
				if mission then
					p [[^^Ты знаешь, что у него не получилось переправить {$fmt em|их} в мир людей. Но должно получиться у тебя. Ведь так сказала лунная принцесса.]]
				end
			end;
		}:attr '~animate';
	};
	Careful {
		-"рефрактор|антенна";
		description = function(s)
			p [[Двухметровая антенна радиотелескопа обращена в сторону Земли.]];
			if mission then
				p [[^^Ты проведёшь {$fmt em|их} с помощью трансмиттера в сознание самых близких для тебя людей.]]
			end
		end;
	};
	Careful {
		-"оборудование|приборы|провода";
		description = [[Ты видишь детали, которые были когда-то частью различного оборудования и приборов со
		станции.]];
	};
	Useless {
		-"запчасти|луноход|колёса";
		description = [[От лунохода почти ничего не осталось.]];
		before_Enter = [[От этого лунохода почти ничего не осталось.]];
	};
	Careful {
		-"сооружение",
		description = function(s)
			p [[Тебе кажется, что всё происходящее -- сон.]];
			if mission then
				p [[Но это не так. Во сне, который исполнит все твои заветные желания, ты окажешься после того,
				как проведёшь {$fmt em|их} в сознание близких тебе людей на Земле.]]
			end
		end;
	};
}
room {
	-"пик,Малаперт*|вершина,гора";
	nam = 'malapert';
	vacuum = true;
	title = 'Пик Малаперта';
	w_to = 'device';
	dsc = [[Ты находишься на вершине горы Малаперт рядом с радиомаяком. На грунте ты замечаешь множество следов от колёс лунохода. На западе за небольшим холмом виднеется антенна радиотелескопа.]];
	before_Any = before_buggy;
	["before_Walk,Enter"] = function(s, w)
		if w ^ '@e_to' then
			if not me():inside'buggy' then
				p [[Слишком далеко, чтобы идти пешком.]]
				return
			end
			p [[Ты едешь на луноходе к базе.]]
			move('buggy', 'base')
			return
		end
		return false
	end;
	enter = function(s)
		pic_add '6'
	end
}:with {
	Path {
		-"радиотелескоп,телескоп|антенна";
		desc = [[Ты можешь пройти к радиотелескопу.]];
		walk_to = 'device';
	};
	'moonsky';
	'пыль',
	Useless {
		-"грунт,следы*";
		description = [[Глядя на серый грунт ты думаешь о том, что печальный лунный ландшафт везде одинаков. На грунте ты видишь следы от лунохода. Они ведут дальше на запад.]];
	};
	Careful {
		-"маяк,радиомаяк,фонарь";
		description = [[Это радиомаяк, который привёл луноход к пику. Также он снабжён оптическим светодиодным пульсирующим фонарём. Работает от солнечных батарей.]];
	}:with {
		Careful {
			-"батареи";
			nam = 'батареи';
			description = [[Здесь всегда светло. Солнечных батарей достаточно, чтобы запитать маяк.]];
		};
	}
}

room {
	-"площадка";
	nam = 'moon2';
	vacuum = true;
	title = 'Посадочная площадка';
	n_to = 'base';
	in_to = 'drag_door';
	enter = function(s)
		pic_add '10'
	end;
	dsc = function(s)
		p [[Ты находишься на посадочной площадке базы. Здесь стоит китайский лунный модуль "Дракон".]];
		if not disabled 'пар' then
			p [[Всё окутано розовым туманом.]];
		end
		p [[^^Можно вернуться на север к базе.]];
	end;
}: with {
	'пар',
	'moonsky',
	'пыль',
	'грунт',
	Path {
		-"база";
		desc = [[Ты можешь вернуться к базе.]];
		walk_to = 'base';
	};
	obj {
		-"модуль,Дракон";
		description = [["Дракон" угрюмо стоит под чёрным лунным небом. Ты видишь шлюзовую дверь.]];
		before_Enter = function(s)
			mp:xaction("Enter", _'drag_door')
		end;
	}:attr'scenery,enterable';
	'drag_door';
}
room {
	-"кабина|Дракон";
	title = 'кабина "Дракона"';
	nam = 'drag_cab';
	vacuum = true;
	d_to = 'drag_tech';
	dsc = function(s)
		p [[Ты находишься в кабине "Дракона". Освещение не работает, но яркий солнечный свет, проникающий сквозь широкие окна, хорошо освещает всё вокруг.
		Ты видишь изуродованную панель управления. В кабине не хватает одного кресла пилота.]]
		p[[^^Можно спуститься вниз в технический отсек.]]
	end;
}:with {
	Path { -"технический отсек", desc = "Ты можешь спуститься в технический отсек.", walk_to = 'drag_tech' };
	Distance { -"Луна|пейзаж", description = [[Молчаливый и чужой мир смотрит на тебя.]] };
	Furniture {
		-"кресло";
		inside_dsc = [[Ты сидишь в кресле.]];
		description = function(s)
			p [[На китайском лунном модуле больше места, здесь используются нормальные кресла вместо стоек. Но кресла второго пилота нет! Похоже, что кто-то демонтировал его. Так же, как и оборудование.]];
			if mission then
				p[[^^Ты знаешь, что кресло нужно для носителя. Сейчас носитель -- это ты.]]
			end
		end
	}:attr'scenery,enterable,supporter';
	Careful {
		-"окна|окно";
		description = [[Здесь окна больше, чем на лунном модуле "Арго". Некоторое время ты рассматриваешь унылый лунный пейзаж.]];
	};
	obj {
		-"панель управления,панель,отверст*,компьют*,пульт*|приборы";
		description = [[Панель управления полностью разворочена. В ней зияют отверстия от демонтированных приборов. На полу кабины валяются осколки.]];
		before_Attack = [[Тут и так уже ничего не осталось.]];
	}:attr'scenery';
	Prop { -"пол" };
	Useless { -"осколки", description = [[Кусочки панели и стекла. Обрывки проводов. Что здесь произошло?]] };
	'moonsky';
}
room {
	-"технический отсек,отсек,Дракон";
	title = 'технический отсек "Дракона"';
	nam = 'drag_tech';
	out_to = 'drag_door';
	u_to = 'drag_cab';
	vacuum = true;
	dsc = [[В техническом отсеке темно. В стене расположена выходная дверь. Путь наверх ведёт в кабину.]];
}:with {
	'drag_door';
	Path {
		-"кабина",
		desc = "Ты можешь подняться в кабину.";
		walk_to = 'drag_cab';
	};
}
door {
	-"дверь,шлюз";
	nam = 'drag_door';
	["before_Open,Close"] = [[Дверь управляется с помощью рычага.]];
	description = function(s)
		if here() ^ 'moon2' then
			p [[Эта прямоугольная массивная дверь ведёт внутрь модуля. Возле двери установлен красный рычаг.]]
			return false
		end
		p [[Эта прямоугольная массивная дверь ведёт наружу.]]
		p [[Возле двери установлен красный рычаг.]];
		return false
	end;
	door_to = function(s)
		if here() ^ 'moon2' then
			return 'drag_tech'
		else
			return 'moon2'
		end
	end
}:attr 'static,openable,scenery':with {
	obj {
		-"рычаг,красный рычаг";
		description = [[С помощью рычага можно управлять выходной дверью.]];
		before_Transfer = stick_transfer;
		["before_Push,Pull"] = function(s)
			if _'drag_door':hasnt 'open' then
				_'drag_door':attr 'open'
				p [[Ты открываешь дверь.]]
				return
			else
				_'drag_door':attr '~open'
				p [[Ты закрываешь дверь.]]
				return
			end
			return false
		end;
	}:attr 'static';
};
obj {
	nam = 'spaceman2';
	-"космонавт|Чжан,Ян";
	step = 1;
	before_Take = [[К чему тебе это?]];
	description = function(s)
		p [[Это второй космонавт "Дракона". Его зовут Чжан Ян. ]]
		if s.step < -3 then
			p [[Он не подаёт признаков жизни.]]
		elseif not _'труба':inside(s) then
			p [[Тебе кажется, что он плачет.]]
		else
			p [[{$fmt em|Они} советуют избавиться от него.
		Он шёл сюда пешком и сильно ослаб. Лунная принцесса говорит, что она будет твоей, а не его.]];
			if s.step < 1 then
				pn"^"
				s:dsc()
			end
		end
	end;
	daemon = function(s)
		if not _'труба':inside(s) then
			s:daemonStop()
			return
		end
		s.step = s.step + 1
		if s.step == 3 then
			p [[Космонавт нападает на тебя, но ты с лёгкостью уворачиваешься.]]
			s.step = 1
		elseif s.step == 1 then
			p [[Космонавт поднимается на ноги.]]
		end
	end;
	['before_Attack,Push'] = function(s)
		if s.step < 1 then
			if have 'труба' then
				p [[Ты набрасываешься на лежащего космонавта, нанося ему сильные удары куском трубы.]]
			else
				p [[Ты набрасываешься на лежащего космонавта, нанося ему сильные удары.]]
			end
			if _'труба':inside(s) then
				place 'труба'
			end
			s.step = -100
			DaemonStop(s)
		else
			p [[Ты бьёшь космонавта и он падает на грунт.]]
			s.step = -3
		end
	end;
	dsc = function(s)
		if not isDaemon(s) then
			p [[Космонавт лежит на грунте.]]
			return
		end
		if s.step < 1 then
			if s.step < -3 then
				p [[Космонавт лежит на грунте.]]
			else
				p [[Космонавт лежит на грунте, пытаясь встать.]]
			end
		else
			p [[Ты видишь недалеко от себя космонавта, держащего в руках кусок алюминиевой трубы. Он готовится атаковать!]];
		end
	end;
}:with {
	obj {
		nam = 'труба';
		-"труба";
		description = [[Кусок алюминиевой трубы от какой-то несущей рамы.]];
		before_Take = function(s)
			if not s:inside'spaceman2' then
				return false
			end
			if _'spaceman2'.step < 1 then
				p [[Ты забираешь трубу.]]
				take 'труба'
				return
			else
				p [[Это не так-то просто сделать.]]
			end
		end;
	}
}
room {
	-"Луна,пейзаж*";
	nam = 'moon1';
	vacuum  = true;
	title = 'У лунного модуля';
	in_to = 'door1';
	["before_Walk,Enter"] = function(s, w)
		if isDaemon'spaceman2' then
			if _'spaceman2'.step >= 1 then
				p [[Космонавт не даёт тебе уйти.]]
				return
			elseif _'spaceman2'.step >= -3 then
				p [[Космонавт поднялся на ноги и не даёт тебе уйти.]]
				return
			end
		end
		if w ^ '@w_to' or w ^ 'пар' then
			if not me():inside'buggy' then
				p [[Слишком далеко, чтобы идти пешком.]]
				return
			end
			if not visited 'moonw' then
				if _'пеленгатор':hasnt'on' then
					p [[Без помощи пеленгатора ориентироваться внутри этого странного облака будет сложно.]]
				else
					walkin 'moonw'
				end
				return
			else
				p [[Ты едешь на луноходе к базе.]]
				move('buggy', 'base')
			end
			return
		end
		return false
	end;
	enter = function(s)
		pic_add '5'
		if s:once() then
			p [[Ты осторожно спускаешься по лестнице и осматриваешься. Перед тобой разворачивается чужой и мёртвый мир.]]
			return
		end
		if _'запчасти'.got and mission and s:once'attack' then
			p [[Ты осторожно спустился по лестнице и направился к луноходу, когда тебя настиг удар. В уменьшенной лунной гравитации ты пролетел почти два метра, прежде чем упал на грунт. Не без труда ты встал на ноги и осмотрелся. Ты видишь перед собой космонавта!]]
			move('spaceman2', 'moon1')
			DaemonStart'spaceman2'
		end
	end;
	dsc = function(s)
		if not me():inside'buggy' then
			p [[Ты стоишь у лунного модуля.]]
		end
	 	p [[Вокруг простирается безжизненный лунный пейзаж. В чёрном небе ты видишь Землю.]];
	 	if not disabled 'пар' then
	 		p [[На западе клубится розовый пар.]];
	 	end
	end;
}:with {
	'moonsky',
	Careful { -"опоры/мн|опора", description = "Опоры погружены в лунную пыль." };
	Useless { nam = 'пыль', -"пыль", description = [[Она здесь повсюду.]]; };
	'грунт',
	Distance { nam ='пар', -"пар,туман,газ|облако",
		description = function(s)
			if here() ^ 'moon1' then
				p [[До него несколько сотен метров. Интересно, что он из себя представляет? Газовый выброс?]]
			else
				p [[Странный газ. Интересно, когда это явление закончится?]]
			end
		end
	};
	door {
		-"модуль,корабль";
		description = [[Необычно видеть модуль снаружи. Небольшая лестница ведёт к входной двери.]];
		before_Enter = function(s)
			mp:xaction("Enter", _'door1')
		end;
	}:attr'scenery,enterable,static';
	door {
		-"лестница";
		description = [[Модуль стоит на четырёх опорах и добраться до входной двери можно только по алюминиевой лестнице.]];
		["before_Enter,Climb"] = function(s)
			mp:xaction("Enter", _'door1')
		end;
	}:attr'scenery,enterable,static';
	'door1';
}
global 'docking' (false)
global 'turned' (false)
global 'faraway' (false)

local dirs = {
	n = 'север',
	s = 'юг',
	e = 'восток',
	w = 'запад'
}
global 'manual_docking' (false)

room {
	nam = 'moonmod';
	dir = 'w';
	pos = 0;
	height = 273;
	speed = 0;
	vspeed = -5;
	curspeed = 0;
	title = 'лунный модуль';
	-"модуль,корабль|кабина";
	['before_Answer,Ring'] = function()
		if _'скафандр':has'worn' then
			if _'скафандр'.radio then
				p [[Для того чтобы поговорить по радио, просто попробуйте поговорить с Зарёй, Беркутом или Арго.]];
				return
			end
		end
		return false
	end;
	d_to = 'moontech';
	before_Any = function(s, ev, w)
		if eph_event(ev) then
			return false
		end
		if w and  w ^ '#люк' and me():where()^'place' then
			p [[Ты пристёгнут ремнями.]]
			return
		end
		return false
	end;
	before_Listen = function(s)
		if _'alex'.state == 3 then
			p [[Ты слышишь аварийный сигнал бортового компьютера.]]
			return
		end
		if _'alex'.state == 5 then
			p [[Ты слышишь рёв двигателей.]]
			return
		end
		return false
	end;
	before_Wait = function(s)
		local m = s
		if m.pos >= 100 and m.vspeed < 0 and m.speed == 0 and m.height < 250 and m.height > 0 then
			walkin 'stage4'
			return
		end
		return false
	end;
	dsc = function(s)
		if s:once 'first' then
			p [[Ты и Александр, облачённые в скафандры, находитесь в кабине лунного модуля.]]
		else
			p [[Ты находишься в кабине лунного модуля.]]
		end
		_'#win':dsc()
		p [[Панель управления занимает большую часть кабины.]]
		p [[^^Ты можешь спуститься вниз в технический отсек.]]
	end;
}:with {
	Path { -"технический отсек", desc = "Ты можешь спуститься в технический отсек.", walk_to = 'moontech' };
	Ephe { -"космос", description = [[Ты никогда не привыкнешь к этому зрелищу. Одновременно пугающему и прекрасному.]] };
	Distance { nam = 'клубы'; -"туман,пар,вспышк*|клубы/мн";
		description = function()
			if _'moonmod'.pos >= 100 then
				p [[Тумана больше нет.]]
				return
			end
			p [[Время от времени ты видишь в тумане яркие вспышки.]];
		end;
	}:disable();
	Careful {
		nam = '#win';
		-"окна,пейзаж*|окно";
		dsc = function()
			if gravity then
				p [[Сквозь трапециевидные окна виден лунный пейзаж.]]
				if _'alex'.state == 5 then
					local m = _'moonmod'
					if m.dir ~= 'e' or m.pos < 50 then
						p [[Ты видишь клубы розового тумана, скрывающего лунную поверхность!]]
					else
						if m.pos > 50 and m.pos < 100 then
							p [[Ты видишь как туман постепенно рассеивается.]]
						end
					end
				end
			else
				p [[Сквозь трапециевидные окна виден бездонный, чёрный космос.]]
			end
		end;
		description = function(s)
			p [[Окна лунного модуля достаточно большие и обеспечивают неплохой обзор.]]
			s:dsc()
		end;
	};
	Careful {
		nam = 'panel';
		broken = false;
		-"панель управления,панель,прибор*|компьютер";
		before_Attack = function(s, w)
			if not know_parts then
				return false
			end
			if _'запчасти'.got then
				p [[Лунная принцесса говорит, что запчастей уже достаточно.]]
				return
			end
			if (not w and not have'screw') or (w and not w ^ 'screw') then
				p [[Просто сломать? Лунной принцессе нужны запчасти, а не обломки.]]
				if not have 'screw' then p [[Тебе нужен инструмент.]] end
				return
			end
			s.broken = true
			_'запчасти'.got = true
			take 'запчасти'
			p [[Содрогаясь от того, что ты делаешь, ты разбираешь панель и демонтируешь из неё нужные запчасти. Ты не знаешь точно, что именно ты делаешь. Но {$fmt em|они} подсказывают тебе.]]
		end;
		prog = 1;
		daemon = function(s)
			local m = _'moonmod'
			if here() ~= m then
				return
			end
			m.height = m.height + (rnd(3)-2 + m.vspeed)
			if m.height < 120 then
				if m.pos < 100 then
					p [[Садиться в таких условиях видимости -- безумие!]]
				elseif m.speed ~= 0 then
					p [[Для посадки нужно погасить горизонтальную скорость.]]
				else
					walkin 'stage4'
					return
				end
				p [[Ты сдвинул левую ручку вперёд и снова набрал высоту.]]
				m.vspeed = 0
				m.height = 120 + rnd(7)
			end
			if m.height > 512 then
				m.height = 512
			end
			m.curspeed = m.curspeed + m.speed*(rnd(5) + 2)
			if m.speed == 0 and m.curspeed > 0 then m.curspeed = 0 end
			if m.speed == 0 and m.curspeed < 0 then m.curspeed = 0 end
			if m.curspeed > 30 then m.curspeed = 30 + rnd(6) end
			if m.curspeed < -30 then m.curspeed = -30 + rnd(6) end
			if m.dir == 'e' then
				m.pos = m.pos + m.curspeed
			elseif m.dir == 'w' then
				m.pos = m.pos - m.curspeed
			end
			if m.pos < -100 then m.pos = -100 end
			if m.pos > 150 then m.pos = 150 end
		end;
		description = function(s)
			if s.broken then
				p [[Панель управления полностью разрушена.]]
				return
			end
			local progs = {
				"расстыковка";
				"нав. Пик Малаперта";
			}
			if gravity then
				pn ("Ориентация: ", dirs[_'moonmod'.dir])
				pn ("Высота: ", _'moonmod'.height, " м.")
				pn ("Горизонт. скорость ", _'moonmod'.curspeed, " м/с.")
				pn ("Вертик. скорость ", _'moonmod'.vspeed, " м/с.")
			end
			if s.prog then
				pn ("Программа: ", progs[s.prog])
				if _'#люк':has'open' then
					pn ("Внимание! Стыковочный люк: открыт")
				end
				if _'alex'.state == 3 then
					pn ("Внимание! Стыковочные замки: отказ")
				end
			end
			p [[На панели ты видишь кнопку запуска и отмены программы и две ручки управления: левую и правую.]]
		end;
	}:with {
		Careful { -"ручки", description = [[Эти ручки позволяют управлять двигателями модуля. Ты можешь двигать их: влево, вправо, вперёд и назад.]] };
		Careful {
			-"правая ручка,ручка,правая/но";
			description = [[Это ручка управления тангажом и креном. Ты можешь двигать её: влево, вправо, вперёд и назад.]];
			before_Turn = [[Ты можешь двигать ручку: вправо, влево, вперёд и назад.]];
			before_Transfer = stick_transfer;
			["before_Push,Pull"] = function(s)
				if gravity then
					if _'moonmod'.height == 0 then return "Ничего не произошло." end
					if _'panel'.prog then
						p [[Сначала нужно перевести модуль в режим ручного управления.]]
						return
					end

					local m = _'moonmod'
					local d
					if mp.event == 'Push' then
						d = 1
						m.speed = m.speed + 1
						if m.speed > 2 then
							m.speed = 2
							p [[Опасно накренять модуль так сильно.]]
							return
						end
					else
						d = -1
						m.speed = m.speed - 1
						if m.speed < -2 then
							m.speed = -2
							p [[Опасно накренять модуль так сильно.]]
							return
						end
					end
					if m.speed == 0 then
						p [[Плавным движением ручки ты выровнял модуль.]]
					elseif d > 0 then
						if m.speed < 0 then
							p [[Плавным движением ручки ты уменьшил крен лунного модуля.]]
						else
							if m.speed == 2 then
								p [[Плавным движением ручки ты ещё больше накренил лунный модуль вперёд.]]
							else
								p [[Плавным движением ручки ты накренил лунный модуль вперёд.]];
							end
						end
					else
						if m.speed > 0 then
							p [[Плавным движением ручки ты уменьшил крен лунного модуля.]]
						else
							if m.speed == -2 then
								p [[Плавным движением ручки ты ещё больше накренил лунный модуль назад.]]
							else
								p [[Плавным движением ручки ты накренил лунный модуль назад.]]
							end
						end
					end
					return
				end
				if not manual_docking then
					p [[Что ты делаешь? Расстыковка ещё не произведена!]]
					return
				end
				if not docking then
					p [[Сначала надо удалиться от Арго на безопасное расстояние.]]
				else
					p [[Уверенным движением ручки ты развернул модуль на 180 градусов.]]
					turned = not turned
					if not turned then
						p [[Сейчас прямо по курсу находится Арго.]]
					else
						p [[Теперь Арго находится за кормой.]]
					end
				end
			end;
			["before_PushRight,PushLeft"] = function(s)
				if gravity then
					if _'moonmod'.height == 0 then return "Ничего не произошло." end
					if _'panel'.prog then
						p [[Сначала нужно перевести модуль в режим ручного управления.]]
						return
					end
					local dirs = { 'w', 'n', 'e', 's' }
					local d = _'moonmod'.dir
					local ns = { w = 1, n = 2, e = 3, s = 4 }
					d = ns[d]
					if mp.event == 'PushRight' then
						d = d + 1
					else
						d = d - 1
					end
					if d <= 0 then d = 4 elseif d > 4 then d = 1 end
					_'moonmod'.dir = dirs[d]
					local names = { 'запад', 'север', 'восток', 'юг' }
					p ([[Плавным движением ручки ты развернул модуль на ]]..names[d]..".")
					return
				end
				if not manual_docking then
					p [[Что ты делаешь? Расстыковка ещё не произведена!]]
					return
				end
				if not docking then
					mp:xaction("Push", s);
				else
					p [[Ты не видишь смысла тратить топливо для вращения модуля.]]
				end
			end;
		};
		Careful {
			-"левая ручка,ручка,левая/но";
			description = [[Это ручка управления двигателями. Ты можешь двигать её: влево, вправо, вперёд и назад.]];
			before_Turn = [[Ты можешь двигать ручку: вправо, влево, вперёд и назад.]];
			before_Push = function(s)
				if gravity then
					if _'moonmod'.height == 0 then return "Ничего не произошло." end
					if _'panel'.prog then
						p [[Сначала нужно перевести модуль в режим ручного управления.]]
						return
					end
					local m = _'moonmod'

					m.vspeed = m.vspeed + rnd(3)
					if m.vspeed > 7 then
						m.vspeed = 7
						p [[Скорость подъёма и так достаточно большая. Не стоит её увеличивать!]]
						return
					end
					p [[Плавным движением ручки вперёд ты увеличил вертикальную тягу.]]
					return
				end
				if not manual_docking then
					p [[Что ты делаешь? Расстыковка ещё не произведена!]]
					return
				end
				if not docking then
					p [[Хочешь протаранить Арго?]]
				else
					p [[Ты толкнул ручку от себя.]]
					if not turned then
						docking = false
						faraway = false
						p [[Маневровые двигатели включились, дав импульс модулю на причаливание.]]
					else
						p [[Маневровые двигатели включились, дав импульс модулю на дальнейшее расхождение с Арго.]]
						faraway = true
					end
				end
			end;
			before_Transfer = stick_transfer;
			["before_PushRight,PushLeft"] = function(s)
				if gravity then
					if _'moonmod'.height == 0 then return "Ничего не произошло." end
					if _'panel'.prog then
						p [[Сначала нужно перевести модуль в режим ручного управления.]]
						return
					end
					if mp.event == 'PushRight' then
						p [[Плавным движением ручки ты сдвинул лунный модуль правее.]]
					else
						p [[Плавным движением ручки ты сдвинул лунный модуль левее.]]
					end
					return
				end
				if not manual_docking then
					p [[Что ты делаешь? Расстыковка ещё не произведена!]]
					return
				end
				if not docking then
					mp:xaction("Push", s);
				else
					p [[Ты не видишь смысла тратить топливо для смещения корабля в сторону.]]
				end
			end;
			["before_Pull"] = function(s,w)
				if gravity then
					if _'moonmod'.height == 0 then return "Ничего не произошло." end
					if _'panel'.prog then
						p [[Сначала нужно перевести модуль в режим ручного управления.]]
						return
					end
					local m = _'moonmod'
					m.vspeed = m.vspeed - rnd(3)
					if m.vspeed < -7 then
						m.vspeed = -7
						p [[Скорость падения и так высокая. Не стоит увеличивать её ещё больше!]]
						return
					end
					p [[Плавным движением ручки назад ты уменьшил вертикальную тягу.]]
					return
				end
				if not manual_docking then
					p [[Что ты делаешь? Расстыковка ещё не произведена!]]
					return
				end
				if docking then
					if turned then
						p [[Хочешь протаранить Арго кормой?]]
					else
						p [[Модуль уже удалился от Арго на достаточное расстояние.]]
					end
				else
					docking = 1
					p [[Ты потянул ручку на себя. Маневровые двигатели включились, дав импульс модулю на отчаливание.]];
				end
			end;
		};
	};
	obj {
		-"место пилота,место|стойка|места/мн|стойки/мн";
		nam = 'place';
		title = 'в стойке';
		inside_dsc = function() p [[Ты пристёгнут с стойке пилота.]]; end;
		description = [[В кабине есть два места для пилотов. Космонавты весь полёт проводят стоя,
		пристегнувшись ремнями к специальным стойкам.]];
		before_LetIn = function(s)
			p [[Ты пристёгиваешься к своей стойке.]]
			place(me(), s)
		end;
		before_LetGo = function(s)
			p [[Тебе мешают ремни.]]
		end;
	}:attr'supporter,scenery,static,enterable':with {
		'belts';
	};
	Careful {
		nam = '#button';
		-"кнопка";
		description = [[Красная кнопка запуска хорошо заметна на панели управления.]];
		before_Push = function()
			if not _'panel'.prog then
				p "Программа не выбрана."
				return
			end
			if not me():where()^'place' then
				p [[Сначала нужно пристегнуться к своей стойке.]]
				return
			end
			if _'#люк':has'open' then
				p [[-- Внимание! Стыковочный люк открыт. Расстыковка невозможна! -- слышишь ты синтезированную речь бортового компьютера.]]
				return
			end
			if _'alex'.state == 2 then
				if _'Беркут'.ack then
					p [[Сначала нужно проверить радиосвязь.]]
					return
				end
				if _'скафандр':hasnt'worn' then
					p [[Хорошо бы сначала надеть скафандр.]]
					return
				end
				_'Арго'.ack = false
				_'Заря'.ack = false
				stage = 'locking'
				_'alex'.state = 3
				DaemonStop 'alex'
				p [[Ты нажимаешь кнопку.^-- Поехали!^Послышался тревожный сигнал компьютера. Снова неполадки?]]
			elseif _'alex'.state == 3 then
				p [[Ты нажимаешь кнопку.]]
				if _'болтик':inside'lock' then
					p [[Ничего не происходит!]]
				else
					_'alex'.state = 4
					_'panel'.prog = false
					manual_docking = true
					p [[Лунный модуль вздрагивает. Замки сработали! Теперь нужно отлететь от Арго на безопасное расстояние и развернуться.]]
				end
			elseif _'alex'.state == 4 then
				if not turned then
					p [[Прежде чем активировать программу, лучше развернуть модуль и отвести его подальше от Арго.]]
					return
				end
				if not faraway then
					p [[Прежде чем активировать программу, лучше отвести модуль подальше от Арго.]]
					return
				end
				walkin 'stage3'
				return
			elseif _'alex'.state == 5 and _'panel'.prog then
				_'panel'.prog = false
				pn [[Ты включаешь режим ручного управления модулем.]]
				pn [[-- Командир, ручной режим. Начинаю мониторинг приборов! -- слышишь ты по радио голос Александра.]];
				DaemonStart 'alex'
				return
			elseif _'alex'.state == 1 then
				p [[Рано начинать расстыковку.]]
			else
				p [[Не стоит нажимать на кнопки просто так.]]
				return
			end
		end;
	};
	obj {
		-"Александр,Саша/мр";
		nam = 'alex';
		state = 1;
		suit = false;
		radio = -1;
		mwalk = 0;
		daemon = function(s)
			if gravity and _'moonmod'.height > 0 then
				if not here() ^ 'moonmod' then
					return
				end
				p ("-- Высота ", _'moonmod'.height,".")
				p (" Вертикальная скорость ", _'moonmod'.vspeed, ".")
				if (_'moonmod'.vspeed < 0) then p "Снижаемся!" end
				if _'moonmod'.curspeed ~= 0 then
					p (" Ориентация на ", dirs[_'moonmod'.dir], ".", " Скорость ", _'moonmod'.curspeed,".")
					if (_'moonmod'.curspeed < 0) then
						p [[Движемся назад!]]
					end
				end
				if _'moonmod'.pos >= 100 then
					p [[^-- Видимость для посадки -- нормальная!]]
				else
					p [[^-- Видимость -- плохая!]];
				end
				pn()
				return
			end
			if gravity and _'moonmod'.height == 0 then
				if here() ^'moontech' and _'door1':has'open' and s:once 'moontech' then
					p [[В этот момент в технический отсек из кабины спустился Александр.]]
					move('alex', 'moontech')
				elseif _'buggy':inroom() ^ 'moontech' and s:inroom() ^ 'moontech' then
					s.mwalk = s.mwalk + 1
					if _'door1':has'open' and here()^'moon1' and s.mwalk > 3 then
						move('buggy', 'moon1')
						_'buggy'.indoor = true
						enable 'тросы'
						p [[Ты видишь как в проёме двери показался сложенный луноход. Это Александр, закрепив его тросами перекинутыми через блоки в потолке технического отсека, начал его выгрузку.^-- Командир! Принимай груз!]]
					end
				elseif _'buggy':inroom() ^ 'moon1' and not _'buggy'.indoor and s:inroom() ^ 'moontech' and s:once 'moon1' then
					p [[Александр слезает по лестнице и становится рядом с луноходом.]]
					move(s, 'moon1')
					s.mwalk = 0
				elseif _'buggy':inroom() ^ 'moon1' and not _'buggy'.indoor and not _'buggy'.assembled and here() ^ 'moon1' then
					s.mwalk = s.mwalk + 1
					if time()%3 == 1 then
						p [[Ты слышишь по радио раздражённое мычание Александра.]]
					else
						if s.mwalk > 3 then
							p [[Ты видишь, как Александр безуспешно пытается разложить луноход.]]
						else
							p [[Ты видишь, как Александр раскладывает луноход.]]
						end
					end
				elseif here() == s:inroom() and me():inside'buggy' and not s:inside'buggy' then
					p [[Александр сел в луноход.]]
					move(s, 'buggy')
				elseif here() == s:inroom() and not me():inside'buggy' and s:inside'buggy' then
					p [[Александр покинул луноход.]]
					move(s, here())
				elseif player_moved() and _'alex'.state == 7 and here():hasnt'cutscene' and not s:inside'buggy' and here() ~= s:inroom() then
					p [[Александр следует за тобой.]]
					move(s, here())
				end
				return
			end
			local radio = {
				"-- Проверка радиосвязи! -- голос Александра прозвучал непривычно близко. -- Арго, я Беркут. Как слышно?",
				"-- Беркут, я Арго. Связь отличная. -- это отозвался Сергей из командного модуля. -- Проверяем связь с ЦУП. -- Заря, это Арго. Как связь?";
				"-- ... Арго, Заря. Слышу вас хорошо! -- ответ от Земли пришёл с заметной задержкой.";
				"-- Ястреб, я Беркут. Как связь? -- Александр ожидающе смотрит на тебя сквозь защитное стекло скафандра.";
			}
			if (s.ack or _'Арго'.ack or _'Заря'.ack) and time() % 4 == 1 then
				if _'скафандр':hasnt'worn' then
					return
				end
				if s.ack then
					p [[-- Ястреб, я Беркут. Ответьте! -- слышишь ты голос Александра по радиосвязи.]]
				elseif _'Арго'.ack then
					p [[-- Ястреб, я Арго. Ответь, командир!]]
				elseif _'Заря'.ack then
					p [[-- Ястреб, Ястреб. Я Заря. Как слышно?]]
				end
				return
			end
			if s.radio then
				s.radio = s.radio + 1
				if _'скафандр':hasnt'worn' and s.radio > 0 then
					if here() ^ 'moonmod' then
						p [[Александр машет тебе правой рукой и стучит левой по своему шлему. Нужно проверить связь.]]
					end
					s.radio = s.radio - 1
					return
				end
				if s.radio < 1 then
					return
				end
				p (radio[s.radio])
				if s.radio == #radio then
					_'Беркут'.ack = true
					_'Заря'.ack = true
					_'Арго'.ack = true
					s.radio = false
				end
				return
			elseif not s.ack and not _'Заря'.ack and not _'Арго'.ack and s.state == 1 then
				s.state = 2
				p "-- Ястреб, Заря. Начинайте расстыковку."
				_'Заря'.ack = "-- Заря, я Ястреб. Начинаем расстыковку."
			end
		end;
		dsc = function(s)
			if s.state == 1 then
				p [[Александр возится у панели управления.]];
			elseif s.state == 2 then
				p [[Александр пристёгнут к стойке пилота.]]
			elseif s.state == 3 then
				p [[Александр, пристёгнутый к своей стойке, изучает показания приборов на панели управления.]]
			elseif here() ^ 'liv' and _'spaceman1':inside'кровать' then
				if mission then
					p [[Александр спит.]]
				else
					p [[Александр сидит на краю кровати.]]
				end
			else
				p [[Здесь находится Александр.]]
			end
		end;
		description = function(s)
			if s:inroom() ^ 'moontech' and _'buggy':inroom() ^ 'moontech' then
				p [[Александр готовит луноход к выгрузке.]]
			elseif s:inroom() ^ 'moon1' and not _'buggy'.assembled then
				p [[Александр пытается разложить луноход, но в условиях лунной гравитации эта задача оказывается не такой простой.]]
			else
				if s.suit then
					p [[В скафандрах все космонавты похожи друг на друга.]]
				else
					if mission then
						p [[Глядя на спящего Александра, тебя жжёт совесть, но лунная принцесса обещала избавить тебя от мук. После того, как ты выполнишь свою миссию.]]
						return
					end
					p [[Ты рад видеть знакомое лицо Александра без скафандра.]]
				end
			end
		end;
		life_Give = function(s)
			if mission then
				p [[Лунная принцесса не желает этого.]]
				return
			end
			return false
		end;
		before_WakeOther = function(s)
			if mission then
				p [[Лунная принцесса не желает этого.]]
				return
			end
			return false
		end;
		before_Talk = function(s)
			if _'скафандр':hasnt'worn' and s.suit or _'скафандр':has'worn' and not s.suit then
				p [[Александр не слышит тебя.]]
				if _'скафандр':has'worn' then
					p [[Наверное, потому, что ты в скафандре, а он -- нет.]]
				else
					p [[Наверное, потому, что он в скафандре.]]
				end
				return
			end
			if here() ^ 'liv' and _'spaceman1':inside'кровать' then
				if mission then
					p [[Лунная принцесса не хочет, чтобы ты будил Александра.]]
					return
				end
				pn [[-- У нас есть два часа.^-- Вздремни часок, командир. Потом я.^-- Спасибо, Саша.]]
				return
			end
			return false
		end;
	}:attr'animate';
	obj {
		-"Сергей,Серёжа";
		nam = '#serg';
		description = [[Сергей не выглядит весёлым. Всё то время, пока ситуация на "Луна-9" не прояснится, ему придётся ждать на орбите. А затем, если не потребуется экстренная эвакуация, Сергею предстоит одинокое возвращение на Землю.]];
		before_Talk = function(s)
			p [[-- Не скучай, Серёжа!^
			-- Для первого полёта я уже получил массу впечатлений.^
			-- Ладно, до связи!]]
		end;
	}:attr'animate,scenery';
	obj {
		-"люк";
		nam = '#люк';
		dsc = function(s)
			if s:has'open' then
				if not disabled '#serg' then
					p [[В открытый стыковочный люк заглядывает Сергей.]]
				else
					p [[Стыковочный люк открыт.]]
				end
			else
				p [[Стыковочный люк закрыт.]]
			end
		end;
		description = function(s)
			if not disabled 'locks' then
				p [[^Ты можешь осмотреть стыковочные замки.]]
			else
				p [[Небольшой круглый люк связывает командный модуль с лунным модулем. Было непросто протиснуться в него! К счастью, это не надо делать часто.]];
			end
			return false
		end;
		before_Open = function(s)
			if _'alex'.state > 3 then
				if gravity then
					p [[Это стыковочный люк. Шлюзовая дверь находится в техническом отсеке.]]
					return
				end
				p [[Не стоит разгерметизировать лунный модуль.]]
				return
			end
			if _'alex'.state == 3 then
				_'locks':enable()
			end
			return false
		end;
		before_Close = function(s)
			if not _'скафандр'.radio then
				disable '#serg'
				_'скафандр'.radio = true
				DaemonStart 'alex'
				me().scope:add 'Беркут'
				me().scope:add 'Заря'
				me().scope:add 'Арго'
			end
			_'locks':disable()
			return false
		end;
		before_Enter = function(s)
			if s:has'open' then
				if not disabled 'locks' and  _'болтик':inside 'lock' then
					p [[Ты можешь осмотреть стыковочные замки.]]
				else
					p [[О командном модуле позаботится Сергей.]];
				end
			else
				p [[Люк закрыт.]]
			end
		end;
	}:attr'openable,open,static,enterable':with {
		Careful {
			nam = 'locks';
			-"стыковочные замки|замки";
			description = function(s)
				p [[Двенадцать стыковочных замков установлены по периметру стыковочного узла.]];
				if not disabled 'lock' then
					p [[Твоё внимание привлекает замок номер 3.]]
				else
					p [[По внешнему виду замков невозможно определить неполадки, даже если они и есть.]]
				end
			end;
		}:disable():with {
			Prop { -"узел" };
			Careful {
				nam = 'lock';
				-"стыковочный замок|замок,механизм|корпус";
				description = function(s)
					p [[Судя по телеметрии, проблема именно в этом замке.]]
					if s:hasnt'open' then
						p [[Замок закрыт корпусом.]];
					else
						p [[Ты рассматриваешь механизм.]]
						return false
					end
				end;
				before_LetGo = function(s, w) if w^'болтик' then _'болтик'.know = true end return false end;
				["before_Close,Lock"] = function(s, w)
					if w and w ^ 'screw' then
						mp:xaction("Close", s)
						return
					end
					return false
				end;
				['before_Open,Unlock,Attack'] = function(s, w)
					if s:has'open' then
						p [[Уже вскрыт.]]
						return
					end
					if not w then
						p [[Чем? Голыми руками это не получится.]]
						return
					end
					if not have(w) then
						p ([[Но у тебя с собой нет ]], w:noun'рд', [[!]])
						return
					end
					if not w ^ 'screw' then
						p ([[Идея интересная, но ]], w:noun(), [[ здесь не поможет.]])
						return
					end
					s:attr'open'
					p [[Ты вскрываешь корпус 3-го замка дрелью-шуруповёртом.]]
				end;
			}:attr'container,openable':disable():with {
				obj {
					nam = 'болтик';
					know = false;
					screw = false;
					-"болтик,болт";
					init_dsc = [[В механизме привода замка застрял болтик.]];
					before_Pull = function(s)
						mp:xaction("Take", s)
					end;
					["before_Take,Remove"] = function(s)
						if _'болтик'.screw then
							p [[Болтик нужен для крепления крыла.]]
							return
						end
						return false
					end;
					before_Turn = function(s)
						if not have'screw' then
							p [[У тебя нет необходимого инструмента.]]
							return
						end
						if s.screw then
							p [[Уже закручен.]]
							return
						end
						local w = s:where()
						if w == me() or std.is_obj(w, 'room') then
							p [[Сначала нужно вставить болтик куда-нибудь.]]
							return
						end
						if w ^ 'крыло' then
							s.screw = true
							p [[Ты закрутил болтик. Теперь крыло надёжно закреплено!]]
							return
						end
						p ([[Нет необходимости закручивать болтик в ]], w:noun 'вн', ".")
					end;
					description = function(s)
						s.know = true;
						if s:where() ^ 'lock' then
							p [[Болтик застрял в механизме замка! Поэтому расстыковка не удалась!]]
						else
							p [[Небольшой болтик. Интересно, откуда он выпал?]]
						end
					end;
				}
			}
		}
	}
}
Ephe {
	-"Беркут";
	ack = false;
	nam = 'Беркут';
	before_Talk = function(s)
		if mission then
			p [[Лунная принцесса хочет, чтобы ты соблюдал радиомолчание.]]
			return
		end
		if s.ack then
			p "-- Беркут, я Ястреб. Связь в норме."
			s.ack = false
			return
		end
		if _'alex'.radio then
			p "Ты не стал перебивать Александра."
			return
		end
		if _'alex'.state == 3 then
			if _'болтик'.know then
				p [[-- Беркут, это был болтик!^-- Интересно, откуда он выпал?^-- Хороший вопрос.]]
			else
				p [[-- Беркут, ты выяснил в чём проблема?^-- 3-й стыковочный замок не отвечает и автоматика прекращает процесс расстыковки!]]
			end
			_'lock':enable()
			return
		end
		if _'alex'.state == 4 then
			if not _'panel'.prog then
				p [[-- Беркут, активируй программу навигации!^-- Есть, командир!]]
				_'panel'.prog = 2
			else
				p [[-- Беркут, программа загружена?^-- Так точно!]]
			end
			return
		end
		if _'alex'.state == 5 then
			if _'moonmod'.pos >= 100 then
				p [[-- Беркут, кажется, вышли!^-- Да, командир, можно садиться!]];
				if _'moonmod'.speed ~= 0 then
					p [[Гаси горизонтальную скорость, командир!]]
				end
			else
				p [[-- Беркут, ты видишь это?^-- Да, командир.]]
			end
			return
		end
		if _'buggy'.indoor then
			p [[-- Тебе нужна помощь?^-- Да, лучше перестраховаться, командир.]]
			return
		end
		if not _'buggy'.assembled and here() ^ 'moon1' then
			p [[-- Какие-то проблемы?^-- Да, раму заело. Тяни на себя, командир. Попробуем метод грубой силы.^-- Подожди, я сейчас.]]
			return
		end
		if _'alex':visible() then
			if here() ^'device' then
				p [[-- Да что же здесь происходит!^
				-- Нам нужно эвакуировать космонавта, командир.]]
				return
			end
			if here() ^ 'drag_cab' then
				p [[-- Что ты думаешь об этом?^
				-- Проблемы с психикой у экипажа?]];
				return
			end
			if here() ^ 'tech' then
				if not know_panel then
					p [[-- Что ты думаешь об этом?^
					-- Командир, смотри что с командным пультом!]];
				else
					p [[-- Что ты думаешь об этом?^
					-- Мне это не нравится, командир.]];
				end
				return
			end
			p [[-- Как настрой, Беркут?^-- Всё в порядке, командир!]]
		else
			p [[-- Беркут, я Ястреб. Как обстановка?^-- Ястреб, Беркут. Всё в порядке.]]
		end
	end;
}
Ephe {
	-"Заря|ЦУП";
	ack = false;
	req = false;
	nam = 'Заря';
	before_Talk = function(s)
		if mission then
			p [[Лунная принцесса хочет чтобы ты соблюдал радиомолчание.]]
			return
		end
		if _'alex'.radio then
			p "Ты не стал перебивать Александра."
			return
		end
		s.req = false
		if s.ack then
			if type(s.ack) == 'string' then
				p(s.ack)
			else
				p "-- Заря, Ястреб на связи.^-- ... Ястреб, Заря. Принято."
			end
			s.ack = false
			return
		end
		if _'alex'.state == 3 then
			if _'болтик'.know then
				pn "-- Заря, я Ястреб. Я обнаружил болтик в 3-м замке."
				pn "-- Ястреб, я Заря. Вас понял."
			else
				pn "-- Заря, я Ястреб. Расстыковка не состоялась."
				pn "-- Ястреб, я Заря. Мы изучаем телеметрию. Нет данных по З-му стыковочному замку. Вероятно, проблема в нём. Может быть, замыкание датчика замка поможет."
				pn "-- Заря, Ястреб. Вас понял, приступаю."
			end
			_'lock':enable()
			return
		end
		if _'alex'.state == 4 then
			pn "-- Заря, это Ястреб. Расстыковка успешно осуществлена!"
			pn "-- ... Ястреб, Заря желает вам успешной посадки!"
			return
		end
		if _'alex'.state == 5 then
			if _'moonmod'.pos >= 100 then
				pn "-- Заря, я Ястреб! Вышли из зоны явления. Садимся!"
				pn "... -- Ястреб, Заря желает вам успешного прилунения!"
				return
			end
			pn "-- Заря, я Ястреб. Что за преходящие лунные явления?"
			pn "... Ястреб, Заря. Вы должны уже видеть это. Мы наблюдаем розовые вспышки закрывающие пик."
			pn "-- Заря, я Ястреб. Вы понимаете что это такое?"
			pn "-- ... Ястреб, Заря. Не вполне. Возможно, это электростатические разряды в пыли. В любом случае, ЦУП принял решение не рисковать. Сажайте модуль восточнее запланированного места."
			pn "-- Заря, Ястреб. Вас понял."
			return
		end
		if _'alex'.state == 6 then
			pn [[-- Заря, я Ястреб! Мы готовы идти к базе.]]
			pn [[-- Ястреб, Заря. Луна-9 находится на западе в четырёх километрах от вас.]]
			return
		end
		if _'alex'.state == 7 then
			if know_panel and not visited 'sklad' then
					pn [[-- Заря, Ястреб. Тут что-то странное происходит.]]
					pn [[... -- Ястреб, Заря. Что именно?]]
					pn [[-- Разобрано радио и другое оборудование. Также, мы не видим лунохода у станции...]]
					pn [[... -- Вас поняли, продолжайте наблюдение.]]
					pn [[-- Есть.]]
					know_panel = 2
					return
			end
			if visited 'sklad' then
				if visited'device' then
					pn [[-- Заря, я Ястреб. Мы нашли космонавта при странных обстоятельствах. Эвакуируем на базу.
					Подробности позже.]]
					p [[-- Ястреб, Заря. Вас поняли. Ждём сеанса связи.]]
					return
				end
				if visited 'malapert' then
					pn [[-- Заря, я Ястреб. Мы на месте. Изучаем обстановку.]];
					pn [[-- ... Ястреб, Заря. Вас поняли.]]
					return
				end
				p [[-- Заря, я Ястреб. Мы осмотрели базу. Никого не нашли.]]
				if know_panel and know_panel ~= 2 then
					pn [[Часть оборудования станции повреждено.]]
					pn [[... -- Повторите, не понял...]]
					pn [[-- Часть оборудования демонтировано или разобрано. Мы не понимаем, что это значит.]]
				else
					pn()
				end
				pn [[.. -- Ястреб, Заря... Мы ввели в пеленгатор лунохода частоту Пика Малаперта, обследуйте её тоже.]];
				pn [[-- Вас понял, приступаем.]]
				know_malapert = true
				return
			end
			pn [[-- Заря, я Ястреб! Мы на месте. Изучаем обстановку.]]
			pn [[... -- Ястреб, Заря. Вас поняли. Докладывайте как только выясните что-нибудь.]]
			pn [[-- Есть.]];
			return
		end
		p [[Сейчас нет необходимости связываться с Землёй.]]
	end;
}
Ephe {
	-"Арго";
	nam = 'Арго';
	ack = false;
	before_Talk = function(s)
		if mission then
			p [[Лунная принцесса хочет, чтобы ты соблюдал радиомолчание.]]
			return
		end
		if _'alex'.radio then
			p "Ты не стал перебивать Александра."
			return
		end
		if s.ack then
			p "-- Арго, Ястреб на связи.^-- Ястреб, Арго. Принято!"
			s.ack = false
			return
		end
		if _'alex'.state == 3 then
			pn "-- Арго, Ястреб. Расстыковка не состоялась. Работаем над решением проблемы. Возможна разгерметизация. Оставайся в командном модуле.^-- Ястреб, Арго. Вас понял. На связи."
			return
		end
		if _'alex'.state == 4 then
			pn "-- Арго, Ястреб. Расстыковка произошла!"
			p "-- Ястреб, Арго."
			if not docking then
				pn "Вижу вас совсем рядом."
			elseif turned then
				pn "Вижу вас во всём великолепии! До встречи, командир!"
			else
				pn "Наблюдаю ваше удаление!"
			end
			return
		end
		if _'alex'.state == 5 or _'alex'.state == 6 then
			pn "Связи с Арго нет. Сейчас он облетает противоположную сторону Луны."
			return
		end
		p "Сейчас нет необходимости связываться с Сергеем."
	end;
}
cutscene {
	nam = 'stage4';
	enter = function(s)
		DaemonStop 'alex'
		DaemonStop 'panel'
	end;
	title = "Луна-9";
	text = {
	[[Найдя подходящую ровную поверхность ты погасил горизонтальную скорость и начал спуск.]],
	[[-- Высота 103, скорость 3.4, топливо -- в норме! -- всё так же докладывал показания приборов Александр.
	Но тебе это было уже ни к чему. Ты и так видел всё что было нужно. Твои руки замерли на ручках управления и, казалось, сами собой короткими точными движениями корректировали скорость снижения.]];
	[[ -- Высота 53, скорость 1.7, топливо -- в норме! Поднимается пыль!^
	А вот камень размером с автомобиль. Откуда он взялся? Ты сдвигаешь ручку управления двигателями влево и модуль послушно уходит в сторону.]];
	[[ -- Высота 17, скорость 0.9, топливо -- в норме. Везде пыль!^
	Интересно, зачем Александр сообщает про пыль. Ты и сам видишь, что видимость нулевая. Клубы лунной пыли
	разгоняемые реактивной струёй поднялись наверх и закрыли весь обзор.]],
	[[ -- Высота 6! Контакт! -- ты быстро выключаешь двигатель. С секунду вы напряжённо ждёте, пока модуль свободно падает. Удар! ... Вы на Луне.]];
	};
	exit = function(s)
		_'alex'.state = 6
		disable 'клубы'
		_'moonmod'.height = 0
		_'moonmod'.vspeed = 0
		DaemonStart 'радио'
		_'Заря'.req = [[-- ... Ястреб, Заря! Ответьте!]];
		_'Заря'.ack =[[-- Заря. Ястреб. Мы сели!^
				... -- Ястреб. Заря. Спасибо за отличную новость! Мы проверили телеметрию, всё в порядке!]]
		DaemonStart 'alex'
		pic_add '5'
	end;
}
cutscene {
	nam = 'stage3';
	title = 'Луна-9';
	text = {
		[[Пока двигатель ревел под ногами, давая необходимый импульс для снижения орбиты, ты смотрел в иллюминаторы, сквозь которые сиял голубой серп Земли. Ты думал о Ларисе и Артуре.]];
		[[Привязанному ремнями, падающему на серо-пепельную поверхность Луны, тебе казалось, что ты окончательно уже во власти другого мира. Но представляя спящих жену и сына там, на Земле, ты понимал что разрыв иллюзорен.]];
		[[Место посадки находилось у самого Южного полюса на горе Малаперт у "Пика вечного света". Освещённость 89% времени, прямая видимость с Земли, запасы льда и возможность установки телескопа в тени кратера  -- удобные условия для первой лунной базы человечества.]];
		[[Наконец, Земля постепенно ушла из иллюминаторов. Модуль падал с орбиты. На высоте 3700 метров, он занимал уже почти вертикальное положение. Прошло всего около 15 минут спуска.]];
		[[... -- Ястреб, я Заря! Мы фиксируем на месте посадки преходящее лунное явление. Мы рекомендуем вам изменить место посадки. Как поняли?]];
		[[-- Какое ещё явление?... Заря, я Ястреб. Куда садиться? Решайте быстрее, мы почти на месте!]];
		[[-- ... Ястреб, Заря, берите восточнее, там чисто. Вы сами увидите это, ориентируйтесь визуально.^
		-- Заря, я Ястреб. Что я должен увидеть?^
		-- Борис, смотри!]]
	};
	exit = function()
		gravity = true;
		_'alex'.state = 5
		enable 'клубы'
		DaemonStart 'panel'
		pic_add'7'
	end;
}
cutscene {
	nam = 'tomalapert';
	title = 'Луна-9';
	text = {
		[[Пик Малаперта или пик вечного света -- возвышение у края кратера Малаперта. С этой точки Земля находится всегда
		в прямой видимости. При этом теневая сторона пика всегда находится в радиотени сигналов с Земли.]],
		[[Медленно, но верно луноход продвигается по пологому хребту разрушенного кратера Малаперт. Наконец, Александр
		замечает огонь маяка! Вы на месте!]];
	};
	exit = function(s)
		place('buggy', 'malapert')
		move(me(), 'buggy')
	end;
}
cutscene {
	nam = 'moonw';
	title = 'Луна-9';
	text = {
	[[Ты направил луноход на запад. Туда где должна была находиться база. В лунной гравитации луноход довольно
	ощутимо подбрасывало на неровностях ландшафта. С некоторой тревогой вы приближались к странным розовым клубам пара, озаряемым яркими вспышками света.]];
	[[Наконец, на полной скорости вы въехали в розовое облако. Видимость стала заметно хуже, но вы уверенно шли на сигнал навигационного маяка по пеленгатору. Судя по струям пара бьющим вверх, источник странного газа находился где-то в недрах Луны.]];
	[[Прошло около пятнадцати минут, когда вы с Александром увидели свет маяка сквозь розовый туман. Вы добрались до базы!]];
	};
	exit = function()
		move('buggy', 'base')
		move(me(), 'buggy')
		_'Заря'.ack = false
		if _'Заря'.req then
			_'Заря'.req = "... -- Ястреб, я Заря. Почему не выходите на связь?"
		end
		 _'alex'.state = 7
	end;
}
room {
	-"отсек";
	nam = 'sect1';
	title = "шлюз";
	out_to = 'gate';
	in_to = 'mdoor';
	dsc = function(s)
		p [[В шлюзовом отсеке тускло горит дежурное освещение. Наружу ведёт шлюзовая дверь.]];
		p [[Чтобы попасть в отсеки базы нужно пройти через входной люк. Возле люка расположен шкаф.]];
	end;
}:with {
	Ephe { -"освещение|свет" };
	Careful { -"вентиляторы,вентилятор*", description = "Вентиляторы убирают пыль из шлюза, чтобы она не проникла внутрь жилых модулей." };
	'gate';
	'mdoor';
	obj {
		-"шкаф";
		nam = 'suitbox';
		title = 'шкаф';
		description = function(s)
			p [[Этот шкаф сделан из алюминия и используется для хранения скафандров.]];
			return false
		end;
		before_LetGo = function(s, w)
			if w ^ 'suits' then
				p [[Зачем тебе все скафандры?]]
				return
			end
			if w ^ 'скафандр' then w:attr'~concealed' end
			if w ^ 'скафандр' and _'alex':inroom() == here() then
				p [[Ты забираешь скафандр.]]
				p [[Александр тоже берёт свой скафандр из шкафа.]]
				_'alex'.suit = true
				take(w)
				return
			end
			return false
		end;
		before_LetIn = function(s, w)
			if w ^ 'скафандр' then w:attr'concealed' end
			if w ^ 'скафандр' and _'alex':inroom() == here() then
				p [[Ты помещаешь скафандр в шкаф.]]
				p [[Александр снимает свой скафандр и кладёт его в шкаф вслед за тобой.]]
				_'alex'.suit = false
				move(w, s)
				return
			end
			return false
		end;
	}:attr'scenery,openable,container,enterable':with {
		obj {
			-"скафандры";
			nam = 'suits';
			description = [[Эти скафандры ничем не отличаются от твоего. Кроме размера.]];
		};
	}
}
door {
	-"люк";
	nam = 'mdoor';
	description = [[Массивный межмодульный люк круглой формы.]];
	door_to = function(s)
		if here() ^ 'sect1' then
			return 'lab'
		else
			return 'sect1'
		end
	end;
	before_Open = function(s)
		if _'gate':has'open' then
			p [[Похоже, что люк заблокирован.]]
			return
		end
		return false
	end;
}:attr'scenery,openable'

door {
	-"шлюз,дверь";
	nam = 'gate';
	door_to = function(s)
		if here() ^ 'base' then
			return 'sect1'
		else
			return 'base'
		end
	end;
	before_Attack = [[Дверь слишком крепкая.]];
	["before_Open,Close"] = [[Шлюзовая дверь не может быть открыта или закрыта в ручном режиме.]];
	description =function(s)
		p [[В шлюз ведёт массивная прямоугольная дверь рядом с которой находится красный рычаг.]];
		return false
	end;
}:attr'static,scenery,openable':with {
	Careful {
		-"рычаг";
		description = [[Красный рычаг с помощью которого открывается шлюз.]];
		["before_Push,Pull"] = function(s)
			if not power then
				p [[Ничего не произошло.]]
				if know_station then
					p [[Вероятно, потому что станция обесточена.]]
				else
					p [[Странно.]]
				end
				return
			end
			if _'gate':has'open' then
				_'gate':attr'~open'
				p [[Шлюзовая дверь закрылась.]]
				if here() ^ 'sect1' then
					p [[Ты увидел как заработали вентиляторы, вытягивая лунную пыль из шлюзового отсека.]]
				end
			else
				if _'скафандр':hasnt'worn' then
					p [[Но без скафандра ты умрёшь!]]
					return
				end
				if _'mdoor':has'open' then
					p [[Ничего не произошло. Автоматика блокирует шлюзовую дверь!]]
					return
				end
				_'gate':attr'open'
				p [[Шлюзовая дверь отъехала в сторону.]]
			end
		end;
	};
}

obj {
	nam = "запчасти";
	got = false;
	-"запчасти";
	description = [[Необходимые компоненты для починки трансмиттера. {$fmt em|Они} подскажут тебе что и
	как делать.]];
}

global 'know_parts' (false)

room {
	nam = 'base';
	vacuum = true;
	title = 'Луна-9';
	n_to = 'station';
	s_to = 'moon2';
	in_to = 'gate';
	-"база";
	enter = function(s)
		pic_add '8'
		if mission and (_'powergen':has'on' or _'gate':has'open') then
			p [[Лунная принцесса хочет, чтобы ты заблокировал выход из базы. Чтобы Александр не помешал миссии.]]
			return
		elseif mission and not _'запчасти'.got then
			know_parts = true
			p [[Ты знаешь, что во время последнего запуска трансмиттера произошёл сбой. Чтобы отремонтировать трансмиттер нужны электронные запчасти.]]
		end
	end;
	dsc = function(s)
		p [[База "Луна-9" представляет из себя пять модулей цилиндрической формы, сцеплённых вместе. Рядом находится шлюз.]];
		if not disabled 'пар' then
			p [[Всё окутано розовым туманом.]];
		end
		p [[Здесь установлен маяк. На севере находится электростанция. На юге расположена посадочная площадка.]];
	end;
	before_Any = before_buggy;
	["before_Walk,Enter"] = function(s, w)
		if w ^ '@w_to' and not know_malapert then
			p [[Этот путь недоступен.]]
			return
		end
		if w ^ '@e_to' or w ^ '@w_to' then
			if not me():inside'buggy' then
				p [[Слишком далеко, чтобы идти пешком.]]
				return
			end
			if mission and _'powergen':has'on' then
				p [[Но лунная принцесса желает, чтобы сначала я заблокировал выход из базы.]]
				return
			end
			if w ^ '@e_to' then
				p [[Ты едешь на луноходе к лунному модулю.]]
				move('buggy', 'moon1')
			elseif w ^ '@w_to' then
				if s:once'malapert' then
					walkin 'tomalapert'
				else
					p [[Ты едешь на луноходе к Пику Малаперта.]]
					move('buggy', 'malapert')
				end
			end
			return
		end
		return false
	end;
}:with {
	'gate';
	'пар';
	'moonsky';
	'пыль';
	Careful {
		-"маяк,радиомаяк,фонарь";
		broken = false;
		description = function(s)
			if s.broken then
				p [[Радиомаяк вскрыт и из него извлечён контроллер заряда, так что больше он не заряжается. Интересно, на сколько хватит заряда?]]
				return
			end
			p [[Это радиомаяк, который и привёл вас к базе. Также он снабжён оптическим светодиодным пульсирующим фонарём. Работает маяк на солнечных батареях.]];
		end;
		after_Receive = function(s, w)
			if w ^ 'контроллер' then
				p [[Ты вставил контроллер в радиомаяк.]]
				return
			end
			p [[Это не запчасть для радиомаяка.]]
		end;
		before_Attack = function(s, w)
			if s.broken then
				p [[Маяк уже разобран.]]
				return
			end
			if controller then
				return false
			end
			if not w or not w ^'screw' then
				p [[Нужен подходящий инструмент.]]
				return
			end
			s.broken = true
			take 'контроллер'
			controller = true
			p [[Ты разобрал маяк и достал из него контроллер заряда.]]
		end;
	}:with {
		'батареи';
	};
	Useless {
		-"грунт";
		nam = 'грунт';
		description = [[Глядя на серый грунт ты думаешь о том, что печальный лунный ландшафт везде одинаков.]];
	};
	Useless {
		-"модули";
		description = [[Модули врыты в грунт и покрыты противометеоритной защитой.]];
	};
	Useless {
		-"защита,анти*";
		description = [[Защита представляет из себя толстую насыпь из лунного грунта.]];
	};
	Path {
		-"электростанция,станция";
		desc = [[Ты можешь пойти к электростанции.]];
		walk_to = 'station';
	};
	Path {
		-"посадочная площадка,площадка";
		desc = [[Ты можешь пойти к посадочной площадке.]];
		walk_to = 'moon2';
	};
};

obj {
	nam = 'контроллер';
	-"контроллер";
	description = [[Типовой контроллер заряда. Промежуточное звено между солнечными панелями и аккумулятором.]]
}
global 'controller' (false)
global 'know_station' (false)
global 'power' (false)
room {
	nam = 'station';
	vacuum = true;
	title = "Электростанция";
	dsc = [[Ты находишься у электростанции на солнечных батареях. Ты можешь вернуться к шлюзу.]];
	s_to = 'base';
	enter = function(s)
		pic_add '9'
	end;
}:with {
	Careful {
		nam = 'powergen';
		-"электростанция,станция|управляющий модуль,модуль,корпус";
		before_SwitchOn = function(s)
			if s:has'on' then
				return false
			end
			if not _'контроллер':inside(s) then
				return [[Ты попробовал включить станцию. Не работает.]]
			end
			power = true
			s:attr'on'
			p [[Ты включаешь электростанцию. Работает!]]
		end;
		before_LetGo = function(s, w)
			if w ^'контроллер' and s:has'on' then
				p [[Сначала надо выключить станцию.]]
				return
			end
			return false
		end;
		before_SwitchOff = function(s)
			if s:hasnt'on' then
				return false
			end
			if _'gate':has'open' then
				p [[Автоматика не позволит выключить станцию, пока шлюзовая дверь открыта.]];
				return
			end
			power = false
			if mission and _'gate':hasnt'open' then
				p [[Ты выключаешь станцию и теперь дверь в базу заблокирована. Сейчас лунная принцесса желает, чтобы ты начал процесс переноса.]]
				s:attr'~on'
				return
			end
			return false
		end;
		before_Receive = function(s, w)
			if not w ^'контроллер' then
				p [[Это не запчасть для электростанции.]]
				return
			end
			move(w, s)
			p [[Ты вставил контроллер в управляющий модуль электростанции.]]
		end;
		description = function(s)
			if not _'контроллер':inside(s) then
				p [[Корпус управляющего модуля электростанции вскрыт и ты видишь, что в нём не хватает контроллера заряда.]];
				know_station = true
			end
			if s:hasnt'on' then
				p [[Электростанция выключена.]]
			end
			return false
		end;
	}:attr'switchable,container,open,openable';
	Careful {
		-"солнечные батареи,батареи|парус";
		description = "Парус из батарей поднимается вверх на 15 метров!";
	};
	Careful {
		-"аккумуляторы,аккумулятор*";
		description = [[Аккумуляторы нужны для того, чтобы запасать энергию на период недолгой ночи на горе Малаперт.]];
	};
	Path {
		-"шлюз";
		desc = [[Ты можешь вернуться к шлюзу.]];
		walk_to = 'base';
	};
	'пар';
	'moonsky';
	'пыль';
	'грунт';
}
room {
	nam = 'lab';
	-"модуль";
	title = "научный модуль";
	out_to = 'mdoor';
	in_to = 'tech';
	e_to = 'mdoor';
	w_to = 'tech';
	dsc = function(s)
		p [[Ты находишься внутри научного модуля. Вдоль стен стоят столы с оборудованием. Ты можешь выйти обратно в люк или пройти в служебный модуль на запад.]];
	end;
}:with {
	'mdoor';
	'wall',
	Careful {
		-"столы";
		description = [[Белые столы занимают всю длину модуля. На них ты видишь разнообразное оборудование и образцы.]];
	};
	Useless {
		-"оборудование";
		description = [[Оборудование позволяет производить биологические и физические эксперименты. Рядом с оборудованием ты видишь образцы.]];
	};
	Careful {
		-"образцы|грунт";
		description = [[Ты видишь образцы лунного грунта и колбы с розоватым газом внутри.]];
	};
	Careful {
		-"колбы|колба|газ";
		description = function(s)
			p [[Похоже, что в этих колбах находится тот самый газ с лунной поверхности!]];
			know_gas = true
			if mission then
				p [[^^Ты знаешь, что этот газ способствовал контакту с {$fmt em|ними}.]]
			end
		end;
		before_Take = [[Ты решил не трогать колбы.]];
	};
	Path {
		-"служебный модуль";
		desc = [[Ты можешь зайти в служебный модуль.]];
		walk_to = 'tech';
	};
}
global 'know_panel' (false)
global 'know_gas' (false)
room {
	nam = 'tech';
	title = 'служебный модуль';
	-"служебный модуль";
	e_to = 'lab';
	n_to = 'liv';
	out_to = 'lab';
	in_to = 'liv';
	dsc = function(s)
		p [[Служебный модуль на станции играет роль командного центра и кают-компании.
		Здесь находится командный пульт. Рядом стоит кресло оператора. У противоположной стены расположен небольшой диванчик и стол.^^Ты можешь вернуться в научный модуль на восток или пройти дальше в жилой модуль на север.]];
	end;
}:with {
	'wall',
	obj {
		-"постер,плакат";
		init_dsc = [[Ты видишь на стене постер.]];
		["before_Tear,Attack"] = function(s)
			if mission then return "Ты не можешь себя заставить сделать это." end
			p [[Это не твоя вещь, зачем портить?]]
		end;
		description = function(s)
			pic_add '12'
			p [[На постере изображена полуобнажённая девушка. Правой рукой она поправляет волосы. Левая рука небрежно лежит на гибкой талии. На голове у девушки надета корона, искрящаяся серебром. Белоснежная улыбка девушки излучает кокетство и власть.]];
			if mission then
				p [[^^С тяжестью на сердце ты понимаешь, что лунная принцесса -- всего лишь изображение на фривольном постере. Но какая разница? Лунная принцесса сказала, что в её мире возможно всё. И что этот мир -- не менее реален чем мир, в котором живут люди.]]
			end
		end;
		["before_Show,Give"] = function(s, w)
			if w ^ 'alex' and not mission then
				p [[Александр только удивлённо покачал головой.]]
				return
			end
			return false
		end;
	};
	obj {
		-"пульт,провод*,дыр*";
		description = function(s)
			know_panel = true
			p [[Даже быстрого взгляда на командный пульт достаточно, чтобы сказать, что здесь произошло что-то странное! Пульт пытались сломать или разобрать. Ты видишь, что большинство сложных приборов демонтированы, а на их месте зияют дыры. На месте радиостанции ты видишь лишь обрывки проводов.]]
			if mission then
				p [[^^Ты знаешь, что демонтированное оборудование было необходимо для сбора трансмиттера
				на Пике Малаперта.]]
			end
		end;
	}:attr'scenery';
	Furniture {
		-"кресло";
		inside_dsc = [[Ты сидишь в кресле оператора.]];
		dsc = function(s) mp:content(s) end;
		description = function(s) p [[Небольшое и не слишком удобное.]]; return false; end;
	}:attr'supporter,enterable';
	Furniture {
		-"диванчик,диван";
		inside_dsc = [[Ты развалился на диванчике.]];
		dsc = function(s) mp:content(s) end;
		description = function(s) p [[Ты не ожидал увидеть такой диванчик на лунной станции.]]; return false; end;
	}:attr'supporter,enterable';
	Furniture {
		-"стол";
		inside_dsc = [[Ты стоишь на столе.]];
		dsc = function(s) mp:content(s) end;
		description = function(s) p [[Стол сделан из пластика.]]; return false; end;
	}:attr'supporter,enterable':with {
		obj {
			-"бутерброд,сыр,хлеб";
			init_dsc = [[На столе лежит бутерброд.]];
			description = [[Кусок белого хлеба с сыром. Выглядит вполне съедобно.]];
		}:attr 'edible';
	};
	Path {
		-"научный модуль";
		desc = [[Ты можешь зайти в научный модуль.]];
		walk_to = 'lab';
	};
	Path {
		-"жилой модуль";
		desc = [[Ты можешь зайти в жилой модуль.]];
		walk_to = 'liv';
	};
}

room {
	nam = 'liv';
	title = 'жилой модуль';
	-"жилой модуль";
	out_to = 'tech';
	in_to = 'sklad';
	s_to = 'tech';
	n_to = 'sklad';
	before_Sleep = function(s)
		if _'spaceman1':inside'кровать' then
			walkin 'stage6'
		else
			p [[Сейчас не время спать.]]
		end
	end;
	dsc = function(s)
		p [[В жилом модуле установлены кровати и шкафчики. Ты можешь вернуться в служебный модуль на юг или пройти в складской модуль на север.]]
	end;
	onexit = function(s)
		if _'spaceman1':inside'кровать' and not mission then
			p [[Лучше воспользоваться оставшимся временем, чтобы отдохнуть.]]
			return false
		end
	end;
}:with {
	'wall',
	Furniture {
		-"шкаф,шкафчик|шкафы,шкафчики";
		description = [[Небольшие шкафчики из алюминия стоят у каждой кровати.]];
		before_Open = [[Ничего интересного в шкафчиках ты не обнаружил.]];
	}:attr'concealed,openable,container';
	Furniture {
		-"кровати";
		description = [[В отличие от кресел на "Арго", на этих кроватях можно нормально спать!]];
		["before_Enter,Climb"] = function(s)
			mp:xaction("Enter", _"кровать")
		end;
	}:attr'concealed';
	Furniture {
		nam = 'кровать';
		-"кровать";
		inside_dsc = [[Ты лежишь на кровати.]];
		dsc = function(s)
			mp:content(s)
		end;
		before_Enter = function(s)
			if _'spaceman1':inside(s) then
				mp:xaction("Sleep")
				return
			end
			return false
		end;
		description = function(s)
			p [[Глядя на кровать ты понимаешь как ты устал.]];
			return false
		end
	}:attr'enterable,supporter';
	Path {
		-"служебный модуль";
		desc = [[Ты можешь зайти в служебный модуль.]];
		walk_to = 'tech';
	};
	Path {
		-"складской модуль,склад";
		desc = [[Ты можешь зайти в складской модуль.]];
		walk_to = 'sklad';
	};
}

room {
	nam = 'sklad';
	title = 'складской модуль';
	-"складской модуль,склад";
	out_to = 'liv';
	s_to = 'liv';
	dsc = function(s)
		p [[В складском модуле работает дежурное освещение. Ты можешь выйти в жилой модуль на юг. Склад завален оборудованием. Здесь же расположен туалет.]]
	end;
}:with {
	Ephe { -"освещение|свет" };
	'wall',
	Careful {
		-"оборудование";
		description = [[Сейчас тебя не интересует оборудование.]];
	};
	Careful {
		-"туалет|кабинка";
		description = [[Небольшая кабинка в углу склада.]];
		["before_Open,Enter,Climb,Use"] = function(s)
			if s:once() then p [[Ты воспользовался туалетом.]]
			elseif _'alex':inroom() == here() and s:once'alex' then p [[Александр воспользовался туалетом.]]
			else
				p [[Тебе не нужно в туалет.]]
			end
		end;
	}:attr'enterable,container,openable';
	Path {
		-"жилой модуль";
		desc = [[Ты можешь выйти в жилой модуль.]];
		walk_to = 'liv';
	};
}
game.after_Sleep = [[Спать сейчас?]];
global 'mission' (false)
cutscene {
	nam = 'stage8';
	title = 'Луна-9';
	text = {
	[[Ты сел в кресло. Перед тобой в чёрном небе висел серп Земли. {$fmt em|Они} торопили тебя и ты не мог сопротивляться долго. Уверенным движением пальцев ты настроил режим передачи. Осталось только запустить процесс трансмиссии. {$fmt em|Они} готовились. Ты чувствовал их вкрадчивое шептание в закоулках подсознания. Сколько их? Легион!]];
	[[-- Что же ты медлишь? -- услышал ты глубокий голос лунной принцессы. -- Скоро мы будем вместе! Начинай!]];
	[[Твои пальцы сами нашли тумблер и переключили его. Только сейчас ты заметил, как на чёрном небе проступили звёзды.]];
	[[А потом всё поглотил бледный лунный свет.]];
	};
	next_to = 'home';
	exit = function(s)
		_'жена'.talk_step = 0
		_'жена'.talk2 = false
		place('жена', 'home')
		_'скафандр':attr'~worn'
		inv():zap()
		DaemonStop 'радио'
		place('телефон', 'столик')
		pic_add '1'
	end
}

cutscene {
	nam = 'stage7';
	title = 'Луна-9';
	enter = function(s)
		inv():cat(_'stage6'.inv)
	end;
	text = {
		[[-- Борис! Командир! Что с тобой! -- слышишь ты сквозь сон крики Александра.^
		-- Всё нормально. Кошмар. Сколько я спал?^
		-- Пол часа, командир.^
		-- Ложись, Саша, я подежурю.^
		-- Но ещё пол часа!^
		-- Я уже не засну. Спи ты. Считай, это приказ!^
		-- Как скажешь, командир.]],
		[[Лунная принцесса не обманула. Ты знаешь, что нужно делать. С болью в сердце
		ты выходишь из жилого модуля. Сначала, нужно заблокировать дверь базы, чтобы Александр не мешал миссии.]];
	};
	exit = function(s)
		move(me(), 'tech')
		mission = true
		me().scope:add'принцесса'
	end;
}

Ephe {
	nam = "принцесса";
	-"принцесса,лунная принцесса";
	description = [[Ты вспоминаешь {$fmt em|её}.]];
	before_Talk = [[Она сама говорит с тобой, когда хочет.]];
}

cutscene {
	nam = 'stage6';
	title = 'Луна-9';
	inv = std.list {};
	enter = function(s)
		DaemonStop 'alex'
		s.inv:cat(inv())
		inv():zap()
	end;
	text = {
		[[Ты выбрал одну из кроватей и сразу повалился на неё, даже не сняв ботинки.^^
		За долгие годы службы ты научился засыпать в любых условиях, когда предоставляется такая возможность. Сейчас в твоём распоряжении был всего час. Половина времени выделенного на отдых, которое вы поделили с Александром пополам.^^
		Ты не заметил как провалился в глубокий сон.^-- Я привёл его, моя принцесса! -- кто сказал это? Не важно, ты спишь.]];
	};
	next_to = 'замок';
	exit = function(s)
		pic_add '13'
	end;
}
room {
	-"зал";
	nam = 'замок';
	title = 'Во дворце';
	step = 1;
	before_Wake = function(s)
		if s.step == 1 or s.step == 2 then
			p [[Это, наверное, сон? Если и так, то зачем просыпаться?]]
		elseif s.step == 3 then
			p [[Ты пытаешься проснуться. Изо всех сил ты пытаешься широко разжать глаза. Это часто помогало тебе во время кошмаров. Но только не сейчас.]]
		else
			walkin 'stage7'
		end
	end;
	dsc = function(s)
		p [[Ты стоишь посреди огромного, искрящегося серебром зала. К высокому своду взлетают
		мраморные колонны. Красная ковровая дорожка под твоими ногами ведёт к трону. В резных окнах
		ты видишь черное небо. ]];
	end;
}:with {
	Ephe { -"свет", description = [[Свет не похож на солнечный. Это лунный свет! Догадываешься ты.]] };
	Distance {-"люстры", description = [[Каждая люстра, словно россыпь ярких звёзд.]] };
	Distance { -"свод,потолок,узор",
		description = [[Свод зала расписан причудливым узорами. Роскошные люстры заполняют зал светом!]] };
	Useless { -"окна,пейзаж*", description = [[Сквозь высокие прорези окон ты видишь пейзаж... Лунный пейзаж.]] };
	Distance { -"небо", description = [[Чёрное небо, на котором ты не видишь звёзд. ]] };
	Careful { -"дорожка|ковёр", description = [[Ты видишь, что над дорожкой клубится розоватый пар.]]; before_Enter = [[Ты и так стоишь на ковровой дорожке.]]; ["before_GetOff,Exit"] = "Зачем?"; };
	Ephe { -"пар", ["before_Smell,Taste"] = [[Запах благовоний.]], description = [[Этот пар тебе что-то напоминает, но ты не можешь вспомнить что именно.]]; };
	obj {
		-"колонны";
		description = [[Высокие колонны абсолютно гладкие и ровные, сверкают яркими вспышками в свете искрящихся люстр.]];
	}:attr'scenery';
	Furniture {
		nam = 'трон';
		-"трон,спинк*,серп*";
		dsc = function(s)
			mp:content(s)
		end;
		description = function(s)
			p [[Трон великолепен! На вид он сделан из мрамора. Высокая спинка трона возвышается на 2 метра. Спинку трона венчает изображение лунного серпа.]]
			return false
		end;
		before_Walk = function(s)
			mp:xaction('Walk', _'girl')
		end;
		before_Any = function(s, ev)
			return _'girl':before_Any(ev)
		end;
	}:attr'supporter,enterable':with {
		obj {
			nam = 'girl';
			scope = {
				Careful {
					-"корона";
					description = [[Ты где-то видел эту корону раньше. Но где?]];
				};
				Careful {
					-"платье";
					description = [[Сквозь воздушное платье ты видишь белую, гладкую кожу девушки. У тебя кружится голова.]];
				};
			};
			-"девушка,принцесса,фигур*,голов*";
			step = 0;
			["before_Push,Attack"] = [[Ты не можешь сделать это!]];
			daemon = function(s)
				if s.step == 0 then
					s.step = 1
					return
				end
				if s:inside'трон' and s.step == 1 then
					p [[Заметив, что ты заворожён её чарами, девушка улыбнулась манящей улыбкой и, легко встав
					с трона, спустилась к тебе.]]
					move(s, here())
				else
					if s.step == 1 then
						p [[Девушка протягивает правую руку и проводит ладонью по твоей щеке.^
						-- Бедный... Но всё в прошлом. Не бойся, я подарю тебе забвение, которого ты жаждешь. -- её глубокий голос пронзает тебя насквозь. Кажется, ты парализован.]]
						_'замок'.step = 3
						s.step = 2
					elseif s.step == 2 then
						p [[Девушка улыбается манящей улыбкой, в её глазах ты видишь власть и кокетство. Она гладит тебя по затылку не отпуская от себя. И тебе кажется, что она видит все твои тайные желания.^
						-- Бедный, бедный космонавт. Я залечу твои шрамы, я выполню все твои желания. Я стану
						твоей принцессой. Но сначала, ты должен помочь нам.^^От благовоний и близости её тела ты почти потерял рассудок.]];
						s.step = 3
					elseif s.step == 3 then
						p [[Девушка понимающе улыбается.^
						-- Я вижу, что ты готов, я прочитала ответ в твоём сердце. Ты -- мой. Когда вернёшься в свой мир, ты будешь знать всё, что нужно сделать. И ты сделаешь всё как надо! И тогда, вернувшись ко мне, ты получишь всё то, о чём мечтал, но не смел надеяться.]]
						s.step = 4
					elseif s.step == 4 then
						p [[Девушка обнимает тебя левой рукой. По твоему лицу стекают капельки пота.^
						-- Все раны будут залечены. Всё, что тебя терзало в прошлом -- забыто. В мире, который твоя раса называет сном, нет границ.  Но он так же реален, как и ваш. К счастью, твой народ не знает об этом. Пока.]]
						s.step = 5
					elseif s.step == 5 then
						p [[-- Ты поможешь нам. Перенесёшь нас всех в себе. Ты сможешь. Я познала тебя, ты подходишь для нашей миссии и, на этот раз, всё получится. Теперь я -- твоя лунная принцесса. Когда ты проснёшься, ты будешь знать что делать.]]
						s.step = 6
					elseif s.step == 6 then
						p [[Лунная принцесса отпускает тебя и возвращается на трон. Тебя бъёт сильная дрожь. Ты хочешь {$fmt em|проснуться}.]]
						s.step = 7
						move(s, 'трон')
						_'замок'.step = 4
					end
				end
			end;
			dsc = function(s)
				if s:inside'трон' then
					return false
				else
					p [[Рядом с тобой стоит девушка.]]
				end
			end;
			before_Smell = [[Она пахнет благовониями. У тебя кружится голова.]];
			description = function(s)
				local v = _'замок'
				if v.step == 1 then
					p [[Отсюда тебе плохо видны черты её лица.]];
				else
					if not s:inside'трон' then
						p [[У тебя кружится голова от её близости. Девушка видит твою робость и её это забавляет.]]
						return
					end
					pn [[От чувственных черт её лица твоё сердце испытывает сладкую тоску.
					Воздушное платье девушки почти не скрывает изящную фигуру и гладкую, нежную кожу.
					На голове девушки ты видишь миниатюрную корону, искрящуюся серебром.^]]
					p [[Странно, но тебе кажется, что ты её где-то видел раньше. Только тебе сложно вспомнить, где именно.]]
					DaemonStart(s)
				end
			end;
			["before_Kiss,Touch,Taste,Take,Pull"] = function(s)
				if _'girl'.step >=3 then
					if _'girl'.step >= 6 then
						p [[Ты должен проснуться!]]
						return
					end
					p [[Ты не можешь сопротивляться наваждению и привлекаешь девушку к себе.
					Ты слышишь смех, и тебе становится страшно. Но ты не можешь ничего сделать.
					Твоя воля парализована. Всё, что ты хочешь. Чтобы она стала твоей принцессой.]]
				else
					p [[Даже если это всего лишь сон, тебе не хватает смелости сделать это.]]
				end
			end;
			before_Talk = function(s)
				local v = _'замок';
				p [[Ты не можешь осмелиться заговорить с ней.]]
			end;
			before_Any = function(s, ev)
				local v = _'замок'
				if ev == 'Exam' or ev == 'Look' or ev == 'Walk' or ev == 'Wait' or ev == 'Think'
					or v.step > 1 then
					return false
				end
				p [[Сначала нужно подойти к трону.]]
			end;
			before_Walk = function(s)
				local v = _'замок'
				if v.step > 1 then
					p [[Ты и так находишься у трона.]]
				else
					p [[Ты подошёл к трону.]]
					v.step = 2
				end
			end;
		}
	}
};

mp.msg.HELP = [[{$fmt b|КАК ИГРАТЬ?}^^

Вводите ваши действия в виде простых предложений вида: глагол -- существительное. Например:^
> открыть дверь^
> отпереть дверь ключом^
^
Описание обстановки: {$fmt em|осмотреть}, {$fmt em|осм} или просто нажмите "ввод".^
Осмотр предмета: {$fmt em|осмотреть книгу} или просто {$fmt em|книга}.^
Попробуйте {$fmt em|осмотреть себя} и узнать, кто вы. Предметы с собой: {$fmt em|инвентарь} или {$fmt em|инв}.^
^
Ходить по направлениям: {$fmt em|идти на север} или {$fmt em|север} или просто {$fmt em|с}, {$fmt em|вверх} или {$fmt em|вв}, {$fmt em|вниз} или {$fmt em|вн}.
Ходить по соседним локациям: {$fmt em|идти в лабораторию} или {$fmt em|в лабораторию}, {$fmt em|внутрь}, {$fmt em|наружу}.^
Иногда нужно просто {$fmt em|ждать}.
^^
Вы можете воспользоваться клавишей "TAB" для автодополнения ввода и сокращать существительные.
]]
