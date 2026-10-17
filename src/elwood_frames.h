#ifndef ELWOOD_FRAMES_H
#define ELWOOD_FRAMES_H

#include "cpctelera.h"

// Frames autentics d'Elwood (DOS) - 16 px Mode 0 (8 bytes x 30 = 480 B)
// Banc proposat 0xC3 (lliure), base 0x4000. REVISAR a F0.2.
#define ELWOOD_FRAMES_BANK 0xC3
#define ELWOOD_FRAMES_BASE 0x4000
#define ELWOOD_FRAME_SIZE 480
#define ELWOOD_FRAMES_COUNT 29
// Dansa select (DANCE.BIN, amb FRONT):
#define DANCE_FRAMES_COUNT 20
// 0..5 Jake A (33-38), 6..8 Jake B (21-23),
// 9..13 Elwood A (51,71,72,73,100), 14..19 Elwood B (88,83,84,85,86,87)
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
// 26 (12480): dazed1
// 27 (12960): dazed2
// 28 (13440): dazed3

#endif
