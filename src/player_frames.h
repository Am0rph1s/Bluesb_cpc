#ifndef PLAYER_FRAMES_H
#define PLAYER_FRAMES_H

#include "cpctelera.h"

// Jake frames reside in bank 7; the blitter reads them while mapped.
#define PLAYER_FRAMES_BANK 0xC7
#define PLAYER_FRAMES_BASE 0x4000
#define PLAYER_FRAME_SIZE 360

typedef struct { u16 offset; u8 wb; u8 h; } PSprFrame;
static const PSprFrame g_player_frames_r[4] = {
    { 0, 6, 30 },
    { 360, 6, 30 },
    { 720, 6, 30 },
    { 1080, 6, 30 },
};

static const PSprFrame g_player_frames_l[4] = {
    { 1440, 6, 30 },
    { 1800, 6, 30 },
    { 2160, 6, 30 },
    { 2520, 6, 30 },
};

#endif
