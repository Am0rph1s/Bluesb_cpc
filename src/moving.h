#ifndef MOVING_H
#define MOVING_H

#include "cpctelera.h"

#define MAG_ELEVATOR_COUNT 5
#define ELEVATOR_W_BYTES 8
#define ELEVATOR_H 14
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
    u8 bg[2][ELEVATOR_BG_SIZE];
} MovingElevator;

extern MovingElevator g_mag_elevators[MAG_ELEVATOR_COUNT];

void moving_init(void);
void moving_update(void);
void moving_restore(u8 page, u8 force);
void moving_draw(u8 page, u16 cam_x4, u16 cam_row);
u8 level_get_tile_type(u16 col, u16 row);
i8 moving_find_landing(i16 player_x, i16 previous_feet, i16 current_feet,
                       i16 vy, i16* player_top);
i16 moving_conveyor_push(u16 col0, u16 col1, u16 row);

#endif
