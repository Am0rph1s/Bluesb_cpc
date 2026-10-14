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

// Vora fixa (hardcode, 0 risc ABI: el param en A/L ja ens ha mossegat
// un cop - la vora sortia blanca). f_fpal la torna negra en sortir.
static void f_bord_j(void) { // blau 0x44 = Jake
    __asm
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x44
        out     (c), a
        ret
    __endasm;
}
static void f_bord_e(void) { // 0x4C = Elwood
    __asm
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x4C
        out     (c), a
        ret
    __endasm;
}
// Tinta paleta (pen f_inkp = f_inkv): pel pols del focus (swap pen0<->pen2:
// canvi GARANTIT visible sense saber quina tinta es l'oval blau).
static volatile u8 f_inkp, f_inkv;
static void f_ink(void) {
    __asm
        ld      bc, #0x7F00
        ld      a, (#_f_inkp)
        out     (c), a
        ld      a, (#_f_inkv)
        out     (c), a
        ret
    __endasm;
}
// Ballarins select: frames 16x30 (parelles inv,img: dst=(dst&inv)|img) a la
// cua de FSELECT.ZX0 (mini-DANCE 4x480: Jake 0/1, Elwood 2/3; el depack els
// ignora); fons a 0x9800 (2x240, pagina oculta). Ovals a x38/86 bytes
// 19-26/43-50, y118 (files 118..147). Tot C: sense ASM delicat.
extern const u8 fselect_dance_base[]; // EQU front_ext (0x8400+off)
static u16 f_rowaddr(u8 y, u8 xb) {
    return (u16)0xC000 + (u16)(y >> 3) * 80 + xb + ((u16)(y & 7) << 11);
}
static void f_bg(u8 side, u8 save) {
    u8 r, k;
    u8 xb = side ? 43 : 19;
    u8* bg = (u8*)(side ? 0x9900 : 0x9800);
    for (r = 0; r < 30; r++) {
        u8* v = (u8*)f_rowaddr((u8)(118 + r), xb);
        for (k = 0; k < 8; k++) {
            if (save) bg[(u16)r * 8 + k] = v[k];
            else v[k] = bg[(u16)r * 8 + k];
        }
    }
}
static void f_draw(u8 fidx) {
    u8 r, k;
    const u8* s = &fselect_dance_base[(u16)fidx * 480];
    u8 xb = (fidx < 2) ? 19 : 43;
    for (r = 0; r < 30; r++) {
        u8* v = (u8*)f_rowaddr((u8)(118 + r), xb);
        for (k = 0; k < 8; k++) {
            u8 inv = *s++;
            u8 img = *s++;
            v[k] = (v[k] & inv) | img;
        }
    }
}
static volatile u8 f_dph, f_dlast, f_pul, f_plast;
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
        // mus_init() DESPRES de la imatge (a baix): la intro arrenca neta,
        // sense glitch de lectura pel mig. El player encara no iniciat
        // (g_mus_ready=0): la ISR no sona durant aquestes dues lectures.
    } else {
        // MUTE en lectura d'imatge (HW real 13/10/26: amb la ISR sonant la
        // lectura grinyola/interfereix). mus_stop = silenci immediat (sense
        // nota clavada) + HOLD = la ISR no fa Play (l'AKG reprendria el so
        // al tick seguent). Despres: HOLD=0 + mus_init (intro de nou).
        mus_stop();
        g_mus_hold = 1;
    }
    for (t = 0; t < 3 && !ok; t++) {
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
    // Lectura feta: reobrir so (intro de nou, des de dalt) i espera amb
    // musica. Splash (load_mus): HOLD ja a 0 (el motor el neteja simetric
    // en sortir del C1); select/map: netegem el mute manual d'abans.
    g_mus_hold = 0;
    mus_init();
    // Espera TECLA/BOTO (INFINITA: res de timeouts auto-pass). Primer espera
    // que no hi hagi res premut (si l'usuari venia prement de la pantalla
    // anterior, no saltem en cadena) i despres espera la premuda (SPACE o
    // foc joystick). La musica la porta la ISR (50 Hz) i aqui corre lliure
    // (la lectura ja es muda: stop+HOLD abans, init despres).
    // SELECT (flag EXPLICIT del caller: els statics banked neixen amb
    // BROSSA - vist 14/10/26: un comptador intern enganxava l'splash).
    // Escriu g_player_choice directe via EQU (el caller no hi toca res).
    if (g_front_args.select_mode) {
        // SELECT Jake/Elwood: ballarins animats (2 frames ~3/s) + focus
        // polsant (swap pen0<->pen2) + L/R (joy + fletxes) amb vora
        // persistent + FIRE/SPACE confirma. Default Jake (com DOS).
        u8 d;
        f_choice = 0;
        f_bord_j();
        f_bg(0, 1);
        f_bg(1, 1);
        f_draw(0);
        f_draw(2);
        f_dph = 0;
        f_dlast = g_ticks;
        f_pul = 0;
        f_plast = g_ticks;
        while (f_fkey_pressed() || f_dir_mask()) { }
        for (;;) {
            if ((u8)(g_ticks - f_dlast) >= 100) {
                f_dlast = g_ticks;
                f_dph ^= 1;
                f_bg(0, 0);
                f_bg(1, 0);
                f_draw(f_dph);
                f_draw((u8)(2 + f_dph));
            }
            if ((u8)(g_ticks - f_plast) >= 150) {
                f_plast = g_ticks;
                f_pul ^= 1;
                if (f_pul) { f_inkp = 0; f_inkv = 0x44; f_ink(); f_inkp = 2; f_inkv = 0x47; f_ink(); }
                else { f_inkp = 0; f_inkv = 0x47; f_ink(); f_inkp = 2; f_inkv = 0x44; f_ink(); }
            }
            d = f_dir_mask();
            if (d & 1) {
                if (f_choice) { f_choice = 0; f_bord_j(); }
                while (f_dir_mask() & 1) { }
            }
            if (d & 2) {
                if (!f_choice) { f_choice = 1; f_bord_e(); }
                while (f_dir_mask() & 2) { }
            }
            if (f_fkey_pressed()) break;
        }
        g_player_choice = f_choice;
    } else {
        while (f_fkey_pressed()) { }
        while (!f_fkey_pressed()) { }
    }
}
