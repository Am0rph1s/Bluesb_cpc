// ============================================================
// render.c - Wrappers del HUD al Banc 1 (MUSBANK)
// ------------------------------------------------------------
// El render de tiles i d'habitacions (_render_tile_world, _render_all,
// _render_room, _render_column, _render_row) viu en ASM natiu a
// engine/tile_blit.s (0 bytes d'IX stack frame i sense __mulint).
// ============================================================

#include "cpctelera.h"
#include "bank.h"
#include "moving.h"

u16 g_render_tile_offset;

// HUD: el codi viu al Banc 1 COMPARTIT (MUSBANK, src/hud_bank.c) perque
// escriu a la VRAM. Les adreces son EQUs generats per build_music
// (obj/hud_ext.s), no constants al resident.
extern void hud_init_o(void);
extern void hud_render_o(void);
extern void ram2_hud_copy(u8 full_v);
extern u8 g_lives_count, g_vinyls_count, g_hearts_count, g_has_instrument;

static u8 s_hud_ok;
static u8 s_hlives, s_hvinyls, s_hhearts, s_hinst;

void hud_init(void) {
    s_hud_ok = 0;
    call_banked(0xC0, (void*)hud_init_o);
}

void hud_render(u8 page, u8 force) {
    if (s_hud_ok &&
        s_hlives == g_lives_count &&
        s_hvinyls == g_vinyls_count &&
        s_hhearts == g_hearts_count &&
        s_hinst == g_has_instrument) {
        if (!force && !page) return;
        ram2_hud_copy(page);
        return;
    }
    bc_a = page;
    bc_b = force;
    call_banked(0xC0, (void*)hud_render_o);
    s_hud_ok = 1;
    s_hlives = g_lives_count;
    s_hvinyls = g_vinyls_count;
    s_hhearts = g_hearts_count;
    s_hinst = g_has_instrument;
}
