local utf = {
}
function utf.sym(str)
	return system.utf_sym(str)
end
function utf.chars(b)
	local i = 1
	local s
	local res = {}
	local ff = system.utf_next
	while i <= b:len() do
		s = i
		i = i + ff(b, i)
		table.insert(res,  b:sub(s, i - 1))
	end
	return res
end
function utf.strip(str)
	if not str then return str end
	str = str:gsub("^[ \t]+",""):gsub("[ \t]+$","")
	return str
end

function utf.split(s, sep_arg)
	local sep, fields = sep_arg or " ", {}
	local pattern = string.format("([^%s]+)", sep)
	s:gsub(pattern, function(c) table.insert(fields, utf.strip(c)) end)
	return fields
end

return utf
