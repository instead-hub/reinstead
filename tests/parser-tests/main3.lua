-- Parser tests (headless). Run: tests/run-parser-tests.sh
-- Check parser behavior (data/stead3/parser) on a synthetic scene.
-- Finish with os.exit(0/1), so the engine never reaches autoscript.

require "parser/mp-ru"
require "fmt"

local checks, failures = 0, 0

local function ok(name, cond, extra)
	checks = checks + 1
	if cond then
		print("ok - " .. name)
	else
		failures = failures + 1
		print("FAIL - " .. name .. (extra and (": " .. tostring(extra)) or ""))
	end
end

room {
	nam = 'main';
	word = -"зал/мр";
	dsc = 'Тестовая комната.';
	obj = { 'stone', 'box', 'key1', 'key2', 'redcrystal', 'bluecrystal' };
}

obj {
	nam = 'stone';
	-"камень,валун";
	dsc = 'Обычный камень.';
}

obj {
	nam = 'box';
	-"ящик";
	dsc = 'Закрытый ящик.';
	obj = { 'gem' };
}:attr 'container';

obj {
	nam = 'gem';
	-"самоцвет";
	dsc = 'Самоцвет в ящике.';
}

obj {
	nam = 'redcrystal';
	-"красный кристалл,кристалл";
	dsc = 'Красный кристалл.';
}

obj {
	nam = 'bluecrystal';
	-"синий кристалл,кристалл";
	dsc = 'Синий кристалл.';
}

obj {
	nam = 'key1';
	-"ключ";
	dsc = 'Первый ключ.';
}

obj {
	nam = 'key2';
	-"ключ";
	dsc = 'Второй ключ.';
}

pl.word = -"я/мр,1л";

game.dsc = 'Парсерные тесты.';

-- two verbs with the same pattern: priority decides the winner
Verb { "#TestPrioLow", "тестприоритет", "{noun}/вн : TestPrioLow" }
Verb { "#TestPrioHigh", "тестприоритет", "{noun}/вн : TestPrioHigh", prio = 1 }

local function parse(inp)
	mp.cache.nouns = mp:nouns()
	return mp:input(mp:norm(inp))
end

local function parsed_ob(n)
	local a = mp.parsed and mp.parsed.args and mp.parsed.args[n]
	return a and a.ob
end

-- mp.parsed.args also contains pattern service words (e.g. prepositions),
-- so objects are looked up by scanning.
local function has_arg_ob(ob)
	for _, a in ipairs(mp.parsed and mp.parsed.args or {}) do
		if a.ob == ob then return true end
	end
	return false
end

local function test_parse()
	local stone = std.ref 'stone'

	local r = parse "взять камень"
	ok("взять камень -> Take", r and mp.parsed.ev == 'Take', mp.parsed and mp.parsed.ev)
	ok("взять камень: объект", parsed_ob(1) == stone)

	r = parse "взять валун"
	ok("взять валун (синоним) -> Take", r and mp.parsed.ev == 'Take')

	r = parse "осмотреть камень"
	ok("осмотреть камень -> Exam", r and mp.parsed.ev == 'Exam')

	r = parse "положить камень в ящик"
	ok("положить камень в ящик -> Insert", r and mp.parsed.ev == 'Insert', mp.parsed and mp.parsed.ev)
	ok("положить камень в ящик: оба объекта",
		has_arg_ob(stone) and has_arg_ob(std.ref 'box'))

	-- objects with the same name: the parser must choose one of them
	r = parse "взять ключ"
	local key1, key2 = std.ref 'key1', std.ref 'key2'
	local chosen = parsed_ob(1)
	ok("взять ключ: выбран один из ключей",
		r and (chosen == key1 or chosen == key2), chosen and chosen.nam)

	-- object without a verb: xaction with default_Event
	local xev, xob
	local oxaction = mp.xaction
	mp.xaction = function(_, ev, ...)
		xev, xob = ev, ...
		return true
	end
	parse "камень"
	ok("камень -> Exam (default_Event)", xev == 'Exam', xev)
	ok("камень: передан объект", xob == stone)
	mp.xaction = oxaction

	-- empty input is replaced with default_Verb ("осмотреть" in mp-ru -> Look)
	local r2 = parse ""
	ok("пустой ввод -> Look (default_Verb)", r2 and mp.parsed.ev == 'Look', mp.parsed and mp.parsed.ev)

	-- extra words: the parser remembers the matched prefix for hints
	r = parse "взять камень в руки"
	ok("лишние слова: подсказка-префикс",
		r == false and mp.extra and mp:match_words(mp.extra) == "взять камень",
		mp.extra and mp:match_words(mp.extra))

	-- missing required slot: hint carries the continuation placeholder
	r = parse "взять камень в руки"
	local hinted = table.concat(mp.hints, "|")
	ok("подсказка с плейсхолдером следующего слота",
		hinted:find("\1{noun}", 1, true) ~= nil, hinted)
	ok("падеж плейсхолдера", mp:err_noun("{noun}/рд"):find("кого/чего", 1, true) ~= nil)

	-- shared short word (comma form): the parser must report both objects
	local r4, v4 = parse "взять кристалл"
	ok("взять кристалл -> MULTIPLE", r4 == false and v4 == 'MULTIPLE', v4)
	ok("в MULTIPLE оба кристалла", #(mp.multi or {}) == 2, #(mp.multi or {}))

	-- unknown verb
	local r3, v3 = parse "прыгнуть через луну"
	ok("неизвестный глагол -> ошибка", r3 == false and v3 ~= nil, v3)
end

local function test_patterns()
	local w = mp:pattern("[|по]йти", ",")
	local words = {}
	for _, v in ipairs(w) do
		words[v.word] = true
	end
	ok("pref pattern: [|по]йти -> идти/пойти", words['йти'] and words['пойти'])

	w = mp:pattern("иди[|те]", ",")
	words = {}
	for _, v in ipairs(w) do
		words[v.word] = true
	end
	ok("suff pattern: иди[|те] -> иди/идите", words['иди'] and words['идите'])

	w = mp:pattern("?на", ",")
	ok("optional: ?на помечен optional", #w == 1 and w[1].optional and not w[1].default)

	w = mp:pattern("+в", ",")
	ok("default: +в помечен optional+default", #w == 1 and w[1].optional and w[1].default)

	w = mp:pattern("~под", ",")
	ok("hidden: ~под помечен hidden", #w == 1 and w[1].hidden)

	w = mp:pattern("смотреть/вн", ",")
	ok("morph: /вн вырезан в morph", #w == 1 and w[1].word == 'смотреть' and w[1].morph == 'вн')

	ok("eq: регистр", mp:eq("ВЗЯТЬ", "взять"))
	ok("eq: префикс со *", mp:eq("взят*", "взять"))
	ok("eq: не равно", not mp:eq("взять", "положить"))
end

local function test_completion()
	-- emulate typing: completion context accumulates as input grows
	local function complete(inp)
		mp.inp = ''
		mp:compl_reset()
		mp:compl_fill(mp:compl '')
		local c
		for i = 1, #inp do
			mp.inp = inp:sub(1, i)
			c = mp:compl(mp.inp)
		end
		return c
	end

	local function has_word(c, w)
		for _, v in ipairs(c or {}) do
			if v.word == w then return true end
		end
		return false
	end

	ok("дополнение 'вз' содержит 'взять'", has_word(complete "вз", 'взять'))
	ok("дополнение 'взять к' содержит 'камень'", has_word(complete "взять к", 'камень'))
	ok("дополнение 'осмотреть я' содержит 'ящик'", has_word(complete "осмотреть я", 'ящик'))
end

local function test_grammar()
	local cases = { "взять", "[|по]йти", "иди[|те]", "?на", "+в", "~под", "смотреть/вн", "в|во" }
	for _, v in ipairs(cases) do
		local c = mp:compile_element(v)
		local p = mp:pattern(v)
		local same = not c.dynamic and #c.words == #p
		if same then
			for i = 1, #p do
				local a, b = c.words[i], p[i]
				if a.word ~= b.word or
					not not a.optional ~= not not b.optional or
					not not a.hidden ~= not not b.hidden or
					not not a.default ~= not not b.default or
					a.morph ~= b.morph then
					same = false
					break
				end
			end
		end
		ok("compile == pattern: " .. v, same)
	end
	ok("compile dynamic: {noun}/вн", mp:compile_element("{noun}/вн").dynamic)

	local r = parse "тестприоритет камень"
	ok("приоритет глагола решает исход",
		r and mp.parsed.ev == 'TestPrioHigh', mp.parsed and mp.parsed.ev)

	local key1, key2 = std.ref 'key1', std.ref 'key2'
	local first, stable = nil, true
	for _ = 1, 20 do
		parse "взять ключ"
		local chosen = parsed_ob(1)
		if not first then
			first = chosen
		elseif chosen ~= first then
			stable = false
			break
		end
	end
	ok("выбор одноимённого объекта детерминирован",
		stable and (first == key1 or first == key2))
end

local function test_regressions()
	-- 1. mplib.lua: an inaccessible second object must be detected even
	-- if the first argument is a room (it used to check first).
	local op = p
	std.rawset(_G, 'p', function() end)
	mp.first = std.ref 'main'
	mp.second = std.ref 'gem'
	ok("самоцвет недоступен (в закрытом ящике)", not std.ref('gem'):access())
	ok("check_touch: недоступный второй объект при first-комнате",
		mp:check_touch() == true)
	mp.first, mp.second = nil, nil
	std.rawset(_G, 'p', op)

	-- 2. mp.lua: VerbExtend without a tag must give a clear message
	-- (".." used to bind tighter than "or", losing '#Undefined').
	local okk, err = pcall(VerbExtend, { "ещё" })
	ok("VerbExtend без тега: внятное сообщение",
		okk == false and tostring(err):find("Extending non existing verb", 1, true) ~= nil,
		tostring(err))
end

function init()
	print("== parser tests ==")
	local ok_all, err = pcall(function()
		test_parse()
		test_patterns()
		test_completion()
		test_grammar()
		test_regressions()
	end)
	if not ok_all then
		print("FAIL - исключение: " .. tostring(err))
		failures = failures + 1
	end
	print(string.format("== checks=%d failures=%d ==", checks, failures))
	if failures > 0 then
		os.exit(1)
	end
	os.exit(0)
end
