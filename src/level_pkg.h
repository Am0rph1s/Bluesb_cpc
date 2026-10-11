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
#define LEVEL_START_PX      184
#define LEVEL_START_PY      860
#define LEVEL_CAM0_X4       0
#define LEVEL_CAM0_ROW      124

#define LEVEL_ELEVATOR_COUNT 5

#ifndef LEVEL_PKG_DEFS_ONLY
static const i16 s_bank_start_x[LEVEL_ELEVATOR_COUNT] = { 760, 808, 760, 808, 304 };
static const i16 s_bank_start_y[LEVEL_ELEVATOR_COUNT] = { 384, 464, 592, 736, 784 };
static const u8 s_bank_map_col[LEVEL_ELEVATOR_COUNT] = { 95, 101, 95, 101, 38 };

// Taula unificada de 6 fases (MCM de 3 i 2) per a totes les animacions de tiles del nivell
#define LEVEL_ANIM_SEQ_COUNT 7
static const u8 s_level_anim_seqs[LEVEL_ANIM_SEQ_COUNT][6] = {
    { 253, 252, 251, 253, 252, 251 }, // seq 0 (DOS b4=29)
    { 240, 241, 242, 240, 241, 242 }, // seq 1 (DOS b4=30)
    { 248, 249, 250, 248, 249, 250 }, // seq 2 (DOS b4=31)
    { 239, 238, 237, 239, 238, 237 }, // seq 3 (DOS b4=32)
    { 131, 199, 131, 199, 131, 199 }, // seq 4 (DOS b4=76)
    { 149, 217, 149, 217, 149, 217 }, // seq 5 (DOS b4=77)
    { 170, 247, 170, 247, 170, 247 }, // seq 6 (DOS b4=78)
};

typedef struct {
    u8 row;
    u8 col_start;
    u8 col_end;
    u8 seq;
} LevelAnimSpan;

#define LEVEL_ANIM_SPAN_COUNT 18
static const LevelAnimSpan s_level_anim_spans[LEVEL_ANIM_SPAN_COUNT] = {
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
#endif // LEVEL_PKG_DEFS_ONLY

#endif
