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

void moving_bank_find(void) {
    u8 i;
    const MovingElevator* e = g_mag_elevators;
    if ((i16)bc_d < 0) { bc_r = -1; return; }

    for (i = 0; i < LEVEL_ELEVATOR_COUNT; i++, e++) {
        if ((u16)(e->center_x - bc_a + 8) < 33) {
            i16 surface = (i16)(e->y - ELEVATOR_OBJECT_H);
            if ((i16)bc_b <= (i16)(surface + 8) && (i16)bc_c >= surface) {
                *(i16*)bc_e = (i16)(surface - 30);
                bc_r = i;
                return;
            }
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
            e->delta_y = (i8)-(i8)step;
        } else {
            if (b5_tile_type(e->map_col, (u8)(row + 1)) == 10) {
                e->direction = -1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y + step);
            e->delta_y = (i8)step;
        }

        e->frame = (u8)((e->anim_tick >> 2) & 1);
        e->anim_tick++;
    }

    if (++s_conveyor_tick >= 4) {
        u8 s;
        const LevelAnimSpan* sp = s_level_anim_spans;
        s_conveyor_tick = 0;
        if (++s_conveyor_phase >= 6) {
            s_conveyor_phase = 0;
        }
        for (s = 0; s < LEVEL_ANIM_SPAN_COUNT; s++, sp++) {
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
    // Prioritat absoluta a l'escala sobre l'aigua si qualsevol part del cos toca un tile de tipus 7:
    if (tt != 7) {
        if (b5_tile_type(col, (u8)((py + 8) >> 4)) == 7 ||
            b5_tile_type(col, (u8)((py + 20) >> 4)) == 7 ||
            b5_tile_type(col, (u8)((py + PH) >> 4)) == 7) {
            tt = 7;
        }
    }
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
            s_vy = (tt == 7) ? -24 : -12;
            s_on_ground = 0;
        } else if (crouch) {
            s_vy = (tt == 7) ? 24 : 16;
        } else if (tt == 11 && !s_on_ground) {
            s_vy = 8;
        } else if (tt == 7) {
            s_vy = 0;
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
            s_carry_x = (g_face == 0) ? (i16)(s_px8 + 4 * SUB) : (i16)(s_px8 - 4 * SUB);
            s_carry_y = (i16)(s_py8 + 4 * SUB);
            s_carry_vx = (g_face == 0) ? 96 : -96;
            s_carry_state = 1;
        } else if (s_carry_kind == 2) {
            if (!s_carry_state) {
                s_carry_x = s_px8;
                s_carry_y = s_py8;
                s_carry_state = 1;
                s_vy = 0;
            }
        } else if (s_carry_kind == 8) {
            sprite_abort_balloon();
            s_carry_kind = 0;
        } else if (!s_carry_kind && s_on_ground) {
            u8 crate_row = row;
            if (b5_tile_type(col, crate_row) != 5 && row > 0 && b5_tile_type(col, (u8)(row - 1)) == 5) {
                crate_row = (u8)(row - 1);
            }
            if (b5_tile_type(col, crate_row) == 5) {
                b5_world_reset_tile(col, crate_row);
                s_carry_kind = 1; s_carry_state = 0;
                s_anim_idx = 0; s_anim_timer = 0;
            }
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
        const LevelAnimSpan* sp = s_level_anim_spans;
        for (s = 0; s < LEVEL_ANIM_SPAN_COUNT; s++, sp++) {
            u8 tile;
            if ((u16)(((u16)sp->row << 1) - g_cam_row + 1) >= 21) continue;
            tile = s_level_anim_seqs[sp->seq][s_conveyor_phase];
            for (c = sp->col_start; c <= sp->col_end; c++) {
                if ((u16)(((u16)c << 1) - g_cam_x4 + 1) >= 41) continue;
                render_tile_world(tile, c, sp->row, g_cam_x4, g_cam_row);
            }
        }
        s_page_conveyor_phase[page] = s_conveyor_phase;
    }

    // 2. Globus: vol lliure i POP només en tocar sostre dur real (op == 20..28) o sortida
    if (s_carry_kind == 2) {
        if (s_carry_state == 1) {
            s_carry_y = (i16)(s_carry_y - 32); // ascens lliure ràpid (4 px/frame)
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

    // 3. Reixes de primer pla dirigides per TRIG.BIN (byte 9: avt_num 12..17)
    {
        u16 px = (u16)(s_px8 >> 3);
        u16 py = (u16)(s_py8 >> 3);
        const u8* tp = b5_trig_ptr((u8)((px + 8) >> 3), (u8)((py + 16) >> 4));
        u8 avt = tp ? tp[9] : 255;
        if ((u8)(avt - 12) <= 5) {
            g_grate_enable = 1;
            g_grate_phase_x = (u8)((px >> 1) & 1);
            g_grate_base_y = (u8)(py & 7);
        } else {
            g_grate_enable = 0;
        }
    }

    // 4. Dibuixar sprite emergent (popup -10, -20, +50) si està actiu i visible
    if (s_popup_timer && page <= 1) {
        if ((u16)(s_popup_wx - (g_cam_x4 << 2)) <= 152 &&
            (u16)(s_popup_wy - (g_cam_row << 3)) <= 153) {
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
}
