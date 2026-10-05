// ============================================================
// render.c - Render del nivell en Mode 0 (Double Buffer 128 KB)
// ------------------------------------------------------------
// Dibuixa l'àrea visible (40 caràcters × 20 files = 160x160 px) al ring actiu.
// Les dades de TILES viuen al Banc 4 (0xC4 a 0x4000).
// Les dades de MAP viuen al Banc 5 (0xC5 a 0x4000).
// ============================================================

#include "cpctelera.h"

#define TILESET    ((const u8*)0x4000)
#define GMAP       ((const u8*)0x4000)

#define PLAY_CHARS 40
#define PLAY_ROWS  20

extern void render_tile_fast(const u8* tile);

u16 g_render_tile_offset;

static void draw_char(u8 tile_index, u16 ma, u8 tile_half_y, u8 tile_half_x) {
    u16 tile_subrow;
    const u8* tile;

    tile_subrow = (u16)((tile_half_y << 5) + (tile_half_x << 1));
    tile = TILESET + (tile_index << 6) + tile_subrow;

    // Un caràcter CRTC conté 2 bytes: mitja amplada del subtile de 8 píxels.
    g_render_tile_offset = (u16)(ma << 1);
    render_tile_fast(tile);
}

// Llegeix una tira de 4 px: un caràcter CRTC d'ample per cada fila de tile.
static void render_map_char_column(u16 cam_x4, u16 cam_row, u16 screen_char) {
    u8 tile_ids[PLAY_ROWS];
    u16 sy;
    u16 ma;
    u16 world_char_x = (u16)(cam_x4 + screen_char);
    u16 map_col = (u16)(world_char_x >> 1);
    u8 tile_half_x = (u8)(world_char_x & 1);

    cpc_bank_set(0xC5);
    for (sy = 0; sy < PLAY_ROWS; sy++) {
        u16 world_subrow = (u16)(cam_row + sy);
        u16 map_row = (u16)(world_subrow >> 1);
        if (map_col < 128 && map_row < 72)
            tile_ids[sy] = GMAP[(map_row << 7) + map_col];
        else
            tile_ids[sy] = 0;
    }

    cpc_bank_set(0xC4);
    ma = (u16)(((cam_row * 40) + world_char_x) & 0x03FF);
    for (sy = 0; sy < PLAY_ROWS; sy++) {
        draw_char(tile_ids[sy], ma, (u8)((cam_row + sy) & 1), tile_half_x);
        ma = (u16)((ma + 40) & 0x03FF);
    }
}

void render_all(u16 cam_x4, u16 cam_row) {
    u16 sx;

    for (sx = 0; sx < PLAY_CHARS; sx++) {
        render_map_char_column(cam_x4, cam_row, sx);
    }
    cpc_bank_restore();
}

void render_column(u16 cam_x4, u16 cam_row, u16 sx) {
    if (sx >= PLAY_CHARS) return;
    render_map_char_column(cam_x4, cam_row, sx);
    cpc_bank_restore();
}

void render_row(u16 cam_x4, u16 cam_row, u16 sy) {
    u16 sx;
    u16 world_subrow;
    u16 map_row;
    u8 tile_half_y;
    u8 tile_ids[PLAY_CHARS];

    if (sy >= PLAY_ROWS) return;

    world_subrow = (u16)(cam_row + sy);
    map_row = (u16)(world_subrow >> 1);
    tile_half_y = (u8)(world_subrow & 1);
    world_subrow = (u16)(((world_subrow * 40) + cam_x4) & 0x03FF);

    cpc_bank_set(0xC5);
    for (sx = 0; sx < PLAY_CHARS; sx++) {
        u16 world_char_x = (u16)(cam_x4 + sx);
        u16 map_col = (u16)(world_char_x >> 1);
        if (map_col < 128 && map_row < 72)
            tile_ids[sx] = GMAP[(map_row << 7) + map_col];
        else
            tile_ids[sx] = 0;
    }

    cpc_bank_set(0xC4);
    for (sx = 0; sx < PLAY_CHARS; sx++) {
        draw_char(tile_ids[sx], world_subrow, tile_half_y,
                  (u8)((cam_x4 + sx) & 1));
        world_subrow = (u16)((world_subrow + 1) & 0x03FF);
    }
    cpc_bank_restore();
}
