#include <SDL2/SDL.h>
#include "external.h"
#include "platform.h"

static void
tolow(char *p)
{
	while (*p) {
		if (*p >=  'A' && *p <= 'Z')
			*p |= 0x20;
		p ++;
	}
}

static SDL_Window *window;

double
Time(void)
{
	return SDL_GetPerformanceCounter() / (double) SDL_GetPerformanceFrequency();
}

unsigned long
Ticks(void)
{
	return SDL_GetTicks();
}

void
WindowMode(int n)
{
	SDL_SetWindowFullscreen(window,
		n == WIN_FULLSCREEN ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
	if (n == WIN_NORMAL)
		SDL_RestoreWindow(window);
	else if (n == WIN_MAXIMIZED)
		SDL_MaximizeWindow(window);
}

void
WindowTitle(const char *title)
{
	SDL_SetWindowTitle(window, title);
}

int
WaitEvent(float n)
{
	return SDL_WaitEventTimeout(NULL, n * 1000);
}

void
Delay(float n)
{
	SDL_Delay(n * 1000);
}

static char*
key_name(int sym)
{
	static char dst[16];
	strcpy(dst, SDL_GetKeyName(sym));
	tolow(dst);
	return dst;
}

static char*
button_name(int button)
{
	static char nam[16];
	switch (button) {
	case 1:
		strcpy(nam, "left");
		break;
	case 2:
		strcpy(nam, "middle");
		break;
	case 3:
		strcpy(nam, "right");
		break;
	default:
		snprintf(nam, sizeof(nam), "btn%d", button);
		break;
	}
	nam[sizeof(nam)-1] = 0;
	return nam;
}
float
GetScale(void)
{
	float dpi;
	SDL_GetDisplayDPI(0, NULL, &dpi, NULL);
	return dpi / 96.0f;
}

int
PlatformInit(void)
{
#ifdef _WIN32
	HINSTANCE lib = LoadLibrary("user32.dll");
	int (*SetProcessDPIAware)() = (void*) GetProcAddress(lib, "SetProcessDPIAware");
	if (SetProcessDPIAware)
		SetProcessDPIAware();
#endif
	if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS))
		return -1;
	return 0;
}

static SDL_Surface *winbuff = NULL;

void
PlatformDone(void)
{
	if (winbuff)
		SDL_FreeSurface(winbuff);
	SDL_DestroyWindow(window);
	SDL_Quit();
}

const char *
GetPlatform(void)
{
	return SDL_GetPlatform();
}

int
WindowCreate(void)
{
	SDL_DisplayMode mode;
	SDL_GetCurrentDisplayMode(0, &mode);
	window = SDL_CreateWindow("",
		SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED,
		mode.w * 0.5, mode.h * 0.8,
		SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI);
	if (!window)
		return -1;
	return 0;
}

const char *
GetExePath(const char *progname)
{
	static char path[4096];
#if _WIN32
	int len = GetModuleFileName(NULL, path, sizeof(path) - 1);
	path[len] = 0;
#elif __APPLE__
	unsigned size = sizeof(path);
	_NSGetExecutablePath(path, &size);
#elif __linux__
	int len;
	char proc_path[256];
	snprintf(proc_path, sizeof(proc_path), "/proc/%d/exe", getpid());
	len = readlink(proc_path, path, sizeof(path) - 1);
	path[len] = 0;
#else
	strncpy(path, progname, sizeof(path));
#endif
	path[sizeof(path) - 1] = 0;
	return path;
}

void
WindowResize(int w, int h)
{
	SDL_FreeSurface(winbuff);
	winbuff = NULL;
}

void
WindowUpdate(int x, int y, int w, int h)
{
	SDL_Rect r;
	if (!winbuff)
		return;
	if (w > 0 && h > 0) {
		r.x = x;
		r.y = y;
		r.w = w;
		r.h = h;
		SDL_BlitSurface(winbuff, &r, SDL_GetWindowSurface(window), &r);
	} else {
		SDL_BlitSurface(winbuff, NULL, SDL_GetWindowSurface(window), NULL);
	}
	SDL_UpdateWindowSurface(window);
}

void
Icon(unsigned char *ptr, int w, int h)
{
	SDL_Surface *surf;
	surf = SDL_CreateRGBSurfaceFrom(ptr, w, h,
			32, w * 4,
			0x000000ff,
			0x0000ff00,
			0x00ff0000,
			0xff000000);
	if (!surf)
		return;
	SDL_SetWindowIcon(window, surf);
	SDL_FreeSurface(surf);
	return;
}

unsigned char *
WindowPixels(int *w, int *h)
{
	SDL_Surface *surf = SDL_GetWindowSurface(window);
	if (!surf)
		return NULL;
	if (winbuff && (winbuff->w != surf->w || winbuff->h != surf->h)) {
		SDL_FreeSurface(winbuff);
		winbuff = NULL;
	}
	if (!winbuff)
		winbuff = SDL_CreateRGBSurface(0, surf->w, surf->h, 32,
			0x000000ff, 0x0000ff00, 0x00ff0000, 0xff000000);
	if (!winbuff)
		return NULL;
	*w = surf->w;
	*h = surf->h;
	return (unsigned char*)winbuff->pixels;
}

int
sys_poll(lua_State *L)
{
	SDL_Event e;
top:
	if (!SDL_PollEvent(&e))
		return 0;

	switch (e.type) {
	case SDL_QUIT:
		lua_pushstring(L, "quit");
		return 1;

	case SDL_WINDOWEVENT:
		if (e.window.event == SDL_WINDOWEVENT_RESIZED) {
			lua_pushstring(L, "resized");
			lua_pushnumber(L, e.window.data1);
			lua_pushnumber(L, e.window.data2);
			WindowResize(e.window.data1, e.window.data2);
			return 3;
		} else if (e.window.event == SDL_WINDOWEVENT_EXPOSED) {
			//rencache_invalidate();
			lua_pushstring(L, "exposed");
			return 1;
		}
		/* on some systems, when alt-tabbing to the window SDL will queue up
		** several KEYDOWN events for the `tab` key; we flush all keydown
		** events on focus so these are discarded */
		if (e.window.event == SDL_WINDOWEVENT_FOCUS_GAINED) {
			SDL_FlushEvent(SDL_KEYDOWN);
			SDL_FlushEvent(SDL_KEYUP);
		}
		goto top;
	case SDL_KEYDOWN:
		lua_pushstring(L, "keydown");
		lua_pushstring(L, key_name(e.key.keysym.sym));
		return 2;
	case SDL_KEYUP:
		lua_pushstring(L, "keyup");
		lua_pushstring(L, key_name(e.key.keysym.sym));
		return 2;
	case SDL_TEXTINPUT:
		lua_pushstring(L, "text");
		lua_pushstring(L, e.text.text);
		return 2;
	case SDL_MOUSEBUTTONDOWN:
		if (e.button.button == 1) { SDL_CaptureMouse(1); }
		lua_pushstring(L, "mousedown");
		lua_pushstring(L, button_name(e.button.button));
		lua_pushnumber(L, e.button.x);
		lua_pushnumber(L, e.button.y);
		lua_pushnumber(L, e.button.clicks);
		return 5;
	case SDL_MOUSEBUTTONUP:
		if (e.button.button == 1) { SDL_CaptureMouse(0); }
		lua_pushstring(L, "mouseup");
		lua_pushstring(L, button_name(e.button.button));
		lua_pushnumber(L, e.button.x);
		lua_pushnumber(L, e.button.y);
		return 4;
	case SDL_MOUSEMOTION:
		lua_pushstring(L, "mousemotion");
		int x = e.motion.x;
		int y = e.motion.y;
		int xrel = e.motion.xrel;
		int yrel = e.motion.yrel;
		while (SDL_PeepEvents(&e, 1, SDL_GETEVENT, SDL_MOUSEMOTION, SDL_MOUSEMOTION) > 0) {
			x = e.motion.x;
			y = e.motion.y;
			xrel += e.motion.xrel;
			yrel += e.motion.yrel;
		}
		lua_pushnumber(L, x);
		lua_pushnumber(L, y);
		lua_pushnumber(L, xrel);
		lua_pushnumber(L, yrel);
		return 5;
	case SDL_MOUSEWHEEL:
		lua_pushstring(L, "mousewheel");
		int my = e.wheel.y;
		while (SDL_PeepEvents(&e, 1, SDL_GETEVENT, SDL_MOUSEWHEEL, SDL_MOUSEWHEEL) > 0) {
			my = my + e.wheel.y;
		}
		lua_pushnumber(L, my);
		return 2;
	default:
		goto top;
	}
	return 0;
}
