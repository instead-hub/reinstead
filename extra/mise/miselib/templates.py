"""The shapes of the generated Lua text (the emitter vocabulary)."""

FUNC_LUA = 'function(%s)\n%s\nend'
FUNC_IND = 'function(%s)\n%s\n%s'
FN_DEF = 'local function %s(%s)\n%s\nend'
TABLE = '{ %s }'
QUOTED = "'%s'"
REF = "_'%s'"
ASSIGN = '%s = %s'
FIELD = '%s%s = %s;'
FIELD_BARE = '%s%s = %s'
DOT_ASSIGN = '%s.%s = %s'
INDEX_ASSIGN = '%s["%s"] = %s;'
INDEX_KEY = '%s["%s%s"] = %s;'
EVENT_ASSIGN = '%s%s%s%s = %s;'
LINE = '%s%s;'
NAM = '%snam = %s;'
CONST = "const '%s' (%s)"
GLOBAL = "global '%s' (%s)"
ASSIGN_TRUE = '%s = true'
PRIO = 'prio = %s'
HINT = 'hint = %s'
TAG_LIT = "'#%s'"
OPEN = '%s{'
CLOSE = '%s}'
OBJ_OPEN = '%sobj = {'
OBJ_CLOSE = '%s};'
CTOR_OPEN = '%s%s {'
CTOR_OPEN_PARENT = '%s%s({'
TAIL_PARENT = '%s}, %s)'
VERB = '%sVerb { %s%s }'
VERB_EXTEND = '%s%s { %s%s }'
ATTRS = ":attr '%s'"
DICT = ':dict %s'
IMPL_DICT = '%s:dict %s'
LIST_ITEM = "%s'%s';"
FN_S = '%sfunction(s)'
P_CALL = '%sp(%s)'
END = '%send'
TALK_COND = 'cond = function() return %s end'
TALK_NEXT = "next = '#%s'"
DLG = '%sdlg {'
DLG_NAM = "%snam = '%s';"
PHR = '%sphr = {'
GAME_DSC = 'game.dsc = %s'
TAKE = "%stake('%s')"
WORDS_ALIAS = '%s-"%%s";'
FMT = 'fmt.%s = true'
HERO_WORD = 'pl.word = -"%s"'
RETURN = '%sreturn%s'
FOR = '%sfor %s do'
THEN = '%s%s %s then'
META = '--$%s:%s$'
REQUIRE = 'require "%s"'
REQUIRE_PARSER = 'require "parser/mp-%s"'
