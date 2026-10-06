#ifndef SPRITE_HFLIP_H
#define SPRITE_HFLIP_H

#include "cpctelera.h"

extern u8 g_hflip_lut_hi;

// Inicialitza la taula LUT (ha d'estar alineada a 256 bytes, p.ex. a 0x7F00 al Banc 7)
void sprite_hflip_init_lut(u8* lut_256_aligned);

// Inverteix un frame d'en Jake de 360 bytes en Mode 0
void sprite_hflip(const u8* src, u8* dst);

#endif
