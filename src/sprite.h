#ifndef SPRITE_H
#define SPRITE_H

#include "cpctelera.h"

// Blit d'sprite [mask,img] per pixel, amb desat/restauracio de fons.
void sprite_blit_bg(const u8* spr, u16 sy, u16 sx, u8 w, u8 h, u8* bg);
void sprite_restore(const u8* bg, u16 sy, u16 sx, u8 w, u8 h);

#endif