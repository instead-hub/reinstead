local lay = require "layout"
local conf = require "config"

local tbox = {
}

function tbox:new()
	local o = {
		lay = lay:new(),
		off = 0,
		sw = math.round(conf.scrollw) * SCALE,
	}
	if o.sw < 3 then o.sw = 3 end
	o.pad = conf.pad
	self.__index = self
	setmetatable(o, self)
	return o
end

function tbox:resize(w, h, ...)
	self.w, self.h = w, h
	self.lay:resize(self.w - self.sw - self.pad * 2, self.h - self.pad * 2, ...)
	self.scrollh = math.floor(self.lay.h - (self.lay.fonts.regular.h * self.lay.hspace))
end

function tbox:mouse(e, b, x, y)
	local off
	if e == 'mouseup' then
		self.scroll_start = false
		return
	end
	if e == 'mousemotion' then
		x, y = b, x
	end
	if self.scroll_start or
		(x >= 0 and y >=0 and x < self.sw and y < self.h) then -- scroll
		if e == 'mousedown' and b == 'left' then
			local stop, sbot = self:scrollpos()
			if y < stop or y >= sbot then
				off = y * self.lay.realh / self.h
				self.scroll_start = 0
			else
				self.scroll_start = y - stop
			end
		elseif e == 'mousemotion' and self.scroll_start then
			off = (y - self.scroll_start)* self.lay.realh / self.h
		else
			return
		end
	else
		return
	end
	if not off or self.off == off then
		return
	end
	self.off = off
	self:scroll(0)
	return true
end

function tbox:scroll(scroll)
	local ooff = self.off
	scroll = scroll or 1
	local l = self.lay
	self.off = self.off + scroll
	if l.realh <= self.h - self.pad *2 then
		self.off = 0
		return
	end
	if self.off < 0 then self.off = 0 end
	if self.off > l.realh - self.h + self.pad*2 then self.off = l.realh - self.h + self.pad*2 end
	return ooff ~= self.off
end
function tbox:set(text)
	self.lay:set(text)
	self:resize(self.w, self.h)
end

function tbox:add(text, cache)
	if cache == false then
		self.lay.nocache = true
	end
	local n = #self.lay.lines
	self.lay:add(text)
	self:resize(self.w, self.h, n)
	if cache == false then
		self.lay.nocache = false
	end
end

function tbox:add_img(img)
	local n = #self.lay.lines
	self.lay:add_img(img)
	self:resize(self.w, self.h, n)
end
function tbox:scrollpos()
	local b = math.round(SCALE)
	local _, rh = self.lay:size()
	local h = self.h - 2*b;
	local stop = math.round(self.off * h/rh)
	local sbot = math.round((self.off + self.lay.h) * h/rh)
	local sh = sbot - stop
	if sh <= 0 then sh = 1 end
	if sh > self.h - 2*b then sh = self.h - 2*b end
	return stop + b, stop + b + sh
end
function tbox:render(dst, xoff, yoff)
	dst = dst or gfx.win()
	xoff = xoff or 0
	yoff = yoff or 0
	dst:fill(xoff, yoff, self.w, self.h, self.lay.bg)
	self.lay:render(dst, xoff + self.sw + self.pad, yoff + self.pad, self.off)
	dst:fill(xoff, yoff, self.sw, self.h, conf.scroll_bg)
	local stop, sbot = self:scrollpos()
	local b = math.round(SCALE)
	dst:fill(xoff + b, yoff + stop, self.sw - 2*b,  sbot - stop,
		conf.scroll_fg)
end
function tbox:render_line(dst, n, xoff, yoff)
	xoff = xoff or 0
	yoff = yoff or 0
	self.lay:render_line(dst, n, xoff + self.sw + self.pad, yoff + self.pad, self.off)
end

function tbox:texth()
	return self.lay.realh
end

function tbox:lines()
	return self.lay.lines
end

function tbox:reset()
	return self.lay:reset()
end

return tbox
