--$Name:Метель$
--$Author:Peter Kosyh & Pakowacz$
--$Version:2.1$
require "parser/mp-ru"
require "fmt"
fmt.dash = true
fmt.quotes = true
-- mp.errhints = false
game.dsc = false; --[[Простая игра написанная специально для ЗОК-2019.]]

function pic_push(name)
end

function pic_pop()
end

function pic_set(name)
end

include "pic"

cutscene {
	nam = 'intro';
	enter = function()
		pic_set('1')
	end;
	text = {
		[[Старенький синий седан едет по заснеженной трассе. Внутри машины -- двое.^^
		Ведёт машину усталая женщина лет 35. На заднем сидении справа сидит её дочь -- девочка-подросток.^^
		Девочка прислонилась лбом к холодному стеклу. Мать продолжает начатый разговор...^^
		-- Вот увидишь, тебе там понравится.]];
	};
	next_to = 'В машине';
}
global 'blizzard'(0)

obj {
	-"браслет";
	nam = 'браслет';
	before_Exam = function(s)
		p [[Этот детский браслет мама подарила тебе на Рождество, когда тебе было ещё 9 лет.
Просто игрушка. Леска, на которую нанизаны бусинки и пластмассовое сердечко.]];
		if s:once() then
			p [[Странно, что он оказался в бардачке... Ты думала, что он давно потерялся.]]
		end
	end;
	before_Give = function(s, w)
		if w ^ 'королева' then
			walk 'badend4'
			return
		end
		return false
	end;
	before_Disrobe = function(s)
		if visited 'gotmirror' then
			p [[Тебе кажется, что в этом странном месте лучше никогда не снимать этот браслет!]]
		else
			return false
		end
	end;
	after_Wear = [[Надев браслет на правое запястье, ты чувствуешь, что на душе у тебя потеплело.]];
}:attr'clothing'

Title = Class ({
	title = false;
	OnError = function(s)
		mp:clear()
		std.pclr()
	end;
	before_Default = function(s, ev)
		if ev == 'Next' then
			return false
		end
		mp:clear()
		me():need_scene(true)
	end;
}, cutscene):attr 'noprompt'

Prop = Class {
	before_Default = function(s, ev)
		p ("Тебе нет дела до ", s:noun 'рд', ".")
	end;
}:attr 'scenery'

Useless = Class {
	before_Default = function(s, ev)
		p ("Тебе нет дела до ", s:noun 'рд', ".")
	end;
}

room {
	-"машина";
	nam = 'В машине';
	before_Cry = function(s)
		if seen '#мама' then
			p [[-- Прекрати истерику! -- произносит мать.]]
		else
			return false
		end
	end;
	dsc = [[Ты сидишь на заднем сидении машины и смотришь в окно.]];
	exit = function()
		if seen '#мама' then
			_'#мама':daemonStop()
		end
	end;
	out_to = function(s)
		if blizzard < 7 then
			p [[Лучше не делать этого, пока машина движется.]]
		elseif seen '#мама' then
			p [[Там холодно.]]
		else
			s:daemonStop()
			if not have 'скрипка' then
				move('скрипка', 'машина')
			end
			if not have 'телефон' then
				move('телефон', 'бардачок')
			end
			walk 'метель1'
		end
	end;
	daemon = function(s)
		local t = {
			"Машину потряхивает на снежных ухабах.";
			"По другую сторону окна кружатся снежинки.";
			"Вы проезжаете мимо занесённых снегом коттеджей.";
			"Машину слегка заносит на снежной дороге.";
		}
		if blizzard >= 2 then
			blizzard = blizzard + 1
			if blizzard < 7 and blizzard > 3 then
				pic_set '2-pan-left'
			end
			if blizzard > 5 then
				enable '#заправка'
				disable '#метель'
				if blizzard == 7 then
					p [[Мать заглушила двигатель.]]
					return
				end
				if blizzard == 8 then
					pic_set '7'
					p [[-- Подожди меня, я скоро вернусь. -- говорит тебе мать и выходит из машины, захлопывая за собой дверь.]];
					remove '#мама'
					return
				end
				if blizzard == 11 then
					p [[Ты ждёшь мать, но её все нет. Может быть, выйти из машины?]]
					return
				end
				if blizzard > 8 then
					return
				end
				p [[Вы подъезжаете к заправке.]]
				return
			end
		end
		if here() == s and rnd(100) <= 25 then
			pn (t[rnd(#t)])
		end
	end;
	enter = function(s)
		s:daemonStart()
		_'#мама':daemonStart()
	end;
	before_Listen = function(s)
		if seen '#мама' then
			p [[Ты слышишь шум мотора и музыку, доносящуюся из радио.]];
	else
			p [[В машине играет радио.]]
		end
	end;
}: with {
	obj {
		-"мать,мама,женщина";
		nam = '#мама';
		time = 0;
		before_Exam = [[Твоя мать очень много работает и поэтому выглядит усталой.]];
		before_Kiss = [[Ты зла на свою мать и сейчас ваши отношения нельзя назвать близкими.]];
		init_dsc = [[Машину ведёт твоя мать.]];
		['before_Ask,Tell,Talk'] = function(s)
			if visited 'разговор1' then
				if _'телефон'.seen and have 'телефон' then
					p [[-- Я не буду с тобой разговаривать, пока ты не отдашь мне телефон! Ну же!]]
					return
				end
				if blizzard > 0 then
					if blizzard >= 2 then
						p [[-- Мама! Это важно!^]]
						if not disabled '#заправка' then
							p [[-- Сейчас заправимся и поговорим.]]
						else
							p [[-- Скоро заправка, подожди пять минут и поговорим!]]
						end
						return
					end
					p [[-- Мама! Посмотри, там справа. Что то странное...^]]
					p [[-- Не отвлекай меня от дороги!]]
					pic_set '6'
					blizzard = 2
					return
				end
				p [[Ты не решаешься поговорить с ней.]]
				return
			end
			walk 'разговор1'
		end;
		daemon = function(s)
			local t = {
				[[-- Ты не собираешься со мной поговорить?]];
				[[-- Почему ты молчишь?]];
				[[-- Давай поговорим?]];
				[[-- Ну, чего ты молчишь?]];
			}
			s.time = s.time + 1
			if s.time > 3 then
				if rnd(3) == 1 then
					p (t[rnd(#t)])
					p [[ -- обращается к тебе мать.]];
				end
			end
		end;
	}:attr 'animate';
	'скрипка';
	Prop {
		-"бардачок";
		before_Exam = function(s)
			if _'телефон':inside 'бардачок' then
				p [[Бардачок закрыт.]]
				return
			end
			p [[Тебе нет до него дела.]]
		end;
		before_Open = [[Ты не можешь дотянуться до него с заднего сидения.]];
	};
	Prop {
		-"дверь";
		before_Open = function(s)
			mp:xaction("Exit")
		end;
		before_Enter = function(s)
			mp:xaction("Exit")
		end;
		before_Close = [[Дверь закрыта.]];
	};
	Prop {
		-"руль|радио";
	};
	obj {
		nam = '#метель';
		-"метель,буря|смерч|клубы";
		before_Default = [[Она пока ещё далеко.]];
		before_Exam = [[Буря, метель или ... смерч? Что бы это ни было, оно пугает тебя.]];
	}:attr'scenery':disable();
	obj {
		-"окно,стекло";
		nam = '#окно';
		before_Open = "Слишком холодно, чтобы опускать стекло.";
		['before_Search,Exam'] = function(s)
			if not disabled '#заправка' then
				p [[За стеклом ты видишь смутный силуэт заправки.]];
				return
			end
			if visited 'разговор1' and _'телефон'.seen then
				if blizzard == 0 then
					pn [[Разглядывая белоснежный пейзаж, ты замечаешь вдали нечто странное.]]
					enable '#метель'
					blizzard = 1
					pic_set '5'
				end
				pn [[Ты видишь, как по земле ползут огромные клубы пара или снега.]]
				p [[Огромная снежная буря, накрывая деревья, движется к трассе!]]
				return
			end
			p [[Ты видишь, как за стеклом кружится метель.]];
			if s:once() then
				pic_set '2-pan-left'
			end
		end;
	}:attr 'scenery,openable';
	Prop {
		nam = "#заправка";
		-"заправка";
		before_Exam = [[Сквозь метель ты едва различаешь темные очертания заправки.]];
	}:disable();
}

dlg {
	nam = 'разговор1';
	title = false;
	enter = function()
		pic_set('3')
	end;
	phr = {
		[[-- Я говорю, тебе там понравится. Там хорошая школа, я узнавала... И музыкальная школа совсем недалеко. -- ты слышишь в голосе матери настойчивость.]];
		{
			'Я устала терять друзей.',
			'-- Ты же знаешь, что это необходимо! Я должна работать, чтобы ты смогла учиться в хорошем вузе! И это не конец света! На новом месте заведёшь новых друзей.',
			next = '#дальше';
		};
		{
			'Хорошо, мама...',
			'-- Ну что ты вечно строишь из себя мученика? Ты всего-лишь меняешь школу. Я работаю на твоё будущее и никакой благодарности!',
			next = '#дальше';
		};
	}
}: with {
	{
		'#дальше';
		{
			'Я заранее знаю всё, что ты скажешь!';
			'-- Ну зачем ты так? Ты стала такой грубой!';
		};
		{
			'Ты меня не поймёшь.';
			'-- А тебе не приходило в голову, что мне тоже было 13 лет?';
		};
		{
			'Просто мне очень плохо.';
			'-- Ты ведёшь себя как эгоистичный ребёнок. Ты думаешь мне легко?';
			{
				'Я ненавижу твою работу!',
				'-- Ты неблагодарная! Вместо поддержки, ты снова треплешь мне нервы!';
				{
					'Я устала от твоих скандалов. Замолчи!';
					'-- Ты это матери говоришь? Таким тоном? Как ты... можешь!';
				};
				{
					'Давай просто закончим этот разговор.';
					'-- Ты жестокая! Я отдала тебе все! И это моя самая большая ошибка!';
					{
						'Мама, прекрати!';
						function()
							p '-- Да, не ожидала я... Что у меня такая дочь...';
							if have 'телефон' then
								DaemonStart 'телефон'
							end
							walkback()
						end;

					}
				};
			};
			{
				'Ты могла бы сменить работу...',
				'-- Да? И получать гроши. И кто оплатит твоё обучение?';
			};
		}
	}
}
function pl:before_LetGo(w, ww)
	if w ^ 'телефон' then
		local s = w
		if s.compass and ww ~= pl then
			p [[В телефоне есть компас, который тебе нужен.]]
			return
		end
		return false
	elseif w ^ 'скрипка' and here() ^ 'пещера2' and mp:thedark() then
		p [[Ты не хочешь расставаться со своей скрипкой.]]
		return
	elseif w ^ 'осколки' then
		local s = w
		if not here() ^ 'пещера2' then
			return false
		end
		p [[Ты бросаешь осколки кристалла на пол пещеры. Маленькие светящиеся огоньки рассыпаются по ледяной поверхности. В тот же момент, пещеру заполняет шум хлопающих крыльев.]];
		here().solved = true
		drop(s)
		return
	end;
	return false
end

--"фонарик,фонарь"
--"сообщения|сообщение"

obj {
	function(s)
		pr (-"мобильный телефон,телефон,мобильник,смартфон");
		if s.flash then
			pr "|фонарик,фонарь"
		end
		if have(s) and here() ^ 'В машине' then
			pr "|сообщения|сообщение";
		end
	end;
	nam = "телефон";
	flash = false;
	compass = false;
	seen = false;
	each_turn = function(s)
		if here() ^ 'пещера2' and s:has'light' and not here().solved then
			p [[В ту же секунду ты слышишь хлопанье крыльев и успеваешь заметить,
как множество чёрных теней бросаются к тебе с потолка. Инстинктивно ты успеваешь выключить фонарик. Удивительно, но это успокаивает тварей. Некоторое время ты слышишь шум их крыльев. Затем всё затихает.]]
			s:attr'~light'
			return
		end
		if here():has 'light' and s:has 'light' then
			p [[В целях экономии заряда ты выключила фонарик.]]
			s:attr '~light'
		end
	end;
	daemon = function(s)
		if rnd(10) > 3 then
			p [[Ты слышишь сигнал входящего сообщения на своём смартфоне.]]
		end
	end;
	["before_Burn,Light"] = function(s)
		s.flash = true
		if s:has 'light' then
			p [[Фонарик в телефоне и так включён.]]
			return
		end
		if not mp:thedark() then
			p [[Тут и так светло.]]
			return
		end
		p [[Ты включила в мобильнике фонарик.]]
		pl:need_scene(true)
		s:attr 'light'
	end;
	before_SwitchOn = function(s)
		if s:multi_alias() == 2 then
			s:before_Light()
			return
		end
		if not s.flash and mp:thedark() then
			p [[Тебе приходит в голову мысль, что в телефоне есть фонарик и его можно включить...]]
			s.flash = true
			return
		end
		return false
	end;
	before_SwitchOff = function(s)
		if s:has 'light' then
			p [[Ты выключила фонарик в телефоне.]]
			s:attr '~light'
			pl:need_scene(true)
			return
		end
		if s:multi_alias() == 2 then
			p [[Фонарик и так выключен.]]
			return
		end
		if s.compass then
			p [[Если ты выключишь телефон, ты лишишься компаса.]]
			return
		end
		if not s.seen then
			p [[Ты не любишь, когда твой смартфон выключен.]]
			return
		end
		return false
	end;
	before_Exam = function(s)
		if not s:has 'on' then
			p [[Телефон выключен.]]
			return
		end
		if s:has 'light' then
			p [[В телефоне включён фонарик.]]
			return
		end
		if seen '#мама' then
			p [[Ты собираешься проверить новые сообщения, но
твоя мать замечает это в зеркале заднего вида.^
-- Ты круглые сутки сидишь с телефоном! Отдай его мне, сейчас же!]];
			s.seen = true
			s:daemonStop()
		else
			if not s.flash and mp:thedark() then
				p [[Тебе приходит в голову мысль, что можно посветить телефоном...]]
				s.flash = true
				return
			end
			if not s.compass then
				p [[Странно, нет приёма...]]
			end
			if here()^'поле' or here()^'В лесу' then
				if not s.compass then
					p [[Но в твоём смартфоне есть компас. И, похоже, он работает! Теперь ты можешь ориентироваться по сторонам света.]]
					s.compass = true
				else
					p [[Здорово, что в твоём смарфоне есть компас! В целях экономии батареи ты включаешь режим "в полёте".]]
				end
			else
				p [[Это твой старенький китайский смартфон. В основном, ты используешь его для социальных сетей.]]
				p [[А сейчас он служит тебе компасом.]]
				if s.flash then p [[И фонариком.]] end
			end
		end
	end;
	before_Give = function(s, w)
		if w ^ '#мама' then
			p [[Ты протягиваешь телефон матери, она молча забирает его и кладёт в бардачок.]]
			if not s.seen then
				s.seen = true
				s:daemonStop()
				p [[^Мать выглядит немного удивлённой -- ведь ты обычно тяжело расстаёшься со своим смартфоном.]]
			end
			move(s, 'бардачок')
			pic_set '4'
			return
		end
		return false
	end;
}:attr 'switchable,on,multi';


obj {
	nam = -"скрипка";
	init_dsc = [[Рядом лежит скрипка.]];
	before_Exam = [[Твоя скрипка. Тебе остался год, чтобы закончить музыкальную школу. Если честно, благодаря музыкальной школе ты стала ненавидеть музыку.]];
	after_Play = [[У тебя сейчас нет настроения играть.]];
}

function mp:Play(w)
	if not w then
		mp:xaction("Play", _'скрипка')
		return
	end
	if w ~= _'скрипка' then
		p [[Ты умеешь играть только на скрипке.]]
		return
	end
	if not have 'скрипка' then
		p [[Сначала тебе нужно взять скрипку в руки.]]
		return
	end
	return false
end

Verb {
	'#Attack2';
	'[|раз]бить,[|раз]бей';
	'{noun}/вн,scene : Attack';
}

Verb {
	'#PutOn';
	'повес/ить',
	'{noun}/вн,held на {noun}/вн,scene : PutOn',
	'~ на {noun}/вн,scene {noun}/вн,held : PutOn reverse',
}

Verb {
	'#Play';
	'играть,сыграть',
	'на {noun}/пр : Play',
	' : Play',
}

Verb {
	'#Light';
	'[|по|под]свети/ть,[|по|свеч/у,освети/ть';
	'{noun}/тв,held : Light'
}
VerbHint (
	'#Light',
	function(s)
		return mp:thedark() and have 'телефон'
	end
)
function mp:Light(w)
	if mp:check_held(w) then
		return
	end
	p "{#First} не {#if_hint/#first,plural,могут,может} светить."
end

function mp:Knock(w)
	if mp:check_live(w) then
		return
	end
	if mp.args[1].word == 'в' then
		p [[Ты постучала в]]
		p (w:noun'вн', ".")
	else
		p [[Ты постучала по]]
		p (w:noun'дт', ".")
	end
	p "Ничего не произошло."
end

function mp:Cry(w)
	p [[Это тебе не поможет.]]
end

function mp:Fun(w)
	p [[Ты глупо смеёшься.]]
end

Verb {
	"#Cry",
	"[|по|за]крич/ать,[|по]звать,крикн/уть,[|за|по]плак/ать,[|за|по]плач/ь",
	": Cry"
}

Verb {
	"#Fun",
	"[|по|рас|за]смеяться,[|по|за|рас]смей/ся,[|по|за|рас]смею/сь,[|по|за|рас]хохо/таться",
	": Fun"
}

Verb {
	"#Knock",
	"[|по]стуч/ать",
	"в {noun}/вн : Knock",
	"по {noun}/дт : Knock"
}

Verb {
	'#Tune';
	'настро/ить,настра/ивать',
	'{noun}/вн : Tune',
}
function mp:Tune(w)
	p ([[Тебе не нужно настраивать ]], w:noun 'вн', ".")
end
function mp:Photo()
	if not have 'телефон' then
		p [[Дебе нечем делать снимки.]];
	elseif mp:thedark() then
		p [[Нет света. Может быть, посветить телефоном?]]
	else
		local t = {
			[[Ты делаешь пару неудачных фоток и удаляешь их из телефона.]];
			[[Ты сделала удачную фотку.]];
			[[Ты сделала пару фоток и селфи.]];
		}
		p(t[rnd(#t)])
	end
end

Verb {
	'#Photo';
	'[|с|по]фото/графировать';
	'Photo';
}

function start(load)
	if not load then
----		fading.set {'fadeblack', max = 64, delay = 25 };
		move(pl, 'intro')
	end
end
function init()
	if theme.name() == '.mobile' or theme.name() == '.mobile2' then
		mp.togglehelp = true
		mp.autohelp = true
		mp.autohelp_limit = 1000
		mp.compl_thresh = 0
	else
		mp.togglehelp = false
		mp.autohelp = false
		mp.autohelp_limit = 8
		mp.compl_thresh = 1
	end
	pl.description = [[Тебя зовут Вера. Тебе почти 13 лет.]];
	pl.word = -'ты/жр,2л'
--	pl.room = 'intro'
	take 'телефон'
end

cutscene {
	nam = "метель1";
	title = false;
	exit = function(s)
		pic_set('81')
	end;
	enter = function(s)
		pic_set('75')
		if std.ref'mplayer' then
			lifeon 'mplayer'
		end
	end;
	text = {
		[[Ты открываешь дверь и толкаешь её наружу.^^
		Ты чувствуешь, как ветер давит на дверь с другой стороны, но ты сильней и вот -- дверь открыта.^^
		Холод, вместе с вихрем злых снежинок, быстро забирается внутрь салона.^^
		Ты выходишь из машины когда...^^
		На тебя обрушивается...]];
	};
	next_to = "метель2";
}

Title {
	nam = 'метель2';
	text = {
		[[{$fmt y,50%}{$fmt c|{$fmt b|МЕТЕЛЬ}}^^
{$fmt c|Игра на ЗОК-2019}^^^
{$fmt em|{$fmt c|Код: Пётр Косых^Графика: Pakowacz}}]];
	};
	next_to = 'поле';
	exit = function(s)
		pic_set('20-pan')
	end
}

obj {
	-"машина|дверь";
	nam = 'машина';
	inside_dsc = [[Ты находишься в машине.]];
	description = function(s)
		if s:multi_alias() == 2 then
			p [[Тебе нет дела до двери.]]
			return
		end
		return false
	end;
	dsc = function(s)
		p [[В снегу стоит машина.]];
		if _'перо':where() == s and _'перо':hasnt 'moved' then
			_'перо':init_dsc()
		end
	end;
	after_Close = function(s)
		if _'перо':inside(s) and not have 'перо' then
			p [[Когда ты захлопнула дверь машины, перо упало с крыши в снег.]]
			move('перо', 'поле')
			return
		end
		return false
	end;
	before_SwitchOn = [[Тебе не удаётся завести машину. Впрочем, ты все-равно не умеешь водить.]];
	before_SwitchOff = [[Двигатель не работает.]]
}:attr 'container,openable,open,static,enterable,light':with {
	obj {
		nam = 'радио';
		-"радио";
		after_SwitchOn = [[Ты включаешь радио. Шум помех нарушает тишину.]];
		['before_Turn,Tune'] = function(s)
			if s:hasnt 'on' then
				p [[Радио выключено.]]
				return
			end
			p [[Ты пытаешься поймать какую-нибудь волну, но на всех частотах только шум помех.]];
		end;
		when_on = 'Радио в машине издаёт помехи.';
		when_off = false;
	}:attr 'static,switchable,on';
	obj {
		nam = 'бардачок';
		-"бардачок|перчаточный ящик";
		obj = { 'браслет' };
		when_open = "Бардачок открыт.";
		before_Exam = function(s)
			if s:hasnt'open' then
				p [[Бардачок закрыт.]]
				return
			end
			return false
		end;
		when_closed = "Твоё внимание привлекает бардачок.";
	}:attr 'static,openable,container';
};
local function have_compass()
	return  have'телефон' and _'телефон'.compass
end

local function check_compass(w)
	if w == 'u_to' or w == 'd_to' or w == 'in_to' or w == 'out_to' then
		return
	end
	if not have_compass() then
		p [[Чтобы ориентироваться в пространстве, тебе нужен компас.]]
		return true
	end
	return
end

Area = Class ({
	compass_look = function(s, w)
		if check_compass(w) then
			return
		end
		if w == 'u_to' then
			mp:xaction("Exam", _'#небо')
			return
		end
		if w == 'd_to' then
			mp:xaction("Exam", _'#снег')
			return
		end
		return false
	end;
	cant_go = function(s, w)
		if check_compass(w) then
			return
		end
		return false
	end;
}, room)

Snow = Class {
	-"снег";
	before_Take = function(s)
		p [[Тебе не хочется играть в снежки.]]
	end;
	['before_Enter,Walk'] = "Ты и так стоишь среди снега.";
	['before_Receive'] = function(s, w)
		if here() ^ 'В лесу' then
			p ([[Потом ]], w:noun'вн', [[ сложно будет найти.]])
		else
			return false
		end
	end;
	after_Receive = function(s, w)
		move(w, here())
		return false
	end;
}:attr 'scenery,supporter';

Sky = Class {
	-"небо|облака";
	before_Exam = function(s)
		p [[Бледное небо нависло над головой. Солнца не видно.]];
	end;
	before_Default = "Небо далеко...";
}:attr 'scenery';

Area {
	nam = 'поле';
	-"поле";
	before_Walk = function(s)
		if where(pl) ^ 'машина' then
			p [[Машина не заводится. Придётся выйти и идти пешком.]]
			return
		end
		return false
	end;
	before_Cry = [[-- Ма-маааааа! -- нет ответа.]];
	onenter = function(s)
		if visited(s) then
			return
		end
		p [[Холод. Ты лежишь в снегу и медленно приходишь в себя.^
Некоторое время ты смотришь в небо. Затем поднимаешься на ноги и оглядываешься.^
Странно, но ты не видишь никакой заправки. Впрочем, и трассы тоже.]];
	end;
	dsc = function(s)
		p [[Ты стоишь в заснеженном поле.]]
		if have_compass() then
			p [[На западе начинается хвойный лес.]]
		else
			p [[Неподалёку начинается хвойный лес.]];
		end
	end;
	before_Listen = function(s)
		if _'радио':hasnt'on' then
			p [[Стоит звенящая тишина.]];
		else
			p [[Ты слышишь шум радиопомех из машины.]]
		end
	end;
	["n_to,ne_to,e_to,se_to,s_to"] = function(s, t)
		if mp.event == 'Exam' then
			return false
		end
		if check_compass('w_to') then
			return
		end
		p ("Ты идешь некоторое время на ", (_('@'..t).word), ".")
		p ("Ничего не меняется. Вокруг все-такой же пустынный пейзаж. Ты решаешь вернуться к машине.")
	end;
	["w_to,nw_to,sw_to"] = function(s)
		if check_compass('w_to') then
			return
		end
		return "#лес"
	end;
	out_to = function()
		p [[Сначала нужно решить, куда тебе идти.]];
	end;
}:with {
	'машина',
	Sky { nam = '#небо' };
	Snow {
		nam = '#снег';
		before_Exam = function(s)
			p [[Ты видишь запорошенные снегом следы, которые ведут в лес.]]
			enable '#следы'
		end;
	};
	obj {
		nam = '#лес';
		-"хвойный лес,лес|чаща|деревья";
		before_Default = [[Лес далеко.]];
		before_Exam = function()
			p "На деревьях лежит снег.";
		end;
		['before_Walk,Enter,Climb'] = function(s)
			walk 'В лесу';
		end;
	}:attr 'scenery';
	obj {
		nam = '#следы';
		before_Exam = "Следы уже почти скрылись под свежим снегом.";
	}:attr 'scenery';
	Prop {
		-"колёса|колесо|двери";
	};
}

game:dict {
	["деревья/мн,С"] = {
		"деревья/им";
		"деревья/вн";
		"деревьев/рд";
		"деревьями/тв";
		"деревьях/пр";
		"деревьям/дт";
	};
	["огонь/вн"] = "огонь";
	["стены/рд"] = "стен";
	["голем/рд"] = "голема";
	["голем/дт"] = "голему";
	["голем/тв"] = "големом";
	["голем/вн"] = "голема";
	["голем/пр"] = "големе";
}

obj {
	-"олень";
	nam = 'олень';
	sit = false;
	['before_Touch,Talk,Ask,Tell,Kiss'] = function(s)
		s.step = 4
		p [[Олень попятился и шумно задышал, жадно втягивая морозный воздух.]]
	end;
	['life_Give,Show'] = function(s, w)
		if not w ^ 'перо' then
			return false
		end
		if s.sit then
			p [[Олень никак не отреагировал.]]
			return
		end
		s.sit = true
		p [[Ты подносишь перо к носу оленя. Чувствуя прикосновение, он шумно втягивает в себя воздух. Затем он опускается перед тобой на колени.]];
		s:daemonStop()
	end;
	init_dsc = [[Ты видишь на поляне оленя.]];
	["before_Enter,Climb"] =  function(s)
		if where(pl) == s then
			p [[Но ты уже и так на олене.]]
			return
		end
		if not s.sit then
			s:before_Touch()
			return
		end
		if not have 'перо' then
			p [[Ты подумала, что тебе стоит сначала взять с собой перо странной совы. Кто знает, куда умчит тебя олень?]]
			return
		end
		s:daemonStop()
		s.sit = false
		if here() ^ 'В лесу' then
			walk 'к хребту'
		else
			walk 'к поляне'
		end
	end;
	before_Exam = function(s)
		if s.sit then
			p [[Олень стоит перед тобой на коленях.]]
		else
			if s:once() then
				p [[Ты замечаешь, что у оленя странные глаза.]]
			else
				p [[Чёрные дырки-глаза оленя пугают тебя.]]
			end
		end
	end;
	step = 0;
	daemon = function(s)
		s.step = s.step + 1
		if s.step > 5 then
			p [[Олень скрылся в лесу.]]
			s:disable()
			s:daemonStop()
			s.step = 0;
		end
		return
	end;
}:disable():with {
	obj {
		-"глаза оленя,глаза,дыр*";
		before_Exam = [[Вместо глаз у оленя чёрные дырки.]];
		before_Default = [[Тебе не нравятся глаза оленя.]];
	}:attr 'scenery';
	Prop { -"рога оленя,рога" };
}:attr 'supporter'

local function forest_scenery(s)
	disable 'сова'
	disable 'олень'
	disable '#ручей'
	disable '#поляна'
	if s.depth == 0 then
		enable 'сова'
	elseif s.depth == 2 then
		enable '#ручей'
	elseif s.depth == 3 then
		enable '#поляна'
		enable 'олень'
		pic_set '22'
		_'олень'.step = 0
		_'олень'.sit = false
		_'олень':daemonStart()
	end
end
Area {
	-"лес|чаща";
	depth = 0;
	nam = 'В лесу';
	before_Cry = [[-- Ма-маааааа! -- нет ответа.]];
	title = 'Лес';
	enter = function(s)
		if seen 'сова' then
			_'сова':daemonStart()
		end
	end;
	before_Drop = function(s, w)
		p ("Зачем бросать ", w:noun'вн', " в лесу?")
	end;
	dsc = function(s)
		p [[Ты находишься в хвойном лесу.]]
		if s.depth == 0 then
			if not have_compass() then
				p [[Между деревьями ты видишь снежное поле.]];
			else
				p [[Между деревьями на востоке ты видишь снежное поле.]];
			end
		elseif s.depth == 1 then
			p [[Тебя окружают деревья.]]
		elseif s.depth == 2 then
			p [[Ты видишь здесь замёрзший ручей.]]
		elseif s.depth == 3 then
			p [[Ты вышла на небольшую поляну.]]
		elseif (s.depth - 4) % 2 == 0 then
			p [[Лес становится всё гуще.]]
		elseif (s.depth - 4) % 2 == 1 then
			p [[Деревья окружают тебя со всех сторон.]]
		end
	end;
	['w_to,nw_to,sw_to'] = function(s, t)
		if check_compass(t) then
			return
		end
		s.depth = s.depth + 1
		if s.depth > 8 then s.depth = 6 + rnd(3) end
		forest_scenery(s)
		pl:need_scene(true)
		p ("Ты идешь некоторое время на ", (_('@'..t).word), ".")
		if s.depth > 7 and rnd(100) < 30 then
			p [[^Ты можешь идти так целую вечность...]]
		end
	end;
	['s_to,n_to'] = function(s, t)
		if check_compass(t) then
			return
		end
		if s.depth <= 1 then
			p [[Ты решила, что идти вдоль границы леса не очень хорошая идея.]]
		else
			p [[Ты решила, что лучше держаться западного направления.]]
		end
	end;
	['e_to,se_to,ne_to'] = function(s, t)
		if check_compass(t) then
			return
		end
		if s.depth == 0 then
			return '#поле'
		end
		pl:need_scene(true)
		s.depth = s.depth - 1
		p ("Ты идешь некоторое время на ", (_('@'..t).word), ".")
		if s.depth == 0 then
			p [[За деревьями на востоке ты видишь снежное поле.]]
		end
		forest_scenery(s)
	end;
	out_to = function(s)
		if s.depth == 0 then
			return '#поле';
		end
		return false
	end;
}: with {
	Sky { nam = '#небо' };
	Snow {
		nam = '#снег';
		before_Exam = function(s)
			if here().depth == 0 then
				p [[Здесь едва заметный след теряется.]];
			else
				return false
			end
		end;
	};
	obj {
		nam = '#поле';
		before_Exam = "Снежное поле выглядит бескрайним.";
		before_Default = [[Поле далеко.]];
		['before_Walk,Enter,Climb'] = function(s)
			if here().depth == 0 then
				walk 'поле'
			else
				p [[Поле где-то на востоке.]]
			end
		end;
	}:attr 'scenery';
	Prop {
		-"деревья|дерево|сосна,ветк*";
		nam = '#деревья';
		before_Exam = function(s)
			if s:hint'plural' then
				p "Деревья покрыты снегом.";
			else
				p "Ветви дерева покрыты снегом.";
			end
		end;
		["before_Enter,Climb"] = "Первые ветки находятся высоко. У тебя не получится забраться.";
	};
	obj {
		nam = 'сова';
		talked = false;
		seen = false;
		-"полярная сова,сова,птица";
		init_dsc = [[Ты замечаешь большую сову, сидящую на ветке сосны.]];
		before_Touch = function(s)
			if where(s) ^ 'В лесу' then
				p [[Она слишком высоко.]]
				return
			end
			if not s.seen then
				p [[Сначала хорошо бы рассмотреть, с чем имеешь дело.]]
				return
			end
			if s.talked then
				p [[Тебе не очень хочется иметь с ней дело.]]
			else
				p [[Ты осторожно дотронулась до птицы.^]]
				p [[Сова вздрогнула и её глаза-дырки уставились на тебя.]]
			end
		end;
		talk_to = function(s)
			if where(s) ^ 'В лесу' then
				p [[Хлопая крыльями сова улетела в сторону поля.]]
				move(s, 'поле')
				return
			end
			if not s.seen then
				p [[Сначала хорошо бы рассмотреть, с чем имеешь дело.]]
				return
			end
			if s.talked then
				p [[-- Что всё это значит?^
-- Я сделала то, что мне повелела госпожа.]];
				p [[^Сова хлопнула крыльями и улетела.]]
				remove(s)
				s:daemonStop()
				return
			end
			return 'разговор с совой'
		end;
		dsc = function(s)
			if where(s) ^ 'поле' then
				p [[На машине сидит сова.]]
			else
				p [[На ветке сосны сидит сова.]]
			end
		end;
		before_Exam = function(s)
			p [[Тебе кажется, что это полярная сова. Только у неё странные глаза.]];
			if here() ^ 'поле'  then
				pn()
				_'#глаза совы':before_Exam()
			end
		end;
		daemon = function(s)
			if s.talked then
				return
			end
			if s:where() ^ 'В лесу' and where(s) ^ 'В лесу' and _'В лесу'.depth == 0
			and rnd(3) == 1 then
				p [[Хлопая крыльями сова улетела в сторону поля.]]
				move(s, 'поле')
			elseif here() ^ 'поле' and where(s) ^ 'поле' and s.talked and rnd(3) == 1 then
				p [[Хлопая крыльями сова улетела в сторону леса.]]
				move(s, 'В лесу')
			end
			return
		end;
	} : with {
		obj {
			-"глаза совы,глаза,дыр*";
			nam = '#глаза совы';
			before_Exam = function(s)
				p [[На месте глаз у совы зияют чёрные дырки.]];
				if not _'сова'.seen then
					p [[^Интересно, видит ли она тебя?]]
				end
				_'сова'.seen = true
			end;
			before_Default = [[Тебе не нравятся эти глаза.]];
		}
	};
	Prop {
		-"поляна";
		nam = '#поляна';
	}:disable():attr'scenery';
	Prop {
		-"ручей";
		nam = '#ручей';
	}:disable():attr'scenery';
	'олень';
}
obj {
	-"перо";
	nam = 'перо';
	init_dsc = function(s)
		if s:hasnt 'moved' and where(pl) ^ 'машина' then
			return
		end
		p [[На крыше машины лежит белое перо.]];
	end;
	before_Exam = function(s)
		p [[Белое перо.]]
		if have(s) then
			p [[Зачем оно тебе?]];
		else
			p [[Его оставила сова с дырками вместо глаз.]]
		end
	end;
}

dlg {
	nam = 'разговор с совой';
	title = false;
	enter = function(s)
		pic_set '21'
	end;
	exit = function()
--		pic_pop()
	end;
	phr = {
		[[-- О, я слышу тебя, дитя! -- ответ птицы напугал тебя.]],
		{
			"Ты меня не видишь?";
			"-- Я тебя чувствую...";
		};
		{
			"Ты умеешь говорить?";
			"-- Я разговариваю с тобой.";
		};
		{
			"Что с твоими глазами?";
			"-- Такой меня сделала моя госпожа.";
			{
				"Кто твоя госпожа?";
				"-- Она вызвала меня. Она сказала, чтобы я передала тебе...";
				{

					"Что?";
					"-- Твоя мама ждёт тебя во дворце. Поспеши.";
					next = "#deep";
				};
				{
					"Ты видела мою маму?";
					"-- Твоя мама ждёт тебя во дворце. Поспеши.";
					next = "#deep";

				}
			}
		};
	}
}: with {
	{
		'#deep';
		{
			"Где этот дворец?";
			"-- Он за ледяным хребтом на западе.";
			{
				"Это далеко?";
				function(s)
					p "-- Расстояние -- всего лишь время. А время здесь замёрзло. Возьми перо. По нему тебя узнают другие слуги госпожи.";
					move ('перо', 'машина')
					_'перо':attr '~moved'
					_'сова'.talked = true
					walkout()
				end;
			}
		};
		{
			"Что за бред ты несёшь.";
			"-- Моя госпожа сказала мне передать тебе...";
			{
				"Ладно, ладно...";
				"-- Поспеши же, дитя!";
			}
		}
	}
}

cutscene {
	nam = 'к хребту';
	title = false;
	text = {
		[[Ты садишься на оленя и он поднимается с колен.^^
		Вы мчитесь через лес на запад. Снова и снова олень ловко огибает встречные деревья и вы оставляете их позади.^^
		Постепенно лес начинает редеть и сквозь деревья ты видишь ледяные горы.^^
		Олень остановился перед ледяной стеной и опустился, чтобы ты могла слезть.]];
	};
	next_to = 'Ледяные горы';
	onexit = function(s, to)
		p[[Ты слезаешь с оленя.]]
		move('олень', to)
	end;
}

cutscene {
	nam = 'к поляне';
	title = false;
	text = {
		[[Ты садишься на оленя и он поднимается с колен.^^
		Вы мчитесь через лес на восток. Снова и снова олень ловко огибает встречные деревья и вы оставляете их позади.^^
		Постепенно лес начинает редеть.^^
		Олень остановился и опустился на колени, чтобы ты могла слезть.]];
	};
	next_to = 'В лесу';
	onexit = function(s, to)
		p[[Ты слезаешь с оленя.]]
		move('олень', to)
	end;
}

Area {
	nam = 'Ледяные горы';
	title = 'У ледяных гор';
	dsc = [[Ты стоишь перед ледяной стеной, которая продолжается на север и юг. На востоке начинается лес.]];
	['e_to,ne_to,se_to'] = '#лес';
	w_to = '#стена';
	in_to = '#стена';
	onexit = function(s, t)
		if t ^ 'пещера' and not visited 'пещера' then
			pic_set '23-pan'
		end
	end;
	['nw_to,sw_to,n_to,s_to'] = function(s)
		p [[По этому направлению нет ничего интересного. Такая же ледяная стена.]];
	end;
}: with {
	obj {
		nam = '#лес';
		-"хвойный лес,лес|чаща|деревья";
		before_Default = [[Лес далеко.]];
		before_Exam = function()
			p "На деревьях лежит снег.";
		end;
		['before_Walk,Enter,Climb'] = function(s)
			p "В этом лесу можно ходить вечность.";
		end;
	}:attr 'scenery';
	Snow { nam = '#снег' };
	Sky { nam = '#небо' };
	obj {
		function(s)
			pr (-"ледяная стена,стена|лёд|лед|поверхность|скала|гора|горы/жр");
			if s.light > 0 then
				pr (-"|свечение/ср|свет")
			end
		end;
		nam = '#стена';
		light = 0;
		before_Taste = [[А язык не приклеится?]];
		before_Climb = [[У тебя вряд ли это получится. Стена отвесная.]];
		["before_Enter,Walk"] = function(s)
			if s.light == 0 then
				p [[Как ты это сделаешь? Стена твёрдая, гладкая и скользкая.]]
				return
			end
			walk 'пещера'
		end;
		before_Exam = function(s)
			if s.light > 0 then
				p [[Сквозь лёд ты видишь фиолетовое свечение.]]
			else
				p [[Ледяная стена отвесно уходит вверх. Её поверхность выглядит скользкой.]]
			end
		end;
		daemon = function(s)
			if player_moved() then
				s.light = 0
				s:daemonStop()
				return
			end
			if s.light == 1 then
				p [[Ты замечаешь, что под поверхностью льда разливается фиолетовое свечение.]]
			elseif s.light == 2 then
				p [[Фиолетовое свечение под поверхностью льда усиливается!]]
			elseif s.light == 3 then
				p [[Фиолетовое свечение ослабевает.]]
			else
				s:daemonStop()
				s.light = 0
				return
			end
			s.light = s.light + 1
		end;
		before_Attack = function(s)
			p [[Скала {$fmt em|выглядит} твёрдой. Ты решила не рисковать.]];
		end;
		before_Knock = function(s)
			if s.light == 0 then
				return false
			end
			p [[Ты попыталась постучать по стене, но у тебя это не вышло! Рука прошла сквозь лёд!]]
		end;
		['before_Touch,Push'] = function(s)
			p [[Ты касаешься ладонью гладкой ледяной поверхности.]];
			if s.light > 0 then
				p [[Как странно, твоя рука проходит сквозь лёд!]]
				s.light = 2
			else
				s.light = 1
			end
			s:daemonStart();
		end;
	}:attr 'scenery';
}

room {
	nam = 'пещера';
	-"пещера";
	onenter = function(s)
		if not visited(s) then
			p [[Доверившись интуиции, ты входишь в фиолетовое свечение, которое вдруг заполняет всё вокруг. Шаг. Еще один. И вдруг ты оказываешься в полной темноте. Если не считать слабого свечения позади.]]
		end
	end;
	title = function(s)
		if mp:thedark() then
			p [[В темноте]]
		else
			p [[Ледяная пещера]]
		end
	end;
	dark_dsc = [[Ты видишь слабое свечение в темноте.]];
	dsc = [[Ты находишься внутри небольшой ледяной пещеры. У восточной стены ты видишь странное свечение.^
Пещера продолжается на северо-запад.]];
	out_to = 'Ледяные горы';
	nw_to = function(s)
		if mp:thedark() and not visited'пещера2' then
			p [[Ты же не видишь куда идти.]]
			return
		end
		return 'пещера2'
	end;
	Play = function(s, w)
		if not w or not have 'скрипка' then
			return false
		end
		if not w then w = _'скрипка' end
		if not w ^ 'скрипка' then
			return false
		end
		if _'#кристаллы'.try == 0 or _'#кристаллы'.broken then
			return false
		end
		_'#кристаллы'.broken = true
		pic_set '24'
		p [[Интересно... А что если? Не успев додумать мысль, ты уже берёшь скрипку в руки.^^
Ты извлекаешь "ми" второй октавы. Сначала ничего не происходит, но затем ты слышишь, как странный кристалл отзывается
на звук твоей скрипки.^^
Звуки скрипки и кристалла усиливают друг друга в резонансе. Ты почти физически ощущаешь, как
напряжение кристалла достигает своего пика. И, наконец, он шумно взрывается на мелкие осколки.]]
		enable 'осколки'
	end;
	e_to = '#свечение';
}:attr '~light': with {
	obj {
		nam = '#свечение';
		-"свечение";
		['before_Touch,Push,Knock'] = 'Твоя рука проходит сквозь свечение.';
		before_Exam = function(s)
			p [[Этим путём ты попала сюда. Вероятно, с помощью него можно выйти наружу.]];
			p [[^Ты обращаешь внимание, что источником странного свечения служат фиолетовые кристаллы, растущие из стены.]]
			enable '#кристаллы'
		end;
		['before_Walk,Climb,Enter'] = function(s)
			walk 'Ледяные горы';
		end;
	}:attr 'scenery,luminous';
	Prop {
		nam = '#стены';
		-"стены|стена|пол|потолок";
		['before_Touch,Push,Knock'] = [[Похоже, ты находишься в ледяной пещере.]];
		before_Exam = function(s)
			if mp:thedark() then
				p [[В полной темноте это будет сложно.]]
			else
				return false
			end
		end;
	}:attr 'luminous';
	obj {
		-"кристаллы|кристалл";
		nam = '#кристаллы';
		try = 0;
		broken = false;
		before_Exam = [[Полупрозрачные кристаллы растут прямо из льда.]];
		before_Touch = function(s)
			if s.try == 0 or s.broken then
				return false
			else
				p [[Ты чувствуешь как кристалл вибрирует.]]
			end
		end;
		['before_Attack,Knock'] = function(s)
			if s.broken then
				p [[Ты уже разрушила один кристалл.]]
				return
			end
			if s.try == 2 then
				p [[Ты постучала по звонкому кристаллу.]]
			else
				p [[Ты постучала по одному из кристаллов.]]
			end
			if s.try == 0 then
				s.try = 1
				p [[Ответом был мелодичный звенящий звук. Твой музыкальный слух определил его как "фа" малой октавы, что
				находится вне диапазона твоей скрипки. Интересно, они все звучат одинаково?]]
			elseif s.try == 1 then
				p [[На этот раз звук оказался более высоким. Ты определила его как {$fmt em|"ми"} второй октавы.]]
				p [[^Ты решила запомнить этот кристалл.]]
				s.try = 2
			else
				p [[Звенящий звук кристалла долго отражается от ледяных стен. Ты чувствуешь вибрацию.]]
			end
		end;
	}:attr 'luminous,static':disable();
	obj {
		-"осколки кристалла,осколок*|осколки|кусочки|куски";
		nam = 'осколки';
		before_Exam = [[Осколки кристалла пульсируют слабым фиолетовым свечением.]];
		before_Take = function(s)
			if here() ^ 'пещера2' and here().solved then
				p [[Ты боишься беспокоить летучих мышей.]]
				return
			end
			return false
		end;
		before_Light = [[Свет испускаемый осколками очень тусклый для этого.]];
	}:attr 'luminous':disable();
}

obj {
	nam = 'ообрыв';
	-"обрыв,разлом|пропасть";
	before_Exam = function(s)
		p [[Глубокий разлом во льду. Света фонарика недостаточно, чтобы оценить его глубину. К счастью, ширина разлома не превышает двух метров.]];
	end;
	before_JumpOver = function(s)
		p [[Ты разбегаешься и прыгаешь через пропасть...]]
		if here() ^ 'обрыв' then
			walk 'Другая сторона'
		else
			walk 'обрыв'
		end
	end;
	before_Receive = function(s, w)
		p ("Ты потом не сможешь достать ", w:noun 'вн', " из пропасти.")
	end;
	before_Enter = [[Прыгнуть в пропасть? Тебе нужно найти маму, а не сбегать от проблем...]];
}:attr 'scenery,container,open';

room {
	-"пещера";
	solved = false;
	nam = 'пещера2';
	title = "Пещера с летучими мышами";
	out_to = function(s)
		if from() ^ 'пещера' then
			return 'пещера'
		else
			return 'обрыв'
		end
	end;
	dsc = function(s)
		pn [[Стены этой части пещеры испещрены небольшими отверстиями.]];
		if from() ^ 'пещера' then
			p [[Ты попала сюда с юго-востока. Пещера продолжается на юго-запад.]]
		else
			p [[Ты попала сюда с юго-запада. Пещера продолжается на юго-восток.]]
		end
		if not s.solved then
			p [[^^Твой взгляд прикован к потолку, который усеян чёрными лоскутками. Ты вздрагиваешь, когда ответ приходит тебе в голову. Пещера заполнена летучими мышами!]]
		else
			p [[^^Ты видишь, как странные чёрные твари дерутся за фиолетовые осколки кристалла,
котрые ты рассыпала по полу пещеры.]];
		end
	end;
	before_Listen = function(s)
		if s.solved then
			p [[Ты слышишь отвратительный писк и хлопанье крыльев.]]
		else
			p [[Стоит мёртвая тишина.]]
		end
	end;
	['se_to,e_to'] = 'пещера';
	['sw_to,w_to'] = function(s)
		if mp:thedark() and not visited'обрыв' then
			p [[Сложно сделать это в полной темноте.]]
			return
		end
		return 'обрыв';
	end;
}:attr '~light' : with {
	Prop {
		-"стены|стена|пол|потолок";
	};
	obj {
		nam ='#мыши';
		-"летучие мыши,мыши,твари,мышь*";
		before_Attack = [[Тебе не удастся убить их всех.]];
		['life_Show,Give'] = [[Пока они заняты, лучше их не беспокоить.]];
		description = function(s)
			p [[Тебе они не нравятся. Называя вещи своими словами -- ты их панически боишься.]];
			if here().solved then
				p [[^Но кажется, они поглощены борьбой за светящимися осколками кристалла.]]
			end
		end;
	}:attr 'concealed,animate';
	obj {
		-"отверстия|дырки|дыры";
		before_Receive = [[Не стоит туда соваться.]];
		description = [[Тебе приходит в голову, что эти отверстия могут быть норами. Лучше держаться от них подальше.]];
	}:attr'scenery,container'
}
room {
	nam = 'обрыв';
	dsc = [[На западе гладкий пол пещеры заканчивается обрывом. Выход находится на юго-востоке.]];
	out_to = 'пещера2';
	w_to = "ообрыв";
	['se_to,e_to'] = 'пещера2';
}:attr '~light': with {
	Prop {
		-"стены|стена|пол|потолок";
	};
	'ообрыв';
}

obj {
	function()
		pr (-"отверстие|выход|дырка|дыра");
		if here() ^ 'За ледяной стеной' then
			pr (-"|пещера")
		end
	end;
	nam = "отверстие";
	before_Exam = [[Отверстие достаточно широкое для того, чтобы пролезть в него.]];
	["before_Enter,Walk,Climb"] = function(s)
		if here() ^ 'Другая сторона' then
			walk 'За ледяной стеной';
		else
			walk 'Другая сторона'
		end
	end;
}:attr 'scenery';

room {
	nam = 'Другая сторона';
	title = "Пещера";
	-"пещера";
	dsc = [[Здесь светло. Свет поступает в пещеру через широкое отверстие на западе.
Пропасть находится на востоке.]];
	out_to = "отверстие";
	w_to = "отверстие";
	e_to = "ообрыв";
}: with {
	"ообрыв",
	'отверстие',
	Prop {
		-"стены|стена|пол|потолок";
	};
}

room {
	nam = 'За ледяной стеной';
	title = 'Плато';
	-"плато/ср";
	dsc = function()
		p [[Ты находишься на снежном плато, рядом со входом в пещеру. Ледяные горы окружают плато со всех сторон. Может быть поэтому, стоит мёртвая тишина.]]
		p [[На западе, в центре плато возвышается ледяная скала.]];
	end;
	in_to = 'отверстие';
	e_to = 'отверстие';
	w_to = '#замок';
	cant_go = function(s)
		p [[На плато не видно ничего интересного, кроме скалы.]]
	end;
}: with {
	'отверстие';
	Prop {
		-"горы/но,мн|стена|стены";
	};
	Snow { nam = '#снег' };
	Sky { nam = '#небо' };
	obj {
		nam = '#замок';
		-"скала|замок|дворец|вершины";
		before_Exam = [[Остроконечные вершины ледяной громады высоко возвышаются над плато.]];
		before_Default = [[Сначала к скале нужно подойти.]];
		['before_Enter,Walk,Climb'] = function(s)
			walk 'У замка'
		end;
	}:attr 'scenery'
}

obj {
	-"разлом|проход|отверстие|щель|вход";
	nam = 'ворота';
	description = [[Высота разлома с неровными краями достигает трёх метров, а ширина -- двух. Верх отверстия имеет форму арки.]];
	['before_Walk,Enter,Climb'] = function(s)
		if here() ^ 'У замка' then
			mp:xaction("Enter", _'#замок')
		else
			walk 'У замка'
		end
	end;
}:attr 'scenery':disable()

obj {
	function(s)
		if s:has'animate' then
			p (-"ледяной человек/ед,мр,од|человек|статуя|голем/ед,мр,од");
		else
			p (-"статуя|ледяной человек|человек");
		end
	end;
	nam = 'голем';
	before_Taste = [[А язык не приклеится?]];
	init_dsc = function(s)
		if s:has'animate' then
			p [[У стены стоит ледяной человек.]]
		else
			p [[Твоё внимание привлекает огромная ледяная статуя.]]
		end
	end;
	before_Any = function(s, e)
		if e == 'Exam' or e == 'Walk' or e == 'Climb' or e == 'Enter' then
			return false
		end
		if not disabled 'дверь' or not visited 'королева-диалог' then
			return false
		end
		p [[Сначала к голему нужно подойти.]]
	end;
	description = function(s)
		if s:has'animate' then
			p [[Высота ледяного человека около двух метров. У него есть руки и ноги, но вместо головы лишь небольшой выступ.]]
			if visited 'королева-диалог' and disabled 'дверь' then
				p [[Сейчас голем стоит у северной части зала и ждет тебя.]]
			end
		else
			p [[Статуя сделана из льда и изображает двухметрового человека с массивным телосложением.]]
		end
	end;
	before_Climb = [[Это не так просто сделать.]];
	['before_Walk,Enter,Climb'] = function(s)
		if visited 'королева-диалог' and disabled 'дверь' then
			p [[Ты последовала за големом. Обогнув колонну и подойдя к северной стене, ты заметила небольшую деревянную дверь.]]
			enable 'дверь'
			return
		end
		return false
	end;
	['before_Take,Push,Pull'] = function(s)
		p (s:Noun(), " весит не меньше сотни килограмм. Как ты это сделаешь?");
	end;
	['life_Give,Show,ThrowAt'] = function(s, w)
		if w ^ 'перо' then
			if disabled 'ворота' then
				p [[Едва ты достала перо, как статуя сдвинулась с места. Сделав два шага по направлению к тебе,
страшный ледяной человек остановился.^]]
				enable 'ворота'
				p [[-- Госпожа ждёт тебя! -- прогремел голос с двух метровой высоты.^]]
				p [[После этих слов голем размахнулся и ударил своим кулаком в стену.]]
				p [[Стена с треском раскололась и в ней образовался проход.]]
				s:attr'animate'
			else
				if not visited 'Тронный зал' then
					p [[-- Госпожа ждёт тебя! -- прогремел голос с двух метровой высоты.]]
				else
					p [[-- Я узнал тебя.]]
				end
			end
			return
		end
		return false
	end;
}: attr '~animate':with {
	Prop {
		-"ноги|руки|голова|выступ"
	};
}

room {
	nam = 'У замка';
	title = 'У подножия скалы';
	e_to = 'За ледяной стеной';
	w_to = '#замок';
	in_to = '#замок';
	onenter = function(s)
		if not visited(s) then
			pic_set '25'
		end
	end;
	dsc = function(s)
		p [[Ты стоишь у подножия ледяной скалы. Отвесная стена уходит высоко вверх.]];
		if not disabled 'ворота' then
			p [[В стене зияет разлом.]]
		end
		p [[Пещера, с помощью которой ты прошла сквозь горы, находится на востоке.]]
	end;
}: with {
	'голем';
	obj {
		nam = '#замок';
		-"скала|гора|замок|дворец|стена";
		description = [[Острые вершины скалы устремлены в небо.]];
		before_Taste = [[А язык не приклеится?]];
		obj = { 'ворота' };
		['before_Enter,Walk,Climb'] = function(s)
			if disabled 'ворота' then
				return false
			end
			if _'голем':hasnt'moved' then
				move('голем', 'Тронный зал')
			end
			walk 'Тронный зал';
		end;
	}:attr 'scenery';
	Snow { nam = '#снег' };
	Sky { nam = '#небо' };
}

obj {
	-"мама,мать,королева,женщина";
	nam = 'королева';
	queen = false;
	init_dsc = function(s)
		p [[На троне сидит твоя мама.]]
		if s.queen then
			p [[Или это не мама?]]
		end
	end;
	before_Walk = function(s)
		return _'#трон':before_Walk()
	end;
	daemon = function(s)
		local tt = {
			"-- Иди ко мне скорее, моё дитя!",
			"-- Что же ты медлишь? Обними и поцелуй свою мать!",
			"-- Я так долго тебя ждала!",
			"-- Теперь всё будет хорошо, я буду любить тебя всегда!",
			"-- Мы будем вместе!",
		}
		p (tt[rnd(#tt)], " -- произносит твоя мать с трона.")
	end;
	['before_Talk,Say,Ask,Tell'] = function(s)
		if not s.queen then
			p [[Сначала ты хочешь рассмотреть её внимательней.]]
		else
			s:daemonStop()
			if visited'королева-диалог' then
				p [[-- Ты уже готова стать моей дочерью?^
-- Нет!^
-- Ну что же, я подожду.]]
			else
				if _'браслет':has 'worn' then
					walk 'королева-диалог'
				else
					walk 'badend2'
				end
			end
		end
	end;
	['before_Kiss,Touch'] = function(s)
		p [[Тебе кажется, что это не твоя мама. Тебе становится страшно.]]
	end;
	description = function(s)
		s.queen = true
		if _'Тронный зал'.near then
			p [[Женщина похожа на твою маму, но в чертах её лица ты видишь что-то незнакомое, чужое и, поэтому, неприятное.
Но больше всего тебя пугают её глаза. Они закрыты. Ты растерянно вглядываешься в её лицо, снова и снова пытаясь отыскать родные черты.]];
		else
			p [[Это твоя мама! Не может быть! Что это за место? Что она тут делает? Столько вопросов!]]
		end
	end;
}:attr 'animate':with {
	obj {
		-"лицо";
		description = function(s)
			if _'Тронный зал'.near then
				_'королева':description()
			else
				p [[Отсюда плохо видно её лицо.]]
			end
		end;
	};
	obj {
		-"глаза";
		description = function(s)
			if _'Тронный зал'.near then
				if not visited 'королева-диалог' then
					p [[Её глаза закрыты. Как будто она спит. Тебе становится страшно.]]
				else
					p [[Ты стараешься не думать о глазах твоей {$fmt em|новой} мамы.]]
				end
			else
				p [[Отсюда плохо видны её глаза.]]
			end
		end;
	};
};

room {
	-"зал";
	nam = 'Тронный зал';
	near = false;
	['s_to,d_to'] = '#лестница';
	in_to = function(s)
		if not disabled 'дверь' then
			return 'дверь'
		end
		return false
	end;
	n_to = function(s)
		if disabled 'дверь' and visited 'королева-диалог' then
			return 'голем'
		end
		if not disabled 'дверь' then
			return 'дверь'
		end
		return false
	end;
	before_Default = function(s, e, w)
		if not w then
			return false
		end
		if not w ^ 'королева' and not w ^ '#трон' then
			return false
		end
		if e == 'Exam' or s.near then
			return false
		end
		if e == 'Walk' then
			return false
		end
		p [[Сначала нужно подойти к трону.]]
	end;
	onexit = function(s, to)
		if to ^ 'королева-диалог' or to ^ 'badend2' or to ^ 'badend4' then
			return
		end
		if not s.near then
			if _'браслет':hasnt'worn' then
				if to ^ 'Зал с зеркалами' then
					p [[Сейчас не лучшее время для прогулок.]]
					return false
				end
				p [[Поддавшись смутному интуитивному чувству, ты покидаешь тронный зал.]]
				DaemonStop 'королева'
				return
			end
			p [[Ты нашла свою маму! Не время уходить!]]
			return false
		end
		if seen 'голем' then
			if not visited 'королева-диалог' then
				p [[Ты пытаешься уйти из зала, но ледяной голем преграждает тебе путь.]]
				return false
			end
		end
	end;
	enter = function(s)
		if s:once() then
			pn [[Набравшись мужества ты вошла внутрь и оказалась в длинном коридоре.]]
			p [[Голем последовал за тобой. Его шаги гулко отражались от изломанных стен и сводчатого потолка.]]
			pn [[Через некоторое время коридор кончился и вы вошли в большой зал.]]
			pn [[Зал был огромен! В его центре ты увидела трон, на котором сидела женщина... Твоя... мама?]]
			pn [[-- Я ждала тебя! Подойди же и поцелуй меня! -- голос матери, отраженный от ледяных стен зала показался тебе чужим.]]
			DaemonStart 'королева'
			remove 'сова'
			pic_set '30'
		end
	end;
	dsc = function(s)
		p [[Ты находишься в огромном зале. В центре зала установлен трон. Все пространство зала залито светом, который отражается
от ледяных стен, пола, потолка и массивных колонн. У южной стены расположена широкая лестница, ведущая вниз. Выход из зала находится на востоке.]];
		if not disabled'дверь' then
			p [[Дверь в твою комнату находится в северной стене.]]
		end
	end;
	['out_to,e_to'] = 'ворота';
	u_to = function(s)
		if visited 'комната' then return 'дверь' end
		return false
	end;
}:with {
	obj {
		-"трон|кресло";
		nam = "#трон";
		['before_Enter,Climb'] = function(s)
			if seen 'королева' then
				p "Трон занят.";
			else
				p "Тебе не нужна власть. Тебе нужна мама.";
			end
		end;
		description = [[Великолепный трон сделан, как и всё вокруг, из льда. Высокая прямая спинка украшена причудливыми узорами.]];
		before_Walk = function(s)
			if _'Тронный зал'.near then
				return false
			end
			p [[Ты бежишь к трону. Твоё сердце от радости выпрыгивает из груди. Но что-то странное ты замечаешь в облике матери.
В нерешительности ты останавливаешься в нескольких шагах от неё.]]
			if _'браслет':hasnt 'worn' then
				DaemonStop'королева'
				walk 'badend2'
				return
			end
			_'Тронный зал'.near = true
		end;
	}:attr 'scenery,supporter';
	'королева';
	Prop { -"узоры|спинка|колонны|стены" };
	door {
		-"деревянная дверь|дверь";
		nam = 'дверь';
		description = function(s) p [[Небольшая деревянная дверь. Странно, что она сделана не из льда.]]; return false; end;
		door_to = function(s)
			if here() ^ 'комната' then
				return 'Тронный зал'
			else
				return 'комната';
			end
		end;
	}:disable():attr 'scenery';
	'ворота';
	obj {
		-"свет";
		before_Default = 'Как ты сделаешь это с светом?';
		before_Exam = 'Свет кажется тебе каким то бледным. Он не приносит радости.';
	}:attr 'scenery';
	obj {
		nam = '#лестница';
		['before_Enter,Walk,Climb'] = function(s)
			walk 'Зал с зеркалами';
		end;
		description = [[Широкая лестница начинается от южной стены и ведёт вниз.]];
	}:attr 'scenery';
}

dlg {
	nam = 'королева-диалог';
	title = false;
	phr = {
		[[-- Иди же и обними меня! -- глаза матери по прежнему закрыты и это пугает тебя.]];
		{
			'Почему твои глаза закрыты?',
			'-- Поцелуй меня и я открою их.',
			next = '#дальше';
		};
		{
			'Ты точно моя мама?',
			'-- Да, а ты моя дочь. Я так ждала тебя, иди и обними меня.',
			next = '#дальше';
		};
	};
	exit = function()
		p [[^Твоя мама махнула рукой голему и тот, с грохотом, направился к северной стене зала. Дойдя до неё он остановился.]];
	end;
}: with {
	{
		'#дальше';
		{

			'Я не верю тебе! Ты не моя мама!';
			'-- Ну зачем ты так? Ты стала такой грубой!';
			{
				'Хватит притворяться!';
				'-- Я твоя {$fmt em|другая} мама. Я буду любить тебя вечно. Поцелуй меня, дитя.';
			};
			{
				'Куда ты дела мою настоящую маму?';
				'-- Здесь нет другой мамы, кроме меня. Зачем ты упрямишься? У нас есть целая вечность, чтобы полюбить друг-друга.';
			};
			{
				'Открой свои... чёртовы глаза!';
				'-- Хорошо, как скажешь... -- женщина открыла глаза. На месте глаз ты видишь чёрные отверстия. Тебе кажется, что ты сходишь с ума.';
			};
			onempty = function(s)
				push '#дальше2'
			end;

		};
		{
			'Хорошо, сейчас.';
			function(s)
				walk 'badend'
			end;
		};
	};
	{
		'#дальше2';
		{
			'Я знаю, ты забрала мою маму! Сейчас же верни её!';
			[[-- Хорошо, дитя. Жаль, что тебе нужно время, чтобы привыкнуть ко мне. Но я подожду. Мой слуга проводит тебя в твою комнату.]];
			{
				[[Я всё равно сбегу и найду свою настоящую маму! Я знаю -- она где-то здесь!]];
				[[-- Глупышка, ты думаешь я тебя обманываю? Знай, ты свободна ходить туда, куда хочешь. И делать то, что хочешь. Можешь искать свою... {$fmt em|другую} маму. Но не отказывай мне, посмотри свою комнату. Отдохни. И приходи ко мне, когда забудешь о своих фантазиях.]];
				{
					[[А если я найду маму, ты нас отпустишь?]];
					[[-- Ты никогда не найдёшь её. Но хорошо, я обещаю. Только и ты пообещай мне, что если отчаешься найти её, то станешь моей дочерью.]];
					{
						[[Хорошо, обещаю.]];
						function(s)
							p [[-- Ну что же, чувствуй себя как дома. Дворец в твоём распоряжении.]];
							walkback'Тронный зал'
						end;
					};
					{
						[[Похоже, у меня нет выбора. Я в твоей власти? Мне не выбраться отсюда?]];
						function(s)
							p [[-- Хорошо, что мы поняли друг-друга. Дворец в твоём распоряжении.]];
							walkback 'Тронный зал'
						end
					}
				};
			}
		}
	}
}


cutscene {
	nam = 'badend';
	title = 'Конец';
	onenter = function()
		pic_push '99'
	end;
	exit = function()
		pic_pop()
	end;
	text = {
		[[Ты поднимаешься по ступенькам пьедестала и обнимаешь свою мать.^^
		От неё веет холодом, который сковывает тебя, но ты уже ничего не можешь изменить.^^
		Глаза Снежной Королевы открываются и ты смотришь в чёрную бездну...^^
		{$fmt b|{$fmt c|КОНЕЦ}}]];
		[[{$fmt r|{$fmt em|Но всё могло закончиться по другому...}}]];
	};
	next_to = 'королева-диалог';
}

cutscene {
	nam = 'badend2';
	onenter = function()
		pic_push '99'
	end;
	exit = function()
		pic_pop()
	end;
	title = false;
	text = {
		[[-- Не бойся меня, беззащитное дитя. Я вижу, что на тебе нет {$fmt em|её} талисмана. Это лучше для нас обеих, всё закончится быстро...^^
		И все сомнения вдруг уходят. Чувствуя в глубине ужас, ты поднимаешься по ступенькам пьедестала и обнимаешь свою мать.^^
		От неё веет холодом, который сковывает тебя, и ты уже ничего не можешь изменить.^^
		Ты смотришь внутрь черных дыр-глаз Снежной Королевы...^^
		{$fmt b|{$fmt c|КОНЕЦ}}]];
		[[{$fmt r|{$fmt em|Но всё могло закончиться по другому...}}]];
	};
	next_to = 'Тронный зал';
}

cutscene {
	nam = 'badend4';
	onenter = function()
		pic_push '99'
		disable 'королева'
	end;
	exit = function()
		pic_pop()
		enable 'королева'
	end;
	title = false;
	text = {
		[[-- Спасибо, дитя. Ты правильно сделала, что сама отдала мне {$fmt em|её} талисман. Это лучше для нас обеих, всё закончится быстро...^^
		И все сомнения вдруг уходят. Чувствуя в глубине ужас, ты поднимаешься по ступенькам пьедестала и обнимаешь свою мать.^^
		От неё веет холодом, который сковывает тебя, и ты уже ничего не можешь изменить.^^
		Ты смотришь внутрь черных дыр-глаз Снежной Королевы...^^
		{$fmt b|{$fmt c|КОНЕЦ}}]];
		[[{$fmt r|{$fmt em|Но всё могло закончиться по другому...}}]];
	};
	next_to = 'Тронный зал';
}

dlg {
	nam = 'сова2-диалог1';
	title = false;
	enter = function(s)
		pic_set '21'
	end;
	phr = {
		[[-- Я хочу помочь тебе, дитя. -- сказала странная птица.]];
		{
			'Как именно?',
			'-- Я покажу тебе путь отсюда.',
			{
				'Но я нашла свою маму. Правда, она застряла в зеркале... Ты можешь помочь?',
				'-- Глупое дитя. Ты так ничего и не поняла? Повесь зеркало на стену.';
			};
		};
	};
}

dlg {
	nam = 'сова2-диалог2';
	title = false;
	enter = function(s)
		pic_set '21'
	end;
	phr = {
		[[-- Итак, дитя, ты уже поняла, что твоя мама находится в нормальном мире? А ты -- за зеркалом?]];
		{
			'Да.',
			'-- Хорошо, это сэкономит нам время. Итак, чтобы вернуться в нормальный мир, ты должна войти в зеркало...',
			next = '#дальше';
		};
		{
			'Нет.',
			'-- Всё просто, ты находишься за зеркалом. Твоя мама -- в обычном мире. Чтобы вернуться домой ты должна войти в зеркало...',
			next = '#дальше';
		};
	};
}:with {
	{
		'#дальше';
		{
			'Просто войти в зеркало?';
			'-- Да. Но сначала, его нужно разморозить. И это могу сделать я. Для тебя.';
			{
				"Так сделай это!";
				"-- Я могу это сделать. Но для этого, мне нужны глаза.";
				next = "#дальше2";
			};
			{
				"Что ты хочешь взамен?";
				"-- Мне нужны глаза.";
				next = "#дальше2";
			}
		};
		{
			'Но я нашла свою маму. Значит, мы свободны!';
			'-- Снежная Королева всё равно не отпустит тебя, дитя. Но я могу тебе помочь.';
		};
		{
			'Зачем ты помогаешь мне?',
			'-- Я хочу стать свободной, мне надоело служить госпоже.',
		};
	};

	{
		'#дальше2';
		{
			'Глаза?';
			'-- Да. Существа, подобные мне, не могут даже коснуться зеркала. Но с настоящими глазами...';
			{
				'И где же я найду глаза?';
				'-- У тебя есть глаза. В этом месте ты единственная, у кого они есть. Отдай их мне!';
				{
					'Нет!';
					function(s)
						p '-- Я возьму их не надолго. Больно не будет. Тебе просто нужно согласиться. И помни. Я одна могу помочь тебе вернуться домой и увидеть маму. Так "да", или "нет"?';
						push '#данет'
					end;

				};
				{
					'#данет';
					'Хорошо.';
					'-- Мне нужен ответ. Да или нет?';
					{
						'Да.';
						function(s)
							walk 'yes'
						end;

					};
					{
						'Нет!';
						function(s)
							p [[-- Ну что же. Я подожду, если ты передумаешь...]]
							walkout()
						end;
					}
				}
			}
		}
	}
}
dlg {
	nam = 'сова2-диалог3';
	title = false;
	enter = function(s)
		pic_set '21'
	end;
	phr = {
		[[-- Итак, дитя, что ты решила? Ты отдашь мне свои глаза?]];
		{
			'Да.';
			function()
				walk 'yes'
			end;

		};
		{
			'Нет!';
			function(s)
				p [[-- Ну что же. Я подожду, если ты передумаешь...]]
				walkout()
			end;
		}
	};
}

obj {
	-"полярная сова,сова,птица";
	nam = 'сова2';
	num = 0;
	finside = false;
	description = [[Похоже, это та самая сова, которая привела тебя в это место. Ты боишься смотреть в её чёрные глаза.]];
	talk_to = function(s)
		if not s.finside then
			p [[Она за стеклом.]]
			return
		end
		if visited 'сова2-диалог1' and not where'зеркало' ^ '#стена' then
			p [[-- Повесь зеркало на стену, дитя. Скорее!]]
			return
		end
		if not visited 'сова2-диалог1' and not where'зеркало' ^'#стена' then
			return 'сова2-диалог1'
		end
		if not visited 'сова2-диалог2' then
			return 'сова2-диалог2'
		end
		return 'сова2-диалог3'
	end;
	daemon = function(s)
		s.num = s.num + 1
		if s.num < 3 then
			return
		end
		if _'#окно':hasnt 'open' then
			p [[Ты слышишь стук в окно.]]
		else
			p [[Ты видишь, как в открытое окно влетает полярная сова и садится прямо на стол.]]
			s:daemonStop()
			s.finside = true
			move(s, '#стол')
			s:attr'~scenery'
		end
	end;
} : with {
	obj {
		-"глаза совы,глаза,дыр*";
		nam = '#глаза совы';
		before_Exam = function(s)
			p [[На месте глаз у совы зияют чёрные дырки.]];
		end;
		before_Default = [[Тебе не нравятся эти глаза.]];
	}
 }:attr'scenery,animate';

room {
	-"комната";
	nam = 'комната';
	onexit = function(s, t)
		if seen 'королева2' and not t ^ 'комната2' then
			p [[Если переход в зеркале закроется, ты никогда не вернёшься домой. Надо спешить!]]
			return false
		end
	end;
	exit = function(s)
		DaemonStop 'сова2'
		if not _'сова2'.finside then
			remove 'сова2'
		end
	end;
	enter = function(s)
		if s:once() then
			p [[За дверью оказалась лестница, которая вела наверх. Ты поднялась по ней и оказалась в ... своей комнате.]];
			move('голем', 'У замка')
		end
		if visited 'gotmirror' and _'зеркало'.seen and not _'сова2'.finside  then
			_'сова2'.num = 0
			DaemonStart 'сова2'
		end
	end;
	dsc = function(s)
		p [[Это действительно твоя комната. Комната, которую ты покинула ещё совсем недавно. Перед тем... как вы уехали с мамой...^^
Ты видишь те же: стол, шкаф, кровать и книжные полки... И даже окно!]];
		if not visited 'gotmirror' then
			p [[Правда, мебель стоит неправильно и на стене нет зеркала. Интересно, куда оно подевалось?]];
		else
			p [[Правда, мебель стоит неправильно.]]
			if where 'зеркало' ^ '#стена' then
				p [[На стене висит зеркало.]]
			end
		end
		if seen 'королева2' then
			p [[^^В комнате, прислонившись к стене, стоит Снежная Королева. Ты видишь как поверхность зеркала мерцает фиолетовым светом.]]
		end
		if where 'сова2' and where 'сова2' ^ '#стол' then
			p [[^^Полярная сова по прежнему сидит на твоём столе.]]
		end
	end;
	['s_to,out_to']= 'дверь';
}:with {
	'дверь';
	obj {
		-"книжные полки/жр,мн|полки/мн,жр|полка/жр";
		description = function(s)
			p "Полки висят на стене прямо над столом."
			if where'сказки' == s and disabled 'сказки' then
				p [[Они завалены школьными учебниками и тетрадками.]];
				p [[^Ты видишь на одной из полок сказки Андерсена. Ты узнала книгу по голубому цвету обложки и золотым буквам на корешке.]];
				enable 'сказки'
				return
			end
			return false
		end;
	}:attr'scenery,supporter':with{
		Useless {
			-"учебники";
		};
		Useless {
			-"тетрадки";
		};
		obj {
			-"сказки/мн|книга";
			nam = 'сказки';
			['before_Consult,Search,Open,Exam'] = function(s)
				if not have(s) then
					p [[Сначала книгу нужно взять.]]
					return
				end
				if s:once() then
					pn [[Ты открыла книгу на случайной странице. Буквы были знакомыми, но текст не читался.
Не сразу, но все-таки ты сообразила, что слова написаны наоборот. С трудом ты прочитала следующее:^]];
				end
				p [[{$fmt em|Стенами чертогам были вьюги, окнами и дверями буйные ветры. Сто с лишним зал тянулись здесь одна за другой так, как наметала их вьюга. Все они освещались северным сиянием, и самая большая простиралась на много-много миль. Как холодно, как пустынно было в этих белых, ярко сверкающих чертогах!}]];
				p [[^^Как странно...]]
			end
		}:attr 'openable':disable();
	};
	obj {
		-"стол";
		nam = '#стол';
		description = function(s) p [[За этим столом ты обычно делаешь... делала уроки.]]; return false; end;
		['before_Push,Pull,Transfer'] = [[Пусть стоит там, где ему место.]];
	}:attr 'scenery,supporter';
	obj {
		-"шкаф";
		title = "В шкафу";
		inside_dsc = [[Ты находишься внутри шкафа.]];
		['before_Push,Pull,Transfer'] = [[Пусть стоит там, где ему место.]];
		description = function(s)
			p [[Платяной шкаф с твоей одеждой.]]
			if s:has'open' then
				p [[Шкаф открыт.]]
			end
			return false
		end;
		obj = {
			Useless {
				-"одежда";
			};
		}
	}:attr 'scenery,openable,container,enterable';
	obj {
		-"кровать";
		before_Enter = "Хотя ты валишься с ног, ещё не время спать.";
		['before_Push,Pull,Transfer'] = [[Пусть стоит там, где ей место.]];
	}:attr 'enterable,supporter,scenery';
	obj {
		-"окно";
		nam = '#окно';
		when_open = [[Окно открыто. В твою комнату залетают колючие снежинки.]];
		description = function(s)
			p [[В окне ты видишь пустынный белый пейзаж.]];
			if _'сова2'.num >= 3 and not _'сова2'.finside then
				p [[Ты видишь за окном полярную сову.]]
				move('сова2', here())
			end
			return false
		end;
		before_Enter = [[Это слишком опасно.]];
	}:attr'scenery,openable';
	Prop {
		nam = '#стена';
		-"стена|шуруп";
		before_Exam = function(s)
			if where 'зеркало' ~= s then
				p [[На стене у шкафа висело зеркало. Сейчас его нет.]]
			else
				p [[На стене висит зеркало.]]
			end
		end;
	};
	Prop {
		-"стены|потолок|пол|снежинки";
	};
	Prop {
		-"мебель";
		before_Exam = [[Здесь есть: стол, кровать, шкаф и полки.]];
	};
}

room {
	-"зал";
	nam = 'Зал с зеркалами';
	u_to = 'Тронный зал';
	know = false;
	o_to = '#лестница';
	e_to = function(s)
		if not s.know then
			return false
		end
		p [[Ты решила осмотреть восточное направление. Ведь именно туда дула метель. Ты долго шла на восток, сверяясь с компасом и вглядываясь в бесконечную
череду зеркал, но так ничего и не обнаружила. Разочарованная, ты вернулась к лестнице.]]
	end;
	w_to = function(s)
		if not s.know then
			return false
		end
		return 'портал1'
	end;
	daemon = function(s)
		if rnd(100) < 25 then
			local t = {
				[[Ты чувствуешь на своём лице дуновение холодного ветра.]];
				[[Рой маленьких колких снежинок ударяется в щёки.]];
				[[Снежинки снова и снова ударяются о твоё лицо.]];
				[[Небольшая метель метёт тебе прямо в глаза.]];
			}
			p(t[rnd(#t)])
		end
	end;
	['before_Drop,ThrowAt'] = function(s, w)
		if not w ^ 'перо' then
			return false
		end
		if mp:check_held(w) then
			return
		end
		if s.know then
			p [[Ты снова выпускаешь перо из рук и убеждаешься ещё раз, что метель дует с запада.]];
		else
			p [[Ты выпускаешь перо из рук и видишь, как оно улетает строго на восток. Это значит, что метель дует с запада.]];
		end
		move(w, s)
		s.know = true
	end;
	d_to = function(s)
		p [[Интересно, есть ли другие лестницы ведущие ещё глубже?]];
	end;
	cant_go = function(s)
		p [[Ты можешь плутать по залу вечность. Ты раздавлена его масштабами и не видишь смысла блуждать между зеркалами в поисках чего-либо, кроме пустоты.]]
	end;
	enter = function(s, f)
		if f ^ 'Тронный зал' then
			p [[Это была очень длинная лестница без перил. Закручиваясь спиралью вокруг массивной колонны, она вела глубоко вниз.^
Опасный и долгий спуск по скользким ступенькам занял продолжительное время и открыл твоему взору грандиозный вид.]]
		end
		s:daemonStart();
	end;
	exit = function(s, t)
		if t ^ 'Тронный зал' then
			p [[Не без труда преодолевая скользкие ступени, ты покидаешь громадный зал.]];
		end
		s:daemonStop()
	end;
	dsc = [[Ты находишься в громадном зале. Ты даже боишься представить его размеры. Километры ледяных стен подсвеченные всполохами полярных сияний.
Высокие колонны пронзают пространство зала. Куда хватает взгляда ты видишь, что зал заполнен зеркалами. По залу кружатся мелкие колючие снежинки.^^
Здесь есть спиральная лестница, ведущая наверх.]];
}: with {
	obj {
		-"лестница";
		nam = '#лестница';
		['before_Enter,Walk,Climb'] = function(s)
			walk 'Тронный зал';
		end;
		description = [[Широкая лестница без перил, закрученная спиралью вокруг массивной колонны, ведёт наверх -- к тронному залу.]];
	}:attr 'scenery';
	obj {
		-"колонны";
		description = "Ты думаешь, что высота колонн может достигать пятидесяти метров.";
	}:attr'scenery';
	obj {
		-"колонна";
		description = "Ледяная колонна уходит вертикально вверх. Ты думаешь, что высота колонны может достигать пятидесяти метров.";
	}:attr'scenery';
	obj {
		-"потолок|потолки";
		description = "Потолок подсвечивается всполохами, похожими на полярное сияние.";
	}:attr'scenery';
	obj {
		-"пол|поверхность";
		description = "Поверхность пола -- абсолютно гладкая ледяная поверхность.";
	}:attr'scenery';
	obj {
		-"стены|стена";
		description = "Километры стен подсвечиваются всполохами, похожими на полярное сияние.";
	}:attr'scenery';
	obj {
		-"зеркала|зеркало";
		description = [[Зеркала повсюду. Они разной формы, разного размера. Они висят на колоннах, вморожены в глыбы льда, закреплены на фрагментах стен.
Ты даже боишься представить сколько их может быть здесь, в этом громадном зале.]];
		before_Search = function(s)
			p [[Ты подошла к одному из зеркал и заглянула в него. Странно, но вместо своего отражения ты видишь нечто другое....^^]]
			local t = {
				[[Небольшая комната. В ней ты видишь мужчину и женщину. У обоих раздражение на лице. В комнате ты видишь детскую кроватку.]];
				[[Ванная комната. Мужчина лет 40 бреется. Уголки губ опущены вниз.]];
				[[Помещение, напоминающее школьный класс. Сейчас он пуст. Только молодая учительница сидит за столом. Рядом с ней -- стопка тетрадей.]];
				[[Большой зал торгового центра. Ты видишь магазин с одеждой, заполненный посетителями.]];
				[[Аптека. Полки с лекарствами. Ты видишь провизора в белом халате. Это пожилая женщина.]];
				[[Спортивный зал. Натянута сетка. Дети играют в волейбол.]];
				[[Танцевальный зал. Много молодых людей и девушка - инструктор.]];
				[[Тёмная комната завалена хламом и пустыми бутылками. На диване лежит мужчина.]];
				[[За поверхностью зеркала -- темнота.]];
				[[Салон легковой машины. На заднем сидении сидит мальчик с грустными глазами.]];
				[[Мужской туалет. Все писсуары свободны.]];
			}
			pn(t[rnd(#t)])
			p [[Изображение в зеркале статично. Словно кто-то сделал стоп-кадр. Ты отходишь от зеркала.]]
		end;
		before_Take = [[Зачем тебе это?]];
		before_Attack = [[Ты не разобьешь их всех.]];
		before_Touch = [[Ты коснулась одного из зеркал. Холодное.]];
		['before_Push,Pull,Transfer'] = [[Стоит ли это делать?]];
	}:attr 'scenery';
	obj {
		-"снежинки|метель|ветер";
		description = [[Интересно, откуда здесь снег? Странно, но тебе кажется, что метель дует с определённого направления...]];
		before_Listen = [[Тихо...]];
	}:attr'scenery';
	obj {
		-"всполохи|сияние";
		description = [[Это похоже на полярное сияние. Правда, ты никогда не видела полярное сияние по-настоящему...]];
	}:attr'scenery';
}

cutscene {
	title = false;
	nam = 'портал1';
	text = {[[Ты решаешь осмотреть западное направление. Ведь именно оттуда дует метель и эта загадка требует ответа.^^
		Ты идёшь на запад, сверяясь с компасом и вглядываясь в бесконечные зеркала. Сила ветра всё возрастает.^^
		Идти становится всё труднее и ты почти отчаялась, когда вдруг, ты замечаешь впереди нечто странное...]];
	};
	next_to = 'ледяное-пламя';
}

room {
	title = "У ледяного огня";
	nam = 'ледяное-пламя';
	['out_to,e_to'] = 'Зал с зеркалами';
	warm = 0;
	cant_go = [[Ты можешь плутать по залу вечность. Ты раздавлена его масштабами и не видишь смысла искать здесь что-нибудь кроме пустоты.]];
	enter = function(s)
		s.warm = 0
		s:daemonStart()
	end;
	exit = function(s)
		s:daemonStop()
	end;
	after_Disrobe = function(s, w)
		if w ^ 'браслет' then
			s.warm = 0
		end
		return false
	end;
	daemon = function(s)
		if _'браслет':has'worn' then
			s.warm = s.warm + 1
			if s.warm == 3 then
				p [[Ты чувствуешь, как браслет согревает твою руку.]]
			elseif s.warm == 4 then
				p [[Ты чувствуешь, как от браслета на твоей руке по телу начинает разливаться тепло.]]
			elseif s.warm == 5 then
				p [[Ты чувствуешь, как от браслета на твоей руке по телу разливается тепло.]]
			elseif s.warm > 5 then
				p [[Ты чувствуешь, как браслет согревает тебя.]]
			end
		end
	end;
	dsc = function(s)
		p [[Ты видишь перед собой мерцающее свечение. Словно пламя огромного фиолетового огня, пучки сияния вырываются из постамента
и уходят высоко вверх. Переплетаясь между собой, языки странного пламени не греют.]]
		if s.warm <= 5 then
			p [[Наоборот, ты чувствуешь сильный всепроникающий холод.^^]]
		else
			p [[Наоборот, они излучают пронзительный холод. К счастью, ты чувствуешь как браслет защищает тебя от него.^^]]
		end
		p [[Ты пришла сюда с востока.]];
	end;
}:with {
	obj {
		nam = '#постамент';
		-"постамент";
		description = function(s)
			p [[Массивный постамент представляет из себя ледяную глыбу квадратной формы.]];
			return false
		end;
		['before_Enter,Climb'] = function(s)
			mp:xaction("Enter", _'#пламя')
		end;
	}:attr 'scenery,supporter,enterable':with{
		obj {
			nam = '#пламя';
			-"сияние|пламя|огонь|свечение";
			dsc = [[На постаменте пылает ледяное пламя.]];
			before_Take = [[Это невозможно взять.]];
			before_Default = function(s, ev, w)
				if ev == 'ThrownAt' or ev == 'Receive' then
					p ([[Тебе жаль расставаться с ]], w:noun'тв', '. Ведь ты не сможешь забрать ', w:it'вн', ' назад.')
				else
					p [[Как ты сделаешь это?]];
				end
			end;
			before_Listen = [[Ты слышишь потрескивание.]];
			before_Touch = function(s)
				if here().warm <= 5 then
					p [[Твоя рука моментально начинает замерзать. Лучше не пытаться это делать.]]
				else
					p [[Ты чувствуешь прохладу.]]
				end
			end;
			before_Exam = [[Языки странного огня излучают холод.]];
			before_Enter = function(s)
				if visited 'gotmirror' then
					p [[Ты уже взяла то, что тебе было нужно.]]
					return
				end
				if here().warm <= 5 then
					walk 'badend3'
				else
					walk 'gotmirror'
				end
			end;
		};
	};
}

cutscene {
	nam = 'badend3';
	title = 'Конец';
	onenter = function()
		pic_push '99'
	end;
	exit = function()
		pic_pop()
	end;
	text = {
		[[Превозмогая холод, ты поднимаешься на пьедестал и входишь в ледяное пламя.^^
		Непонятно, на какое чудо ты надеялась? Ледяное пламя охватывает тебя.^^
		Ты успеваешь заметит, как твое тело превращается в лёд...^^
		{$fmt b|{$fmt c|КОНЕЦ}}]];
		[[{$fmt r|{$fmt em|Но всё могло закончиться по другому...}}]];
	};
	next_to = 'ледяное-пламя';
}

obj {
	-"зеркало";
	nam = 'зеркало';
	seen = false;
	description = function(s)
		p [[Небольшое овальное зеркало.]];
		if seen 'королева2' then
			p [[Поверхность зеркала сияет фиолетовым светом.]]
		end
	end;
	before_Search = function(s)
		if here() ^ 'комната' and not _'сова2'.finside and not s.seen then
			_'сова2'.num = 0
			DaemonStart 'сова2'
		end
		s.seen = true
		p [[Вместо своего отражения, ты видишь в зеркале свою маму! {$fmt em|Настоящую} маму.]];
		if s:where() ^ '#стена' then
			p [[Ты видишь в зеркале комнату. Все вещи в ней находятся на своих местах.]]
		end
		if seen 'королева2' then
			p [[Поверхность зеркала сияет фиолетовым светом.]]
		end
	end;
	before_Touch = function(s)
		if seen 'королева2' then
			p [[Твоя рука свободно проходит сквозь поверхность зеркала.]]
		else
			p [[Какое оно холодное...]]
		end
	end;
	before_Take = function(s)
		if seen 'королева2' then
			p [[Лучше как можно быстрее бежать отсюда!]]
			return
		end
		p [[Ты забираешь зеркало.]]
		move(s, pl)
	end;
	before_PutOn = function(s, w)
		if mp:check_held(s) then
			return
		end
		if w ^ '#стена' and here() ^ 'комната' then
			move(s, w)
			p [[Ты нашла в стене одинокий шуруп и повесила на него зеркало.]]
			return
		end
		return false
	end;
	before_Attack = function(s)
		if s.seen then
			p [[Там твоя мама!]]
		else
			p [[Зачем разбивать зеркало, которое ты так долго искала?]]
		end
	end;
	before_Enter = function(s)
		if seen 'королева2' then
			walk 'комната2'
		else
			return false
		end
	end;
}

cutscene {
	nam = 'gotmirror';
	title = false;
	text = {
		[[Ты входишь в ледяное пламя и странное свечение окутывает тебя со всех сторон.^^
		Ничто живое не смогло бы пережить этот холод, но ты чувствуешь, как тебя согревает браслет матери.^^
		Ты вглядываешься в фиолетовые языки ледяного пламени и вдруг замечаешь, что можешь охватить взором весь этот громадный зал.^^
		Сотни тысяч зеркал, среди которых есть то, что ты ищешь...^^
		Ты протягиваешь руки и вот -- ты уже держишь его! Зеркало из твоей комнаты. Ты выходишь из ледяного пламени.]];
	};
	exit = function(s)
		take 'зеркало'
		remove 'королева'
	end;
	next_to = 'ледяное-пламя';
}

cutscene {
	nam = 'happyend';
	title = "Конец";
	onenter = function(s)
		pic_set '31'
	end;
	exit = function(s)
		pic_set '81'
	end;
	text = {
		[[-- Ты что -- совсем рехнулась?]];
		[[... Что ты устраиваешь?]];
		[[... Я понимаю, ты не хочешь этого переезда, но надо держать себя в руках!]];
		[[... Определённо, тебя надо показать психологу!]];
		[[... Ты бы видела себя! Ты же способна сделать что угодно!]];
		[[-- Всё хорошо, мама. Я собрала вещи мы можем ехать.]];
		[[-- Что?]];
		[[-- Всё хорошо. У нас теперь всё будет хо-ро-шо!...]];
	};
	next_to = 'titles';
}


cutscene {
	nam = 'yes';
	title = false;
	text = {
		[[Звук твоих слов еще отражался от стен комнаты, когда ты услышала смех {$fmt em|другой} мамы.]];
		[[-- Как просто! Тебе так и не помог {$fmt em|её} талисман! Теперь я свободна!]];
		[[Ты снова услышала её дьявольский смех. А потом наступила тьма...]];
	};
	next_to = 'Тьма';
}

room {
	nam = 'Тьма';
	num = 0;
	before_Default = [[Отчаяние захватило тебя. Всё, что ты можешь делать это думать и плакать.]];
	before_Think = [[Ты думаешь, что навсегда останешься здесь. Мама! Забери меня отсюда!]];
	before_Wait = [[Проходит немного времени.]];
	before_Play = function(s, w)
		if not w then
			w = _'скрипка'
		end
		if not w ^ 'скрипка' then
			return false
		end
		if not instead.tiny then
			snd.music ('mus/violin.ogg', 1)
		end
		walk 'cry2'
	end;
	before_Cry = function(s)
		s.num = s.num + 1
		if s.num < 5 or have 'скрипка' then
			p [[Тебя душат рыдания.]];
			if s.num == 1 then
				p [[Но у тебя нет глаз, чтобы плакать.]]
			elseif s.num == 2 then
				p [[Отчаяние захватило тебя.]]
			elseif s.num == 3 then
				p [[Но можно ли плакать без глаз?]]
			else
				p [[Ты едва сдерживаешься.]]
				if have 'скрипка' then
					p [[Ты чувствуешь в своих руках скрипку.]]
				end
			end
		else
			walk 'cry'
		end
	end;
}:attr '~light';

cutscene {
	nam = 'cry2';
	title = false;
	text = {
		[[Ты берёшь в руки скрипку и извлекаешь первые ноты.^^
		Комната наполнятся звуками.^^
		Отчаяние всё ещё душит тебя. Но постепенно под натиском музыки оно отступает.^^
		Ты чувствуешь как музыка проникает сквозь стены, уносится вверх, спускается глубоко вниз. В самые глубины ледяного замка, в каждый его уголок...^^
		"Дрянь! Дрянь! Дрянь!" -- раздаётся искорёженный ненавистью голос.^^
		"Дрянная девчонка!" -- это {$fmt em|её} голос.]];
		[[{$fmt b|{$fmt c|ВСПЫШКА}}]];
	};
	exit = function()
		remove 'сова2'
		move('королева2', 'комната')
		_'королева2'.violin = true
		_'зеркало':attr'enterable'
	end;
	next_to = 'комната';
}

cutscene {
	nam = 'cry';
	title = false;
	text = {
		[[Наконец, рыдания прорываются наружу и ты плачешь. Несмотря на то, что у тебя нет глаз, ты чувствуешь как по лицу текут тёплые слёзы.^^
		"Дрянь! Дрянь! Дрянь!" -- раздаётся искорёженный ненавистью голос.^^
		"Дрянная девчонка!" -- это {$fmt em|её} голос.]];
		[[{$fmt b|{$fmt c|ВСПЫШКА}}]];
	};
	exit = function()
		remove 'сова2'
		move('королева2', 'комната')
		_'зеркало':attr'enterable'
	end;
	next_to = 'комната';
}

obj {
	nam = 'королева2';
	-"Снежная Королева|королева|женщина|другая мама";
	violin = false;
	before_Exam = function(s)
		if s.violin then
			p [[Она закрывает уши руками. Ты видишь под её ладонями кровь.]];
		else
			p [[Она закрывает лицо руками. Ты видишь под её ладонями кровь.]];
		end
	end;
	before_Default = [[Лучше держаться от неё подальше.]];
	each_turn = function(s)
		local t = {
			"-- Дрянь! -- шипит Снежная Королева.";
			"Снежная Королева стонет.";
			"-- Я до тебя доберусь! -- произносит Снежная Королева.";
		}
		p (t[rnd(#t)])
	end;
}:attr 'scenery';

obj {
	-"мама|мать";
	nam = 'мама2';
	init_dsc = [[В комнате находится твоя мама. Немой вопрос застыл на её губах.]];
	description = [[Это твоя мама. Милая, родная мама!]];
	['before_Touch,Kiss'] = [[Ты бросаешься маме на шею и обнимаешь её.^
-- Мамочка!]];
	talk_to = function(s)
		if seen 'зеркало2' then
			p [[Сначала нужно завершить кое-какое дело.]];
		else
			walk 'happyend'
		end
	end;
}:attr 'animate';

obj {
	-"зеркало";
	nam = 'зеркало2';
	before_Search = [[Тебе кажется, что ты видишь за зеркалом Снежную Королеву!]];
	init_dsc = "На стене висит зеркало.";
	description = [[Ты видишь, что поверхность зеркала имеет фиолетовый оттенок.]];
	['before_Attack,Take,Remove'] = function(s)
		p [[Ты берёшь зеркало в руки и с размаху бросаешь на пол. Сотни мелких осколков разлетаются по всей комнате.^^
-- Что, черт возьми, ты себе позволяешь? -- слышишь ты, наконец, голос мамы.]];
		remove(s)
	end;
};

room {
	nam = 'комната2';
	title = 'Комната';
	out_to = function()
		p 'Сначала нужно завершить кое-какое дело.';
	end;
	enter = function(s)
		pn [[Ты бросаешься к зеркалу понимая, что это твой последний шанс на спасение.]]
		p [[Фиолетовое свечение заполняет всё и ты оказываешься... В своей комнате.]];
	end;
	dsc = [[Ты находишься в своей настоящей комнате. Все вещи находятся там, где и должны быть.]];
}: with {
	Prop {
		-"вещи|кровать|стол|стул|шкаф|стена|осколки";
	};
	'зеркало2';
	'мама2';
}

Verb {
	"#LookIn",
	"смотреть",
	"в|во {noun}/вн : Search",
}

Verb {
	"#Sit",
	"сесть",
	"на {noun}/вн : Enter",
}

if false then
global 'hint_num' (5)
function use_hint()
end
function mp:before_Think()
	if here() ^ 'Тьма' then
		return false
	end
	if here() ^ 'В машине' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]];
		if not visited'разговор1' then
			p [[поговорить с матерью.]]
		elseif not _'телефон'.seen then
			p [[смотреть в телефон.]]
		elseif have 'телефон' then
			p [[отдать телефон матери.]]
		elseif blizzard == 0 then
			p [[смотреть в окно.]]
		elseif blizzard == 1 then
			p [[поговорить с матерью.]]
		elseif blizzard < 11 then
			p [[ждать.]]
		else
			p [[выйти из машины.]]
		end
		return
	end
	if here() ^ 'поле' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]];
		if not have 'телефон' or not have 'браслет' then
			p [[осмотреть машину.]]
			if not _'бардачок':has'open' then
				p [[Затем открыть бардачок.]]
			else
				p [[взять всё из бардачка.]]
			end
		elseif not have 'скрипка' then
			p [[взять скрипку.]]
		elseif not _'телефон'.compass then
			p [[посмотреть в телефон. В нём есть компас.]]
		elseif not _'сова'.talked then
			if not seen 'сова' then
				p [[идти в лес.]]
			else
				if _'сова'.seen then
					p [[поговорить с совой.]]
				else
					p [[осмотреть сову.]]
				end
			end
		elseif not have 'перо' then
			p [[взять перо.]]
		else
			p [[идти в лес.]]
		end
		return
	end
	if here() ^ 'В лесу' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]];
		if not _'сова'.talked then
			if where'сова' ^ 'В лесу' then
				p [[ждать.]];
			else
				p [[идти на восток.]];
			end
		elseif not seen 'олень' or disabled 'олень' then
			p [[идти на запад.]]
		elseif not _'олень'.sit then
			p [[дать оленю перо.]]
		else
			p [[сесть на оленя.]]
		end
		return
	end
	if here() ^ 'Ледяные горы' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if _'#стена'.light == 0 then
			p [[дотронуться стены.]]
		else
			p [[войти в свечение.]]
		end
		return
	end
	if here() ^ 'пещера' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if mp:thedark() then
			p [[посветить телефоном.]]
		elseif disabled '#кристаллы' then
			p [[осмотреть свечение.]]
		elseif _'#кристаллы'.try < 2 then
			p [[постучать по кристаллам.]]
		elseif not _'#кристаллы'.broken then
			p [[играть на скрипке.]]
		elseif seen 'осколки' then
			p [[взять осколки.]]
		else
			p [[идти на северо-запад.]]
		end
		return
	end
	if here() ^ 'пещера2' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if not seen 'осколки' then
			if not have'осколки' then
				p [[идти на юго-восток.]]
			else
				p [[бросить осколки.]]
			end
		elseif mp:thedark() then
			p [[включить фонарик.]]
		else
			p [[идти на юго-запад.]]
		end
		return
	end
	if here() ^ 'обрыв' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову перепрыгнуть через обрыв.]]
		return
	end
	if here() ^ 'Другая сторона' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову выйти наружу.]]
		return
	end
	if here() ^ 'За ледяной стеной' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову идти к скале.]]
		return
	end
	if here() ^ 'У замка' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if disabled 'ворота' then
			p [[дать перо статуе.]]
		else
			p [[войти внутрь.]]
		end
		return
	end
	if here() ^ 'Тронный зал' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if visited 'gotmirror' and not _'зеркало'.seen then
			p [[посмотреть в зеркало.]]
		elseif _'браслет':hasnt'worn' then
			p [[надеть браслет.]]
		elseif not _'Тронный зал'.near then
			p [[подойти к матери.]]
		elseif not _'королева'.queen then
			p [[осмотреть мать.]]
		elseif not visited 'королева-диалог' then
			p [[поговорить с матерью.]]
		elseif disabled 'дверь' then
			p [[идти к голему.]]
		elseif not visited 'gotmirror' then
			p [[идти вниз.]]
		elseif _'дверь':has'open' then
			p [[идти в дверь.]]
		else
			p [[открыть дверь.]]
		end
		return
	end
	if here() ^ 'Зал с зеркалами' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if not _'Зал с зеркалами'.know then
			p [[бросить перо.]]
		elseif not have 'перо' then
			p [[взять перо.]]
		elseif visited 'gotmirror' then
			p [[идти наверх.]]
		else
			p [[идти на запад.]]
		end
		return
	end
	if here() ^ 'ледяное-пламя' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if visited 'gotmirror' then
			if not _'зеркало'.seen then
				p [[посмотреть в зеркало.]]
			else
				p [[идти на восток.]]
			end
		elseif _'ледяное-пламя'.warm <= 5 then
			p [[ждать.]]
		else
			p [[войти в пламя.]]
		end
		return
	end
	if here() ^ 'комната' then
		if use_hint() then
			return
		end
		p [[Тебе приходит в голову ]]
		if seen 'королева2' then
			p [[войти в зеркало.]]
			return
		end
		if not seen 'зеркало' and not have 'зеркало' then
			if not visited 'gotmirror' then
				p [[выйти из комнаты.]]
			else
				p [[идти и забрать зеркало оттуда, где ты его оставила.]]
			end
		elseif not _'зеркало'.seen then
			p [[Посмотреть в зеркало.]]
		elseif not _'сова2'.finside and _'сова2'.num < 3 then
			p [[ждать.]]
		elseif _'#окно':hasnt'open' and not _'сова2'.finside then
			p [[открыть окно.]]
		elseif not visited 'сова2-диалог1' and not visited 'сова2-диалог1' then
			p [[поговорить с совой.]]
		elseif not _'зеркало':where() ^ '#стена' then
			p [[повесить зеркало на стену.]]
		else
			p [[поговорить с совой.]]
		end
		return
	end
	if here() ^ 'Тьма' then
		return false
	end
	return false
end
end

function mp:Sing()
	p [[То, что ты учишься в музыкальной школе не означает, что ты хорошо поёшь.]]
end

function mp:Ring()
	if not have 'телефон' then
		p [[У тебя нет телефона.]]
		return
	end
	if seen '#мама' then
		p [[Тебе сейчас некому звонить.]]
		return
	end
	if _'телефон'.compass then
		p [[Нет приёма.]]
		return
	end
	p [[Странно, нет приёма.]]
end
Verb {
	"#Ring",
	"[|по]звон/ить",
	"Ring",
}

Verb {
	"#SwitchOn2",
	"завести/,завед/и",
	"~ {noun}/вн :SwitchOn",
}

Verb {
	"#WalkThrough",
	"идти,иди",
	"~ сквозь {noun}/вн,scene :Enter",
}

Verb {
	"#Give",
	"дать,отда/ть,предло/жить,предла/гать,дам,даю,дадим",
	"{noun}/вн,held {noun}/дт,scene : Give",
	"~ {noun}/дт,scene {noun}/вн,held : Give reverse",
}

game.hint_verbs = { "#Exam", "#Drop", "#LookIn", "#ThrowAt", "#Walk", "#Take", "#Play", "#Give", "#Touch", "#Attack2", "#Talk", "#Cry", "#Open", "#Close", "#Jump", "#Wait", "#Wear", "#Sit", "#Exit", "#SwitchOn", "#SwtchOff", "#PutOn", "#Light" }
