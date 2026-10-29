#ifndef MOVING_H
#define MOVING_H

#include "cpctelera.h"

#define MAG_ELEVATOR_COUNT 5
// Premses (op11, nivells 2-6): van al mateix array que els ascensors,
// a partir de MAG_ELEVATOR_COUNT. Al DOS (objects.c object_func_op11) puja
// 2 px/frame i baixa 4 px/frame, amb 40 passos d'espera a cada extrem, i
// el jugador hi puja damunt.
#define MAG_PRESS_COUNT 3
#define PRESS_OBJECT_H 30   // level_obj_h[22] del DOS (al�ada de l'objecte)
#define MAG_MOVER_COUNT (MAG_ELEVATOR_COUNT + MAG_PRESS_COUNT)
#define ELEVATOR_W_BYTES 8
#define ELEVATOR_H 14
#define ELEVATOR_OBJECT_H 14
#define ELEVATOR_SPR_HALF_W 8
#define ELEVATOR_BG_SIZE (ELEVATOR_W_BYTES * ELEVATOR_H)
#define ELEVATOR_WIDTH_PX 18
#define ELEVATOR_SPR_WIDTH_PX (ELEVATOR_W_BYTES * 2)
#define ELEVATOR_HALF_W 9
// Premses (op11, level_obj_w[22] = 10 px DOS -> 5 px CPC): mateixa finestra
// de suport que al DOS (do_level_handle_object_bonus_collision).
#define PRESS_HALF_W 5

typedef struct {
    i16 center_x;               // coordenades de joc Mode 0 (px)
    i16 y;                      // origen vertical de l'objecte (px)
    i8 delta_y;
    i8 direction;               // -1 amunt, +1 avall
    u8 map_col;                 // columna original per als triggers de parada
    u8 wait;
    u8 anim_tick;
    u8 frame;
    u8 drawn[2];
    u8 drawn_byte_count[2];
    u8 drawn_row_count[2];
} MovingElevator;

#define ELEVATOR_BG_BASE 0x7200
#define elevator_bg_ptr(idx, page) ((u8*)(ELEVATOR_BG_BASE + (((u16)(idx) << 1) + (page)) * ELEVATOR_BG_SIZE))

extern MovingElevator g_mag_elevators[MAG_MOVER_COUNT];

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
extern u8  s_climb_t6;
extern u8  s_crouch_hold;
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
extern u8  s_rep_col[4], s_rep_row[4], s_rep_tile[4], s_rep_pages[4];

// Estat d'ítems, bonus i malus (actualitzat al Banc 5):
extern u8  g_vinyls_count;
extern u8  g_hearts_count;
extern u8  g_lives_count;
extern u8  g_has_instrument;
extern u8  g_level_complete;
extern u8  g_checkpoint;
extern u8  g_enemy_decomp_cnt;   // diagnostic: descompressions de cela d'enemic (cache miss)
extern u8 s_dance_timer;
extern u8 s_dying_timer;
extern u8 s_pipe_up; // Tuberia (op 17/18/19 del DOS): 1 = el jugador esta dins
                     // del trigger i puja amb forca -> gravetat invertida (DOS: yacc = -3).

// Tram animat del tilemap (row, col_ini, col_fi, seq). El defineix moving.h
// (no level_pkg.h) perquè el tick resident hi accedeix per bc_*.
// El tick en deriva base=(row<<7)+col (un sol shift, barat respecte
// duplicar la taula: el C5 va just per als 6 nivells).
typedef struct {
    u8 row;
    u8 col_start;
    u8 col_end;
    u8 seq;
} AnimSpan;
// Tick d'anims: actualitza MAP_MUT amb C5 mapejat (cridat des del Banc 5).
void anim_tick_c5(void);

void carry_abort(void);
void acid_hurt(i16 vy); // dany d'àcid kind=10 (resident, per estalviar C5)
void moving_popup_restore(u8 page);

// Bloc de paràmetres per crides bankades amb args/retorn (CP-2.2).
extern u16 bc_a, bc_b, bc_c, bc_d, bc_e;
extern i16 bc_r;
extern i16 g_belt_push; // push de cinta del frame (propi: bc_r el trepitgen els enemics)
extern u8  g_on_ice;    // 1 si el jugador es a terra sobre gel (op=30 o rampes 32..35)

// Slots fixos de la taula de salts del Banc 5 (engine/bank5_table.s).
// Font unica (abans duplicats a moving.c): 0x6E00+3k per sempre.
#define BC_TABLE   0x7FE8
#define BC_UPDATE  ((void*)(BC_TABLE + 0))
#define BC_RESTORE ((void*)(BC_TABLE + 3))
#define BC_DRAW    ((void*)(BC_TABLE + 6))
#define BC_PUSH    ((void*)(BC_TABLE + 9))
#define BC_FIND    ((void*)(BC_TABLE + 12))
#define BC_INIT    ((void*)(BC_TABLE + 15))
#define BC_CONVEYOR ((void*)(BC_TABLE + 18))
#define BC_RESPAWN ((void*)(BC_TABLE + 21))

extern u16 g_moving_dst;
extern u16 g_moving_background;
extern u16 g_moving_sprite;
extern u8 g_moving_span;
extern u8 g_moving_rows;
extern u8 g_moving_spr_skip;
extern void moving_blit_box(void);
extern void moving_restore_box(void);
extern u8* ring_address(u8 page, i16 x, i16 y);

void moving_init(void);
void moving_update(void);
void moving_respawn(void);
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
u8 enemy_probe_turn(u8 acol, u8 lcol, u8 r_feet, u8 r_floor, u8 r_head, u8 bit, u8 on_ground);
u8 enemy_probe_floor(u8 c1, u8 c2, u8 trow);

#endif


