VERSION='0.7'
conf = require "config"
local iface = require "iface"
local utf = require "utf"
local util = require "util"

local gameinfo = {}

local FONT_MIN = 10
local FONT_MAX = 64
local FONT_DEF = conf.fsize
math.round = function(num, n)
	local m = 10 ^ (n or 0)
	return math.floor(num * m + 0.5) / m
end

if conf.scale == false then SCALE = 1.0 end
if type(conf.scale) == 'number' then SCALE = conf.scale end

local core = {}
local mwin
local cleared = false

local dirty = false
local last_render = 0
local fps = 1/conf.fps;
local GAME = false

local icon = gfx.new(DATADIR..'/icon.png')

local busy_time = false

function instead_busy(busy)
	if not busy then
		busy_time = false
		iface.input_detach()
		return
	end
	local t = system.time()
	if not busy_time then
		busy_time = t
		return
	end
	if t - last_render > 1/10 and t - busy_time > 3 then
		system.poll()
		iface.input_attach('Wait, please...')
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

function instead_settings()
	if not conf.settings then
		return false
	end
	local p = (conf.appdata or DATADIR)..'/settings'
	local cfg = ''
	if iface.tts_mode() and not system.is_speak() and not conf.tts then
		cfg = cfg .. "!tts on\n"
	end
	cfg = cfg .. string.format("!font %d\n", conf.fsize)
	if GAME and conf.settings_game then
		cfg = cfg .. string.format("!game %s\n", GAME)
	end
	if util.write(p, cfg) then
		return true
	end
	if conf.appdata then
		return false
	end
	return util.write_settings(cfg)
end

local parser_mode = false
local menu_mode = false

local function savepath(load)
	return util.instead_savepath(GAME, load)
end

local function instead_start(game, load)
	need_restart = false
	parser_mode = false
	menu_mode = false
	local icon
	if conf.show_icons then
		icon = util.game_icon(game)
	end
	gameinfo = util.game_tags(game)
	mwin:set(false)
	local r, e = instead.init(game)
	if not r then
		mwin:set(string.format("Trying: %q", game)..'\n'..e)
		return
	end
	r = system.mkdir(util.instead_savedir(GAME))
	if not r then
		mwin:set("Can't create "..util.instead_savedir(GAME).." dir.")
		return
	end
	system.title(gameinfo.name)
	util.win_icon(gfx.new 'icon.png')

	if load then
		local f = io.open(savepath(load), "r")
		if f then
			r, e = instead.cmd("load "..savepath(load))
			f:close()
		else
			load = false
		end
	end
	if not load then
		r, e = instead.cmd"look"
	end
	if instead.error() then
		e = e.. '\n'.. instead.error("")
	end
	if r then
		iface.input_detach()
		if icon then
			mwin:add_img(icon)
		end
		if load then
			e = "*** "..util.basename(savepath(load)) .. "\n" .. (e or '')
			mwin:add(util.output(e))
		else
			mwin:add(util.output(e))
		end
		iface.input_attach()
	else
		iface.input_detach()
		mwin:add(util.output(e))
	end
	iface.tts_more(e)
	mwin.off = 0
	cleared = true
end

function instead_clear()
	mwin:set(false)
--	iface.input_attach(input)
	mwin.off = 0
	cleared = true
end

local function instead_save(w, silent)
	need_save = false
	local r, e
	iface.input_detach()
	if not GAME then
		r, e = true, "No game."
	else
		if not silent then
			instead_clear()
		end
		r, e = instead.cmd("save "..savepath(w))
	end
	e = util.output(e)
	if not r then
		e = "Error! "..w
	else
		local msg = ''
		if e ~= '' and type(e) == 'string' then
			msg = '\n'..e
		end
		e = "*** "..util.basename(savepath(w))..msg
	end
	if not silent then
		mwin:add(e)
		iface.tts_more(e)
	end
	iface.input_attach()
end

local function instead_load(w)
	need_load = false
	if not GAME then
		iface.input_detach()
		mwin:add("No game.\n\n")
		iface.input_kill()
		return
	end
	local rw = savepath(w)
	local f = io.open(rw, "r")
	if not f then
		iface.input_detach()
		mwin:add("No file.\n\n")
		iface.input_kill()
		return
	end
	f:close()
	instead_done()
	instead_start(GAME, w)
end

local GAMES

local function dir_list(dirs)
	dirs = type(dirs) == 'table' and dirs or { dirs }
	GAMES = {}
	iface.input_detach()
	mwin:set(false)
	if icon and conf.show_icons then
		local w, _ = icon:size()
		mwin:add_img(icon:scale(128 * SCALE/w))
	end
	if conf.dir_title then
		mwin:add("<c>"..conf.dir_title.."</c>\n\n")
	end
	util.scangames(dirs, function(dirpath, v)
		local gameinfo = util.game_tags(dirpath)
		local name = gameinfo.name
		if name == dirpath then name = v end
		table.insert(GAMES, { path = dirpath, name = name })
	end)
	table.sort(GAMES, function(a, b) return a.path < b.path end)
	for k, v in ipairs(GAMES) do
		--mwin:add_img(v.icon)
		mwin:add(string.format("<c>%s <i>(%d)</i></c>", v.name, k))
		iface.tts_more(string.format("%s %d\n", v.name, k))
	end
	if #GAMES == 0 then
		mwin:set("No games in \""..dirs[1].."\" found.")
	end
	mwin:add "\n"
	iface.input_kill()
	mwin.off = 0
end

local DIRECTORY = false

local function info()
	if GAME then
		return util.gameinfo(gameinfo)
	end
	return util.info()
end

local loading_settings = false

local function autoscript_push(fname)
	local f, e
	if not fname or fname == '' then fname = 'autoscript' end
	if type(fname) == 'string' then
		f, e = io.open(fname, "r")
		if f then
			print("Using input file: " .. fname)
		else
			print("Input file: " .. e)
			return
		end
	else
		f = fname
	end
	if not AUTOSCRIPT then
		AUTOSCRIPT = { f }
	else
		table.insert(AUTOSCRIPT, 1, f)
	end
end

local function autoscript_pop(err)
	if not AUTOSCRIPT[1] then
		return
	end
	AUTOSCRIPT[1]:close()
	table.remove(AUTOSCRIPT, 1)
	loading_settings = false
	return true
end

local function autoscript_stop()
	while autoscript_pop() do end
end

function core.init()
	local skip
	for k=2, #ARGS do
		local a = ARGS[k]
		if skip then
			skip = false
		elseif a:find("-", 1, true) ~= 1 then
			GAME = a
		elseif a == "-appdata" then
			APPDATA = ARGS[k+1] or false
			conf.appdata = APPDATA
			skip = true
		elseif a == "-debug" or a == "-d" then
			instead.debug(true)
		elseif a == "-tts" then
			conf.tts = true
		elseif a == '-noautoload' then
			conf.autoload = false
		elseif a == '-noautosave' then
			conf.autosave = false
		elseif a == '-i' then
			local script = ARGS[k+1] or "autoscript"
			conf.autoload = false
			skip = true
			autoscript_push(script)
		elseif a == '-h' or a == '-help' then
			print("RE:INSTEAD v"..VERSION)
			print(string.format("Usage:\n\t%s [gamedir] [-debug] [-i <autoscript>] [-scale <f>]", EXEFILE))
			os.exit(0)
		elseif a == "-scale" then
			SCALE = tonumber(ARGS[k+1] or "1.0")
			skip = true
		else
			print("Unknown option: "..a)
		end
	end
	local f = util.open_settings()
	if f then
		autoscript_push(f)
		loading_settings = true
	end
	if conf.debug then
		instead.debug(true)
	end
	if conf.appdata then
		conf.appdata = util.datadir(conf.appdata)
	end
	print("scale: ", SCALE)
	if system.is_speak() or conf.tts then
		system.input()
		iface.tts_mode(true)
	end
	core.start()
end

function core.start()
	util.win_icon(icon)
	need_restart = false

	if not GAME and conf.autostart then
		GAME = conf.autostart
		if GAME:find("./", 1, true) == 1 then
			GAME = util.datadir(GAME)
		elseif conf.directory then
			GAME = util.datadir(conf.directory)..'/'..GAME
		end
	end
	if GAME then
		system.title(GAME)
	else
		system.title(conf.title)
	end

	gfx.win():clear(conf.bg)
	gfx.flip()

	mwin = iface.win()

	if not GAME and conf.directory then
		dir_list(conf.directory)
		DIRECTORY = true
	end

	if GAME then
		instead_start(GAME, conf.autoload and 'autosave')
	elseif not DIRECTORY then
		mwin:set(info())
		mwin:add(string.format("<b>Usage:</b>\n<w:    >%s \\<game> [-debug] [-scale \\<f>]", EXEFILE))
		mwin:add('\nLook into "'..DATADIR..'/core/config.lua" for cusomization.')
		mwin:add('\n<b>Press ESC to exit.</b>')
	end
	dirty = true
end

local alt = false
local control = false
local fullscreen = false

local function font_changed()
	mwin = iface.reset()
	dirty = true
end


local function commands_mode(input)
	local cmd = utf.strip(input:sub(2))
	cmd = util.cmd_aliases(cmd)
	local a = utf.split(cmd)
	local r = true
	local v
	if cmd == 'restart' then
		need_restart = true
		v = ''
	elseif cmd == 'quit' then
		return 'break'
	elseif cmd == 'stop' then
		autoscript_stop()
	elseif cmd == 'info' then
		v = info()
	elseif cmd == 'tts on' then -- settings?
		iface.tts_mode(true)
		iface.tts_replay()
	elseif a[1] == 'debug' then
		if a[2] == 'off' then
			v = 'Debug mode off'
			instead.debug(false)
		else
			v = 'Debug mode on'
			instead.debug(true)
		end
	elseif cmd == 'tts' then -- toggle
		iface.tts_mode(not iface.tts_mode())
	elseif cmd:find("script ", 1, true) == 1 or cmd == 'script' then
		autoscript_push(utf.strip(input:sub(8)))
	elseif cmd:find("load ", 1, true) == 1 or cmd == "load" then
		need_load = cmd:sub(6)
	elseif cmd:find("save ", 1, true) == 1 or cmd == "save" then
		need_save = cmd:sub(6)
	elseif cmd:find("rm ", 1, true) == 1 or cmd == "rm" then
		if not GAME then
			v = "No game."
		else
			os.remove(savepath(utf.strip(cmd:sub(4)) or "autosave"))
		end
	elseif cmd == "saves" or cmd == "ls" then
		if not GAME then
			v = "No game."
		else
			local t = system.readdir(util.instead_savedir(GAME))
			table.sort(t)
			v = ''
			for _, f in ipairs(t) do
				v = v .. f..'\n'
			end
		end
	elseif cmd:find("font ", 1) == 1 then
		conf.fsize = (tonumber(a[2]) or FONT_DEF)
		if conf.fsize < FONT_MIN then conf.fsize = FONT_MIN end
		if conf.fsize > FONT_MAX then conf.fsize = FONT_MAX end
		font_changed()
	elseif cmd == "font" then
		v = tostring(conf.fsize)
	elseif cmd:find("game .+", 1) == 1 then
		if not GAME then
			local p = utf.strip(cmd:sub(6))
			instead_settings() -- if game crashed
			GAME = util.datadir(p)
			iface.tts(false)
			instead_start(GAME, conf.autoload and 'autosave')
		end
		r = 'hidden'
		v = false
	elseif input:find("/", 1, true) then
		r, v = instead.cmd(cmd)
		if r == false and v == '' then v = '?' end
		r = true
	else
		r = nil
	end
	return r, v
end

local function dir_mode(input)
	local r, v
	local n = tonumber(input)
	if n then n = math.floor(n) end
	if not n or n > #GAMES or n < 1 then
		if #GAMES > 1 then
			dir_list(conf.directory)
			v = '1 - ' .. tostring(#GAMES).. '?'
		else
			v = 'No games.'
		end
		r = true
	else
		GAME = GAMES[n].path
		instead_start(GAMES[n].path, conf.autoload and 'autosave')
		r = 'skip'
		v = false
	end
	return r, v
end

local function font_adjust(v)
	if v == '=' or v == '++' then
		conf.fsize = conf.fsize + 1
	elseif v == '-' or v == '--' then
		conf.fsize = conf.fsize - 1
	else
		conf.fsize = FONT_DEF
	end
	if conf.fsize < FONT_MIN then
		conf.fsize = FONT_MIN
	end
	if conf.fsize > FONT_MAX then
		conf.fsize = FONT_MAX
	end
end

function core.run()
	local start = system.time()
	if not dirty and not AUTOSCRIPT[1] then
		while not system.wait(5) do end
	else
		if system.time() - last_render > fps and not loading_settings then
			mwin:render()
			gfx.flip()
			dirty = false
			last_render = system.time()
		end
	end
	local e, v, a, b, nv
	e, v, a, b = system.poll()
	-- system.log(string.format("%q %q", e or 'nil', v or 'nil'))
	if e ~= 'quit' and e ~= 'exposed' and e ~= 'resized' then
		nv = AUTOSCRIPT[1] and AUTOSCRIPT[1]:read("*line")
		if not nv and AUTOSCRIPT[1] then
			autoscript_pop()
			gfx.flip()
		end
		if nv then
			iface.input_set(nv:gsub("[\r\n]",""))
			e = 'keydown'
			v = 'return'
		end
	end
	if e == 'quit' then
		return false
	end
	if e == 'save' then
		instead_settings()
		if conf.autosave and GAME then
			instead_save('autosave', true)
		end
	end
	if (e == 'keydown' or e == 'keyup') and v:find"alt" then
		alt = (e == 'keydown')
	end

	if (e == 'keydown' or e == 'keyup') and v:find"ctrl" then
		control = (e == 'keydown')
	end
	if e == 'keydown' then
		if v == 'escape' and not GAME and not DIRECTORY then -- exit
			return false
		elseif v == 'f5' then
			iface.tts_replay()
		elseif v == 'escape' or v == 'ac back' then
			iface.input_detach()
			if iface.input() ~= '' then
				iface.input_set ''
			else
				mwin:add(conf.short_help)
				iface.tts_more(conf.short_help)
			end
			iface.input_attach()
			dirty = true
		elseif v == 'backspace' or (control and v == 'h') then
			dirty = iface.input_bs() or dirty
		elseif v == 'delete' then
			dirty = iface.input_bs(true) or dirty
		elseif alt and v == 'return' then
			alt = false
			fullscreen = not fullscreen
			if fullscreen then
				system.window_mode 'fullscreen'
			else
				system.window_mode 'normal'
			end
		elseif (control and (v == '=' or v == '-' or v == '0')) or v == '++' or v == '--' or v == '==' then
			font_adjust(v)
			font_changed()
		elseif (control and v == 'w') or v == 'Ketb' then
			dirty = iface.input_etb() or dirty
		elseif v == 'return' or v:find 'enter' or (control and v == 'j') then
			local oh = mwin:texth()
			local off = mwin.off
			local r, v
			local cmd_mode
			local input = utf.strip(iface.input())
			if input:find("/", 1, true) == 1 or input:find("!", 1, true) == 1 then
				cmd_mode = true
				r, v = commands_mode(input)
				if r == 'break' then
					return false
				end
			end
			if not r and DIRECTORY and not GAME then
				cmd_mode = true
				r, v = dir_mode(input)
			elseif not r and not parser_mode then
				r, v = instead.cmd(string.format("use %s", input))
				if not r then
					r, v = instead.cmd(string.format("go %s", input))
				end
				if r then
					menu_mode = true
				end
			end
			if not r and not menu_mode and r ~= "" then
				r, v = instead.cmd(string.format("@metaparser %q", input:gsub("[<>]", "")))
				if r then
					parser_mode = true
				end
			end
			if not r then
				r, v = instead.cmd(string.format("act %s", input))
			end
			if instead.error() then
				if type(v) ~= 'string' then v = '' end
				v = v ..'\n('.. instead.error("")..')'
				autoscript_stop()
			end
			if not parser_mode and not cmd_mode and false then -- disabled for parser games
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
			iface.input_detach()
			if not loading_settings and r ~= 'skip' and (r or v ~= '') then
				iface.input_history(input, r ~= 'hidden' and not cleared)
				iface.tts_more(input..'\n')
			end
			if v then
				mwin:add(util.output(v))
				iface.tts_more(v)
			end
			iface.input_kill()
			if not cleared then
				if loading_settings then
					mwin.off = off
				else
					mwin.off = oh
				end
			else
				mwin.off = 0
			end
			mwin:scroll(0)
			dirty = true
		elseif v == 'up' then
			dirty = iface.history_prev() or dirty
		elseif v == 'down' then
			dirty = iface.history_next() or dirty
		elseif v == 'left' then
			dirty = iface.input_left() or dirty
		elseif v == 'right' then
			dirty = iface.input_right() or dirty
		elseif v == 'a' and control or v == 'home' then
			dirty = iface.input_home() or dirty
		elseif v == 'e' and control or v == 'end' then
			dirty = iface.input_end() or dirty
		elseif ((v == 'k' or v == 'u') and control) or v == 'Knack' then
			dirty = iface.input_kill() or dirty
		elseif (v == 'pagedown' or (v == 'n' and control)) and
			mwin:scroll(mwin.scrollh) then
			dirty = true
		elseif (v == 'pageup' or (v == 'p' and control)) and
			mwin:scroll(-mwin.scrollh) then
			dirty = true
		end
	elseif e == 'edit' then
		dirty = iface.input_edit(v) or dirty
	elseif e == 'text' and not control and not alt then
		if v == ' ' and mwin:scroll(mwin.scrollh) then
			dirty = true
		else
			dirty = iface.input_text(v) or dirty
		end
	elseif e == 'mousedown' or e == 'mousemotion' or e == 'mouseup' then
		dirty = iface.mouse(e, v, a, b) or dirty
	elseif e == 'exposed' or e == 'resized' then
		local iv = iface.input_visible()
		local oh = mwin.h
		mwin:resize(gfx.win():size())
		if iv then
			mwin:scroll(oh)
		else
			mwin:scroll(0)
		end
		dirty = true
	elseif e == 'mousewheel' then
		if conf.scroll_inverse then
			v = -v
		end
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
		instead_settings()
		if conf.autoload then
			os.remove(util.instead_savedir(GAME)..'/autosave')
		end
		instead_done()
		if GAME and not DIRECTORY then
			instead_start(GAME)
		elseif DIRECTORY then
			GAME = false
			core.start()
		end
	end
	local elapsed = system.time() - start
	if not loading_settings and iface.tts() and system.is_speak() then
		system.input()
	end
	if not AUTOSCRIPT[1] then
		system.wait(math.max(0, fps - elapsed))
	end
	cleared = false
	return true
end

function core.done()
	if conf.autosave and GAME then
		instead_save 'autosave'
	end
	iface.tts(false)
	instead.done()
	instead_settings()
end
return core
