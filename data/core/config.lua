return {
	prompt = '<b>> </b>',
	title = "RE:INSTEAD",
	fsize = 16,
	bg = { 0xff, 0xff, 0xe8, 0xff },
	fg = { 0, 0, 0, 0xff },
	cursor_fg = { 0, 0, 0, 0xff },
	scroll_bg = { 0x99, 0x99, 0x4c, 0xff },
	scroll_fg = { 0xff, 0xff, 0xe8, 0xff },
	pad = 14,
	fps = 60,
	hspace = 1.2,
	width = 75, -- maximum text width in elements
	regular = 'fonts/Go-Regular.ttf',
	italic = 'fonts/Go-Italic.ttf',
	bold = 'fonts/Go-Bold.ttf',
	bold_italic = 'fonts/Go-Bold-Italic.ttf',
	scrollw = 11,
	autostart = false, -- add path here to autorun game
	directory = './games', -- set path (or { path, ... }) of the games directory to browse
	dir_auth_info = false, -- show authors?
	dir_title = false, -- '<b>Select game</b>',
	scroll_inverse = false,
--	scroll_drag = true,
	show_icons = true,
	scale = true, -- autoscale using dpi info, set number to force specific scale
	autosave = true,
	short_help = "<c>***</c>\n!info - info\n!save - save game\n!load - load game\n!restart - restart game\n"..
		"!font <size> - change font size\n!tts - toggle tts\n!quit - exit\n\n"..
		"<i>All commands must be entered with an exclamation mark at the beginning!</i>\n\n",
	note = '<c>https://parser.hugeping.ru</c>',
	settings = true, -- store font size
--	settings_game = true, -- store selected game
--	autoload = true,
--	debug = true,
}
