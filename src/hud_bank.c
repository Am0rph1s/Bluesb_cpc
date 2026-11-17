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
static u8 s_hud_lives, s_hud_vinyls, s_hud_hearts, s_hud_inst;
static u16 s_hud_vram_start;
extern void ram2_hud_copy(u8 full_v);

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
        ld   hl, #0x8760    ; VRAM fixa del HUD a RAM 2 (MA = 0x23B0)
        push hl             ; (SP) = cur20
        ld   ix, #_s_hud_layout
        ld   b, #40
    hb_col_loop$:
        ld   l, 0(ix)
        inc  ix
        ld   c, #0x7F
        pop  de
        push de
        push bc
        call hb_draw_one$
        pop  bc
        pop  hl
        inc  hl
        inc  hl
        push hl
        djnz hb_col_loop$
        pop  hl
        pop  ix
        ret

        ; --- Dibuixa 1 columna (DE = cur20, L = tile, C = 0x7F/0xFF) ---
    hb_draw_one$:
        push de             ; guarda cur20
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
        pop  de
        push de             ; DE = cur20
        bit  7, c
        jr   nz, hb_r20_skip_ff$
        ld   a, #0xFF       ; ra=0..1 inline
        ld   (de), a
        inc  e
        ld   (de), a
        set  3, d
        ld   (de), a
        dec  e
        ld   (de), a
    hb_r20_skip_ff$:
        res  3, d
        set  4, d           ; RA=2 directament
        call hb_blit6$      ; ra=2..7 (LDI no toca B ni bit 7 de C)

        ; --- Row 21 (ra=0..7) ---
        pop  de             ; DE = cur20 (neta pila)
        ex   de, hl         ; HL = cur20, DE = strip_ptr+12
        push de
        ld   de, #80
        add  hl, de
        res  3, h
        ex   de, hl         ; DE = cur21
        pop  hl             ; HL = strip_ptr+12
        call hb_blit6$      ; ra=0..5 (deixa DE a RA=6)
        bit  7, c
        ret  nz
        ld   a, #0xFF       ; ra=6..7 inline
        ld   (de), a
        inc  e
        ld   (de), a
        set  3, d
        ld   (de), a
        dec  e
        ld   (de), a
        ret

    hb_blit6$:
        ld   a, #3
    hb_blit6_loop$:
        push af
        ; Linia parella (RA+0):
        ldi
        ld   a, (hl)
        inc  hl
        ld   (de), a
        ; Linia imparella (RA+1):
        set  3, d
        dec  e
        ldi
        ld   a, (hl)
        inc  hl
        ld   (de), a
        dec  e
        ld   a, d
        add  a, #8
        ld   d, a
        pop  af
        dec  a
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
    s_hud_lives = s_hud_vinyls = s_hud_hearts = s_hud_inst = 0xFF;
    s_hud_vram_start = 0xFFFF;
}

void hud_render_b(void) {
    u8 force = (u8)bc_b;
    u8 full_v = (u8)bc_a;
    u8 stats_same = (u8)(s_hud_lives == g_lives_count &&
                         s_hud_vinyls == g_vinyls_count &&
                         s_hud_hearts == g_hearts_count &&
                         s_hud_inst == g_has_instrument);
    u8 first = (u8)(s_hud_vram_start == 0xFFFF);
    u8 i;
    u8* p;
    if (!force && !first && stats_same) {
        return;
    }
    s_hud_vram_start = 0;

    if (!stats_same || first) {
        s_hud_lives  = g_lives_count;
        s_hud_vinyls = g_vinyls_count;
        s_hud_hearts = g_hearts_count;
        s_hud_inst   = g_has_instrument;

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
        hud_blit_columns();
        full_v = 1;
    }

    ram2_hud_copy(full_v);
}

// Banner GAME OVER (1:1 DOS): 34 files de 40 bytes sobre la pantalla 0xC000.
void gameover_banner_b(void) {
    const u8* src = (const u8*)(u16)s_lv.gameover_off;
    u8 y, k;
    for (y = 0; y < 34; y++) {
        u16 ma = (u16)((g_vram_start + (u16)(10 + (y >> 3)) * 40 + 10) & 0x03FF);
        u16 r_hi = (u16)(0xC000 | ((u16)(y & 7) << 11));
        for (k = 0; k < 20; k++) {
            u8* dst = (u8*)(r_hi | (ma << 1));
            *dst++ = *src++;
            *dst = *src++;
            ma = (u16)((ma + 1) & 0x03FF);
        }
    }
}

// Dany d'acid kind=10, b6=2/3/4 (1:1 DOS tiles.c:907-919: yfriction 14/10/5,
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
