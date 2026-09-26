/*
 * Build compatibility shim for metaparser-js.
 *
 * The minizip glue in this directory (ioapi.h, unzip.c, unpack.c) came from
 * a project that had its own externals.h, utils.h and ints.h. Those headers
 * are not part of this tree, so this file provides exactly what is needed:
 * common standard headers plus the engine functions used by unpack.c
 * (idf_magic, unix_path).
 */
#ifndef MP_COMPAT_EXTERNALS_H
#define MP_COMPAT_EXTERNALS_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <limits.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#include "idf.h"  /* idf_magic() */
#include "util.h" /* unix_path() */

#endif
