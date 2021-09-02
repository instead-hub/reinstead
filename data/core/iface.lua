local mwin
local tbox = require "tbox"
local utf = require "utf"
local cursor

local iface = {
}

local input = ''
local input_pos = 1;
local input_prompt = conf.prompt

local function fmt_esc(s)
	return s:gsub("\\","\\\\"):gsub("<","\\<"):gsub(" ", "<w: >")
end

local history = { }
local history_len = 50
local history_pos = 0

function iface.history_prev()
	history_pos = history_pos + 1
	if history_pos > #history then
		history_pos = #history
	end
	local i = history[history_pos]
	if i then
		input = i
		return iface.input_attach(i)
	end
	return
end

function iface.history_next()
	history_pos = history_pos - 1
	if history_pos < 1 then
		history_pos = 1
	end
	local i = history[history_pos]
	if i then
		input = i
		return iface.input_attach(i)
	end
	return
end

function iface.input_history(input, add)
	history_pos = 0
	if history[1] ~= input and input ~= '' then
		table.insert(history, 1, input)
	end
	if #history > history_len then
		table.remove(history, #history)
	end
	iface.input_detach()
	if add ~= false then
		mwin:add("<b>"..input_prompt..fmt_esc(input).."</b>")
	end
end

local input_attached = false

function iface.create_cursor()
	local h = mwin.lay.fonts.regular.h + math.ceil(SCALE * 2)
	local w = math.floor(3 * SCALE);
	if w < 3 then
		w = 3
	elseif w % 3 ~= 0 then
		if (w - 1) % 3 == 0 then
			w = w - 1
		else
			w = w + 1
		end
	end
	local b = w / 3
	cursor = gfx.new(w, h)
	if b <=0 then
		cursor:fill(0, 0, w, h, conf.cursor_fg)
		return
	end
	cursor:fill(b, 0, b, h, conf.cursor_fg)
	cursor:fill(0, 0, w, w, conf.cursor_fg)
	cursor:fill(0, h - w, w, w, conf.cursor_fg)
end

local function input_line(chars)
	local pre = ''
	local n = #mwin:lines()
	for i=1,input_pos-1 do pre = pre .. chars[i] end
	local post = ''
	for i = input_pos,#chars do post = post .. chars[i] end
	mwin:add(input_prompt..fmt_esc(pre)..'<w:\1>'..fmt_esc(post), false)
	local l = mwin:lines()[n + 1]
	for _, v in ipairs(l or {}) do
		if v.t == '\1' then
			v.w = 0
			v.img = cursor
			local w, h = cursor:size()
			v.h = h
			v.xoff = -w/2
			break
		end
	end
	mwin:resize(mwin.w, mwin.h, n)
	return l
end

function iface.input_detach()
	local l
	if input_attached then
		l = table.remove(mwin:lines(), #mwin:lines())
	end
	input_attached = false
	return l
end

function iface.input_attach(input, edit)
	input = input or iface.input()
	local o = iface.input_detach()
	local chars = utf.chars(input)
	if not edit then
		if not chars[1] then
			input_pos = 1
		else
			input_pos = #chars + 1
		end
	end
	local l = input_line(chars)
	input_attached = l
	l = o and l and (l.h == o.h)
	if not mwin:scroll(mwin:texth()) and l then
		mwin:render_line(gfx.win(), #mwin:lines())
		return false
	else
		return true
	end
end
function iface.input_left()
	input_pos = input_pos - 1
	if input_pos == 0 then input_pos = 1 end
	return iface.input_attach(input, true)
end

function iface.input_right()
	input_pos = input_pos + 1
	local n = #utf.chars(input)
	if input_pos > n then
		input_pos = n + 1
	end
	return iface.input_attach(input, true)
end

function iface.input_home()
	input_pos = 1
	return iface.input_attach(input, true)
end

function iface.input_end()
	input_pos = #utf.chars(input) + 1
	return iface.input_attach(input, true)
end

function iface.input_kill()
	input = ''
	return iface.input_attach(input)
end

function iface.input_text(v)
	local t = utf.chars(input)
	local app = utf.chars(v)
	table.insert(t, input_pos, v)
	input = table.concat(t, '')
	input_pos = input_pos + #app
	return iface.input_attach(input, true)
end

function iface.input_edit(v)
	local dirty = iface.input_attach(input..v)
	input_pos = #utf.chars(input) + 1
	return dirty
end

function iface.input_bs()
	local t = utf.chars(input)
	if input_pos <= #t + 1 and input_pos > 1 then
		table.remove(t, input_pos - 1)
		input_pos = input_pos - 1
		if input_pos < 1 then input_pos = 1 end
	end
	input = table.concat(t, '')
	return iface.input_attach(input, true)
end

function iface.input_etb()
	local input = iface.input():gsub("[ \t]+$", "")
	local t = utf.chars(input)
	local sp = 1
	for k = #t, 1, -1 do
		if t[k] == ' ' then sp = k break end
	end
	input = ''
	for k = 1, sp - 1 do input = input .. t[k] end
	iface.input_set(input)
	return iface.input_attach()
end

function iface.input()
	return input
end

function iface.input_set(v)
	input = v
end

function iface.mouse(e, v, a, b)
	if input_attached and e == 'mousedown' then
		local x, y, w, h = mwin.sw + mwin.pad, input_attached.y - mwin.off + mwin.pad,
			mwin.lay.w, input_attached.h
		if v == 'left' and a >= x and a < x + w and b >= y and b < y + h then
			system.input()
		end
	end
	return mwin:mouse(e, v, a, b)
end

function iface.win()
	if mwin then
		return mwin
	end
	mwin = tbox:new()
	mwin:resize(gfx.win():size())
	iface.create_cursor()
	return mwin
end

function iface.reset()
	local lines = mwin:lines()
	local win = gfx.win()
	mwin = tbox:new()
	mwin.lay.lines = lines
	mwin:reset()
	mwin:resize(win:size())
	iface.input_detach()
	iface.create_cursor()
	iface.input_attach(input)
	return mwin
end

return iface
