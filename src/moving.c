// Moving Magasin objects: conveyor floor triggers and the five DOS elevators.
#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"

// Frames d'ascensor al Banc 7 (ELEV.BIN carregat a 0x78E0, 2x224 B).
// Abans eren consts a _CODE (448 B); alliberats per a lògica de joc.
// moving_draw ja commuta a 0xC7 abans de llegir-los (buffers de fons).
#define ELEVATOR_FRAMES_BASE ((const u8*)0x78E0)
#define ELEVATOR_FRAME_SIZE  224

#define MAP_PTR  ((const u8*)0x4000)
#define MAP_MUT  ((u8*)0x4000)
#define TRIG_PTR ((const u8*)0x6400)
#define ELEVATOR_WAIT 33
// DOS ±2px/f@30Hz (60px/s) -> 2.375px/f@25Hz (59.4px/s, -1% invisible):
// patró de 8 [3,3,3,2,2,2,2,2] via (anim_tick&7)<3 (barat, sense % ni lib).
#define ELEVATOR_OBJECT_H 14
// Alçada de l'objecte 14 = sprite sencer: en Jake va amb els peus a y-14,
// 1:1 amb DOS (ypos - level_obj_h[7]=15 + 1). Amb 30 flotava 1 tile amunt
// als dos extrems sense que les parades (triggers 1:1 DOS) tinguessin res.
#define ELEVATOR_SPR_HALF_W 8
#define MOVING_CONVEYOR_MAX 32

typedef struct {
    u8 row;
    u8 col_start;
    u8 col_end;
    u8 op;
} MagConveyorBelt;

static const MagConveyorBelt s_belts[4] = {
    { 36, 84, 86, 27 },
    { 39, 83, 89, 28 },
    { 42, 80, 86, 27 },
    { 45, 84, 89, 28 }
};

MovingElevator g_mag_elevators[MAG_ELEVATOR_COUNT];
u16 g_moving_dst;
u16 g_moving_background;
u16 g_moving_sprite;
u8 g_moving_span;

extern void moving_blit_span(void);
extern void moving_restore_span(void);
extern void render_tile_world(u8 tile, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);

// These are object slots 19..23 (type 7, object opcode 4) in cyxx/blues'
// Magasin level data. X is halved because DOS/Amiga graphics are 320 px wide.
static const i16 s_start_x[MAG_ELEVATOR_COUNT] = { 760, 808, 760, 808, 304 };
static const i16 s_start_y[MAG_ELEVATOR_COUNT] = { 384, 464, 592, 736, 784 };
static const u8 s_map_col[MAG_ELEVATOR_COUNT] = { 95, 101, 95, 101, 38 };
static u8 s_conveyor_phase;
static u8 s_conveyor_tick;
static u8 s_page_conveyor_phase[2];

static const u8 s_belt_right_body[3]   = { 248, 249, 250 };
static const u8 s_belt_right_roller[3] = { 253, 252, 251 };
static const u8 s_belt_left_body[3]    = { 239, 238, 237 };
static const u8 s_belt_left_roller[3]  = { 240, 241, 242 };

extern u8 level_get_tile_type(u16 col, u16 row);

static u8* ring_address(u8 page, i16 x, i16 y) {
    u16 x_byte = (u16)(x >> 1);
    u16 ma = (u16)((((u16)(y >> 3) * 40) + (x_byte >> 1)) & 0x03FF);
    u16 offset = (u16)(((ma << 1) + (x_byte & 1)) & 0x07FF);
    u16 base = page ? 0x8000 : 0xC000;
    return (u8*)(base + (((u16)y & 7) << 11) + offset);
}

void moving_init(void) {
    u8 i;

    s_conveyor_phase = 0;
    s_conveyor_tick = 0;
    s_page_conveyor_phase[0] = s_page_conveyor_phase[1] = 0xFF;

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
        e->drawn_start_byte[0] = e->drawn_start_byte[1] = 0;
        e->drawn_byte_count[0] = e->drawn_byte_count[1] = 0;
        e->drawn_start_row[0] = e->drawn_start_row[1] = 0;
        e->drawn_row_count[0] = e->drawn_row_count[1] = 0;
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
        // Pas 2/3 segons patró (mitjana 2.375px/f = DOS 60px/s a 25Hz).
        {
            i16 step = (((e->anim_tick & 7) < 3) ? 3 : 2);
            if (e->direction < 0) {
                if (row >= 4 && level_get_tile_type(e->map_col, (u16)(row - 4)) == 10) {
                    e->direction = 1;
                    e->wait = 1;
                    continue;
                }
                e->y = (i16)(e->y - step);
                e->delta_y = (i16)-step;
            } else {
                if (level_get_tile_type(e->map_col, (u16)(row + 1)) == 10) {
                    e->direction = -1;
                    e->wait = 1;
                    continue;
                }
                e->y = (i16)(e->y + step);
                e->delta_y = step;
            }
        }

        e->frame = (u8)((e->anim_tick >> 2) & 1);
        e->anim_tick++;
    }

    if (++s_conveyor_tick >= 4) {
        u8 b, c;
        s_conveyor_tick = 0;
        if (++s_conveyor_phase >= 3) {
            s_conveyor_phase = 0;
        }
        cpc_bank_set(0xC5);
        for (b = 0; b < 4; b++) {
            u8 body_tile   = (s_belts[b].op == 27) ? s_belt_right_body[s_conveyor_phase]
                                                   : s_belt_left_body[s_conveyor_phase];
            u8 roller_tile = (s_belts[b].op == 27) ? s_belt_right_roller[s_conveyor_phase]
                                                   : s_belt_left_roller[s_conveyor_phase];
            u16 row_off = (u16)s_belts[b].row << 7;
            MAP_MUT[row_off + s_belts[b].col_start] = roller_tile;
            for (c = (u8)(s_belts[b].col_start + 1); c < s_belts[b].col_end; c++) {
                MAP_MUT[row_off + c] = body_tile;
            }
            MAP_MUT[row_off + s_belts[b].col_end] = roller_tile;
        }
        cpc_bank_restore();
    }
}

void moving_draw_conveyor_tiles(u8 page, u16 cam_x4, u16 cam_row) {
    u8 b, c;
    if (page > 1 || s_page_conveyor_phase[page] == s_conveyor_phase) return;

    for (b = 0; b < 4; b++) {
        u16 belt_subrow = (u16)s_belts[b].row << 1;
        if (belt_subrow + 2 <= cam_row || belt_subrow >= cam_row + 20) continue;

        {
            u8 body_tile   = (s_belts[b].op == 27) ? s_belt_right_body[s_conveyor_phase]
                                                   : s_belt_left_body[s_conveyor_phase];
            u8 roller_tile = (s_belts[b].op == 27) ? s_belt_right_roller[s_conveyor_phase]
                                                   : s_belt_left_roller[s_conveyor_phase];
            for (c = s_belts[b].col_start; c <= s_belts[b].col_end; c++) {
                u16 char_x = (u16)c << 1;
                if (char_x + 2 <= cam_x4 || char_x >= cam_x4 + 40) continue;
                u8 tile = (c == s_belts[b].col_start || c == s_belts[b].col_end) ? roller_tile : body_tile;
                render_tile_world(tile, c, s_belts[b].row, cam_x4, cam_row);
            }
        }
    }
    s_page_conveyor_phase[page] = s_conveyor_phase;
}

static u8 elevator_needs_redraw(const MovingElevator* e, u8 page) {
    i16 x = (i16)(e->center_x - ELEVATOR_SPR_HALF_W);
    i16 y = (i16)(e->y - ELEVATOR_OBJECT_H);
    return !e->drawn[page] || e->drawn_x[page] != x ||
           e->drawn_y[page] != y || e->drawn_frame[page] != e->frame;
}

void moving_restore(u8 page, u8 force) {
    u8 prev_bank;
    u8 i, y;
    if (page > 1) return;

    prev_bank = bank_set(0xC7);
    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        if (!e->drawn[page] || (!force && !elevator_needs_redraw(e, page))) continue;

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
        // The ring contains only the viewport-sized working set. Off-screen
        // world positions alias into visible VRAM after the CRTC wrap, so
        // never blit an elevator unless its sprite intersects this viewport.
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

i8 moving_find_landing(i16 player_x, i16 previous_feet, i16 current_feet,
                       i16 vy, i16* player_top) {
    u8 i;
    if (vy < 0) return -1;

    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        const MovingElevator* e = &g_mag_elevators[i];
        i16 left = (i16)(e->center_x - ELEVATOR_HALF_W);
        i16 right = (i16)(left + ELEVATOR_WIDTH_PX);
        i16 surface = (i16)(e->y - ELEVATOR_OBJECT_H);
        // Overlap EXACTE amb l'ample d'en Jake (PW=16): ha de coincidir amb el
        // test de persistència de main.c (px+PW). Amb +24 hi havia una franja
        // de 8px on aterrava 1 sol frame (flaix idle en caigudes del shaft).
        if ((i16)(player_x + 16) <= left || player_x >= right) continue;
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
