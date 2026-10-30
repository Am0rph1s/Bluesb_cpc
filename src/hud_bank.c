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

extern u16 g_vram_start;
extern u8 g_has_instrument;
extern u8 s_invuln_timer;
extern u8 s_dying_timer;
extern u8 s_dazed_timer;

static u8 s_hud_layout[PLAY_CHARS];
// Snapshot GLOBAL del contingut (lives, vinyls, hearts, instrument).
// Nomes cal un: quan canvia, la pagina de torn es reconstrueix i l'altra
// copia d'ella al frame seguent. Amb adreces absolutes el check es ~3 B.
static u8 s_hud_snap[4];
static u16 s_hud_vram_start[2];

static u16 s_cur_off20;
static u16 s_cur_off21;
static u8  s_base_hi;

// Pas A: copia del HUD des de l'altra pagina (resident, sempre mapejat).
extern u8 hud_try_copy(u8 page, u16 src_ma, u16 dst_ma);

static void hud_set_vinyl_digits(u8 val) {
    u8 tens = 9;
    while (val >= 10) {
        val = (u8)(val - 10);
        tens++;
    }
    s_hud_layout[21] = tens;
    s_hud_layout[22] = (u8)(9 + val);
}

static void hud_blit_columns(void) __naked {
    __asm
        push ix
        ; --- 1. Calcular offsets de video per a sy=20 i sy=21 ---
        ld   hl, (_g_vram_start)
        ld   de, #800
        add  hl, de
        ld   a, h
        and  #0x03
        ld   h, a
        add  hl, hl
        ld   (_s_cur_off20), hl
        ld   de, #80
        add  hl, de
        res  3, h
        ld   (_s_cur_off21), hl

        ; --- 2. Bucle de les 40 columnes ---
        ld   ix, #_s_hud_layout
        ld   b, #40
    hb_col_loop$:
        ; HL = strips + tile * 24
        ld   l, 0(ix)
        inc  ix
        ld   h, #0
        add  hl, hl         ; *2
        add  hl, hl         ; *4
        add  hl, hl         ; *8
        ld   e, l
        ld   d, h
        add  hl, hl         ; *16
        add  hl, de         ; *24
        ld   de, (_s_lv + 73) ; s_lv.hud_off
        add  hl, de

        ; --- Row 20 (ra=0..7) ---
        ld   de, (_s_cur_off20)
        ld   a, (_s_base_hi)
        add  a, d
        ld   d, a
        call hb_blit_ff$     ; ra=0 (0xFF)
        call hb_blit_ff$     ; ra=1 (0xFF)
        call hb_blit6$       ; ra=2..7 (6 linies grafics)

        ; --- Row 21 (ra=0..7) ---
        ld   de, (_s_cur_off21)
        ld   a, (_s_base_hi)
        add  a, d
        ld   d, a
        call hb_blit6$       ; ra=0..5 (6 linies grafics)
        call hb_blit_ff$     ; ra=6 (0xFF)
        ; ra=7 (0xFF)
        ld   a, #0xFF
        ld   (de), a
        inc  e
        ld   (de), a

        ; --- Avancar offsets +2 (wrap a 2048 / 0x0800) ---
        ld   hl, (_s_cur_off20)
        inc  hl
        inc  hl
        res  3, h
        ld   (_s_cur_off20), hl

        ld   hl, (_s_cur_off21)
        inc  hl
        inc  hl
        res  3, h
        ld   (_s_cur_off21), hl

        djnz hb_col_loop$
        pop  ix
        ret

    hb_blit_ff$:
        ld   a, #0xFF
        ld   (de), a
        inc  e
        ld   (de), a
        dec  e
        ld   a, d
        add  a, #8
        ld   d, a
        ret

    hb_blit6$:
        ld   c, #6
    hb_blit6_loop$:
        ld   a, (hl)
        inc  hl
        ld   (de), a
        inc  e
        ld   a, (hl)
        inc  hl
        ld   (de), a
        dec  e
        ld   a, d
        add  a, #8
        ld   d, a
        dec  c
        jr   nz, hb_blit6_loop$
        ret
    __endasm;
}

void hud_init_b(void) {
    u8 i;
    u8* p = s_hud_layout;
    for (i = 0; i < PLAY_CHARS; i++) *p++ = 0;
    s_hud_layout[0]  = 1;
    s_hud_layout[1]  = 3;
    s_hud_layout[2]  = 4;
    s_hud_layout[18] = 5;
    s_hud_layout[19] = 6;
    s_hud_layout[39] = 2;
    *(u16*)&s_hud_snap[0] = 0xFFFF;
    *(u16*)&s_hud_snap[2] = 0xFFFF;
    s_hud_vram_start[0] = s_hud_vram_start[1] = 0xFFFF;
}

void hud_render_b(void) {
    u8 page = (u8)bc_a;
    u8 force = (u8)bc_b;
    u8 i;
    u8* p;
    if (!force &&
        s_hud_snap[0] == g_lives_count &&
        s_hud_snap[1] == g_vinyls_count &&
        s_hud_snap[2] == g_hearts_count &&
        s_hud_snap[3] == g_has_instrument) {
        if (s_hud_vram_start[page] == g_vram_start) return;
        // Nomes ha canviat l'offset de l'anell (scroll) i el contingut es el
        // mateix: copiem el HUD de l'altra pagina en lloc de reconstruir-lo.
        if (hud_try_copy(page, s_hud_vram_start[page ^ 1], g_vram_start)) {
            s_hud_vram_start[page] = g_vram_start;
            return;
        }
    }
    s_hud_vram_start[page] = g_vram_start;
    s_hud_snap[0] = g_lives_count;
    s_hud_snap[1] = g_vinyls_count;
    s_hud_snap[2] = g_hearts_count;
    s_hud_snap[3] = g_has_instrument;

    // Vides 1 digit (maxim real 8; clamp defensiu a 9).
    { u8 lv = (g_lives_count > 9) ? 9 : g_lives_count;
      s_hud_layout[4] = (u8)(9 + lv); }
    hud_set_vinyl_digits(g_vinyls_count);
    p = &s_hud_layout[7];
    for (i = 0; i < 5; i++) {
        u8 h0 = (i < g_hearts_count) ? 7 : 0;
        *p++ = h0;
        *p++ = h0 ? 8 : 0;
    }
    // Slots col.leccionables: slot i gris (19+4i,20+4i), color si es el del
    // nivell i ja s'ha recollit (21+4i,22+4i).
    p = &s_hud_layout[24];
    for (i = 0; i < 5; i++) {
        u8 sb = (u8)(19 + (i << 2) + ((i == s_lv.level_id && g_has_instrument) ? 2 : 0));
        *p++ = sb;
        *p++ = (u8)(sb + 1);
    }

    s_base_hi = (page == 0) ? 0xC0 : 0x80;
    hud_blit_columns();
}

// Banner GAME OVER (1:1 DOS): 34 files de 40 bytes sobre el backbuffer.
void gameover_banner_b(void) {
    u8 page = (u8)bc_a;
    u16 vram_base = (page == 0) ? 0xC000 : 0x8000;
    const u8* src = (const u8*)(u16)s_lv.gameover_off;
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
