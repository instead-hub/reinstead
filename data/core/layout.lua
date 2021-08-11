local font = require "font"
local conf = require "config"
local lay = {
}

function lay:new()
	local o = {
		lines = {},
		fonts = {},
		w = 0,
		h = 0,
		hspace = conf.hspace,
		fsize = math.round(conf.fsize * SCALE),
		bg = conf.bg,
		fg = conf.fg,
	}
	self.__index = self
	setmetatable(o, self)
	o:font(conf.regular, o.fsize);
	o:font(conf.italic, o.fsize, 'italic')
	o:font(conf.bold, o.fsize, 'bold')
	o:font(conf.bold_italic, o.fsize, 'bold-italic')
	return o
end

function lay:font(path, size, style)
	self.fonts[style or 'regular'] = font:new(DATADIR..'/'..path, size)
end

local function find_esc_sym(t, set, s)
	local ns
	s = s or 1
	while true do
		ns = t:find("[\\"..set.."]", s)
		if not ns then
			return false
		end
		local c = t:sub(ns, ns)
		if c == '\\' then
			s = ns + 2
		else
			return ns
		end
	end
end

local function token_unesc(s)
        s = s:gsub("\\?[\\<>]", {
			   ['\\<'] = '<',
			   ['\\>'] = '>',
			   ['\\\\'] = '\\'
	})
        return s
end

local function next_token(t)
	local s
	s = find_esc_sym(t, "<\n")
	if not s then
		return token_unesc(t), t:len()
	end
	local c = t:sub(s, s)
	if c == '\n' then
		if s == 1 then
			return "\n", 1
		end
		return token_unesc(t:sub(1, s - 1)), s - 1
	end
	if s == 1 then
		s = find_esc_sym(t, ">")
		if not s then
			return token_unesc(t), t:len()
		end
		return token_unesc(t:sub(1, s)), s, true
	end
	return token_unesc(t:sub(1, s - 1)), s - 1
end

function lay:size()
	return self.realw, self.realh
end
function lay:line_align(l, f)
	local len = 0
	if not l[1] then
		return
	end
	local x
	table.insert(l, { x = 0 })
	for k, w in ipairs(l) do
		if len > 0 and w.x <= x then
			w = l[k-1]
			local d = (self.w - w.x - w.w)
			if f == 'center' then
				d = d / 2
			end
			for i=k-len, k-1 do
				w = l[i]
				w.x = w.x + d
			end
			len = 0
		end
		x = w.x
		len = len + 1
	end
	table.remove(l, #l)
end
function lay:resize(width, height, linenr)
	local y = 0
	if linenr == 0 then linenr = nil end
	if linenr then
		y = self.lines[linenr].y
	end
	linenr = linenr or 1
	self.w, self.h = width, height
	local realw = 0
	for k = linenr, #self.lines do
		local l = self.lines[k]
		local x = 0
		local h = self.fonts['regular'].h * self.hspace
		local maxy = y
		l.y = y
		for _, w in ipairs(l) do
			if w.h > h then
				h = w.h + h -- * self.hspace
			end
			w.x = x
			w.y = y
			x = x + w.w + w.spw
			if x - w.spw >= width then
				x = 0
				y = y + h
				if w.x > 0 then -- not first word
					w.x = x
					w.y = y
					x = x + w.w + w.spw
				else
					h = 0
				end
			else
				if x > realw then
					realw = x
				end
			end
			maxy = y
		end
		if l.center or l.right then
			self:line_align(l, l.center and 'center' or 'right')
		end
		l.h = maxy + h - l.y
		y = l.y + l.h
		self.realh = y
	end
	self.realw = realw
end

function lay:render_word(dst, w, xoff, yoff, diff)
	local limit
	if w.xoff then
		xoff = xoff + w.xoff
	end
	if w.y - diff >= 0 then
		if w.y + w.h - diff >= self.h then
			limit = true
			local ydiff = math.floor(self.h - (w.y - diff))
			if ydiff > 0 then
				w.img:blend(0, 0, w.w, ydiff,
					    dst, xoff + w.x, yoff + w.y - diff)
			end
		else
			w.img:blend(dst, xoff + w.x, yoff + w.y - diff)
		end
	elseif w.y + w.h - diff >= 0 then
		local ydiff = math.floor(diff - w.y)
		w.img:blend(0, ydiff, w.w, w.h - ydiff,
			    dst, xoff + w.x, yoff)
	end
	return limit
end

function lay:render_line(dst, n, xoff, yoff, off)
	xoff = xoff or 0
	yoff = yoff or 0
	off = off or 0
	dst = dst or gfx.win
	local l = self.lines[n]
	if l.y < off and l.y+l.h < off then
		return
	end
	dst:fill(xoff, yoff + l.y - off, l.w, l.h, self.bg)
	for _, w in ipairs(l) do
		if w.y >= off or w.y + w.h >= off then
			self:render_word(dst, w, xoff, yoff, off)
		end
	end
	gfx.flip(xoff, yoff + l.y - off, l.w, l.h)
end

function lay:render(dst, xoff, yoff, off)
	off = off or 0
	xoff = xoff or 0
	yoff = yoff or 0
	dst = dst or gfx.win
	local diff
	local limit
	for _, l in ipairs(self.lines) do
		if diff or l.y >= off or l.y + l.h >= off then
			if not diff then
				diff = off
			end
			for _, w in ipairs(l) do
				limit = self:render_word(dst, w, xoff, yoff, off)
			end
			if limit then break end
		end
	end
end

function lay:set(text)
	for _, v in pairs(self.fonts) do -- reset font caches
		v.cache:zap()
	end
	self.lines = {}
	if text then
		return self:add(text)
	end
end

function lay:add_img(img)
	local w, h = img:size()
	local l = {{ img = img, w = w, h = h, spw = 0 }, center = true}
	table.insert(self.lines, l)
end

function lay:add(text)
	local t
	local l = 1
	local line = {  }
	local fstyle = 'regular'
	local fn = self.fonts[fstyle]
	fn.nocache = self.nocache
	local style = { bold = 0, italic = 0, bold_italic = 0, center = 0, right = 0 }
	local tags = {
		b = 'bold',
		i = 'italic',
		c = 'center',
		r = 'right',
	}
	while l ~= 0 do
		local tag
		t, l, tag = next_token(text)
		local txt = t
		local parsed = true
		-- print(string.format("%q/%d", t, l))
		if t == '\n' then
			table.insert(self.lines, line)
			line = { }
		elseif tag then
			t=t:gsub("^<", ""):gsub(">$", "")
			local c = t:sub(1,1) == '/'
			t=t:gsub("^/","")
			local ftag=tags[t]
			if ftag then
				if c then
					style[ftag] = style[ftag] - 1
				else
					style[ftag] = style[ftag] + 1
				end
			end
			fn.nocache = false
			if style.bold > 0 and style.italic > 0 then
				fn = self.fonts['bold-italic']
			elseif style.bold > 0 then
				fn = self.fonts.bold
			elseif style.italic > 0 then
				fn = self.fonts.italic
			else
				fn = self.fonts.regular
			end
			fn.nocache = self.nocache
			if t:find("w:", 1, true) then
				t = t:sub(3)
				local img = fn:text(t, self.fg)
				if img then
					local w, h = img:size()
					table.insert(line, { img = img, w = w, h = h, spw = 0, t = t })
				end
			elseif t:find("g:", 1, true) then
				t = t:sub(3)
				local img = gfx.new(t)
				if img then
					img = img:scale(SCALE)
					local w, h = img:size()
					table.insert(line, { img = img, w = w, h = h, spw = 0 })
				end
			elseif not ftag then
				t = txt
				parsed = false
			end
		else
			parsed = false
		end
		if not parsed and t ~= "" then
			if t:find("^ ") and #line > 0 then
				line[#line].spw = fn.spw
			end
			t:gsub("[^ \t]+", function(c)
					local img = fn:text(c, self.fg)
					local w, h = img:size()
					table.insert(line, { img = img, w = w, h = h, spw = fn.spw })
			end)
			if not t:find(" $") then
				line[#line].spw = 0
			end
		end
		if style.center > 0 then
			line.center = true
		end
		if style.right > 0 then
			line.right = true
		end
		text = text:sub(l + 1)
	end
	if #line > 0 then
		table.insert(self.lines, line)
	end
	fn.nocache = false
end
return lay
