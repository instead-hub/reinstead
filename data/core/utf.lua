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

return utf
