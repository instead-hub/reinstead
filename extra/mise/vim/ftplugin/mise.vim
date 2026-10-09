if exists('b:did_ftplugin')
  finish
endif
let b:did_ftplugin = 1

setlocal commentstring=#\ %s
setlocal comments=:#,b:#
setlocal iskeyword+=#

let b:undo_ftplugin = 'setlocal commentstring< comments< iskeyword<'
