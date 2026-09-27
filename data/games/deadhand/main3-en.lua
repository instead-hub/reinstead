--$Name: Doomsday$
--$Version:0.1
--$Author:Peter Kosyh$
--$Info:A short sketch about a lone cosmonaut.$

require "fmt"
fmt.dash = true
fmt.quotes = false

require 'parser/mp-en'
pl.description = [[You are an astronaut in a spacesuit.]];

local DH_TO = 2

function game:before_Walk(w)
	local dir = mp:compass_dir(w)
	if not dir then
		return false
	end
	if dir == 'in_to' or dir == 'out_to' then
		return false
	end
	p [[There are compass directions on Earth, but not in space.]]
end

cutscene {
	nam = 'main';
	title = false;
	text = {
		[[{$fmt c|***}^^The ship's hull burst and its contents, hundreds of shards glittering in the Sun, gushed out into open space.
It all happened in a single instant. Just half a second -- and a complex, well-tuned machine turned into a cloud of space debris...^^
One of those glittering shards was you. The white spacesuit reflected the rays perfectly, making you a bright glowing dot in the black void.^^
Spinning, you drifted slowly in the dark...]];

	};
	next_to = 'space';
}

function init()
	take 'suit'
end;

global 'known' (false)
local channels = {
	{ "You hear classical music on the radio." };
	{ "-- Of course, there is a chance that we are alone in the universe, but...",
	  "-- But you do not believe it?", "-- I categorically refuse to believe it!",
	  "-- But then why do we not hear their signals?", "-- Yes, the Fermi paradox raises questions, but here is what I will tell you..."};
	{ "You hear French speech on the radio." };
	{ "You hear jazz on the radio." };
	{ "You hear a news broadcast on the radio." };
	{ "You listen to a political debate on the radio." };
	{ "You hear radio static." };

}

pl.before_LetGo = function(s)
	p [[There is no point in throwing things around in space.]];
end;
local pres = [[-- pssst. .. ..talk? ... (pause) ... If anyone is drifting out there right now... and can hear me. All I can say is, forgive us.
You will forever remain in our hearts. Faithful sons of the Earth, of the Motherland... Once again, forgive us and accept my condolences.^^
tzzzt...]]

obj {
	nam = 'suit';
	-"spacesuit,suit";
	description = function(s)
		p "Your spacesuit is equipped with various instruments.";
		if here().rotate then
			p [[But right now you are thinking only about the maneuvering thrusters.]]
			return
		end
		if not known then
			p [[For example, the radio.]]
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
			p 'That is suicide!';
		end
	end;
}:attr 'worn,clothing':with {
	obj {
		-"maneuvering thrusters,thrusters,engines/plural|thruster";
		nam = 'engines';
		description = [[The maneuvering thrusters allow you to orient yourself in space and move short distances. You can turn them on.]];
		after_SwitchOn = function(s)
			if here().rotate then
				p [[You turn on the maneuvering thrusters and try to stop the spin.
Eventually you succeed! Though you spent quite a lot of fuel. You turn the thrusters off again.]]
				here().rotate = false
				s:attr'~on'
			else
				if seen 'tetr' then
					p [[You turn on the maneuvering thrusters.]]
					return
				end
				p [[You give a couple of bursts. Better to save fuel. Although... why?]];
				s:attr'~on'
			end
		end;
	}:attr 'switchable,scenery';
	obj {
		nam = 'radio';
		-"radio,receiver,transceiver";
		description = function(s)
			p [[A VHF receiver is built into the spacesuit.]];
			if s:has'on' then
				if freq then
					p [[The working frequency is set to 143.625 MHz.]]
				else
					p [[The working frequency is not set.]]
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
					p("Suddenly, the silence of the airwaves was broken.^",pres)
					p [[^^The signals stopped. You noticed that the text on the screen had changed.]]
				else
					p [[You hear a hissing sound from the radio.]]
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
				p ([[You turned the radio on at the working frequency.^^
...ing.. .ast... Guys, if any of you survived. The oxygen supply in your spacesuits is not enough
for us to find and pick any of you up in time... We are very sorry... And now, please listen to
the president's address:^
...^
]]..pres..[[ We repeat this broadcast every 15 minutes for two hours.]])
				known = true
			else
				p [[You turned the radio on at the working frequency 143.625 MHz.]];
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
	"fly";
	"to {noun}/scene : Walk";
	"into|in {noun}/scene : Enter";
	"{compass1} : Walk",
}

Verb {
	"tune,set,change";
	"{noun} : Tune";
	"frequency|channel : Tune";
}

function mp:Tune(w)
	if not w or w ^ 'radio' then
		w = _'radio'
		if w:hasnt 'on' then
			p [[The radio is off.]]
			return
		else
			return false
		end
	end
	if w then
		p (w:It(), " cannot be tuned.")
		return
	end
end;

global 'freq' (true)
global 'freq_hz' (1)
global 'channel_pos' (1)
function mp:after_Tune(w)
	freq = not freq
	if not freq then
		p [[You changed the frequency.]]
		freq_hz = rnd(#channels)
		channel_pos = rnd(#channels[freq_hz])
		DaemonStart 'radio'
	else
		p [[You returned to the working frequency: 143.625 MHz.]]
	end
end

obj {
	nam = 'earth';
	-"Earth,planet|clouds/plural";
	description = [[Sooner or later you will fall to Earth and burn up in the atmosphere. But for now your breath is taken away
by the grandeur and beauty of the space panorama.]];
	found_in = { 'space', 'space2' };
	before_Exam = stub;
	["before_Walk,Enter,Climb"] = [[Sooner or later you will fall to it anyway.]];
	before_Default = [[The Earth is too far away.]];
}:attr'scenery';

obj {
	nam = 'stars';
	-"stars/plural|star";
	description = [[You look at the scattering of stars. And they seem to be looking inside you. Maybe you will soon become one of them?]];
	found_in = { 'space', 'space2' };
	before_Exam = stub;
	before_Default = [[The stars are too far away.]];
}:attr 'scenery';

game.before_Taste = function(s, w)
	if _'suit':has'worn' then
		p [[In a spacesuit?]]
		return
	end
	return false
end

game.before_Smell = function(s, w)
	if _'suit':hasnt'worn' then
		return false
	end
	if not w or w:inside(pl) then
		p [[There is no smell in a spacesuit.]]
		return
	end
	p [[That is impossible in a spacesuit.]]
end
game.before_Jump = [[That is impossible in zero gravity.]];
game.before_JumpOver = game.before_Jump

game.before_Listen = function(s)
	if _'radio':hasnt'on' then
		p [[You need to turn the radio on for that.]]
	else
		if freq then
			p [[The radio is silent.]]
		else
			p [[The spacesuit is filled with the sound of the radio.]];
		end
	end
end;

obj {
	-"debris|fragments/plural";
	description = [[This is all that is left of the ship.]];
	['before_Walk,Enter,Climb'] = [[The wreckage of the ship has already scattered far apart.
There is no point in searching there.]];
	found_in = { 'space', 'space2' };
}:attr 'scenery';

obj {
	-"object,UFO";
	nam = 'tetr';
	dsc = [[Against the stars you see some bright object.]];
	description = [[From here you can only tell that it is quite large. Space debris? It is moving on a course almost parallel to yours.]];
	before_Default = [[It is too far away.]];
	before_Exam = stub;
	['before_Walk,Climb,Enter'] = function()
		if _'engines':hasnt'on' then
			p [[First you need to turn the engines on.]]
			return
		end
		walk 'space2';
	end;
}
room {
	nam = 'space';
	title = "open space";
	-"space,void,scenery";
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
			p [[You thought you saw some bright object.]]
			s:daemonStop()
		end
	end;
	dsc = function(s)
		if s.rotate then
			p [[Spinning fast, you drift in open space.]]
		else
			p [[You drift in open space. Below you stretches the blue expanse of the planet Earth.]]
		end
	end;
	before_Default = function(s, ev, w)
		if not s.rotate or ev == 'Look' or ev == 'Wait' or ev == 'Inv' then
			return false
		end
		if w and w:inside(pl) or w == pl then
			return false
		end
		p [[Because of the frantic spinning, you cannot get your bearings.]]
		if s:once 'self' then
			p [[Maybe you should try to examine yourself?]]
		end
	end;
}

door {
	-"airlock hatch,airlock,hatch";
	nam = 'gate';
	door_to = function(s)
		if here() ^ 'space2' then
			return 'ship';
		else
			return 'space2';
		end
	end;
	before_Close = [[It closes automatically.]];
	description = function() p [[Next to the hatch there is a red lever.]]; enable 'lever' return false; end;
}:attr 'static,openable,enterable,locked':disable();
obj {
	nam = 'lever';
		-"red lever,lever";
	['after_Pull,Transfer'] = function(s)
		if here() ^ 'ship2' then
			if _'gate2':has'open' then
				p [[You pulled the lever and the entry hatch closed. At the same time, the lights inside the ship came on.]];
				_'gate2':attr '~open'
			else
				p [[You pulled the lever and the entry hatch opened. The lights went out.]];
				_'gate2':attr 'open'
			end
			return
		end
		local open = _'gate':has'open'
		if here() ^ 'ship' then
			if not open then
				p [[You pulled the lever and the entry hatch closed. Then the airlock hatch opened.]];
				_'gate2':attr'~open'
			end
		end
		if open then
			p [[You pulled the lever and the airlock hatch closed.]];
			_'gate':attr'~open';
		else
			if here() ^ 'space2' then
				p [[You pulled the lever and the airlock hatch opened.]];
			end
			_'gate':attr'open';
		end
		if here() ^ 'ship' then
			if open then
				p [[After a while the entry hatch leading inside the ship opened.]];
				_'gate2':attr'open'
			end
		end
	end;
}:attr 'fixed,luminous':disable();

room {
	nam = 'space2';
	title = "open space";
	-"space,void,scenery";
	in_to = function(s)
		if disabled'gate' then
			p [[How will you get inside?]];
		else
			return 'gate'
		end
	end;
	onenter = function(s)
		p [[Working the maneuvering thrusters and almost out of fuel, you managed to match your orbit with that of the object.
It turned out to be a satellite shaped like a tetrahedron.]];
		_'engines':attr '~on';
	end;
	dsc = [[You hover in the black abyss next to an unknown satellite. Below, Earth's clouds drift over the turquoise expanse.]];
}: with {
	obj {
		-"satellite,tetrahedron,ship,object,UFO";
		description = [[The satellite is bristling with antennas and transmitters like a hedgehog. Its grey tetrahedral hull slowly rotates around its axis.]];
		['before_Enter,Climb'] = [[You need an airlock to get inside.]];
	}:attr 'scenery':with {
		obj {
			-"hull,antenna*,transmitter*";
			description = function(s)
				if s:once() then
					p [[Examining the hull carefully, you noticed an airlock hatch.]];
					enable 'gate'
				else
					if perimetr then
						p [[Now you know what this satellite is.]];
					else
						p [[A communications satellite, perhaps?]];
					end
				end
			end;
		}:attr 'scenery';
	};
	'gate', 'lever',

}

room {
	nam = 'ship';
	title = "airlock";
	-"airlock compartment";
	onenter = function(s, f)
		if f ^ 'space2' then
			p [[You flew into the airlock compartment.]];
		end
	end;
	out_to = 'gate';
	in_to = 'gate2';
}: with {
	'gate', 'lever', 'gate2'
}

door {
	nam = 'gate2';
	-"entry hatch,hatch,entry";
	before_Close = [[It closes automatically.]];
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
	"145.800 MHz",
	"143.625 MHz",
	"4625 kHz",
	"147.211 MHz",
	"192.112 MHz",
}
room {
	nam = 'ship2';
	-"ship";
	title = "inside the ship";
	out_to = 'gate2';
	daemon = function(s)
		if good_to > DH_TO and s:once('ack') then
			if here() == s then
				if not isDaemon'radio' then
					p [[The signals stopped. You noticed that the text on the screen had changed.]]
				end
			end
			s:daemonStop()
		else
			if here() == s then
				p [[You hear a pulsing beep that echoes through the ship every second.]]
				if know2 then
					p ([[Time to the first wave: ]], timeout, " s.")
				end
			end
		end
	end;
	onenter = function(s)
		if s:once() then
			p [[With anxiety and hope, you flew inside the strange ship.]]
		end
	end;
	dsc = function(s)
		p [[There is not much room inside the ship. Then again, you are used to that.]];
		if _'gate2':has'open' then
			p [[It is quite dark in here. The details of the interior are barely visible in the half-light.]]
		end
	end;
	onexit = function(s)
		if _'suit':hasnt 'worn' then
			p [[Without a spacesuit? Suicide!]]
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
				p [[Good call.]]
			else
				p [[You pressed the button and lines of text ran across the console screen.]]
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
		-"control panel,panel|instruments/plural";
		description = [[You see many instruments whose purpose you do not understand, and a console screen.
A red button catches your attention.]];
	}:attr'static,supporter':with {
		obj {
			nam = 'button';
			-"red button,red,button";
			description = [[You see no inscriptions or markings on the button.]];
			before_Push = function()
				if perimetr then
					perimetr_ask = perimetr_ask + 1
					if perimetr_ask > 5 then perimetr_ask = 0 end
					p [[You pressed the button again.]]
					p [[You noticed that one of the lines on the screen had changed.^]]
					p ("Voice abort mode: ")
					if perimetr_ask == 0 then
						p ("off")
					else
						p(freqs[perimetr_ask])
					end
					return
				end
				p [[An unknown ship. A red button. Are you sure you want to do this?^Confirm. Yes or no?]]
				ask = true
			end;
		}:attr 'static,concealed';
		obj {
			nam = 'screen';
			-"screen,console,text";
			description = function(s)
				if good_to > DH_TO then
					DaemonStop'ship2'
					DaemonStop'radio'
					walkin 'goodend'
					return
				end
				if perimetr then
					p ([[PERIMETER program activated.^^
Switching to autonomous mode: yes^]])
					if perimetr_ask > 0 then
						p ([[Voice abort mode: ]], freqs[perimetr_ask], ".")
					else
						p ([[Voice abort mode: off.]])
					end
					p ([[^Disabling control over communication channels: yes^
Countdown to the start of the active phase: ]], timeout,
[[^First-wave nuclear strike: pending^
Second-wave nuclear strike: pending^
Final wave: pending]])
					know2 = true
				else
					p [[The screen is inactive.]];
				end
			end;
		}:attr 'static';
	};
};

cutscene {
	nam = 'badend';
	title = 'The End';
	text = { [[You never managed to shut down the doomsday machine.^
Almost mad, you watched from orbit as the Earth burned in nuclear hell.^
You would have been better off dying in open space...^
^{$fmt em|But it could have ended differently...}]] };
	onexit = function(s)
		timeout = 600
	end;
}

cutscene {
	nam = 'goodend';
	title = false;
	text = {
		[[Procedure interrupted.^
Reason: the president is alive^
Exiting autonomous mode: yes^
Signal from protected facilities: restored]];
		[[{$fmt c|***}^^You slowly came back to your senses. The horror of the inevitable only now fell upon you
with full force. So for a long time you drifted detached in weightlessness.^^
It seems that the broadcast from Earth, received by the satellite, stopped the final strike procedure.^^
Yes, it will take time to get used to this doomsday machine and send a signal to the flight center.^^
But the main thing is that you did not become the cause of your world's destruction. That was all that mattered to you now.]]
	};
	next_to = 'titles';
}

gameover {
	title = fmt.c(fmt.b([[DOOMSDAY]]));
	nam = 'titles';
--	noparser = true;
	dsc = [[{$fmt c|Story and code by Peter Kosyh^^
Specially for INSTEDOZ-6^^
March -- 2019^^
If you liked the game,
^visit http://instead-games.ru
}
]]
}
