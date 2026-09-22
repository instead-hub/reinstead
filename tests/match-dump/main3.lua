-- Golden dump: фиксирует результат разбора на детерминированном корпусе.
-- Запуск: tests/run-parser-tests.sh (секция match-dump).
-- Пишет out.txt рядом с собой.

require "parser/mp-ru"
require "fmt"

room {
	nam = 'main';
	word = -"зал/мр";
	dsc = 'Тестовая сцена.';
	obj = { 'stone', 'box', 'key1', 'key2', 'dog', 'door', 'table', 'bag', 'coin1', 'coin2',
		'redgem', 'greengem', 'bigstone', 'smallstone', 'sunsetgem', 'garden', 'plaingarden' };
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

obj {
	nam = 'table';
	-"стол";
	dsc = 'Стол.';
}:attr 'supporter';

obj {
	nam = 'bag';
	-"мешок";
	dsc = 'Открытый мешок.';
	obj = { 'coin1', 'coin2' };
}:attr 'container,open';

obj {
	nam = 'coin1';
	-"монета";
	dsc = 'Первая монета.';
}

obj {
	nam = 'coin2';
	-"монета";
	dsc = 'Вторая монета.';
}

obj {
	nam = 'redgem';
	-"красный алмаз|алмаз";
	dsc = 'Красный алмаз.';
}

obj {
	nam = 'greengem';
	-"зелёный алмаз|алмаз";
	dsc = 'Зелёный алмаз.';
}

obj {
	nam = 'bigstone';
	-"большой камень|камень";
	dsc = 'Большой камень.';
}

obj {
	nam = 'smallstone';
	-"маленький камень|камень";
	dsc = 'Маленький камень.';
}

obj {
	nam = 'sunsetgem';
	-"алмаз заката";
	dsc = 'Алмаз заката.';
}

obj {
	nam = 'garden';
	-"шепчущий сад";
	dsc = 'Шепчущий сад.';
}

obj {
	nam = 'plaingarden';
	-"сад";
	dsc = 'Обычный сад.';
}

pl.word = -"я/мр,1л";

game.dsc = 'match dump.';

-- дополнительные шаблоны: опциональные слова, vargs, пропуски, приоритет
Verb { "#DumpOpt", "смешать,смешай", "?быстро {noun}/вн : DumpOpt" }
Verb { "#DumpTwo", "сравнить,сравни", "{noun}/вн с|со {noun}/тв : DumpTwo" }
Verb { "#DumpVarg", "перемешать", "* : DumpVarg" }
Verb { "#DumpVarg2", "проверить", "{noun}/вн * : DumpVarg2" }
Verb { "#DumpSkip", "пробросить", "{noun}/вн за {noun}/вн : DumpSkip" }
Verb { "#DumpPrioLow", "тестприоритет", "{noun}/вн : DumpPrioLow" }
Verb { "#DumpPrioHigh", "тестприоритет", "{noun}/вн : DumpPrioHigh", prio = 1 }

local noise = {
	"блабла", "ктото", "очень", "но", "там", "это", "быстро", "и", "с", "под", "не", "кроме",
}
local objects = {
	"камень", "валун", "ящик", "ключ", "самоцвет", "дверь", "пёс",
	"я", "стол", "мешок", "монета", "зал", "алмаз", "сад", "заката", "шепчущий",
}
local vocab = {
	"взять", "положить", "осмотреть", "открыть", "закрыть", "идти", "смешать", "сравнить",
	"перемешать", "проверить", "пробросить", "тестприоритет",
	"на", "в", "из", "под", "за", "с", "не", "кроме",
	"камень", "валун", "ящик", "ключ", "самоцвет", "дверь", "пёс",
	"север", "вверх", "стол", "мешок", "монета", "зал", "алмаз", "камень",
	"сад", "заката", "шепчущий", "блабла", "очень", "это",
}

local seed = 424242
local function rnd(n)
	seed = (seed * 1103515245 + 12345) % 2147483648
	return seed % n
end

local function pick_word(el, n)
	local p = mp:pattern(el)
	local w = p[1 + (n % math.max(#p, 1))] and p[1 + (n % math.max(#p, 1))].word
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

-- явные кейсы: перестановки, вставки, vargs (*)
local explicit = {
	"взять камень", "камень взять", "взять быстро камень", "быстро взять камень",
	"взять камень быстро", "камень быстро взять", "камень взять быстро",
	"положить камень в ящик", "в ящик положить камень", "ящик камень положить",
	"положить быстро камень в ящик", "положить камень быстро в ящик",
	"положить камень в ящик быстро", "положить камень в быстро ящик",
	"перемешать", "перемешать а", "перемешать а б в", "а б перемешать",
	"перемешать а камень", "перемешать камень а", "а камень б перемешать",
	"проверить камень", "проверить камень а б", "проверить а камень б",
	"а проверить камень", "проверить камень быстро", "проверить быстро камень",
	"смешать быстро камень", "быстро смешать камень", "смешать камень быстро",
	"смешать камень", "камень смешать", "смешать очень быстро камень",
	"сравнить камень с ключом", "с ключом сравнить камень", "камень сравнить с ключом",
	"сравнить камень ключом", "сравнить с ключом камень",
	"пробросить камень за ящик", "за ящик пробросить камень", "пробросить за ящик камень",
	"читать о камне", "о камне читать", "читать камень", "читать о очень камне",
	"искать в ящике", "в ящике искать", "искать ключ в ящике", "искать о ключе в ящике",
	"осмотреть камень и ключ", "взять камень и ключ", "камень и ключ взять",
	"положить камень и ключ в ящик", "положить камень в ящик и мешок",
	"взять алмаз", "взять красный алмаз", "алмаз взять", "красный алмаз взять",
	"взять зелёный алмаз", "взять камень", "камень взять", "взять большой камень",
	"взять маленький камень", "большой камень взять",
}

-- группы вариантов из шаблонов: перестановки, вставки, опечатки
local function insert_at(words, pos, w)
	local r = {}
	for _, x in ipairs(words) do
		table.insert(r, x)
	end
	table.insert(r, math.min(math.max(pos, 1), #r + 1), w)
	return r
end

local function reversed(words)
	local r = {}
	for i = #words, 1, -1 do
		table.insert(r, words[i])
	end
	return r
end

local function swapped(words, a, b)
	if #words < b then
		return nil
	end
	local r = {}
	for _, x in ipairs(words) do
		table.insert(r, x)
	end
	r[a], r[b] = r[b], r[a]
	return r
end

local function gen_corpus()
	local corpus, sample = {}, {}
	local n = 0
	local ncase = 0
	local function push(words, important)
		if words and #words > 0 then
			local s = table.concat(words, " ")
			table.insert(corpus, s)
			ncase = ncase + 1
			if important or (ncase % 12) == 0 then
				table.insert(sample, s)
			end
		end
	end
	local function push_str(inp, important)
		table.insert(corpus, inp)
		ncase = ncase + 1
		if important or (ncase % 12) == 0 then
			table.insert(sample, inp)
		end
	end
	local function mutate(words, with_verb)
		push(words)
		if #words < 2 then
			return
		end
		push(reversed(words))
		push(swapped(words, 1, 2))
		push(swapped(words, 2, 3))
		local L = #words
		for k, pos in ipairs({ 1, 2, math.floor(L / 2) + 1, L, L + 1 }) do
			push(insert_at(words, pos, noise[1 + (k % #noise)]))
		end
		push(insert_at(words, L + 1, noise[1]))
		push(insert_at(words, L + 2, noise[2]))
		local ch = mp.utf.chars(words[L] or "")
		if #ch > 2 then
			table.remove(ch, 1 + rnd(#ch - 1))
			local t = {}
			for i = 1, L - 1 do
				t[i] = words[i]
			end
			t[L] = table.concat(ch)
			push(t)
		end
	end
	for _, v in ipairs(mp:verbs()) do
		for _, d in ipairs(v.dsc) do
			local args, opt = {}, {}
			for _, el in ipairs(d.pat) do
				n = n + 1
				local w = pick_word(el, n)
				table.insert(args, w)
				if not el:find("^[?+]") then
					table.insert(opt, w)
				end
			end
			if #args > 0 then
				push(args)
				if #opt > 0 and #opt ~= #args then
					push(opt)
				end
				local vword = v.verb[1] and v.verb[1].word
				if vword and vword ~= '' then
					local sentence, sentence_opt = { vword }, { vword }
					for _, w in ipairs(args) do
						table.insert(sentence, w)
					end
					for _, w in ipairs(opt) do
						table.insert(sentence_opt, w)
					end
					mutate(sentence, true)
					if #opt > 0 and #opt ~= #args then
						mutate(sentence_opt, true)
					end
				end
			end
		end
	end
	for _, inp in ipairs(explicit) do
		push_str(inp, true)
	end
	-- compass movement, word orders and input shortenings
	local compass = {
		"север", "юг", "запад", "восток", "северо-восток", "северо-запад",
		"юго-восток", "юго-запад", "вверх", "вниз", "внутрь", "наружу",
		"наверх", "назад", "вход", "выход",
		"идти на север", "идти на юг", "идти на запад", "идти на восток",
		"идти на северо-восток", "идти на юго-запад",
		"идти вверх", "идти вниз", "идти внутрь", "идти наружу", "идти назад",
		"на север", "на юг", "в зал", "во внутрь",
		"север идти", "на север идти", "вверх идти", "идти быстро на север",
		"быстро идти на север", "идти на север быстро", "идти на север и юг",
		"идти к залу", "идти к мешку", "идти в ящик", "войти в ящик",
		"зайти в мешок", "идти внутрь мешка",
		"с", "ю", "з", "в", "св", "юв", "сз", "юз", "вн", "вв",
		"и", "ж", "о", "осм", "см", "вкл", "выкл",
		"о камень", "осм камень", "см камень", "вкл камень", "выкл камень",
	}
	for _, inp in ipairs(compass) do
		push_str(inp, true)
	end
	-- targeted: every object noun/alias with Take/Exam, to cover shared aliases
	for _, o in ipairs(mp.cache.nouns) do
		local ww = {}
		o:noun(ww)
		for _, w in ipairs(ww) do
			if w.word and w.word ~= '' then
				push_str("взять " .. w.word, true)
				push_str("осмотреть " .. w.word, true)
			end
		end
	end
	for _ = 1, 1200 do
		local len = 1 + rnd(6)
		local w = {}
		for _ = 1, len do
			table.insert(w, vocab[1 + rnd(#vocab)])
		end
		push(w)
	end
	return corpus, sample
end

local last_xact = {}

local function fmt_words(t)
	if type(t) ~= 'table' then
		return "-"
	end
	local r = {}
	for _, v in ipairs(t) do
		if type(v) == 'table' then
			table.insert(r, tostring(v.word) .. ":" .. tostring(v.lev))
		else
			table.insert(r, tostring(v))
		end
	end
	return table.concat(r, ",")
end

local function match_words(p)
	local r = {}
	for i = 1, #p do
		table.insert(r, tostring(p[i]))
	end
	return table.concat(r, ",")
end

-- emulate typing to build the completion context, then return candidates
local function complete(inp)
	mp.inp = ''
	mp:compl_reset()
	mp:compl_fill(mp:compl '')
	local c
	for i = 1, #inp do
		mp.inp = inp:sub(1, i)
		c = mp:compl(mp.inp)
		mp:compl_fill(c)
	end
	return mp.completions
end

local function fmt_compl(t)
	local r = {}
	for _, v in ipairs(t or {}) do
		if type(v) == 'table' then
			table.insert(r, tostring(v.word) .. (v.hidden and "~" or ""))
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
				tostring(a.alias), a.default and "d" or (a.optional and "o" or "r"),
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
		"fields=" .. (p and table.concat({
			"skip=" .. tostring(p.skip), "wild=" .. tostring(p.wildcards),
			"def=" .. tostring(p.defaults), "extra=" .. tostring(p.extra),
			"prio=" .. tostring(p.prio), "words=" .. match_words(p),
			"vargs=" .. fmt_words(p.vargs),
		}, ",") or "-"),
		"hints=" .. fmt_words(mp.hints),
		"unknown=" .. fmt_words(mp.unknown),
		"multi=" .. fmt_words(mp.multi),
		"extra=" .. (mp.extra and mp:match_words(mp.extra) or "-"),
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
		local corpus, sample = gen_corpus()
		for _, inp in ipairs(corpus) do
			cur_inp = inp
			last_xact = {}
			std.rawset(mp, 'parsed', false)
			mp.cache.nouns = mp:nouns()
			local r, v = mp:input(mp:norm(inp))
			f:write(snap(inp, r, v), "\n")
		end
		f:close()
		local cf = io.open(dir .. 'out-compl.txt', 'w')
		for _, inp in ipairs(sample) do
			cur_inp = inp
			mp.cache.nouns = mp:nouns()
			local comp = complete(inp)
			local tab = mp:docompl(inp)
			cf:write(inp .. "\t" .. fmt_compl(comp) .. "\t" .. tostring(tab) .. "\n")
		end
		cf:close()
	end, function(e) return tostring(e) .. " @ [" .. tostring(cur_inp) .. "]" end)
	if not ok then
		print("DUMP FAIL: " .. tostring(err))
	end
	print("match-dump done")
	os.exit(0)
end

std.mod_start(run_dump, 9)
