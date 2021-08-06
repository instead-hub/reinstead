local font = require "font"
local core = {}
local box
local text
local utf = require "utf"
local tbox = require "tbox"
local mwin

local dirty = false
local last_render = 0
local fps = 1/60
local input = ''
local input_pos = 0;
local input_prompt = '> '
local GAME = false

local function fmt_esc(s)
	return s:gsub("<","\\<"):gsub(" ", "<w: >")
end

local input_attached = false

local function input_detach()
	if input_attached then
		table.remove(mwin.lay.lines, #mwin.lay.lines)
	end
	input_attached = false
end

local history = { }
local history_len = 50
local history_pos = 0

local function output(str)
	str = str:gsub("^\n+",""):gsub("\n+$","")
	if str ~= "" then return str .. '\n\n' end
	return str
end

local function history_prev()
	history_pos = history_pos + 1
	if history_pos > #history then
		history_pos = #history
	end
	return history[history_pos]
end

local function history_next()
	history_pos = history_pos - 1
	if history_pos < 1 then
		history_pos = 1
	end
	return history[history_pos]
end

local function input_history(input)
	history_pos = 0
	if history[1] ~= input then
		table.insert(history, 1, input)
	end
	if #history > history_len then
		table.remove(history, #history)
	end
	local uinp = utf.chars(input)
	input_detach()
	mwin:add("<b>"..input_prompt..fmt_esc(input).."</b>")
end

local function input_attach(input)
	local uinp = utf.chars(input)
	input_pos = #uinp
	input_detach()
	mwin:add(input_prompt..fmt_esc(input)..'|')
	local win = gfx.win()
	local w, h = win:size()
	mwin:resize(w, h, #mwin.lay.lines)
	input_attached = true
	if not mwin:scroll(mwin.lay.realh) then
		mwin:render_line(win, #mwin.lay.lines)
		return false
	else
		return true
	end
end

function instead_done()
	local win = gfx.win()
	local w, h = win:size()
	mwin:resize(w, h)
	mwin:render(win)
	gfx.flip()
	instead.done()
end

local parser_mode = false
local menu_mode = false

local function instead_name(game)
	local f = io.open(game..'/main3.lua', "r")
	if not f then
		return game
	end
	local n = 100
	for l in f:lines() do
		n = n - 1
		if n < 0 then break end
		if l:find("^[ \t]*--[ \t]*%$Name:") then
			local s, e = l:find("$Name:", 1, true)
			game = l:sub(e + 1):gsub("^[ \t]*", ""):gsub("[ \t%$]$", "")
		end
	end
	f:close()
	return game
end

function instead_start(game, load)
	need_restart = false
	parser_mode = false
	menu_mode = false
	local r, e = instead.init(game)
	if not r then
		mwin:set(e)
		return
	end
	r = system.mkdir"saves"
	if not r then
		mwin:set("Can't create "..game.."/saves/ dir.")
		return
	end

	system.title(instead_name(game))
	gfx.icon(gfx.new 'icon.png')

	r, e = instead.cmd"look"
	if load then
		r, e = instead.cmd("load "..load)
	end
	if r then
		input_detach()
		if load then
			mwin:set("*** "..load..output(e))
		else
			mwin:set(output(e))
		end
		input_attach(input)
		mwin.off = 0
	end

end
local cleared = false
function instead_clear()
	mwin:set("")
--	input_attach(input)
	mwin.off = 0
	cleared = true
end

local function save_path(w)
	return "saves/"..w:gsub("/", "_"):gsub("%.", "_"):gsub('"', "_")
end

function instead_save(w)
	w = save_path(w)
	local r, e = instead.cmd("save "..w)
	input_detach()
	e = output(e)
	if e == "" then
		e = "*** "..w
	end
	mwin:add(e)
	input_attach(input)
	need_save = false
end

function instead_load(w)
	need_load = false
	w = save_path(w)
	local f = io.open(w, "r")
	if not f then
		input_detach()
		mwin:add("No file.\n\n")
		input_attach("")
		return
	end
	f:close()
	instead_done()
	instead_start(GAME, w)
end

function core.init()
	local skip
	for k=2, #ARGS do
		local a = ARGS[k]
		if skip then
			skip = false
		elseif a:find("-", 1, true) ~= 1 then
			GAME = a
		elseif a == "-debug" then
			instead.debug(true)
		elseif a == "-scale" then
			SCALE = tonumber(ARGS[k+1] or "1.0")
			skip = true
		end
	end
	print("scale: ", SCALE)
	if GAME then
		system.title(GAME)
	else
		system.title("Info")
	end
	local win = gfx.win()
	mwin = tbox:new()
	win:clear(mwin.lay.bg)
	gfx.flip()
	if GAME then
		instead_start(GAME)
	else
		mwin:set(string.format("<b>Usage:</b>\n<w:    >%s \\<game>", EXEFILE))
	end
	local w, h = win:size()
	mwin:resize(w, h)
end

local alt = false
local fullscreen = false

function core.run()
	while true do
		local start = system.time()
		if not dirty then
			system.wait(1)
		else
			if system.time() - last_render > fps then
				local win = gfx.win()
				mwin:render(win)
				gfx.flip()
				dirty = false
				last_render = system.time()
			end
		end
		local e, v, a, b = system.poll()
		if e == 'quit' then
			break
		end
		-- print(e, v, a)
		if (e == 'keydown' or e == 'keyup') and v:find"alt" then
			alt = (e == 'keydown')
		end
		if e == 'keydown' then
			if v == 'escape' and not GAME then -- exit
				break
			elseif v == 'escape' then
				input_detach()
				mwin:add("<c>***</c>\n/quit - exit\n/restart - restart\n\n")
				input_attach(input)
				local w, h = gfx.win():size()
				mwin:resize(w, h)
				dirty = true
			elseif v == 'backspace' then
				local t = utf.chars(input)
				table.remove(t, #t)
				input = table.concat(t, '')
				dirty = input_attach(input)
			elseif alt and v == 'return' then
				alt = false
				fullscreen = not fullscreen
				if fullscreen then
					system.window_mode 'fullscreen'
				else
					system.window_mode 'normal'
				end
			elseif v == 'return' then
				local oh = mwin.lay.realh
				local r, v
				local cmd_mode
				input = input:gsub("^ +", ""):gsub(" +$", "")
				if input:find("/", 1, true) == 1 then
					cmd_mode = true
					r = true
					if input == '/restart' then
						need_restart = true
						v = ''
					elseif input == '/quit' then
						break
					else
						r, v = instead.cmd(input:sub(2))
						r = true
					end
				elseif not parser_mode then
					r, v = instead.cmd(string.format("use %s", input))
					if not r then
						r, v = instead.cmd(string.format("go %s", input))
					end
					if r then
						menu_mode = true
					end
				end
				if not r and not menu_mode and r ~= "" then
					r, v = instead.cmd(string.format("@metaparser %q", input))
					if r then
						parser_mode = true
					end
				end
				if not r then
					r, v = instead.cmd(string.format("act %s", input))
				end
				if not parser_mode and not cmd_mode then
					local ok, w = instead.cmd "way"
					v = v .. '\n'
					if ok and w ~= "" then
						v = v .. ">> "..w
					end
					ok, w = instead.cmd "inv"
					if ok and w ~= "" then
						v = v .. "** ".. w
					end
				end
				input_history(input)
				mwin:add(output(v))
				input = ''
				input_attach(input)
				local w, h = gfx.win():size()
				mwin:resize(w, h)
				if not cleared then
					mwin.off = oh
				else
					mwin.off = 0
				end
				cleared = false
				mwin:scroll(0)
				dirty = true
			elseif v == 'up' then
				input = history_prev() or input
				input_attach(input)
			elseif v == 'down' then
				input = history_next() or input
				input_attach(input)
			end
		elseif e == 'text' then
			if v == ' ' and mwin:scroll(mwin.lay.h - mwin.lay.fonts.regular.h) then
				dirty = true
			else
				input = input .. v
				dirty = input_attach(input)
			end
		elseif e == 'mousedown' or e == 'mousemotion' or e == 'mouseup' then
			dirty = mwin:mouse(e, v, a, b)
		elseif e == 'mouseup' then
			mouse[v] = false
		elseif e == 'exposed' or e == 'resized' then
			local win = gfx.win()
			local w, h = win:size()
			mwin:resize(w, h)
			mwin:scroll(0)
			dirty = true
		elseif e == 'mousewheel' then
			mwin:scroll(-v *mwin.lay.fsize)
			dirty = true
		end
		if need_save then
			instead_save(need_save)
		end
		if need_load then
			instead_load(need_load)
		end
		if need_restart then
			instead_done()
			instead_start(GAME)
		end
		local elapsed = system.time() - start
--		system.sleep(math.max(0, fps - elapsed))
		system.wait(math.max(0, fps - elapsed))
	end
end
return core
