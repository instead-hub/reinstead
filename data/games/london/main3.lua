--$Name: Лондон 1884$
--$Version: 0.4$
--$Author: Андрей Лобанов$

require "fmt"
require "snapshots"
require "parser/mp-ru"

function init()
   pl.word = -"я/мр,1л"
   pl.room = "гостиная"
end

game.dsc = fmt.b("Лондон 1884") .. " версия: 0.4^^" .. fmt.em(fmt.b "Автор: " .. "Андрей Лобанов^Специально для Инстедоз 6.^^За тестирование спасибо Петру Косых, Irremann'у,  Zlobot'у и Goraph'у.")

Verb {
   "[ |под]жечь,жг/и,подожги/,поджиг/ай,зажг/и,зажиг/ай,зажечь,[под|рас]курить",
   "{noun}/вн : Burn",
   "{noun}/вн {noun}/тв,held : Burn",
   "~ {noun}/тв,held {noun}/вн reverse",
}

VerbHint ( "#Burn", function(v)
			  return have "спички"
end)

function game.beforeBurn()
   if not have "спички" then
	  return "Мне нечем поджечь {#first/вн}."
   end
end

function mp:Burn(w, wh)
   if mp:check_touch() then
	  return
   end
   if wh and mp:check_held(wh) then
	  return
   end
   p "Я не собираюсь устраивать пожар."
end

Verb {
   "наб/ить,заб/ить",
   "{noun}/вн,held : FillPipe",
   "{noun}/вн,held {noun}/тв,held : FillPipe",
}

function mp:FillPipe(w)
   return "Какая-то глупость."
end

Verb {
   "потушить,тушить",
   "{noun}/вн,held : Extinguish"
}

function mp:Extinguish(w)
   if w ^ "лампа" then
	  if w.fire then
		 w.fire = false
		 if here() ^ "терраса_" or here() ^ "склад" then
			here():attr "~light"
		 end
		 return "Я потушил лампу."
	  else
		 return "Лампа не зажжена."
	  end
   else
	  return "{#First} не горит."
   end
end

Verb {
   "стучать,постучать",
   "по {noun}/дт : Knock",
   "в {noun}/им : Knock",
}

function mp:Knock(w)
   if mp.args[1].word == "в" then
	  return "Я постучал в {#first/вн}."
   else
	  return "Я постучал по {#first/дт}."
   end
end

Verb {
   "выстрелить,стрелять",
   "в {noun}/вн : Shoot",
}

function mp:Shoot(w)
   if have "револьвер" then
	  if _"револьвер".loaded then
		 if w:has "animate" then
			return "Я не собираюсь убивать {#first/вн}."
		 else
			return "Я не хочу стрелять в {#first/вн}."
		 end
	  else
		 return "В револьвере не осталось патронов."
	  end
   else
	  return "Мне не из чего стрелять."
   end
end

Verb {
	"толк/ать,пих/ать,нажим/ать,нажм/и,нажать,сдвин/уть,подвин/уть,двига/ть,задви/нуть,запих/нуть,затолк/ать,[ |на]давить,опрокинуть",
	"?на {noun}/вн : Push",
	"{noun}/вн на|в|во {noun}/вн : Transfer",
	"{noun}/вн {compass2} : Transfer",
	"~ на|в|во {noun}/вн {noun}/вн : Transfer reverse",
	"~ {compass2} {noun}/вн : Transfer reverse"
}

obj {
   nam = "таймер",
   n = 0,
   daemon = function(s)
	  if s.n > 2 and s.n < 7 then
		 if not disabled "полисмен" then
			if here() ^ "Сейнт Джордж стрит" then
			   p "Полицейский ушёл -- как будто растворился у тумане."
			end
			disable "полисмен"
		 end
	  else
		 if disabled "полисмен" then
			if here() ^ "Сейнт Джордж стрит" then
			   p "Из тумана вышел полицейский"
			end
			enable "полисмен"
			s.n = 0
		 end
	  end
	  s.n = s.n + 1
   end,
}

room {
	  -"гостиная",
   nam = "гостиная",
   disp = "Гостиная",
   onexit = function(s, w)
	  if w ^ "Кейбл стрит" then
		 if _"окно дома".seen then
			if not have "револьвер" then
			   p "Опасно выходить на улицу безоружным."
			   return false
			end
			if not have "спички" then
			   take "спички"
			   return "Я на всякий случай прихватил с собой спички."
			end
		 else
		   p "В холодной осенней ночью совсем не хочется выходить на улицу."
		   return false
		 end
	  end
   end,
   obj = {
	  obj {
			-"камин,очаг,огонь",
		 nam = "камин",
		 seen = false,
		 dsc = "Напротив камина",
		 description = function(s)
			if not s.seen then
			   s.seen = true
			   return "В камине потрескивают дрова, огонь приятно освещает гостиную."
			else
			   return "Камин занимает добрую половину стены."
			end
		 end,
	  }:attr "static",
	  obj {
			-"кресло",
		 nam = "кресло",
		 dsc = "стоят кресло ",
		 description = "Старое массивное кресло в стиле королевы Анны.",
		 before_Take = function()
			p "Кресло слишком тяжёлое."
			return true
		 end,
	  }:attr "static,enterable,supporter",
	  obj {
			-"столик,стол",
		 nam = "столик",
		 dsc = function(s)
			p "и столик."
			mp:content(s)
		 end,
		 description = "Маленький столик.",
		 obj = {
			obj {
				  -"бокал,бренди",
			   full = true,
			   nam = "бокал",
			   description = function(s)
				  if s.full then
					 return "В бокале налито бренди."
				  else
					 return "Бокал пуст."
				  end
			   end,
			   Drink = function(s)
				  if have(s) then
					 if s.full then
						s.full = false
						return "Я одним глотком осушил бокал. Крепкий напиток обжёг язык и нёбо, спустился по пищеводу колючим комком и приятным теплом растёкся по телу."
					 else
						return "Бокал пуст."
					 end
				  else
					 return "Сперва нужно взять бокал."
				  end
			   end,
			   after_Drop = "Я аккуратно поставил бокал.",
			},
			obj {
				  -"трубка",
			   nam = "трубка",
			   full = false,
			   sm = false,
			   FillPipe = function(s)
				  if s.full then
					 return "Трубка уже набита."
				  else
					 if have "кисет" then
						if s.sm then
						   return "Мне больше не хочется курить."
						else
						   s.full = true
						   return "Я аккуратно набил трубку."
						end
					 else
						return "Нужен табак."
					 end
				  end
			   end,
			   before_Receive = function(s, w)
				  if w ^ "кисет" then
					 return s:FillPipe(s)
				  else
					 return "{#First} не влезет в трубку."
				  end
			   end,
			   Burn = function(s)
				  if have(s) then
					 if s.full then
						if here() ^ "гостиная" then
						   s.sm = true
						   p "Я с удовольствием раскурил трубку и некоторое время сидел, глядя в камин и пуская кольца дыма."
						elseif here() ^ "спальня" then
						   p "Не люблю курить в спальне."
						else
						   p "Предпочитаю курить в спокойной обстановке, а не на ходу."
						end
					 else
						if s.sm then
						   p "Мне больше не хочется курить."
						else
						   p "В трубке нет табака."
						end
					 end
				  else
					 return "У меня нет трубки."
				  end
			   end,
			   description = "Простая курительная трубка. Люблю покурить перед сном.",
			}:attr "container",
			obj {
				  -"кисет,табак",
			   nam = "кисет",
			   description = "Датский \"МакБарен\". Отличный табак, который иногда мне высылает друг из Дании.",
			   before_Open = "В кисете лежит отличный датский табак.",
			},
			obj {
				  -"спички|спичка",
			   nam = "спички",
			   description = "Коробок спичек фирмы \"Брайан и Мей\".",
			},
			obj {
				  -"газета,дейли меил",
			   nam = "газета",
			   seen = false,
			   description = function(s)
				  if have(s) then
					 local v = "Первая полоса посвящена статье с кричащим заголовком \"Загадка Ист-сайда\", в которой некий Адам Уильямс повествует о загадочных исчезновениях людей в Ист-сайде. Пространные размышления о росте уровня преступности он перемежает путаными свидетельскими показаниями о загадочном силуэте, который можно встретить на улице туманными вечерами. По мнению опрошенных Уильямсом очевидцев, именно эта тень похищает людей... Читать статью дальше я не нашёл в себе сил."
					 if not s.seen then
						s.seen = true
						v = v .. "^^Вряд ли в ближайшее время я буду сожалеть о каких-либо тратах больше, чем о подписке на это издание."
					 end
					 return v
				  else
					 return "\"Дейли меил\" за 13 октября 1884 года."
				  end
			   end,
			},
		 },
	  }:attr "static,supporter",
	  obj {
			-"лестница",
		 nam = "лестница дома",
		 dsc = "Наверх ведёт узкая лестница.",
		 description = "Деревянная лестница с вытертыми от времени перилами.",
	  }:attr "static",
	  obj {
			-"окно,окошко",
		 nam = "окно дома",
		 seen = false,
		 dsc = "В окне видны отсветы уличного освещения.",
		 description = function(s)
			if not s.seen then
			   s.seen = true
			   local v = "В тусклом свете фонарей, едва пробивающемся через плотный туман, мелькнул тёмный силуэт. Его порывистые движения выглядят странно."
			   if _"газета".seen then
				  v = v .. " Возможно, это прочитанная статья позволила разыграться моему воображению, но есть в них что-то неестественное."
			   end
			   return v
			else
			   return "За окном видны тусклые огни фонарей, едва пробивающиеся через плотный туман."
			end
		 end,
	  }:attr "static",
   },
   u_to = "спальня",
   s_to = "дверь дома",
   out_to = "дверь дома",
}

door {
	  -"дверь,входная дверь",
   nam = "дверь дома",
   dsc = function()
	  if here() ^ "гостиная" then
		 return "В южной стене находится входная дверь."
	  else
		 return "В северной стене находится дверь в мою квартиру."
	  end
   end,
   description = "Обычная деревянная дверь.",
   door_to = function(s)
	  if here() ^ "гостиная" then
		 return "Кейбл стрит"
	  else
		 return "гостиная"
	  end
   end,
   found_in = { "гостиная", "Кейбл стрит" },
}:attr "static,openable"

room {
	  -"спальня",
   nam = "спальня",
   obj = {
	  obj {
			-"кровать",
		 nam = "кровать",
		 dsc = "Здесь есть кровать",
	  }:attr "static,enterable,supporter",
	  obj {
			-"тумбочка",
		 nam = "тумбочка",
		 dsc = function(s)
			p " и тумбочка"
			mp:content(s)
		 end,
		 description = function(s)
			p "Симпатичная тумбочка."
			mp:content(s)
		 end,
		 before_Receive = function(s, w)
			if mp.xevent == "Insert" then
			   move(w, "#втумбочке")
			   p("{#Me} положил ", w:noun'вн', " в тумбочку.")
			else
			   return false
			end
		 end,
		 before_Open = function()
			_"#втумбочке":attr "open"
			p(mp.msg.Open.OPEN)
		 end,
		 before_Close = function()
			_"#втумбочке":attr "~open"
			p(mp.msg.Close.CLOSE)
		 end,
		 obj = {
			obj {
				  -"тумбочка",
			   nam = "#втумбочке",
			   dsc = function(s)
				  mp:content(s)
			   end,
			   obj = {
				  obj {
						-"револьвер,пистолет",
					 nam = "револьвер",
					 loaded = true,
					 description = "Новенький армейский \"Webley\".",
				  },
			   },
			}:attr "static,container,openable",
		 },
	  }:attr "static,supporter,enterable",
   },
   d_to = "гостиная",
}

room {
   nam = "Кейбл стрит",
   seen = false,
   dsc = function(s)
	  local v
	  if not s.seen then
		 s.seen = true
		 v =  "Я вышел в холодный вечерний туман улиц. Привычная Кейбл стрит поздним вечером выглядит пустынно и неуютно. Звуки как будто вязнут в тумане."
		 if _"окно дома".seen then
			v = v .. "^^В тумане можно легко ошибиться, но кажется, виденный мной ранее силуэт движется на юг - в сторону Сейнт Джордж стрит."
		 end
	  else
		 v = "Я нахожусь на Кейбл стрит."
	  end
	  v = v .. "^^На юге темнеет маленькая Пелл стрит. На юго-западе находится Уэллклоус сквер."
	  return v
   end,
   n_to = "дверь дома",
   s_to = "Пелл стрит",
   sw_to = "Уэллклоус сквер",
}

room {
   nam = "Уэллклоус сквер",
   seen = false,
   dsc = function(s)
	  local v
	  if not s.seen then
		 s.seen = true
		 v = "В окружении лавочек и фонарей посреди Уэллклоус сквер расположена большая клумба."
	  else
		 v = "Я нахожусь на Уэллклоус сквер."
	  end
	  v = v .. " На северо-восток ведёт проход на Кейбл стрит. Сейнт Джордж стрит тянется на юго-востоке."
	  return v
   end,
   exit = function(s, w)
	  if not w ^ "разговор с Джайлсом" and not disabled "Джайлс" then
		 disable "Джайлс"
		 _"дверь Джайлса":attr "~open"
	  end
   end,
   obj = {
	  obj {
			-"лавочки,скамейки",
		 nam = "лавочки",
		 description = "Удобные лавочки.",
	  }:attr "scenery",
	  obj {
			-"фонари",
		 nam = "фонари Уэллклоус сквер",
		 description = "Газовые фонари мало что освещают в густом тумане.",
	  }:attr "scenery",
	  obj {
			-"клумба",
		 nam = "клумба",
		 description = "Без цветов клумба выглядит мрачно. Или это туман так меняет моё восприятие?",
	  }:attr "scenery",
	  obj {
			-"мышь,механическая мышь|механизм",
		 nam = "механическая мышь",
		 dsc = "Возле двери одной из квартир лежит странный механизм.",
		 description = "Больше всего это устройство похоже на игрушечную мышь.",
		 before_Take =  "Я попытался взять этот странный механизм, но он оказался на удивление юрким.",
	  }:attr "~animate":disable(),
	  obj {
			-"дверь",
		 nam = "дверь Джайлса",
		 dsc = function(s)
			if disabled "механическая мышь" and disabled "Джайлс" then
			   return "Здесь есть дверь, ведущая в квартиру Джайлса."
			end
		 end,
		 description = "Ничем не примечательная деревянная дверь.",
		 Open = "Не стоит вламываться в чужую квартиру.",
		 Knock = function(s)
			if _"Джайлс".talked then
			   return "Пожалуй, не стоит его больше беспокоить."
			else
			   if s:has "open" then
				  return "Дверь уже открыта."
			   else
				  s:attr "open"
				  enable "Джайлс"
				  disable "механическая мышь"
				  return "Я постучал в дверь. Из квартиры послышались шаги, после чего дверь открылась. На пороге показался мужчина средних лет. Механическая мышь скользнула внутрь."
			   end
			end
		 end,
	  }:attr "static,openable":disable(),
	  obj {
			-"мужчина,Джайлс",
		 nam = "Джайлс",
		 talked = false,
		 dsc = function(s)
			local v = "На пороге одной из квартир стоит "
			if not s.talked then
			   v = v .."мужчина."
			else
			   v = v .. "Джайлс."
			end
			return v
		 end,
		 description = "Невысокий мужчина средних лет, с пробивающейся в волосах сединой.",
		 Talk = function(s)
			if not s.talked then
			   s.talked = true
			   walk "разговор с Джайлсом"
			else
			   return "У Джайлса такой вид, как будто он совершенно не расположен к разговору со мной."
			end
		 end,
	  }:attr "animate":disable():dict {
		 ["Джайлс/рд"] = "Джайлса",
		 ["Джайлс/дт"] = "Джайлсу",
		 ["Джайлс/вн"] = "Джайлса",
		 ["Джайлс/тв"] = "Джайлсом",
		 ["Джайлс/пр"] = "Джайлсе",
									  },
   },
   ne_to = "Кейбл стрит",
   se_to = "Сейнт Джордж стрит",
}

dlg {
   nam = "разговор с Джайлсом",
   phr = {
	  "-- Чем я могу вам помочь?",
	  { "Вы видели этот странный механизм?", "-- Вы про мою игрушку? Да. Это механическая мышь. Механический соглядатай, если угодно.",
		{ "Это ваше изобретение?", "-- Как и многое другое. Меня зовут Джайлс, -- имя прозвучало так, как будто весь Лондон знает его обладателя в лицо, -- и я изобретатель. В последнее время стали пропадать люди и я нашёл, если можно так выразиться, применение своим изобретениям.",
		  { "Вам удалось что-то найти?", "-- Не так много. По большей части я смог только подтвердить слухи, имеющие хождение в народе и раздуваемые дешёвой прессой.",
			{ "Вы о загадочных тенях, описываемых очевидцами? Я сегодня, кажется, видел одну. Она направлялась в сторону складов.", "-- А вот и новая информация. Мои игрушки хороши, но не заменяют пару острых глаз. Пока я только смог установить, что происшествия всегда случаются в районе доков.",
			  { "Мы могли бы сходить и посмотреть что там происходит.", "-- Пожалуй, вы бы действительно смогли бы, а вот я уже не столь быстр и ловок, как в молодости, -- тут я заметил, что в руках у него находится трость.",
				{ "Я мог бы разведать что там происходит.", "-- Не хотелось бы подвергать посторонних людей излишней опасности только лишь из моего любопытства.",
				  { "Сохранение безопасности -- долг каждого джентльмена и подданного Её Величества.", "-- Совершенно верно. Современная молодёжь начала об этом забывать." },
				}
			  },
			},
		  },
		},
	  },
   },
}

room {
   nam = "Пелл стрит",
   seen = false,
   dsc = function(s)
	  local v
	  if not s.seen then
		 s.seen = true
		 v = "Пелл стрит - не самое приятное место туманной ночью. Свет фонарей едва освещает эту маленькую улочку."
	  else
		 v = "Я нахожусь на Пелл стрит." 
	  end
	  v = v .. "^^На севере манит домашним уютом Кейбл стрит. С юга угадывается свет фонарей Сейнт Джордж стрит."
	  return v
   end,
   obj = {
	  obj {
			-"фонари,свет",
		 nam = "фонари Сейнт Джордж",
		 description = "И без того тусклый свет газовых фонарей усугубляется плотным туманом.",
	  }:attr "scenery",
   },
   n_to = "Кейбл стрит",
   s_to = "Сейнт Джордж стрит",
}

room {
   nam = "Сейнт Джордж стрит",
   seen = false,
   dsc = function(s)
	  local v
	  if not s.seen then
		 s.seen = true
		 v = "После темноты Пелл стрит, свет фонарей в тумане воспринимается почти как солнечный."
	  else
		 v = "Я нахожусь на Сейнт Джордж стрит."
	  end
	  v = v .. "^^На севере темнеет Пелл стрит. На юге тянется Пеннингтон стрит. На северо-западе расположен Уэллклоус сквер."
	  return v
   end,
   obj = {
	  obj {
			-"полисмен,полицейский",
		 nam = "полисмен",
		 talked = false,
		 dsc = "Вдоль улицы неторопливо прохаживается полисмен.",
		 description = "Начинающий полнеть джентльмен с густыми усами.",
		 obj = {
			obj {
				  -"усы",
			   description = "Тебе действительно это интересно?",
			}:attr "scenery",
		 },
		 talk_to = function(s)
			if not s.talked then
			   s.talked = true
			   return "разговор с полисменом"
			else
			   p "Полисмен повернулся ко мне и сказал:^^-- Будьте осторожны, сэр."
			   return
			end
		 end,
	  }:attr "animate",
   },
   n_to = "Пелл стрит",
   s_to = "Пеннингтон стрит",
   nw_to = "Уэллклоус сквер",
}

dlg {
   nam = "разговор с полисменом",
   phr = {
	  "-- Добрый вечер, сэр,",
	  { "Добрый вечер.", "-- Не ходили бы вы ночью по улице. В последнее время что-то странное происходит рядом с доками.",
		{ "Вы о тех сплетнях, что разносят дешёвые газеты?", "-- Это не сплетни. Нет, сэр. Я сам не верил, пока меня не отправили патрулировать район доков.",
		  { "Вы что-то видели?", "-- Ничего конкретного, но в последние дни вечерами стали появляться странные силуэты в тумане, а по утру кто-нибудь приходит в участок и сообщает о пропаже человека. Шли бы вы домой, сэр.",
			{ "Хорошо. Спасибо, констебль.", function() p "-- Будьте осторожны, сэр."; DaemonStart "таймер"; end },
		  },
		},
	  },
   },
}

room {
   nam = "Пеннингтон стрит",
   seen = false,
   dsc = function(s)
	  local v
	  if not s.seen then
		 s.seen = true
		 enable "механическая мышь"
		 enable "дверь Джайлса"
		 v = "Чем ближе к докам, тем уже и грязнее улочки.^^Что-то небольшое, напоминающее металлическую крысу, быстро пробежало поперёк улицы и скрылось на севере."
	  else
		 v = "Я нахожусь на Пеннингтон стрит."
	  end
	  v = v .. " На севере находится Сейнт Джордж стрит, на востоке -- старая дорога. На юге расположены складские помещения."
	  return v
   end,
   onexit = function(s, w)
	  if w ^ "склады" then
		 p "Охрана складских помещений вряд ли пропустила бы меня и днём. Ночью и подавно не пропустит."
		 return false
	  end
   end,
   obj = {
	  obj {
			- "стена,кирпичная стена",
		 nam = "стена",
		 dsc = "На юге расположена стена, огораживающая склады.",
		 description = "Кирпичная стена высотой около восьми футов.",
		 obj = {
			obj {
				  - "склады",
			   nam = "склады со стороны Пеннингтон стрит.",
			   description = "Однотипные унылые коробки, в которых хранятся ввозимые по Темзе товары.",
			}:attr "static",
		 },
		 before_Climg = "Стена слишком высока, чтобы я смог на неё забраться.",
	  }:attr "static",
	  obj {
			-"ворота",
		 nam = "ворота",
		 dsc = "Высокие ворота ведут на складскую территорию.",
		 description = "Железные ворота из кованых прутьев.",
	  }:attr "static",
	  obj {
			-"охранники/мр,мн|охрана",
		 nam = "охранники",
		 dsc = "У ворот стоят охранники.",
		 description = "Крепкие ребята.",
		 Talk = "-- Приходите утром, сэр. Сейчас здесь нечего делать.",
	  }:attr "animate",
   },
   n_to = "Сейнт Джордж стрит",
   s_to = "склады",
   e_to = "перекрёсток",
}

room {
   nam = "перекрёсток",
   seen = false,
   dsc = function(s)
	  local v = ""
	  if not s.seen then
		 s.seen = true
		 v = "Тёмное пересечение Пеннингтон стрит и старой гравийной дороги. Не самое приятное место в Ист-сайде. "
	  end
	  v = v .. "На западе видны ворота, ведущие на территорию складов. На юге дорога ведёт к Темзе."
	  return v
   end,
   obj = {
	  obj {
			-"дорога,гравийная дорога",
		 nam = "гравийная дорога",
		 description = "Старая гравийная дорога. Если в ней и есть что-то примечательное, то это не обнаружить туманной ночью.",
	  }:attr "scenery",
	  obj {
			-"стена",
		 nam = "угол стены",
		 dsc = "Стена, ограждающая склады, поворачивает здесь на юг.",
		 description = "Скучная кирпичная стена. Конечно, я не вижу её, чтобы судить о том насколько она скучная или кирпичная, но весь предыдущий опыт хождения возле неё говорит именно об этом.",
	  }:attr "static",
	  obj {
			-"ворота",
		 description = "Железные ворота из кованых прутьев.",
		 before_Take = "Ворота находятся далеко.",
	  }:attr "scenery",
   },
   w_to = "Пеннингтон стрит",
   s_to = "к востоку от складов",
}

room {
   nam = "к востоку от складов",
   seen = false,
   dsc = function(s)
	  local v = ""
	  if not s.seen then
		 s.seen = true
		 v = "В этой части старой дороги отсутствуют даже далёкие отсветы фонарей. "
	  end
	  v = v .. "На юге слышна Темза. Гравийная дорога уходит на север."
	  return v
   end,
   onexit = function(s, w)
	  if w ^ "на дереве" and not _"Джайлс".talked then
		 p "Приятно вспомнить себя мальчишкой, но лазить по деревьям посреди ночи мне не хочется."
		 return false
	  end
   end,
   before_Listen = "Слышен плеск воды.",
   obj = {
	  "гравийная дорога",
	  obj {
			-"стена",
		 nam = "восточная стена",
		 dsc = function (s)
			if here() ^ "к востоку от складов" then
			   return "Стена, окружающая склады, тянется с севера на юг."
			else
			   return "На западе угадывается силуэт стены."
			end
		 end,
		 description = function(s)
			if here() ^ "к востоку от складов" then
			   return "Всё такая же скучная и кирпичная."
			else
			   return "Пожалуй, отсюда я бы смог перелезть через стену."
			end
		 end,
	  }:attr "static",
	  obj {
			-"деревце,дерево|берёза",
		 nam = "дерево",
		 dsc = "Небольшое деревце скорее угадывается, чем видится в тёмном тумане.",
		 description = "Кажется, это берёза.",
		 before_Climb = function()
			if not _"Джайлс".talked then
			   p "Приятно вспомнить себя мальчишкой, но лазить по деревьям посреди ночи мне не хочется."
			else
			   walk "на дереве"
			end
		 end,
	  }:attr "static",
	  obj {
			-"река,Темза",
		 nam = "река у дерева",
		 description = "Отец Темза. Действительно величественный после постройки канализации и окончании Великого Зловония.",
		 before_Take = "Как можно взять реку?",
		 before_Listen = function(s)
			return s.description
		 end,
	  }:attr "scenery"
   },
   n_to = "перекрёсток",
   u_to = "на дереве",
}

room {
   nam = "на дереве",
   dsc = "Вспомнив времена своего детства, я довольно быстро взобрался на дерево.",
   obj = {
	  obj {
			-"ветки",
		 nam = "ветки",
		 dsc = "Густые ветки затрудняют движение.",
		 description = "Ничем не примечательные ветки.",
	  }:attr "static",
	  "восточная стена",
   },
   d_to = "к востоку от складов",
   w_to = "склады"
}

room {
   nam = "склады",
   seen = false,
   dsc = function(s)
	  if not s.seen then
		 s.seen = true
		 return "Оттолкнувшись посильнее, я допрыгнул до стены. Правда несколько не рассчитал силу прыжка и больно ударился животом. Немного отдышавшись, спрыгнул вниз и только потом понял, что не знаю как буду выбираться обратно."
	  else
		 return false
	  end
   end,
   onexit = function(s, t)
	  if t ^ "второй этаж" and _"керосин".fire then
		 p "Не стоит лезть в горящее здание. Нужно найти способ унести отсюда ноги незамеченным."
		 return false
	  end
   end,
   obj = {
	  obj {
			-"лампа",
		 nam = "лампа",
		 fire = false,
		 dsc = "На стене висит лампа.",
		 description = function(s)
			if have(s) then
			   if s.fire then
				  return "Лампа зажжена."
			   else
				  return "Обычная керосиновая лампа. Полна керосина."
			   end
			else
			   return "Обычная керосиновая лампа."
			end
		 end,
		 Burn = function(s)
			if s.fire then
			   return "Лампа уже зажжена."
			else
			   s.fire = true
			   if here() ^ "терраса_" or here() ^ "склад" then
				  here():attr "light"
			   end
			   return "Я зажёг лампу."
			end
		 end,
	  },
	  obj {
			-"склады,здания",
		 nam = "склады о",
		 description = "Приземистые кирпичные коробки.",
	  }:attr "scenery",
	  obj {
			-"большой склад,склад,здание",
		 nam = "большой склад",
		 dsc = function(s)
			if _"керосин".fire then
			   return "Рядом со мной находится двухэтажное здание объятое огнём."
			else
			   return "Рядом со мной находится двухэтажное здание."
			end
		 end,
		 description = function(s)
			if _"керосин".fire then
			   return "Огонь уже охватил здание целиком."
			else
			   return "Оно существенно выделяется на фоне одноэтажных складов."
			end
		 end,
	  }:attr "static",
	  obj {
			-"ворота",
		 nam = "ворота склада",
		 dsc = "Большие ворота, ведущие на Пеннингтон стрит, закрыты.",
		 description = "Железные ворота из кованых прутьев.",
		 Open = "Думаю, охранники будут весьма рады встретить меня, выходящим прямо через ворота. Пожалуй, стоит держаться подальше.",
	  }:attr "static,openable",
	  obj {
			-"охранники/мр,мн|охрана",
		 nam = "охранники внутри",
		 dsc = "За воротами стоят охранники.",
		 description = "Их задача, в первую очередь, никого не впускать. Поэтому они стоят спиной к воротам.",
	  }:attr "animate",
	  obj {
			-"лестница,ступеньки",
		 nam = "лестница склада",
		 dsc = function()
			if here() ^ "склады" then
			   return "Металлическая лестница ведёт на второй этаж ближайшего склада."
			else
			   return "Вниз ведёт металлическая лестница."
			end
		 end,
		 description = "Обычная металлическая лестница.",
	  }:attr "static",
	  obj {
			-"река,Темза",
		 dsc = "На юге слышен плеск реки.",
		 before_Take = "Как можно взять реку?",
	  }:attr "static",
   },
   u_to = "второй этаж",
   s_to = "у реки",
}

room {
   nam = "у реки",
   seen = false,
   dsc = function(s)
	  local v
	  if not s.seen then
		 s.seen = true
		 v = "Я подошёл к Темзе. Над рекой туман настолько плотный, что не разглядеть даже воду."
	  else
		 v = "Я нахожусь у реки."
	  end
	  v = v .. " К северу находятся склады."
	  return v
   end,
   onexit = function(s, t)
	  if t ^ "склады" and _"керосин".fire then
		 p "На север уже не пройти из-за бушующего пламени."
		 return false
	  end
   end,
   before_Swim = function(s)
	  _"Темза":before_Enter()
   end,
   obj = {
	  obj {
			-"река,вода",
		 nam = "Темза",
		 dsc = "Под набережной плещется холодная вода.",
		 description = function(s)
			if _"керосин".fire then
			   return "Тёмная вода осенней Темзы отражает огонь пожара, освещая всё вокруг неверным колышущимся светом."
			else
			   return "В темноте и тумане реку не видно."
			end
		 end,
		 before_Take = function()
			p "Невозможно взять реку."
			return true
		 end,
		 before_Enter = function()
			if _"керосин".fire then
			   walk "конец"
			   return true
			else
			   p "У меня нет никакого желания прыгать в холодную воду ночью."
			end
		 end,
		 obj = {
			obj {
				  -"набережная",
			   nam = "набережная",
			   description = function(s)
				  if _"керосин".fire then
					 return "В свете пожара всю набережную видно как на ладони."
				  else
					 return "Набережная теряется в темноте."
				  end
			   end,
			}:attr "scenery",
		 },
	  }:attr "static,container",
   },
   n_to = "склады",
}

room {
   nam = "второй этаж",
   dsc = "Отсюда хорошо просматривается весь район.",
   obj = {
	  "лестница склада",
   },
   d_to = "склады",
   e_to = "окно склада",
   in_to = "окно склада",
}

door {
	  -"окно",
   nam = "окно склада",
   dsc = function()
	  if here() ^ "второй этаж" then
		 return "В склад можно попасть через окно."
	  else
		 return "Наружу можно выбраться через окно."
	  end
   end,
   description = "Окно легко открывается с обоих сторон.",
   door_to = function()
	  if here() ^ "второй этаж" then
		 return "терраса_"
	  else
		 return "второй этаж"
	  end
   end,
   found_in = { "второй этаж", "терраса_" },
}:attr "static"

room {
   nam = "терраса_",
   disp = "терраса",
   seen = false,
   snapshot = false,
   dsc = function(s)
	  if not s.seen then
		 s.seen = true
		 return "Я оказался на террасе, опоясывающей склад внутри по периметру."
	  else
		 return "Я нахожусь на террасе."
	  end
   end,
   enter = function(s, f)
	  if have "лампа" and _"лампа".fire then
		 s:attr "light"
	  end
	  if not s.snapshot then
		 s.snapshot = true
		 snapshots:make()
	  end
   end,
   exit = function(s, w)
	  s:attr "~light"
   end,
   obj = {
	  obj {
			-"терраса",
		 nam = "терраса",
		 description = "Железная терраса проходит по периметру всего здания.",
	  }:attr "scenery",
	  obj {
			-"лестница",
		 nam = "лестница внутри склада",
		 dsc = function()
			if here() ^ "терраса_" then
			   return "Вниз ведёт металлическая лестница."
			else
			   return "Наверх ведёт металлическая лестница."
			end
		 end,
	  }
   },
   w_to = "окно склада",
   out_to = "окно склада",
   d_to = "склад",
}:attr "~light"

room {
   nam = "склад",
   seen = false,
   dsc = function(s)
	  if not s.seen then
		 s.seen = true
		 return "В ночной тишине мои шаги по металлическим ступенькам пророкотали на всю округу. По крайней мере мне так показалось."
	  else
		 return false
	  end
   end,
   enter = function(s, f)
	  if have "лампа" and _"лампа".fire then
		 here():attr "light"
	  end
	  DaemonStart "монстр"
   end,
   exit = function(s, w)
	  s:attr "~light"
   end,
   obj = {
	  obj {
			-"бочки",
		 nam = "бочки",
		 dsc = function(s)
			local v = "Вдоль западной стены стоят бочки."
			if s.pushed then
			   v = v .. " Одна из них лежит на боку."
			end
			return v
		 end,
		 description = function(s)
			if s:has"open" then 
			   return "Судя по запаху, в бочках хранится керосин."
			else
			   return "Металлические бочки."
			end
		 end,
		 before_Take = "Бочки слишком тяжёлые.",
		 before_Push = "Я не могу толкнуть все бочки.",
		 before_Open = "Мне кажется, что достаточно открыть одну бочку.",
	  }:attr "static,openable",
	  obj {
			-"бочка",
		 nam = "бочка",
		 pushed = false,
		 description = function(s)
			if s:has"open" then 
			   return "Судя по запаху, в бочке хранится керосин."
			else
			   return "Металлическая бочка. Крышка бочки плотно закрыта."
			end
		 end,
		 before_Take = "Бочка слишком тяжёлая.",
		 Push = function(s)
			if not s.pushed then
			   s.pushed = true
			   if s:has "open" then
				  enable "керосин"
				  return "Я опрокинул открытую бочку. Из неё вылился керосин."
			   else
				  return "Я опрокинул одну из бочек."
			   end
			else
			   return "Одна из бочек уже на боку."
			end
		 end,
		 Open = function(s)
			if not s:has "open" then
			   s:attr "open"
			   if s.pushed then
				  enable "керосин"
				  return "Я отвинтил крышку лежащей на боку бочки. Из неё вылился керосин."
			   else
				  return "Я открыл бочку."
			   end
			else
			   return "Одна из бочек уже открыта."
			end
		 end,
	  }:attr "scenery,openable",
	  obj {
			-"керосин",
		 nam = "керосин",
		 dsc = "Рядом с опрокинутой бочкой разлит керосин.",
		 n = 0,
		 fire = false,
		 daemon = function(s)
			if s.n < 4 then
			   s.n = s.n + 1
			else
			   DaemonStop(s)
			   if here() ^ "склад" or here() ^ "терраса_" then
				  walk "смерть2"
			   end
			end
		 end,
		 before_Take = "Мне не во что набрать керосин.",
		 Burn = function(s)
			if not s:isDaemon() then
			   if _"бочка":has "open" and _"бочка".pushed then
				  s.fire = true
				  enable "огонь"
				  DaemonStart(s)
				  return "Я зажёг спичку и бросил её в лужу керосина. Огонь вспыхнул моментально."
			   else
				  return "Так я чудовище победить не смогу."
			   end
			else
			   return "Огонь уже распространяется по складу."
			end
		 end,
	  }:attr "static":disable(),
	  obj {
			-"пламя",
		 nam = "огонь",
		 dsc = "Пламя быстро распространяется по помещению склада.",
		 description = "Горячее и коварное.",
		 before_Take = "Даже если было бы возможно взять огонь, я бы всё равно не стал это делать.",
	  }:disable(),
	  obj {
			-"фигура|монстр|существо",
		 nam = "монстр",
		 alive = true,
		 seen = false,
		 n = 0,
		 dsc = function(s)
			if s.alive then
			   if not s.seen then
				  s.seen = true
				  return "За бочками показалась тёмная фигура."
			   else
				  return "Страшное существо приближается ко мне."
			   end
			else
			   return "Рядом с бочками неподвижно лежит монстр. Надеюсь, он мёртв."
			end
		 end,
		 daemon = function(s)
			if s.alive then
			   if s.n < 4 then
				  s.n = s.n + 1
			   else
				  walk "смерть1"
			   end
			end
		 end,
		 description = function(s)
			local v = "Мельком существо похоже на силуэт человека. Если же приглядеться, то становится понятно, что ничего человеческого в нём нет -- практически чёрная бугрящаяся плоть, наросты на теле, напоминающие щупальца морской твари, отсутствующие глаза и ротовое отверстие."
			if s.alive then
			   v = v .. " Сейчас эта тварь стремительно приближается ко мне."
			end
			return v
		 end,
		 Shoot = function(s)
			if have "револьвер" then
			   s.alive = false
			   _"револьвер".loaded = false
			   return "Я направил револьвер на монстра и нажал на спусковой крючок. Не знаю сколько времени прошло и что конкретно происходило, но я обнаружил себя стоящим рядом с телом монстра, с пустым револьвером. От страха я сам не заметил, как потратил все патроны."
			else
			   return "Мне не из чего стрелять."
			end
		 end,
	  },
	  obj {
			-"плоть",
		 nam = "массив плоти",
		 seen = false,
		 dsc = function(s)
			if not s.seen then
			   s.seen = true
			   return "Свет лампы выхватывает из темноты за бочками гигантский массив тёмной плоти."
			else
			   return "За бочками находится массив тёмной плоти."
			end
		 end,
		 description = "Чёрная пульсирующая масса мерзкой плоти занимает приличную часть склада.",
	  }:attr "animate",
   },
   u_to = "терраса_",
}:attr "~light"

cutscene {
   nam = "смерть1",
   text = function()
	  if _"лампа".fire then
		 return fmt.b(". . .^^") .. "Монстр обхватил меня своими ужасными щупальцами. Моё сознание угасло..."
	  else
		 return fmt.b(". . .^^") .. "Что-то мягкое и скользкое обхватило меня. Моё сознение угасло..."
	  end
   end,
   Next = function()
	  snapshots:restore()
   end,
}

cutscene {
   nam = "смерть2",
   dsc = fmt.b(". . .^^") .. "Пока я топтался на месте, огонь уже полностью распространился по складу. Я не смог выбраться...",
   Next = function()
	  snapshots:restore()
   end,
}

room {
   nam = "конец",
   dsc = "Я прыгнул в воду, течение быстро унесло меня в сторону и на берег я выбрался уже далеко от складов.^^На следующий же день буквально все газеты пестрели заголовками о пожаре на складах, но нигде не упоминалось ни о каких странностях. Со временем воспоминания об увиденном начали блекнуть...^^Пока однажды мне не почудилась в тумане тёмная фигура, лишь отдалённо напоминающая человека.",
   noparser = true,
}
