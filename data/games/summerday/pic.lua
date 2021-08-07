require "sprite"
require "timer"
require "theme"
require "snd"
if not theme.name() or theme.name():find(".", 1, true) ~= 1 then
	dprint "Disabling pictures"
else
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
			spr = spr:scale(hh / h)
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
		if not spr_blank then
			spr_blank = sprite.new(theme.get'scr.gfx.w', theme.get'scr.gfx.h')
			spr_blank:fill '#333333'
			spr = sprite.new(p)
			local hh = tonumber(theme.get'scr.gfx.h')
			local w, h = spr:size()
			local ww, hh = spr_blank:size()
			spr = spr:scale(hh/h)
			w, h = spr:size()
			spr:copy(0, 0, ww, hh, spr_blank, (ww - w)/2, 0)
		end
		return spr_blank
	end
end

function pic_push(name)
	name = 'img/'..name .. '.png'
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
