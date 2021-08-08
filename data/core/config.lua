return {
	prompt = '> ',
	title = "RE/INSTEAD",
	fsize = 14,
	bg = { 0xff, 0xff, 0xe8, 0xff },
	fg = { 0, 0, 0, 0xff },
	cursor_fg = { 0, 0, 0, 0xff },
	scroll_bg = { 0x99, 0x99, 0x4c, 0xff },
	scroll_fg = { 0xff, 0xff, 0xe8, 0xff },
	pad = 14,
	fps = 60,
	hspace = 1.2,
	regular = 'fonts/Go-Regular.ttf',
	italic = 'fonts/Go-Italic.ttf',
	bold = 'fonts/Go-Bold.ttf',
	bold_italic = 'fonts/Go-Bold-Italic.ttf',
	scrollw = 9,
	autostart = false, -- add path here to autorun game
	directory = './games', -- set path of the games directory to browse
	dir_title = false, -- '<b>Select game</b>',
	scroll_inverse = false,
	show_icons = true,
	scale = true, -- autoscale using dpi info, set number to force specific scale
	autosave = true,
--	autoload = true,
	debug = true,
}
