" Vim syntax file
" Language:    mise DSL (RE:INSTEAD)
" Maintainer:  opencode
" Filenames:   *.mise
"
" Установка:
"   Vim:     cp -r extra/mise/vim/* ~/.vim/
"   Neovim:  cp -r extra/mise/vim/* ~/.config/nvim/
"   или в vimrc/init.lua:
"     set runtimepath+=/path/to/reinstead/extra/mise/vim
"     (init.lua: vim.opt.runtimepath:append('...'))

if exists('b:current_syntax')
  finish
endif

syn sync fromstart

" --- комментарии: `#` в начале строки или отдельным словом ---
syn region miseComment start=/^\s*\zs#\%(\s\|$\)/ end=/$/ keepend contains=@Spell
syn region miseComment start=/\s\zs#\%(\s\|$\)/ end=/$/ keepend contains=@Spell

" --- строки ---
syn region miseString start=/"/ skip=/\\"/ end=/"/ oneline
syn region miseString start=/'/ skip=/\\'/ end=/'/ oneline
syn region miseLongString matchgroup=miseLongDelim start=/\[\[/ end=/\]\]/ keepend
syn region miseLongString matchgroup=miseLongDelim start=/\[=\[/ end=/\]=\]/ keepend
syn region miseLongString matchgroup=miseLongDelim start=/\[==\[/ end=/\]==\]/ keepend
syn region miseRaw start=/`/ end=/`/ oneline

" --- литералы ---
syn match miseNumber /\v<[-+]?\d+(\.\d+)?>/
syn keyword miseBoolean true false
syn keyword miseNil nil

" --- типы (аннотации, props, `->`); контекстно, чтобы не спорить с `obj:`/`event:` ---
syn match miseArrow /->/
syn match miseType /[:,(|[\]]\s*\zs\%(obj\|str\|num\|bool\|any\|event\|tbl\|list\|ref\|fn\)\>/
syn match miseType /\%(->\s*\)\@<=\%(obj\|str\|num\|bool\|any\|event\|tbl\|list\|ref\|fn\)\>/

" --- ключи полей (до деклараций: спец-ключи и секции важнее) ---
syn match miseKey /^\s*\zs\w\+\%(\s*,\s*\w\+\)*\ze\s*[:(]/
syn match miseSpecialKey /^\s*\zs\%(words\|word\|attrs\|attr\|dict\|disabled\|with\|inside\|text\|found_in\|exit\|enter\|scope\|nam\|tag\|way\|lifes\)\ze\s*[:(]/

" --- декларации и секции (в начале строки) ---
syn match miseDecl /^\s*\zs\%(obj\|room\|door\|story\|ending\|class\|mixin\|verb\|talk\|impl\|const\|global\|type\|event\|entry\|extern\|extend\|remove\|fn\|lua\)\>\ze\%(\s\|:\|$\)/
syn match miseDirective /^\s*\zs\%(game\|name\|version\|author\|info\|lang\|fmt\|include\|require\)\>/
syn match miseDecl2 /\%(^\s*extend\s\+\)\@<=\%(type\|event\|verb\)\>/
syn match miseImplTarget /\%(^\s*impl\s\+\)\@<=[^[:space:]:]\+/
syn match miseMethodSpec /\%(=\s*method\s\+\)\@<=\w\+/

" --- фазы и имена событий ---
syn match misePhase /^\s*\zs\%(on\|life\|before\|after\|post\)\ze\s\+\u\w*/
syn match misePhaseEvt /\%(^\s*\%(on\|life\|before\|after\|post\)\s\+\)\@<=\u\w*\%(\s*,\s*\u\w*\)*/
syn match miseEventHandler /\%(^\s*\%(on\|before\|after\|post\|life\)\s\+\%([A-Z]\w*\s*,\s*\)*[A-Z]\w*\%(([^)]*)\)\?\s*=\)\@<==/

" --- логика ---
syn match miseLogicKw /^\s*\zs\%(if\|elseif\|else\|while\|match\|for\|local\|return\|break\|stop\|pass\|entry\|event\|extern\|value\|lvalue\|global\|method\)\ze\%(\s\|$\|:\)/
syn keyword miseLogicOp and or not in of
syn match miseFnRef /&\%((\)\@!\w\+/
syn match miseLambda /&\ze(/
syn match miseBind /:=/

" --- паттерны глаголов: {noun}/вн, {direction}; имя события после `:` ---
syn match misePatternSlot /{[a-z_0-9]\+}/
syn match misePatternDir /\/[а-яa-z]\+/

" --- ссылки: #тег ---
syn match miseTag /\%(^\|\s\)\zs#[^[:space:]:,()|{}[\].#]\+/
syn keyword miseTodo TODO FIXME XXX

" --- подсветка ---
hi def link miseComment      Comment
hi def link miseString       String
hi def link miseLongString   String
hi def link miseLongDelim    Delimiter
hi def link miseRaw          Special
hi def link miseNumber       Number
hi def link miseBoolean      Boolean
hi def link miseNil          Constant
hi def link miseType         Type
hi def link miseArrow        Operator
hi def link miseKey          Identifier
hi def link misePatternSlot  Special
hi def link misePatternDir  Type
hi def link miseSpecialKey   Type
hi def link miseDecl         Keyword
hi def link miseDirective    PreProc
hi def link miseDecl2        Keyword
hi def link miseImplTarget   Function
hi def link misePhase        Statement
hi def link misePhaseEvt     Function
hi def link miseLambda       Special
hi def link miseBind         Operator
hi def link miseMethodSpec   Function
hi def link miseEventHandler Keyword
hi def link miseLogicKw      Statement
hi def link miseLogicOp      Operator
hi def link miseFnRef        Function
hi def link miseTag          Tag
hi def link miseTodo         Todo

let b:current_syntax = 'mise'
