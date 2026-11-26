#ifndef DISK_TABLES_H
#define DISK_TABLES_H
#include "fdc.h"

#define CRC_FDC 0x13CB

static const u8 g_front_chs[12] = {
    0x04,0xC5,0x04,0xC6,0x04,0xC7,0x04,0xC8,0x04,0xC9,0x05,0xC1,
};
static const DiskFileDesc g_file_front = { 2608, 6, g_front_chs };
#define CRC_FRONT 0x9D27

#define CRC_FSPLASH 0x9E30

#define CRC_MUSBANK 0x775D

#define CRC_FSELECT 0x9A85

#define CRC_FMAP 0xD62D

static const u8 g_jake_chs[12] = {
    0x0D,0xC4,0x0D,0xC5,0x0D,0xC6,0x0D,0xC7,0x0D,0xC8,0x0D,0xC9,
};
static const DiskFileDesc g_file_jake = { 3038, 6, g_jake_chs };
#define CRC_JAKE 0x5B3F

static const u8 g_elwood_chs[12] = {
    0x0E,0xC1,0x0E,0xC2,0x0E,0xC3,0x0E,0xC4,0x0E,0xC5,0x0E,0xC6,
};
static const DiskFileDesc g_file_elwood = { 2940, 6, g_elwood_chs };
#define CRC_ELWOOD 0xF6CE

#define CRC_L1WORLD 0x46C3

#define CRC_L1ENEMI 0xE80E

#define CRC_L2WORLD 0x8F41

#define CRC_L2ENEMI 0x7973

#define CRC_L3WORLD 0x323F

#define CRC_L3ENEMI 0x03AA

#define CRC_L3C1 0x0972

#define CRC_L4WORLD 0xC310

#define CRC_L4ENEMI 0xC701

#define CRC_L5WORLD 0xE6B6

#define CRC_L5ENEMI 0xFD21

#define CRC_L5C1 0x7CB4

#define CRC_L6WORLD 0x5FA2

#define CRC_L6ENEMI 0x686E

#endif
