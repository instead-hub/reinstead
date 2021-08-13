local VERSION='0.1'
conf = require "config"

math.round = function(num, n)
	local m = 10 ^ (n or 0)
	return math.floor(num * m + 0.5) / m
end

if conf.scale == false then SCALE = 1.0 end
if type(conf.scale) == 'number' then SCALE = conf.scale end

local core = {}
local utf = require "utf"
local tbox = require "tbox"
local mwin
local cleared = false

local dirty = false
local last_render = 0
local fps = 1/conf.fps;
local input = ''
local input_pos = 1;
local input_prompt = conf.prompt
local GAME = false
local cursor

local icon = gfx.new(DATADIR..'/icon.png')

local function fmt_esc(s)
	return s:gsub("\\","\\\\"):gsub("<","\\<"):gsub(" ", "<w: >")
end

local input_attached = false

local function input_detach()
	if input_attached then
		table.remove(mwin:lines(), #mwin:lines())
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
	if history[1] ~= input and input ~= '' then
		table.insert(history, 1, input)
	end
	if #history > history_len then
		table.remove(history, #history)
	end
	input_detach()
	mwin:add("<b>"..input_prompt..fmt_esc(input).."</b>")
end

local function input_line(chars)
	local pre = ''
	local n = #mwin:lines()
	for i=1,input_pos-1 do pre = pre .. chars[i] end
	local post = ''
	for i = input_pos,#chars do post = post .. chars[i] end
	mwin.lay.nocache = true
	mwin:add(input_prompt..fmt_esc(pre)..'<w:\1>'..fmt_esc(post))
	mwin.lay.nocache = false
	local l = mwin:lines()[n + 1]
	for _, v in ipairs(l) do
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
end

local function input_attach(input, edit)
	input_detach()
	local chars = utf.chars(input)
	if not edit then
		if not chars[1] then
			input_pos = 1
		else
			input_pos = #chars + 1
		end
	end
	input_line(chars)
	input_attached = true
	if not mwin:scroll(mwin.lay.realh) then
		mwin:render_line(gfx.win(), #mwin:lines())
		return false
	else
		return true
	end
end

local busy_time = false

function instead_busy(busy)
	if not busy then
		busy_time = false
		input_detach()
		return
	end
	local t = system.time()
	if not busy_time then
		busy_time = t
		return
	end
	if t - last_render > 1/10 and t - busy_time > 3 then
		system.poll()
		input_attach('Wait, please...')
		mwin:render()
		gfx.flip()
		last_render = system.time()
	end
end

local function instead_done()
	mwin:render()
	gfx.flip()
	instead.done()
end

local function instead_icon(dirpath, norm)
	local icon = gfx.new(dirpath..'/icon.png')
	if icon and norm then
		local w, _ = icon:size()
		icon = icon:scale(128/w)
	end
	return icon
end

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
			local _, e = l:find("$Name:", 1, true)
			game = l:sub(e + 1):gsub("^[ \t]*", ""):gsub("[ \t%$]$", "")
		end
	end
	f:close()
	return game
end

local parser_mode = false
local menu_mode = false

local function instead_start(game, load)
	need_restart = false
	parser_mode = false
	menu_mode = false
	local icon
	if conf.show_icons then
		icon = instead_icon(game, true)
	end
	mwin:set(false)
	local r, e = instead.init(game)
	if not r then
		mwin:set(string.format("Trying: %q", game)..'\n'..e)
		return
	end
	r = system.mkdir(instead_savepath())
	if not r then
		mwin:set("Can't create "..game..instead_savepath().." dir.")
		return
	end

	system.title(instead_name(game))
	gfx.icon(gfx.new 'icon.png')

	if load then
		local f = io.open(load, "r")
		if f then
			r, e = instead.cmd("load "..load)
			f:close()
		else
			load = false
		end
	end
	if not load then
		r, e = instead.cmd"look"
	end
	if r then
		input_detach()
		if icon then
			mwin:add_img(icon)
		end
		if load then
			mwin:add("*** "..load)
			mwin:add(output(e))
		else
			mwin:add(output(e))
		end
		input_attach(input)
	else
		input_detach()
		mwin:add(output(e))
	end
	mwin.off = 0
	cleared = true
end

function instead_clear()
	mwin:set(false)
--	input_attach(input)
	mwin.off = 0
	cleared = true
end

function instead_savepath()
	if not GAME then return "" end
	if system.mkdir("./saves") then
		return "./saves"
	end
	local g = GAME:gsub("^.*[/\\]([^/\\]+)$", "%1")
	local h = os.getenv('HOME') or os.getenv('home')
	if h and
		system.mkdir(h.."/.reinstead") and
		system.mkdir(h.."/.reinstead/saves") then
		return h.."/.reinstead/saves/"..g
	end
	return "./saves"
end

local function save_path(w)
	return instead_savepath() .."/"..w:gsub("/", "_"):gsub("%.", "_"):gsub('"', "_")
end

local function instead_save(w)
	w = save_path(w)
	local r, e = instead.cmd("save "..w)
	input_detach()
	e = output(e)
	if not r then
		e = "Error! "..w
	else
		local msg = ''
		if e ~= '' and type(e) == 'string' then
			msg = '\n<i>'..e..'</i>'
		end
		e = "*** "..w..msg
	end
	mwin:add(e)
	input_attach(input)
	need_save = false
end

local function instead_load(w)
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

local function create_cursor()
	local h = mwin.lay.fonts.regular.h + math.ceil(SCALE * 2)
	local w = math.floor(3 * SCALE);
	if w < 3 then
		w = 1
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
local GAMES

local function dir_list(dir)
	if dir:find("./", 1, true) == 1 then
		dir = DATADIR .. '/' .. dir:sub(3)
	end
	GAMES = {}
	input_detach()
	mwin:set(false)
	if icon and conf.show_icons then
		local w, _ = icon:size()
		mwin:add_img(icon:scale(128 * SCALE/w))
	end
	if conf.dir_title then
		mwin:add("<c>"..conf.dir_title.."</c>\n\n")
	end
	local t = system.readdir(dir)
	for _, v in ipairs(t or {}) do
		local dirpath = dir .. '/'.. v
		local p = dirpath .. '/main3.lua'
		local f = io.open(p, 'r')
		if f then
			local name = instead_name(dirpath)
			if name == dirpath then name = v end
			f:close()
			table.insert(GAMES, { path = dirpath, name = name })
		end
	end
	table.sort(GAMES, function(a, b) return a.path < b.path end)
	for k, v in ipairs(GAMES) do
		--mwin:add_img(v.icon)
		mwin:add(string.format("<c>%s <i>(%d)</i></c>", v.name, k))
	end
	if #GAMES == 0 then
		mwin:set("No games in \""..dir.."\" found.")
	end
	mwin:add "\n"
	input_attach("")
	mwin.off = 0
end

local DIRECTORY = false

local function info()
	return "<c><b>RE:INSTEAD V"..VERSION.." by Peter Kosyh (2021)</b>\n".."<i>Platform: "..PLATFORM.." / ".._VERSION.."</i></c>\n\n".. (conf.note or '')
end

function core.init()
	local skip
	gfx.icon(icon)
	need_restart = false
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
	if conf.debug then
		instead.debug(true)
	end
	if not GAME and conf.autostart then
		GAME = conf.autostart
		if GAME:find("./", 1, true) == 1 then
			GAME = DATADIR .. '/' .. GAME:sub(3)
		end
	end
	print("scale: ", SCALE)
	if GAME then
		system.title(GAME)
	else
		system.title(conf.title)
	end
	local win = gfx.win()
	mwin = tbox:new()
	mwin:resize(win:size())
	win:clear(mwin.lay.bg)
	gfx.flip()

	create_cursor()

	if not GAME and conf.directory then
		dir_list(conf.directory)
		DIRECTORY = true
	end

	if GAME then
		instead_start(GAME, conf.autoload and (instead_savepath()..'/autosave'))
	elseif not DIRECTORY then
		mwin:set(info())
		mwin:add(string.format("<b>Usage:</b>\n<w:    >%s \\<game> [-debug] [-scale \\<f>]", EXEFILE))
		mwin:add('\nLook into "'..DATADIR..'/core/config.lua" for cusomization.')
		mwin:add('\n<b>Press ESC to exit.</b>')
	end
end

local alt = false
local control = false
local fullscreen = false

function core.run()
	while true do
		local start = system.time()
		if not dirty then
			while not system.wait(5) do end
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

		if (e == 'keydown' or e == 'keyup') and v:find"alt" then
			alt = (e == 'keydown')
		end

		if (e == 'keydown' or e == 'keyup') and v:find"ctrl" then
			control = (e == 'keydown')
		end
		if e == 'keydown' then
			if v == 'escape' and not GAME and not DIRECTORY then -- exit
				break
			elseif v == 'escape' then
				input_detach()
				mwin:add(conf.short_help)
				input_attach(input)
				dirty = true
			elseif v == 'backspace' then
				local t = utf.chars(input)
				if input_pos <= #t + 1 and input_pos > 1 then
					table.remove(t, input_pos - 1)
					input_pos = input_pos - 1
					if input_pos < 1 then input_pos = 1 end
				end
				input = table.concat(t, '')
				dirty = input_attach(input, true)
			elseif alt and v == 'return' then
				alt = false
				fullscreen = not fullscreen
				if fullscreen then
					system.window_mode 'fullscreen'
				else
					system.window_mode 'normal'
				end
			elseif v == 'return' or v:find 'enter' or (control and v == 'j') then
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
					elseif input == '/info' then
						v = info()
						r = true
					else
						r, v = instead.cmd(input:sub(2))
						r = true
					end
				elseif DIRECTORY and not GAME then
					local n = tonumber(input)
					if n then n = math.floor(n) end
					if not n or n > #GAMES or n < 1 then
						if #GAMES > 1 then
							v = '1 - ' .. tostring(#GAMES).. '?'
						else
							v = 'No games.'
						end
						r = true
					else
						GAME = GAMES[n].path
						instead_start(GAMES[n].path, conf.autoload and (instead_savepath()..'/autosave'))
						r = 'skip'
						v = false
					end
					cmd_mode = true
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
				if instead.error() then
					v = v ..'\n'.. instead.error("")
				end
				if not parser_mode and not cmd_mode then
					local _, w = instead.cmd "way"
					v = v .. '\n'
					if w ~= "" then
						v = v .. ">> "..w
					end
					_, w = instead.cmd "inv"
					if w ~= "" then
						v = v .. "** ".. w
					end
				end
				if r ~= 'skip' then
					input_history(input)
				end
				if v then
					mwin:add(output(v))
				end
				input = ''
				input_attach(input)
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
			elseif v == 'left' then
				input_pos = input_pos - 1
				if input_pos == 0 then input_pos = 1 end
				input_attach(input, true)
			elseif v == 'right' then
				input_pos = input_pos + 1
				local n = #utf.chars(input)
				if input_pos > n then
					input_pos = n + 1
				end
				input_attach(input, true)
			elseif v == 'a' and control or v == 'home' then
				input_pos = 1
				input_attach(input, true)
			elseif v == 'e' and control or v == 'end' then
				input_pos = #utf.chars(input) + 1
				input_attach(input, true)
			elseif ((v == 'k' or v == 'u') and control) or v == 'kill' then
				input = ''
				input_attach(input)
			elseif (v == 'pagedown' or (v == 'n' and control)) and
				mwin:scroll(mwin.scrollh) then
				dirty = true
			elseif (v == 'pageup' or (v == 'p' and control)) and
				mwin:scroll(-mwin.scrollh) then
				dirty = true
			end
		elseif e == 'text' then
			if v == ' ' and mwin:scroll(mwin.scrollh) then
				dirty = true
			else
				local t = utf.chars(input)
				table.insert(t, input_pos, v)
				input = table.concat(t, '')
				input_pos = input_pos + 1
				dirty = input_attach(input, true)
			end
		elseif e == 'mousedown' or e == 'mousemotion' or e == 'mouseup' then
			dirty = mwin:mouse(e, v, a, b)
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
			if conf.autoload then
				os.remove (instead_savepath()..'/autosave')
			end
			instead_done()
			if GAME and not DIRECTORY then
				instead_start(GAME)
			elseif DIRECTORY then
				GAME = false
				core.init()
			end
		end
		local elapsed = system.time() - start
--		system.sleep(math.max(0, fps - elapsed))
		system.wait(math.max(0, fps - elapsed))
	end
	if conf.autosave and GAME then
		instead_save 'autosave'
	end
	instead.done()
end
return core
