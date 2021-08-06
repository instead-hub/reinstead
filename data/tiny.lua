if API ~= 'stead3' then
	return
end

require 'tiny3'

local instead = std '@instead'
local iface = std '@iface'
instead.music_callback = function() end
instead.restart = function()
	core_eval 'need_restart = true'
end
instead.menu = instead_menu
instead.savepath = function() return "./saves/" end

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
		mp.msg.CUTSCENE_MORE = '^'..mp.msg.CUTSCENE_HELP
		std.rawset(mp, 'clear', function(self)
			self.text = ''
			core_eval 'instead_clear()'
		end)
		std.rawset(mp, 'MetaSave', function(self, w)
			w = w or 'autosave'
			core_eval(string.format("need_save = %q", w))
		end)
		std.rawset(mp, 'MetaLoad', function(self, w)
			w = w or 'autosave'
			core_eval(string.format("need_load = %q", w))
		end)
		VerbExtend ({
			"#MetaSave",
			"*:MetaSave",
		}, mp)
		VerbExtend ({
			"#MetaLoad",
			"*:MetaLoad",
		}, mp)
	end
end)
