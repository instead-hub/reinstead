if instead.tiny or not theme.name() or theme.name():find(".", 1, true) ~= 1 then
declare 'theme'({})
function theme.name()
	return 'default'
end

	dprint "Disabling pictures"
local titles = [[
{$fmt c|{$fmt b|МЕТЕЛЬ}^^

{$fmt em|История и код:}^
Пётр Косых^
{$fmt em|Иллюстрации:}^
Pakowacz^^

{$fmt em|По мотивам:}^
Коралина // Нил Гейман^^

{$fmt em|Музыка:}^
Autumn: Meditativo by Dee Yan-Key^
Largo – from Concerto No 5 – J.S. Bach // Jon Sayles^
J.S. Bach: Partia No.2 - Allemande // Scott Slapin^^

{$fmt em|Движок:}^
INSTEAD3: МЕТАПАРСЕР3 // Пётр Косых^^

http://instead.syscall.ru^^

{$fmt em|Альфа тестирование:}^
techniX^
Irremann^
spline^
Борис Тимофеев^^

{$fmt em|Благодарности:}^
Семье (за терпение)^
Работодателю (за зарплату)^
Вам (за прохождение нашей игры)^
Всем тем, кто не мешал^^

{$fmt b|КОНЕЦ}^^

{$fmt em|Февраль 2019}}]];

room {
	nam = 'titles';
	title = false;
	dsc = titles;
	noparser = true;
	enter = function(s)
		pic_set '81'
		if not instead.tiny then
			snd.music 'mus/largo.ogg'
		end
	end;
}
if instead.tiny then

global 'pictures' ({})
game.gfx = function(s)
	local top = #pictures
	if top == 0 then
		return false
	end
	if here():type'dlg' and here().__gfx == pictures[top] then
		return
	end
	if here():type'dlg' then
		here().__gfx = pictures[top]
	end
	return pictures[top]
end

function pic_push(name)
--	me():need_scene(true)
	name = 'img/'..name .. '.jpg'
	table.insert(pictures, name)
end

function pic_pop()
	local top = #pictures
	if top == 0 then
		return
	end
	table.remove(pictures, top)
end

function pic_set(name)
	local top = #pictures
	if top == 0 then
		return pic_push(name)
	end
	name = 'img/'..name .. '.jpg'
	if pictures[top] == name then
		return
	end
--	me():need_scene(true)
	pictures[top] = name
end
end
else
require "sprite"
require "theme"
require "snd"

require "titles"
global 'pictures' ({})

local spr
local spr_blank
local spr_pos = 0
local pan_left = false

function game:timer()
	if not spr then
		return false
	end
	local w, h = spr:size()
	local ww, hh = spr_blank:size()
	if spr_pos >= w - ww then
		timer:stop()
		return false
	end
	spr_blank:fill('#ffffff')
	if pan_left then
		spr:copy(w - ww - spr_pos, 0, ww, hh, spr_blank)
	else
		spr:copy(spr_pos, 0, ww, hh, spr_blank)
	end
	if spr_pos < w - ww then
		spr_pos = spr_pos + 1
	end
	return false
end

game.pic = function(s)
	local mobile = theme.name():find("^%.mobile")
	local top = #pictures
	if top == 0 then
		return false
	end
	local p = pictures[top]
	if (p:find("%-pan") or p:find("%-PAN")) and not mobile then
		if not spr then
			instead.fading(true)
			spr = sprite.new(p)
			pan_left = not not p:find("left")
			local w, h = spr:size()
			local hh = tonumber(theme.get'scr.gfx.h')
			spr = spr:scale(hh/h)
			w, h = spr:size()
			spr_pos = 0
			timer:set(50)
			if not spr_blank then
				spr_blank = sprite.new(theme.get'scr.gfx.w', theme.get'scr.gfx.h')
			end
			local ww, hh = spr_blank:size()
			if pan_left then
				spr:copy(w - ww, 0, ww, hh, spr_blank)
			else
				spr:copy(0, 0, ww, hh, spr_blank)
			end
		end
		return spr_blank
	else
		return p
	end
end

function pic_push(name)
	name = 'img/'..name .. '.jpg'
	spr = false
	timer:stop()
	instead.need_fading(true)
	if theme.name():find("^%.mobile") then
		mp:clear()
	end
	table.insert(pictures, name)
end

function pic_pop()
	local top = #pictures
	if top == 0 then
		return
	end
	table.remove(pictures, top)
	spr = false
	timer:stop()
end

function pic_set(name)
	local top = #pictures
	if top == 0 then
		return pic_push(name)
	end
	name = 'img/'..name .. '.jpg'
	if pictures[top] == name then
		return
	end
	pictures[top] = name
	instead.need_fading(true)
	if theme.name():find("^%.mobile") then
		mp:clear()
	end
	spr = false
	timer:stop()
end
end
