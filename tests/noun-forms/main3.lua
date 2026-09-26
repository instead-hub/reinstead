-- $Name:Звезды знают всё, но молчат$
-- $Version: 0.2$
-- $Author: Dwarf Vader$
-- $Info: Игра написанная за два с половиной часа специально для Спринт ИЛ$
require "parser/mp-ru"
require "fmt"

obj {
	-"раковина надежды/но";
	nam = "o1";
}
obj {
	-"чистая раковина,рак*";
	nam = "o2";
}

obj {
	-"зеленая раковина,рак*";
	nam = "o3";
}

obj {
	-"дома старосты";
	nam = "o4";
}

obj {
	-"дома старост";
	nam = "o5";
}

obj {
	-"бегущая по волнам";
	nam = "o6";
}

obj {
	-"блестящий шлем";
	nam = "o7";
}

obj {
	-"блестящие шлемы";
	nam = "o8";
}

obj {
	-"посох разрушения";
	nam = "o9";
}

obj {
	-"ведро";
	nam = "o10";
}

obj {
	-"участковый пункт полиции/но";
	nam = "o11";
}

obj {
	-"деревья";
	nam = "o12";
}

obj {
	-"огонь";
	nam = "o13";
}


obj {
	-"цветы/мн,мр";
	nam = "o14";
}

obj {
	-"песок";
	nam = "o15";
}

obj {
	-"клевер";
	nam = "o16";
}

obj {
	-"хлам";
	nam = "o17";
}

function init()
	local dir = std.getinfo(1).source:gsub("^@", ""):gsub("[^/\\]*$", "")
	local f = io.open(dir .. 'out.txt', 'w')
	if not f then
		print("can not open dump file")
		os.exit(2)
	end
	for i = 1, 17 do
		local o =  _("o"..tostring(i))
		for k, v in ipairs({"вн", "рд", "дт", "тв", "пр", "им"}) do
			f:write("["..o.word.."]\n")
			f:write(v, "\t:\t", o:noun(v), "\n")
			f:write(v, "\t(мн):\t", o:noun(v..",мн"), "\n")
		end
	end
	f:close()
	print("noun-forms done")
	os.exit(0)
end
