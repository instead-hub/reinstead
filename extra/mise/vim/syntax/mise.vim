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
syn match miseType /[:,(|[\]]\s*\zs\%(obj\|str\|num\|bool\|any\|event\|tbl\|ref\|fn\)\>/
syn match miseType /\%(->\s*\)\@<=\%(obj\|str\|num\|bool\|any\|event\|tbl\|ref\|fn\)\>/

" --- ключи полей (до деклараций: спец-ключи и секции важнее) ---
syn match miseKey /^\s*\zs\w\+\ze\s*[:(]/
syn match miseSpecialKey /^\s*\zs\%(words\|word\|attrs\|dict\|disabled\|with\|inside\|text\|found_in\)\ze\s*[:(]/

" --- декларации и секции (в начале строки) ---
syn match miseDecl /^\s*\zs\%(obj\|scenery\|room\|door\|story\|ending\|class\|mixin\|verb\|talk\|setup\|impl\|props\|refs\|const\|global\|event\|type\|extend\|fn\|lua\)\>\ze\%(\s\|:\|$\)/
syn match miseDirective /^\s*\zs\%(name\|version\|author\|info\|lang\|fmt\|include\|require\)\ze\s*:/
syn match miseDecl2 /\%(^\s*extend\s\+\)\@<=\%(refs\|type\)\>/
syn match miseImplTarget /\%(^\s*impl\s\+\)\@<=[^[:space:]:]\+/
syn match miseEventName /\%(^\s*event\s\+\)\@<=\u\w*/

" --- фазы и имена событий (lookbehind: слово фазы уже просканировано) ---
syn match misePhase /^\s*\zs\%(on\|life\|before\|after\|post\)\ze\s\+\u\w*/
syn match misePhaseEvt /\%(^\s*\%(on\|life\|before\|after\|post\)\s\+\)\@<=\u\w*\%(\s*,\s*\u\w*\)*/

" --- логика (`|` и `|lua` блоки) ---
syn match misePipe /|\s*$/
syn match misePipeLua /|lua\s*$/
syn match miseLogicKw /^\s*\zs\%(if\|elseif\|else\|when\|default\|for\|local\|return\|break\|stop\|pass\)\ze\%(\s\|$\|:\)/
syn keyword miseLogicOp and or not in
syn match miseUse /\<use\s\+\zs\w\+/
syn match miseFnRef /&\w\+/

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
hi def link miseSpecialKey   Type
hi def link miseDecl         Keyword
hi def link miseDirective    PreProc
hi def link miseDecl2        Keyword
hi def link miseImplTarget   Function
hi def link miseEventName    Function
hi def link misePhase        Statement
hi def link misePhaseEvt     Function
hi def link misePipe         Special
hi def link misePipeLua      Special
hi def link miseLogicKw      Statement
hi def link miseLogicOp      Operator
hi def link miseUse          Special
hi def link miseFnRef        Function
hi def link miseTag          Tag
hi def link miseTodo         Todo

let b:current_syntax = 'mise'
