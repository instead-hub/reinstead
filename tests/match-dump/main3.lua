-- Golden dump: фиксирует результат разбора на детерминированном корпусе.
-- Запуск: tests/run-parser-tests.sh (секция match-dump).
-- Пишет tests/match-dump/out.txt относительно CWD (runner делает cd $ROOT).

require "parser/mp-ru"
require "fmt"

room {
	nam = 'main';
	word = -"зал/мр";
	dsc = 'Тестовая сцена.';
	obj = { 'stone', 'box', 'key1', 'key2', 'dog', 'door' };
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
	nam = 'key1';
	-"ключ";
	dsc = 'Первый ключ.';
}

obj {
	nam = 'key2';
	-"ключ";
	dsc = 'Второй ключ.';
}

obj {
	nam = 'dog';
	-"пёс,собака/мр,од,жив";
	dsc = 'Собака.';
}

obj {
	nam = 'door';
	-"дверь/жр";
	dsc = 'Дверь.';
}:attr 'openable';

pl.word = -"я/мр,1л";

game.dsc = 'match dump.';

local objects = { "камень", "валун", "ящик", "ключ", "самоцвет", "дверь", "пёс", "я" }
local vocab = {
	"взять", "положить", "осмотреть", "открыть", "закрыть", "идти",
	"на", "в", "из", "под", "не", "кроме",
	"камень", "валун", "ящик", "ключ", "самоцвет", "дверь", "пёс",
	"север", "вверх", "чтонибудь", "слово", "и", "с",
}

local seed = 42
local function rnd(n)
	seed = (seed * 1103515245 + 12345) % 2147483648
	return seed % n
end

local function pick_word(el, n)
	local p = mp:pattern(el)
	local w = p[1] and p[1].word
	if w and w ~= '' and not w:find("[{}*]") then
		return w
	end
	if el:find("compass1") then return "север" end
	if el:find("compass2") then return "вверх" end
	if el:find("noun") or el == '*' or el == '~*' then
		return objects[1 + (n % #objects)]
	end
	if w then
		w = w:gsub("[{}*]", "")
		if w ~= '' then return w end
	end
	return "слово"
end

local function gen_corpus()
	local corpus = {}
	local n = 0
	for _, v in ipairs(mp:verbs()) do
		for _, d in ipairs(v.dsc) do
			local full, opt = {}, {}
			for _, el in ipairs(d.pat) do
				n = n + 1
				local w = pick_word(el, n)
				table.insert(full, w)
				if not el:find("^[?+]") then
					table.insert(opt, w)
				end
			end
			if #full > 0 then
				table.insert(corpus, table.concat(full, " "))
				if #opt > 0 and #opt ~= #full then
					table.insert(corpus, table.concat(opt, " "))
				end
			end
			if #corpus > 1200 then
				return corpus
			end
		end
	end
	for i = 1, 800 do
		local len = 1 + rnd(4)
		local w = {}
		for _ = 1, len do
			table.insert(w, vocab[1 + rnd(#vocab)])
		end
		table.insert(corpus, table.concat(w, " "))
	end
	return corpus
end

local last_xact = {}

local function fmt_words(t)
	local r = {}
	for _, v in ipairs(t or {}) do
		if type(v) == 'table' then
			table.insert(r, tostring(v.word) .. ":" .. tostring(v.lev))
		else
			table.insert(r, tostring(v))
		end
	end
	return table.concat(r, ",")
end

local function snap(inp, r, v)
	local p = mp.parsed
	local args = {}
	if p then
		for _, a in ipairs(p.args or {}) do
			table.insert(args, table.concat({
				tostring(a.word), a.ob and a.ob.nam or "-",
				tostring(a.alias), a.default and "d" or "-",
			}, ":"))
		end
	end
	return (table.concat({
		inp,
		"r=" .. tostring(r),
		"v=" .. tostring(v),
		"x=" .. tostring(last_xact.ev) .. ":" .. tostring(last_xact.ob),
		"ev=" .. (p and tostring(p.ev) or "-"),
		"args=" .. table.concat(args, " "),
		"hints=" .. fmt_words(mp.hints),
		"unknown=" .. fmt_words(mp.unknown),
		"multi=" .. fmt_words(mp.multi),
	}, "\t"))
end

local function run_dump()
	local dir = std.getinfo(1).source:gsub("^@", ""):gsub("[^/\\]*$", "")
	local f = io.open(dir .. 'out.txt', 'w')
	if not f then
		print("can not open dump file")
		os.exit(2)
	end
	std.rawset(mp, 'xaction', function(_, ev, ...)
		last_xact = { ev = ev, ob = ... and ... or "-" }
		return true
	end)
	mp.cache.nouns = mp:nouns()
	local cur_inp = '?'
	local ok, err = xpcall(function()
		local corpus = gen_corpus()
		for _, inp in ipairs(corpus) do
			cur_inp = inp
			last_xact = {}
			std.rawset(mp, 'parsed', false)
			mp.cache.nouns = mp:nouns()
			local r, v = mp:input(mp:norm(inp))
			f:write(snap(inp, r, v), "\n")
		end
	end, function(e) return tostring(e) .. " @ [" .. tostring(cur_inp) .. "]" end)
	if not ok then
		print("DUMP FAIL: " .. tostring(err))
	end
	f:close()
	print("match-dump done")
	os.exit(0)
end

std.mod_start(run_dump, 9)
