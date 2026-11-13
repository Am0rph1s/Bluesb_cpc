#ifndef DISK_TABLES_H
#define DISK_TABLES_H
#include "fdc.h"

#define CRC_FDC 0xBDA6

static const u8 g_front_chs[12] = {
    0x04,0xC5,0x04,0xC6,0x04,0xC7,0x04,0xC8,0x04,0xC9,0x05,0xC1,
};
static const DiskFileDesc g_file_front = { 2608, 6, g_front_chs };
#define CRC_FRONT 0x3AE8

#define CRC_FSPLASH 0x9E30

#define CRC_MUSBANK 0x9EE9

#define CRC_FSELECT 0x9A85

#define CRC_FMAP 0xD62D

static const u8 g_jake_chs[12] = {
    0x0D,0xC4,0x0D,0xC5,0x0D,0xC6,0x0D,0xC7,0x0D,0xC8,0x0D,0xC9,
};
static const DiskFileDesc g_file_jake = { 2949, 6, g_jake_chs };
#define CRC_JAKE 0x98AC

static const u8 g_elwood_chs[12] = {
    0x0E,0xC1,0x0E,0xC2,0x0E,0xC3,0x0E,0xC4,0x0E,0xC5,0x0E,0xC6,
};
static const DiskFileDesc g_file_elwood = { 2851, 6, g_elwood_chs };
#define CRC_ELWOOD 0xD971

#define CRC_L1WORLD 0x45E0

#define CRC_L1ENEMI 0xD4E1

#define CRC_L2WORLD 0x905C

#define CRC_L2ENEMI 0xCE01

#define CRC_L3WORLD 0x30EF

#define CRC_L3ENEMI 0x759B

#define CRC_L3C1 0x8CC0

#define CRC_L4WORLD 0x799F

#define CRC_L4ENEMI 0x6D78

#define CRC_L5WORLD 0x68E4

#define CRC_L5ENEMI 0xA1ED

#define CRC_L5C1 0x758C

#define CRC_L6WORLD 0xDE11

#define CRC_L6ENEMI 0xE9EE

#endif
