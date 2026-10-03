// ============================================================
// render.c - Render del nivell en Mode 0
// ------------------------------------------------------------
// Dibuixa l'area visible (20x20 subtiles = 160x160 px) a 0xC000 amb
// l'adreçament interleaved estandard del CPC:
//   addr = 0xC000 | ((y&7)<<11) | ((y>>3)*80 + x)
// El scroll (de moment) es fa re-renderitzant el viewport quan la camera
// es mou. El display start del CRTC queda fix a 0.
// ============================================================

#include "cpctelera.h"

#define VRAM       ((u8*)0xC000)
#define TILESET    ((const u8*)0x3600)
#define GMAP       ((const u8*)0x7600)

#define LEVEL_W    128
#define PLAY_COLS  20
#define PLAY_ROWS  20

static const u8* subtile_ptr(u16 scol, u16 srow) {
    u16 trow = (u16)(srow >> 1);
    u16 sub  = (u16)(srow & 1);
    u8  b    = GMAP[trow * LEVEL_W + scol];
    u16 num  = (u16)(b & 0x7F);
    u16 half = (u16)(b >> 7);
    return (const u8*)(TILESET + ((half * 128 + num) << 6) + (sub << 5));
}

static void draw_sub(const u8* t, u16 sy, u16 sx) {
    u16 j, k;
    for (j = 0; j < 8; j++) {
        u16 y = (u16)(sy * 8 + j);
        u16 a = (u16)(((y & 7) << 11) + (y >> 3) * 80 + sx * 4);
        for (k = 0; k < 4; k++) VRAM[a + k] = t[j * 4 + k];
    }
}

void render_all(u16 cam_col, u16 cam_row) {
    u16 sy, sx;
    for (sy = 0; sy < PLAY_ROWS; sy++)
        for (sx = 0; sx < PLAY_COLS; sx++)
            draw_sub(subtile_ptr((u16)(cam_col + sx), (u16)(cam_row + sy)), sy, sx);
}

void render_column(u16 cam_col, u16 cam_row, u16 sx) {
    u16 ry;
    for (ry = 0; ry < PLAY_ROWS; ry++)
        draw_sub(subtile_ptr((u16)(cam_col + sx), (u16)(cam_row + ry)), ry, sx);
}

void render_row(u16 cam_col, u16 cam_row, u16 sy) {
    u16 sx;
    for (sx = 0; sx < PLAY_COLS; sx++)
        draw_sub(subtile_ptr((u16)(cam_col + sx), (u16)(cam_row + sy)), sy, sx);
}

void scroll_set(u16 word_off) { (void)word_off; }
u16  scroll_get(void)         { return 0; }