// ============================================================
// moving_bank.c - Mòdul de Nivell i Entitats al Banc 5 (CP-2.2)
// ------------------------------------------------------------
// Aquest mòdul s'enllaça a 0x6E00 (finestra 0x4000, Banc 5) i
// conté les particularitats del nivell (src/level_pkg.h generat per
// tools/pack_level.py), l'animació de tiles basada en TRIG.BIN,
// els ascensors/entitats i els efectes dels tiles sobre en Jake.
// Com que viu al Banc 5 (0xC5), el mapa (0x4000) i el TRIG compacte
// (trig_off de LevelParams) estan mapejats directament sense commutar bancs.
// ============================================================

#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"
#include "level_pkg.h"
#include "level_params.h"

#define MAP_PTR  ((const u8*)0x4000)
#define MAP_MUT  ((u8*)0x4000)
#define TP_B6   3
#define TP_AVT  4

#define SUB           8
#define PH            30
#define ELEVATOR_WAIT 33

extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);

extern const u8* b5_trig_ptr(u8 col, u8 row);
extern u8 b5_tile_type(u8 col, u8 row);
extern void b5_set_tile(u8 col, u8 row, u8 new_tile);
extern void b5_world_reset_tile(u8 col, u8 row);
extern void moving_bank_push(void);

static u8  s_popup_timer;
static u8  s_popup_idx;
static i16 s_popup_wx;
static i16 s_popup_wy;
u8  s_popup_drawn[2];
u16 s_popup_dst[2];
u8  s_popup_bg[2][28];

void moving_bank_respawn(void) {
    u8 i;
    MovingElevator* e;

    s_popup_timer = 0;
    s_popup_drawn[0] = s_popup_drawn[1] = 0;

#if LEVEL_INST_TILE != 0
    MAP_MUT[(LEVEL_INST_ROW << 7) + LEVEL_INST_COL] = LEVEL_INST_TILE;
#endif

    s_conveyor_phase = 0;
    s_conveyor_tick = 0;
    s_page_conveyor_phase[0] = s_page_conveyor_phase[1] = 0xFF;

    __asm
    ld hl, #_g_mag_elevators
    ld (hl), #0
    ld de, #_g_mag_elevators + 1
    ld bc, #127
    ldir
    __endasm;

#if LEVEL_SCAFFOLD_COUNT > 0
    e = g_mag_elevators;
    for (i = 0; i < LEVEL_SCAFFOLD_COUNT; i++, e++) {
        e->center_x = s_bank_start_x[i];
        e->y = s_bank_start_y[i];
        e->direction = -1;
        e->map_col = s_bank_map_col[i];
    }
#elif LEVEL_ELEVATOR_COUNT > 0
    e = g_mag_elevators;
    for (i = 0; i < LEVEL_ELEVATOR_COUNT; i++, e++) {
        e->center_x = s_bank_start_x[i];
        e->y = s_bank_start_y[i];
        e->direction = -1;
        e->map_col = s_bank_map_col[i];
    }
#endif

#if LEVEL_PRESS_COUNT > 0
    e = &g_mag_elevators[MAG_ELEVATOR_COUNT];
    for (i = 0; i < LEVEL_PRESS_COUNT; i++, e++) {
        e->center_x = s_bank_press_x[i];
        e->y = s_bank_press_y[i];
        e->direction = -1;
        e->map_col = s_bank_press_map_col[i];
    }
#endif
}

void moving_bank_init(void) {
    g_cam_x4 = LEVEL_CAM0_X4;
    g_cam_row = LEVEL_CAM0_ROW;
    s_px8 = (i16)(LEVEL_START_PX * SUB);
    s_py8 = (i16)(LEVEL_START_PY * SUB);

    g_vinyls_count = 0;
    g_hearts_count = 3;
    g_lives_count = 3;
    g_has_instrument = 0;
    g_level_complete = 0;
    g_checkpoint = 0;
    s_dance_timer = 0;

    moving_bank_respawn();
}

void moving_bank_find(void) __naked {
#if LEVEL_SCAFFOLD_COUNT == 0 && LEVEL_ELEVATOR_COUNT == 0 && LEVEL_PRESS_COUNT == 0
    __asm
    ld hl, #-1
    ld (_bc_r), hl
    ret
    __endasm;
#else
    __asm
    ld hl, (_bc_d)
    bit 7, h
    jr z, mbf_start$
mbf_none$:
    ld hl, #-1
    ld (_bc_r), hl
    ret
mbf_start$:
    push ix
    __endasm;

#if LEVEL_SCAFFOLD_COUNT > 0
    __asm
    ld ix, #_g_mag_elevators
    ld b, #LEVEL_SCAFFOLD_COUNT
    ld c, #0
mbf_scaff_loop$:
    ; Check X: (u16)(center_x - bc_a + 20) < 41
    ld l, 0 (ix)
    ld h, 1 (ix)
    ld de, (_bc_a)
    or a
    sbc hl, de
    ld de, #20
    add hl, de
    ld de, #41
    or a
    sbc hl, de
    jr nc, mbf_scaff_next$
    ; surface = e->y - 20 (SCAFFOLD_OBJECT_H)
    ld l, 2 (ix)
    ld h, 3 (ix)
    ld de, #-20
    add hl, de
    ; check bc_b <= surface + 8  <=>  (surface + 8) - bc_b >= 0
    push hl
    ld de, #8
    add hl, de
    ld de, (_bc_b)
    or a
    sbc hl, de
    pop hl
    jp m, mbf_scaff_next$
    ; check bc_c >= surface  <=>  bc_c - surface >= 0
    ld de, (_bc_c)
    ex de, hl
    or a
    sbc hl, de
    jp m, mbf_scaff_next$
    ; Found! *(i16*)bc_e = surface - 30
    ex de, hl
    ld de, #-30
    add hl, de
    ld de, (_bc_e)
    ld a, l
    ld (de), a
    inc de
    ld a, h
    ld (de), a
    ; bc_r = c
    ld l, c
    ld h, #0
    ld (_bc_r), hl
    pop ix
    ret
mbf_scaff_next$:
    ld de, #16
    add ix, de
    inc c
    djnz mbf_scaff_loop$
    __endasm;
#elif LEVEL_ELEVATOR_COUNT > 0
    __asm
    ld ix, #_g_mag_elevators
    ld b, #LEVEL_ELEVATOR_COUNT
    ld c, #0
mbf_elev_loop$:
    ; Check X: (u16)(center_x - bc_a + 8) < 33
    ld l, 0 (ix)
    ld h, 1 (ix)
    ld de, (_bc_a)
    or a
    sbc hl, de
    ld de, #8
    add hl, de
    ld de, #33
    or a
    sbc hl, de
    jr nc, mbf_elev_next$
    ; surface = e->y - 14 (ELEVATOR_OBJECT_H)
    ld l, 2 (ix)
    ld h, 3 (ix)
    ld de, #-14
    add hl, de
    ; check bc_b <= surface + 8  <=>  (surface + 8) - bc_b >= 0
    push hl
    ld de, #8
    add hl, de
    ld de, (_bc_b)
    or a
    sbc hl, de
    pop hl
    jp m, mbf_elev_next$
    ; check bc_c >= surface  <=>  bc_c - surface >= 0
    ld de, (_bc_c)
    ex de, hl
    or a
    sbc hl, de
    jp m, mbf_elev_next$
    ; Found! *(i16*)bc_e = surface - 30
    ex de, hl
    ld de, #-30
    add hl, de
    ld de, (_bc_e)
    ld a, l
    ld (de), a
    inc de
    ld a, h
    ld (de), a
    ; bc_r = c
    ld l, c
    ld h, #0
    ld (_bc_r), hl
    pop ix
    ret
mbf_elev_next$:
    ld de, #16
    add ix, de
    inc c
    djnz mbf_elev_loop$
    __endasm;
#endif

#if LEVEL_PRESS_COUNT > 0
    __asm
    ld ix, #(_g_mag_elevators + 16 * MAG_ELEVATOR_COUNT)
    ld b, #LEVEL_PRESS_COUNT
    ld c, #MAG_ELEVATOR_COUNT
mbf_press_loop$:
    ; Check X: (u16)(center_x - bc_a + 8) < 33
    ld l, 0 (ix)
    ld h, 1 (ix)
    ld de, (_bc_a)
    or a
    sbc hl, de
    ld de, #8
    add hl, de
    ld de, #33
    or a
    sbc hl, de
    jr nc, mbf_press_next$
    ; surface = e->y - 30 (PRESS_OBJECT_H)
    ld l, 2 (ix)
    ld h, 3 (ix)
    ld de, #-30
    add hl, de
    ; check bc_b <= surface + 8  <=>  (surface + 8) - bc_b >= 0
    push hl
    ld de, #8
    add hl, de
    ld de, (_bc_b)
    or a
    sbc hl, de
    pop hl
    jp m, mbf_press_next$
    ; check bc_c >= surface  <=>  bc_c - surface >= 0
    ld de, (_bc_c)
    ex de, hl
    or a
    sbc hl, de
    jp m, mbf_press_next$
    ; Found! *(i16*)bc_e = surface - 30
    ex de, hl
    ld de, #-30
    add hl, de
    ld de, (_bc_e)
    ld a, l
    ld (de), a
    inc de
    ld a, h
    ld (de), a
    ; bc_r = c
    ld l, c
    ld h, #0
    ld (_bc_r), hl
    pop ix
    ret
mbf_press_next$:
    ld de, #16
    add ix, de
    inc c
    djnz mbf_press_loop$
    __endasm;
#endif

    __asm
    pop ix
    jr mbf_none$
    __endasm;
#endif
}

static void b5_update_entities_and_spans(void) {
    u8 i;
#if LEVEL_SCAFFOLD_COUNT > 0
    MovingElevator* e = g_mag_elevators;
    for (i = 0; i < LEVEL_SCAFFOLD_COUNT; i++, e++) {
        u8 row;
        i8 dir;
        e->delta_y = 0;
        e->frame = 0;
        if (e->wait < 40) { e->wait++; continue; }
        row = (u8)(e->y >> 4);
        dir = e->direction;
        if (dir < 0) {
            if (row >= 3 && b5_tile_type(e->map_col, (u8)(row - 3)) == 1) {
                e->direction = 1; e->wait = 1; continue;
            }
            e->delta_y = -2;
        } else {
            if (b5_tile_type(e->map_col, (u8)(row + 1)) == 1) {
                e->direction = -1; e->wait = 1; continue;
            }
            e->delta_y = 2;
        }
        e->y = (i16)(e->y + e->delta_y);
    }
#elif LEVEL_ELEVATOR_COUNT == 0 && LEVEL_PRESS_COUNT > 0
    MovingElevator* e = &g_mag_elevators[MAG_ELEVATOR_COUNT];
    for (i = 0; i < LEVEL_PRESS_COUNT; i++, e++) {
        u8 row;
        e->delta_y = 0;
        if (e->wait < 40) { e->wait++; continue; }
        row = (u8)(e->y >> 4);
        if (e->direction < 0) {
            if (row >= 4 && b5_tile_type(e->map_col, (u8)(row - 4)) == 10) {
                e->direction = 1; e->wait = 1; continue;
            }
            e->delta_y = -2;
        } else {
            if (b5_tile_type(e->map_col, (u8)(row + 2)) == 10) {
                e->direction = -1; e->wait = 1; continue;
            }
            e->delta_y = 4;
        }
        e->y = (i16)(e->y + e->delta_y);
    }
#elif LEVEL_PRESS_COUNT == 0 && LEVEL_ELEVATOR_COUNT > 0
    MovingElevator* e = g_mag_elevators;
    for (i = 0; i < LEVEL_ELEVATOR_COUNT; i++, e++) {
        u8 row;
        e->delta_y = 0;
        e->frame = 0;
        if (e->wait < ELEVATOR_WAIT) { e->wait++; continue; }
        row = (u8)(e->y >> 4);
#if LEVEL_ID == 5
        if (e->direction < 0) {
            if (row >= 5 && b5_tile_type(e->map_col, (u8)(row - 5)) != 0) {
                e->direction = 1; e->wait = 1; continue;
            }
            e->delta_y = -2;
        } else {
            if (b5_tile_type(e->map_col, (u8)(row + 1)) != 0) {
                e->direction = -1; e->wait = 1; continue;
            }
            e->delta_y = 2;
        }
#else
        {
            u8 step = (((e->anim_tick & 7) < 3) ? 3 : 2);
            if (e->direction < 0) {
                if (row >= 4 && b5_tile_type(e->map_col, (u8)(row - 4)) == 10) {
                    e->direction = 1; e->wait = 1; continue;
                }
                e->delta_y = (i8)-(i8)step;
            } else {
                if (b5_tile_type(e->map_col, (u8)(row + 1)) == 10) {
                    e->direction = -1; e->wait = 1; continue;
                }
                e->delta_y = (i8)step;
            }
        }
#endif
        e->y = (i16)(e->y + e->delta_y);
        e->anim_tick++;
    }
#endif

    bc_a = (u16)s_level_anim_spans;
    bc_b = LEVEL_ANIM_SPAN_COUNT;
    bc_c = (u16)s_anim_data;
    bc_d = (u16)s_anim_off;
    bc_e = (u16)s_anim_len;
    anim_tick_c5();

    if (s_popup_timer) {
        s_popup_timer--;
        s_popup_wy--;
    }
}

static void b5_check_bonus_triggers(u8 col, u8 row, u8 crouch) {
    const u8* tp;
    u8 b6, idx;
    const LevelTriggerEntry* e;

    if (row >= s_lv.room_row0) return;
    tp = b5_trig_ptr(col, row);
    if (!tp) return;
    b6 = tp[TP_B6];
    if (b6 == 255 && !crouch && row > 0) {
        row--;
        tp = b5_trig_ptr(col, row);
        if (!tp) return;
        b6 = tp[TP_B6];
    }
#if LEVEL_HAS_ACID
    if (b6 >= 2 && b6 <= 5) {
        acid_hurt((b6 == 2) ? -56 : (b6 == 3) ? -40 : -20);
        return;
    }
#endif
    if (b6 >= 64) return;
    idx = s_b6_to_trig3[b6];
    if (idx == 0xFF) return;
    e = &s_level_trig3[idx];

    if (e->exit_flag) {
        if (g_has_instrument != (LEVEL_ID + 1) || g_level_complete) return;
        g_level_complete = 1;
        if (s_carry_kind) carry_abort();
    }
    b5_set_tile(col, row, e->bg_tile);
    if (e->kind == 12 && e->popup_or_chk < LEVEL_POPUP_COUNT) {
        s_popup_idx = e->popup_or_chk;
        s_popup_wx = (i16)((s_px8 >> 3) & ~1);
        s_popup_wy = (i16)((s_py8 >> 3) - 8);
        s_popup_timer = 30;
    } else if (e->popup_or_chk && !g_checkpoint) {
        g_checkpoint = e->popup_or_chk;
    }
    if (e->add_vinyls) {
        u8 v = (u8)(g_vinyls_count + e->add_vinyls);
        if (v >= 100) { v = (u8)(v - 100); if (g_hearts_count < 5) g_hearts_count++; }
        g_vinyls_count = v;
    }
    if (e->sub_vinyls) {
        g_vinyls_count = (g_vinyls_count > e->sub_vinyls) ? (u8)(g_vinyls_count - e->sub_vinyls) : 0;
    }
    if (e->add_heart && g_hearts_count < 5) g_hearts_count++;
    if (e->add_life && g_lives_count < 99) g_lives_count++;
    if (e->instrument && !g_has_instrument) g_has_instrument = e->instrument;
    if (e->special_anim == 21) s_dance_timer = 52;
}

#if LEVEL_SWITCH_COUNT > 0
static u8 s_switch_lock;

static u8 b5_switch_match(u8 b6) {
    u8 i;
    for (i = 0; i < LEVEL_SWITCH_COUNT; i++) {
        if (s_switch_b6[i] == b6) return (u8)(i + 1);
    }
    return 0;
}

static void b5_apply_switch(u8 idx) {
    u8 i = (u8)(idx - 1);
    const u8* p = s_switch_changes + s_switch_off[i];
    u8 n = s_switch_nc[i];
    while (n--) {
        b5_set_tile(p[0], p[1], p[2]);
        p += 3;
    }
}
#endif

static u8 b5_solid_ceil(u8 col, u8 row) {
    const u8* tp = b5_trig_ptr(col, row);
    u8 op = tp ? tp[2] : 255;
    return (op <= 3 || op == 20 || (op >= 27 && op <= 29));
}

void moving_bank_update(void) {
    u8 jump = (u8)bc_b;
    u8 crouch = (u8)bc_c;
    u8 grab = (u8)bc_d;
    u8 climbing = 0;
    u8 col, row, tt;

    b5_update_entities_and_spans();

    if (crouch) {
        s_crouch_hold = 1;
    } else if (s_crouch_hold) {
        i16 px = (i16)(s_px8 >> 3);
        u8 cy  = (u8)(s_py8 >> 7);
        if (!b5_solid_ceil((u8)((px + 1) >> 3), cy) &&
            !b5_solid_ceil((u8)((px + 14) >> 3), cy)) {
            s_crouch_hold = 0;
        }
    }

    if (s_dance_timer || s_dying_timer) {
        if (s_dance_timer) s_dance_timer--;
        s_vx = 0;
        bc_r = 0;
        g_belt_push = 0;
        return;
    }

    col = (u8)(((s_px8 >> 3) + 8) >> 3);
    row = (u8)(((s_py8 >> 3) + PH - 1) >> 4);
    s_pipe_up = 0;
#if LEVEL_HAS_PIPE
    {
        const u8* tp = b5_trig_ptr(col, row);
        u8 op = tp ? tp[2] : 255;
        if (op >= 17 && op <= 19 && s_vy < -2 * SUB) {
            s_vy = (i16)(s_vy - 3 * SUB);
            s_pipe_up = 1;
            s_px8 = (i16)((s_px8 & ~63) +
                           (op == 17 ? 28 : (op == 18 ? 68 : -4)));
        }
    }
#endif
#if LEVEL_ID == 5
    {
        const u8* tp = b5_trig_ptr(col, row);
        u8 op = tp ? tp[2] : 255;
        g_on_ice = 0;
        if (op == 40) {
            static u16 s_concert_counter = 0;
            s_dance_timer = 2;
            s_vx = 0;
            if (s_concert_counter < 400) {
                s_concert_counter++;
            } else {
                g_level_complete = 1;
            }
        }
    }
#endif

    b5_check_bonus_triggers(col, row, crouch);

#if LEVEL_SWITCH_COUNT > 0
    {
        u8 sw = 0, b6 = 255;
        const u8* tp = b5_trig_ptr(col, row);
        if (tp) b6 = tp[TP_B6];
        sw = (b6 != 255) ? b5_switch_match(b6) : 0;
        if (!sw && row > 0) {
            tp = b5_trig_ptr(col, (u8)(row - 1));
            if (tp) b6 = tp[TP_B6];
            sw = (b6 != 255) ? b5_switch_match(b6) : 0;
        }
        if (sw) {
            if (!s_switch_lock) {
                b5_apply_switch(sw);
                s_switch_lock = 1;
            }
        } else {
            s_switch_lock = 0;
        }
    }
#endif

    tt = b5_tile_type(col, row);
#if LEVEL_HAS_WATER
    {
        u8 is_water = (tt >= 11 && tt <= 15);
        if (!is_water && s_climb_prev == 2) {
            u8 mid_tt = b5_tile_type(col, (u8)(((s_py8 >> 3) + 16) >> 4));
            if (mid_tt >= 11 && mid_tt <= 15) is_water = 1;
        }
        if (tt != 6 && tt != 7 && !is_water && !s_climb_prev && (jump || crouch)) {
            if (col > 0 && b5_tile_type((u8)(col - 1), row) == 7) { col--; tt = 7; }
            else if (b5_tile_type((u8)(col + 1), row) == 7) { col++; tt = 7; }
        }
        if (tt == 6 || tt == 7 || is_water) {
            u8 at_base = (u8)(s_on_ground && b5_solid_ceil(col, (u8)(row + 1)));
            if (tt == 6 || tt == 7) {
                if (tt == 7 && s_climb_prev != 1 && (jump || crouch)) {
                    s_px8 = (i16)((((u16)col << 3) - 4) * SUB);
                }
                if (s_climb_prev || jump || crouch || !at_base) {
                    climbing = 1;
                    s_climb_t6 = (tt == 6);
                    s_on_ground = 0;
                    if (s_carry_kind == 2 || s_carry_kind == 8) carry_abort();
                    s_vy = jump ? -16 : (crouch ? 16 : 0);
                    s_ground_elevator = -1;
                }
            } else {
                climbing = 2;
                s_climb_t6 = 0;
                s_on_ground = 0;
                if (s_carry_kind == 2 || s_carry_kind == 8) carry_abort();
                if (jump) {
                    u8 cr = (u8)(((s_py8 >> 3) + 10) >> 4);
                    if (b5_tile_type(col, cr) >= 11) {
                        s_vy = -16;
                    } else {
                        s_vy = 0;
                        s_py8 = (i16)((((cr + 1) << 4) - 8) * SUB);
                    }
                } else if (crouch) {
                    s_vy = 16;
                } else if (tt != 13) {
                    s_vy = 4;
                } else {
                    s_vy = 0;
                }
                s_ground_elevator = -1;
            }
        }
    }
#else
    if (tt != 6 && tt != 7 && !s_climb_prev && (jump || crouch)) {
        if (col > 0 && b5_tile_type((u8)(col - 1), row) == 7) { col--; tt = 7; }
        else if (b5_tile_type((u8)(col + 1), row) == 7) { col++; tt = 7; }
    }
    if (tt == 6 || tt == 7) {
        if (tt == 7 && s_climb_prev != 1 && (jump || crouch)) {
            s_px8 = (i16)((((u16)col << 3) - 4) * SUB);
        }
        if (s_climb_prev || jump || crouch || !(s_on_ground && b5_solid_ceil(col, (u8)(row + 1)))) {
            climbing = 1;
            s_climb_t6 = (tt == 6);
            s_on_ground = 0;
            if (s_carry_kind == 2 || s_carry_kind == 8) carry_abort();
            s_vy = jump ? -16 : (crouch ? 16 : 0);
            s_ground_elevator = -1;
        }
    }
#endif

#if LEVEL_HAS_BALLOON || LEVEL_HAS_UMBRELLA
    if (!s_carry_kind && !climbing &&
#if LEVEL_HAS_BALLOON && LEVEL_HAS_UMBRELLA
        (tt == 8 || tt == 9)
#elif LEVEL_HAS_BALLOON
        (tt == 8)
#else
        (tt == 9)
#endif
        ) {
        b5_world_reset_tile(col, row);
        if (row > 0) b5_world_reset_tile(col, (u8)(row - 1));
        s_carry_kind = (tt == 8) ? 2 : 8;
    }
#endif

    if (grab && !s_grab_prev && (!climbing || s_carry_kind == 1)) {
        if (s_carry_kind == 1 && !s_carry_state) {
            s_carry_x = (g_face == 0) ? (i16)(s_px8 + 8 * SUB) : (i16)s_px8;
            s_carry_y = (i16)(s_py8 - 6 * SUB);
            s_carry_vx = (g_face == 0) ? 96 : -96;
            s_carry_state = 1;
#if LEVEL_HAS_BALLOON
        } else if (s_carry_kind == 2) {
            if (!s_carry_state) {
                s_carry_x = s_px8;
                s_carry_y = s_py8;
                s_carry_state = 1;
                s_vy = 0;
            }
#endif
#if LEVEL_HAS_UMBRELLA
        } else if (s_carry_kind == 8) {
            s_carry_kind = 0;
#endif
        } else if (!s_carry_kind && s_on_ground) {
            u8 cr = row;
            if (b5_tile_type(col, cr) != 5 && row > 0) cr--;
            if (b5_tile_type(col, cr) == 5) {
                b5_world_reset_tile(col, cr);
                s_carry_kind = 1; s_carry_state = 0;
                s_anim_idx = 0; s_anim_timer = 0;
            }
        }
    }
    s_grab_prev = grab;

#if LEVEL_HAS_CONVEYOR
    if (s_on_ground) {
        bc_a = (u8)(((s_px8 >> 3) + 3) >> 3);
        bc_b = col;
        bc_c = (u8)(((s_py8 >> 3) + PH) >> 4);
        moving_bank_push();
    } else {
        g_on_ice = 0;
        bc_r = 0;
    }
    g_belt_push = bc_r;
#else
    if (!s_on_ground) g_on_ice = 0;
    g_belt_push = 0;
    bc_r = 0;
#endif
    s_climb_prev = climbing;
}

#if LEVEL_ID == 4
void moving_bank_conveyor(void) {}
#else
void moving_bank_conveyor(void) {
    u8 page = (u8)bc_a;
    if (page < 2 && s_page_conveyor_phase[page] != s_conveyor_phase) {
        u8 s;
        const AnimSpan* sp = s_level_anim_spans;
        u8 lo = (u8)(g_cam_x4 >> 1);
        u8 hi = (u8)((g_cam_x4 + 39) >> 1);
        s_page_conveyor_phase[page] = s_conveyor_phase;
        for (s = 0; s < LEVEL_ANIM_SPAN_COUNT; s++, sp++) {
            u8 qq = sp->seq;
            u8 p = s_anim_pos[qq];
            u8 prev = (p == 0) ? (u8)(s_anim_len[qq] - 1) : (u8)(p - 1);
            u8 off = s_anim_off[qq];
            u8 tile = s_anim_data[off + p];
            if (tile != s_anim_data[off + prev]) {
                u8 r = sp->row;
                if ((u16)(((u16)r << 1) - g_cam_row + 1) < 21) {
                    u8 c = sp->col_start;
                    u8 c1 = sp->col_end;
                    if (c < lo) c = lo;
                    if (c1 > hi) c1 = hi;
                    while (c <= c1) {
                        render_tile_world(tile, c, r, g_cam_x4, g_cam_row);
                        c++;
                    }
                }
            }
        }
    }

#if LEVEL_HAS_BALLOON
    if (s_carry_kind == 2) {
        if (s_carry_state == 1) {
            s_carry_y = (i16)(s_carry_y - 32);
        }
        {
            u16 cur_px = (u16)((s_carry_state ? s_carry_x : s_px8) >> 3);
            i16 cur_py = (i16)((s_carry_state ? s_carry_y : s_py8) >> 3);
            i16 b_top = (i16)(cur_py - 28);
            u8 bcol = (u8)((cur_px + 8) >> 3);
            u8 brow = (b_top > 0) ? (u8)(b_top >> 4) : 0;
            const u8* tp = b5_trig_ptr(bcol, brow);
            if (b_top <= 16 || (tp && (tp[2] == 20 || tp[2] == 21 || tp[2] == 27 || tp[2] == 28))) {
                s_carry_kind = 0;
                s_carry_state = 0;
                s_vy = 0;
            }
        }
    }
#endif

#if LEVEL_ID == 0
    {
        u16 px = (u16)(s_px8 >> 3);
        u16 py = (u16)(s_py8 >> 3);
        const u8* tp = b5_trig_ptr((u8)((px + 8) >> 3), (u8)((py + 16) >> 4));
        u8 avt = tp ? tp[TP_AVT] : 255;
        if ((u8)(avt - 12) <= 5) {
            g_grate_enable = 1;
            g_grate_phase_x = (u8)((px >> 1) & 1);
            g_grate_base_y = (u8)(py & 7);
        } else {
            g_grate_enable = 0;
        }
    }
#else
    g_grate_enable = 0;
#endif

#if LEVEL_POPUP_COUNT > 0
    if (s_popup_timer && page <= 1) {
        u16 rx = (u16)(s_popup_wx - (g_cam_x4 << 2));
        u16 ry = (u16)(s_popup_wy - (g_cam_row << 3));
        if (rx <= 152 && ry <= 153) {
            g_moving_dst = (u16)ring_address(page, s_popup_wx, s_popup_wy);
            s_popup_dst[page] = g_moving_dst;
            g_moving_background = (u16)s_popup_bg[page];
            g_moving_sprite = (u16)s_popup_sprites[s_popup_idx];
            g_moving_span = 4;
            g_moving_rows = 7;
            g_moving_spr_skip = 0;
            moving_blit_box();
            s_popup_drawn[page] = 1;
        }
    }
#endif
}

#endif // LEVEL_ID == 4
