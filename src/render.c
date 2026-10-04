// ============================================================
// render.c - Render del nivell en Mode 0 (Double Buffer 128 KB)
// ------------------------------------------------------------
// Dibuixa l'àrea visible (20x20 subtiles = 160x160 px) al backbuffer actiu.
// Les dades de TILES viuen al Banc 4 (0xC4 a 0x4000).
// Les dades de MAP viuen al Banc 5 (0xC5 a 0x4000).
// ============================================================

#include "cpctelera.h"

#define TILESET    ((const u8*)0x4000)
#define GMAP       ((const u8*)0x4000)

#define LEVEL_W    128
#define PLAY_COLS  20
#define PLAY_ROWS  20

extern u8* g_backbuffer;

void render_all(u16 cam_col, u16 cam_row) {
    u16 sx, sy;
    u8* vram = g_backbuffer;

    for (sx = 0; sx < PLAY_COLS; sx++) {
        u16 scol = (u16)(cam_col + sx);
        for (sy = 0; sy < PLAY_ROWS; sy++) {
            u16 srow = (u16)(cam_row + sy);
            u16 trow = (u16)(srow >> 1);
            u16 sub_off = (u16)((srow & 1) << 5);
            u8* dst = vram + sy * 80 + (sx << 2);
            u8 b;
            const u8* t;
            u8 j;

            // Llegir índex de tile des del Banc 5
            cpc_bank_set(0xC5);
            b = GMAP[(trow << 7) + scol];

            // Llegir gràfic del tile des del Banc 4
            cpc_bank_set(0xC4);
            t = TILESET + (((u16)b) << 6) + sub_off;

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
    cpc_bank_restore();
}

void render_column(u16 cam_col, u16 cam_row, u16 sx) {
    (void)cam_col; (void)cam_row; (void)sx;
}

void render_row(u16 cam_col, u16 cam_row, u16 sy) {
    (void)cam_col; (void)cam_row; (void)sy;
}

void scroll_set(u16 word_off) { (void)word_off; }
u16  scroll_get(void)         { return 0; }