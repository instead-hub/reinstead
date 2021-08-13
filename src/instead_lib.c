#include <string.h>
#include <stdlib.h>
#include <lua.h>
#include <lualib.h>
#include <lauxlib.h>
#include "lua-compat.h"
#include "instead.h"

static lua_State *IL = NULL;

static int
docall(lua_State *L)
{
	int status;
	status = lua_pcall(L, 0, LUA_MULTRET, 0);
	/* force a complete garbage collection in case of errors */
	if (status != 0)
		lua_gc(L, LUA_GCCOLLECT, 0);
	return status;
}

static int
ui_eval(lua_State *L)
{
	int n, i;
	const char *expr = luaL_optstring(L, 1, NULL);
	if (!expr)
		return 0;
	int N = lua_gettop(IL);
	int status = luaL_loadstring(IL, expr) || docall(IL);
	if (status && !lua_isnil(IL, -1)) {
		const char *msg = lua_tostring(IL, -1);
		if (msg == NULL)
			msg = "(error object is not a string)";
		lua_pop(IL, 1);
		lua_pushboolean(L, 0);
		lua_pushstring(L, msg);
		return 2;
	}
	n = lua_gettop(IL) - N;
	lua_pushboolean(L, 1);
	for (i = 0; i < n; i++) {
		if (lua_isnumber(IL, i - n)) {
			lua_pushnumber(L, lua_tonumber(IL, i - n));
		} else if (lua_isboolean(IL, i - n)) {
			lua_pushboolean(L, lua_toboolean(IL, i - n));
		} else {
			lua_pushstring(L, lua_tostring(IL, i - n));
		}
	}
	lua_pop(IL, n);
	return n + 1;
}

static const luaL_Reg tiny_funcs[] = {
	{ "core_eval", ui_eval },
	{ NULL, NULL }
};

static int
tiny_init(void)
{
	int rc;
	char path[1024];
	instead_api_register(tiny_funcs);
	snprintf(path, sizeof(path), "%s/stead3/reinstead.lua", instead_lua_path(NULL));
	rc = instead_loadfile(path);
	if (rc)
		return rc;
	return 0;
}


static struct
instead_ext ext = {
	.init = tiny_init,
};

static int
cmd(lua_State *L)
{
	int rc = 0;
	char *str;
	const char *cmd = luaL_optstring(L, 1, NULL);
	if (!cmd)
		return 0;
	str = instead_cmd((char*)cmd, &rc);
	lua_pushboolean(L, !rc);
	if (!str)
		str = strdup("");
	lua_pushstring(L, str);
	free(str);
	return 2;
}

static int
init(lua_State *L)
{
	const char *path = luaL_optstring(L, 1, NULL);
	if (!path)
		return 0;
	if (instead_extension(&ext)) {
		lua_pushboolean(L, 0);
		lua_pushstring(L, "Can't register tiny extension\n");
		return 2;
	}
	if (instead_init(path)) {
		lua_pushboolean(L, 0);
		lua_pushstring(L, instead_err());
		return 2;
	}
	if (instead_load(NULL)) {
		lua_pushboolean(L, 0);
		lua_pushstring(L, instead_err());
		return 2;
	}
	lua_pushboolean(L, 1);
	return 1;
}

static int
done(lua_State *L)
{
	instead_done();
	return 0;
}
static int
debug(lua_State *L)
{
	instead_set_debug(lua_toboolean(L, 1));
	return 0;
}

static int
standalone(lua_State *L)
{
	instead_set_standalone(lua_toboolean(L, 1));
	return 0;
}

static int
error(lua_State *L)
{
	const char *msg = luaL_optstring(L, 1, NULL);
	lua_pushstring(L, instead_err());
	if (msg) {
		instead_err_msg(msg[0]?msg:NULL);
	}
	return 1;
}

static const luaL_Reg
instead_funcs[] = {
	{ "init", init },
	{ "done", done },
	{ "cmd", cmd },
	{ "debug", debug },
	{ "error", error },
	{ "standalone", standalone },
	{ NULL, NULL },
};

int
instead_lib(lua_State *L)
{
	luaL_newlib(L, instead_funcs);
	IL = L;
	return 0;
}
