--$Name: Урзи$
--$Version: 1.03$
--$Author: Антон Жучков (fireton)$

require "parser/mp-en"
require "fmt"

if not instead.tiny then
  require "autotheme"
end

mp.msg.EMPTY = "Meow?"
mp.msg.UNKNOWN_VERB = function(w)
  return "Imma does not understand how to " .. w
end
mp.msg.INCOMPLETE_NOUN = function(w)
  return "What Imma must " .. w .. "?"
end
mp.msg.Attack.LIFE = "No. Imma is kind."
mp.msg.Attack.ATTACK = "Why? Imma not angry."
mp.msg.UNKNOWN_OBJ = "Where? Imma not see."
mp.msg.INCOMPLETE = "Need more. Imma not understand."
mp.msg.Eat.NOTEDIBLE = "Imma not eat this."
mp.msg.Talk.SELF = "Stupid."
mp.msg.Talk.NOTLIVE = "Imma can't talk with {#first}."
mp.msg.Tell.SELF = "It's stupid."
mp.msg.UNKNOWN_WORD = "Imma not understand."
mp.msg.Touch.LIVE = "Imma touched with paw."
mp.msg.Touch.TOUCH = "Imma not want."
mp.msg.CUTSCENE_HELP = "To continue press {$fmt b|enter} or type {$fmt em|more}."
mp.msg.INCOMPLETE_SECOND_NOUN = function(w)
	p ("Imma must ", w ,"?")
end
mp.msg.Sleep.SLEEP = "Imma slept enough."
mp.msg.Yes.YES = "Imma did not ask."
mp.msg.COMPASS_EXAM_NO = "Nothing unusual."
mp.msg.Insert.NOTCONTAINER = "Imma not know how."
mp.msg.Insert.WHERE = "Already there."
mp.msg.PutOn.WHERE = "Already there."
mp.msg.Wake.WAKE = "Imma not sleeping."
mp.msg.WakeOther.WAKE = "Tally not sleeping."
mp.msg.WakeOther.NOTLIVE = "Imma not know how."
mp.msg.Think.THINK = "Talk to Imma. Imma will do."
mp.msg.Swim.SWIM = "Imma hate swim."

function mp:pre_input(str)
	local a = std.split(str)
	if #a <= 1 or #a > 3 then
		return str
	end
	if a[1] == 'in' or a[1] == 'on' or a[1] == 'into' or a[1] == 'to' or a[1] == 'towards' then
		return "go "..str
	end
	if a[1] == 'under' then
		return "look "..str
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
	pn "Imma not know where it is. Imma has little paws."
end

function game:Take(w)
  pn "Imma not carry."
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
		p ('Imma can go to ', std.ref(s.walk_to):noun('вн'), '.');
	end;
	default_Event = 'Walk';
}:attr'scenery,enterable';



function init()
  game.dsc = false;
  mp.errhints = false;
  mp.auto_animate = false;

  mp.autohelp = false
  mp.togglehelp = false

  pl.word = "Imma/live,male"
  move('claws', pl)
  move('tail', pl)
  move('paws', pl)
  move('teeth', pl)
  pl.description = "Imma. Fluffy and big here. Has paws and tail."
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

-- Proposed update for metaparser

Verb { "#Lie",
	"lie",
	"?down in|into|inside|on {noun}/scene,enterable : Enter" }

VerbExtend{"#Jump",
  "on {noun} : Climb",
  "off : Exit"
}

VerbExtend{"#Open",
  "with {noun}/held {noun} : Unlock"
}

-- End of proposed update

VerbExtend {"#Pull",
  "{noun} with {noun} : PullWith",
}

VerbExtend{"#Eat",
  "from {noun} : Eat"
}

Verb {"#PushExt",
  "roll",
  "{noun} : Push"
}

Verb {"#Play",
  "play",
  "Play",
  "{noun} : PlayWith",
  "with {noun} : PlayWith"
}

Verb {"#Bite",
  "bite,scratch",
  "{noun} : Attack"
}

Verb {"#Meow",
  "meow",
  "Meow",
  "at|to|with {noun}/live : Talk",
  "{noun},live : Talk"
}

Verb {"#Sharpen",
  "sharpen",
  "{noun} : Sharpen"
}

Verb {"#Purr",
  "purr",
  "Purr",
  "at|to|with {noun} : Purr",
  "{noun}/live : Purr"
}

----- Урзи

PartOfCat = Class {
  ["before_Take,Drop,Attack,Throw,ThrowAt"] = function(s)
    p("Silly. Imma's part it is.")
  end,
  before_Smell = 'Smells like Imma.',
}:attr 'static';

PartOfCat {
  -"claws/plural|claw";
  nam = 'claws';
  description = 'Sharp. Imma sharpens often.';
  before_Sharpen = function(s,w)
    pn "Sharp already."
  end
}:attr 'static';

PartOfCat {
  -"paws/plural|paw";
  nam = 'paws';
  description = 'Soft. Imma walks and jumps. But there is claws.';
}:attr 'static';

PartOfCat {
  -"tail";
  nam = 'tail';
  description = 'Long and fluffy.';
  before_PlayWith = function(s)
    pn "Imma not a kitten. Big already."
  end
}:attr 'static';

PartOfCat {
  -"teeth/plural|tooth";
  nam = 'teeth';
  description = 'Not see them.';
}:attr 'static';

function mp:Sharpen()
  pn "{#Me} can not sharpen {#first}."
end

function mp:Meow()
  pn "Meow!"
end

function mp:Purr()
  local t = {
    'Purr.',
    'Mrr...',
    'Purrr...'
  }
  p (t[rnd(#t)])
end

function mp:PlayWith(w)
  pn "{#Me} can not play with {#first}."
end

function mp:Play()
  if pl.hungry then
    pn "Imma want no play. Imma wants eat."
  else
    pn "Imma not play with self."
  end
end

function mp:PullWith(w,s)
  pn "Imma can not do it."
end

function mp:EatFrom(w)
  pn "Nothing edible."
end

function game:before_PlayWith(w)
  if pl.hungry then
    pn "Imma want no play. Imma wants eat."
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
    "Imma slept much. Heard some sound and Imma waked up. Stretched self. Nice. Have to eat.";
  },
  next_to = 'couch'
}

room {
  nam = 'main',
  -"lit|living",
  title = 'Lit',
  enter = function(s,w)
    if w ^ 'intro' then
      p [[{$fmt b|Imma}, a game for «Train-6»^ Author: Anton Zhuchkov,
Testing: Sergey Mozhaiskiy and Petr Kosyh^ If don't know how to play,
type {$fmt em|help}.^^]]
    end
  end,
  dsc = function(s)
	  pn [[Lit and big. Imma likes it here. Can sleep. Can play. High
	  is standing here. And Soft is here. Nice. Can go to Long.]]
  end,
  before_Any = function(s, ev)
		if not pl:inside'couch' then
			return false
		end
		if ev == 'Look' or ev == 'Exam' or ev == 'Exit' or ev == 'GetOff' or ev == 'Sleep' or ev == 'Wake' or ev == 'Walk'
			or ev == 'Jump' or ev == 'JumpOn' or ev == 'Meow' or ev == 'Purr' then
			return false
		end
		pn "Inconvenient from here. Must jump off."
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
      -"high|tall|table|legs",
      nam = "table",
      description = [[High. The legs are long and hard. Can jump on it
      	but Tally don't like. Imma jumps on anyway. Because big here.]],
      ["before_Enter,Climb"] = function(s)
        walk 'on_table'
      end
    }:attr "static,concealed,enterable,supporter",
    obj {
      -"soft|couch|sofa",
      nam = 'couch',
      description = 'Soft. It is nice to sleep here.',
      before_LookUnder = function(s)
        if _'ball'.underCouch then
          pn "Ball is there."
        else
          pn "Nothing is there."
        end
      end,
      before_Enter = function(s) pn "Imma jumped up." return false end,
      before_Exit = function(s) pn "Imma jumped down." return false end,
      after_Enter = function(s) disable('ball') end,
      after_Exit  = function(s) enable('ball') end,
    }:attr "static,concealed,enterable,supporter",

    obj {
      -"ball",
      nam = 'ball',
      underCouch = false,
      description = function(s)
        p("Imma's ball. Imma plays sometimes.")
        if s.underCouch then
				  pn [[It lies under the Soft. Far. Can't reach. Pity! Imma wants to play!]]
        end
      end,
      dsc = function(s)
        if s.underCouch then
          return nil
        else
          return 'Ball is here.'
        end
      end,
      ["before_PlayWith,Attack,Pull,Push,PullWith,Move"] = function(s)
        if s.underCouch then
          pn "Far. Can't reach."
        else
          if pl.hungry then
            pn "Imma want no play. Imma wants to eat."
          else
            pn "Imma hit with paw. Played. Rolled the ball under the Soft. Paw can't reach. Pity."
            s.underCouch = true
          end
        end
      end,
      before_Take = function(s)
        if s.underCouch then
          pn "Far. Can't reach."
        else
         return false
        end
      end
    }
  }
}

room {
  nam = 'on_table',
  -"high|tall|table|legs",
  title = 'On the Tall',
  dsc = [[It is smooth here. Imma don't like. Sometimes tasty here. Not now.]],
  enter = 'Imma jumped up.',
  exit  = 'Imma jumped down.',
  obj = { 'phone' },
  d_to = 'main',
  out_to = 'main',
  ["before_GetOff,Exit"] = function(s) mp:xaction("Walk", _'@d_to') end
}

obj {
  nam = 'phone',
  -"ffo|phone",
  dsc = 'Ffo is here.',
  description = [[It is ffo. Tally likes. Often talks with ffo. Imma
  	should not touch ffo. Tally gets angry.]],
  ["before_PlayWith,Attack,Push,Pull,PullWith,Move"] = function(s)
    if pl.hungry then
      pn "Imma want no play. Imma wants to eat."
      return
    end
    if not _'ball'.underCouch then
      pn "Can play. Imma wants. But should not touch ffo. Ball is better."
      return
    end
    if s:inside 'on_table' then
      pn "Should not touch ffo. But Imma wants to play. Imma big here! Hit with paw. Ffo fell down."
      move(s, 'main')
      return
    end
    if s:inside 'main' then
      pn "Hit with paw again. Ffo runs away! Fast. Imma is faster. Caught. But ffo ran to the Long!"
      move(s, 'corridor')
      return
    end
    if s:inside 'corridor' then
      pn "Tally is here. But Imma plays. Hit ffo. Ffo ran directly to Tally. Eh, tricky ffo!"
      walk 'happyend'
      return
    end
  end
}

-- проход в коридор
Path {
  nam = 'corridor_path';
  -"long|corridor";
  walk_to = 'corridor';
  desc = 'Can go to the Long.';
  found_in = {'main', 'kitchen'};
}

----------------------------------------------------------------------------------------------

room {
  nam = 'corridor',
  -"long|corridor",
  title = 'Long',
  dsc = [[It is Long. There is a way to the Main. And to the Lit. Also
  	to the Wet. But Imma does not like to go there.]],
  enter = function(s) _'nanni':daemonStart() end,
  exit  = function(s) _'nanni':daemonStop() end,
  before_Meow = function(s)
    mp:xaction("Talk", _'nanni')
  end,
  obj = {
    Path {
      nam = '#main';
      -"lit|living";
      walk_to = 'main';
      desc = 'Can return to the Lit.'
    },
    Path {
      nam = '#kitchen',
      -"main|kitchen";
      walk_to = 'kitchen';
      desc = 'Can go to the Main';
    },
    Path {
      nam = '#bathroom',
      -"wet|bathroom";
      ['before_Walk,Enter'] = function(s)
        pn "Imma will not go.";
      end,
      desc = 'Wet there. Imma not like.';
    }
  }
}

obj {
  nam='nanni',
  -"Tally/female,live",
  description = [[It is Tally. Loves Imma. And Imma loves. Tally feeds
  	and pets nicely. Now Tally lies down. Tired probably.]],
  dsc = 'Near the way to the Wet Tally lies.',
  ["before_Ask,Tell,Say,Talk"] = function(s)
    pn "— Meow.^"
    pn "— Imma... ... feed ... ..."
    if not pl.hungry then
      pn "^^Tally does not understand again. Imma is already not hungry."
    else
      p("^^That's right. Imma wants to eat. Usually Tally goes. But now does not go. Lies.")
    end
    if s:once() then
      pn "^^Imma hears a sound. It is ffo in the Lit. Tally hears it too."
      pn "^— Imma ... ffo ... ffo — speaks Tally."
      pn "^Imma knows. Should not touch ffo. Imma played. Tally got angry. Should not touch ffo."
      pn "^^Usually Tally goes to ffo. Now lies."
    end
  end,

  before_PlayWith = function(s)
    if s:once 'play' then
      pn "Imma tried. Touched with paw."
    end
    pn "Tally does not want."
  end,

  daemon = function(s)
    local t = {
      'Tally makes a sound.';
      'Tally moves. Wants to sleep?';
      'Imma smelled Tally. Tally is rarely so low. Unusual.';
      'Tally looks at Imma. Eyes are wet.';
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
  -"main|kitchen",
  title = 'Main',
  dsc = [[It is Main. Imma eats here. Smells tasty. There is White in
	  the corner, important. Near the way to the Long is a bowl. Important
	  too.]],
  before_Smell = function(s,w)
    if not w then
      pn "Smells tasty from White."
    else
      return false
    end
  end,
  out_to = 'corridor'
}: with {'fridge', 'bowl'}

obj {
  -"white|fridge|refrigerator",
  nam = "fridge",
  description = function(s)
    pn "White is very important. All tasty is there.";
    if s:has'open' then
      pn "White is opened. Tasty is there. Imma sees."
    end
  end,

  before_EatFrom = function(s)
    if s:has 'open' then
      mp:xaction("Eat", _'food')
    else
      pn "But White is closed!"
    end
  end,

  before_Open = function(s)
    if s:has'open' then
      pn "Already open."
    else
      pn "Want it very much. But with what?"
    end
  end,

  before_Pull = function(s)
    if s:has'open' then
      mp:xaction("Open",s)
    else
      pn "With what? Imma has paws."
    end
  end,

  before_Smell = 'Smells tasty. As always.',

  ["before_Unlock,PullWith"] = function(s,w)
    if s:has'open' then
      pn "Already open."
    else
		if w ^ 'claws' then
		  pn "Imma is clever. Caught White with claws and pulled. White opened! Tasty is there!"
		  s:attr 'open'
		elseif w ^ 'teeth' then
		  pn "Can not get there."
		elseif w ^ 'paws' then
		  pn "Can not catch White."
		else
		  pn "Imma can not do that."
		end
	end
  end,

  before_Close = 'Why?',

  before_Climb = 'White is smooth. Imma jumped on it once. Fell.',

  obj = {
    obj {
      -"tasty|food";
      nam = 'food';
      description = 'Many things. Smells tasty.',
      before_Smell = function(s)
        if pl.hungry then
          pn "Smells very tasty. Imma wants."
        else
          pn "Smells nice. But Imma is not hungry anymore."
        end
      end,
      ["before_Eat,Take,Pull,PullWith,Attack"] = function(s)
        if pl.hungry then
          pn "Imma ate. Pulled tasty. Threw around some. Ate."
          pl.hungry = false
        else
          pn "Imma does not want to eat more. Imma wants to play."
        end
      end,
      before_PlayWith = 'Imma not play with food.'
    }
  }
}:attr 'static,concealed,openable,container'

obj {
  nam = 'bowl',
  -"bowl,cup",
  description = "Imma's bowl. Empty.",
  before_Smell = 'Smells tasty. But nothing is there. Imma ate everything before.',
  ["before_PlayWith,Move,Push,Pull"] = 'No. Not a toy.',
  before_EatFrom = function(s)
    pn "Nothing here. Imma ate everything."
  end,
  ["before_Taste,Eat"] = function(s)
    if pl.hungry then
      pn "Tasty a little. But Imma wants to eat."
    else
      pn "Imma is not hungry already."
    end
  end
}:attr 'static,concealed'

cutscene {
  nam = 'happyend',
  text = {
    "Tally took ffo. Talked. Imma was there and was petted. Good.",
    [[Later Some Whites came and Asha. Asha is kind and pets
    Imma.^^Imma was angry at Some. Smelled strange and stomped
    loudly. They took Tally.^^Asha stayed. Fed Imma a lot and petted
    and was wet. Imma ate nicely.]],
    "..."
  },
  next_to = 'gossip'
}

cutscene {
  nam = 'gossip',
  text = {
					[[— Did you hear about Natalie, from the eighteenth?^^
            — No, why?^^
            — She’s almost kicked the bucket. Fell down by her bathroom. A stroke. Can you imagine, that cat of hers, Simba, it saved her. It brought her phone from the room. I wouldn’t believe it if someone told me!^^
            — What are the odds? And they say they are not intelligent. They understand everything...^^
            — Exactly...]]
  },
  next_to = 'theend'
}

gameover {
  nam = 'theend',
  title = 'The End',
  dsc = "Congratulations! You have completed the game. Hope you liked it."
}

function mp:MetaHelp()
	pn "{$fmt b|HOW TO PLAY?}"
	pn [[^Talk to Imma. Imma will do. How:^
> go to long^
> bite the ball^
> meow^^

If need to look around, ask it. Can "look", or "examine" or press "enter".^^

If need to look at something, ask "look at ball" or "ball".^^

Imma is handsome. Can "look at self" and see.^^

Sometimes can go "up" and "down". But not often.^^

So.]]
end
