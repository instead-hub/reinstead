#ifndef __PLATFORM_SDL_H
#define __PLATFORM_SDL_H

#ifdef USE_SDL3
# if defined(__has_include) && __has_include(<SDL3/SDL.h>)
#  include <SDL3/SDL.h>
# else
#  include <SDL.h>
# endif
#else
# include <SDL.h>
#endif

#ifdef USE_SDL3
# define SDL_ANDROID_JNI_ENV() SDL_GetAndroidJNIEnv()
# define SDL_ANDROID_ACTIVITY() SDL_GetAndroidActivity()
# define SDL_ANDROID_INTERNAL_STORAGE() SDL_GetAndroidInternalStoragePath()
#else
# define SDL_ANDROID_JNI_ENV() SDL_AndroidGetJNIEnv()
# define SDL_ANDROID_ACTIVITY() SDL_AndroidGetActivity()
# define SDL_ANDROID_INTERNAL_STORAGE() SDL_AndroidGetInternalStoragePath()
#endif

#endif
