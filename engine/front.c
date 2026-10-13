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
void cpct_scanKeyboard_f(void); // EQU central (mateix scan que el joc)
extern u8 cpct_keyboardStatusBuffer[10]; // EQU central (buffer 10 files)

// Tecla/boto premut? (13/10/26: l'scan ASM duplicat no detectava en HW
// real (ni teclat ni joystick); el timeout ho emmascarava. Ara fem servir
// EXACTAMENT el codi provat del joc (cpct_scanKeyboard_f + buffer), via
// EQU central (patro mus.s): 0 bytes al Bloc 0, mateix comportament que
// moure en Jake. Cobreix teclat + joystick (fila 9).
static u8 f_fkey_pressed(void) {
    u8 r = 0, i;
    cpct_scanKeyboard_f();
    for (i = 0; i < 10; i++) r |= cpct_keyboardStatusBuffer[i];
    return (u8)(r != 0xFF);
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
    // anterior, no saltem en cadena) i despres espera la premuda.
    // f_fkey cobreix teclat + joystick (fila 9 de la matriu). La musica la
    // porta la ISR (50 Hz) i aqui corre lliure (cap HOLD en C0).
    while (f_fkey_pressed()) { }
    while (!f_fkey_pressed()) { }
}
