#ifndef PLAYER_FRAMES_H
#define PLAYER_FRAMES_H

#include "cpctelera.h"

// Frames autèntics de Jake (DOS 16 colors) al Banc 7 - 16 px Mode 0 (8 bytes)
#define PLAYER_FRAMES_BANK 0xC7
#define PLAYER_FRAMES_BASE 0x4000
#define PLAYER_FRAME_SIZE 480
#define PLAYER_FRAMES_COUNT 26

typedef struct { u16 offset; u8 wb; u8 h; } PSprFrame;
static const PSprFrame g_player_frames_r[26] = {
    {     0, 8, 30 }, //  0: idle
    {   480, 8, 30 }, //  1: walk1
    {   960, 8, 30 }, //  2: walk2
    {  1440, 8, 30 }, //  3: walk3
    {  1920, 8, 30 }, //  4: jump
    {  2400, 8, 30 }, //  5: ladder_back
    {  2880, 8, 30 }, //  6: crouch1
    {  3360, 8, 30 }, //  7: crouch2
    {  3840, 8, 30 }, //  8: crouch3
    {  4320, 8, 30 }, //  9: ladder1
    {  4800, 8, 30 }, // 10: ladder2
    {  5280, 8, 30 }, // 11: ladder3
    {  5760, 8, 30 }, // 12: crate_walk1
    {  6240, 8, 30 }, // 13: crate_walk2
    {  6720, 8, 30 }, // 14: crate_walk3
    {  7200, 8, 30 }, // 15: crate_walk4
    {  7680, 8, 30 }, // 16: crate_walk5
    {  8160, 8, 30 }, // 17: crate_lift
    {  8640, 8, 30 }, // 18: crate_throw
    {  9120, 8, 30 }, // 19: crate_push
    {  9600, 8, 30 }, // 20: carry_float
    { 10080, 8, 30 }, // 21: item2
    { 10560, 8, 30 }, // 22: item3
    { 11040, 8, 30 }, // 23: hurt1
    { 11520, 8, 30 }, // 24: hurt2
    { 12000, 8, 30 }, // 25: hurt3
};

#endif
