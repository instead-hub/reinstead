if API ~= 'stead3' then
	return
end

require 'tiny3'

local re_eval = core_eval
function core_eval() end

local instead = std '@instead'
instead.reinstead = true
std.busy = function(busy)
	re_eval ('instead_busy('..(busy and 'true' or 'false')..')')
end

local iface = std '@iface'
instead.music_callback = function() end
instead.restart = function()
	re_eval 'need_restart = true'
end

instead.savepath = function()
	local r, v = re_eval 'return instead_savepath()'
	return v
end
instead_savepath = instead.savepath

std.savepath = instead.savepath
function iface:em(str)
	if type(str) == 'string' then
		return '<i>'..str..'</i>'
	end
end

function iface:bold(str)
	if type(str) == 'string' then
		return '<b>'..str..'</b>'
	end
end

function iface:right(str)
	if type(str) == 'string' then
		return '<r>'..str..'</r>'
	end
end

function iface:center(str)
	if type(str) == 'string' then
		return '<c>'..str..'</c>'
	end
end

function iface:nb(str)
	if type(str) == 'string' then
		return '<w:'..str:gsub(">","\\>")..'>'
	end
end

function iface:img(str)
	if type(str) == 'string' then
		return '<g:'..str..'>'
	end
end

std.mod_start(function()
	std.mod_init(function()
		std.rawset(_G, 'instead', instead)
		require "ext/sandbox"
	end)
	local mp = std.ref '@metaparser'
	if mp then
--		mp.msg.CUTSCENE_MORE = '^'..mp.msg.CUTSCENE_HELP
		std.rawset(mp, 'clear', function(self)
			self.text = ''
			re_eval 'instead_clear()'
		end)
		std.rawset(mp, 'MetaSave', function(self, w)
			w = w or 'autosave'
			re_eval(string.format("need_save = %q", w))
			std.abort()
		end)
		std.rawset(mp, 'MetaLoad', function(self, w)
			w = w or 'autosave'
			re_eval(string.format("need_load = %q", w))
			std.abort()
		end)
		VerbExtend ({
			"#MetaSave",
			"*:MetaSave",
		}, mp)
		VerbExtend ({
			"#MetaLoad",
			"*:MetaLoad",
		}, mp)
		std.rawset(mp, 'show_prompt', function(self, inp)
			if mp:autoplay_pending() then
				pn(fmt.b(self.prompt .. inp))
				return true
			end
			if std.here():has'cutscene' then
				return false
			end
			-- nil -- to show mp:correct()
			-- false -- do not show mp:correct()
		end)
		mp.autocompl = false
		mp.autohelp = false
		mp.compare_len = 3
		local _, v = re_eval 'return conf.prompt'
		mp.prompt = v
	end
end)
