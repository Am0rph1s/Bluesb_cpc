// ============================================================
// render.c - Render del nivell en Mode 0 (Double Buffer 128 KB)
// ------------------------------------------------------------
// Dibuixa l'àrea visible (40 caràcters × 20 files = 160x160 px) al ring actiu.
// Les dades de TILES viuen al Banc 4 (0xC4 a 0x4000).
// Les dades de MAP viuen al Banc 5 (0xC5 a 0x4000).
// ============================================================

#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"
#include "hud_pkg.h"

#define LEVEL_PKG_DEFS_ONLY
#include "level_pkg.h"

#define TILESET    ((const u8*)0x4000)
#define GMAP       ((const u8*)0x4000)

#define PLAY_CHARS 40
#define PLAY_ROWS  20

extern void render_tile_fast(const u8* tile);
extern void hud_blit_col(const u8* strip24, u16 ma20);

u16 g_render_tile_offset;

static u8 s_hud_layout[PLAY_CHARS];
static u8 s_hud_lives[2];
static u8 s_hud_vinyls[2];
static u8 s_hud_hearts[2];
static u8 s_hud_inst[2];

static void hud_set_digits(u8 col, u8 val) {
    u8 tens = 9;
    while (val >= 10) {
        val = (u8)(val - 10);
        tens++;
    }
    s_hud_layout[col] = tens;
    s_hud_layout[(u8)(col + 1)] = (u8)(9 + val);
}

void hud_init(void) {
    u8 i;
    for (i = 0; i < PLAY_CHARS; i++) s_hud_layout[i] = 0;
    s_hud_layout[0]  = 1;
    s_hud_layout[1]  = 3;
    s_hud_layout[2]  = 4;
    s_hud_layout[18] = 5;
    s_hud_layout[19] = 6;
    s_hud_layout[39] = 2;
    s_hud_lives[0] = s_hud_lives[1] = 0xFF;
}

void hud_render(u8 page, u8 force) {
    u8 cx, i;
    u16 ma;
    if (!force &&
        s_hud_lives[page] == g_lives_count &&
        s_hud_vinyls[page] == g_vinyls_count &&
        s_hud_hearts[page] == g_hearts_count &&
        s_hud_inst[page] == g_has_instrument) {
        return;
    }
    s_hud_lives[page]  = g_lives_count;
    s_hud_vinyls[page] = g_vinyls_count;
    s_hud_hearts[page] = g_hearts_count;
    s_hud_inst[page]   = g_has_instrument;

    // Vides 1 digit (maxim real 8; clamp defensiu a 9).
    { u8 lv = (g_lives_count > 9) ? 9 : g_lives_count;
      s_hud_layout[4] = (u8)(9 + lv); }
    hud_set_digits(21, g_vinyls_count);
    for (i = 0; i < 5; i++) {
        u8 c = (u8)(7 + (i << 1));
        u8 h0 = (i < g_hearts_count) ? 7 : 0;
        s_hud_layout[c] = h0;
        s_hud_layout[(u8)(c + 1)] = h0 ? 8 : 0;
    }
    // Slots col.leccionables: slot i gris (19+4i,20+4i), color si es el del
    // nivell i ja s'ha recollit (21+4i,22+4i).
    for (i = 0; i < 5; i++) {
        u8 sb = (u8)(19 + (i << 2) + ((i == LEVEL_ID && g_has_instrument) ? 2 : 0));
        s_hud_layout[(u8)(24 + (i << 1))] = sb;
        s_hud_layout[(u8)(25 + (i << 1))] = (u8)(sb + 1);
    }

    ma = (u16)((g_vram_start + 800) & 0x03FF);
    for (cx = 0; cx < PLAY_CHARS; cx++) {
        hud_blit_col(s_hud_strips[s_hud_layout[cx]], ma);
        ma = (u16)((ma + 1) & 0x03FF);
    }
}

static void draw_char(u8 tile_index, u16 ma, u8 tile_half_y, u8 tile_half_x) {
    u16 tile_subrow;
    const u8* tile;

    tile_subrow = (u16)((tile_half_y << 5) + (tile_half_x << 1));
    tile = TILESET + (tile_index << 6) + tile_subrow;

    // Un caràcter CRTC conté 2 bytes: mitja amplada del subtile de 8 píxels.
    g_render_tile_offset = (u16)(ma << 1);
    render_tile_fast(tile);
}

// Repinta un tile animat de 8x16 del mapa, només els caràcters CRTC de 4x8
// que cauen dins el viewport actual. Això manté el ring circular lliure de wraps.
void render_tile_world(u8 tile_index, u16 col, u16 row,
                       u16 cam_x4, u16 cam_row) {
    u16 cx = (u16)(col << 1);
    u16 cy = (u16)(row << 1);
    u16 ma;
    i16 sx, sy;
    u8 prev_b;

    prev_b = bank_set(0xC4);

    sy = (i16)cy - (i16)cam_row;
    sx = (i16)cx - (i16)cam_x4;

    // Subrow 0 (meitat superior del tile)
    if (sy >= 0 && sy < PLAY_ROWS) {
        ma = (u16)(((cy * 40) + cx) & 0x03FF);
        if (sx >= 0 && sx < PLAY_CHARS) {
            draw_char(tile_index, ma, 0, 0);
        }
        if ((sx + 1) >= 0 && (sx + 1) < PLAY_CHARS) {
            draw_char(tile_index, (u16)((ma + 1) & 0x03FF), 0, 1);
        }
    }

    // Subrow 1 (meitat inferior del tile)
    sy++;
    cy++;
    if (sy >= 0 && sy < PLAY_ROWS) {
        ma = (u16)(((cy * 40) + cx) & 0x03FF);
        if (sx >= 0 && sx < PLAY_CHARS) {
            draw_char(tile_index, ma, 1, 0);
        }
        if ((sx + 1) >= 0 && (sx + 1) < PLAY_CHARS) {
            draw_char(tile_index, (u16)((ma + 1) & 0x03FF), 1, 1);
        }
    }

    bank_restore(prev_b);
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
