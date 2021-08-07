--$Name: The Archive$
--$Version: 1.0$
--$Author:Peter Kosyh$

require "fmt"
require "link"
if instead.tiny then
	function iface:tab()
		return '    '
	end
end
function mus_play(f)
end
function mus_stop(f)
end
function snd_play(f)
end
function snd_stop()
end
function snd_start()
end

if not instead.tiny then
require "autotheme"
require "timer"
require "sprite"
require "theme"
require "snd"
timer:set(350)
local w, h = sprite.fnt(theme.get 'inv.fnt.name',
	tonumber(theme.get 'inv.fnt.size')):size("|")
local blank = sprite.new(w, h)
local cur_on = false
require "fading"
function game:timer()
	if cur_on or mp.autohelp then
		mp.cursor = fmt.b '|'
	else
		mp.cursor = fmt.top(fmt.img(blank));
	end
	cur_on = not cur_on
	return true, false
end
function mus_play(f)
	snd.music('mus/'..f..'.ogg')
end
function mus_stop(f)
	snd.stop_music()
end

function snd_stop(f)
	if not f then
		instead.stop_sound() -- halt all
	else
		_'sound':stop(f)
	end
end

function snd_play(f, loop)
	if loop then
		_'sound':play(f, 0)
	else
		snd.play ('snd/'..f..'.ogg', -1, 1)
	end
end

obj {
	nam = 'sound';
	sounds = {
	};
	play = function(s, name, loop)
		if s.sounds[name] then
			return
		end
		local chan = {}
		for k, v in pairs(s.sounds) do
			table.insert(chan, v[2])
		end
		table.sort(chan)
		local free
		for k, v in ipairs(chan) do
			if k ~= v then
				free = k
				break
			end
		end
		if not free then
			free = #chan + 1
		end
--		print("play ", name, free)
		s.sounds[name] = { name, free, loop }
		snd.play('snd/'..name..'.ogg', free, loop)
	end;
	start = function(s)
		for k, v in pairs(s.sounds) do
			snd.play('snd/'..v[1]..'.ogg', v[2], v[3])
		end
	end;
	stop = function(s, name)
		if not s.sounds[name] then
			return
		end
--		print("stop ", name, s.sounds[name][2])
		snd.stop(s.sounds[name][2])
		s.sounds[name] = nil
	end;
}
function snd_start()
	instead.stop_sound() -- halt all
	_'sound':start()
	snd.music_fading(1000)
end
end

fmt.dash = true
fmt.quotes = false

require 'parser/mp-en'

function set_pic(f)
	game.pic = 'gfx/'..f..'.jpg'
end

function get_pic(f)
	local r = game.pic:gsub("^gfx/", ""):gsub("%.jpg$", "")
	return r
end

game.dsc = [[{$fmt b|ARCHIVE}^^The interactive mini-novel to
be run on electronic computing devices.^^For instructions type "help" and press "Enter".]];

function game:before_Any(ev, w)
	if ev == "Ask" or ev == "Say" or ev == "Tell" or ev == "AskFor" or ev == "AskTo" then
		p [[Just try to talk.]];
		return
	end
	return false
end

function mp:pre_input(str)
	local a = std.split(str)
	if #a <= 1 or #a > 3 then
		return str
	end
	if a[1] == 'to' or a[1] == 'in' or a[1] == 'into' or
		a[1] == "on" then
		return "walk "..str
	end
	return str
end

Path = Class {
	['before_Walk,Enter'] = function(s)
		if mp:check_inside(std.ref(s.walk_to)) then
			return
		end
		walk(s.walk_to)
	end;
	before_Default = function(s)
		if s.desc then
			p(s.desc)
			return
		end
		p ([[You can go to ]], std.ref(s.walk_to):the_noun(), '.');
	end;
	default_Event = 'Walk';
}:attr'scenery,enterable';

Careful = Class {
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" or
	ev == 'Listen' or ev == 'Smell' then
			return false
		end
		p ("Better be careful with ", s:the_noun(), ".")
	end;
}:attr 'scenery'

Distance = Class {
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" then
			return false
		end
		p ("But ", s:the_noun(), " ", s:hint'plural' and 'are' or 'is', " far away.");
	end;
}:attr 'scenery'

Furniture = Class {
	['before_Push,Pull,Transfer,Take'] = [[Better to leave where
	{#if_hint/#first,plural,they are,it is}.]];
}:attr 'static'

Prop = Class {
	before_Default = function(s, ev)
		p ("You don't care about ", s:the_noun(), ".")
	end;
}:attr 'scenery'

Distance {
	"stars/plural";
	nam = 'stars';
	description = [[The stars are looking at you.]];
}

obj {
	"space,void";
	nam = 'space';
	description = [[Humanity reaching hyperspace did not bring the stars much closer.
	After all, before you build a gate near new star system, you have to get to it.
	A flight to an unexplored star system still takes years or even decades.]];
	obj = {
		'stars';
	}
}:attr 'scenery';

global 'radio_ack' (false)
global 'rain' (true)
global 'know_bomb' (false)

Careful {
	nam = 'windows';
	"windows,portholes/plural";
	description = function(s)
		if here().planet then
			if rain then
				p [[All you see from the cabin is wheat-colored field and the rainy sky.]]
			elseif bomb_cancel then
				p [[How strange, you see no planet landscape!]];
			else
				p [[All you see from the cabin is wheat-colored field and the cyan sky]]
			end
		elseif here() ^ 'burnout' then
			p [[Through thick windows you see the glow of hyperspace.]];
			if not _'engine'.flame then
				_'hyper2':description()
			end
		elseif here() ^ 'ship1' then
			p [[Through thick windows you see a purple planet. It is Dimidius.]];
		end
	end;
	found_in = { 'ship1', 'burnout' };
};

obj {
	"photo|photography";
	nam = 'photo';
	init_dsc = [[There is a photo attached to a window corner.]];
	description = [[A photo of your daughter Lisa, when she was only 9 years old.
	She is all grown up now.]];
	found_in = { 'ship1', 'burnout' };
};

Careful {
	nam = 'panel';
	"dashboard,panel|controls,devices/plural|equipment";
	till = 27;
	stop = false;
	daemon = function(s)
		s.till = s.till - 1
		if s.till == 0 then
			DaemonStop(s)
		end
	end;
	description = function(s)
		if here() ^ 'ship1' or bomb_cancel then
			p [[All ship systems are functional. You may push the thrust lever.]];
		elseif here() ^ 'burnout' then
			if _'burnout'.planet then
				p [[The atmosphere analysis shows the air is breathable.]]
			end
			if _'engine'.flame then
				p [[Fire in engine room!]];
			end
			if s.till > 20 then
				p [[Problems in engine two.]];
			elseif s.till > 15 then
				p [[Engine one and engine two failed. Failure of stabilization system.]];
			else
				p [[All engines are out of order.]]
				s.stop = true
			end
			if _'engine'.flame then
				p [[It's very dangerous!]]
			end
			if s.till and not _'burnout'.planet then
				p ([[^^Time till complete transition is ]], s.till,
	[[ second(s).]])
			end
			_'throttle':description()
		end
	end;
	found_in = { 'ship1', 'burnout' };
	obj = {
		obj {
			"lever,thrust";
			nam = 'throttle';
			ff = false;
			['before_SwitchOn,SwitchOff'] = [[The thrust lever can be pulled or pushed.]];
			description = function(s)
				if here() ^ 'ship1' or bomb_cancel then
					p [[The heavy thrust lever is in neutral position.]];
				elseif here() ^ 'burnout' then
					if s.ff then
						pr [[Thrust is on]];
						if _'panel'.stop then
							pr [[, but the engines are no longer running.]]
						end
						pr '.'
					else
						p [[Thrust is off.]]
					end
				end
			end;
			before_Push = function(s)
				if not radio_ack then
					p [[You completely forgot to contact the traffic control. To do it, the radio should be switched on.]];
				elseif here() ^ 'ship1' then
					s.ff = true
					walk 'transfer'
				elseif here() ^ 'burnout' then
					if bomb_cancel then
						if _'outdoor':has'open' then
							p [[Probably the airlock should be sealed first?]]
							return
						end
						walk 'happyend'
						return
					end
					if not s.ff then
						p [[You moved the lever forward.]]
					end
					s.ff = true
					p [[The lever is set to the maximum thrust.]];
				end
			end;
			before_Transfer = function(s, w)
				if w == pl then
					return mp:xaction("Pull", s)
				end
				return false
			end;
			before_Pull = function(s)
				if here() ^ 'ship1' then
					return false
				elseif here() ^ 'burnout' then
					if s.ff and not bomb_cancel then
						if not _'panel'.stop then
							p [[It is possible to exit hyperspace only when the ship reaches a certain speed.
							Stopping the engines would mean an aborted transition. And then -- there's no way out!]];
							return
						end
						p [[You pull the lever.]]
					end
					s.ff = false
					p [[The thrust lever is in neutral position.]]
				end
			end;
		}:attr'static';
		obj {
				"radio";
			description = [[The radio is built into the dashboard.]];
			before_SwitchOn = function(s)
				if s:once() then
					--mus_stop()
					snd_play 'sfx_radio'
					p [[-- Dimidius,
board FL510, 51-Peg gate, ready for transition.^
-- ...Board FL510, 51-Peg gate, cleared for transition.^
-- Cleared for transition, 51-Peg gate, board FL510.]];
					radio_ack = true;
				elseif here() ^ 'burnout' then
					if _'burnout'.planet then
						p [[You're getting radio interference. You turn off the radio.]]
					else
						p [[Radio cannot work in hyperspace.]]
					end
				else
					p [[You have already received the transition clearance.]]
				end
			end;
		}:attr 'switchable,static';
	};
}:attr'supporter';
cutscene {
	nam = 'happyend';
	enter = function(s)
		set_pic 'hyper'
		if have 'photo' then
			pn [[You take out your daughter's photo and mount it to a window corner. Then, you put your hand on the thrust lever.]];
		else
			pn [[You put your hand on the thrust lever.]]
		end
	end;
	text = function(s, n)
		local t = {
		[[You push the lever away to the maximum position.]];
		[[The flashes of hyperspace outside the window come to life...^
The countdown begins (or continues?) on the dashboard.]];
		[[25, 24, 23...]],
		[[10, 9, 8, 7...]],
		[[3, 2, 1...]];
		[[I'll be back soon!]];
		};
--		if n == 6 then
--			snd_play 'sfx_explosion_3'
--		end
		return t[n]
	end;
	next_to = 'titles';
}

cutscene {
	noparser = true;
	nam = 'titles';
	title = false,
	enter = function(s)
		if not instead.tiny then
			fading.set { 'fadewhite', delay = 60, max = 64 }
		end
		set_pic 'crash'
		mus_play 'jump-memories'
	end;
	dsc = fmt.c[[{$fmt b|ARCHIVE}^
{$fmt em|Peter Kosyh / May 2020}^
{$fmt em|Translation: prirai, canwolf, Khaelenmore Thaal}^
{$fmt em|Music, sound: Alexander Soborov}^
{$fmt em|Jump Memories / Keys of Moon}^
{$fmt em|Testing: Khaelenmore Thaal, Oleg Bosh}^
Thank you for playing this little game!^
If you liked it, you can find similar games at:^^
{$link|http://instead-games.ru}^
{$link|https:/parser.hugeping.ru}^
{$link|https://instead.itch.io}^^
And if you would like to write your own story,^welcome to:^
{$link|https://instead.hugeping.ru}^^
{$fmt b|THE END}
]];
}

room {
	"cabin|control room,room|cockpit|Frisky|ship|spaceship";
	title = "control room";
	nam = 'ship1';
	dsc = [[The cabin of Frisky is cramped. Through the narrow windows, the oblique rays of star 51-Peg
	penetrate into the cockpit illuminating the dashboard.
	Straight ahead are transit gates floating over Dimidius.^^
	Everything is set up to begin the transition. Nevertheless you wish to take
	another look at the dashboard.]];
	out_to = function(s)
		p [[It is not the time for walking on the ship. You are getting ready to make the transition. All the instruments are in control room.]]
	end;
	obj = {
		'space',
		'panel',
		Distance {
			"star|sun|Peg";
			description = [[It has been known for a long time that an exoplanet
			similar to the Earth orbits around 51-Peg.
			But only in 2220 the hyperspace gates were opened here.
			The Earth is 50 light years or 4 transition jumps away.
			120 years of human expansion into deep space...]];
		};
		'windows';
		Distance {
			"planet|Dimidius";
			description = [[
Dimidius became the first planet reached with living conditions fit for humans.^^
As soon as the gates have been installed here in 2220, pioneers rushed to Dimidius in search of a new life.
And 5 years later the richest deposits of uranium were discovered on the planet.
The old world suffered from the lack of resources, but money and power were concentrated there.
Therefore, Dimidius was not destined to become the New Earth.
It turned into a colony.^^
Your six-month contract for Dimidius is over, it's time to return home.]];
		};
		obj {
			"rays/plural";
			description = [[Rays of the local sun slide across the dashboard.]];
		}:attr'scenery';
		Distance {
			"gates/plural|transition";
			description = function(s)
				if s:once() then
					p [["The gates" -- the entrance to hyperspace is called so.
					The gates look like a 40-meter ring slowly rotating in the void.
					The 51-Peg gates were opened in 2220.
					They had become the 12th gates built during the 125-year history of humanity's expansion into deep space.]];
				else
					p [[You see flashes of hyperspace through the gates.]];
				end
			end;
			obj = {
				Distance {
					"hyperspace|flashes/plural";
					description =
						[[Hyperspace was discovered in 2095 during experiments on the BSR.
						It took another 4 years to find a way to synchronize the continuum
						between exit points from hyperspace.]]
				}:attr 'scenery';
			}
		};
	}
}

cutscene {
	nam = "transfer";
	title = "Transition";
	enter = function()
		set_pic "hyper"
	end;
	text = function(s, i)
		local txt = {
		[[Before placing your hand on the massive lever, you looked at your daughter's photo.^
-- Well, God help us...^^
		You carefully move the massive lever forward and watch the gates approach.
		You have done it other times in your 20-year career.
		The ship shudders, the gigantic force pulls it in and -- behold, you are observing the bizarre intertwining of lights.
		Just a few seconds and... ]];
		[[BAM!!! The vibration shakes the ship. Is something wrong?]];
		[[The vibration increases. Bang! Another one! The dashboard blooms with scattering lights.]];
		};
		if i == 2 then
			mus_stop()
			snd_play('sfx_ship_malfunction_ambience_loop', true)
			snd_play 'sfx_explosion_1'
			snd_stop('sfx_ship_ambience_loop')
			snd_stop('sfx_ready_blip_loop')
		elseif i == 3 then
			mus_play 'bgm_emergency'
			snd_play('sfx_siren_loop', true)
			snd_play 'sfx_explosion_2'
		end
		return txt[i]
	end;
	next_to = 'burnout';
	exit = function(s)
		DaemonStart 'panel'
		if _'photo':has 'moved' and not have 'photo' then
			move('photo', 'burnout')
		end
	end;
}
function start_ill()
	--[[
	if _'planet':once 'ill' and _'suit':hasnt 'worn' then
		DaemonStart 'planet'
	end
	]]--
end
room {
	"cabin|control room|room|cockpit|Frisky|ship|spaceship";
	title = "control room";
	nam = 'burnout';
	planet = false;
	transfer = 0;
	exit = function(s)
		if _'engine'.flame then
			snd_stop 'sfx_siren_loop'
			snd_play ('sfx_siren_dampened_loop', true)
		else
			snd_stop 'sfx_ship_ambience_loop'
		end
	end;
	enter = function(s)
		if _'engine'.flame then
			snd_stop 'sfx_siren_dampened_loop'
			snd_play ('sfx_siren_loop', true)
		elseif not s.planet then
			snd_stop 'sfx_ship_malfunction_ambience_loop'
			snd_play ('sfx_ship_ambience_loop', true)
		end
		if bomb_cancel then
			if s:once 'wow' then
				p [[Entering the control room, you noticed something strange.
				Instead of landscape, you see hyperspace through the windows!]];
				_'panel'.stop = false
				place 'hyper2'
				remove 'sky2'
			end
		end
	end;
	daemon = function(s)
		if here() ~= s then
			return
		end
		local txt = {
			"The lights illuminate the control room.";
			"White light fills the control room.";
			"A dazzling white light filled the control room.";
		};
		s.transfer = s.transfer + 1
		pn(fmt.em(txt[s.transfer]))
		if s.transfer > 3 then
			s:daemonStop()
			walk 'transfer2'
		end
	end;
	Listen = function(s)
		if _'engine'.flame then
			p [[The sound of alarm fills the control room.]]
		else
			return false
		end
	end;
	dsc = function(s)
		if s.planet then
			if rain then
				p [[It's light in the cabin of Frisky.
				The dashboard is faintly reflected in the rain-covered window.]];
			else
				if bomb_cancel then
					p [[The cabin of Frisky is cramped.
					Through the windows you see the glow of hyperspace.]]
					p [[All ship systems are functional.]]
				else
					p [[It's light in the cabin of Frisky.
					Through the windows you can see golden yellow field under the clear sky.]];
				end
			end
		elseif _'engine'.flame then
			p [[Control room is filled with the sound of alarm.
			You have to examine the dashboard to find out what happened.]];
		else
			p [[The cabin of Frisky is cramped.
			Through the windows you see the glow of hyperspace.
			The dashboard blinks softly in the dim light.]]
			if not _'engine'.flame and _'panel'.stop and
			not isDaemon('burnout') then
				p [[^^{$fmt em|You notice something strange outside the windows...}]]
			end
		end
		p [[^^You may exit the control room.]]
	end;
	out_to = 'room';
	obj = {
		Distance {
			nam = 'hyper2';
			"hyperspace,someth*,strang*|lights/plural|radiance";
			description = function(s)
				if not _'engine'.flame and _'panel'.stop then
					p [[You see three sparkling dancing lights approaching your ship.
					Or are you moving towards them?]]
					enable '#trinity'
					DaemonStart("burnout");
					set_pic 'trinity'
					snd_play ('sfx_blinding_lights', true)
				else
					p [[The transition is not yet complete.
					The thought prevents you from enjoying the magnificent view.]];
				end
			end;
			obj = {
				Distance {
					nam = '#trinity';
						"light";
					description = [[A dazzling white light fills the cabin.]];
				}:disable();
			};
		};
		'panel';
		'windows';
	};
}
_'@u_to'.word = "up,above,upstairs" -- add upstairs

room {
	"cargo hold,hold";
	title = 'cargo hold';
	nam = 'storage';
	u_to = function(s)
		if ill > 0 then
			p [[You don't have the strength to go upstairs.]]
			return
		end
		return  'room';
	end;
	dsc = [[From here you can go upstairs or exit to the airlock.]];
	out_to = 'gate';
	obj = {
		Path {
			"airlock";
			walk_to = 'gate';
			desc = [[You can exit to the airlock.]];
		};
		Furniture {
			"containers,boxes/plural|cargo|equipment";
			description = [[There are containers with equipment.]];
			before_Open = [[The containers are sealed.
			You shouldn't open them.]];
		}:attr'openable';
	};
}

door {
	"door,airlock door,gateway door";
	nam = 'outdoor';
	['before_Close,Open,Lock,Unlock'] = [[The door is opened and closed with a lever.]];
	door_to = function(s)
		if here() ^ 'gate' then
			return 'planet'
		else
			return 'gate'
		end
	end;
	description = function()
		p [[Massive airlock door.]];
		return false
	end;
	obj = {
		obj {
			"red lever,lever";
			nam = '#lever';
			description = [[A bright red massive lever.]];
			dsc = [[To the right of the door is a red lever.]];
			before_Pull = function(s)
				if not _'burnout'.planet then
					p [[To open the airlock door during the transition? It is suicide!]]
					return
				end
				if _'outdoor':has'open' then
					_'outdoor':attr'~open'
					p [[With a hissing sound, the airlock closed.]]
					if not onair then
						snd_stop 'sfx_rain_loop'
					end
					snd_play 'sfx_door_opens'
					if bomb_cancel and here() ^ 'gate' then
						mus_play 'the_end'
					end
				else
					_'outdoor':attr'open'
					p [[With a hissing sound, the airlock opened.]]
					if rain then
						snd_play ('sfx_rain_loop', true)
					end
					snd_play 'sfx_door_opens'
					start_ill()
				end
			end;
		}:attr 'static';
	}
}:attr 'locked,openable,static,transparent';
global 'onair' (false)
room {
	"airlock,gateway";
	nam = 'gate';
	title = "airlock";
	dsc = [[You are in the airlock.^^
		You can return to the cargo hold or go outside.]];
	in_to = "storage";
	out_to = "outdoor";
	enter = function(s, from)
		if rain and _'outdoor':has'open' then
			snd_play ('sfx_rain_loop', true)
		end
	end;
	exit = function(s, to)
		onair = not (to ^ 'storage')
		if not onair then
			snd_stop ('sfx_rain_loop')
		end
	end;
	obj = {
		obj {
			"closet,cabinet,wardrobe";
			locked = true;
			description = function(s)
				p [[It is a spacesuit closet.]]
				return false
			end;
			obj = {
				obj {
					"spacesuit,suit,space suit";
					nam = "suit";
					description = [[The suit looks massive, but it's actually quite light.]];
					before_Disrobe = function(s)
						if here().flame then
							p [[And suffocate in fire?]]
							return
						end
						return false
					end;
					after_Disrobe = function(s)
						if onair and s:once 'skaf' then
							p [[Not without fear you take off your spacesuit.
							You take a deep breath. Everything seems to be alright!]];
							start_ill()
						elseif here() ^ 'gate'
							and _'outdoor':has 'open' then
							start_ill()
							return false
						else
							return false
						end
					end;
				}:attr'clothing';
			};
		}:attr 'static,openable,container';
		'outdoor',
		Path {
			"cargo hold,hold,cargo";
			walk_to = 'storage';
			desc = [[You can return to the cargo hold.]];
		};
	};
}
room {
	"corridor,hallway";
	title = 'corridor';
	nam = 'room';
	dsc = [[From here you can get to the control room and to the engine room]];
	d_to = "#trapdoor";
	before_Sleep = [[It's not the time to sleep.]];
	before_Smell = function(s)
		if _'engine'.flame then
			p [[It smells like burning.]];
		else
			return false
		end
	end;
	obj = {
		Furniture {
			"bed";
			description = [[Standard bed.
			You can find it in almost every small vessel, such as Frisky.]];
		}:attr 'enterable,supporter';
		door {
			"trapdoor,hatch,door";
			nam = "#trapdoor";
			description = function(s)
				p [[The trapdoor leads down.]]
			end;
			door_to = 'storage';
		}:attr 'static,openable';
		Prop { "wall|walls/plural" };
		obj {
			"fire extinguisher,extinguisher,balloon,fire bottle";
			full = true;
			init_dsc = [[A fire extinguisher is attached to the wall.]];
			nam = "огнетушитель";
			description = function(s)
				p [[A bright-red tank.
				Designed specifically for space fleet usage.]];
				if not s.full then
					p [[The fire extinguisher is empty.]]
				end
			end;
		};
		Path {
			"cabin,cockpit,control room";
			walk_to = 'burnout';
			desc = [[You can go to the control room.]];
		};
		Path {
			"engines/plural|engine|engine room";
			walk_to = 'engine';
			desc = [[You can go to the engine room.]];
		};
	}
}

room {
	"engine room,room";
	title = "engine room";
	nam = 'engine';
	flame = true;
	before_Smell = function(s)
		if s.flame then
			p [[Smells like burning.]];
		else
			return false
		end
	end;
	onenter = function(s)
		if s.flame and _'suit':hasnt 'worn' then
			p [[There's fire in the engine room!
			You cannot enter because of acrid smoke.]]
			return false
		end
	end;
	dsc = function(s)
		if s.flame then
			p [[Fire is burning in the engine room! Smoke is everywhere!]];
		elseif bomb_cancel then
			p [[You are in the engine room.
			The control unit blinks with indicators.]]
		else
			p [[You are in the engine room.
			The burned-out control unit is completely destroyed.]]
		end
		p [[^^You can exit the engine room.]]
	end;
	out_to = 'room';
	after_Exting = function(s, w)
		if not s.flame then
			p [[The fire has already been extinguished.]]
			return
		end
		if not w or w ^ '#flame' or w == s or w ^ '#control' then
			_'огнетушитель'.full = false
			s.flame = false
			p [[You fight the flames fiercely.
			Finally, the fire is extinguished!]]
			remove '#flame'
			mus_stop()
			snd_stop 'sfx_siren_dampened_loop'
		else
			return false
		end
	end;
	obj = {
		obj {
			nam = '#flame';
			"fire,flame|flames/plural|smoke";
			["before_Attack,Take"] = function(s)
				mp:xaction("Exting")
			end;
			before_Exting = function()
				return false
			end;
			before_Default = [[Fire in the engine room!]];
		}:attr 'scenery';
		obj {
			nam="#control";
			"control unit,unit,indicator*";
			description = function(s)
				if here().flame then
					p [[The control unit is in flames!]];
				elseif bomb_cancel then
					p [[The control unit is functional!]]
				else
					p [[The control unit is the ship's engine control system.
					It's burned-out, but not that gets your attention.
					There's a hole in the center of the unit!]];
					enable '#дыра'
					if _'осколки':has 'concealed' then
						_'осколки':attr
						'~concealed';
						p [[^^You notice the shards.]]
					end
				end
			end;
			obj = {
				obj {
					nam = '#дыра';
					"hole";
					description = function()
						p [[It looks like there was an explosion...]];
						return false;
					end;
					before_LetIn = function(s, w)
						if w == pl then
							p [[Too narrow for you.]]
							return
						end
						return false
					end;
				}:attr 'scenery,container,open,enterable':disable();
			};
		}:attr 'static,concealed';
		obj {
			nam = 'осколки';
			"shards,fragments,debris/plural";
			after_Smell = [[A strange smell...]];
			after_Touch = [[The edges are melted. Doesn't look like duralumin.]];
			description = function(s)
				if have(s) then
					p [[Melted shards. They are heavy.
					Strange, it doesn't look like duralumin...]];
				else
					p [[Small black pieces of metal.]]
				end
			end;
		}:attr 'concealed';
		Path {
			"corridor,hallway";
			walk_to = 'room';
			desc = [[You can go out to the corridor.]];
		};
	}
}

Distance {
	nam = "sky2";
	"sky,turquoise|rain|haze";
	description = function(s)
		if rain then
			p [[The sky is covered with rainy haze.]]
		else
			p [[The sky is clear, shines with blue turquoise.]]
		end
		p [[From time to time, the sky lights up with flashes.]];
	end;
	before_Listen = function(s)
		if rain then
			p [[You hear the sound of the rain.]];
			return
		elseif s:multi_alias() == 2 then
			p [[But the rain is over!]]
			return
		end
		p [[You do not hear anything unusual.]]
	end;
	obj = {
		Distance {
			"hyperspace|flashes/plural";
			description = [[A planet in hyperspace? Incredible!]];
		};
		obj {
			"sun,star";
			before_Default = [[Strange but you can't see the sun, although it is day.]];
		}:attr 'scenery';
	}
};

Distance {
	nam = 'planet_scene';
	"planet|landscape|field,wheat|horizon";
	description = function()
		if rain then
			p [[The edges of a wheat-golden field hide in the rainy haze.]];
		else
			p [[The golden wheat field stretches to the horizon..]];
		end
	end;
	obj = {
		'sky2';
		obj {
			"drops,droplets/plural";
			description = function(s)
				if rain then
					p [[For a while, you absentmindedly watch the droplets rolling down the glass.]];
				else
					p [[But it's not raining now.]]
				end
			end;
		}:attr'scenery';
	};
}

cutscene {
	nam = "transfer2";
	title = "...";
	enter = function(s)
		snd_play 'sfx_explosion_3'
		snd_stop 'sfx_blinding_lights'
		snd_stop 'sfx_ship_malfunction_ambience_loop'
		set_pic 'flash'
	end;
	text = {
		[[The blinding light filled everything around.
		You are lost in it, dissolved -- as if you never existed ...
		The ship shudders from impact. Is it the end?]];
		[[Silence...]];
		[[Drops of water on the glass. Big drops.
		They slowly flow down the slanted windows, cover the ship's shell.
		The noise of the rain -- why can't you hear it?]];
	};
	exit = function(s)
		_'burnout'.planet = true
		remove 'hyper2'
		p [[You slowly come to your senses.
		Well, of course, you are still inside Frisky and its casing will not pass such a faint sound as raindrops falling. What a pity...]];
		move('planet_scene', 'burnout')
		set_pic 'crash'
		mus_play 'bgm_plains'
	end;
}

obj {
	nam = 'ship';
	"ship,Frisky,frisk*";
	description =  function(s)
		p [[Not too soft landing, judging by the furrow the ship left behind in the ground.
		But the ship survived!]]
	end;
	before_Enter = function(s)
		mp:xaction("Enter", _'outdoor')
	end;
	obj = {
		obj {
			"furrow,track";
			description = [[Not very deep.
			Somehow, the ship was thrown right into the field...]];
		}:attr'scenery';
	}
}:attr 'scenery,enterable';

obj {
	nam = 'wheat';
	"grains/plural|grain";
	description = [[Large yellow grains, similar to wheat.
	You feel energy concentrated in them.]];
	['after_Smell'] = function(s)
		if rain then
			p [[You like the smell of wet grain.]];
		else
			p [[You like the smell of grain.]];
		end
	end;
	after_Eat = function(s)
		if ill > 0 then
			DaemonStop 'planet'
			if ill > 1 then
				p [[You eat the grains. After a while, you feel the strange weakness recede.]]
				ill = 0
				return
			end
			ill = 0;
		end
		return false
	end;
}:attr 'edible'

obj {
	nam = 'field';
	title = "In the field";
	"field";
	description = function(s)
		if rain then
			p [[The edges of the field having golden wheat color hide in a rainy haze.]]
		else
			p [[The field looks endless.]]
		end
		p [[You watch wheat-like ears sway in the gentle wind.]];
		return false
	end;
	obj = {
		obj {
			"ears,spiklets/plural|wheat";
			description = [[You watch the ears sway in the gentle wind.]];
			["before_Eat,Tear,Take,Pull"] = function(s)
				p [[You plucked a few spikelets and rubbed them in your palms, collecting the grains.]];
				take 'wheat'
			end;
		}:attr 'concealed';
	};
	before_LetIn = function(s, w)
		if w == pl and here() ^ 'planet' then
			p "You wade in a thicket of yellow ears."
			move(pl, s)
			return
		end
		return false
	end;
--	scope = { 'ship' };
	after_LetIn = function(s, w)
		p ([[You drop ]], w:the_noun(), [[ in the field.]])
	end;
}:attr 'scenery,enterable,container,open'

global 'ill' (0)

room {
	nam = 'planet';
	title = "By the ship";
	in_to = 'outdoor';
	after_Listen = function(s)
		if rain then
			p [[You hear raindrops drumming on the hull of the ship.]]
			return
		end
		return false
	end;
	daemon = function(s)
		local txt = {
			"Suddenly you feel weak.";
			"You feel weakness in your whole body.";
			"A strange weakness intensifies.";
			"You feel terribly tired.";
		};
		ill = ill + 1
		local i = ill - 1
		if i > #txt then i = #txt end
		if i <= 0 then
			return
		end
		p (fmt.em(txt[i]))
	end;
	onenter = function(s)
		start_ill()
	end;
	dsc = function(s)
		p [[You stand by Frisky, its nose buried in the ground in the middle of golden-yellow field.]]
		if rain then
			p [[It's raining.]];
		end
		p [[Nearby to the east you see a tree.]];
		p [[To the north you notice a tall tower with its spire directed up to the sky.]];
	end;
	n_to = 'tower';
	e_to = '#tree';
	obj = {
		'sky2';
		'outdoor';
		'ship';
		'field';
		'tower';
		door {
			nam = '#tree';
			"tree,branch*";
			description = [[A lonely tree seems completely redundant here.]];
			door_to = 'tree';
		}:attr 'scenery,open';
	}
}

Distance {
	"spire|tower,top";
	nam = 'tower';
	["before_Enter,Walk"] = function()
		if ill > 0 then
			p [[You won't be able to walk that far in such state.]]
			return
		end
		walk 'шпиль';
	end;
	description = function(s)
		if rain then
			p [[Tower's top is lost in the haze of rain.]]
		else
			p [[The tower is very high. Like a thin black needle, it pierces the sky.]];
		end
	end;
};

room {
	nam = "шпиль";
	"green plain,plain";
	title = "By the spire";
	before_Listen = [[You hear the wind singing.]];
	before_Shout = [[You scream, but nothing happens.]];
	dsc = function(s)
		p [[You are at the foot of a tall tower.
		Its black spire is directed to the sky.
		Green plain stretches all around.
		A lone tree grows to the west of the tower.]];
		if not disabled 'human' then
			p (fmt.em [[You see a dark human figure in a cloak next to the tree!]])
		end
		p [[^^You can go back south.]];
	end;
	exit = function(s, t)
		if t ^ 'planet' then
			p [[You left the strange tower and headed south to your ship.]];
			set_pic 'crash'
			if rain then
				p [[As you walked, the sky cleared and the rain ended.]];
				rain = false
				snd_stop 'sfx_rain_loop'
			end
		elseif t ^ 'tree' then
			set_pic 'sky'
		end
	end;
	enter = function(s, f)
		if f ^ 'planet' then
			p [[You headed north.
			It took at least half an hour before you found yourself at the foot of the strange building.]];
			if rain then
				p [[As you walked, the sky cleared and the rain ended.]];
				rain = false
				snd_stop 'sfx_rain_loop'
			end
		end
		set_pic 'neartower'
	end;
	s_to = "planet";
	in_to = '#tower';
	w_to = '#tree';
	obj = {
		'sky2';
		Distance {
			nam = 'human';
			"man,human/live,male|figure",
			description = [[You can't see from here but
			it seems to be a man! He pays no attention to you.]];
		};
		obj {
			nam = '#tower';
			"tower|spire|foot";
			description = [[The tower surface is matt, black, without a single seam.
			Looks like metal.]];
			before_Touch = [[You feel vibration.]];
			before_Attack = [[The strength is too unequal.]];
			before_Enter = function(s)
				p [[You walked around the foot of the tower, but you never noticed any entrance.]]
			end;
		}:attr 'scenery,enterable';
		door {
			nam = '#tree';
			"tree,branch*,leaves*,leaf*";
			description = function()
				p [[The tree looks old.
				Its huge gnarled branches are almost devoid of leaves.]];
			end;
			door_to = 'tree';
		}:attr 'scenery,open';
	};
}

room {
	"seashore,shore";
	nam = 'sea';
	title = "By the sea";
	old_pic = false;
	before_Listen = [[The sound of the sea caresses your ears.]];
	before_Smell = [[The smell of salt and algae makes you dizzy.]];
	before_Swim = [[It is not the best time for this.]];
	dsc = [[You are standing on the seashore.
	To the south of you, right on the shore, a strange tree grows.]];
	s_to = '#tree';
	out_to = '#tree';
	exit = function(s)
--		set_pic(s.old_pic)
	end;
	enter = function(s, f)
		if get_pic() ~= 'sky' then
			s.old_pic = get_pic()
			set_pic 'sky'
		end
		snd_stop 'sfx_rain_loop'
		mus_stop()
		snd_play ('sfx_ocean_waves_loop', true)
	end;
	obj = {
		door {
			nam = '#tree';
			"tree,branch*";
			description = [[A lonely tree seems completely redundant here.]];
			door_to = 'tree';
		}:attr 'scenery,open';
		obj {
			"sea|water,seawater";
			description = [[Endless space.
			Waves rolling one over another, foaming and breaking at the shore.]];
			before_Drink = [[To drink seawater?]];
		}:attr 'scenery';
		obj {
			"waves/plural";
			description = [[You can watch the waves crash on the shore forever.]];
		}:attr 'scenery';
		'sky2';
	};
}

obj {
	"old man,man,human";
	nam = 'oldman';
	init_dsc = function(s)
		if visited 'oldman_talk' then
			p [[The old man is waiting for an answer from you: {$fmt em|yes}
or {$fmt em|no}?]];
		else
			p [[You see an old man standing at the very edge and looking into the distance.]];
		end
	end;
	description = [[The old man's wrinkled face is hidden by almost completely white beard.
	He is wearing a long hooded black cloak, which now does not cover his head and his gray hair flutters freely in the wind.]];
	before_Talk = function(s)
		walk 'oldman_talk';
	end;
	['before_Attack,Push'] = function(s)
		if visited 'oldman_talk' then
			p [[You should not do that, my friend! -- the old man raised his hand warningly.]]
		else
			p [[The old man raised his hand warningly and shook his head reproachfully.]]
		end
	end;
}
cutscene {
	title = false;
	nam = 'oldman_talk';
	text = {
		[[-- Hello! I don't know if you understand me or not, but ... um ... who are you?^]];
		[[The old man turned his head in your direction and smiled.^
		You had no choice but to smile back.
		You stood like that for a while.]];
		[[-- I am a human from Earth like you are.
		And I am one of the Archive keepers.]];
		[[-- What is the Archive?]];
		[[-- My friend, if I answer this question, you will stay here forever.
		Once you learn the essence of what is happening, the way back will be closed for you.
		So I have to ask you, are you ready to become one of us? {$fmt em|Yes} or {$fmt em|no}?]];
	}
}

cutscene {
	title = false;
	nam = 'oldman_talk2';
	text = {
		[[-- I thought so.^^
With these words the old man got up and walked slowly towards the tree.^^
--  Well, despite the fact you are not able to enter the Archive dimension, anyhow your consciousness is trying to convey it through familiar images, and therefore, you can change a lot while you are here ...]];
		[[-- While I'm here?]];
		[[But the old man did not answer. He has already disappeared behind the trunk of the strange tree.]];
	}
}

room {
	"cliff,rock,edge*";
	nam = 'rock';
	title = "By the rocky cliff";
	before_Listen = [[You hear the whistle of the wind in the rocks.]];
	yes = 0;
	before_Jump = [[Decided to solve all problems at once?]];
	last = [[-- So I have to ask you, are you ready to become one of us?]];
	['before_Yes,No'] = function(s)
		if not visited 'oldman_talk' or not seen 'oldman' then
			return false
		end
		local txt = {
			{ "-- Are you sure?", "Yes" };
			{ [[-- In that case, you won't be able to return to the world you are used to. Do you really want it?]], "Yes" };
			{ [[-- Have you thought well?]], "Yes" };
			{ [[-- Do you want to learn the secret?]], "Yes" };
			{ [[-- You think you are ready to experience the reality?]], "Yes" };
			{ [[-- Do you consider this as your calling?]],
				"Yes" };
			{ [[-- Are you not afraid to regret your choice?]],
				"Yes" };
			{ [[-- Do you think it is just a lousy adventure game?]], "No" };
			{ [[-- But now it was insulting. And you still insist?]], "Yes" };
			{ [[-- You're stubborn, right?]], "Yes" };
			{ [[-- Do you understand you won't be able to tell anyone what is revealed to you?]], "Yes" };
			{ [[-- Maybe you would like to change your mind?]], "Yes" };
			{ [[-- Are we going to talk forever?]],
				"No" };
			{ [[-- Okay, I'll repeat everything from the beginning.]],
				"Yes" };
		}
		local i = (s.yes % #txt) + 1
		local ans = txt[i][2]
		if mp.event == ans then
			s.last = txt[i][1]
			p(txt[i][1])
			s.yes = s.yes + 1
		else
			pn (s.last)
			if mp.event == "Yes" then
				pn [[-- Yes!]];
			else
				pn [[-- No!]];
			end
			walk 'oldman_talk2'
			remove 'oldman'
		end
	end;
	before_WaveHands = function(s)
		if seen 'oldman' then
			p [[The old man muttered meaningfully and waved back at you.]]
			return
		end
		return false
	end;
	dsc = [[You are standing on the top of a cliff.
	A majestic view opens before you below.
	Far far away, over the horizon a black spire is visible.
	There is a strange tree to the north of you.]];
	n_to = '#tree';
	out_to = function(s)
		if mp.words[1]:find "прыг" then
			mp:xaction ("Jump")
			return
		end
		return '#tree';
	end;
	compass_look = function(s, t)
		if t == 'd_to' then
			mp:xaction("Exam", _'#view')
			return
		end
		return false
	end;
	d_to = function(s)
		p [[You can't go down the rocky cliff.]];
	end;
	obj = {
		door {
			nam = '#tree';
			"tree,branch*";
			description = [[The lonely tree seems completely redundant here.]];
			door_to = 'tree';
		}:attr 'scenery,open';
		Distance {
			"view|rocks,debris/plural";
			nam = "#view";
			description = [[Below you see a valley strewn with rock debris.]];
		};
		Distance {
			"spire|tower";
			description = [[The tall, thin spire is barely visible from here.]];
		};
		'sky2';
		'oldman';
	};
}:attr 'supporter';

room {
	title = "Tree";
	nam = 'tree';
	trans = false;
	ff = false;
	exit = function(s)
		if s.trans then
			p ([[You choose to travel ]],s.trans:noun(),
				".")
			p [[After taking just a few steps, you suddenly found yourself in a completely different place...]];
			if s:once 'trans' then
				p [[You've lost your balance. You stumble and fall.
				Finally, the dizziness goes away and you look around in surprise.]]
			end
		end
	end;
	enter = function(s, f)
		s.ff = f;
		s.trans = false
		if f ^ 'шпиль' and s:once'visit' then
			p [[You hurried to the tree.
			Meanwhile, the figure of the person you noticed disappeared behind the tree trunk.
			When you, a little tired, reached the tree, you found noone there...]]
			disable 'human'
		end
	end;
	out_to = function(s)
		return s.ff
	end;
	n_to = function(s)
		if s.ff ^ 'sea' then
			return 'sea';
		end
		return false
	end;
	e_to = function(s)
		if s.ff ^ 'шпиль' then
			return 'шпиль';
		end
		return false
	end;
	s_to = function(s)
		if s.ff ^ 'rock' then
			return 'rock';
		end
		return false
	end;
	d_to = function(s)
		p [[To dig the ground?]];
	end;
	cant_go = function(s, t)
		s.trans = _('@'..t)
		if s.ff ^ 'planet' then -- 'w'
			walk 'sea'
			return
		elseif s.ff ^ 'sea' then
			if rain then
				snd_play ('sfx_rain_loop', true)
			end
			mus_play 'bgm_plains'
			snd_stop 'sfx_ocean_waves_loop'
			set_pic(_'sea'.old_pic)
			walk 'planet'
			return
		elseif s.ff ^ 'шпиль' then
			if t == 'w_to' then
				walk 'rock'
			else
				walk 'intower'
			end
			return
		elseif s.ff ^ 'rock' then
			if t == 'n_to' then
				walk 'intower'
			else
				walk 'шпиль'
			end
			return
		end
	end;
	w_to = function(s)
		if s.ff ^ 'planet' then
			return 'planet';
		end
		return false
	end;
	dsc = function(s)
		p [[You are standing by the old tree.
		Its dry gnarled branches are almost devoid of leaves.]]
		if s.ff ^ 'шпиль' then
			p [[^^The spire of the tower is to the east.]];
		elseif s.ff ^ 'planet' then
			p [[^^Your ship is to the west.]];
		elseif s.ff ^ 'sea' then
			p [[^^The sea is to the north.]];
		elseif s.ff ^ 'rock' then
			p [[^^The cliff is to the south.]];
		end
		p [[The green plain stretches all other directions.]];
	end;
	u_to = '#tree';
	obj = {
		obj {
			nam = '#tree';
			"tree,trunk,leaves*,leaf*,brunch*";
			before_Touch = [[The bark of the tree is rough. Like wrinkles.]];
			description = [[The tree has almost no leaves, but it is alive.]];
			['before_Climb,Enter'] = [[You are not eager to break your neck.]];
		}:attr 'scenery,enterable,supporter';
		obj {
			"green plain,plain";
			description = [[You see nothing remarkable except a desolate plain.]];
		}:attr 'scenery';
	};
}

Distance {
	nam = "clouds";
	"clouds,cloud*/plural";
	description = [[You see snow-white clouds floating below.]];
}

Distance {
	nam = "sky3";
	"sky";
	description = [[The turquoise sky is illuminated with iridescent flashes of all colors.]];
	obj = {
		Distance {
			"flashes/plural|hyperspace,radiance";
			description = [[You are astounded by the beautiful radiance of hyperspace.]];
		};
	}
}
global 'bomb_cancel' (false)
cutscene {
	nam = 'bomb_call';
	title = "The phone call";
	enter = function(s)
		mus_stop()
	end;
	text = function(s, n)
		local t = {
		[[Somewhere in the dark streets of your subconscious, you have an idea.
		Afraid to scare off the strange but exciting thought, you grabbed the phone and dialed.]];
		[[-- They shouldn't have done that! They shouldn't have done it to me!  -- the harsh voice in the receiver frightened you.]];
		[[-- Juan? Is that you?]];
		[[-- Heck! Who's that? Are these your jokes? Get out my head!]];
		[[-- Juan, listen to me carefully! Listen to me, buddy!]];
		[[-- Who the hell are you?]];
		[[-- Juan, have you flown to Dimidius already?]];
		[[-- Not! How do you know I'm going there? Who are you?]];
		[[-- Do not interrupt! Listen carefully!
		On Dimidius, you'll get a technician job and try to commit a terrorist attack by planting a bomb on Frisky.
		The attack ... will fail. Don't do it, Juan! It will crush you.
		You will kill the pilot of the ship in vain, but you are not a killer!]];
		[[-- How do you know? Who are you?]];
		[[-- Consider me your inner voice. I will look after you.]];
		[[-- Go to hell! Have I gone mad?]];
		[[-- If you still don’t listen to me.
		In the cockpit you'll see a photo of a girl.
		It's Lisa, pilot's daughter. Do you understand? Don't forget.]];
		[[-- Get out of my head!]];
		};
		if n == 2 then
			snd_stop()
			snd_play 'sfx_phone_call_2'
		end
		return t[n]
	end;
	exit = function(s)
		p [[You hang up. You wonder if Juan changes his mind.^^
		What is it, stored in the tower? Recorded events of bygone days that can be played back like old records?
		Or maybe the tower is a receiver of everything that really happens, only at a different time?]];
		if have 'осколки' then
			p [[^^Suddenly, you felt you no longer have the shards of the bomb with you!]];
		end
		remove 'осколки'
		_"огнетушитель".full = true
		bomb_cancel = true
		mus_play 'bgm_plains'
	end;
}

cutscene {
	nam = 'bomb_call2';
	title = "The phone call";
	enter = function(s)
		mus_stop()
	end;
	text = function(s, n)
		local t = {
		[[Not understanding exactly what is happening, you dial the number...]];
		[[-- They shouldn't have done that! They shouldn't have done it to me!  -- the harsh unfamiliar voice in the receiver frightened you.]];
		[[-- Hello...]];
		[[-- Heck! If only it was not enough for me. Who's that?]];
		[[-- I...]];
		[[-- Get out my head, get out! Do you hear?]];
		};
		if n == 2 then
			snd_stop()
			snd_play 'sfx_phone_call_2'
		end
		return t[n]
	end;
	exit = function(s)
		p [[You hang up hastily.]];
		mus_play 'bgm_plains'
	end;
}

cutscene {
	nam = 'photo_call';
	title = "The phone call";
	enter = function(s)
		mus_stop()
	end;
	text = function(s, n)
		local t = {
		[[You picked up the phone and dialed the number.
		Desperation and hope for a miracle replaced each other until...]];
		[[-- Dad, is that you?]];
		[[-- Yes it's me! Lisa? Are you ... Where are you?]];
		[[-- At home, of course.
		Am I talking to you in my imagination?]];
		[[-- I guess. I ... don't know for sure.
		Lisa ... Listen, how old are you?]];
		[[-- Almost ten! Have you forgotten? When are you coming back?]];
		[[-- Soon... Tell your mom I love you both.]];
        [[-- You've already called us the regular way, but I'll tell...
        Fine, we're going for a walk. Goodbye!]];
        [[-- Yes, see you!]];
		};
		if n == 2 then
			snd_stop()
			snd_play 'sfx_phone_call_2'
		end
		return t[n]
	end;
	exit = function(s)
		p [[Excited, you hang up. It was Lisa! 10 years ago!]];
		mus_play 'bgm_plains'
	end;
}

room {
	"room";
	title = "Observation room";
	nam = "top";
	before_Walk = function(s, to)
		if to ^ '@u_to' then
			p [[The rail ends here.]]
			return
		elseif to ^ '@d_to' then
			if not pl:inside'platform' then
				move(pl, 'platform')
			end
			p [[You push the button and the platform, with unexpectedly fast acceleration, begins its descent.]]
			snd_play 'sfx_platform'
			move('platform', 'intower')
			return
		end
		return false
	end;
	before_Ring = function(s, w)
		w = tostring(tel_number(w))

		if w == '7220342721' then --photo
			if visited 'photo_call' then
				p [[You don’t have the heart to call your daughter back in the past again.
				She is doing well, and it's all you need to know.]];
			else
				snd_play 'sfx_phone_call_loop'
				walk 'photo_call'
			end
		elseif w == '9333451239' then -- осколки
			if visited 'bomb_call' then
				p [[Poor Juan should not be disturbed.]];
			else
				snd_play 'sfx_phone_call_loop'
				if know_bomb then
					walk 'bomb_call'
				else
					walk 'bomb_call2'
				end
			end
		elseif w == '17' or w == '8703627531' or w == '9236123121' or w == '7691' then
			snd_play 'sfx_phone_call_loop'
			return false
		else
			snd_play 'sfx_phone_wrong_number'
			p [[A woman's voice is heard by the phone: "An object with this identifier was not found in the file cabinet."]]
			return
		end
	end;
	out_to = 'balk';
	dsc = [[You are in a small round room filled with daylight.
	Windows are located along the entire walls perimeter.
	An old telephone is attached to the wall.^^You may come to the observation deck.]];
	obj = {
		obj {
			"telephone,phone,receiver";
			description = [[Antique. Landline phone.
			In ancient times, these were set in telephone booths.
			You can try to {$fmt em|dial <a number>}.]]
		}:attr 'static,concealed';
		Prop { "wall,wall*" };
		Careful {
			"window/plural";
			description = [[Outside the windows you see the observation deck.]];
		};
		Path {
			"deck,observation deck,observation";
			walk_to = 'balk';
			desc = [[You may come to the observation deck.]];
		};
		obj {
			"platform";
			nam = 'platform';
			inside_dsc = "You are standing on the platform. Underneath, on the platform, you see two buttons.";
			description = [[The platform moves along the vertical rail leading up and down.]];
			after_LetIn = function(s, w)
				if w == pl then
					p [[You get up on the platform and look around.
					The controls are extremely simple, there are only two buttons.
					Now you can {$fmt em|go up or down}.]]
					return
				end
				return false
			end;
			obj = {
				obj {
					"buttons/plural|button";
					description = [[You can {$fmt em|go up or down}.]];
					['before_Push,Touch'] =
						[[Going {$fmt em|up} or {$fmt em|down}?]];
				}:attr 'static,concealed';
			};
		}:attr 'supporter,open,enterable,static';
	};
}
room {
	nam = "balk";
	title = "Observation deck";
	out_to = 'top';
	in_to = 'top';
	before_Listen = [[The wind howls in the lattice structure of the observation deck.]];
	dsc = [[Everywhere around is filled by the deep turquoise sky, illuminated by spectral flashes.
	Below your feet are snow-white clouds floating above the patchwork quilt of the fields.
	On the horizon you see the spiers of other towers!^^You may leave the observation deck.]];
	obj = {
		'clouds';
		'sky3';
		Distance {
			"horizon|spiers,towers/plural";
			description = [[You see thin tower spiers piercing the snow-white clouds.
			You walked around the observation deck and counted 5 such spiers. But how many more are there?]]
		};
		Distance {
			"ground,surface,planet,patchwork*,quilt*|fields/plural";
			description = [[How far does the tower rise above the surface?]];
		};
	};
}:attr'supporter';

function check_sit(w)
	if pl:where() ~= _'#chair' then
		if not w then
			return false
		end
		p(w)
	else
		walk 'computer'
	end
end
obj {
	nam = '$char';
	act = function(s,w)
		return w
	end;
}
room {
	"room";
	title = "Computer room";
	enter = function(s, f)
		if f ^ 'intower' then
			snd_play ('sfx_computer_ambience_loop', true)
			mus_stop()
			set_pic 'comp'
		end
		if not disabled 'crash' then
			p [[{$char|^^}{$fmt em|Coming down to the room, you were horrified to find the strange computer again on the damn table!}]];
			disable 'crash'
			enable '#chair'
			enable 'table'
		end
	end;
	exit = function(s, to)
		if to ^ 'intower' then
			snd_stop 'sfx_computer_ambience_loop'
			mus_play 'bgm_plains'
		end
	end;
	dsc = function()
		p [[You are in a dim room.]]
		if disabled 'crash' then
			p [[The only light source here is the turned on computer.
			The computer is on the table. There is an armchair next to the table.]];
		else
			p [[There are fragments of furniture and computer scattered in the room.]]
		end
	end;
	nam = "under";
	before_Attack = function(s, w)
		if pl:inside '#chair' then
			p [[Maybe you should get up from the armchair first?]];
			return
		end
		if not disabled 'crash' then
			p [[You have already done it.]]
			return
		end
		local list = {}
		for _, v in ipairs(objs 'table') do
			if not v ^ 'comp' then
				table.insert(list, v)
			end
		end
		for _, v in ipairs(list) do
			move(v, here())
		end
		p [[In a fit of sudden rage, you start destroying everything around you.]]
		if have 'огнетушитель' then
			p [[The fire extinguisher, which you for some reason carried all this time, came in handy.]]
		end
		p [[In a minute, it was all over.]]
		disable '#chair'
		disable 'table'
		enable 'crash'
	end;
	before_Listen  = [[You hear a subtle hum.]];
	before_Walk = function(s, to)
		if to ^ '@d_to' then
			p [[The rail ends here.]]
			return
		elseif to ^ '@u_to' then
			if not pl:inside'platform' then
				move(pl, 'platform')
			end
			snd_play 'sfx_platform'
			move('platform', 'intower')
			return
		end
		return false
	end;
	obj = {
		Furniture {
			"chair,armchair";
			nam = "#chair";
			title = "In the armchair";
			description = function()
				p [[The armchair looks old. Made of wood.]];
				return false
			end;
			inside_dsc = [[You are sitting in the armchair.]];
			after_LetIn = function(s, w)
				if w == pl then
					p [[You sat down in the armchair.]]
					return
				end
				return false
			end;
		}:attr 'concealed,supporter,enterable';
		Furniture {
			nam = "table";
			"table,desk,surface*";
			description = function(s)
				p [[Matted surface of the desk reflects the monitor glow.]];
				return false
			end;
			obj = {
				Furniture {
					nam = "comp";
					"computer";
					description = [[It is kind of ancient junk.
					The pot-bellied monitor flickers green in the dark.
					The big keyboard is part of the computer.]];
					["before_Search,LookAt"] =
						function(s)
							return check_sit()
						end;
					before_SwitchOff = [[You don't see any switch.
					And no wires here...]];
					obj = {
					Furniture {
						nam = '#keyboard';
						"keyboard|keys,keycaps/plural";
						description =
							[[The keyboard has tall square keys.]];
						['before_Push,Touch,Take'] =
							function(s)
								check_sit
									[[It would be more comfortable to do it in the armchair.]]
							end
						};
						Furniture {
							"monitor,screen";
							before_SwitchOff
								=
								[[You didn't notice any switch button.]];
							description =
								function()
									check_sit [[Probably the screen is bad for the eyes.]];
									end
						}:attr'switchable,on';
					};
				}:attr'switchable,on'
			};
		}:attr 'concealed,supporter';
		Prop {
			nam = "crash";
			"fragments,chunks,pieces/plural";
		}:disable();
	};
}
local ids = {
	['comp'] = 17;
	['photo'] = 7220342721;
	['огнетушитель'] = 8703627531;
	['suit'] = 9236123121;
	['осколки'] = 9333451239;
	['wheat'] = 7691;
}
function search_stat(total, n)
	p (fmt.b(tostring(total) ..[[ total match(es).]]))
	if n == 1 then
		pn (fmt.b([[One important message found.]]))
	else
		pn (fmt.b(tostring(n) ..[[ important messages found.]]))
	end
	pn()
end
room {
	title = false;
	nam = "computer";
	OnError = function(s)
		p [[Syntax error. For instructions type "{$fmt b|help}".]];
	end;
	out_to = "under";
	default_Verb = "examine";
	total = 32174;
	dsc = function(s)
		p [[WELCOME TO THE ARCHIVE^^]];
		pn ([[Total files: ]], s.total, "* E23")
		s.total = s.total + rnd(15);
		p [[Selected language: {$fmt
em|English}^^For instructions type "{$fmt b|help}".]];
	end;
	Look = function()
		pl:need_scene(true)
	end;
	Help = [[^^
{$fmt c|THE ARCHIVE PROGRAM v1.1}^^
{$fmt b|exit} {$fmt tab,50%}-- to quit the program^
{$fmt b|search <id>} {$fmt tab,50%}-- to find a file by item identification number^
{$fmt b|scan} {$fmt tab,50%}-- to scan an item.]];
	Scan = function(s)
		snd_play 'sfx_scan'
		if not instead.tiny then
			fading.set { 'null', delay = 30, max = 60, now = true }
		end
		pn [[{$fmt b|Items on the table:}]]
		for k, v in ipairs(objs 'table') do
			pn (v:noun(), '{$fmt tab,30%|}',' -- ',
			   ids[v.nam] or [[id unknown]])
		end
	end;
	Search = function(s, w)
		if w == '17' then -- comp
			search_stat(1, 1)
			p ([[...The Archivist put the computer on the table and turned it on...]])
		elseif w == '8703627531' then -- огнетушитель
			search_stat(213, 1)
			p [[...You fight the flames fiercely.
			Finally, the fire is extinguished!...]]
		elseif w == '7691' then -- wheat
			search_stat(5, 1)
			p [[...You plucked a few spikelets and rubbed them in your palms, collecting the grains...]];
		elseif w == '9236123121' then -- suit
			search_stat(507, 1)
			p [[...Not without fear you take off your spacesuit.
							You take a deep breath. Everything seems to be alright!..]]
		elseif w == '7220342721' then
			search_stat(173, 1)
			p [[... -- Dad, when are you coming back? -- Lisa spinned in the pilot's chair looking at the dashboard.^
-- I'll be home in a month. Until that, listen to your mom. Okay?^
-- I always listen to my mother!^
-- I know, but still...^
-- Oh, this is my photo! Why here?^
-- Eh, well, I just love you very much...]]
		elseif w == '9333451239' then
			search_stat(12, 2)
			if bomb_cancel then
			p [[... Juan opened the control unit cover and planted the bomb deep inside.
			Then he carefully secured the cover in place.^^
			He really didn't like what he was forced to do.
			Especially after he visited the cockpit and saw the photo.
			At that moment, already forgotten memories of a strange voice in his head flooded over him with renewed vigor.]];
			p [[^^...Scratching hands and cursing, Juan pulled the bomb back out of the control block.
			Finally, the bomb was retrieved and Juan put it in the tool bag.
			^^Juan is not a killer!]];
			else
			p [[...Juan opened the control unit cover and planted the bomb deep inside.
			Then he carefully secured the cover in place.^^
			He didn't like what he was forced to do.
			Especially after he visited the cockpit and saw the photo.
			But he tried to drive away such thoughts.^^
			When the gates are blown up, the fight against the oppressors will begin!
			Dimidius must become a free, new, happy world!
			He will let himself become a murderer for the sake of the new life, Juan doesn't give a damn about himself!]];

			p [[^^...When Juan learned from the news that the bomb exploded later, already after the ship entered hyperspace, in one second his world was destroyed...
			He's a killer, no excuses.
			As a dead man, he walked along the street without seing his way...]];
			know_bomb = true
			end
		else
			if tonumber(w) then
				p [[There is no information in the file index for this item.]]
			else
				p [[Wrong item identification number.]];
			end
		end
	end;
	enter = function()
		_'@compass':disable()
	end;
	ExitComp = function(s)
		move(pl, 'under')
		move(pl, '#chair')
		_'@compass':enable()
	end;
}

Verb ({"help", "Help" }, _'computer')
Verb ({"exit,quit", "ExitComp" }, _'computer')
Verb ({"scan", "Scan" }, _'computer')
Verb ({"search,find,lookup", "* :Search" }, _'computer')
Verb ({"examine,x", "Look" }, _'computer')
Verb {
	"push,move,press,shift",
	"{noun} forward: Push",
}

room {
	"room";
	title = "Inside the tower";
	nam = "intower";
	out_to = "#pass";
	old_pic = false;
	enter = function(s, f)
		if f ^ 'tree' then
			s.old_pic = get_pic()
		end
		set_pic 'intower'
	end;
	exit = function(s, t)
		if t ^ 'шпиль' then
		--	set_pic(s.old_pic)
		end
	end;
	dsc = [[You are inside a spacious cylindrical room.
	In the room center, you see a round fenced shaft going through the floor and the ceiling with a vertical rail running along it.
	There is a passage in the outer wall through which you see green field and a lonely tree in it.]];
	compass_look = function(s, t)
		if t == 'd_to' then
			mp:xaction("Exam", _'#hole')
			return
		end
		if t == 'u_to' then
			mp:xaction("Exam", _'#rail')
			return
		end
		return false
	end;
	before_Walk = function(s, to)
		if not seen 'platform' then
			return false
		end
		if not pl:inside'platform' and (to ^ '@u_to' or to ^
		'@d_to') then
			move(pl, 'platform')
		end
		if to ^ '@u_to' then
			p [[You push the button and the platform, with unexpectedly fast acceleration, begins its ascent.]]
			set_pic 'tower'
			if s:once 'up' then
				p [[^^Floors flash before your eyes: 10, 50, 100...
				How many are there totally? You try to see at least something and it seems to be shelves of books.^^
Books, endless string of bookshelves!
Then the speed increases so much you can't distinguish anything...
Minutes pass, the platform slows down and you find yourself at the top of the tower.]];
			end
			snd_play 'sfx_platform'
			move('platform', 'top')
			return
		elseif to ^ '@d_to' then
			p [[You push the button and the platform, with unexpectedly fast acceleration, begins its descent.]]

			if s:once 'down' then
				p [[^^It's dark in the shaft, and you can't see anything on the floors you fly by so quickly.
				You only see thousands of colored lights.
				Like fireflies, they rush past you.
				Finally, the platform slows down and you find yourself in a dim room.]]
			end
			move('platform', 'under')
			snd_play 'sfx_platform'
			return
		end
		return false
	end;
	obj = {
		door {
			nam = '#pass';
			"passage,tree*,field*";
			door_to = 'шпиль';
			description = [[You realize that you are inside the tower.]];
		}:attr 'scenery,open';
		obj {
			"lever";
			description = [[The lever is installed next to the shaft.]];
			before_Push = function(s)
				p [[Nothing happens.]]
			end;
			before_Pull = function(s)
				if not seen 'platform' then
					p [[You pull the lever and immediately hear a growing noise from somewhere above.
					Few minutes later, a platform descends into the room along the rail.]]
					snd_play 'sfx_platform'
					move('platform', here())
				else
					p [[Nothing happens.]]
				end
			end;
		}:attr'static';
		obj {
			"shaft,hole,fence,barrier,bulkhead*";
			nam = '#hole';
			description = [[The shaft is fenced off with a low barrier.
			You come to the edge and look down, but all you see is an endless series of floors with same fences around the shaft.]];
			before_LetIn = function(s, w)
				if w == pl then
					p [[The shaft is deep!]]
					return
				end
				return false
			end;
			after_LetIn = function(s, w)
				p ([[You throw ]], w:the_noun(), " into the shaft.")
				move(w, 'under')
			end;
		}:attr 'scenery,container,open,enterable';
		obj {
			"rail";
			nam = '#rail';
			description = [[A toothed rail comes up the shaft.
			You lift your head and see an endless series of floors.]];
		}:attr'static,concealed';
	};
}

function game:after_Taste()
	p [[What a strange idea.]]
end

function game:after_Smell()
	p [[Nothing interesting.]]
end

game['before_Taste,Eat,Talk'] = function()
	if _'suit':has'worn' then
		p [[It's impossible while wearing a spacesuit.]]
	else
		return false
	end
end

function game:before_Listen()
	if _'suit':has'worn' then
		p [[Wearing a spacesuit, you can't hear the outside world well.]]
	else
		return false
	end
end

function game:before_Shout()
	if _'suit':has'worn' then
		p [[Wearing a spacesuit, you will go deaf.]]
	else
		return false
	end
end

function game:after_Sing()
	p [[You hum a melody to yourself.]]
end

function game:after_Shout()
	p [[You decided to blow off steam by screaming a little.]]
end

function game:before_Smell()
	if _'suit':has'worn' then
		p [[You don't feel odor wearing the spacesuit.]]
	else
		return false
	end
end

function game:Touch()
	if _'suit':has'worn' then
		p [[It is inconvenient to do it wearing a spacesuit.]]
	else
		return false
	end
end

obj {
	"beard";
	nam = "beard";
	description = [[You're just too lazy to shave. You don't care about your appearance at all]];
	after_Touch = [[You scratched your beard, not without pleasure.]];
}:attr 'static';

pl.description = function(s)
	if ill > 0 then
		p [[You look at your hands and see something strange.
		They become transparent. The light goes through them. Are you... disappearing?]];
		return
	end
	p [[You are a deep space exploration geologist.
	The gray hair in the beard, the tired look and the wrinkles on the face make you a middle-aged man.]]
	if _'suit':has'worn' then
		p [[You're wearing the spacesuit now.]]
	end
	if here() ^ 'ship1' then
		p [[Your six-month contract for Dimidius is over, it's time to return home.
		For six months you worked as a contractor at Dimidius, exploring uranium deposits.
        But now the contract is over.]]
	end;
end
pl.scope = std.list { 'beard' }

VerbExtendWord {
	"#Touch",
	"scratch";
}

VerbExtendWord {
	"#Walk",
	"return to"
}

Verb {
	"leave",
	"{noun} : Exit",
}

function mp:before_Exting(w)
	if not have 'огнетушитель' then
		p [[You have nothing to extinguish the fire with.]]
		return
	end
	return false
end

function mp:after_Exting(w)
	if not w then
		p [[There is nothing to extinguish.]]
	else
		p ([[Extinguish ]], w:the_noun(), "?")
	end
end
function tel_number(w)
	w = w:gsub("[^0-9]+", "")
	return tonumber(w)
end

function mp:before_Ring(w)
	if not here() ^ 'top' then
		p [[There is no telephone.]]
		return
	end
	if _'suit':has'worn' then
		p [[Wearing a spacesuit?]]
		return
	end
	if w and not tel_number(w) then
		p ([[Wrong number: ]]..w, ".")
		return
	end
	if not w then
		p [[Try to {$fmt em|dial <a number>}. For example,
	{$fmt em|dial 12345}.]];
		return
	end
	return false
end

function game:before_Attack(w)
	if w == pl then
		if _'suit':has'worn' then
			p [[The spacesuit protects you.]]
			return
		end
		p [[Are you giving up so quickly?]]
		return
	end
	return false
end

function mp:after_Ring(w)
	p [[No answer...]]
end

Verb {
	"extinguish,put out";
	": Exting";
	"{noun}/scene: Exting";
}

Verb {
	"shout,cry,scream";
	": Shout";
}

Verb {
	"dial,call";
	"* : Ring";
};

function init()
	mp.togglehelp = true
	mp.autohelp = false
	mp.autohelp_limit = 8
	mp.compl_thresh = 1
	set_pic "gate"
	mus_play 'bgm_going_home'
	snd_play('sfx_ship_ambience_loop', true)
	snd_play('sfx_ready_blip_loop', true)
	walk 'ship1'
end
function start()
	snd_start()
	if not instead.tiny then
--		fading.set { 'crossfade', now = true }
	end
end
if not instead.tiny then
function mp:onedit(...)
	if here() ^ 'computer' then
		snd.play('snd/sfx_keyboard_key_press.ogg', 4, 1)
	end
end
end
