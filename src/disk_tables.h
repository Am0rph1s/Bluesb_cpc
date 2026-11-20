#ifndef DISK_TABLES_H
#define DISK_TABLES_H
#include "fdc.h"

#define CRC_FDC 0xBDA6

static const u8 g_front_chs[12] = {
    0x04,0xC5,0x04,0xC6,0x04,0xC7,0x04,0xC8,0x04,0xC9,0x05,0xC1,
};
static const DiskFileDesc g_file_front = { 2608, 6, g_front_chs };
#define CRC_FRONT 0xD06F

#define CRC_FSPLASH 0x9E30

#define CRC_MUSBANK 0xE7B8

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

#define CRC_L1WORLD 0xF9D5

#define CRC_L1ENEMI 0x0D9B

#define CRC_L2WORLD 0x3924

#define CRC_L2ENEMI 0xCE01

#define CRC_L3WORLD 0x8455

#define CRC_L3ENEMI 0x759B

#define CRC_L3C1 0x8CC0

#define CRC_L4WORLD 0xC960

#define CRC_L4ENEMI 0x6D78

#define CRC_L5WORLD 0x78D8

#define CRC_L5ENEMI 0xDFFB

#define CRC_L5C1 0x60EA

#define CRC_L6WORLD 0x0193

#define CRC_L6ENEMI 0x033F

#endif
