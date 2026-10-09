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

u8 s_main(void) {
    u8 tries = 3;
    s_border_blue(); // s_main ha arrencat
    while (tries--) {
        if (fdc_load_file(&g_file_game, 0xC0, (void*)0x0100)) {
            s_border_yellow(); // FDC ok, abans del CRC
            if (s_crc16((const u8*)0x0100, GAME_LEN) == GAME_CRC) {
                s_border_ok(); // verd: GAME íntegre a RAM (3 s visibles)
                { u16 w; u8 v; for (w = 0; w < 300; w++) for (v = 0; v < 200; v++) { } }
                ((void(*)(void))GAME_START)();
            } else {
                s_border_fail(); // vermell: GAME corrupte, no saltar
                while (1) { }
            }
        }
    }
    // 3 intents esgotats: spin (el border vermell ho indicaria si video...).
    while (1) { }
    return 0;
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
        ld      bc, #0x7F8C
        out     (c), c          ; RMR: Mode 0 + ROMs OFF (RAM a tot arreu).
                                ; Sense aixo, 0xC000 es llegeix de la ROM alta
                                ; (la copia a VRAM seria invisible a la CPU).
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
