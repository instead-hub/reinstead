static int destroyed = 0;
static SDL_Window *window = NULL;
static SDL_Renderer *renderer = NULL;
static SDL_Texture *texture = NULL;
static int renderer_soft = 0;

void
TextInput(void)
{
	SDL_StartTextInput(window);
}

void
WindowMode(int n)
{
	SDL_SetWindowFullscreen(window, n == WIN_FULLSCREEN);
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

static int
WaitEventTo(int timeout)
{
	Uint64 expiration = 0;

	if (timeout > 0)
		expiration = SDL_GetTicks() + timeout;

	for (;;) {
		SDL_PumpEvents();
		switch (SDL_PeepEvents(NULL, 1, SDL_GETEVENT, SDL_EVENT_FIRST, SDL_EVENT_LAST)) {
		case -1:
			return 0;
		case 0:
			if (timeout == 0)
				return 0;
			if (timeout > 0 && SDL_GetTicks() >= expiration)
				return 0;
			SDL_Delay(10); /* 1/100 sec */
			break;
		default:
			/* Has events */
			return 1;
		}
	}
}

int
WaitEvent(float n)
{
	return WaitEventTo((int)(n * 1000));
}

float
GetScale(void)
{
	float scale = SDL_GetDisplayContentScale(SDL_GetPrimaryDisplay());
	if (scale <= 0.0f)
		return 1.0f;
	return scale;
}

int
PlatformInit(void)
{
	plat_tolk_init();
	if (!SDL_Init(SDL_INIT_VIDEO))
		return -1;
	return 0;
}

static SDL_Surface *winbuff = NULL;

void
PlatformDone(void)
{
	plat_tolk_done();
	if (winbuff)
		SDL_DestroySurface(winbuff);
	if (texture)
		SDL_DestroyTexture(texture);
	if (renderer)
		SDL_DestroyRenderer(renderer);
	SDL_DestroyWindow(window);
	SDL_Quit();
#ifdef __ANDROID__
	_exit(0);
#endif
}

int
WindowCreate(void)
{
	const SDL_DisplayMode *mode;
	const char *name;

	mode = SDL_GetCurrentDisplayMode(SDL_GetPrimaryDisplay());
	if (!mode)
		return -1;
	if (!SDL_CreateWindowAndRenderer("reinstead", mode->w * 0.5, mode->h * 0.8,
		SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY, &window, &renderer))
		return -1;
#ifndef __ANDROID__
	SDL_StartTextInput(window);
#endif
	name = SDL_GetRendererName(renderer);
	renderer_soft = name && !strcmp(name, SDL_SOFTWARE_RENDERER);
	SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_NONE);
	return 0;
}

void
WindowResize(int w, int h)
{
	if (winbuff)
		SDL_DestroySurface(winbuff);
	winbuff = NULL;
	if (texture)
		SDL_DestroyTexture(texture);
	texture = NULL;
	destroyed = 1;
}

void
WindowUpdate(int x, int y, int w, int h)
{
	SDL_Rect rect;
	int pitch, psize;
	unsigned char *pixels;
	if (!winbuff || !texture)
		return;
	pitch = winbuff->pitch;
	psize = SDL_BYTESPERPIXEL(winbuff->format);
	pixels = winbuff->pixels;
	if (!renderer_soft)
	    w = -1;
	if (w > 0 && h > 0) {
		SDL_FRect frect;
		rect.x = x;
		rect.y = y;
		rect.w = w;
		rect.h = h;
		SDL_RectToFRect(&rect, &frect);
		pixels += pitch * y + x * psize;
		SDL_UpdateTexture(texture, &rect, pixels, pitch);
		SDL_RenderTexture(renderer, texture, &frect, &frect);
	} else {
		SDL_UpdateTexture(texture, NULL, pixels, pitch);
		SDL_RenderClear(renderer);
		SDL_RenderTexture(renderer, texture, NULL, NULL);
		if (destroyed) { /* problem with double buffering */
			SDL_RenderPresent(renderer);
			SDL_UpdateTexture(texture, NULL, pixels, pitch);
			SDL_RenderClear(renderer);
			SDL_RenderTexture(renderer, texture, NULL, NULL);
		}
	}
	SDL_RenderPresent(renderer);
	destroyed = 0;
}

void
Icon(unsigned char *ptr, int w, int h)
{
	SDL_Surface *surf;
	surf = SDL_CreateSurfaceFrom(w, h, SDL_PIXELFORMAT_ABGR8888, ptr, w * 4);
	if (!surf)
		return;
	SDL_SetWindowIcon(window, surf);
	SDL_DestroySurface(surf);
	return;
}

unsigned char *
WindowPixels(int *w, int *h)
{
	SDL_GetWindowSizeInPixels(window, w, h);
	if (winbuff && (winbuff->w != *w || winbuff->h != *h)) {
		SDL_DestroySurface(winbuff);
		winbuff = NULL;
		if (texture)
			SDL_DestroyTexture(texture);
		texture = NULL;
		destroyed = 1;
	}
	if (!winbuff)
		winbuff = SDL_CreateSurface(*w, *h, SDL_PIXELFORMAT_ABGR8888);
	if (!winbuff)
		return NULL;
	if (!texture) {
		texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888,
			SDL_TEXTUREACCESS_STREAMING, *w, *h);
		if (texture)
			SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_NONE);
	}

	return (unsigned char*)winbuff->pixels;
}

#ifdef __ANDROID__
static char edit_str[1024] = {0};
#endif

int
sys_poll(lua_State *L)
{
	SDL_Event e;
#ifdef __linux__
	pid_t pid;
	while ((pid = waitpid(-1, NULL, WNOHANG)) > 0);
#endif
top:
	if (!SDL_PollEvent(&e))
		return 0;

	switch (e.type) {
	case SDL_EVENT_DID_ENTER_BACKGROUND:
		lua_pushstring(L, "save");
		return 1;
	case SDL_EVENT_QUIT:
		lua_pushstring(L, "quit");
		return 1;
	case SDL_EVENT_DID_ENTER_FOREGROUND:
		lua_pushstring(L, "exposed");
		destroyed = 1;
		return 1;
	case SDL_EVENT_WINDOW_RESIZED:
	case SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED:
		lua_pushstring(L, "resized");
		lua_pushnumber(L, e.window.data1);
		lua_pushnumber(L, e.window.data2);
		WindowResize(e.window.data1, e.window.data2);
		return 3;
	case SDL_EVENT_WINDOW_EXPOSED:
	case SDL_EVENT_WINDOW_RESTORED:
		lua_pushstring(L, "exposed");
		return 1;
	case SDL_EVENT_WINDOW_FOCUS_GAINED:
		/* on some systems, when alt-tabbing to the window SDL will queue up
		** several KEYDOWN events for the `tab` key; we flush all keydown
		** events on focus so these are discarded */
		SDL_FlushEvent(SDL_EVENT_KEY_DOWN);
		SDL_FlushEvent(SDL_EVENT_KEY_UP);
		goto top;
	case SDL_EVENT_KEY_DOWN:
		lua_pushstring(L, "keydown");
		lua_pushstring(L, key_name(e.key.scancode));
		return 2;
	case SDL_EVENT_KEY_UP:
		lua_pushstring(L, "keyup");
		lua_pushstring(L, key_name(e.key.scancode));
		return 2;
	case SDL_EVENT_TEXT_INPUT:
		lua_pushstring(L, "text");
		lua_pushstring(L, e.text.text);
		return 2;
#ifdef __ANDROID__
	case SDL_EVENT_TEXT_EDITING:
		if (e.edit.text && e.edit.text[0] &&
			e.edit.text[strlen(e.edit.text) - 1] == '\001') { /* more */
			strncat(edit_str, e.edit.text,
				sizeof(edit_str) - strlen(edit_str) - 2);
			edit_str[strlen(edit_str) - 1] = 0;
			goto top;
		}
		strncat(edit_str, e.edit.text ? e.edit.text : "",
			sizeof(edit_str) - strlen(edit_str) - 1);
		lua_pushstring(L, "edit");
		lua_pushstring(L, edit_str);
		edit_str[0] = 0;
		return 2;
#endif
	case SDL_EVENT_MOUSE_BUTTON_DOWN:
		if (e.button.button == 1) { SDL_CaptureMouse(true); }
		lua_pushstring(L, "mousedown");
		lua_pushstring(L, button_name(e.button.button));
		lua_pushnumber(L, e.button.x);
		lua_pushnumber(L, e.button.y);
		lua_pushnumber(L, e.button.clicks);
		return 5;
	case SDL_EVENT_MOUSE_BUTTON_UP:
		if (e.button.button == 1) { SDL_CaptureMouse(false); }
		lua_pushstring(L, "mouseup");
		lua_pushstring(L, button_name(e.button.button));
		lua_pushnumber(L, e.button.x);
		lua_pushnumber(L, e.button.y);
		return 4;
	case SDL_EVENT_MOUSE_MOTION:
		lua_pushstring(L, "mousemotion");
		float x = e.motion.x;
		float y = e.motion.y;
		float xrel = e.motion.xrel;
		float yrel = e.motion.yrel;
		while (SDL_PeepEvents(&e, 1, SDL_GETEVENT, SDL_EVENT_MOUSE_MOTION, SDL_EVENT_MOUSE_MOTION) > 0) {
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
	case SDL_EVENT_MOUSE_WHEEL:
		lua_pushstring(L, "mousewheel");
		float my = e.wheel.y;
		while (SDL_PeepEvents(&e, 1, SDL_GETEVENT, SDL_EVENT_MOUSE_WHEEL, SDL_EVENT_MOUSE_WHEEL) > 0) {
			my = my + e.wheel.y;
		}
		lua_pushnumber(L, my);
		return 2;
	default:
		goto top;
	}
	return 0;
}
