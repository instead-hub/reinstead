--$Name: Краски октября$
--$Version: 1.0$
--$Author: Пётр Косых$
--$Info: Интерактивная новелла\nПереиздание новеллы "Краски сентября"$
require "fmt"
fmt.dash = true
fmt.quotes = true
require 'parser/mp-ru'
require 'snapshots'
include 'lib'

global 'mission' (false)
global 'mission2' (false)
global 'ranen' (false)
global 'alarm' (false)
global 'deaf' (false)
global 'know_cat' (false)

me().description = function(s)
	if here() ^ 'park1' then
		p [[Кажется, со мной всё в порядке.]]
		return
	end
	if me():where() ^ 'hole' then
		if ranen then
			return [[Похоже, я ранен.]]
		end
		return [[Меня беспокоит острая боль в спине.]]
	end
	p [[Мне не хочется заниматься самоанализом.]];
end

function game:before_Draw(w)
	if not have 'brush' then
		p [[Мне нужна кисть.]]
		return
	end
	if not _'brush'.paint then
		p [[На кисти нет нужной краски.]]
		return
	end
	if have 'plakat' then
		if _'plakat'.draw then
			p [[Нет времени рисовать, да и краска кончилась.]]
			return
		end
		if not w then
			p [[Что именно нарисовать?]]
			return
		end
		if w:find("^на ") or w:find("^по ") or w:find("^под ") or w:find(" на ") or w:find(" по ") then
			p [[Попробуйте просто {$fmt em|"нарисовать что-то"}.]]
			return
		end
		if w:find("^кот") and know_cat then
			_'plakat'.draw = true
			p [[И тут мне пришла в голову идея. Я достал свою кисточку, на которой всё ещё была краска.
			Развернул плакат чистой стороной и схематично нарисовал котёнка.]]
			return
		end
		if not w then w = '' end
		if w ~= '' then w = '"'..w..'"' end
		p ([[У меня осталось немного краски на кисти, и есть бумага, но желания рисовать ]]..w ..[[ что-то нет...]])
		return
	end
	if not _'pict':visible() then
		p [[Здесь нет холста.]]
		return
	end
	if here()^'mast' and here().n >= 5 and not _'phone'.talked then
		p [[Телефонный звонок мешает сосредоточиться.]];
		return
	end
	if _'girl'.seen then
		p [[Там за окном кто-то стоит на краю крыши!]]
		return
	end
	if _'win':hasnt'open' then
		if here().rain then
			here().rain = false
			here():daemonStop()
			p [[Этот звонок выбил меня из колеи. Вдруг я заметил, что шум дождя утих. Может, открыть окно?]]
			return
		end
		p [[Этот звонок выбил меня из колеи. Может, открыть окно?]];
		return
	end
	p "Что-то нет вдохновения."
end
Verb {
	"[|на|раз|по]рис/овать",
	"* :Draw",
	": Draw",
}
VerbExtendWord {
	"#Wait",
	"[от|пере]дохн/уть,отдыхать",
}
Verb {
	"макать,[|об]макн/уть",
	"{noun}/вн,held в {noun}/вн : Smear",
	"~ в {noun}/вн {noun}/вн,held: Smear reverse",
}
Verb {
	"[|с|на]мазать",
	"~ {noun}/вн,held {noun}/тв : Smear",
	"~ {noun}/тв {noun}/вн: Smear reverse",
}
function mp:Smear(w)
	if not w.smear then
		p(w:Noun'вн', " нельзя намазать.")
		return
	end
	return false
end
function game:before_Ring(w)
	if not here() ^ 'mast' or ((not w or w^'phone') and not _'phone'.seen) then
		p [[Для этого нужен телефон.]]
		return
	end
	return false
end

function game:before_Any(ev, w)
	if ev == "Ask" or ev == "Say" or ev == "Tell" or ev == "AskFor" or ev == "AskTo" then
		if w then
			p ([[Попробуйте просто поговорить с ]], w:noun'тв', ".")
		else
			p [[Попробуйте просто поговорить.]]
		end
		return
	end
	return false
end
global 'picture' (false)

function game:pic()
	if not picture then return false end
	return 'gfx/'..picture..'.png'
end

function set_pic(n)
	picture = n
end

game.dsc = [[{$fmt b|{$fmt c|КРАСКИ ОКТЯБРЯ}}^^

{$fmt r|{$fmt b|Версия:} 1.0^
Пётр Косых^
{$fmt em|Москва, осень 2021 г.}}^^Если вам необходима справка по игре, наберите "помощь" и нажмите "ввод".
^^{$fmt c|***}^^]];

function init()
	pl.word = -"я/мр,1л"
	mp.togglehelp = true
	mp.autohelp = false
	mp.autohelp_limit = 8
	mp.compl_thresh = 1
	pl.room = 'intro'
end

cutscene {
	nam = 'intro';
	title = 'пролог';
	text = [[В то утро я, как обычно, был в своей мастерской.
		Капли дождя оставляли на стекле небольшого чердачного окна
		длинные следы. Я сидел на стуле и смотрел на картину, которую
		собирался закончить вот уже несколько дней...^^
		Осень на картине, осень в моей душе...]];
	next_to = 'mast';
	exit = function()
		set_pic 'mast'
	end
}

cutscene {
	nam = 'phone_dlg';
	title = 'Телефонный разговор';
	text = {
		[[-- Привет, старик, ну как ты? -- услышал я знакомый голос.^
		-- Нормально..]],
		[[-- Нормально? Что-то изменилось у тебя? Ха-ха-ха! Ладно, не важно.
		Это всё не важно, потому что я нашёл тебе работу!!! Одевайся, через час у тебя
		собеседование!^
		-- Собеседование?]],
		[[-- Да, старик, собеседование! Вопросы и благодарности потом. Я им
		расписал тебя в лучших красках. Кажется, они даже знают твою фамилию,
		что, признаюсь, меня удивило. В общем, давай, собирайся, записывай адрес...^-- А что за работа?]],
		[[-- Слушай, ты меня пугаешь! Не в твоей ситуации выбирать. Не бойся, работёнка не грязная, будешь рисовать.^ -- Рисовать?]],
		[[-- Да, рисовать! Ты что-то туго сегодня соображаешь. Дай угадаю. Опять напился вчера? Ах-ха-ха-ха! Но теперь твоя жизнь изменится. И всё благодаря мне!^Ладно, у тебя мало времени. Одевайся. Найди какой-нибудь костюм, или что-то вроде того. Тебе нужно добраться до рекламного агентства "Зеркало", оно находится возле...]],
		[[-- Постой, постой... Рекламное агентство? Рисовать рекламу?^-- Ну, конечно! В рекламных агентствах рисуют рекламу. Наконец-то ты приходишь в себя. Короче, это одно из лучших агентств, и тебе крупно повезло, потому что...]],
		[[-- Я не поеду на собеседование, извини, но я...^
		-- Что? Что ты сказал? Я что-то не понял.^
		-- Я не могу. Нет, я не...^
		-- Да ты точно не в себе! Я уже звонил Кате. Она была так рада, что ты, наконец, встанешь на ноги. А ты просто... ломаешься!? Реклама ему не по вкусу! Художник он! Мараться не охота! Да я на...]],
		[[-- Я не могу, понимаешь, просто не могу...^
		-- Молчи! Не хочу слушать этот бред! Я знаю заранее всё то, что ты мне сейчас скажешь! Лучше послушай меня! Хочешь ты этого или нет, тебе придётся играть по правилам игры! Мир крутится деньгами! Если не понимаешь этого, тебя выбросит за борт! Так что...]],
		[[-- Извини, Борис, я не могу сейчас говорить. Я должен дорисовать картину, потом созвонимся...^
		-- Да пошёл ты к чертям собачьим!^^
		На другом конце провода Борис бросил трубку, и я услышал короткие гудки.]]
	};
}
obj {
	nam = 'phone';
	-"телефон|трубка";
	talked = false;
	seen = false;
	before_Any = function(s)
		if s.seen then return false end
		p [[Куда же я его подевал?]]
	end;
	description = function(s)
		p [[Обычный проводной телефон из синего пластика.]]
		if here().n > 5 and not s.talked then
			p [[Звонит, не переставая.]]
		end
	end;
	before_Attack = [[Потом придётся покупать новый.]];
	before_Ring = function(s)
		if _'girl'.exam then
			mp:xaction("Take", s)
			return
		end
		return false
	end;
	['before_Take,Talk'] = function(s)
		if _'girl'.exam then
			p [[Мне кажется, уже поздно звонить по телефону, надо спешить!]]
			return
		end
		p [[Я поднял телефонную трубку.]];
		if here().n >= 5 and not s.talked then
			s.talked = true
			here():daemonStop()
			walkin 'phone_dlg'
		else
			p [[Гудки... Я положил трубку.]]
		end
	end;
}:attr 'concealed,ring'

obj {
	-"окно";
	nam = 'win';
	before_Open = function(s)
		if here().rain then
			p [[За стеклом дождь, не хочу, чтобы он намочил мои картины.]]
			return
		end
		return false
	end;
	after_Open = function(s)
		p [[Я открыл окно. В мастерскую дыхнуло свежестью.]]
		enable 'girl'
		if s:once'girl' then
			_'girl'.seen = true;
			p [[Мой взгляд скользнул по мокрой крыше, когда... Я заметил чей-то силуэт на самом краю!]]
		else
			p [[Я вижу силуэт на краю крыши!]];
		end
	end;
	description = function(s)
		p [[Небольшое чердачное окно, через которое поступает свет в мою мастерскую. Оно выходит на покатую мокрую крышу.]]
		if _'girl'.seen then
			p [[Я вижу силуэт на краю крыши!]]
		end
		return false
	end;
	['before_Enter,Walk'] = function(s)
		if not s:has'open' then
			p [[Окно закрыто.]]
			return
		end
		if _'girl'.seen and not _'girl'.exam then
			_'girl':description()
		end
		if _'girl'.exam then
			walk 'roof'
			return
		end
		p [[Мне не хочется сейчас гулять по крыше.]];
	end;
}:attr 'openable,scenery,enterable,door';

Furniture {
	-"стул";
	nam = 'stul';
	description = [[Деревянный стул. Я привык к его деликатному поскрипыванию.]];
}:attr'concealed,enterable,supporter'

Furniture {
	-"картины/мн|картина";
	nam = 'drawings';
	dsc = [[Вдоль стен на полу лежат картины.]];
	description = [[Мои картины плохо продаются, но на жизнь всё-таки хватает.]];
	['before_Take,Push,Pull,Attack'] = [[Сейчас я работаю над картиной, которую я назвал "Краски октября".]];
}

Useless {
	-"бумаги/мн|бумага|наброски,обрывки";
	nam = 'papers';
	dsc = [[В углу валяются обрывки бумаги.]];
	description = [[Неудачные наброски. Их очень много, не хочу их видеть.]];
	['before_LookUnder,Search'] = function(s)
		p [[Этот хлам давно пора выкинуть.]]
		if not _'phone'.seen then
			p [[Я покопался в набросках и обнаружил там свой телефон.]];
			_'phone'.seen = true
		else
			p [[Больше ничего интересного.]]
		end
	end;
	before_Take = function(s)
		mp:xaction('Exam', s)
	end;
}:attr'~scenery'

Furniture {
	-"холст|картина|мольберт";
	nam = 'pict';
	dsc = [[Напротив окна в центре комнаты стоит мольберт с моим холстом.]];
	description = function(s)
		p [[На холсте изображена осень и скамейка в парке. Картина почти закончена.]]
		pr [[Перед холстом находится табуретка]]
		if where('paint') ^ 'tabur' and where 'brush' ^ 'tabur' then
			p [[, на которой лежат краски и кисть.]];
		else
			p "."
			mp:content(_'tabur')
		end
	end;
}

obj {
	-"масляные краски,краски/мн|краска";
	nam = 'paint';
	smear = false;
	before_Take = [[Не зачем брать краски в руки.]];
	description = [[Мои масляные краски.]];
	['before_Push,Pull,Transfer'] = [[Я могу их уронить.]];
}

obj {
	-"кисть,кисточка";
	nam = 'brush';
	paint = false;
	description = [[Это моя любимая кисточка.]];
	['before_Drop,PutOn'] = function(s, w)
		if 'tabur' ^ w then
			p [[Я положил кисть обратно.]]
			move(s, w)
			return
		end
		if w ^ 'girl' then
			p [[Что за ребячество?]]
			return
		end
		if here()^'mast' then
			return [[Место кисти -- на табуретке.]]
		end
		p [[Кисть мне еще пригодится.]]
	end;
	before_Insert = function(s, w)
		if w ^ 'paint' then
			mp:xaction("Smear", s, w)
		else
			return false
		end
	end;
	before_Smear = function(s)
		if mp:check_held(s) then
			return
		end
		p [[Я обмакнул кисточку в краску.]];
		s.paint = true
	end;
}

Furniture {
	-"табуретка";
	nam = 'tabur';
	before_Enter = [[Тут мои краски!]];
	['before_Take,Push,Pull'] = [[Табуретка должна стоять возле мольберта.]];
}:attr'supporter,enterable,concealed':with { 'paint', 'brush' }

obj {
	-"дверь|выход";
	nam = 'door';
	['before_Walk,Enter,Open'] = [[Нет настроения гулять.]];
	description = function()
		p [[Обшарпанная деревянная дверь, окрашенная в синий цвет.]];
		return false
	end;
}:attr'static,concealed,enterable,openable'

obj {
	nam = 'girl';
	exam = false;
	seen = false;
	word = function(s)
		if not s.exam then
			return -"силуэт,человек";
		else
			return -"девушка|силуэт,человек";
		end
	end;
	description = function(s)
		p [[Тусклый тонкий силуэт на краю крыши. Мне кажется, это девушка!]]
		if here() ^ 'roof' then
			p [[Что она делает здесь? Надо что-то предпринять!]]
			return
		end
		if not s.exam then
			p [[Что она делает там? Неужели? О нет, она собирается прыгать?]];
			s.exam = true;
		end
	end;
	before_Talk = function(s)
		if here() ^ 'roof' then
			p [[-- Послушайте! Эй, вы! -- громко произношу я, но девушка не обращает на меня внимания.]];
			return
		end
		p [[-- Эй, постойте! Послушайте меня!!! -- услышал я свой хриплый и дрожащий голос. Конечно, ничего не изменилось.]];
	end;
	before_Default = function(s, ev)
		if eph_event(ev) or ev == 'Walk' then
			return false
		end
		p [[Девушка далеко.]]
	end;
	Walk = function(s)
		if here() ^ 'roof' then
			walk 'fall'
			return
		end
		mp:xaction('Enter', _'win')
	end;
}:disable():attr'animate,concealed';

room {
	-"мастерская,комната";
	nam = 'mast';
	title = 'мастерская';
	rain = true;
	before_Ring = function(s, w)
		if w or not _'phone'.seen then
			return false
		end
		mp:xaction('Ring', _'phone')
	end;
	out_to = function()
		if _'girl'.seen then
			p [[На крышу можно попасть через окно.]]
			return
		end
		return 'door';
	end;
	n_to = 'win';
	n = 1;
	before_Cry = function(s)
		if _'girl'.seen then
			mp:xaction('Talk', _'girl')
			return
		end
		return false
	end;
	enter = function(s)
		if s:once'ring' then
			s:daemonStart()
		end
	end;
	before_Listen = function(s)
		if s.rain then
			p [[Я слышу тихий стук капель.]]
		else
			p [[Тихо.]]
		end
	end;
	daemon = function(s)
		if not here() ^ 'mast' then
			return
		end
		s.n = s.n + 1
		if s.n == 5 then
			p [[Вдруг раздался телефонный звонок.]]
			if not _'phone'.seen then
				p [[Я огляделся, но телефона нигде не было видно. Куда же я его дел?]];
			end
		elseif s.n > 5 and not _'phone'.talked then
			p [[Я слышу, как звонит телефон.]]
			if not _'phone'.seen then
				if rnd(3) >= 2 then
					p [[Где этот проклятый аппарат?]]
				end
			end
		elseif s.n > 7 and _'brush'.paint then
			s:daemonStop()
			s.rain = false
			p [[Я замечаю, что шум дождя за окном стих.]]
		else
			p [[Я слышу тихий шум дождя за окном.]]
		end
	end;
	dsc = [[В моей мастерской почти нет места, это просто чердак старого дома,
		который уже давно пора сносить. Но здесь есть окно, выходящее на север,
		и достаточно места, чтобы работать.]];
	obj = { 'win', 'stul', 'pict', 'drawings', 'papers', 'phone', 'tabur', 'girl', 'door',
		Path {
			-"крыша";
			desc = [[На крышу можно попасть через окно.]];
			walk_to = 'win';
		},
	Ephe { -"дождь", description = function(s)
		if here().rain then
			p [[Осенний дождь тихо шумит за окном.]]
			return
		end
		p [[Дождь уже кончился.]]
	end } }
}

room {
	-"крыша";
	nam = 'roof';
	title = 'На крыше';
	cant_go = "Нужно что-то предпринять!";
	s_to = 'mast';
	d_to = function(s)
		p [[Прыгнуть?]]
	end;
	before_Jump = "Это не выход из ситуации!";
	out_to = 'mast';
	before_Cry = function(s)
		mp:xaction('Talk', _'girl')
	end;
	enter = function(s)
		set_pic 'roof'
		p [[Я понял, что должен что-то делать. Выбравшись через окно, я встал на ноги и осторожно осмотрелся.]];
	end;
	dsc = [[Я нахожусь на покатой и угрожающе мокрой крыше. На краю крыши я вижу силуэт девушки.]];
	obj = { 'girl' };
}

cutscene {
	nam = 'fall';
	title = '...';
	enter = function(s)
		set_pic 'leaves'
	end;
	text = {
		[[Осторожно ступая, я начал своё движение в сторону девушки.
		Шаг, другой! Только бы успеть! Я не сводил с неё глаз, когда...]];
		[[Моя правая нога соскользнула и я с грохотом упал на мокрую поверхность. Через мгновение я уже катился по жестяному скату!]];
		[[Как странно, но мыслей не было. Я отстранённо подумал о девушке, потом, почему-то вспомнил о своей
		незаконченной картине. "Краски октября"... Огненно-красные листья в парке, в котором я никогда не был...]],
		[[Когда я достигну края? Мир завертелся у меня перед глазами. Внезапно я отчётливо почувствовал запах мокрой листвы.]];
	};
	next_to = 'park1';
}

Path {
	nam = 'skam_nav';
	-"скамейка,скамья";
	walk_to = function(s)
		if here() ^ 'park1' then
			return 'skam'
		end
		return 'park2';
	end;
	description = function(s)
		mp:xaction('Exam', _'skam')
	end;
	desc = [[Я могу пойти к скамейке.]];
}

room {
	-"парк";
	nam = 'park1';
	title = 'Парк';
	e_to = 'park2';
	enter = function(s, f)
		if f ^ 'fall' then
			p [[... Я лежал лицом вниз, уткнувшись в мокрые листья. Голова немного кружилась, и я почувствовал тошноту.
			Странно, я всё ещё на крыше? Я поднял голову и осмотрелся. Потом осторожно, не веря в то,
			что цел, поднялся на ноги. Это был парк. Это не могло быть правдой, но это было так!]]
			if not have'brush' then
				p [[В моей руке находился какой-то предмет. Я с удивлением понял, что держу в руках свою кисть.
					На кисти была свежая краска. В замешательстве я убрал кисть в карман.]]
				take 'brush'
			end
		end
	end;
	dsc = [[Я нахожусь в парке. Мокрые осенние листья под ногами. Неподалёку я вижу скамейку.]];
	obj = { 'sky', 'leaves', 'trees', 'skam_nav' };
}

Useless {
	nam = 'leaves';
	-"листья|листва";
	description = [[Осень в самом разгаре.]];
}:attr'concealed,supporter';

Useless {
	nam = 'trees';
	-"деревья";
	description = [[Листва ещё осталась, но скоро и она облетит...]];
}:attr'scenery,supporter';

Distance {
	-"небо|облака,небеса";
	nam = 'sky';
	description = function(s)
		if mission2 and not visited 'roof2' then
			p [[Я вижу в небе чёрные силуэты самолетов!]]
			return
		end
		p [[Хмурое осеннее небо заволокло облаками.]];
	end;
	before_Talk = [[Я произнёс про себя молитву.]];
}

obj {
	nam = 'skam';
	-"скамейка,скамья,скамеечка";
	description = function(s)
		if here() ^ 'entrance' then
			p [[Скамейка отсюда плохо различима.]]
			return
		end
		p [[Я был уверен, что это та самая скамейка -- с моей картины!
		Удивительное чувство, ведь я не мог её видеть раньше! И тем не менее,
		вот она -- зелёная скамейка в осеннем парке...]];
	end;
	before_Default = function(s, ev)
		if eph_event(ev) then
			return false
		end
		if not here() ^ 'park2' then
			p [[Сначала нужно подойти к скамейке.]]
			return
		end
		return false
	end;
	found_in = { 'park2' };
}:attr'static,concealed,supporter,enterable';

obj {
	-"посетители,прохожие,люди";
	nam = 'people1';
	talk = false;
	ans = false;
	description = function(s)
		if here() ^ 'park2' then
			p "Я вижу пожилую пару, медленно направляющуюся к выходу из парка."
		else
			p [[Пожилые мужчина и женщина, явно супружеская пара.
			Женщина держит мужчину под руку.
			Он одет в чёрное пальто, она -- в сером.]]
		end
	end;
	before_Talk = function(s)
		if not here()^'entrance' then
			p [[Они слишком далеко.]]
			return
		end
		if not s.talk then
			s.talk = true
			DaemonStart 'street'
			p [[-- Простите, вы не подскажете что это за парк? -- осторожно начал я.^
			Они остановились. Я заметил как женщина, быстро бросив взгляд на мужчину,
			крепче сжала его руку.^
			-- Ло сентимос, но ентендемос -- вежливо, но вместе с тем как-то холодно, произнёс мужчина.]]
		else
			if not s.ans then
				s.ans = true
				p [[-- Извините, -- всё, что мне оставалось сказать.]]
			else
				p [[Они меня не поймут. Не стоит их беспокоить.]]
			end
		end
	end;
	before_Default = function(s, ev)
		if eph_event(ev) or ev == 'Walk' or here() ^ 'entrance' then
			return false
		end
		p [[Они слишком далеко.]]
	end;
	before_Walk = function(s)
		if here() ^ 'park2' then
			walk 'entrance'
			return
		end
		return false
	end;
}:attr'animate,concealed';

boy = obj {
	-"мальчик,парень,паренёк,пацан,ребёнок";
	nam = 'boy';
	talk1 = false;
	talk0 = false;
	panic = false;

	dsc = function(s)
		if mission2 then
			if where(me()) ^ 'hole' then
				p [[Мальчик находится рядом со мной.]]
			else
				p [[Я крепко держу мальчика за руку.]]
			end
			return
		end
		return false
	end;

	description = function(s)
		if mission2 then
			p [[Мальчик держит котёнка за пазухой пальто и, кажется,
			это всё, что его сейчас заботит.]]
			return
		end
		if here()^'sad' then
			p [[Я вижу, как он бродит от дерева к дереву.]]
			return
		end
		p [[Паренёк лет десяти с большими тёмными глазами на испачканном сажей лице.
		Одет в мешковатые темно-серые штаны и короткое пальто. На голове нелепо нахлобучена кепка.]]
		if here() ^ 'park2' then
			if not s.talk1 then
				p [[-- Ми гато се пиере! -- мальчик смотрел на меня черными выразительными глазами
				и явно ожидал ответа.]]
				s.talk1 = true
			else
				p [[Мальчик ждет ответа на свой вопрос.]]
			end
		end
	end;
	before_Walk = function(s)
		if here() ^ 'sad' then
			if not mission then
				p [[Я подошёл к мальчику.]]
				return
			end
			if mission and not mission2 then
				if s.panic then
					mp:xaction('Take', s)
				else
					p [[Я подошёл к мальчику.]]
				end
				return
			end
		end
		return false
	end;
	before_Attack = function(s)
		if not mission then
			p [[Этот помысел я быстро отсек.]]
			return
		end
		p [[Оглушить и оттащить в убежище? Нет, это плохая идея.]]
	end;
	before_Take = function(s)
		if mission2 then
			p [[Я покрепче схватил мальчика за руку.]]
			return
		end
		if not mission then
			p [[С чего бы это мне хватать мальчика?]]
			return
		end
		if not s.panic then
			mp:xaction('Talk', s)
			return
		end
		p [[Я попытался догнать мальчика, но он ловко использовал деревья для того,
		чтобы уйти от меня. Так ничего не выйдет!]]
	end;
	before_Talk = function(s)
		if mission2 then
			if deaf and deaf > 2 then
				p [[Я ничего не слышу!]]
				return
			end
			if ranen then
				p [[-- Ничего, скоро мы будем в безопасности. -- мой голос прозвучал
				устало и неубедительно. -- Нам осталось совсем немного.^
				С этими словами я показал рукой по направлению к переходу.^
				Мальчик ничего не ответил, а только кивнул и крепче прижал к
				груди своего котёнка.]]
				return
			end
			p [[Сейчас самое главное добежать до убежища, а поговорить можно и потом.]]
			return
		end
		if here()^'sad' then
			if not mission then
				p [[Интересно, кого он ищет? Но узнать это проблематично.]]
				return
			end
			if not s.panic then
				s.panic = true
				p [[Я подбежал к мальчику и схватил его за руку.^
				-- Скорей, бежим! Самолёты! -- я указал рукой в небо -- Опасно!^
				-- Ан пюедо! Деждано сен Аба! -- мальчик вырвал руку и отбежал от меня на безопасное расстояние.]]
				return
			else
				p [[-- Иди сюда! Бежим, у нас мало времени -- прокричал я в отчаянии. Но напуганный мальчик только ещё дальше углубился в сад.]];
			end
			return
		end
		p [[-- Прости, но я не понимаю... -- я растерянно развёл руками.^]]
		p [[Мальчик, кажется, совсем не удивился, а только разочарованно
		взглянул на меня, бросил что-то вроде: "Дискулпеме!" -- и убежал по
		парковой дорожке в сторону озера.]]
		move(s, 'sad')
		set_pic 'skam'
	end;
}:attr'animate';

door {
	-"ворота/мн";
	nam = 'vorota';
	before_Open = [[Ворота уже открыты.]];
	before_Close = [[Зачем мне делать это?]];
	description = function(s)
		if here()^'park2' then
			p [[Узор на чёрных железных прутьях ворот отсюда плохо различим.]]
			return false
		end
		p [[Чёрные пики прутьев ворот смотрят в хмурые осенние облака. Ворота открыты,
			на их широких створках сварен железный орнамент в виде восьмиконечных звёзд.]];
		return false
	end;
	before_Default = function(s, ev)
		if eph_event(ev) or ev == 'Walk' then
			return false
		end
		if not here()^'entrance' and not here()^'street' then
			p [[К воротам сначала нужно подойти.]]
			return
		end
		return false
	end;
	door_to = function()
		if here() ^ 'street' then
			return 'entrance'
		elseif here() ^ 'park2' then
			return 'entrance'
		else
			return 'street'
		end
	end;
}:attr'openable,open,enterable,scenery';

local function lalarm(s)
	if deaf and deaf > 2 then
		p [[Я ничего не слышу.]]
		return
	end
	if mission2 then
		if isDaemon 'airplane' then
			p [[Я слышу гул пролетающих над нами самолётов!]]
		else
			p [[Я слышу рокот приближающихся самолётов!]]
		end
		return
	end
	if not alarm then
		if here() ^ 'street' or here() ^ 'entrance' or here() ^ 'underground' then
			p [[Здесь совсем тихо.]]
		elseif here() ^ 'lake' then
			p [[Тихий плеск озера едва нарушает тишину.]]
		else
			p [[Здесь тихо, лишь тихий шелест осенних листьев едва нарушает тишину.]]
		end
		return
	end
	if here() ^ 'street' or here() ^ 'entrance' or here() ^ 'underground' then
		p [[Громкий звук сирены мешает сосредоточиться.]]
	elseif here() ^ 'underground2' then
		p [[Здесь почти не слышно звука сирены.]]
	else
		p [[Звук сирены слышен даже здесь.]]
	end
end
room {
	nam = 'entrance';
	title = 'У ворот';
	s_to = 'vorota';
	n_to = 'park2';
	out_to = 'vorota';
	in_to = 'skam_nav';
	before_Listen = lalarm;
	enter = function(s)
		set_pic 'vorota'
	end;
	dsc = function(s)
		p [[Немного покосившиеся железные ворота открыты. Отсюда хорошо заметна
	моя скамейка в парке. Сразу за воротами начинается город.]];
		if seen 'people1' then
			p [[Я вижу двух пожилых людей, которые медленно прогуливаются по парковой дорожке.]]
		end
	end;
	obj = { 'vorota', 'people1', 'sky', 'skam_nav', Path {
		-"город|улица";
		desc = [[Я могу выйти в город.]];
		walk_to = 'vorota';
	} };
	onexit = function(s, t)
		if mission2 and not t^'street' and not t ^'inhole' then
			p [[Нужно бежать к бомбоубежищу, а не гулять по парку!]]
			return false
		end
	end;
	exit = function(s)
		if _'people1'.talk and seen 'people1' then
			remove('people1', s)
			remove('people1', 'park2')
		end
	end
}
room {
	nam = 'park2';
	title = 'парк';
	out_to = 'vorota';
	n_to = 'lake';
	s_to = 'vorota';
	in_to = 'vorota';
	before_Listen = lalarm;
	onexit = function(s, t)
		if mission2 then
			if not t ^ 'entrance' and not t ^ 'inhole' then
				p [[Нужно бежать к бомбоубежищу, а не гулять по парку!]]
				return false
			end
			return
		end
		if seen 'boy' then
			p [[Было бы не вежливо проигнорировать этого паренька.]]
			return false
		end
		if not _'boy'.talk0 then
			_'boy'.talk0 = true
			move(boy, here())
			set_pic 'boy'
			p [[Я поднялся со скамейки и собрался уходить, когда обнаружил, что справа
				ко мне приближается одинокая фигурка в пальто. Это был мальчик, лет десяти.
				Он подбежал ко мне и, едва переведя дыхание, быстро, но негромко проговорил:^
				-- Устед но ас висто ал гато?]]
			return false
		end
	end;
	enter = function(s, f)
		set_pic 'skam';
		if not f ^ 'park1' then
			return
		end
		p [[Медленно, сопровождаемый тихим шорохом листвы, я побрёл к скамейке.
		Она была свободна. Я сел на скамейку и осмотрелся.]]
	end;
	dsc = function(s)
		if seen 'people1' then
			p [[Почти безлюдный осенний парк. Несильный ветер играет листьями под ногами немногочисленных посетителей.]]
		else
			p [[Парк безлюден. Только несильный ветер шелестит опавшей листвой.]]
		end
		p [[Ветви деревьев молчаливо смотрят в хмурое небо. Главная дорожка парка огибает небольшое
		озеро и заканчивается воротами главного входа.]];
	end;
	obj = { 'sky', 'trees', 'people1', 'vorota', 'lake_nav',
		Path {
			-"парковая дорожка,дорожка,дорога";
			desc = "Я могу пройти к озеру или воротам.";
			walk_to = 'lake';
		};
	};
}

Path {
	nam = 'lake_nav';
	-"озеро";
	walk_to = 'lake';
	desc = [[Я могу пойти к озеру.]];
}

obj {
	nam = 'stone';
	-"камень";
	description = [[Серый крупный камень. Округлый и гладкий.]];
	["before_Drop,ThrowAt,Insert"] = function(s, w)
		if not w then
			if here()^'lake' then
				p [[Я выбросил камень.]]
				remove(s, me())
			else
				p [[Камень может мне пригодиться.]]
			end
			return
		end
		if not w ^ 'dog' then
			if w ^ 'cat' then
				return [[Сбить котёнка с дерева? Это уж слишком...]]
			end
			if mission and w^'soldier' then
				p [[Камень вряд ли поможет мне обезвредить солдата.]]
				return
			end
			if mp:animate(w) then
				return [[Я не уверен, что это хорошая идея.]]
			end
			if w ^ 'озеро' then
				remove(s, me())
				return [[Я швырнул камень в озеро и некоторое время смотрел на расходящиеся круги на воде.]]
			end
			p [[Камень может мне пригодиться.]];
		else
			mp:xaction('Attack', w, s)
		end
	end;
	Show = function(s, w)
		if w ^ 'dog' then
			mp:xaction('Attack', w, s)
		else
			return false
		end
	end;
}
obj {
	nam = 'stones';
	-"галька|камни|камень";
	description = [[Круглые крупные камни светло-серых оттенков, уложенные вдоль покатого берега. Кое-где камней не хватает.]];
	before_Take = function(s)
		if not have 'stone' then
			p [[Подумав, я взял один из камней с собой.]]
			take 'stone'
			return
		end
		p [[Мне не нужны больше камни.]]
	end
}:attr'concealed';

room {
	nam = 'lake';
	out_to = 'park2';
	s_to = 'park2';
	n_to = 'sad';
	enter = function(s)
		set_pic 'lake';
	end;
	u_to = function(s)
		if seen'tree' then
			mp:xaction('Climb', _'tree')
		else
			return false
		end
	end;
	before_Listen = function(s)
		if seen 'dog' then
			return "Я слышу громкий собачий лай."
		end
		lalarm(s);
	end;
	before_Swim = function(s)
		mp:xaction("Enter", _'озеро')
	end;
	title = "У озера";
	dsc = function(s)
		p [[По поверхности озера идёт лёгкая рябь. Красно-жёлтые листья, опавшие с растущих
		вдоль берега деревьев, плавают в тёмной воде.
	Берег озера усыпан галькой. Парковая дорожка, идущая из центра парка, где стоит скамейка, огибает озеро и
	ведёт в сад.]];
		if seen'tree' and not seen'dog' then
			p [[^^Моё внимание привлекает дерево, которым интересовался пёс.]]
		end
	end;
	obj = {
		obj {
			-"берег";
			nam = 'берег';
			description = [[Берег озера усыпан крупной галькой. ]];
			before_Enter = [[Я прошёлся вдоль берега озера.]];
		}:attr'scenery';
		'stones',
		'sky',
		'trees',
		obj {
			-"озеро|поверхность озера,поверхность|вода";
			nam = 'озеро';
			description = [[Вода совсем тёмная и, наверное, холодная.]];
			before_Enter = [[Вода холодная...]];
		}:attr'scenery,enterable';
		'skam_nav';
		Path {
			-"парковая дорожка,дорожка,дорога";
			desc = "Я могу пройти в сад или вернуться к скамейке.";
			walk_to = 'sad';
		};
		Path {
			-"сад";
			desc = "Я могу пойти в сад.";
			walk_to = 'sad';
		};
	};
}

room {
	nam = 'sad';
	-"сад";
	before_Listen = lalarm;
	n = 0;
	out_to = 'lake';
	s_to = 'lake';
	before_Smell = [[Пахнет яблоками!]];
	daemon = function(s)
		s.n = s.n + 1
		if s.n > 1 then
			s.n = 0
			p [[Вдруг я услышал как мальчик кого-то зовёт: -- Аба, аба, аба!!!]];
		end
	end;
	enter = function(s)
		s.n = 0
		if not disabled 'boy' then
			s:daemonStart()
		end
		-- picture = 'sad';
	end;
	exit = function(s)
		s:daemonStop()
	end;
	title = 'Яблоневый сад';
	dsc = function(s)
		p [[Я оказался в яблоневом саду. Здесь множество деревьев, которые почти облетели.
			Мои ноги зарываются в толстый слой опавшей листвы.
			Парковая дорожка здесь заканчивается. Я могу вернуться по ней
			обратно к озеру.]]
		if seen 'boy' and not disabled 'boy' then
			p [[Я вижу знакомого мне мальчика, который ходит между деревьями. Кажется,
			он что-то ищет...]]
		end
	end;
	obj = { 'sky', 'trees', 'lake_nav', 'leaves',
		Path {
			-"парковая дорожка,дорожка,дорога";
			desc = "Я могу вернуться к озеру.";
			walk_to = 'lake';
		};
		Useless {
			-"яблоки";
			description = "Они все на земле.";
		};
	};
}
room {
	nam = 'street';
	-"город|улица";
	title = "Город";
	first = false;
	n_to = 'vorota';
	s_to = 'downstairs';
	d_to = 'downstairs';
	n = 0;
	enter = function(s)
		-- picture = 'street';
		if not s.first then
			s.first = true
			p [[Я вышел из парка и оказался на городской улице.]]
			s:daemonStart()
		end;
	end;

	before_Listen = function(s)
		if not alarm then
			p [[Здесь очень тихо.]]
		else
			p [[Этот пронзительно воющий звук сводит меня с ума!
			Его источником, похоже, является столб у подземного перехода.]]
		end
	end;
	daemon = function(s)
		if not s.n then
			s.n = 0
			return
		end
		if here()^'street' or here()^'entrance' then
				s.n = s.n + 1
		end
		if s.n < 5 then
			return
		end
		if s.n == 5 then
			s.n = 6
			alarm = true
			p [[Внезапно тишину нарушил пронзительный звук!]]
			disable 'boy'
			-- set_sound 'snd/sirene.ogg'
			if seen 'people1' then
				p [[Пожилая пара быстро скрылась за воротами парка и я остался в одиночестве.]]
			elseif here()^'street' then
				p [[Я заметил, как из парка выбежала пожилая пара и поспешно скрылась
					в подземном переходе.]]
			end
			remove('people1', 'entrance')
			remove('people1', 'park2')
			objs(_'underground'):lookup('люди'):enable()
			return
		end
		if mission2 then
			-- p [[Рёв двигателей самолетов смешивается с воем сирены.]]
			s:daemonStop()
			return
		end
		if here()^'street' then
			p [[Улица заполнена пронзительным воем.]]
		elseif here()^'underground' then
			p [[Вой сирены мешает сосредоточится.]]
		elseif here()^'entrance' then
			p [[Громкий, пронзительный вой доносится со стороны улицы.]]
		elseif here()^'underground2' then
			p [[Вой сирены здесь заметно тише.]]
		elseif not here()^'sad' then
			p [[Со стороны выхода из парка доносится громкий, воющий звук.]]
		end
	end;

	dsc = function(s)
		p [[Улица, как и парк, выглядит безжизненно. На противоположной стороне
		пустой автомобильной дороги громоздятся дома.]]
		p [[Неподалёку я вижу подземный переход, рядом с которым установлен столб.
		Ворота, ведущие в парк, открыты.]];
		if not alarm then
			p [[^^Я замечаю здесь редких прохожих.]]
		elseif not disabled '#прохожие' then
			p [[^^Я вижу людей, торопливо спускающихся в подземный переход.]]
		end
	end;
	obj = { 'vorota',
		Path {
			-"парк";
			desc = [[Я могу пойти в парк.]];
			walk_to = 'vorota';
		};
		obj {
			-"здания|дома|строения";
			description =  [[Архитектура напоминает 60-е. Только высота этих шести- или семиэтажных
			зданий непривычно большая. Стены покрыты трещинами и сколами. Кое-где я замечаю
			свет в окнах.]];
			before_Enter = [[Судя по всему, в этом городе у меня нет знакомых. Кого мне искать в чужих квартирах?]];
		}:attr'scenery,enterable',
		obj {
			-"окна";
			description = [[В некоторых окнах горит свет. Обычно я люблю смотреть на
			тёплый свет чужих окон, но сейчас он внушает мне тревогу.]];
			['before_Enter,Open'] = "Какая сумасбродная мысль.";
		}:attr'scenery,enterable,openable';
		obj {
			-"дорога|ямы,выбоин*/мн";
			description = [[Пустынная дорога испещрена выбоинами и ямами.]];
		}:attr'scenery';
		obj {
			-"столб,конус*,воронк*";
			description = [[Высота столба около шести метров. На верху столба я вижу три конусообразных воронки, направленные в разные стороны.]];
			before_Climb = [[Какой смысл в том, чтобы залезть на столб?]];
		}:attr'scenery';
		'downstairs',
		Useless {
			-"плакат";
			description = [[Плакат -- щит квадратной формы, на котором схематично
			изображены три человека, вокруг которых расположены четыре красных
			прямоугольных треугольника, смотрящие прямыми углами в центр.]]
		}:attr'static';
		obj {
			nam = '#прохожие';
			-"прохожие|люди";
			description = function(s)
				if alarm then
					p [[Мужчины и женщины спешат по направлению к подземному переходу.]]
				else
					p [[Прохожих единицы. Они словно бы крадутся вдоль потрескавшихся стен
					зданий.]]
				end
			end;
			before_Talk = function(s)
				if alarm then
					p [[Похоже, им сейчас не до моих расспросов.]]
					return
				end
				if _'people1'.talk then
					p [[После разговора с мальчиком и пожилой парой я сомневаюсь,
					что это хорошая идея.]]
				else
					p [[Мне неловко беспокоить их.
					Может быть, лучше поговорить с пожилой парой в парке?]]
				end
			end;
		}:attr'animate,concealed',
		'sky',
	};
}

door {
	nam = 'downstairs';
	-"подземный переход,переход";
	door_to = 'underground';
	description = "Широкие ступеньки ведут вниз. Над входом я заметил плакат.";
}:attr'scenery,open';


room {
	nam = 'underground';
	-"переход|зал";
	title = "переход";
	before_Listen = lalarm;
	onenter = function(s, f)
		if mission and  f^'street' then
			if mission2 then
				walkin 'flashout'
				return
			end
			p [[Сначала нужно найти того мальчика!]]
			return false
		end
	end;
	enter = function(s, f)
		set_pic 'underground';
		if f^'street' then
			p [[Я подошёл к переходу и спустился вниз.]]
			if alarm or mission then
				_'дверь':attr'open'
			end
		else
			if mission then
				p [[Я взлетел по ступенькам и, запыхавшийся, уже побежал по направлению к
					решетчатой двери, когда передо мной возник человек в коричневой форме.]]
			else
				p [[Я поднялся по ступенькам и, запыхавшись, уже направился к
					решетчатой двери, когда передо мной возник человек в коричневой форме.]]
			end
			-- picture = 'soldier';
			enable 'soldier'
			if not _'soldier'.seen then
				_'soldier'.seen = true
				p [[Мне показалось, что это был солдат. На это указывала форма с погонами и
				кобура на широком ремне.]]
			end
			p [[^^-- Но се педе! Но сан пелигросос! -- требовательно произнёс солдат.]]
		end
	end;
	exit = function(s, t)
		if t^'underground2' then
			if not visited'underground2' then
				p [[Я проследовал вместе с людьми через дверь и оказался в зале.
					Зал оканчивался крутыми лестницами, ведущими вниз, и мне
					ничего не оставалось, как начать спуск по одной из них.
					Спуск оказался утомительно долгим,
					и я почти с облегчением преодолел последние ступеньки.]];
					disable 'люди'
			else
				p [[Мне ничего не оставалось, как снова спуститься в подземный зал.]]
			end
		end
	end;
	dsc = function(s)
		if alarm then
			if from()^'underground2' then
				p [[Я нахожусь в просторном, хорошо освещённом зале. Чтобы выйти наверх мне нужно
				пройти через решётчатую дверь, путь к которой преграждает солдат.]]
			else
				p [[Я вижу в переходе людей. Лампы вдоль стен мерцают бледно-жёлтым светом.]]
				p [[Между выходами наверх есть открытая решётчатая дверь.]]
			end
		else
			p [[В переходе никого нет. Лампы, расположенные вдоль стен, не горят.]]
			p [[Между выходами наверх есть решётчатая дверь.]]
		end
	end;
	onexit = function(s, t)
		if t^'street' and from()^'underground2' then
			p [[Я не могу просто так пройти мимо солдата. Нужно что-то предпринять!]]
			return false
		end
		if t^'underground2' then
			if not alarm then
				p "Дверь закрыта."
				return false
			end
		end
	end;
	obj = {
		Path {
			nam = '#down';
			-"лестницы|лестница";
			desc = "Я могу спуститься вниз.";
			walk_to = function(s)
				if disabled'soldier' then
					return 'дверь'
				else
					return '@d_to';
				end
			end
		}:disable();
		door {
			nam = 'дверь';
			-"решётчатая дверь,дверь";
			description = function(s)
				if from()^'underground2' then
					p [[Дверь приоткрыта. Я вижу сквозь решётку жёлтые лампы в переходе.]]
					return
				end
				if not alarm then
					p [[Я подошёл к железной решётчатой двери.
					С другой стороны решётки я увидел просторный,
					хорошо освещённый зал. Зал заканчивался двумя крутыми лестницами, ведущими
					вниз. Справа у стены я заметил человека в коричневой форме.]]
				else
					p [[Я вижу как люди проходят через открытую дверь в
					просторный зал, а затем направляются к лестницам, которые ведут дальше вниз.
					Со стороны зала, рядом с дверью, я вижу человека в коричневой форме.]]
				end
				enable 'soldier'
				enable '#down'
			end;
			before_Open = function(s)
				if alarm  then
					return [[Дверь и так открыта.]]
				end
				p [[Я подёргал дверь, но она не поддалась. Внезапно, я увидел, как с другой стороны
					к двери подошёл человек в коричневой форме и что-то резко произнёс:^
					-- Аледжарс!^Я благоразумно отошел.]]
			end;
			before_Close = function(s)
				if alarm then
					return [[Я думаю мой поступок могут понять неправильно.]]
				end
				p [[Но она же и так закрыта! Это какое-то наваждение, похоже, я схожу с ума.]]
			end;
			door_to = function(s)
				if not alarm then
					p [[Но дверь закрыта.]]
					return
				end
				if from()^'underground2' then
					return 'street'
				else
					return 'underground2';
				end
			end
		}:attr'scenery,openable',
		Useless {
			-"лампы|фонари";
			description = [[Круглые лампы закреплены прямо на стенах.]];
		};
		obj {
			nam = 'люди';
			-"люди|прохожие";
			description = [[Люди спешат к двери. На их лицах я читаю тревогу.]];
			before_Talk = [[Мне кажется, им сейчас не до моих вопросов.]];
		}:disable():attr'animate,concealed';
		'soldier',
	};
	u_to = 'street';
	out_to = 'street';
	in_to = 'дверь';
	d_to = function(s)
		if disabled'soldier' then
			return false
		end
		return 'underground2'
	end;
}

obj {
	nam = 'soldier';
	-"солдат|военный,человек";
	seen = false;
	word = function(s)
		if s.seen then
			return -"солдат|военный|человек|мужчина";
		end
		return -"человек|мужчина";
	end;
	description = function(s)
		p [[Мне кажется, что это военный. На это указывает его форма и кобура на широком ремне.]]
		s.seen = true
	end;
	before_Talk = function(s)
		if mission then
			p [[-- Там в парке ребёнок!!! -- закричал я -- пустите меня!^
				-- Баха пор, баха! -- солдат уверенно перегородил мне проход.^
				-- Пусти меня, там ребёнок!!! -- я попытался жестами показать,
				что мне нужно наружу, но солдат был непреклонен. ]];
			return
		end
		if alarm then
			p [[Мне кажется, сейчас неудачное время для разговоров.]]
		else
			p [[Попросить его открыть дверь? Но как?
			Мне кажется, что эта дверь закрыта неслучайно.]]
		end
	end;
	["before_Attack,Push"] = function(s, w)
		if not mission then
			p [[Это слишком радикально. Нужна веская причина, чтобы сделать это.]]
			return
		end
		if w then
			p [[В последнее время я стараюсь быть проще. Может быть, просто ударить солдата?]]
			return
		end
		p [[Не думая о последствиях, я врезал со всей силы ему по лицу и, не дожидаясь реакции,
		бросился в переход через решетчатую дверь.^^
		Выстрелов не последовало. Через мгновение я был уже на улице...]]
		objs('street'):lookup('#прохожие'):disable()
		walkin 'street'
	end;
	obj = {
		Careful {
			-"кобура|пистолет";
			before_Take = "Не стоит.";
		};
	};
}:disable():attr 'animate,concealed';

room {
	nam = 'underground2';
	before_Listen = lalarm;
	title = 'Подземелье';
	enter = function(s)
		-- picture = 'underground';
	end;
	dsc = [[Я нахожусь в подземном зале, довольно просторном, но с низкими потолками.
		Освещение неяркое, но достаточное. Здесь уже набралось
		десятка два человек. Большинство из них сидят на длинных скамьях, которые стоят рядами
		по всей поверхности плиточного пола.]];
	obj = {
		obj {
			nam = '#floor';
			-"пол,плитк*";
			description = function(s)
				p [[Я посмотрел на пол. Он был пыльным и выглядел старым.]]
				if disabled 'plakat' or seen 'plakat' then
					p [[Возле одной из скамеек я заметил большой лист бумаги.]]
					enable 'plakat'
				end
				return false
			end;
			["before_Enter,Climb,Walk"] = "Но я и так на полу!";
		}:attr'supporter,enterable,scenery';
		'plakat';
		obj {
			nam = 'people';
			-"люди,мужчины,старики|женщины";
			talk = false;
			seen = false;
			description = function(s)
				p [[Я обвёл взглядом людей в подземелье. Лица усталые, многие сидят на скамейках.
				Мужчины, женщины, старики... Детей я среди них не заметил.]];
				s.seen = true
				if _'plakat'.seen then
					mission = true;
					move('dog', 'lake')
					move('tree', 'lake')
					enable 'boy'
					p [[^^{$fmt em|Да, детей среди них не было. Я видел сегодня только одного ребёнка --
					мальчика в парке. И его здесь не было, он остался снаружи!
					Звук сирены говорит о скорой бомбардировке, мне нужно спешить!}]];
				end
			end;
			before_Talk = function(s)
				if not s.talk then
					s.talk = true
					p [[Я выбрал взглядом одного мужчину и подошёл к нему:^
					-- Простите, что здесь происходит?^
					Я заметил как он удивился.^
					-- Ан ентендо. Кэ нестатис.^^
					Я почувствовал, что ловлю на себе подозрительные взгляды от окружающих
					меня людей.]];
				else
					p [[К сожалению, они меня не понимают, а я -- их...]]
				end
			end;
		}:attr'concealed,animate';
		Furniture {
			-"скамейки,скамьи,лавки,лавочки/мн|скамейка,скамья,лавка,лавочка";
			description = [[Грубые деревянные скамьи стоят по всему залу.]];
			before_Default = function(s, ev)
				if eph_event(ev) or ev == 'Walk' then
					return false
				end
				if s:hint'plural' then
					p [[Это действие нельзя совершить со всеми скамейками сразу.]]
					return
				end
				return false
			end;
			["before_LookUnder,Search"] = function(s)
					if disabled 'plakat' or seen 'plakat' then
						p [[Возле одной из скамеек я заметил большой лист бумаги.]]
						enable 'plakat'
						return
					end
					return false
			end
		}:attr'scenery,supporter,enterable';
	};
	u_to = 'underground';
	out_to = 'underground';
}
cutscene {
	nam = 'give_plakat';
	title = '***';
	enter = function()
		set_pic 'boy';
	end;
	text = {
		[[Я достал плакат и развернул его обратной стороной.^
				-- Смотри, вот твой котёнок! Ты же его ищешь?^
		Моя догадка оказалась верна! Мальчик, увидев плакат, подбежал ко мне:^
		-- Донде еста Аба? -- спросил он, быстро заглядывая мне в глаза.^
		-- Да да, Аба, идём за Абой... -- я взял его за руку и мы побежали к озеру...]];
		[[Я показал ему дерево у озера и котёнок, узнав мальчика, спрыгнул к нему в руки.
		Всё это время мне казалось, что я слышу отдалённый, но всё нарастающий рокот.
		Самолёты! Их гул был уже отчётливо слышен, даже не взирая
		на истошный вой сирены.]];
		[[Я потащил мальчика за собой. Мы побежали к воротам...]];
	};
	onexit = function()
		snapshots:make();
		_'airplane':daemonStart()
		set_pic 'bombs'
	end;
	next_to = 'park2';
}

obj {
	nam = 'hole';
	-"воронка,яма,ямка,лунка";
	first = false;
	title = 'В воронке';
	dsc = [[Рядом с воротами я вижу огромную воронку.]];
	inside_dsc = [[Мы валяемся на дне воронки.]];
	description = [[Глубокая воронка которая осталась от взрыва авиабомбы.]];
	before_LetIn = function(s)
		set_pic 'bombs';
		return false
	end;
	before_LetGo = function(s)
			if ranen then
				p [[Я собрал остатки сил, взял мальчика за руку, мы с трудом выползли из воронки и
				побежали...]]
				return false
			end
			ranen = true
			p [[Я попытался выбраться из воронки, но острая боль в спине заставила меня снова сползти
			на дно.]]
			p [[Я ранен? Но здесь опасно долго находиться, а убежище совсем рядом...
			Сейчас, только немного передохну...]]
	end;
	['before_Walk,Enter,Climb'] = function(s)
		if where(me()) ^ s then
			p [[Мы и так находимся в воронке.]]
			return
		end
		s.first = true
		p [[Мы бросились к воронке. Время замерло. Свист падающей бомбы заполнил всё вокруг.
		Перед самой воронкой я с силой толкнул мальчика вперёд и в этот момент прогремел взрыв.
		Я почувствовал сильный толчок в спину и, оглушённый, упал
		в воронку вслед за мальчиком.]]
		deaf = 6
		mp:move(me(), s)
		put('boy', s)
	end;
}:attr'container,open,enterable,static';

cutscene {
	nam = 'flashout';
	title = '***';

	onenter = function(s)
		DaemonStop 'airplane'
		DaemonStop 'street'
		local w = _'airplane'
		if w.n >= 2 then
			local t = w.n - 2
			if (t % 3) == 0 then
				walkin 'replay'
				return false
			end
		end
	end;
	text = { [[Я бежал за мальчиком, всё время держа его в поле зрения. Каждый шаг отдавался острой
	болью в спине.
		Я слышал свист бомб, но мне ничего не оставалось, как просто бежать эти последние метры и надеяться...]],
	[[Сквозь подступающую к сознанию темноту я видел, как мальчик добежал до перехода. Вот он
		оглянулся и вопросительно посмотрел на меня...]],
	[[Я закричал на него и, не обращая внимания на боль, отчаянно замахал руками.]],
	[[Я увидел как он, словно бы неохотно, скрылся в подземном переходе.]],
	[[... Я с трудом преодолел последние несколько метров и повис на лестничных перилах.
	Теряя сознание, я начал сползать вниз. Потом упал и покатился по ступенькам. Перед глазами я видел пляшущие...]],
	[[... краски октября ...]]
	};
	next_to = 'roof2';
}
room {
	nam = 'roof2';
	title = 'На крыше';
	n = 0;
	enter = function(s)
		set_pic 'roof2';
		p [[Запах мокрой листвы... Он появился и куда-то пропал. Холод на щеке. Стук. Глухой стук.
	Крыша... Я качусь по мокрой крыше!!! Ужас захлестнул меня. И в тот же миг крыша кончилась...]];
		remove('stone', me())
		remove('plakat', me())
		s:daemonStart()
		snapshots:make()
	end;
	onexit = function(s)
		s:daemonStop()
	end;
	u_to = '#roof';
	d_to = function(s)
		mp:xaction('Jump')
	end;
	daemon = function(s, w)
		if not s.n then s.n = 0 end
		s.n = s.n + 1
		if s.n == 3 then
			p [[Вдруг, я услышал стук приближающихся шагов по крыше. Кто-то бежит сюда!]]
		elseif s.n == 4 then
			p [[-- Держитесь! -- услышал я дрожащий женский голос. -- Возьмите мою руку!]];
			enable 'girl2'
			enable 'hand'
		elseif not disabled 'hand' then
			if not _'girl2'.talked then
				p [[-- Держите мою руку -- слышу я женский голос.]];
			end
		end
	end;
	before_Jump = "Не стоит торопить события.";
	before_Default = function(s, ev, w)
		if eph_event(ev) or mp:compass_dir(w) then
			return false
		end
		if w and w ^ '#roof' or w ^ 'girl2' or w ^ 'hand' then
			return false
		end
		p [[Всё, что я могу, я уже и так делаю.]];
	end;
	dsc = [[Я вишу на краю крыши. Каким-то чудом я зацепился за водосток, идущий по краю, но
	сил чтобы висеть так долго у меня не хватит. Я цепенею от холода и ужаса, охватившего меня.]];
	obj = {
		obj {
			-"водосток";
			description = [[Водосток идет вдоль края крыши. Какое чудо, что я зацепился за него!]];
			before_Take = [[Я еще крепче ухватился за водосток.]];
		}:attr'static,concealed';
		'sky',
		obj {
			nam = '#roof';
			-"крыша|край крыши,край";
			["before_Climb,Pull,Enter"]  = function(s)
				mp:xaction('Exam', s);
			end;
			description = function(s)
				if here().n == 3 then
					p [[Я собрал остаток сил, немного подтянулся и посмотрел за край.
					Ко мне спешила девушка! Я всё вспомнил! Здесь на крыше была девушка...]]
					enable 'girl2'
					return
				end
				if here().n > 3 then
					p [[Я собрал остаток сил, немного подтянулся и посмотрел за край.
					На краю крыши была девушка. Рядом с ней я заметил вентиляционную трубу.]]
					enable 'girl2'
					enable 'truba'
					return
				end
				p [[Я немного подтянулся и посмотрел за край.
				Отсюда я вижу только небольшой участок крыши.
				Крыша мокрая от дождя.]];
			end;
		}:attr'scenery';
		'girl2';
		'truba';
	};
}
obj {
	nam = 'girl2';
	-"девушка,женщина";
	talked = false;
	truba = false;
	description = function(s)
		if s.talked and not s.truba then
			p [[Девушка негромко плачет. Похоже, её нервная система на пределе.]]
			return
		end
		if s.truba then
			p [[Девушка держится за вентиляционную трубу. Думаю, можно попробовать!]]
			return
		end
		p [[Честно говоря, мне сейчас совсем не до разглядывания девушек.]];
	end;
	["before_Take,Pull,Touch,Kiss"] = [[Лучше взяться за её руку.]];
	before_Talk = function(s)
			if not s.talked and not _'truba'.seen then
				p [[-- Послушайте, вы не удержите меня. Наверное нет никакого способа мне помочь.
				-- я услышал, как девушка всхлипывает. Но, почему-то, сейчас меня это не тронуло.
				^-- Знаете что? Раз уж мне удалось всё-таки поговорить с вами, то...
				не делайте того, что собирались сделать... Ладно?^]]
				p [[Девушка не ответила. Всхлипы сделались громче.^]]
				p [[-- А вообще, попробуйте позвать кого-нибудь на помощь -- произнёс я в надежде, что
				она не увидит как мои ослабевшие пальцы разожмутся.^^]]
				p [[Но девушка не ушла, она просто сидела и плакала.]]
				s.talked = true
				return
			end
			if s.truba then
				p [[-- Всё нормально? -- спросил я уверенным тоном.^
				-- Да -- да, всё нормально... У меня получится!]];
				return
			end
			if _'truba'.seen then
				if not s.talked then
					s.talked = true
					p [[-- Послушайте, вы не удержите меня! Не уверен, что есть способ мне помочь... -- я услышал, как девушка всхлипнула.
					^-- Но, давайте попробуем. ]]
				else
					p [[-- Да, паршивая ситуация. Но у меня появилась идея.]]
				end
				p [[Видите вот эту трубу?
				Попробуйте лечь за неё так, чтобы она была между нами,
				и дайте мне руку. Попробуем вытащить меня.^^]];
				p [[Девушка не перестала плакать, но появление конкретного плана действий вывело её из
				оцепенения и она бросилась его выполнять. Ну что-же, сейчас она достаточно
				безопасно для себя закрепилась на крыше.]]
				s.truba = true
			else
				p [[Я не нашёл что сказать плачущей девушке.]]
			end
	end;
	obj = {'hand'};
}:disable():attr'animate';

obj {
	nam = 'hand';
	-"рука";
	description = [[Женская рука не выглядит сильной.]];
	before_Take = function(s)
		if not _'girl2'.truba then
			walk 'replay2'
			return
		end
		walk 'happyend'
	end;
}:disable():attr'concealed'

obj {
	-"вентиляционная труба,труба,вентиляция,козыр*";
	nam = 'truba';
	seen = false;
	before_Default = function(s, ev)
		if eph_event(ev) then
			return false
		end
		p [[Мне до неё не дотянуться.]]
	end;
	description = function(s)
		s.seen = true;
		p [[Железная вентиляционная труба с козырьком.]];
		if s:once() then
			p [[А что, если...]]
		end
	end;
}:disable():attr('static')

cutscene {
	nam = 'replay2';
	title = '***';
	enter = function(s)
		set_pic 'leaves'
	end;
	text = { [[Я ухватился за женскую маленькую руку и понял, слишком поздно понял, что девушка
	не сможет меня удержать... Я летел вниз и погружался в пёстрые краски октября... ]] };
	Next = function(s)
		snapshots:restore()
	end;
}

cutscene {
	nam = 'happyend';
	title = '***';
	enter = function(s)
		set_pic 'leaves'; -- happyend
	end;
	text = {
		[[Мы сидели на краю мокрой крыши и смотрели на осень в городе.^
		Я не знаю, о чем думала она, а я вспоминал пустынный осенний парк,
		мальчика с котёнком и бомбы...]],
		[[Был ли этот парк реальным? Парк, который я нарисовал, и в котором я оказался тогда,
		когда кому-то понадобилась моя помощь?^
		В кармане я нащупал кисточку и достал её. На ней ещё оставалась краска...
		А в моей мастерской -- незаконченная картина.]],
		[[Я осторожно встал и позвал девушку.]],
		[[И пока мы шли и звук наших шагов раздавался по мокрой крыше я понял,
		что краски октября останутся в моей душе навсегда...]],
		[[... И что ничего не может быть реальней того, кому нужна твоя помощь ...]]
	};
	next_to = 'happyend2';
}

gameover {
	nam = 'happyend2';
	enter = function()
		set_pic 'skam'
	end;
	title = fmt.c'КРАСКИ ОКТЯБРЯ';
	dsc = function(s)
		p [[{$fmt c|Спасибо вам за прохождение этой небольшой игры.^^]]
		p [[{$fmt b|Тестирование:}^{$fmt em|Oleg Bosh^
		Canwolf^
		Nikita Tseykovets}}^^]]
		p (fmt.c("{$fmt b|КОНЕЦ}^^{$fmt r|Пётр Косых, 2021^https://instead.hugeping.ru}"))
	end;
}

obj {
	-"самолёты|самолёт|бомба|бомбы";
	before_Default = [[Меня сковывает ужас, как только я думаю о самолётах и бомбах.]];
	nam = 'airplane';
	n = 0;
	daemon = function(s)
		local t
		if deaf then
			deaf = deaf - 1
			if deaf == 0 then deaf = false end
			if deaf == 2 then
				p [[{$fmt em|Кажется, слух понемногу возвращается!}]]
			elseif deaf == 1 then
				p [[{$fmt|Я различаю шум самолётов!}]]
			end
		end
		s.n = s.n + 1
		local dp = deaf and function() end or p
		if s.n >= 2 then
			t = s.n - 2
		else
			if s.n < 1 then
				return
			end
			if s:once'bomb' and not here() ^ 'entrance' then
				dp [[{$fmt em|Я слышу свист падающей бомбы со стороны входа в парк!}]]
			else
				dp [[{$fmt em|Я слышу нарастающий свист!}]]
			end
			return
		end
		if (t % 3) == 0 then
			if s:once'bomb2' and not here() ^ 'entrance' then
				dp [[{$fmt em|Я слышу пронзительный свист падающей бомбы со стороны входа в парк!}]]
			else
				dp [[{$fmt em|Я слышу над собой пронзительный свист падающей бомбы!}]]
			end
			return
		end
		if (t % 3) == 1 and where(me()) ^ 'hole' then
			dp [[{$fmt em|Где-то рядом взорвалась бомба!}]]
			return
		end
		if (t % 3) == 1 then
			if not seen('hole', 'entrance') and here()^'park2' then
				dp [[{$fmt em|Где-то у входа в парк прогремел взрыв!}]]
				place('hole', 'entrance');
			else
				walkin 'replay'
				return
			end
		end
		if (t % 3) == 2 then
			dp [[{$fmt em|Я слышу звук гула двигателей пролетающих над нами самолётов!}]]
			if _'hole'.first then
				s.n = -1
			end
			return
		end
	end;
}:attr'concealed,scenery';

cutscene {
	nam = 'replay';
	title = '***';
	onenter = function(s)
		set_pic 'leaves'
		_'airplane':daemonStop()
	end;
	text = { [[Взрыв разорвал землю в клочья. Я погружался в пёстрые краски октября...]] };
	Next = function(s)
		snapshots:restore()
	end;
}

obj {
	nam = 'plakat';
	seen = false;
	draw = false;
	word = function(s)
		if s.seen then
			if s.draw then
				return -"плакат,лист|бумага|рисунок|картина";
			end
			return -"плакат,лист|бумага";
		end
		return -"лист бумаги,лист|бумага";
	end;
	before_Show = function(s, w)
		if w^'boy' then
			mp:xaction('Give', s, w)
			return
		end
		return false
	end;
	before_Give = function(s, w)
		if w^'boy' then
			if mission2 then
				p [[Мальчик уже видел мою картину.]]
				return
			end
			if s.draw then
				here():daemonStop()
				mission2 = true
				put('boy', 'street')
				put('airplane', 'street')
				put('boy', 'park2')
				put('airplane', 'park2')
				put('boy', 'entrance')
				put('airplane', 'entrance')
				move('cat', 'boy')
				walkin 'give_plakat';
			else
				p [[Я достал и развернул плакат так, чтобы мальчик увидел изображение бомбоубежища.]]
				p [[По выражению его лица я увидел, что он понял меня,
				но по-прежнему не собирался уходить из парка.]]
			end
			return
		end
		return false
	end;
	description = function(s)
		if s.draw then
			p [[На обратной стороне плаката схематично нарисован котёнок.]]
			return
		end
		if not have(s) then
			if s:hasnt'moved' then
				p [[Большой, немного помятый лист бумаги лежит на полу.]];
			else
				p [[Большой, немного помятый лист бумаги.]]
			end
			return
		end
		s.seen = true
		p [[Я расправил лист бумаги. На нём был изображён плакат.^^
			В нижней части плаката была нарисована женщина держащая на руках ребёнка.
			Над ними была проведена красная черта. Над чертой чёрной краской были изображены птицы...
			Крупные птицы заполонили всю верхнюю часть плаката. Или...^^
			Самолёты! И бомбы! Они сбрасывали бомбы, которые взрывались о красную
			черту -- мать и ребёнок были в безопасности. Я всё понял! Это же бомбоубежище!^^
			Обратная сторона плаката совершенно чистая.]];
		if here() ^ 'underground2' and _'people'.seen then
			mission = true;
			move('dog', 'lake')
			move('tree', 'lake')
			enable 'boy'
			p [[^^{$fmt em|Я обвёл взглядом людей в подземелье. Мальчика здесь не было.
			Он остался снаружи!
			Звук сирены говорит о скорой бомбардировке, мне нужно спешить!}]];
		end
	end;
}:disable()

obj {
	nam = 'dog';
	-"собака|пёс";
	dsc = [[{$fmt em|Я вижу, как вокруг одного из деревьев с громким лаем носится пёс.}]];
	["before_Take,Touch,Kiss,Taste"] = "В детстве я умел ладить с собаками, но с тех пор многое изменилось...";
	before_Talk = [[-- Эй, блоховоз!!! -- неуверенно крикнул я псу. Он на короткое время отвлёкся от дерева, но потом принялся за старое. Может быть, к лучшему?]];
	before_Attack = function(s, w)
		if w^'stone' then
			p [[-- Эй, волчище, смотри что у меня есть!!! -- с этими словами я достал камень и
				размахнулся, делая вид, что хочу бросить его. Как только пёс увидел камень, то с визгом
				кинулся в сторону парковых ворот. Похоже, за свою нелёгкую жизнь он уже не раз
				встречался с камнем. Бедняга.]]
			remove(s)
			return
		end
		p [[Я попытался отогнать пса от дерева, но едва не лишился жизни (как мне показалось).]];
	end;
	description = function(s)
		p [[Большущий пёс коричнево-рыжего окраса.
		Белые клыки и всклоченная шерсть придают ему свирепый вид.
		Он кружит у дерева, задрав моду вверх, и громко лает.]]
	end;
}

obj {
	nam = 'tree';
	-"дерево";
	description = function(s)
		if seen 'dog' then
			p [[Я собрался было подойти поближе к дереву и посмотреть на то,
				что так беспокоит пса, но рычание и оскаленные клыки
				отбили всякое желание это делать.]]
		else
			p [[Я подошёл к дереву и посмотрел вверх. Высоко в ветвях притаился маленький чёрный
			комочек. Это же котёнок!]]
			know_cat = true
			place 'cat'
		end
	end;
	['before_Climb,Enter'] = function(s)
		if not seen 'cat' then
			p [[Увы, но я уже не мальчик. Нужна веская причина, чтобы сделать это.]]
			return
		end
		if seen 'dog' then
			return [[Думаю, псу это не понравится.]]
		end
		mp:xaction('Take', _'cat')
	end;
}:attr 'scenery';

obj {
	nam = 'cat';
	take = false;
	-"котёнок,котик,кот";
	description = function(s)
		if s:where() ^ 'boy' then
			p [[Мальчик прижал котёнка к груди.]]
			return
		end
		p [[Среди тонких ветвей дерева притаился котёнок. Он сильно напуган и крепко вцепился в ствол дерева.]];
	end;
	['before_Kiss,Touch'] = [[Я погладил котёнка. Он был маленьким, хрупким и ... тёплым.]];
	before_Take = function(s)
		if mission2 then
			p [[Зачем забирать котёнка у мальчика?]]
			return
		end
		if seen 'dog' then
			p [[Этот блоховоз тоже хочет его достать...]]
			return
		end
		s.take = true
		p [[Я с сожалением признал, что плохо лазаю по деревьям.
		Особенно по деревьям с такими тонкими ветками. А ведь котёнок
		забрался довольно высоко...]];
	end;
	before_Talk = function(s)
		p [[-- Кис, кис, кис, кис!!!^^Котёнок не прореагировал.]]
		if seen 'dog' then p [[^^Собака с неодобрением покосилась в мою сторону.]] end
	end;
	before_Default = function(s, ev)
		if s:where() ^ 'boy' then
			return false
		end
		if eph_event(ev) then
			return false
		end
		p [[Я не могу достать котёнка отсюда.]];
	end
}:attr'animate,concealed';
