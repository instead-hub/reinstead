var $window = $(window), $doc = $(document), $body, bodylineheight;
var Game;
var input;

const msg = {};

msg['ru'] = {
	nosave: "Нет сохранённой игры.",
	lshelp: "!ls - посмотреть список сохранений.",
	rmhelp: "!rm [файл] - удалить.",
	saved: "Игра сохранена",
	loaded: "Игра восстановлена",
	imported: "Импортировано",
}

msg['en'] = {
	nosave: "No such save.",
	lshelp: "!ls - show saves.",
	rmhelp: "!rm [file] - remove save.",
	saved: "Saved",
	loaded: "Restored",
	imported: "Imported",
}

function _(id)
{
	if (/^ru\b/.test(navigator.language)) {
		return msg['ru'][id];
	}
	return msg['en'][id];
}

$(function()
{
	$body = $('body');
	var elem = $('<span>&nbsp;</span>').appendTo($body);
	bodylineheight = elem.height();
	elem.remove();
});

var selection = window.getSelection ||
	function() { return document.selection ? document.selection.createRange().text : '' };

var Blobs = {};

function matchRe(regexp, string) {
	var isMatching = string.match(regexp);
	if (isMatching) {
		return isMatching[1].trim();
	}
	return '';
}

function basename(path)
{
	var parts = path.split('/');
	return parts[parts.length-1];
}

function gameName()
{
	if (typeof(TextDecoder) == 'undefined') {
		return basename(parser_path());
	}
	var fullpath = parser_path() + '/main3.lua';
	fullpath = fullpath.replace(/^\./, '');
	var fd = FS.open(fullpath, "r");
	var stat = FS.stat(fullpath);
	var len = (stat.size > 192) ? 192:stat.size;
	var buf = new Uint8Array(len);
	FS.read(fd, buf, 0, len, 0);
	var ret = new TextDecoder().decode(buf);
	var nam = matchRe(/--\s*\$Name\(ru\)\s*:\s*([^\$\n]+)/, ret);
	if (nam === '') {
		nam = matchRe(/--\s*\$Name\s*:\s*([^\$\n]+)/, ret);
		if (ret === '') {
			nam = basename(parser_path());
		}
	}
	FS.close(fd);
	return nam;
}
function savePath()
{
	var fullpath = parser_path().replace(/^\./, '').replace(/\/games\//, '');
	fullpath = '/appdata/saves/' + fullpath + '/';
	return fullpath;
}

function isAutosave()
{
	var fullpath = savePath() + parser_savename();
	if (FS.analyzePath(fullpath).exists) {
		return true;
	}
	return false;
}

function rmSave(name)
{
	if (!name)
		name = 'autosave';
	var fullpath = savePath() + name;
	if (FS.analyzePath(fullpath).exists) {
		FS.unlink(fullpath);
		return "Ok.";
	}
	return "No file.";
}

function rmAutosave()
{
	rmSave('autosave')
}

function saveUrl(name)
{
	var fullpath = savePath() + name;
	if (FS.analyzePath(fullpath).exists) {
		return URL.createObjectURL(new Blob([FS.readFile(fullpath)]));
	}
}

function exportFs(fullpath)
{
	console.log(fullpath);
	if (FS.analyzePath(fullpath).exists) {
		return "<a href='" + URL.createObjectURL(new Blob([FS.readFile(fullpath)])) + "' download='"+ fullpath+ "'>" + fullpath + "</a>";
	}
	return fullpath;
}

function exportFsCapt(str, capt)
{
	return exportFs(capt);
}

function dataUrl(path)
{
	var fullpath = parser_path() + '/' + path;
	fullpath = fullpath.trim().replace(/\\/g, '\/').replace(/\/+/g, '\/');
	fullpath = fullpath.replace(/^\./, '');
	if (!Blobs.hasOwnProperty(fullpath)) {
		if (FS.analyzePath(fullpath).exists) {
			var content = FS.readFile(fullpath);
			Blobs[fullpath] = URL.createObjectURL(new Blob([content]));
		} else {
			Blobs[fullpath] = '';
		}

	}
	return Blobs[fullpath];
}

function parseImg(tag, img)
{
	var url = dataUrl(img);
	if (url != "")
		return '<img '+ 'src="' + url + '" onload="input.scroll();">';
	else
		return "";
}

function parseOutput(str)
{
	str = str.replace(/<g:([^>]+)>/g, parseImg);
	str = str.replace(/\/games\/[^/]+\/(log[0-9]+.txt)/g, exportFsCapt);
	return str;
}

function fmtCommand(command)
{
	return '<div role="heading" aria-level="2">&gt; <b>' + command.trim() + '</b></div>\n'
}

var scrollPages = window.scrollByPages || function( pages )
{
	var height = document.documentElement.clientHeight,
	delta = height - Math.min( height / 10, bodylineheight * 2 );
	scrollBy( 0, delta * pages );
}

function uploadSave(input, name)
{
	var reader = new FileReader();
	reader.onload = function importSave(e) {
		var fullpath = parser_path().replace(/^\./, '').replace(/\/games\//, '');
		fullpath = '/appdata/saves/' + fullpath + '/' + name;
		FS.writeFile(fullpath, e.target.result);
		console.log("Imported: " + name + "\n");
		FS.syncfs(function(error) {
			if (error) {
				input.replaceWith("Can't import: " + name +".");
			} else {
				input.replaceWith(_('imported') + ": " + name +".");
			}
		})
	}
	reader.readAsText(input.files[0]);
}

function lsSaves()
{
	var ret = "";
	if (!FS.analyzePath(savePath()).exists)
		return ret;
	FS.readdir(savePath()).forEach(function(dir) {
		if (dir == "." || dir == "..") return;
		if (ret != "") ret = ret + ", ";
		ret = ret + dir;
	});
	if (ret != "") {
		ret = ret+"\n";
		ret = ret + _('rmhelp') +"\n";
	}
	return ret;
}

function Input(output)
{
	var self = this;
	self.input = $('<input>', {
		class: 'TextInput',
		autocapitalize: 'off',
		keydown: function(event)
		{
			var  keyCode = self.keyCode = event.which, cancel;
			if (self.mode != 'line') {
				return;
			}
			if (keyCode == 38) {
				self.prev_next(1);
				cancel = 1;
			} else if (keyCode == 40) {
				self.prev_next(-1);
				cancel = 1;
			} else if (keyCode == 33) {
				scrollPages(-1);
				cancel = 1;
			} else if (keyCode == 34) {
				scrollPages(1);
				cancel = 1;
			} else if (keyCode == 13) {
				self.submitLine();
				cancel = 1;
			}
			event.stopPropagation();
			if (cancel) {
				return false;
			}
		}
	})
	self.output = output;
	self.scrollParent = $('html,body');
	self.history = [];
	self.promptline = $('<div>');
	self.prompt = $('<span>').append('\n&gt; ');
	self.promptline.append(self.prompt);
	self.promptline.append(self.input.val(''));

	self.getLine = function(attach)
	{
		this.mode = 'line'
		this.current = 0;
		this.mutable_history = this.history.slice();
		this.mutable_history.unshift('');
		this.input.val('');
		if (attach)
			this.promptline.appendTo(this.output.parent());
		var width = this.output.width() - this.prompt.width() * 2;
		this.input.width(width);
		this.scroll();
		this.input.focus();
	}
	self.submitLine = function()
	{
		var command = this.input.val();
		command = command.replace(/&/g, " ").replace(/</g, " ").replace(/>/g, " ");
		if (command != this.history[0] && /\S/.test(command)) {
			this.history.unshift(command);
		}
		this.mode = 0;
		var span = $('<div role="listitem">');
		var ret;
		var need_restart = false;
		if (command.startsWith("!")) {
			var args = command.split(" ", 2);
			switch (args[0]) {
			case '!rm':
				console.log(args[1]);
				ret = rmSave(args[1]);
				break;
			case '!ls':
				ret = lsSaves();
				break;
			case '!restart':
				need_restart = true;
				break;
//			case '!export':
//				ret = exportFs(args[1]);
//				break;
			default:
				ret = '?';
			}
		} else {
			ret = parser_cmd('@metaparser "' + command.replace(/"/g, "") + '"'); //'
			if (!ret)
				ret = parser_cmd(command.replace(/"/g, "")); //"
		}
		if (parser_restart() == 1 || need_restart) {
			console.log("Restart game\n.");
			parser_stop();
			parser_start(Game);
			// rmAutosave();
			ret = parser_cmd("look");
			this.output.empty();
		} else if (parser_save() == 1) {
			console.log("Save game\n.");
			ret = parser_autosave().trim();
			if (ret)
				ret = ret + "\n";
			ret = ret + "<i>" + _('saved') + " (" + "<a href='" + saveUrl(parser_savename()) + "' download='"+ parser_savename()+ "'>" + parser_savename() + "</a>)</i>";
			ret = fmtCommand(command) + ret.trim();
		} else if (parser_load() == 1) {
			if (!isAutosave()) {
				ret = fmtCommand(command) + "<i>" + _('nosave') + "</i>\n";
				ret = ret + _('lshelp') + "\n";
				ret = ret + "\n<input type='file' onchange='uploadSave(this,\"" + parser_savename() +"\")'>\n";
			} else {
				console.log("Load game\n.");
				parser_stop();
				parser_start(Game);
				ret = "<i>" + _('loaded') + " (" + parser_savename() + ")</i>\n\n" + parser_autoload();
				this.output.empty();
			}
		} else if (parser_clear() == 1) {
			this.output.empty();
		} else {
			ret = fmtCommand(command) + ret.trim();
		}
		ret = parseOutput(ret);
		ret = ret.trim() + '\n\n';
		span.append(ret);
		span.appendTo(this.output);
		this.getLine();
	}
	this.scroll = function()
	{
		var laststruct = this.output.children().last();
		this.scrollParent.scrollTop(laststruct.offset().top - bodylineheight);
	}
	this.prev_next = function(change)
	{
		var input = this.input,
			mutable_history = this.mutable_history,
			current = this.current,
			new_current = current + change;

		// Check it's within range
		if ( new_current < mutable_history.length && new_current >= 0 ) {
			mutable_history[current] = input.val();
			input.val( mutable_history[new_current] );
			this.current = new_current;
		}
	}
	var input = self.input;
	$doc.on( 'click.TextInput keydown.TextInput',
		function(ev) {
			// Only intercept on things that aren't inputs and if the user isn't selecting text
			if ( ev.target.nodeName != 'INPUT' && selection() == '' ) {
				// If the input box is close to the viewport then focus it
				if ( $window.scrollTop() + $window.height() - input.offset().top > -60 ) {
					// window.scrollTo( 0, 9e9 );
					input.scroll();
					// Manually reset the target incase focus/trigger don't - we don't want the trigger to recurse
					ev.target = input[0];
					input.focus().trigger( ev );
					// Stop propagating after re-triggering it, so that the trigger will work for all keys
					ev.stopPropagation();
				}
				// Intercept the backspace key if not
				else if (ev.type == 'keydown' && ev.which == 8) {
					return false;
				}
			}
	});
}


function Start(fname)
{
	Game = fname;
	$("#about").detach();

	input = new Input($("#transcript"));
	var span = $('<div role="listitem">');

	if (parser_start(fname) != 0) {
		span.append('<b>Error while starting game!</b>');
		span.appendTo(input.output)
		return;
	}
	document.title = gameName();
	var text = parser_cmd("look");
//	if (isAutosave()) {
//		text = "<i>Игра восстановлена. \"Заново\" &mdash; начать сначала.</i>\n\n" + text;
//	}
	text = parseOutput(text).trim();
	span.append(text + '\n\n');
	span.appendTo(input.output);
	input.getLine(true);
}
