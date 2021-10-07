--$Name: Урзи$
--$Version: 1.04$
--$Author: Антон Жучков (fireton)$
require "parser/mp-ru"
require "fmt"

if not instead.tiny then 
  require "autotheme"
end  

mp.msg.EMPTY = 'Мяу?'
mp.msg.UNKNOWN_VERB = function(w)
	p ("Урзи не понимает как это — ", iface:em(w), "?")
end
mp.msg.INCOMPLETE_NOUN = function(w)
	if not w then
		p ("Что Урзи должен?")
		return
	end
	p ("Что Урзи должен ", iface:em(w), "?")
end
mp.msg.Attack.LIFE = "Нет. Урзи добрый."
mp.msg.Attack.ATTACK = "Зачем? Урзи не злой."
mp.msg.UNKNOWN_OBJ = "Где? Урзи не видит."
mp.msg.INCOMPLETE = "Нужно больше. Урзи не понял."
mp.msg.Eat.NOTEDIBLE = "Урзи не ест такое."
mp.msg.Talk.SELF = "Глупо."
mp.msg.Talk.NOTLIVE = "Урзи не умеет говорить с {#first/тв}."
mp.msg.Tell.SELF = "Глупо же."
mp.msg.UNKNOWN_WORD = "Урзи ничего не понял."
mp.msg.Touch.LIVE = "Урзи тронул лапкой."
mp.msg.Touch.TOUCH = "Урзи не хочет."
mp.msg.INCOMPLETE_SECOND_NOUN = function(w)
	p ('Урзи должен ', w ,'?')
end
mp.msg.Sleep.SLEEP = "Урзи уже выспался."
mp.msg.Yes.YES = "Урзи не спрашивал."
mp.msg.COMPASS_EXAM_NO = "Ничего необычного там."
mp.msg.Insert.NOTCONTAINER = "Урзи не понимает, как."
mp.msg.Insert.WHERE = "Уже там."
mp.msg.PutOn.WHERE = "Уже там."
mp.msg.Wake.WAKE = "Урзи не спит."
mp.msg.WakeOther.WAKE = "Нанни не спит."
mp.msg.WakeOther.NOTLIVE = "Урзи не знает, как."
mp.msg.Think.THINK = "Говорите Урзи. Урзи слушается."
mp.msg.Swim.SWIM = "Урзи не любит плавать."

function mp:pre_input(str)
	local a = std.split(str)
	if #a <= 1 or #a > 3 then
		return str
	end
	if a[1] == 'в' or a[1] == 'на' or a[1] == 'во' or a[1] == "к" or a[1] == 'ко' then
		return "идти "..str
	end
	if a[1] == 'под' then
		return 'смотреть '..str
	end
	return str
end

function game:before_Walk(w)
	local dir = mp:compass_dir(w)
	if not dir then
		return false
	end
	if dir == 'd_to' or dir == 'u_to' or dir == 'in_to' or dir == 'out_to' then
		return false
	end
	p [[Урзи не знает, куда это. У Урзи лапки.]]
end

function game:Take(w) 
  p [[Урзи не носит.]]
end

Path = Class {
	['before_Walk,Enter'] = function(s) 
    if mp:check_inside(std.ref(s.walk_to)) then 
      return 
    end; 
    walk(s.walk_to) 
  end;
	before_Default = function(s)
		if s.desc then
			p(s.desc)
			return
		end
		p ([[Урзи может пойти в ]], std.ref(s.walk_to):noun('вн'), '.');
	end;
	default_Event = 'Walk';
}:attr'scenery,enterable';

game : dict {
  ["Нанни/жр,ед,од,С"] = {"Нанни/им"};
  ["Урзи/мр,ед,од,С"]  = {"Урзи/им"};
  ["ефо/мр,ед,но,С"] = {"ефо/им"};
}

function init()
  game.dsc = false;
  mp.errhints = false;
  mp.auto_animate = false;

  mp.autohelp = false
  mp.togglehelp = false
  
  pl.word = "Урзи/мр,од,ед,3л"
  move('claws', pl)
  move('tail', pl)
  move('paws', pl)
  move('teeth', pl)
  pl.description = [[Урзи. Пушист и главный тут. Лапки есть и хвост.]]
  pl.hungry = true
end

VerbRemove "#Wear"
VerbRemove "#Disrobe"
VerbRemove "#Remove"
VerbRemove "#SwitchOn"
VerbRemove "#SwitchOff"
VerbRemove "#Sing"
VerbRemove "#Burn"
VerbRemove "#Kiss"
VerbRemove "#Tie"
VerbRemove "#Blow"
VerbRemove "#Consult"
VerbRemove "#Fill"
VerbRemove "#Wave"
VerbRemove "#Buy"

----- Урзи

PartOfCat = Class {
  ["before_Take,Drop,Attack,Throw,ThrowAt"] = function(s)
    p [[Глупо. Часть Урзи же.]]
  end,
  before_Smell = "Пахнет Урзи.",
}:attr 'static';

PartOfCat {
  -"когти/мн|коготь/ед";
  nam = 'claws';
  description = [[Острые. Урзи часто точит.]];
  before_Sharpen = function(s,w) 
    p [[Уже острые.]]
  end
}:attr 'static';

PartOfCat {
  -"лапки,лапы/мн|лапа,лапка/ед";
  nam = 'paws';
  description = [[Мягкие. Урзи ходит и прыгает. Но есть когти.]];
}:attr 'static';

PartOfCat {
  -"хвост";
  nam = 'tail';
  description = [[Длинный и пушистый.]];
  before_PlayWith = function(s) 
    p [[Урзи уже большой.]]
  end
}:attr 'static';

PartOfCat {
  -"зубы/мн|зуб/ед";
  nam = 'teeth';
  description = [[Не видно их.]];
}:attr 'static';

--- verbs

VerbExtend {"#Pull",
  "{noun}/вн {noun}/тв : PullWith",
  "{noun}/тв {noun}/вн : PullWith reverse"
}

VerbExtend{"#Eat",
  "из {noun}/рд : Eat"
}

Verb {"#JumpOn",
  "запрыг/нуть",
  "на {noun}/вн,scene : Climb"
}

VerbExtendWord { "#GetOff", "спрыгн/уть" }

Verb {"#PushExt",
  "столк/нуть,кати/ть",
  "{noun}/тв : Push"
}

Verb {"#Play",
  "[|по]игра/ть",
  "Play",
  "с|со|в {noun}/тв : PlayWith"
}

Verb {"#Bite",
  "[|у]куси/ть,куса/ть,кусь,[|о|по]царап/ать",
  "{noun}/вн,scene : Attack"
}

Verb {"#Meow",
  "[|по|за]мяук/нуть,мяу",
  "Meow",
  "на|в {noun}/рд,live : Talk",
  "{noun}/дт,live : Talk"
}

Verb {"#Sharpen",
  "[|по|за]точи/ть",
  "{noun}/вн : Sharpen"
}

Verb {"#Purr",
  "[|за|по]мурлы/кнуть,мурч/ать,мур",
  "Purr",
  "на|в {noun}/рд : Purr",
  "{noun}/дт,live : Purr"
}

function mp:Sharpen() 
  p [[{#Me} не {#word/уметь,#me,нст} точить {#first/вн}.]]
end

function mp:Meow()
  p [[Мяу!]]
end

function mp:Purr()
  local t = {
    "Мур.",
    "Мрр...",
    "Мур..."
  }
  p (t[rnd(#t)])
end

function mp:PlayWith(w)
  p [[{#Me} не {#word/уметь,#me,нст} играть с {#first/тв}.]]
end

function mp:Play() 
  if pl.hungry then
    p [[Урзи не хочет играть. Урзи хочет есть.]]
  else
    p [[Урзи не может сам с собой.]]
  end  
end

function mp:PullWith(w,s) 
  p [[Урзи не умеет так.]]
end

function mp:EatFrom(w) 
  p [[Ничего съедобного.]]
end

function game:before_PlayWith(w)
  if pl.hungry then
    p [[Урзи не хочет играть. Урзи хочет есть.]]
  else
    return false
  end  
end
----------------------------------------------------------------------------------------------

function start(load)
  -- require("mobdebug").start()
	if not load then
    disable('ball')
		move(pl, 'intro')
	end
end

cutscene {
  nam = 'intro',
  text = {
    [[Урзи спал долго. Какой-то звук и Урзи проснулся. Потянулся. Хорошо. Надо поесть.]];
  },
  next_to = 'couch'
}

room {
  nam = 'main',
  -"светлая/но,светл*|гостиная",
  title = "Светлая",
  enter = function(s,w)
    if w ^ 'intro' then
      p [[{$fmt b|Урзи}, игра на «Паровозик-6»^
      Автор: Антон Жучков  Тестирование: Сергей Можайский и Пётр Косых^
      Если не знаете, как играть, наберите {$fmt em|помощь}.^^
      ]]
    end
  end,
  dsc = function(s)
    p [[Светлая и большая. Урзи любит тут. Спать можно. Играть можно. Высокий тут стоит. И Мягкий тут. Хорошо. Пойти можно в Длинный.]]
  end,
  before_Any = function(s, ev)
		if not pl:inside'couch' then
			return false
		end
		if ev == 'Look' or ev == 'Exam' or ev == 'Exit' or ev == 'GetOff' or ev == 'Sleep' or ev == 'Wake' or ev == 'Walk'
			or ev == 'Jump' or ev == 'JumpOn' or ev == 'Meow' or ev == 'Purr' then
			return false
		end
		p [[Неудобно отсюда. Надо слезть.]]
	end,
  
  before_Walk = function(s,w)
    if not pl:inside'couch' then
			return false
		end
    local dir = mp:compass_dir(w)
    if not dir then
      return false
    end
    if dir == 'd_to' or dir == 'out_to' then
      mp:xaction("GetOff", _'couch')
    else
      return false
    end
  end,
  
  u_to = 'on_table',
  out_to = 'corridor',
  
  obj = {
    
    obj {
      -"высокий,высок*/но|стол|ноги", 
      nam = "table",
      description = [[Высокий. Ноги длинные и твёрдые. Можно запрыгнуть, но Нанни сердится. Урзи всё равно прыгает. Главный тут.]],
      ["before_Enter,Climb"] = function(s)
        walk 'on_table'
      end
    }:attr "static,concealed,enterable,supporter",
    obj {
      -"мягкий,мягк*/но|диван",
      nam = 'couch',
      description = [[Мягкий. Хорошо спать тут.]],
      before_LookUnder = function(s)
        if _'ball'.underCouch then
          p [[Мячик там.]]
        else
          p [[Ничего нет.]]
        end
      end,
      before_Enter = function(s) p [[Урзи прыгнул.]] return false end,
      before_Exit = function(s) p [[Урзи прыгнул вниз.]] return false end,
      after_Enter = function(s) disable('ball') end,
      after_Exit  = function(s) enable('ball') end,
    }:attr "static,concealed,enterable,supporter",
    
    obj {
      -"мячик,мяч",
      nam = 'ball',
      underCouch = false,
      description = function(s)
        p [[Урзин мячик. Урзи иногда играет.]]
        if s.underCouch then
          p [[Под Мягким лежит. Далеко. Не достать. Обидно. Урзи хочет играть!]]
        end
      end,  
      dsc = function(s)
        if s.underCouch then
          return nil
        else  
          return "Мячик тут."
        end  
      end,
      ["before_PlayWith,Attack,Pull,Push,PullWith,Move"] = function(s)
        if s.underCouch then
          p [[Далеко. Не достать.]]
        else
          if pl.hungry then
            p [[Урзи не хочет играть. Урзи хочет есть.]]
          else  
            p [[Урзи ударил лапой. Поиграл. Загнал под Мягкий. Лапа не достаёт. Обидно.]]
            s.underCouch = true
          end  
        end
      end,
      before_Take = function(s)
        if s.underCouch then
          p [[Далеко. Не достать.]]
        else
         return false
        end 
      end
    }
  }
}

room {
  nam = 'on_table',
  -"высокий,высок*/но|стол|ноги",
  title = "На Высоком",
  dsc = "Гладко тут. Урзи не нравится. Иногда бывает вкусное. Сейчас нет.",
  enter = [[Урзи прыгнул.]],
  exit  = [[Урзи прыгнул вниз.]],
  obj = { 'phone' },
  d_to = 'main',
  out_to = 'main',
  ["before_GetOff,Exit"] = function(s) mp:xaction("Walk", _'@d_to') end
}

obj {
  nam = 'phone',
  -"ефо/мр,но|телефон",
  dsc = "Ефо тут.",
  description = "Это ефо. Нанни любит. Часто говорит с ефо. Урзи нельзя ефо. Нанни злится.",
  ["before_PlayWith,Attack,Push,Pull,PullWith,Move"] = function(s)
    if pl.hungry then
      p [[Урзи не хочет играть. Урзи хочет есть.]]
      return
    end
    if not _'ball'.underCouch then
      p [[Можно бы поиграть. Урзи хочет. Но нельзя ефо. Мячик лучше.]]
      return
    end
    if s:inside 'on_table' then
      p [[Нельзя ефо. Но Урзи хочет играть. Главный тут! Ударил лапой. Ефо упал вниз.]]
      move(s, 'main')
      return
    end
    if s:inside 'main' then
      p [[Ударил лапой опять. Ефо убегает! Быстрый. Урзи быстрее. Поймал. Но ефо убежал в Длинный!]]
      move(s, 'corridor')
      return
    end
    if s:inside 'corridor' then
      p [[Нанни тут. Но Урзи играет. Ударил ефо. Ефо прямо к Нанни убежал. Ух, хитрый!]]
      walk 'happyend'
      return
    end
  end
}

-- проход в коридор
Path {
  nam = 'corridor_path';
  -"длинный,длинн*/но|коридор";
  walk_to = 'corridor';
  desc = "Можно пойти в Длинный.";
  found_in = {'main', 'kitchen'};
}

----------------------------------------------------------------------------------------------

room {
  nam = 'corridor',
  -"длинный,длинн*/но|коридор",
  title = "Длинный",
  dsc = [[Это Длинный. Ход тут в Главную. И в Светлую тоже. Ещё в Мокрую. Но туда Урзи не любит.]],
  enter = function(s) _'nanni':daemonStart() end,
  exit  = function(s) _'nanni':daemonStop() end,
  before_Meow = function(s)
    mp:xaction("Talk", _'nanni')
  end,
  obj = {
    Path {
      nam = '#main';
      -"светлая/но,светл*|гостиная";
      walk_to = 'main';
      desc = "Можно вернуться в Светлую."
    },
    Path {
      nam = '#kitchen',
      -"главная/но,главн*|кухня";
      walk_to = 'kitchen';
      desc = "Можно пойти в Главную";
    },
    Path {
      nam = '#bathroom',
      -"мокрая,мокр*/жр,но|ванная";
      ['before_Walk,Enter'] = function(s)
        p "Урзи не пойдёт.";
      end,
      desc = "Там мокро. Урзи не любит.";
    }
  }
}

obj {
  nam='nanni',
  -"Нанни/жр,од",
  description = [[Это Нанни. Любит Урзи. И Урзи любит. Нанни кормит и гладит хорошо. Сейчас Нанни лежит. Устала наверное.]],
  dsc = "У хода в Мокрую Нанни лежит.",
  ["before_Ask,Tell,Say,Talk"] = function(s)
    p [[— Мяу.^]]
    p [[— Урзи... ... кушать ... ...]]
    if not pl.hungry then
      p [[^^Нанни опять не понимает. Урзи уже не голодный.]]
    else
      p [[^^Правильно. Урзи голодный. Обычно Нанни идёт. Но сейчас не идёт. Лежит.]]
    end
    if s:once() then
      p [[^^Урзи слышит звук. Это ефо в Светлой. Нанни тоже слышит.]]
      p [[^— Урзи ... ефо ... ефо — говорит Нанни.]]
      p [[^Урзи знает. Ефо нельзя. Урзи играл. Нанни сердилась. Нельзя ефо.]]
      p[[^^Обычно Нанни идёт к ефо. Сейчас лежит.]]
    end
  end,
  
  before_PlayWith = function(s) 
    if s:once 'play' then
      p [[Урзи попробовал. Тронул лапкой.]]
    end
    p [[Нанни не хочет.]]
  end,
  
  daemon = function(s)
    local t = {
      "Нанни издаёт звук.";
      "Нанни шевелится. Хочет спать?";
      "Урзи нюхает Нанни. Нанни редко так низко. Необычно.";
      "Нанни смотрит на Урзи. Глаза мокрые.";
    }
    if rnd(100) <= 10 then
			pn(t[rnd(#t)])
		end
  end,
  found_in = {'corridor'}
}:attr 'animate';

-----------------------------------------------------------------------------------------------

room {
  nam = 'kitchen',
  -"главная/но,главн*|кухня",
  title = "Главная",
  dsc = [[Это Главная. Урзи кушает тут. Пахнет вкусно. В углу Белый стоит, важный. У хода в Длинный миска тут. Тоже важно.]],
  before_Smell = function(s,w)
    if not w then
      p [[Пахнет вкусным от Белого.]]
    else
      return false
    end
  end,
  out_to = 'corridor'
}: with {'fridge', 'bowl'}

obj {
  -"белый/но,бел*|холодильник",
  nam = "fridge",
  description = function(s) 
    p [[Белый важный очень. Всё вкусное там.]];
    if s:has'open' then
      p [[Белый открыт. Там вкусное. Урзи видит.]]
    end
  end,
  
  before_EatFrom = function(s)
    if s:has 'open' then
      mp:xaction("Eat", _'food')
    else
      p [[Но Белый закрыт!]]
    end
  end,
  
  before_Open = function(s) 
    if s:has'open' then
      p [[Уже открыт.]]
    else
      p [[Очень хочется. Чем?]]
    end
  end,
  
  before_Pull = function(s)
    if s:has'open' then
      mp:xaction("Open",s)
    else
      p [[Чем? У Урзи лапки.]]
    end
  end,
  
  before_Smell = "Пахнет вкусным. Как всегда.",
  
  ["before_Unlock,PullWith"] = function(s,w) 
    if s:has'open' then
      p('Уже открыт.')
    else
      if w ^ 'claws' then
        p [[Урзи умный. Зацепил Белый когтями и потянул. Белый открылся! Вкусное там!]]
        s:attr 'open'
      elseif w ^ 'teeth' then
        p [[Не подлезть.]]
      elseif w ^ 'paws' then
        p [[Не зацепляется.]]
      else
        p [[Урзи не умеет так.]]
      end
    end
  end,
  
  before_Close = [[Зачем?]],
  
  before_Climb = [[Белый гладкий. Урзи прыгал однажды. Упал.]],
  
  obj = {
    obj {
      -"вкусное/но|еда";
      nam = 'food';
      description = [[Разное. Вкусно пахнет.]],
      before_Smell = function(s)
        if pl.hungry then
          p [[Очень вкусно пахнет. Урзи хочет.]]
        else
          p [[Пахнет хорошо. Но Урзи не голодный больше.]]
        end
      end,
      ["before_Eat,Take,Pull,PullWith,Attack"] = function(s) 
        if pl.hungry then
          p [[Урзи съел. Вытащил вкусное. Разбросал немного. Поел.]]
          pl.hungry = false
        else
          p [[Урзи не голодный больше. Урзи поиграл бы.]]
        end
      end,
      before_PlayWith = [[Урзи не играет с едой.]]
    }
  }
}:attr 'static,concealed,openable,container' 

obj {
  nam = 'bowl',
  -"миска,чашка",
  description = [[Урзина миска. Пусто.]],
  before_Smell = "Пахнет вкусно. Но ничего нет. Урзи всё съел.",
  ["before_PlayWith,Move,Push,Pull"] = "Нет. Не игрушка.",
  before_EatFrom = function(s)
    p [[Ничего нет. Урзи всё съел.]]
  end,
  ["before_Taste,Eat"] = function(s) 
    if pl.hungry then 
      p "Немножко вкусно. Но Урзи голодный."
    else
      p "Урзи наелся уже."
    end
  end
}:attr 'static,concealed'

cutscene {
  nam = 'happyend',
  text = {
    [[Нанни взяла ефо. Говорила. Урзи тут был и гладился. Вот.]],
    [[Потом приехали всякие белые и Аша. Аша добрая и гладится и Урзи.^^Урзи сердился на всяких. Пахли необычно и топали. Забрали Нанни.^^Аша осталась. Много кормила Урзи и гладила и мокрая была. Урзи хорошо поел.]],
    "..."
  },
  next_to = 'gossip'
}

cutscene {
  nam = 'gossip',
  text = {
    [[— Про Анну Николаевну слыхала, из восемнадцатой?^^
    — Нет, а что?^^
    — Она ж чуть только богу душу не отдала. Упала у ванной. Инсульт. Так, представляешь, кот ейный, Мурзик, её и спас. Телефон из комнаты притащил. Кто рассказал бы, не поверила!^^
    — Вот же бывает! А ещё говорят, неразумные они. Всё они понимают...^^
    — Это точно...]]
  },
  next_to = 'theend'
}

gameover {
  nam = 'theend',
  title = "Конец",
  dsc = [[Поздравляю! Вы прошли игру. Надеюсь, она вам понравилась.]]
}

function mp:MetaHelp()

	pn("{$fmt b|КАК ИГРАТЬ?}")

	pn([[^Говорите Урзи. Урзи слушается. Как:^
> идти в длинный^
> укусить мячик^
> мяукнуть^
^
Если посмотреть, скажите. Можно "осмотреть", "осм" или нажать "ввод".^
^
Если осмотреть что-то, скажите "осмотреть мячик" или "мячик".^
^
Урзи красивый. Можно "осмотреть себя" и увидеть.^
^
Иногда можно ходить вверх ("вверх" или "вв") или вниз ("вниз" или "вн"). Но редко.
^^
Вот.
]])
end
