// Runs before the Emscripten runtime initializes, so the output hooks set
// here are the ones the runtime picks up.
//
// The engine reports progress (unpacking a game, building the dictionary,
// ...) on stderr. The browser console shows stderr as errors, which is
// misleading: route it to console.log so it reads as plain messages.
var Module = typeof Module !== "undefined" ? Module : {};

Module["printErr"] = function (text) {
	console.log(text);
};
