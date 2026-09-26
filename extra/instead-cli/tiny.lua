-- some stubs for tiny-instead
-- fake game.gui
-- stat, menu
-- fake audio
-- fake input

if API == 'stead3' then
	require 'tiny3'
	require "ext/sound"
	LANG='en'
	local instead = std '@instead'
	local iface = std '@iface'
	instead.music_callback = function() end
	instead.restart = instead_restart
	instead.menu = instead_menu
	instead.savepath = function() return "./" end
	std.savepath = instead.savepath
	local iface_cmd = iface.cmd
	function iface:cmd(inp)
		local a = std.split(inp, " ,")
		if a[1] == 'use' and #a == 3 then -- use a b  -> use a,b
			std.table.remove(a, 1)
			return iface_cmd(self, 'use '..std.join(a, ','))
		end
		return iface_cmd(self, inp)
	end
	function iface:em(str)
		if type(str) == 'string' then
			return '/'..str..'/'
		end
	end
	function iface:bold(str)
		if type(str) == 'string' then
			return '*'..str..'*'
		end
	end
	instead.get_picture = function()
		local s = stead.call(std.here(), 'pic')
		if not s then
			s = stead.call(std.ref 'game', 'pic')
		end
		return s and std.tostr(s)
	end
	std.mod_start(function()
		std.mod_init(function()
			std.rawset(_G, 'instead', instead)
			require "ext/sandbox"
		end)
	end)
else
	require 'tiny2'
	require "ext/sound"
end
