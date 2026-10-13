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

// Resultat via static (NO en L/A directe!): veure s_fkey_pressed (main.c).
static volatile u8 f_fkres;
// Valors crus de les files 5 (SPACE) i 9 (foc) per les barres DIAG.
static volatile u8 f_raw5, f_raw9;

// Tecla/boto premut? = SPACE (linia 5, bit 7) o Joy0_Fire1 (linia 9,
// bit 4). Port VERBATIM del Loader de nau_dx (Am0rph1s, provat en HW
// real): ni l'scan ASM duplicat ni el cami cpct detectaven des del FRONT
// (sempre 0 / vora DIAG sempre negra); aquesta seq (sense F782 inicial,
// sense INI, files per F64x/F44x, cua F600) si que veu tecles. Nomes
// aquestes dues entrades (prou per "prem per continuar"); no OR de 10.
static u8 f_fkey_pressed(void) {
    f_fkres = 0;
    __asm
        ld      e, #5
        call    00010$
        ld      (_f_raw5), a     ;; cru per les barres DIAG
        and     #0x80             ;; Key_Space = 0x8005 (actiu-baix)
        jr      z, 00011$
        ld      e, #9
        call    00010$
        ld      (_f_raw9), a     ;; cru per les barres DIAG
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
    __endasm;
    return f_fkres;
}

// DIAG2-REALHW (TEMPORAL): dues barres en viu a les files 0-1 de VRAM
// (Mode 0: fila y a 0xC000+(y%8)*2048; files 0,1 = 0xC000,0xC800).
// Barra 0 = valor cru linia 5 (SPACE), barra 1 = linia 9 (foc).
// Longitud = valor>>1 bytes a 0xFF (resta a 0). Lectura:
// - 0xFF estable + cau en premer = scan OK.
// - constant != 0xFF = bit encallat (quina: el valor ho diu).
// - ballant = flotant/soroll (cal debounce).
// Nomes toca VRAM visible (mai finestra/bancs): segur banked. Cridar-la
// NO altera l'estat (AF/BC/DE/HL lliures en C).
static void f_bars(void) {
    __asm
        ld      hl, #0xC000
        ld      a, (_f_raw5)
        call    00020$
        ld      hl, #0xC800
        ld      a, (_f_raw9)
        call    00020$
        jr      00021$
00020$: ;; drawbar: A=valor, HL=inici fila. Neteja 80B, omple A>>1 (max 80).
        ld      c, a
        ld      b, #80
        xor     a
00022$: ld      (hl), a
        inc     hl
        djnz    00022$
        ld      a, c
        srl     a
        cp      #80
        jr      c, 00023$
        ld      a, #80
00023$: ld      b, a
        or      a
        jr      z, 00024$
        ld      a, #0xFF
        ld      de, #0xFFB0       ;; -80: torna a l'inici
        add     hl, de
00025$: ld      (hl), a
        inc     hl
        djnz    00025$
00024$: ret
00021$:
    __endasm;
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

// Mostra una pantalla FRONT (.ZX0 a scratch 0x8400, depack a VRAM visible,
// paleta, espera-premut amb timeout). La pantalla anterior es perd.
// OJO: MAI a 0x8000 (hi viu el motor FDC banked: suicidi, vist 12/10/26).
void front_run(void) {
    const DiskFileDesc* f = g_front_args.desc;
    const u8* palhw = g_front_args.palhw;
    u8 home = g_front_args.home;
    u8 ok = 0, t;
    // MUSICA (nomes splash): carrega MUSBANK (player+intro) a C1:0x4000 via
    // stub CENTRAL (trampoli segur: el stub pagina/restaura; el FRONT (slot 1)
    // MAI pagina ell mateix (desapareixeria: C1 mapeja slot1->banc1)).
    // Home propi (C4): el motor hi restaura en sortir. + mus_init central.
    if (g_front_args.load_mus) {
        u8 mok = 0, mt;
        for (mt = 0; mt < 3 && !mok; mt++) {
            if (fdc_load_file(home, g_front_args.musbank, 0xC1, (void*)0x4000))
                mok = 1;
        }
        if (!mok) {
            __asm
                ld      bc, #0x7F00
                ld      a, #0x10
                out     (c), a
                ld      a, #0x4C
                out     (c), a      ;; vermell (sense cpct_ aqui)
            __endasm;
            while (1) { }
        }
        mus_init();
    }
    for (t = 0; t < 3 && !ok; t++) {
        // Sense mus_stop(): el desti es C0 (scratch 0x8400, RAM no bancable)
        // i el motor ja no posa HOLD (= la ISR continua sonant pel mig, la
        // musica NO es para en llegir pantalles). En copies bancades el HOLD
        // si que congela + el caller muta (drone); aqui no cal.
        if (!fdc_load_file(home, f, 0xC0, (void*)0x8400)) continue;
        zx0_decompress((const void*)0x8400, (void*)0xC000);
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
    f_fpal(palhw);
    // Espera TECLA/BOTO (INFINITA: res de timeouts auto-pass). Primer espera
    // que no hi hagi res premut (si l'usuari venia prement de la pantalla
    // anterior, no saltem en cadena) i despres espera la premuda (SPACE o
    // foc joystick). La musica la porta la ISR (50 Hz) i aqui corre lliure
    // (cap HOLD en C0). DIAG2: f_bars() pinta els valors crus en viu.
    while (f_fkey_pressed()) { f_bars(); }
    while (!f_fkey_pressed()) { f_bars(); }
}
