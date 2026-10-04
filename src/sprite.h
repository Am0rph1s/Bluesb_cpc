#ifndef SPRITE_H
#define SPRITE_H

#include "cpctelera.h"

// Variables globals d'sprite
extern u8 g_spr_y;
extern u8 g_spr_x;
extern u8 g_spr_flip;
extern u8 g_vram_base_hi;

// Rutines ASM Z80
void sprite_blit_player(const u8* spr);
void sprite_restore_player(void);
void cpc_wait_vsync_start(void);
void scroll_shift_left_4(void);
void scroll_shift_right_4(void);
void scroll_shift_up_8(void);
void scroll_shift_down_8(void);

#endif