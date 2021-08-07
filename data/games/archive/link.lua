require "fmt"

if not instead.atleast(3, 2) then
	std.dprint("Warning: link module is not functional on this INSTEAD version")
	function instead.clipboard()
		return false
	end
end

obj {
	nam = '$link';
	act = function(s, w)
		if not instead.clipboard or instead.clipboard() ~= w then
			std.p ('{@link ', w, '|', w, '}')
		else
			std.p(fmt.u (w) ..' [в буфере обмена]')
		end
	end;
}

obj {
	nam = '@link';
	act = function(s, w)
		if instead.clipboard then
			instead.clipboard(w)
		end
	end;
}
