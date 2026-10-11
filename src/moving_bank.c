// ============================================================
// moving_bank.c - Mòdul de Nivell i Entitats al Banc 5 (CP-2.2)
// ------------------------------------------------------------
// Aquest mòdul s'enllaça a 0x6E00 (finestra 0x4000, Banc 5) i
// conté les particularitats del nivell (src/level_pkg.h generat per
// tools/pack_level.py), l'animació de tiles basada en TRIG.BIN,
// els ascensors/entitats i els efectes dels tiles sobre en Jake.
// Com que viu al Banc 5 (0xC5), MAP_PTR (0x4000) i TRIG_PTR (0x6400)
// estan mapejats directament sense necessitat de commutar bancs.
// ============================================================

#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"
#include "level_pkg.h"

#define MAP_PTR  ((const u8*)0x4000)
#define MAP_MUT  ((u8*)0x4000)
#define TRIG_PTR ((const u8*)0x6400)

#define SUB           8
#define PH            30
#define ELEVATOR_WAIT 33

extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);

// --- Consultes directes al Banc 5 (MAP_PTR i TRIG_PTR ja mapejats) ---

static u8 b5_tile_type(u16 col, u16 row) {
    u8 t;
    if (col >= LEVEL_MAP_W || row >= LEVEL_MAP_H) return 0;
    t = MAP_PTR[(row << 7) + col];
    return TRIG_PTR[(((u16)t) << 3) + (((u16)t) << 1)];
}

static void b5_world_reset_tile(u16 col, u16 row) {
    u8 n, m = 0;
    u16 c;
    if (col >= LEVEL_MAP_W || row >= LEVEL_MAP_H) return;
    n = MAP_PTR[(row << 7) + col];
    c = (u16)(col + 1);
    while (c < LEVEL_MAP_W) {
        m = MAP_PTR[(row << 7) + c];
        if (m != n) break;
        c++;
    }
    if (c >= LEVEL_MAP_W) return;
    MAP_MUT[(row << 7) + col] = m;
    if (s_rep_n < 3) {
        s_rep_col[s_rep_n] = (u8)col;
        s_rep_row[s_rep_n] = (u8)row;
        s_rep_tile[s_rep_n] = m;
        s_rep_pages[s_rep_n] = 3;
        s_rep_n++;
    }
}

void moving_bank_init(void) {
    u8 i;

    g_cam_x4 = LEVEL_CAM0_X4;
    g_cam_row = LEVEL_CAM0_ROW;
    s_px8 = (i16)(LEVEL_START_PX * SUB);
    s_py8 = (i16)(LEVEL_START_PY * SUB);

    s_conveyor_phase = 0;
    s_conveyor_tick = 0;
    s_page_conveyor_phase[0] = s_page_conveyor_phase[1] = 0xFF;

    for (i = 0; i < LEVEL_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        e->center_x = s_bank_start_x[i];
        e->y = s_bank_start_y[i];
        e->delta_y = 0;
        e->direction = -1;
        e->map_col = s_bank_map_col[i];
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

void moving_bank_push(void) {
    u16 col0 = bc_a;
    u16 col1 = bc_b;
    u16 row = bc_c;
    u8 op0, op1, tile;
    u16 off;
    i8 direction = 0;

    if (row >= LEVEL_MAP_H || col0 >= LEVEL_MAP_W || col1 >= LEVEL_MAP_W) { bc_r = 0; return; }

    tile = MAP_PTR[(row << 7) + col0];
    off = (((u16)tile) << 3) + (((u16)tile) << 1);
    op0 = TRIG_PTR[off + 2];
    tile = MAP_PTR[(row << 7) + col1];
    off = (((u16)tile) << 3) + (((u16)tile) << 1);
    op1 = TRIG_PTR[off + 2];

    if (op0 == 27 || op1 == 27) direction++;
    if (op0 == 28 || op1 == 28) direction--;
    bc_r = (i16)(direction * 16);
}

void moving_bank_find(void) {
    i16 player_x = (i16)bc_a;
    i16 previous_feet = (i16)bc_b;
    i16 current_feet = (i16)bc_c;
    i16 vy = (i16)bc_d;
    i16* player_top = (i16*)bc_e;
    u8 i;
    if (vy < 0) { bc_r = -1; return; }

    for (i = 0; i < LEVEL_ELEVATOR_COUNT; i++) {
        const MovingElevator* e = &g_mag_elevators[i];
        i16 left = (i16)(e->center_x - ELEVATOR_HALF_W);
        i16 right = (i16)(left + ELEVATOR_WIDTH_PX);
        i16 surface = (i16)(e->y - ELEVATOR_OBJECT_H);
        if ((i16)(player_x + 16) <= left || player_x >= right) continue;
        if (previous_feet <= (i16)(surface + 8) && current_feet >= surface) {
            *player_top = (i16)(surface - 30);
            bc_r = (i16)(i8)i;
            return;
        }
    }
    bc_r = -1;
}

static void b5_update_entities_and_spans(void) {
    u8 i;
    for (i = 0; i < LEVEL_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        u16 row;
        i16 step;

        e->delta_y = 0;
        e->frame = 0;

        if (e->wait < ELEVATOR_WAIT) {
            e->wait++;
            continue;
        }

        row = (u16)(e->y >> 4);
        step = (((e->anim_tick & 7) < 3) ? 3 : 2);
        if (e->direction < 0) {
            if (row >= 4 && b5_tile_type(e->map_col, (u16)(row - 4)) == 10) {
                e->direction = 1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y - step);
            e->delta_y = (i16)-step;
        } else {
            if (b5_tile_type(e->map_col, (u16)(row + 1)) == 10) {
                e->direction = -1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y + step);
            e->delta_y = step;
        }

        e->frame = (u8)((e->anim_tick >> 2) & 1);
        e->anim_tick++;
    }

    if (++s_conveyor_tick >= 4) {
        u8 s, c;
        s_conveyor_tick = 0;
        if (++s_conveyor_phase >= 6) {
            s_conveyor_phase = 0;
        }
        for (s = 0; s < LEVEL_ANIM_SPAN_COUNT; s++) {
            const LevelAnimSpan* sp = &s_level_anim_spans[s];
            u8 tile = s_level_anim_seqs[sp->seq][s_conveyor_phase];
            u16 row_off = (u16)sp->row << 7;
            for (c = sp->col_start; c <= sp->col_end; c++) {
                MAP_MUT[row_off + c] = tile;
            }
        }
    }
}

void moving_bank_update(void) {
    u8 jump = (u8)bc_b;
    u8 crouch = (u8)bc_c;
    u8 grab = (u8)bc_d;
    u8 climbing = 0;
    i16 px, py, belt_push = 0;

    b5_update_entities_and_spans();

    py = (i16)(s_py8 >> 3);
    px = (i16)(s_px8 >> 3);

    // --- Escala (tt==7 -> climbing=1) i Aigua/Peixera (tt==11 -> climbing=2) ---
    {
        u16 lcol = (u16)((px + 8) >> 3);
        u8 tt = b5_tile_type(lcol, (u16)((py + PH - 1) >> 4));
        if (tt != 7 && b5_tile_type(lcol, (u16)((py + PH) >> 4)) == 7) tt = 7;
        if (tt == 7 || tt == 11) {
            climbing = (tt == 7) ? 1 : 2;
            if (s_carry_kind) carry_abort();
            if (tt == 7) {
                if (s_climb_prev != 1) {
                    px = (i16)((lcol << 3) - 4);
                    s_px8 = (i16)(px * SUB);
                }
                s_on_ground = 0;
            }
            if (jump) {
                u16 arow = (u16)(((tt == 7) ? (py - 2) : (py + 12)) >> 4);
                u8 ok = (b5_tile_type(lcol, arow) == tt);
                s_vy = (tt == 7) ? (ok ? -19 : -10) : (ok ? -12 : 0);
                s_on_ground = 0;
            } else if (crouch) {
                s_vy = (tt == 7) ? 19 : 16;
            } else if (tt == 11 && !s_on_ground) {
                s_vy = 8;
            }
            s_ground_elevator = -1;
        }
    }

    // --- Grab / release d'objectes del mapa (globus=8, paraigua=9, caixa=5) ---
    if (!s_carry_kind && !climbing) {
        u16 gcol = (u16)((px + 8) >> 3);
        u16 grow = (u16)((py + PH - 1) >> 4);
        u8 gtype = b5_tile_type(gcol, grow);
        if (gtype == 8 || gtype == 9) {
            b5_world_reset_tile(gcol, grow);
            if (grow > 0) b5_world_reset_tile(gcol, (u16)(grow - 1));
            s_carry_kind = (gtype == 8) ? 2 : 8;
        }
    }
    if (grab && !s_grab_prev && !climbing) {
        if (s_carry_kind == 1 && !s_carry_state) {
            s_carry_x = s_px8;
            s_carry_y = (i16)(s_py8 - 20 * SUB);
            s_carry_vx = (g_face == 0) ? 154 : -154;
            s_carry_drawn[0] = 0; s_carry_drawn[1] = 0;
            s_carry_state = 1;
        } else if (s_carry_kind == 2 || s_carry_kind == 8) {
            sprite_abort_balloon();
            s_carry_kind = 0;
        } else if (!s_carry_kind && crouch && s_on_ground) {
            u16 gcol = (u16)((px + 8) >> 3);
            u16 grow = (u16)((py + PH - 1) >> 4);
            if (b5_tile_type(gcol, grow) == 5) {
                b5_world_reset_tile(gcol, grow);
                s_carry_kind = 1; s_carry_state = 0;
                s_anim_idx = 0; s_anim_timer = 0;
            }
        }
    }
    s_grab_prev = grab;

    if (s_on_ground) {
        bc_a = (u16)((px + 3) >> 3);
        bc_b = (u16)((px + 8) >> 3);
        bc_c = (u16)((py + PH) >> 4);
        moving_bank_push();
        belt_push = bc_r;
    }

    s_climb_prev = climbing;
    bc_r = belt_push;
}

void moving_bank_conveyor(void) {
    u8 page = (u8)bc_a;
    u8 s, c;

    // 1. Repintar spans animats visibles (cintes + superfície d'aigua + vores)
    if (page <= 1 && s_page_conveyor_phase[page] != s_conveyor_phase) {
        for (s = 0; s < LEVEL_ANIM_SPAN_COUNT; s++) {
            const LevelAnimSpan* sp = &s_level_anim_spans[s];
            u16 subrow = (u16)sp->row << 1;
            u8 tile;
            if (subrow + 2 <= g_cam_row || subrow >= g_cam_row + 20) continue;
            tile = s_level_anim_seqs[sp->seq][s_conveyor_phase];
            for (c = sp->col_start; c <= sp->col_end; c++) {
                u16 char_x = (u16)c << 1;
                if (char_x + 2 <= g_cam_x4 || char_x >= g_cam_x4 + 40) continue;
                render_tile_world(tile, c, sp->row, g_cam_x4, g_cam_row);
            }
        }
        s_page_conveyor_phase[page] = s_conveyor_phase;
    }

    // 2. Globus: POP de sostre DOS (basat en TRIG_PTR)
    if (s_carry_kind == 2) {
        i16 bb = (i16)((s_py8 >> 3) - 1);
        u8 pop = (bb < 32);
        if (!pop) {
            u16 bcol = (u16)(((s_px8 >> 3) + 8) >> 3);
            u16 brow = (u16)((bb >> 4) - 2);
            pop = (b5_tile_type(bcol, brow) > 5);
        }
        if (pop) {
            sprite_abort_balloon();
            s_carry_kind = 0;
            s_vy = 0;
        }
    }

    // 3. Reixes de primer pla dirigides per TRIG.BIN (byte 9: avt_num 12..17)
    {
        i16 px = (i16)(s_px8 >> 3);
        i16 py = (i16)(s_py8 >> 3);
        u16 gcol = (u16)((px + 8) >> 3);
        u16 grow = (u16)((py + 16) >> 4);
        u8 avt = 255;
        if (gcol < LEVEL_MAP_W && grow < LEVEL_MAP_H) {
            u8 t = MAP_PTR[(grow << 7) + gcol];
            avt = TRIG_PTR[(((u16)t) << 3) + (((u16)t) << 1) + 9];
        }
        if (avt >= 12 && avt <= 17) {
            g_grate_enable = 1;
            g_grate_phase_x = (u8)((px >> 1) & 1);
            g_grate_base_y = (u8)(py & 7);
        } else {
            g_grate_enable = 0;
        }
    }
}
