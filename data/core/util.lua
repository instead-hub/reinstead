local utf = require "utf"

local util = {}

function util.game_icon(dirpath)
	local icon = gfx.new(dirpath..'/icon.png')
	if icon then
		local w, _ = icon:size()
		icon = icon:scale(128 * SCALE/w)
	end
	return icon
end

function util.win_icon(icon)
	if not icon then return end
	local w, _ = icon:size()
	if w > 64.0 then
		icon = icon:scale(64 * SCALE/w)
	end
	gfx.icon(icon)
end

function util.basename(p)
	p = p:gsub("^.*[/\\]([^/\\]+)$", "%1")
	return p
end

function util.output(str)
	str = str:gsub("^\n+",""):gsub("\n+$","")
	if str ~= "" then return str .. '\n\n' end
	return str
end

function util.write(fn, string)
	local f = io.open(fn, "w")
	if not f then return false end
	if not f:write(string) then
		f:close()
		return false
	end
	return f:close()
end

local function game_tag(name, l)
	local tag
	l = l:gsub("\r", "")
	if l:find("^[ \t]*--[ \t]*%$"..name..":") then
		local _, e = l:find("$"..name..":", 1, true)
		tag = l:sub(e + 1):gsub("^[ \t]+", ""):gsub("[ \t%$]$", ""):gsub("\\n", "\n")
	end
	return tag
end

function util.game_tags(game)
	local gameinfo = { }
	local f = io.open(game..'/main3.lua', "r")
	if not f then
		gameinfo.name = game
		return gameinfo
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
	gameinfo.name = gameinfo.name or util.basename(game)
	return gameinfo
end

function util.instead_savepath(GAME, w)
	w = w and utf.strip(w):gsub("\\","/")
	if not w or w == "" then w = 'autosave' else w = util.basename(w) end
	return util.instead_savedir(GAME) .."/"..w:gsub("/", "_"):gsub("%.", "_"):gsub('"', "_")
end

function util.instead_savedir(GAME)
	if not GAME then return "" end
	if not conf.appdata and system.mkdir("./saves") then
		return "./saves"
	end
	local g = util.basename(GAME)
	local h = conf.appdata or os.getenv('HOME') or os.getenv('home')
	if h then
		local path = string.format("%s/.reinstead", h)
		if conf.appdata then path = h end
		if system.mkdir(path) and
			system.mkdir(path .."/saves") then
			return path .. "/saves/"..g
		end
	end
	return "./saves"
end

function util.datadir(dir)
	local absolute
	if PLATFORM == "Windows" then
		absolute = (dir:sub(2,2) == ':')
	else
		absolute = (dir:sub(1,1) == '/')
	end
	if not absolute then
		dir = dir:gsub("^%./", "")
		dir = DATADIR .. '/' .. dir
	end
	return dir
end

function util.cmd_aliases(cmd)
	if type(conf.cmd_aliases) ~= 'table' then
		return cmd
	end
	for k, v in pairs(conf.cmd_aliases) do
		local _, e = cmd:find(k, 1, true)
		if e then
			local c = cmd:sub(e+1, e+1)
			if c == '' or c == ' ' then
				cmd = v .. cmd:sub(e + 1)
				break
			end
		end
	end
	return cmd
end

function util.write_settings(cfg)
	local h = os.getenv('HOME') or os.getenv('home')
	if h and system.mkdir(h.."/.reinstead") then
		if util.write(h.."/.reinstead/settings", cfg) then
			return true
		end
	end
	return false
end

function util.open_settings()
	if not conf.settings then
		return false
	end
	local f = io.open((conf.appdata or DATADIR)..'/settings', 'r')
	if f then
		return f
	end
	if conf.appdata then
		return false
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

function util.gameinfo(gameinfo)
	local t = gameinfo.name
	if gameinfo.author then t = t .." / "..gameinfo.author end
	if gameinfo.version then t = t.."\nVersion: "..gameinfo.version end
	if gameinfo.info then t = t .. "\n"..gameinfo.info end
	return t
end

function util.info()
	local luaver = _VERSION
	if type(jit) == 'table' and type(jit.version) == 'string' then
		luaver = jit.version
	end
	return "<c><b>RE:INSTEAD v"..VERSION.." by Peter Kosyh (2021-2024)</b>\n"..
		"<i>Platform: "..PLATFORM.." / "..luaver.."</i>\n"..
		"<i>Font renderer: "..FONTRENDERER.."</i></c>\n\n".. (conf.note or '')
end

function util.scangames(dirs, fn)
	for _, dir in ipairs(dirs) do
		dir = util.datadir(dir)
		local t = system.readdir(dir)
		for _, v in ipairs(t or {}) do
			local dirpath = dir .. '/'.. v
			local p = dirpath .. '/main3.lua'
			local f = io.open(p, 'r')
			if f then
				fn(dirpath, v)
				f:close()
			end
		end
	end
end

function util.strip_tags(str)
	if str == '' or not str then return str end
	str = utf.strip(str)
	str = str:gsub("</?[icrb]>", ""):gsub("<g:[^>]*>", ""):gsub("<w:([^>]*)>","%1")
	return str
end

return util
