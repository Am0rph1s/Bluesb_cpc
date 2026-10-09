#ifndef MOVING_H
#define MOVING_H

#include "cpctelera.h"

#define MAG_ELEVATOR_COUNT 5
#define ELEVATOR_W_BYTES 8
#define ELEVATOR_H 14
#define ELEVATOR_OBJECT_H 14
#define ELEVATOR_SPR_HALF_W 8
#define ELEVATOR_BG_SIZE (ELEVATOR_W_BYTES * ELEVATOR_H)
#define ELEVATOR_WIDTH_PX 18
#define ELEVATOR_SPR_WIDTH_PX (ELEVATOR_W_BYTES * 2)
#define ELEVATOR_HALF_W 9

typedef struct {
    i16 center_x;               // coordenades de joc Mode 0 (px)
    i16 y;                      // origen vertical de l'objecte (px)
    i16 delta_y;
    i8 direction;               // -1 amunt, +1 avall
    u8 map_col;                 // columna original per als triggers de parada
    u8 wait;
    u8 anim_tick;
    u8 frame;
    u8 drawn[2];
    u8 drawn_frame[2];
    u8 drawn_start_byte[2];
    u8 drawn_byte_count[2];
    u8 drawn_start_row[2];
    u8 drawn_row_count[2];
    i16 drawn_x[2];
    i16 drawn_y[2];
} MovingElevator;

#define ELEVATOR_BG_BASE 0x70C0

static inline u8* elevator_bg_ptr(u8 idx, u8 page) {
    return (u8*)(ELEVATOR_BG_BASE + (((u16)idx << 1) + page) * ELEVATOR_BG_SIZE);
}

extern MovingElevator g_mag_elevators[MAG_ELEVATOR_COUNT];

typedef struct {
    u8 row;
    u8 col_start;
    u8 col_end;
    u8 op;
} MagConveyorBelt;

// Estat compartit resident (llegit/escribible des del banc):
extern MagConveyorBelt s_belts[4];
extern u8 s_belt_right_body[3];
extern u8 s_belt_right_roller[3];
extern u8 s_belt_left_body[3];
extern u8 s_belt_left_roller[3];
extern u8 s_conveyor_phase;
extern u8 s_conveyor_tick;
extern u8 s_page_conveyor_phase[2];

// Bloc de paràmetres per crides bankades amb args/retorn (CP-2.2).
extern u16 bc_a, bc_b, bc_c, bc_d, bc_e;
extern i16 bc_r;

extern u16 g_moving_dst;
extern u16 g_moving_background;
extern u16 g_moving_sprite;
extern u8 g_moving_span;
extern void moving_blit_span(void);
extern void moving_restore_span(void);
extern u8* ring_address(u8 page, i16 x, i16 y);

void moving_init(void);
void moving_update(void);
void moving_restore(u8 page, u8 force);
void moving_draw(u8 page, u16 cam_x4, u16 cam_row);
u8 level_get_tile_type(u16 col, u16 row);
i8 moving_find_landing(void);
i16 moving_conveyor_push(void);
void moving_draw_conveyor_tiles(void);

#endif
