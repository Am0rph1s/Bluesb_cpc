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

#define PLAY_COLS  20
#define PLAY_ROWS  20

extern void render_tile_fast(const u8* tile);

u16 g_render_tile_offset;

static void draw_subtile(u8 tile_index, u16 ma, u8 tile_half) {
    u16 tile_subrow;
    const u8* tile;

    tile_subrow = (u16)(tile_half << 5);
    tile = TILESET + (tile_index << 6) + tile_subrow;

    // Cada tile ocupa 2 paraules CRTC d'ample i una fila de caràcter d'alt.
    g_render_tile_offset = (u16)(ma << 1);
    render_tile_fast(tile);
}

// Llegeix una columna del mapa amb el Banc 5 actiu i la dibuixa amb el Banc 4.
// Així cada tira només commuta banc dues vegades, no dues vegades per tile.
static void render_map_column(u16 map_col, u16 cam_row) {
    u8 tile_ids[PLAY_ROWS];
    u16 sy;
    u16 ma;

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
    ma = (u16)(((cam_row * 40) + (map_col << 1)) & 0x03FF);
    for (sy = 0; sy < PLAY_ROWS; sy++) {
        draw_subtile(tile_ids[sy], ma, (u8)((cam_row + sy) & 1));
        ma = (u16)((ma + 40) & 0x03FF);
    }
}

void render_all(u16 cam_col, u16 cam_row) {
    u16 sx;

    for (sx = 0; sx < PLAY_COLS; sx++) {
        render_map_column((u16)(cam_col + sx), cam_row);
    }
    cpc_bank_restore();
}

void render_column(u16 cam_col, u16 cam_row, u16 sx) {
    u16 world_col;

    if (sx >= PLAY_COLS) return;
    world_col = (u16)(cam_col + sx);
    render_map_column(world_col, cam_row);
    cpc_bank_restore();
}

void render_row(u16 cam_col, u16 cam_row, u16 sy) {
    u16 sx;
    u16 world_subrow;
    u16 map_row;
    u8 tile_half;
    u8 tile_ids[PLAY_COLS];

    if (sy >= PLAY_ROWS) return;

    world_subrow = (u16)(cam_row + sy);
    map_row = (u16)(world_subrow >> 1);
    tile_half = (u8)(world_subrow & 1);
    world_subrow = (u16)(((world_subrow * 40) + (cam_col << 1)) & 0x03FF);

    cpc_bank_set(0xC5);
    for (sx = 0; sx < PLAY_COLS; sx++) {
        u16 map_col = (u16)(cam_col + sx);
        if (map_col < 128 && map_row < 72)
            tile_ids[sx] = GMAP[(map_row << 7) + map_col];
        else
            tile_ids[sx] = 0;
    }

    cpc_bank_set(0xC4);
    for (sx = 0; sx < PLAY_COLS; sx++) {
        draw_subtile(tile_ids[sx], world_subrow, tile_half);
        world_subrow = (u16)((world_subrow + 2) & 0x03FF);
    }
    cpc_bank_restore();
}
