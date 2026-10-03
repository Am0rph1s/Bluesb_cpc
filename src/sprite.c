// ============================================================
// sprite.c - Blit d'sprite Mode 0 amb mascara + desat de fons
// ------------------------------------------------------------
// Els sprites estan en FORMAT DE BYTES DE VRAM (Mode 0): cada element
// [mask, img] es UN BYTE de pantalla (= 2 pixels). w = bytes per linia.
//   VRAM_byte = (VRAM_byte & ~mask) | (img & mask)
// El blit desa el fons anterior per restaurar-lo el frame seguent.
// ============================================================

#include "cpctelera.h"
#include "sprite.h"

// Adreca VRAM del byte (byte_x, line_y). byte_x: 0..79, line_y: 0..199.
static u8* b_addr(u16 y, u16 byte_x) {
    if (y > 199) y = 199;
    if (byte_x > 79) byte_x = 79;
    return (u8*)(0xC000 | (((y & 7) << 11) + (y >> 3) * 80 + byte_x));
}

// Dibuixa l'sprite (spr = [mask,img] per byte de VRAM, w bytes x h linies)
// a (sy,sx) en BYTES de pantalla. Guarda el fons a bg (w bytes/linia).
void sprite_blit_bg(const u8* spr, u16 sy, u16 sx, u8 w, u8 h, u8* bg) {
    u8 ly, b;
    for (ly = 0; ly < h; ly++) {
        for (b = 0; b < w; b++) {
            u8* a = b_addr((u16)(sy + ly), (u16)(sx + b));
            const u8* p = spr + (((u16)ly * w + b) << 1);
            u8 m = p[0];
            u8 i = p[1];
            bg[(u16)ly * w + b] = *a;
            *a = (u8)((*a & (u8)~m) | (i & m));
        }
    }
}

void sprite_restore(const u8* bg, u16 sy, u16 sx, u8 w, u8 h) {
    u8 ly, b;
    for (ly = 0; ly < h; ly++) {
        for (b = 0; b < w; b++) {
            *b_addr((u16)(sy + ly), (u16)(sx + b)) = bg[(u16)ly * w + b];
        }
    }
}