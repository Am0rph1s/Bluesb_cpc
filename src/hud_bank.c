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
extern volatile u8 g_mus_hold;
extern volatile u8 g_mus_ready;
extern void mus_stop(void);

// Layout fix del HUD i signatures. S'inicialitzen a hud_init_b (la imatge
// del banc 1 no te crt0 que copiï inicialitzadors de SDCC).
static u8 s_hud_layout[PLAY_CHARS];
// Signatura dels valors que influeixen al HUD (vides 0-3, vinils 4-10,
// cors 11-13, instrument 14). 0xFFFF = pagina sense HUD valid.
static u16 s_hud_sig[2];
static u16 s_hud_vram_start[2];

static u16 s_cur_off20;
static u16 s_cur_off21;
static u8  s_base_hi;

static u16 hud_sig(void) {
    return (u16)(g_lives_count & 0x07)
         | ((u16)(g_vinyls_count & 0x7F) << 3)
         | ((u16)(g_hearts_count & 0x07) << 10)
         | ((u16)(g_has_instrument & 0x07) << 13);
}

// Crida la copia del HUD al banc C6 (slot 6, dispatcher _bc_b=0xA5).
// DE = arg empaquetat (base de la pagina font | offset en paraules).
static void hud_copy_call(u16 arg) __naked {
    __asm
        push ix
        push hl
        pop ix
        ld   a, #0xA5
        ld   (_bc_b), a
        ld   a, #0xC6
        ld   de, #0x5A12
        call _call_banked
        pop  ix
        ret
    __endasm;
}

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
        ; Afegeix directament la base de VRAM (0xC0 o 0x80)
        ld   a, (_s_base_hi)
        add  a, h
        ld   h, a
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
        call hb_blit_ff2$    ; ra=0..1 (0xFF)
        call hb_blit6$       ; ra=2..7 (6 linies grafics)

        ; --- Row 21 (ra=0..7) ---
        ld   de, (_s_cur_off21)
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

    hb_blit_ff2$:
        call hb_blit_ff$
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
        ld   c, #3
    hb_blit6_loop$:
        ; Linia A:
        ld   a, (hl)
        inc  hl
        ld   (de), a
        inc  e
        ld   a, (hl)
        inc  hl
        ld   (de), a
        dec  e
        set  3, d
        ; Linia B:
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
    s_hud_sig[0] = s_hud_sig[1] = 0xFFFF;
    s_hud_vram_start[0] = s_hud_vram_start[1] = 0xFFFF;
}

void hud_render_b(void) {
    u8 page = (u8)bc_a;
    u8 force = (u8)bc_b;
    u8 other = (u8)(page ^ 1);
    u16 sig = hud_sig();
    u8 i;
    u8* p;
    if (!force &&
        s_hud_vram_start[page] == g_vram_start &&
        s_hud_sig[page] == sig) {
        return;
    }
    s_hud_vram_start[page] = g_vram_start;
    s_hud_sig[page] = sig;
    s_base_hi = (page == 0) ? 0xC0 : 0x80;

    if (force && s_hud_sig[other] == sig) {
        // HUD ja renderitzat a la pagina oposada amb els MATEIXOS valors:
        // copia les 2 files (8 blocs) des d'alla en lloc de refer els tiles.
        hud_copy_call((u16) ((s_base_hi ^ 0x40u) << 8) |
                      (u16) (s_hud_vram_start[other] & 0x03FFu));
        return;
    }

    // Vides 1 digit (maxim real 8).
    s_hud_layout[4] = (u8)(9 + g_lives_count);
    hud_set_vinyl_digits(g_vinyls_count);
    p = &s_hud_layout[7];
    for (i = 0; i < 5; i++) {
        u8 h0 = (i < g_hearts_count) ? 7 : 0;
        *p++ = h0;
        *p++ = h0 ? 8 : 0;
    }
    // Slots col.leccionables: slot i gris (19+4i,20+4i), color si ja s'ha
    // recollit fins a aquest nivell (i < g_has_instrument -> 21+4i,22+4i).
    p = &s_hud_layout[24];
    for (i = 0; i < 5; i++) {
        u8 sb = (u8)(19 + (i << 2) + ((i < g_has_instrument) ? 2 : 0));
        *p++ = sb;
        *p++ = (u8)(sb + 1);
    }

    hud_blit_columns();
}

// Banner GAME OVER (1:1 DOS): 34 files de 40 bytes sobre el backbuffer.
void gameover_banner_b(void) __naked {
    __asm
        ld   hl, (_g_vram_start)
        ld   de, #410               ;; 10 * 40 + 10
        add  hl, de
        ld   a, h
        and  #0x03
        ld   h, a
        add  hl, hl
        ld   a, (_bc_a)
        or   a
        ld   a, #0xC0
        jr   z, go_base$
        ld   a, #0x80
    go_base$:
        add  a, h
        ld   d, a
        ld   e, l                   ;; DE = VRAM(y=0)
        ld   hl, (_s_lv + 75)       ;; HL = s_lv.gameover_off
        ld   b, #34
    go_row$:
        push bc
        push de
        ld   a, d
        and  #0x07
        cp   #0x07
        jr   nz, go_fast$
        ld   a, e
        cp   #0xD9
        jr   nc, go_wrap$
    go_fast$:
        ld   bc, #40
        ldir
        jr   go_step$
    go_wrap$:
        ld   b, #40
    go_wloop$:
        ld   a, (hl)
        ld   (de), a
        inc  hl
        inc  de
        ld   a, d
        and  #0x07
        or   e
        jr   nz, go_wnext$
        ld   a, d
        sub  #0x08
        ld   d, a
    go_wnext$:
        djnz go_wloop$
    go_step$:
        pop  de
        ld   a, d
        add  a, #0x08
        ld   d, a
        and  #0x38
        jr   nz, go_next$
        ld   a, d
        sub  #0x40
        ld   d, a
        ld   a, e
        add  a, #0x50
        ld   e, a
        jr   nc, go_next$
        ld   a, d
        inc  a
        and  #0xC7
        ld   d, a
    go_next$:
        pop  bc
        djnz go_row$
        ret
    __endasm;
}

// Dany d'acid kind=10 (1:1 DOS tiles.c:907-919: yfriction 14/10/5 -> vy=-yfric*8)
// i dany de premsa op11 (vy==0 -> special_anim=18, s_dazed_timer=20).
void acid_hurt_b(void) {
    i16 vy = (i16)bc_a;
    if (s_invuln_timer || s_dying_timer) return;
    if (g_hearts_count > 0) g_hearts_count--;
    s_invuln_timer = 75;
    if (vy) {
        s_vy = vy;
        s_on_ground = 0;
    } else if (g_hearts_count > 0 && s_climb_prev != 2) {
        s_dazed_timer = 20;
    }
    if (g_hearts_count == 0) {
        s_dying_timer = 64;
        s_dazed_timer = 0;
        s_invuln_timer = 255;
    }
}

void game_pause_b(void) {
    u8 pst = 0;
    u8 was_ready = g_mus_ready;
    g_mus_hold = 1;
    mus_stop();
    for (;;) {
        cpct_scanKeyboard_f();
        if ((u8)(~cpct_keyboardStatusBuffer[(u8)(Key_P)] & (u8)((u16)(Key_P) >> 8))) {
            if (pst == 1) pst = 2;
        } else {
            if (pst == 0) pst = 1;
            else if (pst == 2) break;
        }
    }
    g_mus_ready = was_ready;
    g_mus_hold = 0;
}
