-- mise (the DSL of extra/mise), on the basis of extra/mise/vim/syntax/
-- mise.vim: the comments and #tags, the quoted and long strings, the
-- section declarations and the field keys, the logic keywords and
-- operators, the event names and the "|" logic markers.
local scheme = require "red/scheme"

-- the section declarations of the line start
local decl = {
  obj = true, scenery = true, room = true, door = true, story = true,
  ending = true, class = true, mixin = true, verb = true, talk = true,
  setup = true, impl = true, props = true, refs = true, const = true,
  global = true, event = true, type = true, extend = true, fn = true,
  lua = true,
}

-- the keywords of the logic blocks
local logic = {
  ['if'] = true, ['elseif'] = true, ['else'] = true, when = true,
  ['default'] = true, ['for'] = true, ['local'] = true,
  ['return'] = true, ['break'] = true, stop = true, pass = true,
}

-- the field keys with a meaning of their own
local special = {
  words = true, word = true, attrs = true, dict = true, disabled = true,
  with = true, inside = true, text = true, found_in = true,
}

-- the phases of the event handlers
local phase = {
  on = true, life = true, before = true, after = true, post = true,
}

-- the value types
local types = {
  obj = true, str = true, num = true, bool = true, any = true,
  event = true, tbl = true, ref = true, fn = true,
}

-- the word starting at i (an empty string when there is none)
local function word(txt, i)
  local n = {}
  while txt[i] and txt[i]:find('[%w_]') do
    n[#n + 1] = txt[i]
    i = i + 1
  end
  return table.concat(n)
end

-- true when the only word before i on its line is w
local function afterword(txt, i, w)
  local bol = scheme.rule.linebegin(txt, i)
  local p = scheme.rule.skipspace(txt, bol, 1)
  return word(txt, p) == w and
    scheme.rule.skipspace(txt, p + #w, 1) == i
end

-- the declarations, the logic keywords, the special keys and the
-- phases, all of the line start
local function linekw(ctx, txt, i)
  if not txt[i] or not txt[i]:find('[%w_]') then
    return
  end
  local w = word(txt, i)
  if (w == 'type' or w == 'refs') and afterword(txt, i, 'extend') then
    return #w
  end
  if not scheme.rule.bol(txt, i, '[ \t]') then
    return
  end
  local c = txt[i + #w]
  if (decl[w] or logic[w]) and
    (not c or c == ':' or c == '\n' or scheme.rule.isspace(c)) then
    return #w
  end
  if special[w] then
    local j = scheme.rule.skipspace(txt, i + #w, 1)
    if txt[j] == ':' or txt[j] == '(' then
      return #w
    end
  elseif phase[w] then
    local j = scheme.rule.skipspace(txt, i + #w, 1)
    if txt[j] and txt[j]:find('%u') then
      return #w
    end
  end
end

-- a field key: at the line start, a word followed by ":" or "("
local function key(ctx, txt, i)
  if not txt[i] or not txt[i]:find('[%w_]') or
    not scheme.rule.bol(txt, i, '[ \t]') then
    return
  end
  local j = scheme.rule.skip(txt, i, 1, '[%w_]')
  local k = scheme.rule.skipspace(txt, j, 1)
  if txt[k] == ':' or txt[k] == '(' then
    return j - i
  end
end

-- a type: after ":" "," "(" "|" "[" "]" or "->"
local function type_(ctx, txt, i)
  if not txt[i] or not txt[i]:find('[%w_]') then
    return
  end
  local w = word(txt, i)
  if not types[w] then
    return
  end
  local p = scheme.rule.skipspace(txt, i - 1, -1)
  local c = txt[p]
  if c == ':' or c == ',' or c == '(' or c == '|' or c == '[' or
    c == ']' or (c == '>' and txt[p - 1] == '-') then
    return #w
  end
end

-- the names after "event", "impl", "use" and the phase words; the
-- whole comma-separated event list is one match
local function named(ctx, txt, i)
  local c = txt[i]
  if not c or c == '\n' or c == ':' or scheme.rule.isspace(c) then
    return
  end
  local p = scheme.rule.skipspace(txt, i - 1, -1)
  if p == i - 1 then
    return
  end
  local w = word(txt, scheme.rule.skip(txt, p, -1, '[%w_]') + 1)
  if w == 'use' then
    local j = scheme.rule.skip(txt, i, 1, '[%w_]')
    if j > i then
      return j - i
    end
    return
  end
  if not afterword(txt, i, w) then
    return
  end
  if w == 'event' then
    if c:find('%u') then
      return scheme.rule.skip(txt, i, 1, '[%w_]') - i
    end
  elseif w == 'impl' then
    return scheme.rule.skip(txt, i, 1, '[^ \t:\n]') - i
  elseif phase[w] then
    if not c:find('%u') then
      return
    end
    local j = i
    while true do
      j = scheme.rule.skip(txt, j + 1, 1, '[%w_]')
      local k = scheme.rule.skipspace(txt, j, 1)
      if txt[k] ~= ',' then
        return j - i
      end
      k = scheme.rule.skipspace(txt, k + 1, 1)
      if not txt[k] or not txt[k]:find('%u') then
        return j - i
      end
      j = k
    end
  end
end

-- a function value "&name"
local function fnref(ctx, txt, i)
  if txt[i] ~= '&' then
    return
  end
  local j = scheme.rule.skip(txt, i + 1, 1, '[%w_]')
  if j > i + 1 then
    return j - i
  end
end

-- a "#tag" reference (not a comment)
local function tag(ctx, txt, i)
  if txt[i] ~= '#' then
    return
  end
  local p = txt[i - 1]
  if i > 1 and p ~= '\n' and not scheme.rule.isspace(p) then
    return
  end
  local j = scheme.rule.skip(txt, i + 1, 1, '[^%s:,()|{}%[%].#]')
  if j > i + 1 then
    return j - i
  end
end

-- a "|" or "|lua" logic marker at the end of the line
local function pipe(ctx, txt, i)
  if txt[i] ~= '|' then
    return
  end
  local j = i + 1
  if txt[j] == 'l' and txt[j + 1] == 'u' and txt[j + 2] == 'a' then
    j = j + 3
    local c = txt[j]
    if c and c ~= '\n' and not scheme.rule.isspace(c) then
      return
    end
  end
  local k = scheme.rule.skipspace(txt, j, 1)
  if not txt[k] or txt[k] == '\n' then
    return k - i
  end
end

-- a comment: "#" at the line start or as a separate word
local function comment_start(ctx, txt, i)
  if txt[i] ~= '#' then
    return
  end
  local n = txt[i + 1]
  if n and n ~= '\n' and not scheme.rule.isspace(n) then
    return
  end
  local p = txt[i - 1]
  if i > 1 and p ~= '\n' and not scheme.rule.isspace(p) then
    return
  end
  return 1
end

-- a long string: [[...]], [=[...]=], [==[...]==]
local function longestr(open, close)
  return {
    start = open,
    stop = close,
    scol = scheme.operator,
    ecol = scheme.operator,
    col = scheme.string,
  }
end

local col = {
  col = scheme.default,
  keywords = {
    { linekw, col = scheme.keyword },
    { "true", "false", "nil", col = scheme.keyword, word = true },
    { key, col = scheme.lib },
    { type_, col = scheme.lib },
    { named, col = scheme.lib },
    { fnref, col = scheme.lib },
    { tag, col = scheme.number },
    { pipe, col = scheme.operator },
    { "->", col = scheme.operator },
    { "and", "or", "not", "in", col = scheme.operator, word = true },
    { scheme.rule.number, col = scheme.number },
    { "TODO", "FIXME", "XXX", col = { 255, 0, 0 }, word = true },
  },
  { -- a comment: from # to the end of the line
    start = comment_start,
    stop = '\n',
    col = scheme.comment,
  },
  scheme.rule.string '"',
  scheme.rule.string "'",
  scheme.rule.string '`',
  longestr('[==[', ']==]'),
  longestr('[=[', ']=]'),
  longestr('[[', ']]'),
}

return col
