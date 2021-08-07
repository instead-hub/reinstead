--$Name:Судный день$
--$Version:0.1
--$Author:Пётр Косых$
--$Info:Нано-игра на Инстедоз-6$

require "fmt"
fmt.dash = true
fmt.quotes = true

require 'parser/mp-ru'
pl.description = [[Ты -- астронавт в скафандре.]];

local DH_TO = 2

function game:before_Walk(w)
	local dir = mp:compass_dir(w)
	if not dir then
		return false
	end
	if dir == 'in_to' or dir == 'out_to' then
		return false
	end
	p [[Стороны света есть на Земле, а не в космосе.]]
end

cutscene {
	nam = 'main';
	title = false;
	text = {
		[[{$fmt c|***}^^Корпус корабля лопнул и его содержимое, в виде сотен блестящих на Солнце осколков, хлынуло в открытый космос.
Всё произошло за один миг. Всего лишь пол секунды -- и сложный, отлаженный механизм превратился в облако космического мусора...^^
		Одним из сверкающих осколков был ты. Белый скафандр отлично отражал лучи, делая тебя яркой светящейся точкой в чёрной пустоте.^^
		Вращаясь, ты медленно плыл в темноте...]];

	};
	next_to = 'space';
}

function init()
	take 'suit'
end;

global 'known' (false)
local channels = {
	{ "Ты слышишь по радио классическую музыку." };
	{ "-- Конечно, вероятность того, что мы одиноки во вселенной -- есть, но...",
	  "-- Но вы в это не верите?", "-- Категорически отказываюсь в это верить!",
	  "-- Но почему тогда мы не слышим их сигналов?", "-- Да, парадокс Ферми вызывает вопросы, но вот, что я вам скажу..."};
	{ "Ты слышишь по радио французскую речь." };
	{ "Ты слышишь по радио джаз." };
	{ "Ты слышишь по радио передачу новостей." };
	{ "Ты слушаешь по радио политические дебаты." };
	{ "Ты слышишь радиопомехи." };

}

pl.before_LetGo = function(s)
	p [[Не стоит разбрасываться в космосе вещами.]];
end;
local pres = [[-- пссст. .. ..ворить? ... (пауза) ... Если кто-то сейчас болтается там... и слышит меня. Мне остаётся только сказать, простите.
Вы навсегда останетесь в наших сердцах. Верные сыны Земли, Отечества... Ещё раз, простите нас и примите мои соболезнования.^^
тщщщк...]]

obj {
	nam = 'suit';
	-"скафандр";
	description = function(s)
		p "Твой скафандр оборудован различными приборами.";
		if here().rotate then
			p [[Но сейчас ты думаешь только о маневровых двигателях.]]
			return
		end
		if not known then
			p [[Например, радио.]]
			return
		end
	end;
	["before_Enter,Climb"] = function(s)
		mp:xaction("Wear", s)
	end;
	["before_Exit,GetOff"] = function(s)
		mp:xaction("Disrobe", s)
	end;
	before_Disrobe = function(s)
		if here() ^ 'ship2' then
			return false
		else
			p 'Это самоубийство!';
		end
	end;
}:attr 'worn,clothing':with {
	obj {
		-"маневровые двигатели,двигатели|двигатель";
		nam = 'engines';
		description = [[Маневровые двигатели позволяют ориентироваться в пространстве и перемещаться на небольшие расстояния. Ты можешь включить их.]];
		after_SwitchOn = function(s)
			if here().rotate then
				p [[Ты включаешь маневровые двигатели и пытаешься остановить вращение.
В конце-концов тебе это удаётся! Только топлива ты потратил немало. Ты снова выключаешь двигатели.]]
				here().rotate = false
				s:attr'~on'
			else
				if seen 'tetr' then
					p [[Ты включаешь маневровые двигатели.]]
					return
				end
				p [[Ты даёшь пару импульсов. Лучше экономить горючее. Хотя... зачем?]];
				s:attr'~on'
			end
		end;
	}:attr 'switchable,scenery';
	obj {
		nam = 'radio';
		-"радио|рация|приёмник";
		description = function(s)
			p [[В скафандр встроен УКВ приёмник.]];
			if s:has'on' then
				if freq then
					p [[Задана рабочая частота 143,625 МГц.]]
				else
					p [[Рабочая частота не настроена.]]
				end
			end
			return false
		end;
		daemon = function(s)
			if timeout <= 0 then
				return
			end
			if freq then
				if good_to > DH_TO and s:once('ack') then
					p("Внезапно, пустота радиоэфира нарушилась.^",pres)
					p [[^^Сигналы прекратились. Ты заметил, что текст на экране изменился.]]
				else
					p [[Ты слышишь шипящий звук из рации.]]
				end
			else
				p (channels[freq_hz][channel_pos])
				if #channels[freq_hz] == 1 then
					return
				end
				channel_pos = channel_pos + 1
				if channel_pos > #channels[freq_hz] then
					freq_hz = rnd(#channels)
					channel_pos = rnd(#channels[freq_hz])
				end
			end
		end;
		after_SwitchOn = function(s)
			freq = true
			if s:once() then
				p ([[Ты включил радио на рабочей частоте.^^
... яю.. . аз... Ребята, если кто-то из вас уцелел. Запасов кислорода в ваших скафандрах недостаточно,
чтобы мы успели найти и снять кого-нибудь из вас... Нам очень жаль... А сейчас, прослушайте
обращение президента:^
...^
]]..pres..[[ Мы повторяем эту передачу каждые 15 минут в течении двух часов.]])
				known = true
			else
				p [[Ты включил радио на рабочей частоте 143,625 МГц.]];
			end
			DaemonStart 'radio'
			if here() ^ 'space' then
				DaemonStart 'space'
			end
		end;
		after_SwitchOff = function()
			DaemonStop 'radio'
			return false
		end;
	}:attr 'switchable,scenery';
}

local function stub() return false end

Verb {
	"[|по|под|в|за]лететь,[|по|под|в|за]лети";
	"к {noun}/дт,scene : Walk";
	"в {noun}/вн,scene : Enter";
	"на {compass1} : Walk",
}

Verb {
	"[на|под|пере|перена]строить,[на|под|пере|перена]строй,смен/ить,замен/ить,переключ/иить";
	"{noun}/вн : Tune";
	"частоту|канал : Tune";
}

function mp:Tune(w)
	if not w or w ^ 'radio' then
		w = _'radio'
		if w:hasnt 'on' then
			p [[Радио выключено.]]
			return
		else
			return false
		end
	end
	if w then
		p (w:It(), "не {#if_hint/#first,plural,настраиваются,настраивается}.")
		return
	end
end;

global 'freq' (true)
global 'freq_hz' (1)
global 'channel_pos' (1)
function mp:after_Tune(w)
	freq = not freq
	if not freq then
		p [[Ты сменил частоту.]]
		freq_hz = rnd(#channels)
		channel_pos = rnd(#channels[freq_hz])
		DaemonStart 'radio'
	else
		p [[Ты вернул рабочую частоту: 143,625 МГц.]]
	end
end

obj {
	nam = 'earth';
	-"Земля,планета|облака";
	description = [[Рано или поздно ты упадёшь на Землю и сгоришь в атмосфере. А пока твой дух захватывает
от величия и красоты наблюдаемого космического пейзажа.]];
	found_in = { 'space', 'space2' };
	before_Exam = stub;
	["before_Walk,Enter,Climb"] = [[Рано или поздно ты и так на неё упадёшь.]];
	before_Default = [[Земля слишком далеко.]];
}:attr'scenery';

obj {
	nam = 'stars';
	-"звёзды/но|звезда/но";
	description = [[Ты смотришь на россыпь звёзд. А они, кажется, смотрят внутрь тебя. Может быть, ты скоро станешь одной из них?]];
	found_in = { 'space', 'space2' };
	before_Exam = stub;
	before_Default = [[Звёзды слишком далеко.]];
}:attr 'scenery';

game.before_Taste = function(s, w)
	if _'suit':has'worn' then
		p [[В скафандре?]]
		return
	end
	return false
end

game.before_Smell = function(s, w)
	if _'suit':hasnt'worn' then
		return false
	end
	if not w or w:inside(pl) then
		p [[В скафандре ничем не пахнет.]]
		return
	end
	p [[В скафандре это невозможно.]]
end
game.before_Jump = [[В невесомости это невозможно.]];
game.before_JumpOver = game.before_Jump

game.before_Listen = function(s)
	if _'radio':hasnt'on' then
		p [[Для этого нужно включить радио.]]
	else
		if freq then
			p [[Радио молчит.]]
		else
			p [[Скафандр заполнен звуком радио.]];
		end
	end
end;

obj {
	-"обломки|осколки";
	description = [[Это всё, что осталось от корабля.]];
	['before_Walk,Enter,Climb'] = [[Обломки корабля уже разлетелись друг от друга на большое расстояние.
Нет смысла там что-то искать.]];
	found_in = { 'space', 'space2' };
}:attr 'scenery';

obj {
	-"объект|НЛО";
	nam = 'tetr';
	dsc = [[На фоне звёзд ты видишь какой-то яркий объект.]];
	description = [[Отсюда только понятно, что он достаточно большой. Космический мусор? Он движется почти параллельным к тебе курсом.]];
	before_Default = [[Он слишком далеко.]];
	before_Exam = stub;
	['before_Walk,Climb,Enter'] = function()
		if _'engines':hasnt'on' then
			p [[Сначала нужно включить двигатели.]]
			return
		end
		walk 'space2';
	end;
}
room {
	nam = 'space';
	title = "открытый космос";
	-"космос|пустота|пейзаж";
	rotate = true;
	step = 1;
	daemon = function(s)
		s.step = s.step + 1
		if s.step > 3 and not here().rotate then
			s:daemonStop()
			place 'tetr'
			if isDaemon('radio') then
				pn()
			end
			p [[Тебе показалось, что ты видишь какой-то яркий объект.]]
			s:daemonStop()
		end
	end;
	dsc = function(s)
		if s.rotate then
			p [[Быстро вращаясь, ты плывёшь в открытом космосе.]]
		else
			p [[Ты плывёшь в открытом космосе. Под ногами простирается голубая гладь планеты Земля.]]
		end
	end;
	before_Default = function(s, ev, w)
		if not s.rotate or ev == 'Look' or ev == 'Wait' or ev == 'Inv' then
			return false
		end
		if w and w:inside(pl) or w == pl then
			return false
		end
		p [[Из-за бешеного вращения, ты не можешь сориентироваться.]]
		if s:once 'self' then
			p [[Может быть, попробовать осмотреть себя?]]
		end
	end;
}

door {
	-"шлюзовой люк,люк,шлюзовой|шлюз";
	nam = 'gate';
	door_to = function(s)
		if here() ^ 'space2' then
			return 'ship';
		else
			return 'space2';
		end
	end;
	before_Close = [[Он закрывается автоматически.]];
	description = function() p [[Рядом с люком находится красный рычаг.]]; enable 'lever' return false; end;
}:attr 'static,openable,enterable,locked':disable();
obj {
	nam = 'lever';
		-"красный рычаг|рычаг";
	['after_Pull,Transfer'] = function(s)
		if here() ^ 'ship2' then
			if _'gate2':has'open' then
				p [[Ты дёрнул за рычаг и входной люк закрылся. При этом, внутри корабля включилось освещение.]];
				_'gate2':attr '~open'
			else
				p [[Ты дёрнул за рычаг и входной люк открылся. Освещение выключилось.]];
				_'gate2':attr 'open'
			end
			return
		end
		local open = _'gate':has'open'
		if here() ^ 'ship' then
			if not open then
				p [[Ты дёрнул за рычаг и входной люк закрылся. Затем открылся шлюзовой люк.]];
				_'gate2':attr'~open'
			end
		end
		if open then
			p [[Ты дёрнул за рычаг и шлюзовой люк закрылся.]];
			_'gate':attr'~open';
		else
			if here() ^ 'space2' then
				p [[Ты дёрнул за рычаг и шлюзовой люк открылся.]];
			end
			_'gate':attr'open';
		end
		if here() ^ 'ship' then
			if open then
				p [[Через некоторое время открылся входной люк, ведущий внутрь корабля.]];
				_'gate2':attr'open'
			end
		end
	end;
}:attr 'fixed,luminous':disable();

room {
	nam = 'space2';
	title = "открытый космос";
	-"космос|пустота|пейзаж";
	in_to = function(s)
		if disabled'gate' then
			p [[Как ты попадёшь внутрь?]];
		else
			return 'gate'
		end
	end;
	onenter = function(s)
		p [[Управляя маневровыми двигателями и почти израсходовав топливо, ты смог согласовать свою орбиту с орбитой объекта.
Им оказался спутник в форме тетраэдра.]];
		_'engines':attr '~on';
	end;
	dsc = [[Ты паришь в черной бездне рядом с неизвестным спутником. Под ногами проплывают земные облака над бирюзовой гладью.]];
}: with {
	obj {
		-"спутник,тетраэдр,корабль/но|объект|НЛО";
		description = [[Спутник словно ёж утыкан антеннами и передатчиками. Серый корпус в виде тетраэдра медленно вращается вокруг своей оси.]];
		['before_Enter,Climb'] = [[Чтобы попасть внутрь, нужен шлюз.]];
	}:attr 'scenery':with {
		obj {
			-"корпус,антенн*,передат*";
			description = function(s)
				if s:once() then
					p [[Внимательно осмотрев корпус, ты заметил шлюзовой люк.]];
					enable 'gate'
				else
					if perimetr then
						p [[Теперь ты знешь, что это за спутник.]];
					else
						p [[Спутник связи, может быть?]];
					end
				end
			end;
		}:attr 'scenery';
	};
	'gate', 'lever',

}

room {
	nam = 'ship';
	title = "шлюз";
	-"шлюзовой отсек";
	onenter = function(s, f)
		if f ^ 'space2' then
			p [[Ты влетел в шлюзовой отсек.]];
		end
	end;
	out_to = 'gate';
	in_to = 'gate2';
}: with {
	'gate', 'lever', 'gate2'
}

door {
	nam = 'gate2';
	-"входной люк,люк,входной";
	before_Close = [[Он закрывается автоматически.]];
	door_to = function(s)
		if here() ^ 'ship' then
			return 'ship2'
		else
			return 'ship'
		end
	end;
}:attr 'static,openable,enterable,locked'
global 'ask' (false)
global 'perimetr' (false)
global 'perimetr_ask' (0)
global 'timeout' (600)
global 'good_to' (0)
global 'know2' (false)
local freqs = {
	"145,800 МГц",
	"143,625 МГц",
	"4625 кГц",
	"147.211 МГц",
	"192.112 МГц",
}
room {
	nam = 'ship2';
	-"корабль";
	title = "внутри корабля";
	out_to = 'gate2';
	daemon = function(s)
		if good_to > DH_TO and s:once('ack') then
			if here() == s then
				if not isDaemon'radio' then
					p [[Сигналы прекратились. Ты заметил, что текст на экране изменился.]]
				end
			end
			s:daemonStop()
		else
			if here() == s then
				p [[Ты слышишь пульсирующий звуковой сигнал, который разносится по кораблю каждую секунду.]]
				if know2 then
					p ([[До первой волны ]], timeout, " с.")
				end
			end
		end
	end;
	onenter = function(s)
		if s:once() then
			p [[С тревогой и надеждой, ты влетел внутрь странного корабля.]]
		end
	end;
	dsc = function(s)
		p [[Внутри корабля не так много места. Впрочем, к этому тебе не привыкать.]];
		if _'gate2':has'open' then
			p [[Здесь довольно темно. Детали обстановки плохо различимы в полумраке.]]
		end
	end;
	onexit = function(s)
		if _'suit':hasnt 'worn' then
			p [[Без скафандра? Самоубийство!]]
			return false
		end
	end;
	before_Any  = function(s, ev)
		if perimetr then
			if perimetr_ask == 2 then
				good_to = good_to + 1
			else
				good_to = 0
			end
			timeout = timeout - rnd(25)
			if timeout < 0 then
				if timeout < 0 then
					walkin 'badend'
					return
				end
			end
		end
		if ask and (ev == 'Yes' or ev == 'No') then
			if ev == 'No' then
				p [[Ну и правильно.]]
			else
				p [[Ты нажал на кнопку и на экране консоли побежали строки текста.]]
				DaemonStart 'ship2'
				perimetr = true
			end
			return
		end
		ask = false
		return false
	end;
}: with {
	'gate2', 'lever';
	obj {
		-"панель управления,панель|приборы";
		description = [[Ты видишь множество приборов, назначение которых тебе непонятно, и экран консоли.
Твоё внимание привлеает красная кнопка.]];
	}:attr'static,supporter':with {
		obj {
			nam = 'button';
			-"красная кнопка,красная,кнопка";
			description = [[На кнопке ты не видишь никаких надписей или обозначений.]];
			before_Push = function()
				if perimetr then
					perimetr_ask = perimetr_ask + 1
					if perimetr_ask > 5 then perimetr_ask = 0 end
					p [[Ты ещё раз нажал на кнопку.]]
					p [[Ты заметил, что на экране изменилась одна из строк.^]]
					p ("Режим голосовой отмены: ")
					if perimetr_ask == 0 then
						p ("выкл.")
					else
						p(freqs[perimetr_ask])
					end
					return
				end
				p [[Неизвестный корабль. Красная кнопка. Ты точно готов это сделать?^Подтверди. Да или нет?]]
				ask = true
			end;
		}:attr 'static,concealed';
		obj {
			nam = 'screen';
			-"экран,консоль,текст";
			description = function(s)
				if good_to > DH_TO then
					DaemonStop'ship2'
					DaemonStop'radio'
					walkin 'goodend'
					return
				end
				if perimetr then
					p ([[Программа "ПЕРИМЕТР" активирована.^^
Переход в автономный режим: да^]])
					if perimetr_ask > 0 then
						p ([[Режим голосовой отмены: ]], freqs[perimetr_ask], ".")
					else
						p ([[Режим голосовой отмены: выкл.]])
					end
					p ([[^Отключение управления по каналам связи: да^
Отсчёт времени до начала активной фазы: ]], timeout,
[[^Ядерный удар первой волны: ожидание^
Ядерный удар второй волны: ожидание^
Последняя волна: ожидание]])
					know2 = true
				else
					p [[Экран неактивен.]];
				end
			end;
		}:attr 'static';
	};
};

cutscene {
	nam = 'badend';
	title = 'Конец';
	text = { [[Ты так и не смог отключить машину судного дня.^
Почти обезумевший, ты смотрел с орбиты как Земля сгорает в ядерном аду.^
Лучше бы ты погиб в открытом космосе...^
^{$fmt em|Но всё могло закончиться по-другому...}]] };
	onexit = function(s)
		timeout = 600
	end;
}

cutscene {
	nam = 'goodend';
	title = false;
	text = {
		[[Процедура прервана.^
Причина: президент жив^
Выполняется выход из автономного режима: да^
Сигнал с охраняемых объектов: восстановлен]];
		[[{$fmt c|***}^^Ты медленно приходил в себя. Ужас неотвратимого только сейчас навалился на тебя
со всей силой. Поэтому долгое время ты отстранённо парил в невесомости.^^
Похоже, что передача с Земли, принятая спутником, остановила процедуру последнего удара.^^
Да, понадобится время, чтобы освоиться с этой машиной судного дня и послать сигнал в центр полётов.^^
Но главное, что ты не стал виновником гибели своего мира. Это сейчас было всё, что имело для тебя смысл.]]
	};
	next_to = 'titles';
}

room {
	title = fmt.c(fmt.b([[СУДНЫЙ ДЕНЬ]]));
	nam = 'titles';
	noparser = true;
	dsc = [[{$fmt c|Автор сюжета и кода: Косых Пётр^^
Специально на ИНСТЕДОЗ-6^^
Март -- 2019^^
Если вам понравилась игра,
^заходите на http://instead-games.ru
}
]]
}
