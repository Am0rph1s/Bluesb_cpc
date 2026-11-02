#ifndef DISK_TABLES_H
#define DISK_TABLES_H
#include "fdc.h"

#define CRC_FDC 0xF0D1

static const u8 g_front_chs[12] = {
    0x04,0xC7,0x04,0xC8,0x04,0xC9,0x05,0xC1,0x05,0xC2,0x05,0xC3,
};
static const DiskFileDesc g_file_front = { 2448, 6, g_front_chs };
#define CRC_FRONT 0x3E4F

#define CRC_FSPLASH 0xD44F

#define CRC_MUSBANK 0xA03F

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

#define CRC_L1WORLD 0xD86E

#define CRC_L1ENEMI 0x3FA5

#define CRC_L2WORLD 0xF043

#define CRC_L2ENEMI 0x65A5

#define CRC_L3WORLD 0xFD23

#define CRC_L3ENEMI 0xCCCB

#define CRC_L3C1 0xAE67

#define CRC_L4WORLD 0x32F1

#define CRC_L4ENEMI 0xE8B0

#define CRC_L5WORLD 0xA1E7

#define CRC_L5ENEMI 0x7591

#define CRC_L5C1 0x7EA0

#define CRC_L6WORLD 0xCF41

#define CRC_L6ENEMI 0xD499

#endif
