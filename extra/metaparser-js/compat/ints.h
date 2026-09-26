/*
 * Minimal ints.h in the spirit of minizip-ng: the integer types ioapi.h
 * expects (typedef ui64_t ZPOS64_T).
 */
#ifndef MP_COMPAT_INTS_H
#define MP_COMPAT_INTS_H

#include <stdint.h>

typedef uint8_t ui8_t;
typedef uint16_t ui16_t;
typedef uint32_t ui32_t;
typedef uint64_t ui64_t;

#endif
