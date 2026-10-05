#ifndef PLAYER_FRAMES_H
#define PLAYER_FRAMES_H

#include "cpctelera.h"

// Jake frames reside in bank 7; the blitter reads them while mapped.
#define PLAYER_FRAMES_BANK 0xC7
#define PLAYER_FRAMES_BASE 0x4000
#define PLAYER_FRAME_SIZE 720

typedef struct { u16 offset; u8 wb; u8 h; } PSprFrame;
static const PSprFrame g_player_frames_r[4] = {
    { 0, 12, 30 },
    { 720, 12, 30 },
    { 1440, 12, 30 },
    { 2160, 12, 30 },
};

static const PSprFrame g_player_frames_l[4] = {
    { 2880, 12, 30 },
    { 3600, 12, 30 },
    { 4320, 12, 30 },
    { 5040, 12, 30 },
};

#endif
