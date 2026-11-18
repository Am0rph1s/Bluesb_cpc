// ============================================================
// render.c - Wrappers del HUD al Banc 1 (MUSBANK)
// ------------------------------------------------------------
// El render de tiles i d'habitacions (_render_tile_world, _render_all,
// _render_room, _render_column, _render_row) viu en ASM natiu a
// engine/tile_blit.s (0 bytes d'IX stack frame i sense __mulint).
// ============================================================

#include "cpctelera.h"
#include "bank.h"
#include "enemy.h"
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

// El control d'estat (lives/vinyls/hearts/instrument) viu a hud_bank.c
// (C1), que retorna de seguida si no ha canviat res. Aixi el resident no
// duplica els comptadors ni el codi del fast-path.
void hud_render(u8 full_v, u8 force) {
    bc_a = full_v;
    bc_b = force;
    call_banked(0xC0, (void*)hud_render_o);
}

// Restore del mon (enemics/movers) per al scroll. Viu fora de main.c per
// compartir una sola copia entre el cami normal i el diferit.
void restore_world_scroll(u8 mode) {
    if (mode == 0) enemy_restore(0);
    else if (mode == 1) enemy_restore(2);
    moving_restore(0, 0);
    moving_popup_restore(0);
}
