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

static const u8* b5_trig_ptr(u8 col, u8 row) {
    u8 t;
    if (col >= LEVEL_MAP_W || row >= LEVEL_MAP_H) return 0;
    t = MAP_PTR[((u16)row << 7) + col];
    return &TRIG_PTR[((u16)t << 3) + ((u16)t << 1)];
}

static u8 b5_tile_type(u8 col, u8 row) {
    const u8* p = b5_trig_ptr(col, row);
    return p ? p[0] : 0;
}

static void b5_set_tile(u8 col, u8 row, u8 new_tile) {
    u8 i;
    if (col >= LEVEL_MAP_W || row >= LEVEL_MAP_H) return;
    MAP_MUT[((u16)row << 7) + col] = new_tile;
    i = s_rep_n;
    if (i < 3) {
        s_rep_col[i] = col;
        s_rep_row[i] = row;
        s_rep_tile[i] = new_tile;
        s_rep_pages[i] = 3;
        s_rep_n = (u8)(i + 1);
    }
}

static void b5_world_reset_tile(u8 col, u8 row) {
    const u8* mp;
    u8 n, m, c;
    if (col >= LEVEL_MAP_W || row >= LEVEL_MAP_H) return;
    mp = &MAP_PTR[((u16)row << 7) + col];
    n = *mp;
    for (c = (u8)(col + 1); c < LEVEL_MAP_W; c++) {
        m = *++mp;
        if (m != n) {
            b5_set_tile(col, row, m);
            return;
        }
    }
}

static u8  s_popup_timer;
static u8  s_popup_idx;
static i16 s_popup_wx;
static i16 s_popup_wy;
static u8  s_popup_drawn[2];
static u16 s_popup_dst[2][7];
static u8  s_popup_bg[2][28];

void moving_bank_init(void) {
    u8 i;

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

    s_popup_timer = 0;
    s_popup_drawn[0] = s_popup_drawn[1] = 0;

#if LEVEL_INST_TILE != 0
    // Ubicar l'instrument col·leccionable obligatori del nivell a la seva sala
    MAP_MUT[(LEVEL_INST_ROW << 7) + LEVEL_INST_COL] = LEVEL_INST_TILE;
#endif

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
    }
}

void moving_bank_popup_restore(void) {
    u8 page = (u8)bc_a;
    u8 r;
    const u16* dst_p;
    const u8* bg_p;
    if (page > 1 || !s_popup_drawn[page]) return;
    dst_p = s_popup_dst[page];
    bg_p = s_popup_bg[page];
    for (r = 0; r < 7; r++) {
        g_moving_dst = *dst_p++;
        g_moving_background = (u16)bg_p;
        g_moving_span = 4;
        moving_restore_span();
        bg_p += 4;
    }
    s_popup_drawn[page] = 0;
}

void moving_bank_push(void) {
    u8 row = (u8)bc_c;
    const u8* p0 = b5_trig_ptr((u8)bc_a, row);
    const u8* p1 = b5_trig_ptr((u8)bc_b, row);
    i8 direction = 0;
    if (p0 && p1) {
        u8 op0 = p0[2];
        u8 op1 = p1[2];
        if (op0 == 27 || op1 == 27) direction++;
        if (op0 == 28 || op1 == 28) direction--;
    }
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
        u8 row, step;

        e->delta_y = 0;
        e->frame = 0;

        if (e->wait < ELEVATOR_WAIT) {
            e->wait++;
            continue;
        }

        row = (u8)(e->y >> 4);
        step = (((e->anim_tick & 7) < 3) ? 3 : 2);
        if (e->direction < 0) {
            if (row >= 4 && b5_tile_type(e->map_col, (u8)(row - 4)) == 10) {
                e->direction = 1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y - step);
            e->delta_y = (i16)-(i8)step;
        } else {
            if (b5_tile_type(e->map_col, (u8)(row + 1)) == 10) {
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
        u8 s;
        s_conveyor_tick = 0;
        if (++s_conveyor_phase >= 6) {
            s_conveyor_phase = 0;
        }
        for (s = 0; s < LEVEL_ANIM_SPAN_COUNT; s++) {
            const LevelAnimSpan* sp = &s_level_anim_spans[s];
            u8 tile = s_level_anim_seqs[sp->seq][s_conveyor_phase];
            u8* dst = &MAP_MUT[((u16)sp->row << 7) + sp->col_start];
            u8 n = (u8)(sp->col_end - sp->col_start + 1);
            while (n--) *dst++ = tile;
        }
    }

    if (s_popup_timer) {
        s_popup_timer--;
        s_popup_wy--;
    }
}

static void b5_check_bonus_triggers(u8 col, u8 row, i16 px, i16 py, u8 crouch) {
    const u8* tp = b5_trig_ptr(col, row);
    u8 b6, idx;
    const LevelTriggerEntry* e;

    if (!tp) return;
    b6 = tp[6];
    if (b6 == 255 && !crouch && row > 0) {
        row--;
        tp = b5_trig_ptr(col, row);
        if (!tp) return;
        b6 = tp[6];
    }
    if (b6 >= 64) return;
    idx = s_b6_to_trig3[b6];
    if (idx == 0xFF) return;

    e = &s_level_trig3[idx];
    if (e->kind == 11) {
        if (e->popup_or_chk && !g_checkpoint) {
            g_checkpoint = e->popup_or_chk;
        }
        if (e->exit_flag) {
            if (g_has_instrument == (LEVEL_ID + 1) && !g_level_complete) {
                g_level_complete = 1;
                b5_set_tile(col, row, e->bg_tile);
                if (e->special_anim == 21) s_dance_timer = 52;
                if (s_carry_kind) carry_abort();
            }
            return;
        }
        b5_set_tile(col, row, e->bg_tile);
    } else if (e->kind == 12) {
        b5_set_tile(col, row, e->bg_tile);
        if (e->popup_or_chk < LEVEL_POPUP_COUNT) {
            s_popup_idx = e->popup_or_chk;
            s_popup_wx = (i16)(px & ~1);
            s_popup_wy = (i16)(py - 8);
            s_popup_timer = 30;
        }
    } else {
        return;
    }

    if (e->add_vinyls) {
        u8 v = (u8)(g_vinyls_count + e->add_vinyls);
        if (v >= 100) {
            v = (u8)(v - 100);
            if (g_hearts_count < 5) g_hearts_count++;
        }
        g_vinyls_count = v;
    }
    if (e->sub_vinyls) {
        g_vinyls_count = (g_vinyls_count > e->sub_vinyls)
                       ? (u8)(g_vinyls_count - e->sub_vinyls) : 0;
    }
    if (e->add_heart && g_hearts_count < 5) {
        g_hearts_count++;
    }
    if (e->add_life && g_lives_count < 99) {
        g_lives_count++;
    }
    if (e->instrument && !g_has_instrument) {
        g_has_instrument = e->instrument;
    }
    if (e->special_anim == 21) {
        s_dance_timer = 52;
    }
}

void moving_bank_update(void) {
    u8 jump = (u8)bc_b;
    u8 crouch = (u8)bc_c;
    u8 grab = (u8)bc_d;
    u8 climbing = 0;
    i16 px, py, belt_push = 0;
    u8 col, row, tt;

    b5_update_entities_and_spans();

    py = (i16)(s_py8 >> 3);
    px = (i16)(s_px8 >> 3);

    if (s_dance_timer) {
        s_dance_timer--;
        s_vx = 0;
        bc_r = 0;
        return;
    }

    col = (u8)((px + 8) >> 3);
    row = (u8)((py + PH - 1) >> 4);

    // --- Triggers d'ítems: vinils (+1/-10), interrogants (?), cors, 1-Up, guitarra i meta ---
    b5_check_bonus_triggers(col, row, px, py, crouch);
    if (s_dance_timer) {
        s_vx = 0;
        bc_r = 0;
        return;
    }

    // --- Escala (tt==7 -> climbing=1) i Aigua/Peixera (tt==11 -> climbing=2) ---
    tt = b5_tile_type(col, row);
    if (tt != 7 && b5_tile_type(col, (u8)((py + PH) >> 4)) == 7) tt = 7;
    if (tt == 7 || tt == 11) {
        climbing = (tt == 7) ? 1 : 2;
        if (s_carry_kind) carry_abort();
        if (tt == 7) {
            if (s_climb_prev != 1) {
                px = (i16)(((u16)col << 3) - 4);
                s_px8 = (i16)(px * SUB);
            }
            s_on_ground = 0;
        }
        if (jump) {
            u8 arow = (u8)(((tt == 7) ? (py - 2) : (py + 12)) >> 4);
            u8 ok = (b5_tile_type(col, arow) == tt);
            s_vy = (tt == 7) ? (ok ? -19 : -10) : (ok ? -12 : 0);
            s_on_ground = 0;
        } else if (crouch) {
            s_vy = (tt == 7) ? 19 : 16;
        } else if (tt == 11 && !s_on_ground) {
            s_vy = 8;
        }
        s_ground_elevator = -1;
    }

    // --- Grab / release d'objectes del mapa (globus=8, paraigua=9, caixa=5) ---
    if (!s_carry_kind && !climbing && (tt == 8 || tt == 9)) {
        b5_world_reset_tile(col, row);
        if (row > 0) b5_world_reset_tile(col, (u8)(row - 1));
        s_carry_kind = (tt == 8) ? 2 : 8;
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
        } else if (!s_carry_kind && crouch && s_on_ground && tt == 5) {
            b5_world_reset_tile(col, row);
            s_carry_kind = 1; s_carry_state = 0;
            s_anim_idx = 0; s_anim_timer = 0;
        }
    }
    s_grab_prev = grab;

    if (s_on_ground) {
        bc_a = (u8)((px + 3) >> 3);
        bc_b = col;
        bc_c = (u8)((py + PH) >> 4);
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
            u8 bcol = (u8)(((s_px8 >> 3) + 8) >> 3);
            u8 brow = (u8)((bb >> 4) - 2);
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
        const u8* tp = b5_trig_ptr((u8)((px + 8) >> 3), (u8)((py + 16) >> 4));
        u8 avt = tp ? tp[9] : 255;
        if (avt >= 12 && avt <= 17) {
            g_grate_enable = 1;
            g_grate_phase_x = (u8)((px >> 1) & 1);
            g_grate_base_y = (u8)(py & 7);
        } else {
            g_grate_enable = 0;
        }
    }

    // 4. Dibuixar sprite emergent (popup -10, -20, +50) si està actiu i visible
    if (s_popup_timer && page <= 1) {
        i16 view_x = (i16)(g_cam_x4 << 2);
        i16 view_y = (i16)(g_cam_row << 3);
        if (s_popup_wx >= view_x && s_popup_wx + 8 <= view_x + 160 &&
            s_popup_wy >= view_y && s_popup_wy + 7 <= view_y + 160) {
            u8 r;
            const u8* spr = s_popup_sprites[s_popup_idx];
            u16* dst_p = s_popup_dst[page];
            u8* bg_p = s_popup_bg[page];
            for (r = 0; r < 7; r++) {
                u16 dst = (u16)ring_address(page, s_popup_wx, (i16)(s_popup_wy + r));
                *dst_p++ = dst;
                g_moving_dst = dst;
                g_moving_background = (u16)bg_p;
                g_moving_sprite = (u16)spr;
                g_moving_span = 4;
                moving_blit_span();
                bg_p += 4;
                spr += 8;
            }
            s_popup_drawn[page] = 1;
        }
    }
}
