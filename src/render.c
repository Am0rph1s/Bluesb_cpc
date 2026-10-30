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

// Tires del HUD al banc C1/C0 a 0x6000 (carregades amb MUSMAIN.BIN):
// 936 B fora del Bloc 0. Visibles en C0 (sense tocar Banc 7 ni buffers d'sprites).
extern const u8 s_hud_strips[39][24];

#define LEVEL_PKG_DEFS_ONLY
#include "level_pkg.h"
#include "level_params.h"

#define TILESET    ((const u8*)0x4000)
#define GMAP       ((const u8*)0x4000)

#define PLAY_CHARS 40
#define PLAY_ROWS  20

extern void render_tile_fast(const u8* tile);

u16 g_render_tile_offset;

// HUD: el codi viu al Banc 1 COMPARTIT (MUSBANK, src/hud_bank.c) perque
// escriu a la VRAM. Les adreces son EQUs generats per build_music
// (obj/hud_ext.s), no constants al resident.
extern void hud_init_o(void);
extern void hud_render_o(void);

void hud_init(void) {
    call_banked(0xC0, (void*)hud_init_o);
}

void hud_render(u8 page, u8 force) {
    bc_a = page;
    bc_b = force;
    call_banked(0xC0, (void*)hud_render_o);
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

// Repinta un SPAN de tiles animats (mateixa fila, col_start..col_end) amb
// UNA sola commutacio al Banc 4. Abans (P1b) cada columna feia el seu
// bank_set/bank_restore; ara es fa un unicament per span (4-6 columnes).
// El punter al tile es calcula un sol cop i el MA s'incrementa de 40 per
// subfila en lloc de multiplicar.
void render_tile_span(u8 tile_index, u16 col_start, u16 col_end, u16 row,
                      u16 cam_x4, u16 cam_row) {
    const u8* tp = TILESET + ((u16)tile_index << 6);
    u16 col;
    u8 prev_b;

    prev_b = bank_set(0xC4);
    for (col = col_start; col <= col_end; col++) {
        u16 cx = (u16)(col << 1);
        u16 ma = (u16)(((((u16)row << 1) * 40) + cx) & 0x03FF);
        i16 sx = (i16)cx - (i16)cam_x4;
        i16 sy = (i16)((u16)(row << 1)) - (i16)cam_row;
        u8 sub;
        for (sub = 0; sub < 2; sub++) {
            if (sy >= 0 && sy < PLAY_ROWS) {
                const u8* t = tp + (u16)(sub << 5);
                if (sx >= 0 && sx < PLAY_CHARS) {
                    g_render_tile_offset = (u16)(ma << 1);
                    render_tile_fast(t);
                }
                if ((sx + 1) >= 0 && (sx + 1) < PLAY_CHARS) {
                    g_render_tile_offset = (u16)(((ma + 1) & 0x03FF) << 1);
                    render_tile_fast((const u8*)(t + 2));
                }
            }
            sy++;
            ma = (u16)((ma + 40) & 0x03FF);
        }
    }
    bank_restore(prev_b);
}

// Repinta un sol tile animat (repintats puntuals de main.c / render_room).
void render_tile_world(u8 tile_index, u16 col, u16 row,
                       u16 cam_x4, u16 cam_row) {
    render_tile_span(tile_index, col, col, row, cam_x4, cam_row);
}

extern void render_column(u16 cam_x4, u16 cam_row, u16 sx);

void render_all(u16 cam_x4, u16 cam_row) {
    u16 sx;
    for (sx = 0; sx < PLAY_CHARS; sx++) {
        render_column(cam_x4, cam_row, sx);
    }
}

void render_room(u8 room_idx) {
    u8 r, c;
    u16 base_col = (u16)(room_idx * s_lv.room_cols);
    u16 cam_x4 = (u16)(room_idx * ((u16)s_lv.room_cols << 1));
    for (r = 0; r < 10; r++) {
        u16 r_off = (u16)(s_lv.room_rowoff[r] + base_col);
        for (c = 0; c < s_lv.room_cols; c++) {
            u8 prev_b = bank_set(0xC5);
            u8 t = ((const u8*)(u16)s_lv.rooms_off)[r_off + c];
            bank_restore(prev_b);
            render_tile_world(t, (u16)(base_col + c),
                              (u16)(s_lv.room_row0 + r), cam_x4,
                              s_lv.room_cam_row);
        }
    }
}


