var Module;
FS.mkdir('/appdata');
FS.mount(IDBFS,{},'/appdata');

FS.mkdir('/games');
FS.mount(MEMFS,{},'/games');

var parser_start, parser_stop, parser_cmd, parser_restart, parser_load, parser_load, parser_autoload, parser_autosave, parser_path, parser_clear, parser_savename

function startsWith(str, word) {
	return str.lastIndexOf(word, 0) === 0;
}
Module['postRun'] = [];
Module['postRun'].push(function() {
	console.log("Starting...");
	parser_start = Module.cwrap('parser_start', 'number', ['string'])
	parser_restart = Module.cwrap('parser_restart', 'number')
	parser_stop = Module.cwrap('parser_stop', null)
	parser_cmd = Module.cwrap('parser_cmd', 'string', ['string'])
	parser_autoload = Module.cwrap('parser_autoload', 'string')
	parser_autosave = Module.cwrap('parser_autosave', 'string')
	parser_load = Module.cwrap('parser_load', 'number')
	parser_save = Module.cwrap('parser_save', 'number')
	parser_path = Module.cwrap('parser_path', 'string')
	parser_clear = Module.cwrap('parser_clear', 'number')
	parser_savename = Module.cwrap('parser_savename', 'string')

	var argv = []
	var req
	var url

	var metatags = document.getElementsByTagName('meta');

	for (var mt = 0; mt < metatags.length; mt++) {
		if (metatags[mt].getAttribute("name") === "gamefile") {
			url = metatags[mt].getAttribute("content");
		}
	}
	var crossio = "https://cors-anywhere.herokuapp.com/";
	// crossio = "https://proxy.iplayif.com/proxy/?url="
	if (!url && typeof window === "object") {
		argv = window.location.search.substr(1).trim().split('&');
		if (!argv[0])
			argv = [];
		// argv can be empty: fall back to data.zip below.
		if (argv.length && (startsWith(argv[0], "http:") || startsWith(argv[0], "https:"))) {
			url = crossio + argv[0];
		} else if (argv.length) {
			url = argv[0];
		}
	}

	if (!url) {
		url='data.zip';
	}
	var baseurl = url
	url = url + '?' + (Math.random()*10000000);
	req = new XMLHttpRequest();
	req.open("GET", url, true);
	req.responseType = "arraybuffer";
	console.log("Get: ", url);

	req.onload = function() {
		var basename = function(path) {
			parts = path.split( '/' );
			return parts[parts.length - 1];
		}
		var data = req.response;
		console.log("Data loaded...");
		FS.syncfs(true, function (error) {
			if (error) {
				console.log("Error while syncing: ", error);
			}
			url = basename(baseurl);
			console.log("Writing: ", url);
			FS.writeFile(url, new Int8Array(data), { encoding: 'binary' }, "w");
			console.log("Running...");
			window.onclick = function(){ window.focus() };
			Start(url);
		});
	}
	req.send(null);
});
