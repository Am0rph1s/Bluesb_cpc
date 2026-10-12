#ifndef PLAYER_FRAMES_H
#define PLAYER_FRAMES_H

#include "cpctelera.h"

// Frames autèntics de Jake (DOS 16 colors) al Banc 7 - 16 px Mode 0 (8 bytes x 30 = 480 B)
#define PLAYER_FRAMES_BANK 0xC7
#define PLAYER_FRAMES_BASE 0x4000
#define PLAYER_FRAME_SIZE 480
#define PLAYER_FRAMES_COUNT 26
//  0 (    0): idle
//  1 (  480): walk1
//  2 (  960): walk2
//  3 ( 1440): walk3
//  4 ( 1920): jump
//  5 ( 2400): ladder_back
//  6 ( 2880): crouch1
//  7 ( 3360): crouch2
//  8 ( 3840): crouch3
//  9 ( 4320): ladder1
// 10 ( 4800): dance1
// 11 ( 5280): dance2
// 12 ( 5760): crate_walk1
// 13 ( 6240): crate_walk2
// 14 ( 6720): crate_walk3
// 15 ( 7200): crate_walk4
// 16 ( 7680): crate_walk5
// 17 ( 8160): crate_lift
// 18 ( 8640): crate_throw
// 19 ( 9120): crate_push
// 20 ( 9600): carry_float
// 21 (10080): swim_idle
// 22 (10560): swim_stroke1
// 23 (11040): swim_stroke2
// 24 (11520): swim_vert
// 25 (12000): swim_floor

#endif
