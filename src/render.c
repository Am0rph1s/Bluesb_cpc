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

void hud_init(void) {
    call_banked(0xC0, (void*)hud_init_o);
}

void hud_render(u8 page, u8 force) {
    bc_a = page;
    bc_b = force;
    call_banked(0xC0, (void*)hud_render_o);
}
