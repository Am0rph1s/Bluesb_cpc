#ifndef LEVEL_PKG_H
#define LEVEL_PKG_H

// ============================================================================
// level_pkg.h - Paquet de dades del Nivell 1 (MAGASIN) per al Banc 5
// Generat automàticament per tools/pack_level.py des de MAP0.BIN + TRIG0.BIN
// i tools/blues_dos/bb/staticres.c. NO EDITAR MANUALMENT.
// ============================================================================

#define LEVEL_ID            0
#define LEVEL_MAP_W         128
#define LEVEL_MAP_H         72
#define LEVEL_W_PX          (128 * 8)
#define LEVEL_MAX_CAM_ROW   124
#define LEVEL_START_PX      32
#define LEVEL_START_PY      1106
#define LEVEL_CAM0_X4       0
#define LEVEL_CAM0_ROW      124
#define LEVEL_CHK_PX        352
#define LEVEL_CHK_PY        464
#define LEVEL_CHK_CAM_X4    68
#define LEVEL_CHK_CAM_ROW   48

#define LEVEL_ELEVATOR_COUNT 5
#define LEVEL_ELEVATOR_STORAGE 5
#define LEVEL_PRESS_COUNT 0
#define LEVEL_PRESS_STORAGE 1
#define LEVEL_HAS_ACID 0
#define LEVEL_HAS_BALLOON 1
#define LEVEL_HAS_UMBRELLA 1
#define LEVEL_INST_COL      0
#define LEVEL_INST_ROW      0
#define LEVEL_INST_TILE     0

#ifndef LEVEL_PKG_DEFS_ONLY
static const i16 s_bank_start_x[LEVEL_ELEVATOR_STORAGE] = { 760, 808, 760, 808, 304 };
static const i16 s_bank_start_y[LEVEL_ELEVATOR_STORAGE] = { 384, 464, 592, 736, 784 };
static const u8 s_bank_map_col[LEVEL_ELEVATOR_STORAGE] = { 95, 101, 95, 101, 38 };
static const i16 s_bank_press_x[LEVEL_PRESS_STORAGE] = { 0 };
static const i16 s_bank_press_y[LEVEL_PRESS_STORAGE] = { 0 };
static const u8 s_bank_press_map_col[LEVEL_PRESS_STORAGE] = { 0 };

// Seqüències EXACTES 1:1 DOS en pla (sense MCM6): cada b4 cicla amb
// el seu propi període (2/3/4/20 frames × tick de 4 game-frames).
// Índex: tile = s_anim_data[s_anim_off[seq] + s_anim_phase[seq]].
// s_anim_len porta sentinella 0 (bucle sense comptador).
#define LEVEL_ANIM_SEQ_COUNT 7
#define LEVEL_ANIM_DATA_LEN 18
static const u8 s_anim_data[LEVEL_ANIM_DATA_LEN] = { 236, 235, 234, 223, 224, 225, 231, 232, 233, 222, 221, 220, 130, 192, 148, 202, 164, 230 };
static const u8 s_anim_off[LEVEL_ANIM_SEQ_COUNT] = { 0, 3, 6, 9, 12, 14, 16 };
static const u8 s_anim_len[LEVEL_ANIM_SEQ_COUNT + 1] = { 3, 3, 3, 3, 2, 2, 2, 0 };

// Trams animats: (row, col_ini, col_fi, seq). Tipus AnimSpan de moving.h.

#define LEVEL_ANIM_SPAN_COUNT 18
#define LEVEL_ANIM_SPAN_STORAGE 18
static const AnimSpan s_level_anim_spans[LEVEL_ANIM_SPAN_STORAGE] = {
    { 30,  46,  46, 6 }, // row 30, cols 46..46 (DOS b4=78)
    { 30,  48,  56, 4 }, // row 30, cols 48..56 (DOS b4=76)
    { 30,  58,  58, 5 }, // row 30, cols 58..58 (DOS b4=77)
    { 30,  68,  68, 6 }, // row 30, cols 68..68 (DOS b4=78)
    { 30,  70,  78, 4 }, // row 30, cols 70..78 (DOS b4=76)
    { 30,  80,  80, 5 }, // row 30, cols 80..80 (DOS b4=77)
    { 36,  84,  84, 0 }, // row 36, cols 84..84 (DOS b4=29)
    { 36,  85,  85, 2 }, // row 36, cols 85..85 (DOS b4=31)
    { 36,  86,  86, 0 }, // row 36, cols 86..86 (DOS b4=29)
    { 39,  83,  83, 1 }, // row 39, cols 83..83 (DOS b4=30)
    { 39,  84,  88, 3 }, // row 39, cols 84..88 (DOS b4=32)
    { 39,  89,  89, 1 }, // row 39, cols 89..89 (DOS b4=30)
    { 42,  80,  80, 0 }, // row 42, cols 80..80 (DOS b4=29)
    { 42,  81,  85, 2 }, // row 42, cols 81..85 (DOS b4=31)
    { 42,  86,  86, 0 }, // row 42, cols 86..86 (DOS b4=29)
    { 45,  84,  84, 1 }, // row 45, cols 84..84 (DOS b4=30)
    { 45,  85,  88, 3 }, // row 45, cols 85..88 (DOS b4=32)
    { 45,  89,  89, 1 }, // row 45, cols 89..89 (DOS b4=30)
};

// Taula de triggers d'ítems / bonus / malus (DOS level_triggersdata_2030)
typedef struct {
    u8 kind;         // 11 = directe, 12 = amb popup emergent
    u8 bg_tile;      // tile de fons net que substitueix l'ítem al mapa
    u8 add_vinyls;   // vinils a sumar (+1, +50)
    u8 sub_vinyls;   // vinils a restar (-10, -20, -30, -40, -50)
    u8 add_heart;    // +1 cor d'energia (màx 5)
    u8 special_anim; // 21 = ballar
    u8 instrument;   // >0 = objecte col·leccionable obligatori del nivell
    u8 exit_flag;    // 1 = meta final de nivell (requereix instrument)
    u8 popup_or_chk; // kind==12: grab_type (16..22); kind==11: checkpoint
    u8 add_life;     // +1 vida (ulleres i barret)
} LevelTriggerEntry;

#define LEVEL_TRIG3_COUNT 10
#define LEVEL_TRIG3_STORAGE 10
static const LevelTriggerEntry s_level_trig3[LEVEL_TRIG3_STORAGE] = {
    { 11,  20,  1,  0, 0,  0, 0, 0,   0, 0 }, // DOS b6=14
    { 11,   0,  1,  0, 0,  0, 0, 0,   0, 0 }, // DOS b6=15
    { 11,  20,  0,  0, 1,  0, 0, 0,   0, 0 }, // DOS b6=16
    { 11,  20,  0,  0, 0, 21, 0, 0,   0, 0 }, // DOS b6=17
    { 12,  20, 50,  0, 0,  0, 0, 0,   2, 0 }, // DOS b6=18
    { 12,   0,  0, 10, 0,  0, 0, 0,   0, 0 }, // DOS b6=19
    { 12,  20,  0, 20, 0,  0, 0, 0,   1, 0 }, // DOS b6=20
    { 11,  95,  0,  0, 0,  0, 1, 0,   0, 0 }, // DOS b6=21
    { 11,  20,  0,  0, 0, 21, 0, 1,   0, 0 }, // DOS b6=22
    { 11,  21,  0,  0, 0,  0, 0, 0,   1, 0 }, // DOS b6=50
};

// LUT ràpida: byte 6 de TRIG.BIN (0..63) -> índex a s_level_trig3 (0xFF = cap)
static const u8 s_b6_to_trig3[64] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,    0,    1,
       2,    3,    4,    5,    6,    7,    8, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF,    9, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
};

#define LEVEL_POPUP_COUNT 3
#define LEVEL_POPUP_STORAGE 3
static const u8 s_popup_sprites[LEVEL_POPUP_STORAGE][56] = {
    { 0xFF, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x55, 0x00, 0xAA, 0x00, 0x55, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x55, 0x00 }, // 0: grab_type 16 (-10)
    { 0xFF, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x55, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0xAA, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0xAA, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x55, 0x00 }, // 1: grab_type 17 (-20)
    { 0xFF, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0xAA, 0x00, 0x55, 0x00, 0xAA, 0x00, 0xAA, 0x00, 0xAA, 0x00, 0x55, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x00, 0x00, 0x55, 0x00, 0xAA, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x55, 0x00, 0xFF, 0x00, 0xAA, 0x00, 0x00, 0x00, 0x55, 0x00 }, // 2: grab_type 21 (+50)
};
#endif // LEVEL_PKG_DEFS_ONLY

#endif
