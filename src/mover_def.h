#ifndef MOVER_DEF_H
#define MOVER_DEF_H

#include "cpctelera.h"

// ============================================================
// MoverDef generic (Fase 4) - mateix layout que engine/mover_gen.s
// ------------------------------------------------------------
// NO s'inclou al build de L1 encara. Es la taula que generara
// tools/pack_level.py per a cada nivell (op4/11/14/17/19 i
// horitzontals op5/12/15/18).
//
// ATENCIO: SDCC empaqueta sense alineacio. Offsets contractuals:
//   x=0 (i16), y=2 (i16), map_col=4, flags=5, wait=6,
//   vy_down=7, vy_up=8, up_off=9, down_off=10, stop_op=11,
//   stop_mode=12, limit_y=13 (u16), trig_op=15. sizeof=16.
// ============================================================

#define MF_RIDE     1   // muntable (level_obj_type==1)
#define MF_VERT     2   // mover vertical
#define MF_HORZ     4   // mover horitzontal
#define MF_TILE11   8   // premsa: actualitza tiles com op11
#define MF_TILE17  16   // muntacàrregues: actualitza tiles com op17
#define MF_LIMIT   32   // parada superior per limit_y (op14)
#define MF_4DIR    64   // 4 direccions (op5, data5F/data51)
#define MF_PATTERN 128  // pas 3/2 segons anim_tick&7 (comportament L1 actual)

typedef struct {
    i16 x;
    i16 y;
    u8  map_col;
    u8  flags;
    u8  wait;
    i8  vy_down;
    i8  vy_up;
    i8  up_off;
    i8  down_off;
    u8  stop_op;
    u8  stop_mode;   // 0 ==, 1 !=
    u16 limit_y;
    u8  trig_op;
} LevelMoverDef;

#endif
