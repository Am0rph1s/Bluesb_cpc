// ============================================================
// level_code.c - Els MECANISMES del nivell (ascensors / premses), al Banc 1 (C1)
// ------------------------------------------------------------
// Nivell 1: 5 ascensors (tipus 7, ENEMI1.SQV f0, 16x14 px = 8 bytes x 14 línies).
// Nivell 2: 3 premses hidràuliques (tipus 22, ENEMI2.SQV f33, 24x33 px = 12 bytes x 33 línies).
// Ambdós comparteixen el Banc 1 (C1:0x6E20 per al frame i C1:0x7000 per als buffers de fons).
// ============================================================
#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"
#include "level_params.h"

// --- Dades del mateix Banc 1 --------------------------------------------
#define LC_FRAMES_BASE  ((const u8*)0x6900)   // ELEV.BIN o PRESS.BIN
#define LC_BG_BASE      ((u8*)0x6D00)         // buffers de fons

// Globals del resident (RAM baixa: visibles des de qualsevol banc)
extern u16 g_moving_dst;
extern u16 g_moving_background;
extern u16 g_moving_sprite;
extern u8  g_moving_span;
extern u8  g_moving_rows;
extern u8  g_moving_spr_skip;
extern MovingElevator g_mag_elevators[MAG_MOVER_COUNT];

static u16 s_mover_dst[2][MAG_ELEVATOR_COUNT];
extern LevelParams s_lv;          // parametres del nivell (RAM baixa)

#define LC_ELEV_BG_SIZE  (ELEVATOR_W_BYTES * ELEVATOR_H)  // 8 * 14 = 112
#define LC_PRESS_BG_SIZE (12 * 33)                         // 12 * 33 = 396

void lc_elev_restore_c(void) {
    u8 page = (u8)bc_a;
    u8 is_press = (s_lv.level_id == 1);
    u8 count = is_press ? 3 : MAG_ELEVATOR_COUNT;
    u8 mover_base = is_press ? MAG_ELEVATOR_COUNT : 0;
    u16 bg_size = is_press ? LC_PRESS_BG_SIZE : LC_ELEV_BG_SIZE;
    u8 i;

    if (page > 1) return;
    for (i = count; i > 0; i--) {
        u8 idx = (u8)(i - 1);
        MovingElevator* e = &g_mag_elevators[mover_base + idx];
        if (!e->drawn[page]) continue;
        g_moving_dst = s_mover_dst[page][idx];
        g_moving_background = (u16)(LC_BG_BASE + (u16)idx * 2u * bg_size + (u16)page * bg_size);
        g_moving_span = e->drawn_byte_count[page];
        g_moving_rows = e->drawn_row_count[page];
        moving_restore_box();
        e->drawn[page] = 0;
    }
}

void lc_elev_draw_c(void) {
    u8 page = (u8)bc_a;
    u16 cam_x4 = bc_b;
    u16 cam_row = bc_c;
    u8 is_press = (s_lv.level_id == 1);
    u8 count = is_press ? 3 : MAG_ELEVATOR_COUNT;
    u8 mover_base = is_press ? MAG_ELEVATOR_COUNT : 0;
    u16 bg_size = is_press ? LC_PRESS_BG_SIZE : LC_ELEV_BG_SIZE;
    u8 spr_w_bytes = is_press ? 12 : ELEVATOR_W_BYTES;
    u8 spr_w_px = (u8)(spr_w_bytes << 1);
    u8 spr_half_w = (u8)(spr_w_bytes);
    u8 spr_h = is_press ? 33 : ELEVATOR_H;
    u8 spr_stride_bytes = (u8)(spr_w_bytes << 1); // 16 per elev, 24 per press (inv_mask + data)
    u8 i;
    i16 view_x = (i16)(cam_x4 << 2);
    i16 view_y = (i16)(cam_row << 3);

    if (page > 1) return;

    for (i = 0; i < count; i++) {
        MovingElevator* e = &g_mag_elevators[mover_base + i];
        i16 world_x, world_y, clip_x0, clip_x1, clip_y0, clip_y1;
        u8 start_byte, byte_count, start_row, row_count;

        if (i >= s_lv.elev_count) break;
        if (e->drawn[page]) continue;

        world_x = (i16)(e->center_x - spr_half_w);
        world_y = (i16)(e->y - (is_press ? PRESS_OBJECT_H : ELEVATOR_OBJECT_H));
        clip_x0 = world_x > view_x ? world_x : view_x;
        clip_x1 = (i16)(world_x + spr_w_px) < (i16)(view_x + 160) ?
                  (i16)(world_x + spr_w_px) : (i16)(view_x + 160);
        clip_y0 = world_y > view_y ? world_y : view_y;
        clip_y1 = (i16)(world_y + spr_h) < (i16)(view_y + 160) ?
                  (i16)(world_y + spr_h) : (i16)(view_y + 160);
        if (clip_x0 >= clip_x1 || clip_y0 >= clip_y1) continue;

        start_byte = (u8)((clip_x0 - world_x) >> 1);
        byte_count = (u8)((clip_x1 - clip_x0) >> 1);
        start_row = (u8)(clip_y0 - world_y);
        row_count = (u8)(clip_y1 - clip_y0);
        if (!byte_count || !row_count) continue;

        g_moving_dst = (u16)ring_address(page, clip_x0, clip_y0);
        s_mover_dst[page][i] = g_moving_dst;
        g_moving_background = (u16)(LC_BG_BASE + (u16)i * 2u * bg_size + (u16)page * bg_size);
        g_moving_sprite = (u16)(LC_FRAMES_BASE + ((u16)start_row * (u16)spr_stride_bytes) + (start_byte << 1));
        g_moving_span = byte_count;
        g_moving_rows = row_count;
        g_moving_spr_skip = (u8)(spr_stride_bytes - (byte_count << 1));
        moving_blit_box();

        e->drawn_byte_count[page] = byte_count;
        e->drawn_row_count[page] = row_count;
        e->drawn[page] = 1;
    }
}
