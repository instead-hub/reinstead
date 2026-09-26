// Build check without a browser: load the demo game and talk to the parser.
// Needs `make smoke` (which builds build/smoke/mp.js).

const path = require('path');
const createMP = require('../build/smoke/mp.js');

// A word from the demo game inventory (data/games/trial).
const MARKER = 'скребок';

createMP({
	locateFile: (f) => path.join(__dirname, '..', 'build', 'smoke', f),
})
	.then((M) => {
		const start = M.cwrap('parser_start', 'number', ['string']);
		const cmd = M.cwrap('parser_cmd', 'string', ['string']);

		if (start('/game') !== 0) {
			throw new Error('parser_start could not load the game');
		}

		// Same as lib/mp.js: first try the parser command, then the plain one.
		const run = (c) => cmd('@metaparser "' + c + '"') || cmd(c);
		const reply = run('инвентарь') || '';

		if (!reply.includes(MARKER)) {
			throw new Error('unexpected parser reply:\n' + reply);
		}
		console.log('smoke: ok');
	})
	.catch((e) => {
		console.error('smoke: ' + e.message);
		process.exit(1);
	});
