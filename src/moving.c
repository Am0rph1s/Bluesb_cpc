// ============================================================
// moving.c - Part RESIDENT del mòdul d'objectes mòbils (CP-2.2)
// ------------------------------------------------------------
// La lògica (init/update/conveyor/push/find + efectes de tiles
// i física de nivell) viu al Banc 5 (src/moving_bank.c, 0x6E00)
// i s'hi crida via call_banked() amb el bloc de paràmetres bc_*.
// Aquí queden únicament les dades residents, ring_address i el
// restore/draw d'ascensors que accedeixen al Banc 7 (0xC7).
// ============================================================
#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"

// Slots fixos de la taula de salts del Banc 5 (engine/bank5_table.s).
#define BC_UPDATE ((void*)0x6E00)
#define BC_RESTORE ((void*)0x6E03)
#define BC_DRAW   ((void*)0x6E06)
#define BC_PUSH   ((void*)0x6E09)
#define BC_FIND   ((void*)0x6E0C)
#define BC_INIT   ((void*)0x6E0F)

MovingElevator g_mag_elevators[MAG_ELEVATOR_COUNT];
u16 g_moving_dst;
u16 g_moving_background;
u16 g_moving_sprite;
u8 g_moving_span;

// Bloc de paràmetres resident per crides bankades (CP-2.2).
u16 bc_a, bc_b, bc_c, bc_d, bc_e;
i16 bc_r;

u8 s_conveyor_phase;
u8 s_conveyor_tick;
u8 s_page_conveyor_phase[2];

u8* ring_address(u8 page, i16 x, i16 y) {
    u16 x_byte = (u16)(x >> 1);
    u16 ma = (u16)((((u16)(y >> 3) * 40) + (x_byte >> 1)) & 0x03FF);
    u16 offset = (u16)(((ma << 1) + (x_byte & 1)) & 0x07FF);
    u16 base = page ? 0x8000 : 0xC000;
    return (u8*)(base + (((u16)y & 7) << 11) + offset);
}

void moving_init(void) { call_banked(0xC5, BC_INIT); }

void moving_update(void) { call_banked(0xC5, BC_UPDATE); }

// Frames d'ascensor al Banc 7 (ELEV.BIN a 0x78E0, 2x224 B).
#define ELEVATOR_FRAMES_BASE ((const u8*)0x78E0)
#define ELEVATOR_FRAME_SIZE  224

// CP-2.2b: restore/draw SÓN residents (el codi bancat no pot niuar de banc:
// en commutar, el propi codi a 0x4000-0x7FFF desapareix). Els bank_set(C7)
// aquí són segurs (codi central, sempre mapejat).
void moving_restore(u8 page, u8 force) {
    u8 prev_bank;
    u8 i, y;
    if (page > 1) return;

    prev_bank = bank_set(0xC7);
    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        if (!e->drawn[page]) continue;
        if (!force) {
            i16 x = (i16)(e->center_x - ELEVATOR_SPR_HALF_W);
            i16 yy = (i16)(e->y - ELEVATOR_OBJECT_H);
            if (e->drawn_x[page] == x && e->drawn_y[page] == yy &&
                e->drawn_frame[page] == e->frame) continue;
        }

        for (y = 0; y < e->drawn_row_count[page]; y++) {
            u8 sprite_row;
            u16 bg_off;
            sprite_row = (u8)(e->drawn_start_row[page] + y);
            bg_off = (u16)sprite_row * ELEVATOR_W_BYTES + e->drawn_start_byte[page];
            g_moving_dst = (u16)ring_address(page,
                (i16)(e->drawn_x[page] + e->drawn_start_byte[page] * 2),
                (i16)(e->drawn_y[page] + sprite_row));
            g_moving_background = (u16)(elevator_bg_ptr(i, page) + bg_off);
            g_moving_span = e->drawn_byte_count[page];
            moving_restore_span();
        }
        e->drawn[page] = 0;
    }
    bank_restore(prev_bank);
}

void moving_draw(u8 page, u16 cam_x4, u16 cam_row) {
    u8 prev_bank;
    u8 i, y;
    i16 view_x = (i16)(cam_x4 << 2);
    i16 view_y = (i16)(cam_row << 3);
    if (page > 1) return;

    prev_bank = bank_set(0xC7);
    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        i16 world_x;
        i16 world_y;
        i16 clip_x0, clip_x1, clip_y0, clip_y1;
        u8 start_byte, byte_count, start_row, row_count;
        const u8* frame;

        if (e->drawn[page]) continue;
        world_x = (i16)(e->center_x - ELEVATOR_SPR_HALF_W);
        world_y = (i16)(e->y - ELEVATOR_OBJECT_H);
        clip_x0 = world_x > view_x ? world_x : view_x;
        clip_x1 = world_x + ELEVATOR_SPR_WIDTH_PX < view_x + 160 ?
                  (i16)(world_x + ELEVATOR_SPR_WIDTH_PX) : (i16)(view_x + 160);
        clip_y0 = world_y > view_y ? world_y : view_y;
        clip_y1 = world_y + ELEVATOR_H < view_y + 160 ?
                  (i16)(world_y + ELEVATOR_H) : (i16)(view_y + 160);
        if (clip_x0 >= clip_x1 || clip_y0 >= clip_y1) continue;

        start_byte = (u8)((clip_x0 - world_x) >> 1);
        byte_count = (u8)((clip_x1 - clip_x0) >> 1);
        start_row = (u8)(clip_y0 - world_y);
        row_count = (u8)(clip_y1 - clip_y0);
        frame = e->frame ? (ELEVATOR_FRAMES_BASE + ELEVATOR_FRAME_SIZE)
                           : ELEVATOR_FRAMES_BASE;

        for (y = 0; y < row_count; y++) {
            u8 sprite_row = (u8)(start_row + y);
            u16 bg_off = (u16)sprite_row * ELEVATOR_W_BYTES + start_byte;
            u16 frame_off = bg_off << 1;
            g_moving_dst = (u16)ring_address(page, clip_x0, (i16)(clip_y0 + y));
            g_moving_background = (u16)(elevator_bg_ptr(i, page) + bg_off);
            g_moving_sprite = (u16)(frame + frame_off);
            g_moving_span = byte_count;
            moving_blit_span();
        }
        e->drawn_start_byte[page] = start_byte;
        e->drawn_byte_count[page] = byte_count;
        e->drawn_start_row[page] = start_row;
        e->drawn_row_count[page] = row_count;
        e->drawn_x[page] = world_x;
        e->drawn_y[page] = world_y;
        e->drawn_frame[page] = e->frame;
        e->drawn[page] = 1;
    }
    bank_restore(prev_bank);
}

void moving_draw_conveyor_tiles(void) { call_banked(0xC5, (void*)0x6E12); }

i16 moving_conveyor_push(void) { call_banked(0xC5, BC_PUSH); return bc_r; }

i8 moving_find_landing(void) { call_banked(0xC5, BC_FIND); return (i8)bc_r; }
