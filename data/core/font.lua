local cache = require "cache"

local fn = {
}
function fn:new(fname, size)
	local o = { cache = cache:new() }
	self.__index = self
	setmetatable(o, self)
	local f = gfx.font(fname, size)
	if not f then
		error("Can't load font ".. tostring(fname), 2)
	end
	o.font = f
	o.spw, o.h = f:size(" ")
	o.w = f:size("0")
	return o
end

function fn:size(text)
	return self.font:size(text)
end

function fn:key(text, color)
	if not color then color = { 255, 255, 255, 255 } end
	return string.format("%02x%02x%02x%02x:%s",
				  color[1] or 0,
				  color[2] or 0,
				  color[3] or 0,
				  color[4] or 0xff,
				  text)
end

function fn:text(text, color)
	local s, e = text:find(" ", 1, true)
	if not s then -- fast path
		local key = self:key(text, color)
		local o = self.cache:get(key)
		if o then
			return o
		end
		o = self.font:text(text, color)
		if not self.nocache then
			self.cache:add(key, o)
		end
		return o
	end
	local out = {}
	local w = 0
	while text ~= "" do
		if s == 1 then
			local space = (e - s + 1) * self.spw;
			table.insert(out, space);
			text = text:sub(e + 1)
			w = w + space
		else
			local word
			if s then
				word = text:sub(1, s - 1)
			else
				word = text
			end
			local key = self:key(word, color)
			local o = self.cache:get(key)
			if not o then
				o = self.font:text(word, color)
				if not self.nocache then
					self.cache:add(key, o)
				end
			end
			local ww = o:size()
			w = w + ww
			table.insert(out, o);
			if s then
				text = text:sub(s)
			else
				text = ""
			end
		end
		s, e = text:find(" ", 1, true)
	end
	local o = gfx.new(w, self.h)
	local x = 0
	for _, v in ipairs(out) do
		if type(v) == 'number' then
			x = x + v
		else
			v:copy(o, x, 0)
			x = x + v:size()
		end
	end
	return o
end

return fn
