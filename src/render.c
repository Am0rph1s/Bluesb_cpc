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
extern void hud_blit_col(const u8* strip24, u16 ma20);

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

// Repinta un tile animat de 8x16 del mapa, només els caràcters CRTC de 4x8
// que cauen dins el viewport actual. Això manté el ring circular lliure de wraps.
void render_tile_world(u8 tile_index, u16 col, u16 row,
                       u16 cam_x4, u16 cam_row) {
    u16 cx = (u16)(col << 1);
    u16 cy = (u16)(row << 1);
    i16 sx = (i16)cx - (i16)cam_x4;
    i16 sy = (i16)cy - (i16)cam_row;
    u8 prev_b, sub;

    prev_b = bank_set(0xC4);
    for (sub = 0; sub < 2; sub++) {
        if (sy >= 0 && sy < PLAY_ROWS) {
            u16 ma = (u16)(((cy * 40) + cx) & 0x03FF);
            if (sx >= 0 && sx < PLAY_CHARS) {
                draw_char(tile_index, ma, sub, 0);
            }
            if ((sx + 1) >= 0 && (sx + 1) < PLAY_CHARS) {
                draw_char(tile_index, (u16)((ma + 1) & 0x03FF), sub, 1);
            }
        }
        sy++;
        cy++;
    }
    bank_restore(prev_b);
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
    u16 base_col = (u16)(room_idx * 20);
    u16 cam_x4 = (u16)(room_idx * 40);
    for (r = 0; r < 10; r++) {
        u16 r_off = (u16)r * 100 + base_col;
        for (c = 0; c < 20; c++) {
            u8 prev_b = bank_set(0xC1);
            u8 t = ((const u8*)0x6400)[r_off + c];
            bank_restore(prev_b);
            render_tile_world(t, (u16)(base_col + c), (u16)(74 + r), cam_x4, 148);
        }
    }
}


