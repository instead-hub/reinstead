LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE := main

SDL_PATH := ../SDL

LOCAL_C_INCLUDES := $(LOCAL_PATH)/$(SDL_PATH)/include $(LOCAL_PATH)/reinstead/src/lua $(LOCAL_PATH)/reinstead/src/instead
LOCAL_CFLAGS = -Dmain=SDL_main
# Add your application source files here...
SRC := instead/cache.c instead/idf.c instead/instead.c instead/lfs.c \
	instead/list.c instead/tinymt32.c instead/util.c \
	lua/lapi.c lua/lauxlib.c lua/lbaselib.c lua/lcode.c \
	lua/lcorolib.c lua/lctype.c lua/ldblib.c lua/ldebug.c \
	lua/ldo.c lua/ldump.c lua/lfunc.c lua/lgc.c lua/linit.c \
	lua/liolib.c lua/llex.c lua/lmathlib.c lua/lmem.c lua/loadlib.c \
	lua/lobject.c lua/lopcodes.c lua/loslib.c lua/lparser.c lua/lstate.c \
	lua/lstring.c lua/lstrlib.c lua/ltable.c lua/ltablib.c lua/ltm.c \
	lua/lundump.c lua/lutf8lib.c lua/lvm.c lua/lzio.c gfx.c instead_lib.c lua-compat.c \
	main.c platform.c stb_image.c stb_image_resize.c stb_truetype.c system.c

LOCAL_SRC_FILES = $(patsubst %,reinstead/src/%, $(SRC))
LOCAL_SHARED_LIBRARIES := SDL2

LOCAL_LDLIBS := -lGLESv1_CM -lGLESv2 -llog

include $(BUILD_SHARED_LIBRARY)
