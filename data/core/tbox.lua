local lay = require "layout"
local conf = require "config"
local SCROLLW = conf.scrollw * SCALE

local tbox = {
}

function tbox:new()
	local o = {
		lay = lay:new(),
		off = 0,
	}
	o.pad = conf.pad;
	self.__index = self
	setmetatable(o, self)
	return o
end

function tbox:resize(w, h)
	self.w, self.h = w, h
	self.lay:resize(self.w - SCROLLW - self.pad * 2, self.h - self.pad * 2)
end

function tbox:mouse(e, b, x, y)
	if e == 'mouseup' then
		self.scroll_start = false
		return
	end
	if e == 'mousemotion' then
		x, y = b, x
	end
	if self.scroll_start or
		(x >= 0 and y >=0 and x < SCROLLW and y < self.h) then -- scroll
		if e == 'mousedown' and b == 'left' then
			local stop, sbot = self:scrollpos()
			if y < stop or y >= sbot then
				self.off = y * self.lay.realh / self.h
				self.scroll_start = 0
			else
				self.scroll_start = y - stop
			end
		elseif e == 'mousemotion' and self.scroll_start then
			self.off = (y - self.scroll_start)* self.lay.realh / self.h
		else
			return
		end
	end
	self:scroll(0)
	return true
end
function tbox:scroll(scroll)
	if conf.scroll_inverse then
		scroll = -scroll
	end
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
end

function tbox:add(text)
	self.lay:add(text)
end
function tbox:scrollpos()
	local _, rh = self.lay:size()
	local h = self.h - self.pad*2;
	local stop = math.floor(self.off * h/ rh)
	local sbot = math.floor((self.off + h) * self.h / rh)
	local sh = math.ceil(sbot - stop - 2*SCALE)
	if sh <= 0 then sh = math.ceil(1 * SCALE) end
	if sh > self.h then sh = math.ceil(self.h - 2*SCALE) end
	return stop, stop + sh
end
function tbox:render(dst, xoff, yoff)
	xoff = xoff or 0
	yoff = yoff or 0
	dst:fill(xoff, yoff, self.w, self.h, self.lay.bg)
	self.lay:render(dst, xoff + SCROLLW + self.pad, yoff + self.pad, self.off)
	dst:fill(xoff, yoff, SCROLLW, self.h, conf.scroll_bg)
	local stop, sbot = self:scrollpos()
	dst:fill(xoff + SCALE, yoff + stop + SCALE, SCROLLW - 2*SCALE,  sbot - stop,
		conf.scroll_fg)
end
function tbox:render_line(dst, n, xoff, yoff)
	xoff = xoff or 0
	yoff = yoff or 0
	self.lay:render_line(dst, n, xoff + SCROLLW + self.pad, yoff + self.pad, self.off)
end
return tbox