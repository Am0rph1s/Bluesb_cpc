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
#define elevator_bg_ptr(idx, page) ((u8*)(ELEVATOR_BG_BASE + (((u16)(idx) << 1) + (page)) * ELEVATOR_BG_SIZE))

extern MovingElevator g_mag_elevators[MAG_ELEVATOR_COUNT];

// Estat compartit resident (llegit/escribible des del Banc 5):
extern u8 s_conveyor_phase;
extern u8 s_conveyor_tick;
extern u8 s_page_conveyor_phase[2];

// Estat del jugador i càmera resident (Bloc 0), actualitzat des del Banc 5:
extern u16 g_cam_x4;
extern u16 g_cam_row;
extern i16 s_px8, s_py8;
extern i16 s_vx, s_vy;
extern u8  s_on_ground;
extern u8  s_jump_prev;
extern u8  s_climb_prev;
extern u8  s_carry_kind;
extern u8  s_grab_prev;
extern u8  s_carry_state;
extern i16 s_carry_x, s_carry_y;
extern i16 s_carry_vx;
extern u8  s_carry_drawn[2];
extern i8  s_ground_elevator;
extern u8  g_face;
extern u8  s_anim_idx, s_anim_timer;
extern u8  s_rep_n;
extern u8  s_rep_col[3], s_rep_row[3], s_rep_tile[3], s_rep_pages[3];

// Estat d'ítems, bonus i malus (actualitzat al Banc 5):
extern u8  g_vinyls_count;
extern u8  g_hearts_count;
extern u8  g_lives_count;
extern u8  g_has_instrument;
extern u8  g_level_complete;
extern u8  g_checkpoint;
extern u8  s_dance_timer;

void carry_abort(void);
void moving_popup_restore(u8 page);

// Bloc de paràmetres per crides bankades amb args/retorn (CP-2.2).
extern u16 bc_a, bc_b, bc_c, bc_d, bc_e;
extern i16 bc_r;

// Slots fixos de la taula de salts del Banc 5 (engine/bank5_table.s).
// Font unica (abans duplicats a moving.c): 0x6E00+3k per sempre.
#define BC_UPDATE ((void*)0x6E00)
#define BC_RESTORE ((void*)0x6E03)
#define BC_DRAW   ((void*)0x6E06) // slot 2 sense us (el CRC-hi-va-morir)
#define BC_PUSH   ((void*)0x6E09)
#define BC_FIND   ((void*)0x6E0C)
#define BC_INIT   ((void*)0x6E0F)

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
i8 moving_find_landing(void);
i16 moving_conveyor_push(void);
void moving_draw_conveyor_tiles(void);
u16 fdc_crc16(const u8* p, u16 len); // CRC16-CCITT (moving.c; tambe main.c)

// Tiles de main.c compartits amb el modul C6 (via EQU banked).
u8 tile_type(u16 col, u16 row);
u8 tile_flags(u16 col, u16 row);
u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch);

#endif
