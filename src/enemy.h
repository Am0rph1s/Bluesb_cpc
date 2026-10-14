#ifndef ENEMY_H
#define ENEMY_H

#include "cpctelera.h"

// Enemics walkers del nivell 1 (kinds DOS 8/15/19 -> op1): patrulla
// horitzontal + gravetat + gir en paret, 1:1 amb objects.c:op1.
// Tot el modul viu al BANC C6 (frames 0x4000 + codi 0x5200 + dades);
// el resident hi crida via call_banked (slots enemy_table.s) i li
// dona tiles via helpers centrals (CP-2.2: banked no niua).
#define ENEMY_N 9
#define ENEMY_W 16
#define ENEMY_HT 32
#define ENEMY_WB 8
#define ENEMY_FRAME_SIZE 512
#define ENEMY_FRAMES_BASE ((const u8*)0x4000)

void enemy_init(void);
void enemy_update(void);
void enemy_restore(u8 page);
void enemy_draw(u8 page);

#endif
