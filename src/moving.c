// ============================================================
// moving.c - Part RESIDENT del mòdul d'objectes mòbils (CP-2.2)
// ------------------------------------------------------------
// La lògica (init/update/conveyor/push/find + efectes de tiles
// i física de nivell) viu al Banc 5 (src/moving_bank.c, 0x6E00)
// i s'hi crida via call_banked() amb el bloc de paràmetres bc_*.
// Els ascensors (draw/restore) viuen al Banc 1 (src/level_code.c, 0x6934).
// ============================================================
#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"
#include "fdc.h"
#include "level_params.h"

#define LEVEL_PKG_DEFS_ONLY
#include "level_pkg.h"

// Slots fixos de la taula de salts del Banc 5: a moving.h (font unica).

MovingElevator g_mag_elevators[MAG_ELEVATOR_COUNT];

// Bloc de paràmetres resident per crides bankades (CP-2.2).
u16 bc_a, bc_b, bc_c, bc_d, bc_e;
i16 bc_r;

u8 s_conveyor_phase;
u8 s_conveyor_tick;
u8 s_page_conveyor_phase[2];

u8 g_vinyls_count;
u8 g_hearts_count;
u8 g_lives_count;
u8 g_has_instrument;
u8 g_level_complete;
u8 g_checkpoint;
u8 g_enemy_decomp_cnt;
u8 s_dance_timer;

void moving_init(void) { call_banked(0xC5, BC_INIT); }

void moving_update(void) { call_banked(0xC5, BC_UPDATE); }

// 1:1 DOS init_level(): reinicia el MON (plataformes, fases, instrument)
// sense tocar els comptadors. Es crida al reinici per mort.
void moving_respawn(void) { call_banked(0xC5, BC_RESPAWN); }

void moving_popup_restore(u8 page) { bc_a = page; call_banked(0xC5, BC_RESTORE); }

// Slots del codi del nivell al Banc 1: la BASE ve del paquet
// (s_lv.code_exc_off); engine/bank1_table.s hi posa draw a +0 i restore a +3.
#define LC1_DRAW    ((void*)(u16)(s_lv.code_exc_off))
#define LC1_RESTORE ((void*)(u16)(s_lv.code_exc_off + 3))

void moving_restore(u8 page, u8 force) {
    (void)force;
    if (!s_lv.code_exc_off) return;   // nivell sense codi d'excepcions
    bc_a = page;
    call_banked(0xC0, LC1_RESTORE);
}

void moving_draw(u8 page, u16 cam_x4, u16 cam_row) {
    if (!s_lv.code_exc_off) return;   // nivell sense ascensors
    bc_a = page;
    bc_b = cam_x4;
    bc_c = cam_row;
    call_banked(0xC0, LC1_DRAW);
}

void moving_draw_conveyor_tiles(void) { call_banked(0xC5, (void*)0x6E12); }

i16 moving_conveyor_push(void) { call_banked(0xC5, BC_PUSH); return bc_r; }

i8 moving_find_landing(void) { call_banked(0xC5, BC_FIND); return (i8)bc_r; }

// Trampolins al modul C6 (slots engine/enemy_table.s @0x5C00+3k; el banc
// es C6 perque OUT(0x7F00,0xC2) penja la maquina i C3 reboota, 10/26).
// Tiles via tile_flags/is_floor_solid de main.c (globals via EQU:
// estalvia duplicar-los aqui, ~200 B de Bloc 0).
#define EN_SLOT(n) ((void*)(0x5C00 + (n) * 3))
void enemy_init(void) { call_banked(0xC6, EN_SLOT(3)); }
void enemy_update(void) { call_banked(0xC6, EN_SLOT(0)); }
void enemy_restore(u8 page) { bc_a = page; call_banked(0xC6, EN_SLOT(1)); }
void enemy_draw(u8 page) {
    bc_a = page;
    call_banked(0xC6, EN_SLOT(2));
}

u8 enemy_check_player_hit(i16 px, i16 py, u8 crouch) {
    bc_a = (u16)px;
    bc_b = (u16)py;
    bc_c = (u16)crouch;
    call_banked(0xC6, EN_SLOT(4));
    return (u8)bc_r;
}

u8 enemy_check_crate_hit(i16 cx, i16 cy, i16 cvx) {
    bc_a = (u16)cx;
    bc_b = (u16)cy;
    bc_c = (u16)cvx;
    call_banked(0xC6, EN_SLOT(5));
    return (u8)bc_r;
}

void enemy_room_exit(i16 px, i16 py) {
    u8 i;
    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        g_mag_elevators[i].drawn[0] = 0;
        g_mag_elevators[i].drawn[1] = 0;
    }
    bc_a = (u16)px;
    bc_b = (u16)py;
    call_banked(0xC6, EN_SLOT(6));
}


// --- Carregador FDC banquet (F1) ---
// El motor FDC (fdc.c + assets_fdc.s, TAL QUAL) viu al banc 0xC6 (FDC.BIN,
// slot C6:0x7000). Com que el motor commuta la finestra on s'executaria,
// NO pot correr ni al banc ni a 0x7000 central (paginable!): l'stub el
// copia a scratch central 0x8000 (VRAM pag.2, fora de 0x4000-0x7FFF,
// invisible, esborrat pel GAME post-carregues) i l'hi crida, amb
// comportament bit-identic al resident d'abans. Una sola copia per sessio
// (l'scratch sobreviu: el joc no escriu a 0x8000 central fins al memset;
// FRONT futur: per sota de 0x8000!). Mateixa signatura que fdc.h: main.c
// no canvia. Guany: ~1600 B fora del Bloc 0 + carrega a mig joc (nivells).
#define FDC_BANK_BASE 0x8000
#define FDC_BANK_ENTRY ((u8(*)(u8, const DiskFileDesc*, u8, void*))FDC_BANK_BASE)
extern const u16 g_crc_fdc;
extern const u16 g_len_fdc; // = FDC.BIN sencer (main.c; el build ho verifica)
static u8 s_fdc_ready = 0;
static u8 s_fdc_master_saved = 0;

void fdc_motor_off(void) {
    __asm
        ld      bc, #0xFA7E
        xor     a
        out     (c), a
    __endasm;
    *(volatile u8*)0xBE0B = 0;
    *(volatile u8*)0xBE0C = 0;
    *(volatile u8*)0xBE0D = 0xFF;
    *(volatile u8*)0xBE0E = 0;
}

// CRC16-CCITT compartit (dieta Bloc 0): tambe l'usa el loop de carregues
// de main.c (abans inline duplicat). Global (era static).
u16 fdc_crc16(const u8* p, u16 len) {
    u16 crc = 0xFFFF;
    while (len--) {
        u8 k;
        crc ^= (u16)(*p++) << 8;
        for (k = 0; k < 8; k++)
            crc = (crc & 0x8000) ? (u16)((crc << 1) ^ 0x1021) : (u16)(crc << 1);
    }
    return crc;
}
u8 fdc_load_file(u8 home_bank, const DiskFileDesc* d, u8 bk, void* ad) {
    volatile const DiskFileDesc* file_d = d;
    if (!s_fdc_ready) {
        u8 prev = bank_get();
        u8 i;
        for (i = 0; i < 2; i++) {
            u16 off = (u16)(i << 9);
            bank_set(0xC6);
            cpct_memcpy((void*)0xBC00, (const void*)(0x7000 + off), 512);
            bank_set(0xC0);
            cpct_memcpy((void*)(0x7800 + off), (const void*)0xBC00, 512);
        }
        bank_restore(prev);
        s_fdc_ready = 1;
    }
    if (!file_d) return 1;

    // VRAM Page 1 (0x8000..0xBFFF) is overwritten during gameplay.
    // Always restore the resident FDC driver to 0x8000 from master copy at C0:0x7800.
    __asm
        push    de
        ld      a, #0xC0
        call    _bank_set
        push    af
        ld      bc, (_g_len_fdc)
        ld      de, #0x8000
        ld      hl, #0x7800
        ld      a, b
        or      c
        jr      z, 00138$
        ldir
00138$:
        pop     af
        call    _bank_restore
        pop     de
    __endasm;

    *(volatile u8*)0xBE0A |= 0x80;
    return FDC_BANK_ENTRY(home_bank, (const DiskFileDesc*)file_d, bk, ad);
}
