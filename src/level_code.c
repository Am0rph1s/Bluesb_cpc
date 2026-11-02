// ============================================================================
// level_code.c - Codi auxiliar del nivell (Banc 1, 0x6000..0x67FF)
//
// Rutines que nomes calen per a nivells concrets i que alliberen espai del
// resident (Bloc 0):
//   - Ascensors magnetics / Premses / Bastides (dibuix, fons i restauracio)
//   - S'executa amb Banc 1 actiu a 0x4000..0x7FFF (Bank C1).
// ============================================================================
#include "cpctelera.h"
#include "moving.h"
#include "sprite.h"
#include "level_params.h"

#ifndef LEVEL_ID
#define LEVEL_ID 0
#endif

// --- Dades del mateix Banc 1 --------------------------------------------
#if LEVEL_ID == 4
#define LC_FRAMES_BASE  ((const u8*)0x6B00)   // SCAFFOLD.BIN a C1:0x6B00
#define LC_BG_BASE      ((u8*)0x6D20)         // buffers de fons
#else
#define LC_FRAMES_BASE  ((const u8*)0x6900)   // ELEV.BIN o PRESS.BIN
#define LC_BG_BASE      ((u8*)0x6D00)         // buffers de fons
#endif

// Globals del resident (RAM baixa: visibles des de qualsevol banc)
extern u16 g_moving_dst;
extern u16 g_moving_background;
extern u16 g_moving_sprite;
extern u8  g_moving_span;
extern u8  g_moving_rows;
extern u8  g_moving_spr_skip;
extern MovingElevator g_mag_elevators[MAG_MOVER_COUNT];

static u16 s_mover_dst[2][MAG_MOVER_COUNT];
#if LEVEL_ID == 4
static i8  s_scaffold_slot[2][MAG_MOVER_COUNT];
static const u16 s_scaff_slot_off[4] = { 0, 528, 1056, 1584 };
#endif
extern LevelParams s_lv;          // parametres del nivell (RAM baixa)

#if LEVEL_ID == 4
// Nivell 5: Bastides (Scaffolds)
#define LC_MOVER_COUNT       7
#define LC_MOVER_BASE        0
#define LC_BG_SIZE           264
#define LC_SPR_W_BYTES       12
#define LC_SPR_H             22
#define LC_OBJ_H             SCAFFOLD_OBJECT_H               // 20
#elif LEVEL_ID == 1
// Nivell 2: Premses (Presses)
#define LC_MOVER_COUNT       3
#define LC_MOVER_BASE        MAG_ELEVATOR_COUNT
#define LC_BG_SIZE           396
#define LC_SPR_W_BYTES       12
#define LC_SPR_H             33
#define LC_OBJ_H             PRESS_OBJECT_H                  // 30
#else
// Nivell 1: Ascensors (Elevators)
#define LC_MOVER_COUNT       MAG_ELEVATOR_COUNT
#define LC_MOVER_BASE        0
#define LC_BG_SIZE           (ELEVATOR_W_BYTES * ELEVATOR_H) // 8 * 14 = 112
#define LC_SPR_W_BYTES       ELEVATOR_W_BYTES
#define LC_SPR_H             ELEVATOR_H                      // 14
#define LC_OBJ_H             ELEVATOR_OBJECT_H               // 14
#endif

#define LC_SPR_W_PX          (LC_SPR_W_BYTES << 1)
#define LC_SPR_HALF_W        (LC_SPR_W_BYTES)
#define LC_SPR_STRIDE_BYTES  (LC_SPR_W_BYTES << 1)

void lc_elev_restore_c(void) {
    u8 page = (u8)bc_a;
    u8 i;

    if (page > 1) return;
    for (i = LC_MOVER_COUNT; i > 0; i--) {
        u8 idx = (u8)(i - 1);
        MovingElevator* e = &g_mag_elevators[LC_MOVER_BASE + idx];
        u16 bg_addr;
        if (!e->drawn[page]) continue;
        g_moving_dst = s_mover_dst[page][idx];
#if LEVEL_ID == 4
        {
            u8 slot = (u8)s_scaffold_slot[page][idx];
            bg_addr = (u16)((u16)LC_BG_BASE + s_scaff_slot_off[slot & 3] + (page ? 264 : 0));
        }
#else
        bg_addr = (u16)(LC_BG_BASE + (u16)idx * (2u * LC_BG_SIZE) + (u16)page * LC_BG_SIZE);
#endif
        g_moving_background = bg_addr;
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
#if LEVEL_ID == 4
    u8 next_scaffold_slot = 0;
#endif
    u8 i;
    i16 view_x = (i16)(cam_x4 << 2);
    i16 view_y = (i16)(cam_row << 3);

    if (page > 1) return;

    for (i = 0; i < LC_MOVER_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[LC_MOVER_BASE + i];
        i16 world_x, world_y, clip_x0, clip_x1, clip_y0, clip_y1;
        u8 start_byte, byte_count, start_row, row_count;

        if (e->drawn[page]) continue;

        world_x = (i16)(e->center_x - LC_SPR_HALF_W);
        world_y = (i16)(e->y - LC_OBJ_H);
        clip_x0 = world_x > view_x ? world_x : view_x;
        clip_x1 = (i16)(world_x + LC_SPR_W_PX) < (i16)(view_x + 160) ?
                  (i16)(world_x + LC_SPR_W_PX) : (i16)(view_x + 160);
        clip_y0 = world_y > view_y ? world_y : view_y;
        clip_y1 = (i16)(world_y + LC_SPR_H) < (i16)(view_y + 160) ?
                  (i16)(world_y + LC_SPR_H) : (i16)(view_y + 160);
        if (clip_x0 >= clip_x1 || clip_y0 >= clip_y1) continue;

        start_byte = (u8)((clip_x0 - world_x) >> 1);
        byte_count = (u8)((clip_x1 - clip_x0) >> 1);
        start_row = (u8)(clip_y0 - world_y);
        row_count = (u8)(clip_y1 - clip_y0);
        if (byte_count == 0 || row_count == 0) continue;

        s_mover_dst[page][i] = (u16)ring_address(page, clip_x0, clip_y0);
        g_moving_dst = s_mover_dst[page][i];
#if LEVEL_ID == 4
        if (next_scaffold_slot >= 4) continue;
        s_scaffold_slot[page][i] = (i8)next_scaffold_slot;
        g_moving_background = (u16)((u16)LC_BG_BASE + s_scaff_slot_off[next_scaffold_slot] + (page ? 264 : 0));
        next_scaffold_slot++;
#else
        g_moving_background = (u16)(LC_BG_BASE + (u16)i * (2u * LC_BG_SIZE) + (u16)page * LC_BG_SIZE);
#endif
#if LEVEL_ID == 4
        g_moving_sprite = (u16)(LC_FRAMES_BASE + (((u16)start_row << 4) + ((u16)start_row << 3)) + (start_byte << 1));
#else
        g_moving_sprite = (u16)(LC_FRAMES_BASE + ((u16)start_row * (u16)LC_SPR_STRIDE_BYTES) + (start_byte << 1));
#endif
        g_moving_span = byte_count;
        g_moving_rows = row_count;
        g_moving_spr_skip = (u8)(LC_SPR_STRIDE_BYTES - (byte_count << 1));
        moving_blit_box();

        e->drawn_byte_count[page] = byte_count;
        e->drawn_row_count[page] = row_count;
        e->drawn[page] = 1;
    }
}

#if LEVEL_ID == 4
extern void render_tile_world(u8 tile_index, u16 col, u16 row, u16 cam_x4, u16 cam_row);
extern u16 g_cam_x4;
extern u16 g_cam_row;

static const u8 s_l5_anim_data[15] = { 92, 93, 94, 86, 88, 90, 88, 90, 86, 87, 89, 91, 87, 89, 91 };
static const u8 s_l5_anim_off[3] = { 0, 3, 9 };
static const u8 s_l5_anim_len[3] = { 3, 6, 6 };

static const AnimSpan s_l5_anim_spans[18] = {
    { 12,  71,  71, 1 }, { 12,  72,  72, 2 }, { 12,  73,  73, 1 }, { 12,  74,  74, 2 },
    { 12,  75,  75, 1 }, { 12,  76,  76, 2 }, { 12,  77,  77, 1 }, { 12,  78,  78, 2 },
    { 12,  79,  79, 1 }, { 12,  80,  80, 2 }, { 19,  97,  97, 1 }, { 19,  98,  98, 2 },
    { 45, 116, 116, 0 }, { 48, 124, 124, 0 }, { 57,  89,  89, 1 }, { 57,  90,  90, 2 },
    { 65,  44,  44, 1 }, { 65,  45,  45, 2 }
};

void lc_conveyor_draw_c(void) {
    u8 page = (u8)bc_a;
    if (page < 2 && s_page_conveyor_phase[page] != s_conveyor_phase) {
        u8 s;
        u8 dirty[3];
        u8 cur_tile[3];
        const AnimSpan* sp = s_l5_anim_spans;
        u8 lo = (u8)(g_cam_x4 >> 1);
        u8 hi = (u8)((g_cam_x4 + 39) >> 1);
        s_page_conveyor_phase[page] = s_conveyor_phase;

        for (s = 0; s < 3; s++) {
            u8 p = s_anim_pos[s];
            u8 prev = (p == 0) ? (u8)(s_l5_anim_len[s] - 1) : (u8)(p - 1);
            u8 off = s_l5_anim_off[s];
            u8 t = s_l5_anim_data[off + p];
            cur_tile[s] = t;
            dirty[s] = (t != s_l5_anim_data[off + prev]);
        }

        for (s = 0; s < 18; s++, sp++) {
            u8 qq = sp->seq;
            if (dirty[qq]) {
                u16 sy = (u16)(((u16)sp->row << 1) - g_cam_row);
                if (sy < 20) {
                    u8 c = sp->col_start;
                    if (c >= lo && c <= hi) {
                        render_tile_world(cur_tile[qq], c, sp->row, g_cam_x4, g_cam_row);
                    }
                }
            }
        }
    }
}
#else
void lc_conveyor_draw_c(void) {}
#endif
