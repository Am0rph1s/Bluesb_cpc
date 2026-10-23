// ============================================================
// hud_bank.c - HUD i banner de GAME OVER, al Banc 1 compartit (MUSBANK)
// ------------------------------------------------------------
// Aquest codi ESCRIVIU A LA VRAM (pagina 0 o 1). Per la regla de maquinari
// (ESTAT, sessio 36) el codi que escriu a VRAM ha de viure a la RAM 1 i
// cridar-se amb 0xC0 mapejat: per tant NO fa cap bank_set() (el wrapper
// resident ja deixa 0xC0 posat).
//
// Viu dins MUSBANK.BIN (C1, carregat pel FRONT abans del nivell) a partir de
// 0x4C00, per sobre del player AKG (0x4000-0x4BFF) i per sota de la canco
// del nivell (0x5000): no el trepitja cap carrega de nivell.
//
// Els simbols residents (g_vram_start, g_lives_count...) els resol el link
// amb obj/bank_equ.rel (com level_code.c).
// ============================================================
#include "cpctelera.h"
#include "moving.h"
#include "level_params.h"

#define PLAY_CHARS 40
#define GAMEOVER_PTR ((const u8*)0x5800)

extern const u8 s_hud_strips[39][24];
extern void hud_blit_col(const u8* strip24, u16 ma20);
extern u16 g_vram_start;
extern u8 g_has_instrument;
// Dany d'àcid kind=10 (tiles.c:907-919 + level.c:1583-1593). Viu aquí (C1
// compartit, amb marge) perquè el resident va just; el C5 el crida via el
// wrapper resident acid_hurt() (mateix patró que hud_render_b: vy per bc_a).
extern u8 s_invuln_timer;
extern u8 s_dying_timer;
extern u8 s_dazed_timer;

static u8 s_hud_layout[PLAY_CHARS];
static u8 s_hud_lives[2], s_hud_vinyls[2], s_hud_hearts[2], s_hud_inst[2];
static u16 s_hud_vram_start[2];

static void hud_set_digits(u8 col, u8 val) {
    u8 tens = 9;
    while (val >= 10) {
        val = (u8)(val - 10);
        tens++;
    }
    s_hud_layout[col] = tens;
    s_hud_layout[(u8)(col + 1)] = (u8)(9 + val);
}

void hud_init_b(void) {
    u8 i;
    for (i = 0; i < PLAY_CHARS; i++) s_hud_layout[i] = 0;
    s_hud_layout[0]  = 1;
    s_hud_layout[1]  = 3;
    s_hud_layout[2]  = 4;
    s_hud_layout[18] = 5;
    s_hud_layout[19] = 6;
    s_hud_layout[39] = 2;
    s_hud_lives[0] = s_hud_lives[1] = 0xFF;
    s_hud_vinyls[0] = s_hud_vinyls[1] = 0xFF;
    s_hud_hearts[0] = s_hud_hearts[1] = 0xFF;
    s_hud_inst[0] = s_hud_inst[1] = 0xFF;
    s_hud_vram_start[0] = s_hud_vram_start[1] = 0xFFFF;
}

void hud_render_b(void) {
    u8 page = (u8)bc_a;
    u8 force = (u8)bc_b;
    u8 cx, i;
    u16 ma;
    if (!force &&
        s_hud_vram_start[page] == g_vram_start &&
        s_hud_lives[page] == g_lives_count &&
        s_hud_vinyls[page] == g_vinyls_count &&
        s_hud_hearts[page] == g_hearts_count &&
        s_hud_inst[page] == g_has_instrument) {
        return;
    }
    s_hud_vram_start[page] = g_vram_start;
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
        u8 sb = (u8)(19 + (i << 2) + ((i == s_lv.level_id && g_has_instrument) ? 2 : 0));
        s_hud_layout[(u8)(24 + (i << 1))] = sb;
        s_hud_layout[(u8)(25 + (i << 1))] = (u8)(sb + 1);
    }

    ma = (u16)((g_vram_start + 800) & 0x03FF);
    for (cx = 0; cx < PLAY_CHARS; cx++) {
        hud_blit_col(s_hud_strips[s_hud_layout[cx]], ma);
        ma = (u16)((ma + 1) & 0x03FF);
    }
}

// Banner GAME OVER (1:1 DOS): 34 files de 40 bytes sobre el backbuffer.
void gameover_banner_b(void) {
    u8 page = (u8)bc_a;
    u16 vram_base = (page == 0) ? 0xC000 : 0x8000;
    const u8* src = GAMEOVER_PTR;
    u8 y;
    for (y = 0; y < 34; y++) {
        u8 r_char = (u8)(10 + (y >> 3));
        u16 r_line_hi = (u16)((y & 7) << 11);
        u16 ma_row = (u16)((g_vram_start + (u16)r_char * 40) & 0x03FF);
        u16 ma_start = (u16)((ma_row + 10) & 0x03FF);
        if (ma_start <= 1004) {
            u8* dst = (u8*)(vram_base | r_line_hi | (ma_start << 1));
            cpct_memcpy(dst, src, 40);
        } else {
            u16 chars1 = 1024 - ma_start;
            u16 bytes1 = chars1 << 1;
            u8* dst1 = (u8*)(vram_base | r_line_hi | (ma_start << 1));
            u8* dst2 = (u8*)(vram_base | r_line_hi);
            cpct_memcpy(dst1, src, bytes1);
            cpct_memcpy(dst2, src + bytes1, (u16)(40 - bytes1));
        }
        src += 40;
    }
}

// Dany d'àcid kind=10, b6=2/3/4 (1:1 DOS tiles.c:907-919: yfriction 14/10/5,
// xvelocity=-100, special_anim=22 + SOUND_11; level.c:1583-1593: -1 cor,
// blinking_counter=75). vy = -yfric*4 (enemy.c:685: 12 -> -48).
void acid_hurt_b(void) {
    i16 vy = (i16)bc_a;
    if (s_invuln_timer || s_dying_timer) return;
    if (g_hearts_count > 0) g_hearts_count--;
    s_invuln_timer = 75;
    s_vy = vy;
    s_on_ground = 0;
    if (g_hearts_count == 0) {
        s_dying_timer = 64;
        s_dazed_timer = 0;
        s_invuln_timer = 255;
    } else {
        s_dazed_timer = 20;
    }
}
