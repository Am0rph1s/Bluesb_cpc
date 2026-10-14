#include "fdc.h"
#include "front.h"

// ============================================================
// front.c - FRONT banked (C4:0x4000, overlay d'arrencada).
// Copia fidel de s_fkey/s_fpal/s_fshow (main.c), amb noms f_ i args
// per g_front_args. Nomes toca RAM central, VRAM, PPI i Gate Array
// (mai la finestra bancable): correcte al banc. Crides externes
// (stub central + depack central) resoltes per build via front_ext.s
// (EQU del mapa resident). Sense cpct_* (no enllacats aqui): el
// vermell d'error es OUT directe al Gate Array.
// ============================================================

void zx0_decompress(const void* src, void* dst); // enllacat AL FRONT (no EQU)
void mus_play(void); // EQU central (mus.s: pagina C1, 1 tick, restaura)
void mus_init(void); // EQU central (mus.s: pagina C1, init intro, restaura)
void mus_stop(void); // EQU central (mus.s: silencia AY, posicio intacta)
extern volatile u8 g_ticks; // ISR 300 Hz (central _DATA; llegible banked)
extern volatile u8 g_mus_hold; // HOLD ISR (central _DATA; EQU front_ext.s:
// AKG Play reprendria el so al tick seguent del mus_stop: el mute en
// lectures ha d'anar amb HOLD=1, si no el glitch torna en 20 ms)
extern volatile u8 g_player_choice; // tria F1 (central _DATA; l'escriu el
                                    // select directe: 0=Jake, 1=Elwood)
extern volatile u8 g_map_level; // nivell actual 0..5 (l'escriu el GAME)

// Resultat via static (NO en L/A directe!): veure s_fkey_pressed (main.c).
static volatile u8 f_fkres;
static volatile u8 f_choice; // tria select: 0=Jake(esq), 1=Elwood(dreta)
static volatile u8 f_dres; // mascara direccio (file-scope: nom ASM estable)

// Tecla/boto premut? = SPACE (linia 5, bit 7) o Joy0_Fire1 (linia 9,
// bit 4). Port VERBATIM del Loader de nau_dx (Am0rph1s, provat en HW
// real): ni l'scan ASM duplicat ni el cami cpct detectaven des del FRONT
// (sempre 0 / vora DIAG sempre negra); aquesta seq (sense F782 inicial,
// sense INI, files per F64x/F44x, cua F600) si que veu tecles. Nomes
// aquestes dues entrades (prou per "prem per continuar"); no OR de 10.
static u8 f_fkey_pressed(void) {
    f_fkres = 0;
    __asm
        di                       ;; ATOMIC (13/10/26b): la ISR (musica PSG)
                                 ;; trepitjava la fila seleccionada entre OUT
                                 ;; i IN = lectures tremoloses. El cami cpct
                                 ;; fa DI/EI; el port nau_dx no en tenia.
        ld      e, #5
        call    00010$
        and     #0x80             ;; Key_Space = 0x8005 (actiu-baix)
        jr      z, 00011$
        ld      e, #9
        call    00010$
        and     #0x10             ;; Joy0_Fire1 = 0x1009 (actiu-baix)
        jr      nz, 00012$
00011$: ld      hl, #_f_fkres
        inc     (hl)              ;; premut -> 1
        jr      00012$
00010$: ;; read_keyline_e: E = linia matriu 0..9. A = estat actiu-baix.
        ld      bc, #0xF40E
        out     (c), c
        ld      bc, #0xF6C0
        out     (c), c
        xor     a
        out     (c), a
        ld      bc, #0xF792
        out     (c), c
        ld      a, e
        add     #0x40
        ld      c, a
        ld      b, #0xF6
        out     (c), c
        ld      b, #0xF4
        in      a, (c)
        ld      bc, #0xF782
        out     (c), c
        ld      bc, #0xF600
        out     (c), c
        ret
00012$:
        ei                       ;; fi seccio atomica (veure di de dalt)
    __endasm;
    return f_fkres;
}

extern const u8 fsplash_zx[]; // EQU front_ext (fixa 0x8400)
extern const u8 fsel_zx[]; // EQU front_ext (banc C4 0x4900, propi banc)
extern const u8 fmap_zx[]; // EQU front_ext (fixa darrere splash)
extern u8 f_bg0[]; // EQU front_ext (fons ballari 0, C4 darrere select)
extern u8 f_bg1[]; // EQU front_ext (fons ballari 1, C4 darrere select)
extern const u8 fselect_dance_base[]; // EQU front_ext (cua DANCE20)
extern const u8 fmap_stick_base[]; // EQU front_ext (cua MAPSTICK)
static u16 f_rowaddr(u8 y, u8 xb);
// Focus: groc (0x4A) sobre el triat, blau (0x44) l'altre + terra iluminat
// (groc palid 0x43) vs no (blau cel 0x57). Cons a pens separats (esq 13 /
// dret 14), ovals idem (esq 6 / dret 15): un simple canvi de tinta,
// instantani, sense parpelleig. Es crida a l'inici i a cada canvi L/R.
// (La vora es la negra standard del joc: el diag blau/vermell ja no cal.)
static void f_focus(void) {
    __asm
        ld      bc, #0x7F00
        ld      a, #13
        out     (c), a
        ld      a, (#_f_choice)
        or      a
        jr      nz, 00170$
        ld      a, #0x4A
        jr      00171$
00170$: ld      a, #0x44
00171$: out     (c), a
        ld      a, #14
        out     (c), a
        ld      a, (#_f_choice)
        or      a
        jr      nz, 00172$
        ld      a, #0x44
        jr      00173$
00172$: ld      a, #0x4A
00173$: out     (c), a
        ld      a, #6
        out     (c), a
        ld      a, (#_f_choice)
        or      a
        jr      nz, 00174$
        ld      a, #0x43
        jr      00175$
00174$: ld      a, #0x57
00175$: out     (c), a
        ld      a, #15
        out     (c), a
        ld      a, (#_f_choice)
        or      a
        jr      nz, 00176$
        ld      a, #0x57
        jr      00177$
00176$: ld      a, #0x43
00177$: out     (c), a
        ret
    __endasm;
}
// Blitter rapid (nucli sprite_blit_player del joc, sense bancs/camara/reixa:
// el FRONT corre a C4 i no pot paginar C7). Files de 8 B a xb 19/43,
// y118..147: MAI wrap (43+8=51 < 80). f_blit desa fons + dibuixa (com el
// joc: sense passada prèvia); f_unblit restaura amb LDIR.
static volatile u16 f_row_v, f_row_s, f_row_p;
static void f_blit_row(void) {
    __asm
        ld      de, (#_f_row_v)
        ld      hl, (#_f_row_s)
        ld      bc, (#_f_row_p)
        .rept 8
        ld      a, (de)
        ld      (bc), a
        inc     bc
        and     (hl)
        inc     hl
        or      (hl)
        inc     hl
        ld      (de), a
        inc     de
        .endm
        ret
    __endasm;
}
static void f_unblit_row(void) {
    __asm
        ld      hl, (#_f_row_p)
        ld      de, (#_f_row_v)
        ld      bc, #8
        ldir
        ret
    __endasm;
}
static volatile u8 f_sid, f_fi;
static void f_unblit(void) {
    u8 r;
    u8 xb = f_sid ? 43 : 19;
    u8* bg = (u8*)(f_sid ? f_bg1 : f_bg0);
    for (r = 0; r < 30; r++) {
        f_row_v = f_rowaddr((u8)(118 + r), xb);
        f_row_p = (u16)(bg + (u16)r * 8);
        f_unblit_row();
    }
}
static void f_blit(void) {
    u8 r;
    u8 xb = f_sid ? 43 : 19;
    u8* bg = (u8*)(f_sid ? f_bg1 : f_bg0);
    const u8* s = &fselect_dance_base[(u16)f_fi * 480];
    for (r = 0; r < 30; r++) {
        f_row_v = f_rowaddr((u8)(118 + r), xb);
        f_row_s = (u16)(s + (u16)r * 16);
        f_row_p = (u16)(bg + (u16)r * 8);
        f_blit_row();
    }
}
// Mapa F2: sticker nota + ruta statica DOS (game.c do_inter_screen).
// Posicions DOS xpos[]/ypos[] (x CENTRAT, y a BAIX), sprite 126 de 48x34
// i dashes 125 de 16x6. CPC: sticker xb=(x/2-12)/2, yb=y-34 (24x34);
// dash xb=x/4-2, 6 files y-6..y-1 (8 reals + 8 pad). Files de MAPSTICK
// encoixinades a 8 parells: 1 crida f_olit_row per 8 B VRAM.
static const u8 m_xb[6] = {56, 14, 54, 44, 14, 14};
static const u8 m_yb[6] = {136, 21, 6, 61, 131, 136};
static const u8 m_xd[6] = {250, 80, 240, 200, 80, 80};
static const u8 m_yd[6] = {170, 55, 40, 95, 165, 170};
// Blitter one-shot (sense save: el mapa es static, no hi ha restore).
static void f_olit_row(void) {
    __asm
        ld      de, (#_f_row_v)
        ld      hl, (#_f_row_s)
        ld      b, #8
00100$: ld      a, (de)
        and     (hl)
        inc     hl
        or      (hl)
        inc     hl
        ld      (de), a
        inc     de
        djnz    00100$
        ret
    __endasm;
}
static void f_map_sticker(u8 lvl) {
    u8 r;
    u8 xb = m_xb[lvl];
    u8 yb = m_yb[lvl];
    const u8* s = fmap_stick_base;
    for (r = 0; r < 34; r++) {
        f_row_v = f_rowaddr((u8)(yb + r), xb);
        f_row_s = (u16)(s + (u16)r * 32);
        f_olit_row();
        f_row_v = f_rowaddr((u8)(yb + r), (u8)(xb + 8));
        f_row_s = (u16)(s + (u16)r * 32 + 16);
        f_olit_row();
    }
}
// Un dash DOS (X centre, y baix) -> CPC xb=X/4-2, files y-6..y-1.
static void f_map_dash(u16 x, u8 y) {
    u8 r;
    u8 xb = (u8)(x / 4 - 2);
    u8 yt = (u8)(y - 6);
    const u8* s = fmap_stick_base + 1088;
    for (r = 0; r < 6; r++) {
        f_row_v = f_rowaddr((u8)(yt + r), xb);
        f_row_s = (u16)(s + (u16)r * 16);
        f_olit_row();
    }
}
// Creu de ruta DOS (helper c=0, static): 40+40 dashes en X.
static void f_map_leg(u8 j) {
    u8 i;
    u16 x = m_xd[j];
    u8 y = m_yd[j];
    for (i = 0; i < 40; i++)
        f_map_dash(x + 19 - i, (u8)(y - 19 + i));
    for (i = 0; i < 40; i++)
        f_map_dash(x - 19 + i, (u8)(y - 19 + i));
}
// Ballarins select: 20 frames reals DOS 16x30 (parelles inv,img:
// dst=(dst&inv)|img) a la cua de FSELECT.ZX0 (DANCE20 20x480; el depack els
// ignora). Ordre: Jake dansa 0-5 + Jake idle 6-8 + Elwood dansa-A 9-13 +
// Elwood dansa-B 14-19. Fons a f_bg0/f_bg1 (EQU: 2x240 al C4 darrere el
// select.ZX0; abans 0xB600/0xB700, pero alla hi va el map.ZX0 a fixa).
// Ovals a x38/86 bytes 19-26/43-50, y118 (files 118..147).
// Seqüències DOS tal qual (game.c: 0135/00dd/01d5/022d, 1-indexades -> aquí
// 0-indexades). Tot C: sense ASM delicat.
static u16 f_rowaddr(u8 y, u8 xb) {
    return (u16)0xC000 + (u16)(y >> 3) * 80 + xb + ((u16)(y & 7) << 11);
}
// Seqüències DOS (game.c) mapejades a la cua: Jake dansa (0135: 52 passos),
// Jake idle (00dd: 50, amb wrap a entrada 4 com el DOS), Elwood dansa-A
// (01d5: 50, Jake triat) i dansa-B (022d: 52, Elwood triat). Generades amb
// script (cap transcripció manual).
static const u8 f_jd[52] = {
    2, 2, 3, 3, 4, 4, 5, 5, 0, 0, 1, 1,
    2, 2, 3, 3, 4, 4, 5, 5, 0, 0, 1, 1,
    2, 2, 3, 3, 4, 4, 5, 5, 0, 0, 1, 1,
    2, 2, 3, 3, 4, 4, 5, 5, 0, 0, 1, 1,
    2, 2, 3, 3,
};
static const u8 f_ji[50] = {
    6, 6, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8,
};
static const u8 f_ea[50] = {
    9, 9, 9, 9, 10, 10, 11, 11, 11, 11, 12, 12,
    13, 13, 12, 12, 13, 13, 12, 12, 13, 13, 12, 12,
    13, 13, 12, 12, 13, 13, 12, 12, 13, 13, 12, 12,
    13, 13, 12, 12, 11, 11, 11, 11, 10, 10, 9, 9,
    9, 9,
};
static const u8 f_eb[52] = {
    19, 19, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18,
    19, 19, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18,
    19, 19, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18,
    19, 19, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18,
    19, 19, 14, 14,
};
static volatile u8 f_jt, f_et, f_step, f_lj, f_le;
// Direccio premuda? bit0=esquerra, bit1=dreta (actiu-alt). Joy0 L/R
// (linia 9, bits 2/3 = 0x0409/0x0809) + fletxes (dreta linia 0 bit 1,
// esquerra linia 1 bit 0). Mateix read_keyline_e nau_dx + DI atomic.
static u8 f_dir_mask(void) {
    f_dres = 0;
    __asm
        di
        ld      e, #9             ;; Joy0 L/R/F (una lectura)
        call    00020$
        bit     2, a              ;; Joy0_Left (actiu-baix)
        jr      nz, 00021$
        ld      hl, #_f_dres
        set     0, (hl)
00021$: bit     3, a              ;; Joy0_Right
        jr      nz, 00022$
        ld      hl, #_f_dres
        set     1, (hl)
00022$: ld      e, #0             ;; fletxa dreta (linia 0, bit 1)
        call    00020$
        bit     1, a
        jr      nz, 00023$
        ld      hl, #_f_dres
        set     1, (hl)
00023$: ld      e, #1             ;; fletxa esquerra (linia 1, bit 0)
        call    00020$
        bit     0, a
        jr      nz, 00024$
        ld      hl, #_f_dres
        set     0, (hl)
00024$: ei
        jr      00025$
00020$: ;; read_keyline_e (copia local: etiquetes per-funcio en SDCC)
        ld      bc, #0xF40E
        out     (c), c
        ld      bc, #0xF6C0
        out     (c), c
        xor     a
        out     (c), a
        ld      bc, #0xF792
        out     (c), c
        ld      a, e
        add     #0x40
        ld      c, a
        ld      b, #0xF6
        out     (c), c
        ld      b, #0xF4
        in      a, (c)
        ld      bc, #0xF782
        out     (c), c
        ld      bc, #0xF600
        out     (c), c
        ret
00025$:
    __endasm;
    return f_dres;
}

// Posa paleta HW (HL = taula 16 INKR) + vora negra.
static void f_fpal(const u8* palhw) {
    __asm
        ld      d, #0            ;; D = pen 0..15
00003$: ld      e, (hl)          ;; E = hw
        ld      bc, #0x7F00
        ld      a, d
        out     (c), a
        ld      a, e
        out     (c), a
        inc     hl
        inc     d
        ld      a, d
        cp      #16
        jr      nz, 00003$
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x54
        out     (c), a          ;; vora negra
        ret
    __endasm;
}

// Mostra una pantalla del prejoc (splash/select/mapa). Al SPLASH: carrega
// les 3 (FDC silencios: la musica encara no ha arrencat) + MUSBANK, depack
// splash, mus_init. Select/mapa: depack des de RAM (CAP FDC) = la musica
// no s'atura mai. Dests (EQU front_ext): splash+mapa a fixa, select al
// propi banc C4 (l'unic llegible sense paginar).
// OJO: MAI a 0x8000 (hi viu el motor FDC banked: suicidi, vist 12/10/26).
static void f_load(const DiskFileDesc* f, u8 bank, const void* dst) {
    u8 ok = 0, t;
    u8 home = g_front_args.home;
    for (t = 0; t < 3 && !ok; t++) {
        if (!fdc_load_file(home, f, bank, (void*)dst)) continue;
        ok = 1;
    }
    if (!ok) {
        __asm
            ld      bc, #0x7F00
            ld      a, #0x10
            out     (c), a
            ld      a, #0x4C
            out     (c), a      ;; vermell (sense cpct_ aqui)
        __endasm;
        while (1) { }
    }
}
void front_run(void) {
    const u8* palhw = g_front_args.palhw;
    u8 screen = g_front_args.screen;
    // MUSICA + PANTALLES (nomes splash): MUSBANK (player+intro) a C1:0x4000
    // via stub CENTRAL (trampoli segur) + les 3 pantalles a RAM. Tot
    // silencios (g_mus_ready=0: la ISR encara no sona). Home propi (C4).
    if (g_front_args.load_mus) {
        f_load(g_front_args.musbank, 0xC1, (void*)0x4000);
        f_load(g_front_args.splash, 0xC0, (void*)fsplash_zx);
        f_load(g_front_args.sel, 0xC4, (void*)fsel_zx);
        f_load(g_front_args.map, 0xC0, (void*)fmap_zx);
        // mus_init() DESPRES (a baix): la intro arrenca neta, sense glitch
        // de lectura pel mig.
    }
    // Depack des de RAM (splash ara carregat; select/mapa del splash).
    if (screen == 0) {
        zx0_decompress((const void*)fsplash_zx, (void*)0xC000);
    } else if (screen == 1) {
        zx0_decompress((const void*)fsel_zx, (void*)0xC000);
    } else {
        zx0_decompress((const void*)fmap_zx, (void*)0xC000);
    }
    f_fpal(palhw);
    // So (nomes splash): la intro arrenca aqui i ja no para fins als loads
    // del nivell. Select/mapa: ni stop/HOLD ni init (la ISR sona durant el
    // depack CPU sense interferencia: el mute era pel FDC en HW real).
    if (screen == 0) {
        g_mus_hold = 0;
        mus_init();
    }
    // Espera TECLA/BOTO (INFINITA: res de timeouts auto-pass). Primer espera
    // que no hi hagi res premut (si l'usuari venia prement de la pantalla
    // anterior, no saltem en cadena) i despres espera la premuda (SPACE o
    // foc joystick). La musica la porta la ISR (50 Hz) i aqui corre lliure
    // (la lectura ja es muda: stop+HOLD abans, init despres).
    // SELECT (flag EXPLICIT del caller: els statics banked neixen amb
    // BROSSA - vist 14/10/26: un comptador intern enganxava l'splash).
    // Escriu g_player_choice directe via EQU (el caller no hi toca res).
    if (screen == 1) {
        // SELECT Jake/Elwood: els DOS ballen (seqüències 0135/01d5/00dd/022d
        // tal qual, blitter rapid estil joc) + focus groc/blau + terra per
        // tinta + L/R (joy + fletxes) + FIRE/SPACE confirma. Vora negra
        // standard (sense diag). Default Jake (com DOS).
        u8 d;
        f_choice = 0;
        f_focus();
        f_sid = 0; f_fi = f_jd[0]; f_blit();
        f_sid = 1; f_fi = f_ea[0]; f_blit();
        f_jt = 0;
        f_et = 0;
        f_lj = f_jd[0];
        f_le = f_ea[0];
        f_step = g_ticks;
        while (f_fkey_pressed() || f_dir_mask()) { }
        for (;;) {
            if ((u8)(g_ticks - f_step) >= 24) {
                f_step = g_ticks;
                if (f_choice) {
                    if (++f_jt >= 50) f_jt = 3; // idle: wrap DOS a entrada 4
                    if (++f_et >= 52) f_et = 0;
                    // Nomes si el frame canvia (taules amb holds x2/x4):
                    // redibuixar igual parpelleja (tear) sense motiu.
                    if (f_ji[f_jt] != f_lj) {
                        f_lj = f_ji[f_jt];
                        f_sid = 0; f_fi = f_lj; f_unblit(); f_blit();
                    }
                    if (f_eb[f_et] != f_le) {
                        f_le = f_eb[f_et];
                        f_sid = 1; f_fi = f_le; f_unblit(); f_blit();
                    }
                } else {
                    if (++f_jt >= 52) f_jt = 0;
                    if (++f_et >= 50) f_et = 0;
                    if (f_jd[f_jt] != f_lj) {
                        f_lj = f_jd[f_jt];
                        f_sid = 0; f_fi = f_lj; f_unblit(); f_blit();
                    }
                    if (f_ea[f_et] != f_le) {
                        f_le = f_ea[f_et];
                        f_sid = 1; f_fi = f_le; f_unblit(); f_blit();
                    }
                }
            }
            d = f_dir_mask();
            // Canvi de taules (dansa<->idle): els rangs son disjunts
            // (JD 0-5, JI 6-8, EA 9-13, EB 14-19) i el primer frame
            // sempre difereix de f_lj/f_le: redibuix garantit sense reset.
            if (d & 1) {
                if (f_choice) { f_choice = 0; f_focus(); f_jt = 0; f_et = 0; }
                while (f_dir_mask() & 1) { }
            }
            if (d & 2) {
                if (!f_choice) { f_choice = 1; f_focus(); f_jt = 0; f_et = 0; }
                while (f_dir_mask() & 2) { }
            }
            if (f_fkey_pressed()) break;
        }
        g_player_choice = f_choice;
    } else if (screen == 2) {
        // MAPA F2: fons + ruta statica DOS (creus dels nivells superats)
        // + sticker nota al nivell actual (do_inter_screen, sense animacio
        // ni SOUND_2: no hi ha infra SFX). Nivell 1: nomes la nota al mall.
        u8 j;
        u8 lvl = g_map_level;
        if (lvl > 5) lvl = 5;
        for (j = 0; j < lvl; j++) f_map_leg(j);
        if (lvl == 5) f_map_leg(5);
        else f_map_sticker(lvl);
        while (f_fkey_pressed()) { }
        while (!f_fkey_pressed()) { }
    } else {
        while (f_fkey_pressed()) { }
        while (!f_fkey_pressed()) { }
    }
}
