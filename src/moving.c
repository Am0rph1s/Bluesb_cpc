// Moving Magasin objects: conveyor floor triggers and the five DOS elevators.
#include "cpctelera.h"
#include "moving.h"
#include "sprite.h"
#include "elevator_frames.h"

#define MAP_PTR  ((const u8*)0x4000)
#define TRIG_PTR ((const u8*)0x6400)
#define ELEVATOR_WAIT 40
#define ELEVATOR_SPEED 2
#define ELEVATOR_OBJECT_H 30
#define ELEVATOR_SPR_HALF_W 8

MovingElevator g_mag_elevators[MAG_ELEVATOR_COUNT];

// These are object slots 19..23 (type 7, object opcode 4) in cyxx/blues'
// Magasin level data. X is halved because DOS/Amiga graphics are 320 px wide.
static const i16 s_start_x[MAG_ELEVATOR_COUNT] = { 760, 808, 760, 808, 304 };
static const i16 s_start_y[MAG_ELEVATOR_COUNT] = { 384, 464, 592, 736, 784 };
static const u8 s_map_col[MAG_ELEVATOR_COUNT] = { 95, 101, 95, 101, 38 };

extern u8 level_get_tile_type(u16 col, u16 row);

static u8* ring_address(u8 page, i16 x, i16 y, u8 byte_x) {
    u16 x_byte = (u16)((x >> 1) + byte_x);
    u16 ma = (u16)((((u16)(y >> 3) * 40) + (x_byte >> 1)) & 0x03FF);
    u16 offset = (u16)(((ma << 1) + (x_byte & 1)) & 0x07FF);
    u16 base = page ? 0x8000 : 0xC000;
    return (u8*)(base + (((u16)y & 7) << 11) + offset);
}

void moving_init(void) {
    u8 i;
    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        e->center_x = s_start_x[i];
        e->y = s_start_y[i];
        e->delta_y = 0;
        e->direction = -1;
        e->map_col = s_map_col[i];
        e->wait = 0;
        e->anim_tick = 0;
        e->frame = 0;
        e->drawn[0] = e->drawn[1] = 0;
        e->drawn_frame[0] = e->drawn_frame[1] = 0;
        e->drawn_x[0] = e->drawn_x[1] = 0;
        e->drawn_y[0] = e->drawn_y[1] = 0;
    }
}

void moving_update(void) {
    u8 i;
    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        u16 row;

        e->delta_y = 0;
        e->frame = 0;

        if (e->wait < ELEVATOR_WAIT) {
            e->wait++;
            continue;
        }

        row = (u16)(e->y >> 4);
        if (e->direction < 0) {
            if (row >= 4 && level_get_tile_type(e->map_col, (u16)(row - 4)) == 10) {
                e->direction = 1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y - ELEVATOR_SPEED);
            e->delta_y = -ELEVATOR_SPEED;
        } else {
            if (level_get_tile_type(e->map_col, (u16)(row + 1)) == 10) {
                e->direction = -1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y + ELEVATOR_SPEED);
            e->delta_y = ELEVATOR_SPEED;
        }

        e->frame = (u8)((e->anim_tick >> 2) & 1);
        e->anim_tick++;
    }
}

static u8 elevator_needs_redraw(const MovingElevator* e, u8 page) {
    i16 x = (i16)(e->center_x - ELEVATOR_SPR_HALF_W);
    i16 y = (i16)(e->y - ELEVATOR_OBJECT_H);
    return !e->drawn[page] || e->drawn_x[page] != x ||
           e->drawn_y[page] != y || e->drawn_frame[page] != e->frame;
}

void moving_restore(u8 page, u8 force) {
    u8 i, y, x;
    if (page > 1) return;

    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        if (!e->drawn[page] || (!force && !elevator_needs_redraw(e, page))) continue;

        for (y = 0; y < ELEVATOR_H; y++) {
            i16 world_y = (i16)(e->drawn_y[page] + y);
            for (x = 0; x < ELEVATOR_W_BYTES; x++) {
                *ring_address(page, e->drawn_x[page], world_y, x) =
                    e->bg[page][(u16)y * ELEVATOR_W_BYTES + x];
            }
        }
        e->drawn[page] = 0;
    }
}

void moving_draw(u8 page) {
    u8 i, y, x;
    if (page > 1) return;

    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        i16 world_x;
        i16 world_y;
        const u8* frame;

        if (e->drawn[page]) continue;
        world_x = (i16)(e->center_x - ELEVATOR_SPR_HALF_W);
        world_y = (i16)(e->y - ELEVATOR_OBJECT_H);
        frame = e->frame ? g_elevator_frame_1 : g_elevator_frame_0;

        for (y = 0; y < ELEVATOR_H; y++) {
            i16 line_y = (i16)(world_y + y);
            for (x = 0; x < ELEVATOR_W_BYTES; x++) {
                u16 off = ((u16)y * ELEVATOR_W_BYTES + x) << 1;
                u8* dst = ring_address(page, world_x, line_y, x);
                u8 bg = *dst;
                e->bg[page][(u16)y * ELEVATOR_W_BYTES + x] = bg;
                *dst = (u8)((bg & frame[off]) | frame[off + 1]);
            }
        }
        e->drawn_x[page] = world_x;
        e->drawn_y[page] = world_y;
        e->drawn_frame[page] = e->frame;
        e->drawn[page] = 1;
    }
}

i8 moving_find_landing(i16 player_x, i16 previous_feet, i16 current_feet,
                       i16 vy, i16* player_top) {
    u8 i;
    if (vy < 0) return -1;

    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        const MovingElevator* e = &g_mag_elevators[i];
        i16 left = (i16)(e->center_x - ELEVATOR_HALF_W);
        i16 right = (i16)(left + ELEVATOR_WIDTH_PX);
        i16 surface = (i16)(e->y - ELEVATOR_OBJECT_H);
        if ((i16)(player_x + 24) <= left || player_x >= right) continue;
        if (previous_feet <= (i16)(surface + 8) && current_feet >= surface) {
            *player_top = (i16)(surface - 30);
            return (i8)i;
        }
    }
    return -1;
}

i16 moving_conveyor_push(u16 col0, u16 col1, u16 row) {
    u8 op0, op1, tile;
    u16 off;
    i8 direction = 0;

    if (row >= 72 || col0 >= 128 || col1 >= 128) return 0;

    cpc_bank_set(0xC5);
    tile = MAP_PTR[(row << 7) + col0];
    off = (((u16)tile) << 3) + (((u16)tile) << 1);
    op0 = TRIG_PTR[off + 2];
    tile = MAP_PTR[(row << 7) + col1];
    off = (((u16)tile) << 3) + (((u16)tile) << 1);
    op1 = TRIG_PTR[off + 2];
    cpc_bank_restore();

    if (op0 == 27 || op1 == 27) direction++;
    if (op0 == 28 || op1 == 28) direction--;
    return (i16)(direction * 16);  // Original unk1C = +/-4 px/f; CPC x is 2x wide.
}
