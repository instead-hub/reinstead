#include "platform_sdl.h"
#include "external.h"
#include "platform.h"

#ifdef __ANDROID__
#include <jni.h>
#include <android/log.h>
#define LOG(s) do { __android_log_print(ANDROID_LOG_VERBOSE, "reinstead", "%s", s); } while(0)
#else
#define LOG(s) do { printf("%s\n", (s)); } while(0)
#endif

static void
tolow(char *p)
{
	while (*p) {
		if (*p >=  'A' && *p <= 'Z')
			*p |= 0x20;
		p ++;
	}
}

void
Log(const char *msg)
{
	LOG(msg);
}

double
Time(void)
{
	return SDL_GetPerformanceCounter() / (double) SDL_GetPerformanceFrequency();
}

void
Delay(float n)
{
	SDL_Delay(n * 1000);
}

static char*
key_name(int sym)
{
	static char dst[32];
	const char *name = SDL_GetScancodeName(sym);
	snprintf(dst, sizeof(dst), "%s", name ? name : "");
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

const char *
GetPlatform(void)
{
	return SDL_GetPlatform();
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
	if (len < 0)
		len = 0;
	path[len] = 0;
#else
	strncpy(path, progname, sizeof(path));
#endif
	path[sizeof(path) - 1] = 0;
	return path;
}

#ifdef _WIN32
static HINSTANCE user32_lib;
static HINSTANCE tolk;
static void (*Tolk_Load)() = NULL;
static void (*Tolk_Unload)() = NULL;
static void (*Tolk_TrySAPI)(int trySAPI) = NULL;
static int (*Tolk_Output)(const wchar_t *str, int interrupt) = NULL;
static wchar_t *(*Tolk_DetectScreenReader)() = NULL;
static int Tolk_IsReader = 0;
#endif

static void
plat_tolk_init(void)
{
#ifdef _WIN32
	int (*SetProcessDPIAware)();
	tolk = LoadLibrary("Tolk.dll");
	if (tolk) {
		Tolk_Load = (void*) GetProcAddress(tolk, "Tolk_Load");
		Tolk_Unload = (void*) GetProcAddress(tolk, "Tolk_Unlad");
		Tolk_TrySAPI = (void*) GetProcAddress(tolk, "Tolk_TrySAPI");
		Tolk_Output = (void*) GetProcAddress(tolk, "Tolk_Output");
		Tolk_DetectScreenReader = (void*) GetProcAddress(tolk, "Tolk_DetectScreenReader");
		if (Tolk_TrySAPI)
			Tolk_TrySAPI(0);
		if (Tolk_Load)
			Tolk_Load();
		if (Tolk_DetectScreenReader)
			Tolk_IsReader = !!Tolk_DetectScreenReader();
		if (!Tolk_IsReader && Tolk_TrySAPI)
			Tolk_TrySAPI(1);
	}
	user32_lib = LoadLibrary("user32.dll");
	SetProcessDPIAware = (void*) GetProcAddress(user32_lib, "SetProcessDPIAware");
	if (SetProcessDPIAware)
		SetProcessDPIAware();
	LoadLibrary("Tolk.dll");
#endif
}

static void
plat_tolk_done(void)
{
#ifdef _WIN32
	if (user32_lib)
		FreeLibrary(user32_lib);
	if (tolk) {
		if (Tolk_Unload)
			Tolk_Unload();
		FreeLibrary(tolk);
	}
#endif
}

#ifdef __ANDROID__
void
Speak(const char *text)
{
	JNIEnv *env = (JNIEnv*)SDL_ANDROID_JNI_ENV();
	jobject activity = (jobject)SDL_ANDROID_ACTIVITY();
	jclass cl = (*env)->GetObjectClass(env, activity);
	jmethodID mid = (*env)->GetStaticMethodID(env, cl, "speak", "(Ljava/lang/String;)V");
	jstring jtxt = (*env)->NewStringUTF(env, text);
	(*env)->CallStaticVoidMethod(env, cl, mid, jtxt);
	(*env)->DeleteLocalRef(env, jtxt);
	(*env)->DeleteLocalRef(env, cl);
	(*env)->DeleteLocalRef(env, activity);
}

int isSpeak()
{
	jboolean retval;
	JNIEnv *env = (JNIEnv*)SDL_ANDROID_JNI_ENV();
	jobject activity = (jobject)SDL_ANDROID_ACTIVITY();
	jclass cl = (*env)->GetObjectClass(env, activity);
	jmethodID mid = (*env)->GetStaticMethodID(env, cl, "isSpeak", "()Z");
	retval = (*env)->CallStaticBooleanMethod(env, cl, mid);
	(*env)->DeleteLocalRef(env, cl);
	(*env)->DeleteLocalRef(env, activity);
	return (retval == JNI_TRUE) ? 1 : 0;
}
#else
void
Speak(const char *text)
{
#ifdef _WIN32
	wchar_t* wstr;
	int len;
	if (!Tolk_Output)
		return;
	len = MultiByteToWideChar(CP_UTF8, 0, text, -1, NULL ,0);
	if (len <= 0)
		return;
	wstr = malloc(len * sizeof(wchar_t));
	if (!wstr)
		return;
	MultiByteToWideChar(CP_UTF8, 0, text, -1, wstr, len);
	Tolk_Output(wstr, 1);
	free(wstr);
#endif
#if defined(__linux__)
	pid_t pid;
	pid = fork();
	if (pid != 0)
		return;
	if (*text)
		execlp("spd-say", "spd-say", "-C", "--wait", text, NULL);
	else
		execlp("spd-say", "spd-say", "-C", NULL);
	exit(0);
#endif
}
int isSpeak()
{
#ifdef _WIN32
	if (Tolk_IsReader)
		return 1;
#endif
#if defined(__linux)
/*	if (getenv("ACCESSIBILITY_ENABLED"))
		return 1; */
#endif
	return 0;
}
#endif

#ifdef USE_SDL3
#include "sdl3/platform.c"
#else
#include "sdl2/platform.c"
#endif
