local cc = {}

function cc:new(fname, size)
	local o = { list = {}, hash = {}, max_size = size or 0 }
	if not size or size == 0 then
		o.autogrow = true
	end
	self.__index = self
	setmetatable(o, self)
	return o
end

function cc:add(key, val)
	table.insert(self.list, 1, key)
	self.hash[key] = val
	if self.autogrow and self.max_size < #self.list then
		self.max_size = #self.list
	end
end

function cc:del(key)
	local o = self.hash[key]
	if o == nil then
		return
	end
	for k, v in ipairs(self.list) do
		if v == key then
			table.remove(self.list, k)
			break
		end
	end
	self.hash[key] = nil
	return o
end

function cc:get(key)
	return self.hash[key]
end

function cc:zap()
	self.list = {}
	self.hash = {}
end

function cc:shrink()
	local k = #self.list
	if self.autogrow then
		if self.max_size > 2 * k then
			self.max_size = math.floor(k + k/2)
		end
	end
	if  k <= self.max_size then
		return
	end
	local n = k - self.max_size
	while n > 0 do
		self.hash[table.remove(k)] = nil
		k = k - 1
		n = n - 1
	end
	return true
end

return cc
