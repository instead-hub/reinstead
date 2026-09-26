/*
 * Copyright 2009-2022 Peter Kosyh <p.kosyh at gmail.com>
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation files
 * (the "Software"), to deal in the Software without restriction,
 * including without limitation the rights to use, copy, modify, merge,
 * publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
 * LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
 * WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <locale.h>

#ifdef _WIN32
#include <windows.h>
extern char *dirname(char *);
#else
#include <sys/wait.h>
#endif

#include "instead/instead.h"
#include "instead/util.h"
#define WIDTH 70

static int opt_log = 0;
static int opt_lua = 0;
static int opt_echo = 0;
static int opt_debug = 0;
static int opt_width = WIDTH;
static char *opt_autoload = NULL;
static const char *mmedia_bin = NULL;
static int opt_autosave = 0;
static int opt_mmedia = 0;
static int need_restart = 0;
static int need_load = 0;
static int need_save = 0;

#ifdef _WIN32
static int opt_codepage = 1251;
#endif
static int luaB_menu(lua_State *L)
{
	const char *menu = luaL_optstring(L, 1, NULL);
	if (!menu)
		return 0;
	need_save = !strcmp(menu, "save");
	need_load = !strcmp(menu, "load");
	return 0;
}

static int luaB_restart(lua_State *L)
{
	need_restart = !lua_isboolean(L, 1) || lua_toboolean(L, 1);
	return 0;
}

static const luaL_Reg tiny_funcs[] = {
	{ "instead_restart", luaB_restart },
	{ "instead_menu", luaB_menu },
	{ NULL, NULL }
};

static int tiny_init(void)
{
	int rc;
	char path[1024];
	instead_api_register(tiny_funcs);
	snprintf(path, sizeof(path), "%s/tiny.lua", instead_lua_path(NULL));
	rc = instead_loadfile(path);
	if (rc)
		return rc;
	return 0;
}
static struct instead_ext ext = {
	.init = tiny_init,
};

#define utf_cont(p) ((*(p) & 0xc0) == 0x80)

static int utf_ff(const char *s, const char *e)
{
	int l = 0;
	if (!s || !e)
		return 0;
	if (s > e)
		return 0;
	if ((*s & 0x80) == 0) /* ascii */
		return 1;
	l = 1;
	while (s < e && utf_cont(s + 1)) {
		s ++;
		l ++;
	}
	return l;
}

static void fmt(const char *str, int width)
{
	int l;
	const char *ptr = str;
	const char *eptr = ptr + strlen(str);
	const char *s = str;
	const char *last = NULL;
	char c;
	int w = 0;
	while ((l = utf_ff(ptr, eptr))) {
		c = *ptr;
		ptr += l;
		w ++;
		if (c == ' ' || c == '\t' || c == '\n')
			last = ptr;
		if ((width > 0 && w >= width && last && s < last) || c == '\n') {
			while(s != last) {
			#ifdef _WIN32
				int n = utf_ff(s, last);
				write(1, s, n);
				s += n;
			#else
				putc(*s++, stdout);
			#endif
			}
			if (c != '\n')
				putc('\n', stdout);
			fflush(stdout);
			w = 0;
			last = s;
			ptr = s;
			continue;
		}
	}
	while(s != eptr) {
	#ifdef _WIN32
		int n = utf_ff(s, eptr);
		write(1, s, n);
		s += n;
	#else
		putc(*s++, stdout);
	#endif
	}
	putc('\n', stdout);
	fflush(stdout);
}

static char *trim(char *str)
{
	char *eptr = str + strlen(str);
	while ((*eptr == '\n' || *eptr == 0 || *eptr == ' ') && eptr != str) *eptr-- = 0;
	str += strspn(str, " \t\n\r");
	return str;
}

static void footer(void)
{
	char *p; int way = 0;
	p = instead_cmd("way", NULL);
	if (p && *p) {
		printf("\n");
		way = 1;
		printf(">> "); fmt(trim(p), opt_width);
		free(p);
	}
	p = instead_cmd("inv", NULL);
	if (p && *p) {
		if (!way)
			printf("\n");
		printf("** "); fmt(trim(p), opt_width);
		free(p);
	}
}

static void reopen_stderr(const char *fname)
{
	if (*fname && freopen(fname, "w", stderr) != stderr) {
		fprintf(stderr, "Error opening '%s': %s\n", fname, strerror(errno));
		exit(1);
	}
}

static void reopen_stdin(const char *fname)
{
	if (!fname || !*fname)
		fname = "autoscript";
	if (freopen(fname, "r", stdin) != stdin) {
		fprintf(stderr, "Error opening '%s': %s\n", fname, strerror(errno));
		exit(1);
	}
}

static char *get_input(const char *prompt)
{
	static char input[256];
	char *p;
	printf("\n%s", prompt); fflush(stdout);
	input[0] = 0;
	p = fgets(input, sizeof(input), stdin);
	if (p)
		p[strcspn(p, "\n\r")] = 0;
	if (opt_echo && p)
		printf("%s\n", p);
	return p;
}

static void show_err(void)
{
	if (instead_err()) {
		printf("Error: %s\n", instead_err());
		instead_err_msg(NULL);
	}
}

static char *media[] = { NULL, NULL };
static char *media_fn[] = {
	"instead.get_picture",
	"instead.get_music"
};

static void mmedia_run(const char *f)
{
#ifndef _WIN32
	pid_t pid;
	int status;
	if (!mmedia_bin || !mmedia_bin[0])
		return;
	pid = fork();
	if (pid == -1)
		return;
	else if (pid > 0) {
		waitpid(pid, &status, 0);
	} else {
		execl(mmedia_bin, mmedia_bin, f, NULL);
		exit(1);
	}
#else
	static char cmd[512];
	if (!mmedia_bin || !mmedia_bin[0])
		return;
	snprintf(cmd, sizeof(cmd), "%s \"%s\"", mmedia_bin, f);
	/* not safe! but it is windows... */
	system(cmd);
#endif
}

static void mmedia(int t)
{
	char *mm;
	if (!opt_mmedia)
		return;
	instead_lock();
	instead_function(media_fn[t], NULL);
	mm = instead_retval(0);
	instead_clear();
	instead_unlock();
	if (!mm && !media[t])
		return;
	if ((!media[t] && mm) || (media[t] && !mm) ||
	    strcmp(media[t], mm)) {
		free(media[t]);
		media[t] = mm;
		if (mm && *mm) { /* changed */
			printf("@ %s\n", mm);
			if (t == 0) /* we do not support composed images */
				mm[strcspn(mm, ";")] = 0;
			mmedia_run(mm);
		}
	}
}

int main(int argc, const char **argv)
{
	int rc, i;
	char *str;
	FILE *log_file = NULL;
	const char *game = NULL;
	char cmd[256 + 64];

	int parser_mode = 0;
	int menu_mode = 0;
	int opt_args = 0;

#ifdef _WIN32
	char cwd[1024];
	char base[PATH_MAX];
	GetModuleFileNameA(NULL, cwd, 1024);
	unix_path(cwd);
	snprintf(base, sizeof(base), "%s/%s", dirname(cwd), STEAD_PATH);
	instead_lua_path(base);
#endif

	setlocale(LC_ALL, "");
	for (i = 1; i < argc; i++) {
		if (!strncmp(argv[i], "-l", 2)) {
			opt_log = 1;
			log_file = fopen(argv[i] + 2, "wb");
#ifdef _WIN32
		} else if (!strncmp(argv[i], "-cp", 3)) {
			opt_codepage = atoi(argv[i] + 3);
#endif
		} else if (!strcmp(argv[i], "-a")) {
			opt_autoload = strdup("autosave");
			opt_autosave = 1;
		} else if (!strcmp(argv[i], "-x")) {
			opt_lua = 1;
		} else if (!strncmp(argv[i], "-m", 2)) {
			opt_mmedia = 1;
			mmedia_bin = argv[i] + 2;
		} else if (!strcmp(argv[i], "-e")) {
			opt_echo = 1;
		} else if (!strncmp(argv[i], "-d", 2)) {
			opt_debug = 1;
			reopen_stderr(argv[i] + 2);
		} else if (!strncmp(argv[i], "-w", 2)) {
			opt_width = atoi(argv[i] + 2);
		} else if (!strncmp(argv[i], "-i", 2)) {
			reopen_stdin(argv[i] + 2);
		} else if (!game) {
			game = argv[i];
			opt_args = i + 1;
		}
	}
#ifdef _WIN32
	SetConsoleOutputCP(opt_codepage);
	SetConsoleCP(opt_codepage);
#endif
	if (!game) {
		printf("instead-cli %s (by Peter Kosyh '2021-2025)\n", VERSION);
		fprintf(stdout, "Usage: %s [-d<file>] [-w<width>] [-i<script>] [-l<log>] [-a] <game>\n", argv[0]);
		exit(1);
	}

	if (instead_extension(&ext)) {
		fprintf(stderr, "Can't register tiny extension\n");
		exit(1);
	}

	if (!opt_debug)
		fclose(stderr);

	instead_set_debug(opt_debug);

	if (opt_lua) {
		rc = instead_init_lua(dirpath(game), 0);
		show_err();
		if (rc)
			exit(1);
		rc = instead_loadscript((char*)game, argc - opt_args, (char **)argv + opt_args, 1);
		show_err();
		instead_done();
		exit(!!rc);
	}

restart:
	if (instead_init(game)) {
		fprintf(stdout, "Can not init game: %s (%s)\n", game, instead_err());
		exit(1);
	}
#if defined(_WIN32) && defined(_HAVE_ICONV)
	if (opt_codepage == 65001)
		instead_set_encoding("UTF-8");
	else {
		snprintf(cmd, sizeof(cmd), "CP%d", opt_codepage);
		instead_set_encoding(cmd);
	}
#endif
	if (instead_load(NULL)) {
		fprintf(stdout, "Can not load game: %s\n", instead_err());
		exit(1);
	}
	if (opt_autoload && !access(opt_autoload, R_OK)) {
		snprintf(cmd, sizeof(cmd), "load %s", opt_autoload);
		printf("/%s\n", cmd);
		str = instead_cmd(cmd, &rc);
	} else
		str = instead_cmd("look", &rc);
	mmedia(0); mmedia(1);

	show_err();
	if (!rc && str) {
		fmt(trim(str), opt_width);
	}
	free(str);
	if (opt_autoload) {
		free(opt_autoload);
		opt_autoload = NULL;
	}
	need_restart = need_load = need_save = 0;
	while (1) {
		char *p;
		int cmd_mode = 0;
		p = get_input("> ");
		if (p && *p != '/')
			p = trim(p);
		if (!p || !strcmp(p, "/quit")) {
			printf("\n");
			break;
		} else if (p && !strcmp(p, "/restart")) {
			instead_done();
			goto restart;
		}
		rc = 1; str = NULL;

		if (*p == '/') {
			p++;
			cmd_mode = 1;
			snprintf(cmd, sizeof(cmd), "%s", p);
			str = instead_cmd(cmd, &rc);
			if (rc)
				printf("Error!\n");
			rc = 0; /* force success */
		} else if (!parser_mode) {
			snprintf(cmd, sizeof(cmd), "use %s", p); /* try use */
			str = instead_cmd(cmd, &rc);
			if (rc) { /* try go */
				free(str);
				snprintf(cmd, sizeof(cmd), "go %s", p);
				str = instead_cmd(cmd, &rc);
			}
			if (!rc)
				menu_mode = 1;
		}
		if (rc && !str && !menu_mode) { /* parser? */
			snprintf(cmd, sizeof(cmd), "@metaparser \"%s\"", p);
			str = instead_cmd(cmd, &rc);
			if (!rc && p[0])
				parser_mode = 1;
		}
		if (rc) { /* try act */
			free(str);
			if (!*p) /* empty? */
				cmd[0] = 0;
			else
				snprintf(cmd, sizeof(cmd), "act %s", p);

			str = instead_cmd(cmd, &rc);
		}
		if (str) {
			mmedia(0); mmedia(1);
			fmt(trim(str), opt_width);
			free(str);
		}
		if (!parser_mode && !cmd_mode)
			footer();
		if (opt_log) {
			if (log_file)
				fprintf(log_file, "%s\n", p);
			else
				fprintf(stderr, "%s\n", p);
		}
		if (need_restart) {
			instead_done();
			goto restart;
		}
		if (need_save) {
			puts("?(autosave)"); fflush(stdout);
			p = get_input("> ");
			if (p && *p)
				snprintf(cmd, sizeof(cmd), "save %s", p);
			else
				snprintf(cmd, sizeof(cmd), "save autosave");
			printf("/%s\n", cmd);
			str = instead_cmd(cmd, NULL);
			if (str)
				free(str);
			need_save = 0;
		} else if (need_load) {
			puts("?(autosave)"); fflush(stdout);
			p = get_input("> ");
			if (opt_autoload)
				free(opt_autoload);
			if (p && *p)
				opt_autoload = strdup(p);
			else
				opt_autoload = strdup("autosave");
			if (!access(opt_autoload, R_OK)) {
				instead_done();
				goto restart;
			} else {
				need_load = 0;
				printf("No file\n");
				free(opt_autoload); opt_autoload = NULL;
			}
		}
		show_err();
	}
	if (opt_autosave)
		free(instead_cmd("save autosave", NULL));
	instead_done();
	if (log_file)
		fclose(log_file);
	return 0;
}
