local VERSION='0.4'
conf = require "config"
local iface = require "iface"

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

local function output(str)
	str = str:gsub("^\n+",""):gsub("\n+$","")
	if str ~= "" then return str .. '\n\n' end
	return str
end

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

local function instead_icon(dirpath, norm)
	local icon = gfx.new(dirpath..'/icon.png')
	if icon and norm then
		local w, _ = icon:size()
		icon = icon:scale(128 * SCALE/w)
	end
	return icon
end

local function basename(p)
	p = p:gsub("^.*[/\\]([^/\\]+)$", "%1")
	return p
end

local function game_tag(name, l)
	local tag
	l = l:gsub("\r", "")
	if l:find("^[ \t]*--[ \t]*%$"..name..":") then
		local _, e = l:find("$"..name..":", 1, true)
		tag = l:sub(e + 1):gsub("^[ \t]*", ""):gsub("[ \t%$]$", ""):gsub("\\n", "\n")
	end
	return tag
end

local function instead_tags(game)
	gameinfo = { }
	local f = io.open(game..'/main3.lua', "r")
	if not f then
		gameinfo.name = game
		return
	end
	local n = 16
	for l in f:lines() do
		n = n - 1
		if n < 0 then break end
		gameinfo.name = gameinfo.name or game_tag("Name", l)
		gameinfo.author = gameinfo.author or game_tag("Author", l)
		gameinfo.version = gameinfo.version or game_tag("Version", l)
		gameinfo.info = gameinfo.info or game_tag("Info", l)
	end
	f:close()
	gameinfo.name = gameinfo.name or basename(game)
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
	instead_tags(game)
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
	system.title(gameinfo.name)
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
	if instead.error() then
		e = e.. '\n'.. instead.error("")
	end
	if r then
		iface.input_detach()
		if icon then
			mwin:add_img(icon)
		end
		if load then
			mwin:add("*** "..basename(load))
			mwin:add(output(e))
			iface.tts_more(basename(load).. '\n'..e)
		else
			mwin:add(output(e))
			iface.tts_more(e)
		end
		iface.input_attach()
	else
		iface.input_detach()
		mwin:add(output(e))
		iface.tts_more(e)
	end
	mwin.off = 0
	cleared = true
end

function instead_clear()
	mwin:set(false)
--	iface.input_attach(input)
	mwin.off = 0
	cleared = true
end

local function write(fn, string)
	local f = io.open(fn, "w")
	if not f then return false end
	if not f:write(string) then
		f:close()
		return false
	end
	return f:close()
end

function open_settings()
	if not conf.settings then
		return false
	end
	local f = io.open(DATADIR..'/settings', 'r')
	if f then
		return f
	end
	local h = os.getenv('HOME') or os.getenv('home')
	if h then
		f = io.open(h.."/.reinstead/settings", "r")
		if f then
			return f
		end
	end
	return false
end

function instead_savepath()
	if not GAME then return "" end
	if system.mkdir("./saves") then
		return "./saves"
	end
	local g = basename(GAME)
	local h = os.getenv('HOME') or os.getenv('home')
	if h and
		system.mkdir(h.."/.reinstead") and
		system.mkdir(h.."/.reinstead/saves") then
		return h.."/.reinstead/saves/"..g
	end
	return "./saves"
end

local function save_path(w)
	w = w and w:gsub("^[ \t]+", ""):gsub("[ \t]+$", ""):gsub("\\","/")
	if not w or w == "" then w = 'autosave' else w = basename(w) end
	return instead_savepath() .."/"..w:gsub("/", "_"):gsub("%.", "_"):gsub('"', "_")
end

local function instead_save(w, silent)
	need_save = false
	w = save_path(w)
	local r, e
	iface.input_detach()
	if not GAME then
		r, e = true, "No game."
	else
		if not silent then
			instead_clear()
		end
		r, e = instead.cmd("save "..w)
	end
	e = output(e)
	if not r then
		e = "Error! "..w
	else
		local msg = ''
		if e ~= '' and type(e) == 'string' then
			msg = '\n'..e
		end
		e = "*** "..basename(w)..msg
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
	w = save_path(w)
	local f = io.open(w, "r")
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

function instead_settings()
	if not conf.settings then
		return false
	end
	local p = DATADIR..'/settings'
	local cfg = ''
	if iface.tts_mode() and not system.is_speak() then
		cfg = cfg .. "/tts on\n"
	end
	cfg = cfg .. string.format("/font %d\n", conf.fsize)
	if GAME and conf.settings_game then
		cfg = cfg .. string.format("/game %s\n", GAME)
	end
	if write(p, cfg) then
		return true
	end
	local h = os.getenv('HOME') or os.getenv('home')
	if h and system.mkdir(h.."/.reinstead") then
		if write(h.."/.reinstead/settings", cfg) then
			return true
		end
	end
	return false
end

local function datadir(dir)
	if dir:find("./", 1, true) == 1 then
		dir = DATADIR .. '/' .. dir:sub(3)
	end
	return dir
end

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
	for _, dir in ipairs(dirs) do
		dir = datadir(dir)
		local t = system.readdir(dir)
		for _, v in ipairs(t or {}) do
			local dirpath = dir .. '/'.. v
			local p = dirpath .. '/main3.lua'
			local f = io.open(p, 'r')
			if f then
				instead_tags(dirpath)
				local name = gameinfo.name
				if name == dirpath then name = v end
				f:close()
				table.insert(GAMES, { path = dirpath, name = name })
			end
		end
	end
	table.sort(GAMES, function(a, b) return a.path < b.path end)
	for k, v in ipairs(GAMES) do
		--mwin:add_img(v.icon)
		mwin:add(string.format("<c>%s <i>(%d)</i></c>", v.name, k))
		iface.tts_more(string.format("%s %d\n", v.name, k))
	end
	if #GAMES == 0 then
		mwin:set("No games in \""..dir.."\" found.")
	end
	mwin:add "\n"
	iface.input_kill()
	mwin.off = 0
end

local DIRECTORY = false

local function info()
	if GAME then
		local t = gameinfo.name
		if gameinfo.author then t = t .." / "..gameinfo.author end
		if gameinfo.version then t = t.."\nVersion: "..gameinfo.version end
		if gameinfo.info then t = t .. "\n"..gameinfo.info end
		return t
	end
	return "<c><b>RE:INSTEAD v"..VERSION.." by Peter Kosyh (2021)</b>\n"..
		"<i>Platform: "..PLATFORM.." / ".._VERSION.."</i></c>\n\n".. (conf.note or '')
end

local loading_settings = false

function core.init()
	local skip
	for k=2, #ARGS do
		local a = ARGS[k]
		if skip then
			skip = false
		elseif a:find("-", 1, true) ~= 1 then
			GAME = a
		elseif a == "-debug" or a == "-d" then
			instead.debug(true)
		elseif a == '-i' then
			AUTOSCRIPT = ARGS[k+1] or "autoscript"
			skip = true
		elseif a == '-h' or a == '-help' then
			print("RE:INSTEAD v"..VERSION)
			print(string.format("Usage:\n\t%s [gamedir] [-debug] [-i <autoscript>] [-scale <f>]", EXEFILE))
			os.exit(0)
		elseif a == "-scale" then
			SCALE = tonumber(ARGS[k+1] or "1.0")
			skip = true
		end
	end
	if AUTOSCRIPT then
		local a, e = io.open(AUTOSCRIPT, "r")
		if a then
			print("Using input file: " .. AUTOSCRIPT)
		else
			print("Input file: " .. e)
		end
		AUTOSCRIPT = { a }
	else
		AUTOSCRIPT = { }
	end
	local f = open_settings()
	if f then
		table.insert(AUTOSCRIPT, 1, f)
		loading_settings = true
	end
	if conf.debug then
		instead.debug(true)
	end

	print("scale: ", SCALE)
	if system.is_speak() then
		iface.speak_mode(true)
	end
	core.start()
end

function core.start()
	gfx.icon(icon)
	need_restart = false

	if not GAME and conf.autostart then
		GAME = conf.autostart
		if GAME:find("./", 1, true) == 1 then
			GAME = datadir(GAME)
		elseif conf.directory then
			GAME = datadir(conf.directory)..'/'..GAME
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
		instead_start(GAME, conf.autoload and (instead_savepath()..'/autosave'))
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

function core.run()
	while true do
		local start = system.time()
		if not dirty and not AUTOSCRIPT[1] then
			while not system.wait(5) do end
		else
			if system.time() - last_render > fps then
				mwin:render()
				gfx.flip()
				dirty = false
				last_render = system.time()
			end
		end
		local e, v, a, b, nv
		e, v, a, b = system.poll()
		if e ~= 'quit' and e ~= 'exposed' and e ~= 'resized' then
			nv = AUTOSCRIPT[1] and AUTOSCRIPT[1]:read("*line")
			if not nv and AUTOSCRIPT[1] then
				AUTOSCRIPT[1]:close()
				table.remove(AUTOSCRIPT, 1)
				loading_settings = false
				gfx.flip()
			end
			if nv then
				iface.input_set(nv:gsub("[\r\n]",""))
				e = 'keydown'
				v = 'return'
			end
		end
		if e == 'quit' then
			break
		end
		if e == 'save' then
			instead_settings()
			if conf.autosave and GAME then
				instead_save ('autosave', true)
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
				break
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
			elseif alt and v == 'return' then
				alt = false
				fullscreen = not fullscreen
				if fullscreen then
					system.window_mode 'fullscreen'
				else
					system.window_mode 'normal'
				end
			elseif (control and (v == '=' or v == '-' or v == '0')) or v == '++' or v == '--' or v == '==' then
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
				font_changed()
			elseif (control and v == 'w') or v == 'Ketb' then
				dirty = iface.input_etb() or dirty
			elseif v == 'return' or v:find 'enter' or (control and v == 'j') then
				local oh = mwin:texth()
				local off = mwin.off
				local r, v
				local cmd_mode
				local input = iface.input():gsub("^ +", ""):gsub(" +$", "")
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
					elseif input == '/tts on' then -- settings?
						iface.tts_mode(true)
						r = true
					elseif input == '/tts' then -- toggle
						if not iface.tts_mode(not iface.tts_mode()) then
							iface.tts(false)
						end
						r = true
					elseif input:find("/load", 1, true) == 1 then
						need_load = input:sub(6)
						r = true
					elseif input:find("/save", 1, true) == 1 then
						need_save = input:sub(6)
						r = true
					elseif input:find("/font +[0-9]+", 1) == 1 then
						conf.fsize = (tonumber(input:sub(7)) or conf.fsize)
						if conf.fsize < FONT_MIN then conf.fsize = FONT_MIN end
						if conf.fsize > FONT_MAX then conf.fsize = FONT_MAX end
						font_changed()
						r = true
					elseif input:find("/font", 1) == 1 then
						v = tostring(conf.fsize)
						r = true
					elseif input:find("/game .+", 1) == 1 then
						if not AUTOSCRIPT[1] or (not GAME and conf.settings_game) then
							local p = input:sub(7):gsub("^ +", ""):gsub(" +$", "")
							instead_settings() -- if game crashed
							GAME = datadir(p)
							instead_start(GAME, conf.autoload and (instead_savepath()..'/autosave'))
						end
						r = 'hidden'
						v = false
					else
						r, v = instead.cmd(input:sub(2))
						if r == false and v == '' then v = '?' end
						r = true
					end
				elseif DIRECTORY and not GAME then
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
					if type(v) ~= 'string' then v = '' end
					v = v ..'\n('.. instead.error("")..')'
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
					iface.input_history(input, r ~= 'hidden')
					iface.tts_more(input..'\n')
				end
				if v then
					mwin:add(output(v))
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
				os.remove (instead_savepath()..'/autosave')
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
--		system.sleep(math.max(0, fps - elapsed))
		iface.tts()
		if not AUTOSCRIPT[1] then
			system.wait(math.max(0, fps - elapsed))
		end
		cleared = false
	end
	if conf.autosave and GAME then
		instead_save 'autosave'
	end
	instead.done()
	instead_settings()
end
return core
