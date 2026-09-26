local std = stead
local iface = std '@iface'
local instead = std '@instead'

local function html_tag(nam)
	return function(s, str)
		if not str then return str end
		return '<'..nam..'>'..str..'</'..nam..'>'
	end
end

iface.center = html_tag('center')
iface.bold = html_tag('b')
iface.em = html_tag('i')
iface.img = function(s, str)
	if str then
--		instead.clear() -- always clear window on pictures
		return '<g:'..str..'>'
	end
end
instead.restart = instead_restart
instead.menu = instead_menu
instead.clear = instead_clear
instead.tiny = true -- minimal version
instead.run_js = instead_js
instead.savename = instead_savename

std.mod_start(function()
	local mp = std.ref '@metaparser'
	if mp then
		mp.msg.CUTSCENE_HELP = mp.msg.CUTSCENE_HELP:gsub("<", "&lt"):gsub(">", "&gt");
		std.rawset(mp, 'clear', function(self)
			self.text = ''
			-- uncomment to clear screen on move
			-- instead.clear();
		end)
		VerbExtend ({
			"#MetaSave",
			"*:MetaSave",
		}, mp)
		VerbExtend ({
			"#MetaLoad",
			"*:MetaLoad",
		}, mp)
		std.rawset(mp, 'MetaSave', function(self, w)
			instead.savename(w)
			instead.menu 'save'
		end)
		std.rawset(mp, 'MetaLoad', function(self, w)
			instead.savename(w)
			instead.menu 'load'
		end)
	end
end)
