#ifndef SPRITE_H
#define SPRITE_H

#include "cpctelera.h"

// Variables globals d'sprite
extern u8 g_spr_y;
extern u8 g_spr_x;
extern u8 g_vram_base_hi;
extern u16 g_vram_start;

// Rutines ASM Z80
void sprite_blit_player(const u8* spr);
void sprite_restore_player(void);
void sprite_balloon_init(void);
void sprite_blit_balloon(void);
void sprite_restore_balloon(void);
void sprite_blit_umbrella(void);
void sprite_restore_umbrella(void);
void sprite_abort_balloon(void);
void cpc_wait_vsync_start(void);
void sprite_hflip_init_lut(u8* lut_256_aligned);
void sprite_hflip(const u8* src, u8* dst);

// Reixa Mode 0 (Magasin)
extern u8 g_grate_enable;
extern u8 g_grate_phase_x;
extern u8 g_grate_base_y;

#endif

