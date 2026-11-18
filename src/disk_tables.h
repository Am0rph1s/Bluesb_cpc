#ifndef DISK_TABLES_H
#define DISK_TABLES_H
#include "fdc.h"

#define CRC_FDC 0x3472

static const u8 g_front_chs[12] = {
    0x04,0xC5,0x04,0xC6,0x04,0xC7,0x04,0xC8,0x04,0xC9,0x05,0xC1,
};
static const DiskFileDesc g_file_front = { 2608, 6, g_front_chs };
#define CRC_FRONT 0x4E88

#define CRC_FSPLASH 0x9E30

#define CRC_MUSBANK 0xAD69

#define CRC_FSELECT 0x9A85

#define CRC_FMAP 0xD62D

static const u8 g_jake_chs[12] = {
    0x0D,0xC6,0x0D,0xC7,0x0D,0xC8,0x0D,0xC9,0x0E,0xC1,0x0E,0xC2,
};
static const DiskFileDesc g_file_jake = { 2949, 6, g_jake_chs };
#define CRC_JAKE 0x98AC

static const u8 g_elwood_chs[12] = {
    0x0E,0xC3,0x0E,0xC4,0x0E,0xC5,0x0E,0xC6,0x0E,0xC7,0x0E,0xC8,
};
static const DiskFileDesc g_file_elwood = { 2851, 6, g_elwood_chs };
#define CRC_ELWOOD 0xD971

#define CRC_L1WORLD 0xE51B

#define CRC_L1ENEMI 0x8921

#define CRC_L2WORLD 0x0D27

#define CRC_L2ENEMI 0x0C24

#define CRC_L3WORLD 0xBE14

#define CRC_L3ENEMI 0xE03B

#define CRC_L3C1 0x3D25

#define CRC_L4WORLD 0x43E5

#define CRC_L4ENEMI 0x92EB

#define CRC_L5WORLD 0xC85D

#define CRC_L5ENEMI 0x8985

#define CRC_L5C1 0xDFC3

#define CRC_L6WORLD 0xD6C3

#define CRC_L6ENEMI 0x8D13

#endif
