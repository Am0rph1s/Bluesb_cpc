// ============================================================
// render.c - Render del nivell en Mode 0 (optimitzat)
// ------------------------------------------------------------
// Dibuixa l'area visible (20x20 subtiles = 160x160 px) a 0xC000.
// Adreçament de VRAM interleaved CPC:
//   base linia 0 subtile: VRAM + sy * 80
//   cada linia dins del subtile: + 0x0800
// ============================================================

#include "cpctelera.h"

#define VRAM       ((u8*)0xC000)
#define TILESET    ((const u8*)0x3600)
#define GMAP       ((const u8*)0x7600)

#define LEVEL_W    128
#define PLAY_COLS  20
#define PLAY_ROWS  20

void render_column(u16 cam_col, u16 cam_row, u16 sx) {
    u16 sy;
    u16 scol = (u16)(cam_col + sx);
    for (sy = 0; sy < PLAY_ROWS; sy++) {
        u16 srow = (u16)(cam_row + sy);
        u16 trow = (u16)(srow >> 1);
        const u8* map_ptr = GMAP + (trow << 7) + scol;
        u16 sub_off = (u16)((srow & 1) << 5);
        u8* dst = VRAM + sy * 80 + (sx << 2);
        u8 b = *map_ptr;
        const u8* t = TILESET + (((u16)b) << 6) + sub_off;
        u8 j;
        for (j = 0; j < 8; j++) {
            dst[0] = t[0];
            dst[1] = t[1];
            dst[2] = t[2];
            dst[3] = t[3];
            t += 4;
            dst += 0x0800;
        }
    }
}

void render_lateral(u16 cam_col, u16 cam_row, i8 dir) {
    u8 step, i;
    if (dir >= 0) {
        // Desplaçament lateral d'esquerra a dreta (4 passos de 5 columnes)
        for (step = 0; step < 4; step++) {
            cpct_waitVSYNC();
            for (i = 0; i < 5; i++) {
                render_column(cam_col, cam_row, (u16)(step * 5 + i));
            }
        }
    } else {
        // Desplaçament lateral de dreta a esquerra (4 passos de 5 columnes)
        for (step = 0; step < 4; step++) {
            cpct_waitVSYNC();
            for (i = 0; i < 5; i++) {
                render_column(cam_col, cam_row, (u16)(19 - (step * 5 + i)));
            }
        }
    }
}

void render_all(u16 cam_col, u16 cam_row) {
    u16 sx;
    for (sx = 0; sx < PLAY_COLS; sx++) {
        render_column(cam_col, cam_row, sx);
    }
}

void scroll_set(u16 word_off) { (void)word_off; }
u16  scroll_get(void)         { return 0; }