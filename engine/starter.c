#include "fdc.h"
#include "starter_tables.h"

// Stub local: cap crida del starter la necessita (l'enllaç resident la pren
// de cpc_hardware.s); evita arrossegar tot el hardware al starter.
void cpct_setPALColour(u8 pen, u8 hw) { (void)pen; (void)hw; }

// starter.c - Carregador inicial (~2 KB a 0x3000).
//
// El firmware només carrega el starter (4-5 sectors: poques probabilitats
// de lectura espatllada). El starter es copia a VRAM 0xC000 (s_start PIC),
// carrega GAME.BIN (imatge resident completa) amb el nostre carregador FDC
// (DI + polling, determinista) amb reintents, i salta a l'inici del joc.
// Cal reubicar: GAME ocupa 0x0100..0x3869 i trepitjaria l'starter a 0x3000
// abans del CALL final. Així el firmware gairebé no pot fallar.

void s_start(void);

// Banc a paginar per a la pagina de CRC (el motor restaura 0xC0 en sortir;
// cal re-paginar el banc desti per a verificar-hi a sobre).
u8 g_st_bank;
static void s_bank_apply(void) {
    __asm
        push    bc
        ld      bc, #0x7F00
        ld      a, (_g_st_bank)
        out     (c), a
        pop     bc
    __endasm;
}

static u16 s_crc16(const u8* p, u16 len) {
    u16 crc = 0xFFFF;
    while (len--) {
        u8 i;
        crc ^= (u16)(*p++) << 8;
        for (i = 0; i < 8; i++)
            crc = (crc & 0x8000) ? (u16)((crc << 1) ^ 0x1021) : (u16)(crc << 1);
    }
    return crc;
}

static void s_border_blue(void) {
    // Blau: s_main ha arrencat.
    __asm
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x44
        out     (c), a
    __endasm;
}

static void s_border_yellow(void) {
    // Groc: FDC ha carregat GAME (abans del CRC).
    __asm
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x5E
        out     (c), a
    __endasm;
}

static void s_border_ok(void) {
    // Verd: CRC de GAME correcte.
    __asm
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x42
        out     (c), a
    __endasm;
}

static void s_border_fail(void) {
    // Igual amb vermell.
    __asm
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x4C
        out     (c), a
    __endasm;
}

static u8 s_load_one(const DiskFileDesc* f, u8 bank, void* addr, u16 len, u16 crc) {
    u8 tries = 3;
    while (tries--) {
        // Home 0xC0: l'starter corre en VRAM/central (mai paginat).
        if (fdc_load_file(0xC0, f, bank, addr)) {
            if (crc == 0) return 1;
            // Verificar amb el banc desti paginat (el motor el restaura en sortir).
            g_st_bank = bank; s_bank_apply();
            if (s_crc16((const u8*)addr, len) == crc) {
                g_st_bank = 0xC0; s_bank_apply();
                return 1;
            }
            g_st_bank = 0xC0; s_bank_apply();
        }
    }
    return 0;
}

// NOTA FRONT: les pantalles (SPLASH/SELECT/MAP) les mostra el GAME
// (main() primerenc, central: escriure VRAM des de VRAM es suïcida).
// L'starter nomes carrega+salta (aqui no es desempaca res).

void s_main(void) {
    s_border_blue(); // s_main ha arrencat
    // 1. GAME resident (mateixos colors d'abans).
    if (!s_load_one(&g_file_game, 0xC0, (void*)0x0100, GAME_LEN, GAME_CRC)) {
        s_border_fail(); // vermell: GAME no carregat/corrupte, no saltar
        while (1) { }
    }
    s_border_yellow(); // GAME ok (llegit + CRC)
    // 2. Banc FDC (motor de disc de la sessio; el GAME el crida via scratch).
    // Amb CRC del payload (FDC_LEN-128): si el banc arriba corrupte, vermell.
    if (!s_load_one(&g_file_fdc, 0xC6, (void*)0x7000, FDC_LEN - 128, CRC_FDC)) {
        s_border_fail(); // vermell: FDC no carregat/corrupte, no saltar
        while (1) { }
    }
    // 3. FRONT banked (overlay C4:0x4000, el TILESET el sobreescriura).
    // Amb CRC del payload: si arriba corrupte, vermell (saltar-hi seria deriva).
    if (!s_load_one(&g_file_front, 0xC4, (void*)0x4000, FRONT_LEN - 128, CRC_FRONT)) {
        s_border_fail(); // vermell: FRONT no carregat/corrupte, no saltar
        while (1) { }
    }
    // 4. MUSBANK: NO es carrega aqui. C1 mapeja slot3->banc7 (config 1 del
    // 6128) i l'starter (slot 3: 0xC000) desapareix en paginar = reboot.
    // El GAME (slot 0, segur en totes les configs) el carrega pre-FRONT.
    // (El fitxer MUSBANK continua al DSK; el GAME el llegeix amb el stub.)
    s_border_ok(); // verd: tot a RAM (pausa visible ~0.3 s)
    __asm
        ld      bc, #60000
1$:     dec     bc
        ld      a, b
        or      c
        jr      nz, 1$
    __endasm;
    __asm
        ld      bc, #0x7F00
        ld      a, #0x10
        out     (c), a
        ld      a, #0x40
        out     (c), a   ;; BLANC pre-salt (DIAG F1: si es veu, el salt passa)
    __endasm;
    ((void(*)(void))GAME_START)();
    while (1) { }
}

void s_start(void) {
    // PIC: aquest bloc s'enllaça per a 0xC000 però el firmware l'executa
    // a 0x3000. Només fa servir LD imm + LDIR + JP absolut: segur a totes
    // dues adreces. Copia la finestra sencera a VRAM i salta al _s_main
    // reubicat (la GAME 0x0100..0x3869 trepitjaria 0x3000 en carregar).
    __asm
        di                      ; la ROM marxa: cap interrupcio de firmware
        ld      a, #0xC9
        ld      (0x0038), a     ; stub RET a RST 0x38 (IM1): el FDC fa EI intern
                                ; amb ROMs OFF i sense ISR instal-lada; sense
                                ; aixo, un VSYNC entremig = salt a brossa = reboot.
        xor     a
        ld      (MUS_HOLD_ADDR), a ; HOLD musica ISR = 0 (lliure). La RAM pot
                                ; portar brossa de reboot calent: sense aixo
                                ; la ISR saltaria la musica per sempre.
        ld      a, #0x80
        ld      (0xBE0A), a     ; LED-ink SILENCIOS (NAU_FDC_BLINK bit 7). Si no,
                                ; el motor parpelleja la ink 2 (groc/negre) per
                                ; sector i la brossa de pantalla te pixels en
                                ; tinta 2 = punts grocs parpellejants. El LED
                                ; fisic de la disquetera no en depen.
        ld      bc, #0x7F8C
        out     (c), c          ; RMR: Mode 0 + ROMs OFF (RAM a tot arreu).
                                ; Sense aixo, 0xC000 es llegeix de la ROM alta
                                ; (la copia a VRAM seria invisible a la CPU).
        ld      d, #0           ; TINTES A NEGRE (13/10/26): la pantalla mostra
00020$: ld      bc, #0x7F00      ; 0xC000 = restes BASIC + copia starter (brossa
        ld      a, d            ; blava). Amb inks negres es invisible pero el
        out     (c), a          ; motor fa el mateix. Vores diagnostics intactes
        ld      a, #0x54        ; (verd/blau/groc); FRONT/video posen la seva
        out     (c), a          ; paleta. Nomes LD/OUT: PIC-safe.
        inc     d
        ld      a, d
        cp      #16
        jr      nz, 00020$
        ld      sp, #0x3FFE
        ld      bc, #0x7F00      ; verd immediat: prova que el firmware hi arriba
        ld      a, #0x10
        out     (c), a
        ld      a, #0x42
        out     (c), a
        ld      hl, #0x3000
        ld      de, #0xC000
        ld      bc, #0x0800
        ldir
        jp      _s_main
    __endasm;
}
