#ifndef DISK_TABLES_H
#define DISK_TABLES_H
#include "fdc.h"

#define CRC_FDC 0xF0D1

static const u8 g_front_chs[12] = {
    0x04,0xC7,0x04,0xC8,0x04,0xC9,0x05,0xC1,0x05,0xC2,0x05,0xC3,
};
static const DiskFileDesc g_file_front = { 2448, 6, g_front_chs };
#define CRC_FRONT 0x3DE8

#define CRC_FSPLASH 0xD44F

#define CRC_MUSBANK 0x744C

#define CRC_FSELECT 0x9A85

#define CRC_FMAP 0x0D21

static const u8 g_jake_chs[16] = {
    0x0D,0xC6,0x0D,0xC7,0x0D,0xC8,0x0D,0xC9,0x0E,0xC1,0x0E,0xC2,
    0x0E,0xC3,0x0E,0xC4,
};
static const DiskFileDesc g_file_jake = { 3132, 8, g_jake_chs };
#define CRC_JAKE 0x26D5

static const u8 g_elwood_chs[12] = {
    0x0E,0xC5,0x0E,0xC6,0x0E,0xC7,0x0E,0xC8,0x0E,0xC9,0x0F,0xC1,
};
static const DiskFileDesc g_file_elwood = { 2818, 6, g_elwood_chs };
#define CRC_ELWOOD 0x98D2

#define CRC_L1WORLD 0x8EA2

#define CRC_L1ENEMI 0x6571

#define CRC_L2WORLD 0xEB2F

#define CRC_L2ENEMI 0x43FA

#define CRC_L3WORLD 0xB35C

#define CRC_L3ENEMI 0x9B97

#define CRC_L3C1 0xFE58

#define CRC_L4WORLD 0xD8EE

#define CRC_L4ENEMI 0x54F3

#define CRC_L5WORLD 0x434F

#define CRC_L5ENEMI 0xD0D7

#define CRC_L5C1 0xE735

#define CRC_L6WORLD 0xB77F

#define CRC_L6ENEMI 0xD8AD

#endif
