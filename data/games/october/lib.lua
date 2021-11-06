function eph_event(ev)
	return ev == 'Exam' or ev == 'Smell' or ev == 'Listen' or ev == 'Look' or ev == 'Search' or ev == 'Talk'
		or ev == 'Wait' or ev == 'Ring' or ev == 'Think' or ev == 'Wake'
end

VerbExtend {
	"#Talk",
	"по {noun}/дт : Ring",
	"по {noun}/дт с {noun}/тв,scene : Ring",
	"~ с {noun}/тв,scene по {noun}/дт : Ring reverse",
	":Talk"
}

VerbExtend {
	"#Attack",
	"{noun}/вн,scene {noun}/тв,held: Attack",
	"~ {noun}/тв,held {noun}/вн,scene : Attack reverse",
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
	"покин/уть",
	"{noun}/вн,scene : Exit",
}

Verb {
	"#Ring",
	"[по|]звон/ить",
	"по {noun}/дт: Ring",
	":Ring"
}

VerbExtend {
	"#Wave",
	"{noun}/тв,held : Wave",
	"{noun}/дт,scene,live : WaveOther"
}

Verb {
	"[|по]звать",
	"{noun}/вн,scene,live : Talk",
}

Verb {
	"#Cry",
	"[|по|за|про]крич/ать,крикн/уть",
	"{noun}/дт,scene,live : Talk",
	": Cry"
}

function mp:before_Consult(w)
	mp:xaction("Search", w)
end

function mp:Cry(w)
	p "Это {#me/дт} не поможет."
end

function mp:WaveOther(w)
	if mp:check_touch() then
		return
	end
	return false
end

function mp:after_WaveOther()
	p "{#Me} глупо {#word/помахать,прш,#me} {#first/дт}."
end

Verb {
	"#Answer",
	"ответ/ить,отвеч/ать",
	"{noun}/дт : Talk",
	"по {noun}/дт : Talk",
}


global 'last_talk' (false)

function mp:Ring(w)
	if not w or w:has'ring' then
		p "{#Me/дт} некому сейчас звонить."
		return
	end
	p (w:Noun(), " не телефон и не радио, чтобы говорить c ", w:it 'вн', " помощью.");
end

-- ответить
function mp:before_Answer(w)
	if not w then
		return false
	end
	mp:xaction("Talk", w)
end

function mp:after_Answer(w)
	mp:xaction("Talk", w)
end

-- говорить без указания объекта
function mp:before_Talk(w)
	if w then
		last_talk = w
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
		local o = std.call(s, 'walk_to')
		if mp:check_inside(_(o)) then
			return
		end
		if _(o):has 'door' or mp:compass_dir(_(o)) then
			mp:xaction("Enter", _(o))
			return
		end
		walk(o)
	end;
	before_Default = function(s, ev)
		if (ev == 'Exam' or ev == 'LookAt') and s.description then
			return false
		end
		if s.desc then
			if type(s.desc) == 'function' then
				s:desc()
			else
				p(s.desc)
			end
			return
		end
		p ([[{#Me} {#word/могу,#me,нст} пойти в ]], std.ref(s.walk_to):noun('вн'), '.');
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
			p ("{#Me/дт} нет дела до ", s:noun 'рд', ".")
			return
		end
		p ("Лучше оставить ", s:noun 'вн', " в покое.")
	end;
}:attr 'scenery'

Useless = Class {
	before_Default = function(s, ev)
		if ev == "Exam" or ev == "Look" or ev == "Search" then
			return false
		end
		p ("Лучше оставить ", s:noun 'вн', " в покое.")
	end;
}:attr 'scenery'
