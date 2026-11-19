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
#elif LEVEL_ID == 5
#define LC_FRAMES_BASE  ((const u8*)0x7000)   // LIFT6.BIN a C1:0x7000
#define LC_BG_BASE      ((u8*)0x7100)         // buffers de fons (224 B)
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

static u16 s_mover_dst[2][MAG_MOVER_COUNT];
#if LEVEL_ID == 4
static i8  s_scaffold_slot[2][MAG_MOVER_COUNT];
static const u16 s_scaff_slot_off[4] = { 0, 528, 1056, 1584 };
#endif

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
#elif LEVEL_ID == 5
// Nivell 6: Ascensors d'escenari (Stage Lifts)
#define LC_MOVER_COUNT       2
#define LC_MOVER_BASE        0
#define LC_BG_SIZE           (ELEVATOR_W_BYTES * ELEVATOR_H) // 8 * 14 = 112
#define LC_SPR_W_BYTES       ELEVATOR_W_BYTES
#define LC_SPR_H             ELEVATOR_H                      // 14
#define LC_OBJ_H             ELEVATOR_OBJECT_H               // 14
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

#if LEVEL_ID != 4
static u8  s_ed_page;
static u16 s_ed_vx, s_ed_vy, s_ed_bg, s_ed_dst_ptr;
static u8  s_ed_sbyte, s_ed_bcount, s_ed_srow, s_ed_rcount;
static u16 s_ed_cx0, s_ed_cy0;

void lc_elev_restore_c(void) __naked {
    __asm
#if LEVEL_ID == 1
        K_LC_CNT      = 3
        K_LC_BASE_OFF = 80
        K_LC_LAST_OFF = 32
        K_LC_FRAMES   = 0x6900
        K_LC_BG       = 0x6D00
        K_LC_BG_SIZE  = 396
        K_LC_BG_STEP  = 792
        K_LC_BG_LAST  = 0x7330
        K_LC_HALF_W   = 12
        K_LC_W_PX     = 24
        K_LC_W_BYTES  = 12
        K_LC_STRIDE   = 24
        K_LC_SPR_H    = 33
        K_LC_OBJ_H    = 30
#elif LEVEL_ID == 5
        K_LC_CNT      = 2
        K_LC_BASE_OFF = 0
        K_LC_LAST_OFF = 16
        K_LC_FRAMES   = 0x7000
        K_LC_BG       = 0x7100
        K_LC_BG_SIZE  = 112
        K_LC_BG_STEP  = 224
        K_LC_BG_LAST  = 0x71E0
        K_LC_HALF_W   = 8
        K_LC_W_PX     = 16
        K_LC_W_BYTES  = 8
        K_LC_STRIDE   = 16
        K_LC_SPR_H    = 14
        K_LC_OBJ_H    = 14
#else
        K_LC_CNT      = 5
        K_LC_BASE_OFF = 0
        K_LC_LAST_OFF = 64
        K_LC_FRAMES   = 0x6900
        K_LC_BG       = 0x6D00
        K_LC_BG_SIZE  = 112
        K_LC_BG_STEP  = 224
        K_LC_BG_LAST  = 0x7080
        K_LC_HALF_W   = 8
        K_LC_W_PX     = 16
        K_LC_W_BYTES  = 8
        K_LC_STRIDE   = 16
        K_LC_SPR_H    = 14
        K_LC_OBJ_H    = 14
#endif
        ld   a, (_bc_a)
        cp   #2
        ret  nc
        ld   (_s_ed_page), a
        push ix
        ld   ix, #(_g_mag_elevators + K_LC_BASE_OFF + K_LC_LAST_OFF)
        ld   de, #K_LC_BG_LAST
        ld   hl, #(_s_mover_dst + ((K_LC_CNT - 1) * 2))
        or   a
        jr   z, lcer_go$
        inc  ix
        push hl
        ld   hl, #K_LC_BG_SIZE
        add  hl, de
        ex   de, hl
        pop  hl
        ld   bc, #16
        add  hl, bc
    lcer_go$:
        ld   b, #K_LC_CNT
    lcer_loop$:
        ld   a, 10(ix)
        or   a
        jr   z, lcer_skip$
        ld   a, (_bc_b)
        or   a
        jr   nz, lcer_do$
        ld   a, (_s_ed_page)
        or   a
        jr   nz, lcer_do$
        ld   a, 4(ix)
        or   a
        jr   z, lcer_skip$
    lcer_do$:
        ld   10(ix), #0
        ld   a, (hl)
        ld   (_g_moving_dst), a
        inc  hl
        ld   a, (hl)
        ld   (_g_moving_dst + 1), a
        dec  hl
        ld   (_g_moving_background), de
        ld   a, 12(ix)
        ld   (_g_moving_span), a
        ld   a, 14(ix)
        ld   (_g_moving_rows), a
        push bc
        push de
        push hl
        call _moving_restore_box
        pop  hl
        pop  de
        pop  bc
    lcer_skip$:
        ex   de, hl
        push bc
        ld   bc, #-K_LC_BG_STEP
        add  hl, bc
        pop  bc
        ex   de, hl
        dec  hl
        dec  hl
        push de
        ld   de, #-16
        add  ix, de
        pop  de
        djnz lcer_loop$
        pop  ix
        ret
    __endasm;
}

void lc_elev_draw_c(void) __naked {
    __asm
        ld   a, (_bc_a)
        cp   #2
        ret  nc
        ld   (_s_ed_page), a
        push ix
        ld   hl, (_bc_b)
        add  hl, hl
        add  hl, hl
        ld   (_s_ed_vx), hl
        ld   hl, (_bc_c)
        add  hl, hl
        add  hl, hl
        add  hl, hl
        ld   (_s_ed_vy), hl

        ld   hl, #K_LC_BG
        ld   de, #_s_mover_dst
        or   a
        jr   z, lced_init_ok$
        ld   bc, #K_LC_BG_SIZE
        add  hl, bc
        ld   de, #(_s_mover_dst + 16)
    lced_init_ok$:
        ld   (_s_ed_bg), hl
        ld   (_s_ed_dst_ptr), de
        ld   ix, #(_g_mag_elevators + K_LC_BASE_OFF)
        ld   b, #K_LC_CNT

    lced_loop$:
        ld   a, (_s_ed_page)
        add  a, #10
        ld   e, a
        ld   d, #0
        push ix
        pop  hl
        add  hl, de
        ld   a, (hl)
        or   a
        jp   nz, lced_next$

        ;; world_x - view_x in [-K_LC_W_PX+1 .. 159]
        ld   l, 0(ix)
        ld   h, 1(ix)
        ld   de, #-K_LC_HALF_W
        add  hl, de
        ld   de, (_s_ed_vx)
        or   a
        sbc  hl, de
        push hl
        ld   de, #(K_LC_W_PX - 1)
        add  hl, de
        ld   de, #(160 + K_LC_W_PX - 1)
        or   a
        sbc  hl, de
        pop  hl
        jp   nc, lced_next$

        bit  7, h
        jr   z, lced_x_pos$
        ld   de, (_s_ed_vx)
        ld   (_s_ed_cx0), de
        xor  a
        sub  l
        srl  a
        ld   (_s_ed_sbyte), a
        ld   a, #K_LC_W_PX
        add  a, l
        srl  a
        or   a
        jp   z, lced_next$
        ld   (_s_ed_bcount), a
        jr   lced_y$

    lced_x_pos$:
        xor  a
        ld   (_s_ed_sbyte), a
        ld   a, l
        cp   #(160 - K_LC_W_PX + 1)
        jr   c, lced_x_full$
        ld   a, #160
        sub  l
        srl  a
        or   a
        jp   z, lced_next$
        jr   lced_x_bc$
    lced_x_full$:
        ld   a, #K_LC_W_BYTES
    lced_x_bc$:
        ld   (_s_ed_bcount), a
        ld   de, (_s_ed_vx)
        add  hl, de
        ld   (_s_ed_cx0), hl

    lced_y$:
        ;; world_y - view_y in [-K_LC_SPR_H+1 .. 159]
        ld   l, 2(ix)
        ld   h, 3(ix)
        ld   de, #-K_LC_OBJ_H
        add  hl, de
        ld   de, (_s_ed_vy)
        or   a
        sbc  hl, de
        push hl
        ld   de, #(K_LC_SPR_H - 1)
        add  hl, de
        ld   de, #(160 + K_LC_SPR_H - 1)
        or   a
        sbc  hl, de
        pop  hl
        jp   nc, lced_next$

        bit  7, h
        jr   z, lced_y_pos$
        ld   de, (_s_ed_vy)
        ld   (_s_ed_cy0), de
        xor  a
        sub  l
        ld   (_s_ed_srow), a
        ld   a, #K_LC_SPR_H
        add  a, l
        ld   (_s_ed_rcount), a
        jr   lced_draw$

    lced_y_pos$:
        xor  a
        ld   (_s_ed_srow), a
        ld   a, l
        cp   #(160 - K_LC_SPR_H + 1)
        jr   c, lced_y_full$
        ld   a, #160
        sub  l
        jr   lced_y_rc$
    lced_y_full$:
        ld   a, #K_LC_SPR_H
    lced_y_rc$:
        ld   (_s_ed_rcount), a
        ld   de, (_s_ed_vy)
        add  hl, de
        ld   (_s_ed_cy0), hl

    lced_draw$:
        push bc
        ld   hl, (_s_ed_cy0)
        push hl
        ld   de, (_s_ed_cx0)
        ld   a, (_s_ed_page)
        call _ring_address
        ld   (_g_moving_dst), de
        ld   hl, (_s_ed_dst_ptr)
        ld   (hl), e
        inc  hl
        ld   (hl), d

        ld   hl, (_s_ed_bg)
        ld   (_g_moving_background), hl

        ld   a, (_s_ed_srow)
        ld   l, a
        ld   h, #0
#if LEVEL_ID == 1
        add  hl, hl
        add  hl, hl
        add  hl, hl
        ld   d, h
        ld   e, l
        add  hl, hl
        add  hl, de
#else
        add  hl, hl
        add  hl, hl
        add  hl, hl
        add  hl, hl
#endif
        ld   a, (_s_ed_sbyte)
        add  a, a
        ld   e, a
        ld   d, #0
        add  hl, de
        ld   de, #K_LC_FRAMES
        add  hl, de
        ld   (_g_moving_sprite), hl

        ld   a, (_s_ed_bcount)
        ld   (_g_moving_span), a
        add  a, a
        ld   c, a
        ld   a, #K_LC_STRIDE
        sub  c
        ld   (_g_moving_spr_skip), a
        ld   a, (_s_ed_rcount)
        ld   (_g_moving_rows), a

        call _moving_blit_box

        push ix
        ld   a, (_s_ed_page)
        or   a
        jr   z, lced_p0$
        inc  ix
    lced_p0$:
        ld   a, (_s_ed_bcount)
        ld   12(ix), a
        ld   a, (_s_ed_rcount)
        ld   14(ix), a
        ld   10(ix), #1
        pop  ix
        pop  bc

    lced_next$:
        ld   hl, (_s_ed_bg)
        ld   de, #K_LC_BG_STEP
        add  hl, de
        ld   (_s_ed_bg), hl
        ld   hl, (_s_ed_dst_ptr)
        inc  hl
        inc  hl
        ld   (_s_ed_dst_ptr), hl
        ld   de, #16
        add  ix, de
        dec  b
        jp   nz, lced_loop$
        pop  ix
        ret
    __endasm;
}
#else
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
        {
            u8 slot = (u8)s_scaffold_slot[page][idx];
            bg_addr = (u16)((u16)LC_BG_BASE + s_scaff_slot_off[slot & 3] + (page ? 264 : 0));
        }
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
    u8 next_scaffold_slot = 0;
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
        if ((u16)(world_x - view_x + (LC_SPR_W_PX - 1)) >= (u16)(160 + LC_SPR_W_PX - 1)) continue;
        world_y = (i16)(e->y - LC_OBJ_H);
        if ((u16)(world_y - view_y + (LC_SPR_H - 1)) >= (u16)(160 + LC_SPR_H - 1)) continue;
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
        if (next_scaffold_slot >= 4) continue;
        s_scaffold_slot[page][i] = (i8)next_scaffold_slot;
        g_moving_background = (u16)((u16)LC_BG_BASE + s_scaff_slot_off[next_scaffold_slot] + (page ? 264 : 0));
        next_scaffold_slot++;
        g_moving_sprite = (u16)(LC_FRAMES_BASE + (((u16)start_row << 4) + ((u16)start_row << 3)) + (start_byte << 1));
        g_moving_span = byte_count;
        g_moving_rows = row_count;
        g_moving_spr_skip = (u8)(LC_SPR_STRIDE_BYTES - (byte_count << 1));
        moving_blit_box();

        e->drawn_byte_count[page] = byte_count;
        e->drawn_row_count[page] = row_count;
        e->drawn[page] = 1;
    }
}
#endif

void lc_conveyor_draw_c(void) {}

