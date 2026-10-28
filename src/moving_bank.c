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
// TRIG compacte (5 B/entrada): type, flags, op, b6, avt (a s_lv.trig_off).
#define TP_B6   3
#define TP_AVT  4

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

// 1:1 DOS init_level(): la part que reinicia el MON (no els comptadors).
// El DOS re-inicialitza TOTS els objectes a cada reinici de nivell; aqui
// això son les plataformes/ascensors, els popups, les fases de les cintes i
// el tile de l'instrument. Els comptadors (vides/cors/discos/checkpoint)
// els porta main.c, que es qui sap si es un arrencada o un reinici per mort.
void moving_bank_respawn(void) {
    u8 i;

    s_popup_timer = 0;
    s_popup_drawn[0] = s_popup_drawn[1] = 0;

#if LEVEL_INST_TILE != 0
    // Ubicar l'instrument col·leccionable obligatori del nivell a la seva sala
    MAP_MUT[(LEVEL_INST_ROW << 7) + LEVEL_INST_COL] = LEVEL_INST_TILE;
#endif

    s_conveyor_phase = 0;
    s_conveyor_tick = 0;
    s_page_conveyor_phase[0] = s_page_conveyor_phase[1] = 0xFF;

#if LEVEL_ELEVATOR_COUNT > 0
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
#endif

    // Premses (op11): van despres dels ascensors al mateix array. El DOS
    // (objects.c object_func_op11) inicialitza elevator_direction = -1 i
    // moving_direction = 0 -> puja fins que hi ha un tile de tipus 10 quatre
    // files per damunt, espera 40 passos, baixa fins que hi ha un tile de
    // tipus 10 dues files per sota i torna a pujar.
#if LEVEL_PRESS_COUNT > 0
    for (i = 0; i < LEVEL_PRESS_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[MAG_ELEVATOR_COUNT + i];
        e->center_x = s_bank_press_x[i];
        e->y = s_bank_press_y[i];
        e->delta_y = 0;
        e->direction = -1;
        e->map_col = s_bank_press_map_col[i];
        e->wait = 0;
        e->anim_tick = 0;
        e->frame = 0;
        e->drawn[0] = e->drawn[1] = 0;
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

void moving_bank_find(void) {
    u8 i;
    if ((i16)bc_d < 0) { bc_r = -1; return; }

    // Cada família parteix de la SEVA base (l'e continuat de l'original
    // fallava amb ELEVATOR_COUNT=0: a L2 mirava els slots 0..2 buits en
    // comptes de les premses 5..7 i no s'hi podia aterrar).
#if LEVEL_ELEVATOR_COUNT > 0
    {
        const MovingElevator* e = g_mag_elevators;
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
    }
#endif

    // Premses (op11): la superficie on el jugador hi puja es el cap de
    // l'objecte (level_obj_h[22] = 30 al DOS).
#if LEVEL_PRESS_COUNT > 0
    {
        const MovingElevator* e = &g_mag_elevators[MAG_ELEVATOR_COUNT];
        for (i = 0; i < LEVEL_PRESS_COUNT; i++, e++) {
            if ((u16)(e->center_x - bc_a + 8) < 33) {
                i16 surface = (i16)(e->y - PRESS_OBJECT_H);
                if ((i16)bc_b <= (i16)(surface + 8) && (i16)bc_c >= surface) {
                    *(i16*)bc_e = (i16)(surface - 30);
                    bc_r = (i8)(MAG_ELEVATOR_COUNT + i);
                    return;
                }
            }
        }
    }
#endif
    bc_r = -1;
}

static void b5_update_entities_and_spans(void) {
    u8 i;
    // 1:1 DOS: ascensors (op4, puja 3/2 px, gaps 4/1, wait 33) i premses
    // (op11, puja 2 / baixa 4 px, gaps 4/2, wait 40). Una branca per nivell
    // (C5 d'L2 anava ple): sense paràmetres ni branques en temps d'execució.
#if LEVEL_ELEVATOR_COUNT == 0 && LEVEL_PRESS_COUNT > 0
    // Només premses (L2).
    for (i = 0; i < LEVEL_PRESS_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[MAG_ELEVATOR_COUNT + i];
        u8 row;
        e->delta_y = 0;
        if (e->wait < 40) { e->wait++; continue; }
        row = (u8)(e->y >> 4);
        if (e->direction < 0) {
            if (row >= 4 && b5_tile_type(e->map_col, (u8)(row - 4)) == 10) {
                e->direction = 1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y - 2);
            e->delta_y = -2;
        } else {
            if (b5_tile_type(e->map_col, (u8)(row + 2)) == 10) {
                e->direction = -1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y + 4);
            e->delta_y = 4;
        }
    }
#elif LEVEL_PRESS_COUNT == 0 && LEVEL_ELEVATOR_COUNT > 0
    // Només ascensors (L1).
    for (i = 0; i < LEVEL_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        u8 row, step;
        e->delta_y = 0;
        e->frame = 0;
        if (e->wait < ELEVATOR_WAIT) { e->wait++; continue; }
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
        e->anim_tick++;
    }
#else
    // Nivells futurs amb tots dos: cos compartit amb paràmetres.
    for (i = 0; i < LEVEL_ELEVATOR_COUNT + LEVEL_PRESS_COUNT; i++) {
        MovingElevator* e;
        u8 is_press, wait_max, up_step, down_step, gap_up, gap_down, row, step;
        is_press = (i >= LEVEL_ELEVATOR_COUNT);
        e = is_press ? &g_mag_elevators[MAG_ELEVATOR_COUNT + (u8)(i - LEVEL_ELEVATOR_COUNT)] : &g_mag_elevators[i];
        wait_max = is_press ? 40 : ELEVATOR_WAIT;
        gap_up = 4;
        gap_down = is_press ? 2 : 1;
        e->delta_y = 0;
        if (!is_press) e->frame = 0;
        if (e->wait < wait_max) { e->wait++; continue; }
        row = (u8)(e->y >> 4);
        if (is_press) { up_step = 2; down_step = 4; }
        else { step = (((e->anim_tick & 7) < 3) ? 3 : 2); up_step = step; down_step = step; }
        if (e->direction < 0) {
            if (row >= gap_up && b5_tile_type(e->map_col, (u8)(row - gap_up)) == 10) {
                e->direction = 1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y - up_step);
            e->delta_y = (i8)-(i8)up_step;
        } else {
            if (b5_tile_type(e->map_col, (u8)(row + gap_down)) == 10) {
                e->direction = -1;
                e->wait = 1;
                continue;
            }
            e->y = (i16)(e->y + down_step);
            e->delta_y = (i8)down_step;
        }
        if (!is_press) e->anim_tick++;
    }
#endif

    // Tick d'anims 1:1 DOS al resident (C5 ple): seqüències exactes amb el
    // seu propi període (2/3/4/20). bc_a=spans, bc_b=n, bc_c=data,
    // bc_d=offs, bc_e=lens. El repintat de sota usa el mateix indexat.
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

#if LEVEL_ID == 2
static void b5_set_tile_at(u8 col, u8 row, u8 tile, u8 room) {
    if (!room) {
        b5_set_tile(col, row, tile);
        return;
    }
    {
        u16 off = (u16)s_lv.rooms_off +
                  s_lv.room_rowoff[row - s_lv.room_row0] + col;
        ((u8*)(u16)s_lv.rooms_off)[off] = tile;
        if (s_rep_n < 4) {
            s_rep_col[s_rep_n] = col;
            s_rep_row[s_rep_n] = row;
            s_rep_tile[s_rep_n] = tile;
            s_rep_pages[s_rep_n] = 3;
            s_rep_n++;
        }
    }
}

static void b5_apply_trig3(const LevelTriggerEntry* e, u8 col, u8 row,
                           i16 px, i16 py, u8 room) {
    if (e->kind == 11) {
        if (e->popup_or_chk && !g_checkpoint) {
            g_checkpoint = e->popup_or_chk;
        }
        if (e->exit_flag) {
            if (g_has_instrument == (LEVEL_ID + 1) && !g_level_complete) {
                g_level_complete = 1;
                b5_set_tile_at(col, row, e->bg_tile, room);
                if (e->special_anim == 21) s_dance_timer = 52;
                if (s_carry_kind) carry_abort();
            }
            return;
        }
        b5_set_tile_at(col, row, e->bg_tile, room);
    } else if (e->kind == 12) {
        b5_set_tile_at(col, row, e->bg_tile, room);
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
    if (e->add_heart && g_hearts_count < 5) g_hearts_count++;
    if (e->add_life && g_lives_count < 99) g_lives_count++;
    if (e->instrument && !g_has_instrument) g_has_instrument = e->instrument;
    if (e->special_anim == 21) s_dance_timer = 52;
}

static void b5_room_check(u8 col, u8 row, i16 px, i16 py) {
    u16 off;
    u8 b6, idx, tile;
    if (row < s_lv.room_row0 || row >= (u8)(s_lv.room_row0 + s_lv.room_rows) ||
        col >= s_lv.room_total_cols) return;
    off = (u16)s_lv.rooms_off + s_lv.room_rowoff[row - s_lv.room_row0] + col;
    tile = ((const u8*)(u16)s_lv.rooms_off)[off];
    b6 = ((const u8*)(u16)s_lv.trig_off)[(u16)tile * 5u + TP_B6];
    if (b6 >= 64) return;
    idx = s_b6_to_trig3[b6];
    if (idx == 0xFF) return;
    b5_apply_trig3(&s_level_trig3[idx], col, row, px, py, 1);
}

static void b5_check_bonus_triggers(u8 col, u8 row, i16 px, i16 py, u8 crouch) {
    const u8* tp;
    u8 b6, idx;
    const LevelTriggerEntry* e;

    if (row >= s_lv.room_row0) {
        b5_room_check(col, row, px, py);
        return;
    }
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
    if (b6 == 2 || b6 == 3 || b6 == 4) {
        acid_hurt((b6 == 2) ? -56 : (b6 == 3) ? -40 : -20);
        return;
    }
#endif
    if (b6 >= 64) return;
    idx = s_b6_to_trig3[b6];
    if (idx == 0xFF) return;
    e = &s_level_trig3[idx];
    b5_apply_trig3(e, col, row, px, py, 0);
}
#else
static void b5_check_bonus_triggers(u8 col, u8 row, i16 px, i16 py, u8 crouch) {
    const u8* tp = b5_trig_ptr(col, row);
    u8 b6, idx;
    const LevelTriggerEntry* e;

    if (!tp) return;
    b6 = tp[TP_B6];
    if (b6 == 255 && !crouch && row > 0) {
        row--;
        tp = b5_trig_ptr(col, row);
        if (!tp) return;
        b6 = tp[TP_B6];
    }
#if LEVEL_HAS_ACID
    if (b6 == 2 || b6 == 3 || b6 == 4) {
        acid_hurt((b6 == 2) ? -56 : (b6 == 3) ? -40 : -20);
        return;
    }
#endif
    if (b6 >= 64) return;
    idx = s_b6_to_trig3[b6];
    if (idx == 0xFF) return;
    e = &s_level_trig3[idx];
    if (e->kind == 11) {
        if (e->popup_or_chk && !g_checkpoint) g_checkpoint = e->popup_or_chk;
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
    if (e->add_heart && g_hearts_count < 5) g_hearts_count++;
    if (e->add_life && g_lives_count < 99) g_lives_count++;
    if (e->instrument && !g_has_instrument) g_has_instrument = e->instrument;
    if (e->special_anim == 21) s_dance_timer = 52;
}
#endif

#if LEVEL_SWITCH_COUNT > 0
// Switch/palança: aplica el bloc d'estat que el DOS tria (p[0]-1) amb
// triggers_update_tiles2, pero nomes un cop per contacte (latch).
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

// Sostre (is_floor_solid amb vy<0): ops de plataforma sempre solides.
static u8 b5_solid_ceil(u8 col, u8 row) {
    const u8* tp = b5_trig_ptr(col, row);
    u8 op;
    if (!tp) return 0;
    op = tp[2];
    return (op == 0 || op == 2 || op == 3 || op == 20 || op == 21 ||
            op == 27 || op == 28 || op == 29);
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

    // 1:1 DOS unk2E: l'alçada d'ajupit es manté fins que el cap pot aixecar-se
    // (sostre sobre el cap a les dues columnes del jugador). Així, si es deixa
    // d'ajupir dins un espai baix, el jugador continua ajupit al mateix lloc.
    if (crouch) {
        s_crouch_hold = 1;
    } else if (s_crouch_hold &&
               !b5_solid_ceil((u8)((px + 1) >> 3), (u8)(py >> 4)) &&
               !b5_solid_ceil((u8)((px + 14) >> 3), (u8)(py >> 4))) {
        s_crouch_hold = 0;
    }

    if (s_dance_timer) {
        s_dance_timer--;
        s_vx = 0;
        bc_r = 0;
        g_belt_push = 0;
        return;
    }

    col = (u8)((px + 8) >> 3);
    row = (u8)((py + PH - 1) >> 4);
    // DOS op30 i op36..39 posen unk2D=2 (acceleracio 2 en lloc de 10):
    // gel i terra mullat de les dutxes es comporten igual. op32..35 son
    // rampes (unk2D=0, lliscament propi) i no entren aqui.
    {
        const u8* fp = b5_trig_ptr(col, row);
        u8 op = fp ? fp[2] : 255;
        g_on_ice = (op == 30 || (op >= 36 && op <= 39)) ? 1 : 0;
    }

    // --- TUBERIA (op 17/18/19): 1:1 DOS trigger_func_op17/18/19 (tiles.c) ---
    // El trigger s'aplica al tile on es troba el jugador (columna del centre,
    // fila dels peus). Si el jugador puja amb força (vy < -2 px/frame) el
    // trigger li dona un impuls cap amunt (vy -= 3) i posa yacc = -3 (el
    // motor fa la gravetat invertida: s_pipe_up). Tambe l'alinea
    // horitzontalment: (xpos & ~15) + 7 (op17) / +17 (op18) / -1 (op19).
    // (El DOS treballa en 16 px per tile i nosaltres en 8: les correccions
    // d'X es multipliquen per 4 (subpixels per pixel DOS).)
    s_pipe_up = 0;
    {
        const u8* tp = b5_trig_ptr(col, row);
        u8 op = tp ? tp[2] : 255;
        if (op == 17 || op == 18 || op == 19) {
            if (s_vy < -2 * SUB) {
                s_vy = (i16)(s_vy - 3 * SUB);
                s_pipe_up = 1;
                s_px8 = (i16)((s_px8 & ~63) +
                               (op == 17 ? 28 : (op == 18 ? 68 : -4)));
            }
        }
    }

    // --- Triggers d'ítems: vinils (+1/-10), interrogants (?), cors, 1-Up, guitarra i meta ---
    b5_check_bonus_triggers(col, row, px, py, crouch);
#if LEVEL_SWITCH_COUNT > 0
    // Palanques/comportes: mirar el tile dels peus i el de sobre (DOS
    // triggers_update_tiles1 comprova ypos16 i ypos16-1).
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
    if (s_dance_timer) {
        s_vx = 0;
        bc_r = 0;
        g_belt_push = 0;
        return;
    }

    // --- Escala (tt==7), reixa de L3 (tt==6) i Aigua/Peixera (tt==11) ---
    // DOS level.c do_level_fixup_object_unkA: type 6 i 7 son tots dos
    // escalables (sprite_type 3 i 2). El 7 alinea l'X al centre del tile;
    // el 6 NO, i per tant s'hi pot entrar/sortir pels costats (L3).
    // DOS level.c do_level_fixup_object_unkA: l'escala/reixa nomes s'activa
    // quan el tile dels PEUS es 7/6. No n'hi ha prou que el cap o el cos en
    // toquin una: si hi ha una escala sota una altra, el Jake ha de poder
    // caminar i saltar normalment fins que hi entra amb els peus.
    tt = b5_tile_type(col, row);
    if (tt == 6 || tt == 7 || tt == 11) {
        climbing = (tt == 11) ? 2 : 1;
        s_climb_t6 = (tt == 6);
        // 1:1 DOS level.c:504-506: a l'escala només cauen globus (grab_type 2)
        // i paraigua (grab_type 8); la caixa (grab_type 0) es queda al cap
        // i puja/baixa amb anim 24/4. Abans s'esborrava sempre.
        if (s_carry_kind == 2 || s_carry_kind == 8) carry_abort();
        if (tt == 7) {
            if (s_climb_prev != 1) {
                px = (i16)(((u16)col << 3) - 4);
                s_px8 = (i16)(px * SUB);
            }
            s_on_ground = 0;
        } else if (tt == 6) {
            // Reixa de L3: sense imant horitzontal (DOS no fa el snap del 7).
            s_on_ground = 0;
        }
        if (jump) {
            s_vy = (tt == 11) ? -12 : -24;
            s_on_ground = 0;
        } else if (crouch) {
            s_vy = (tt == 11) ? 16 : 24;
        } else if (tt == 11 && !s_on_ground) {
            s_vy = 8;
        } else if (tt == 6 || tt == 7) {
            s_vy = 0;
        }
        s_ground_elevator = -1;
    }

    // --- Grab / release d'objectes del mapa (globus=8, paraigua=9, caixa=5) ---
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
    if (grab && !s_grab_prev && !climbing) {
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
            // Deixar anar el paraigües: NO abortem el blit (sprite_abort
            // nomes neteja els flags i deixaria el sprite a pantalla).
            // El restore normal del frame seguent torna el fons correcte.
            s_carry_kind = 0;
#endif
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

    // --- Cintes transportadores (op 27/28): 1:1 DOS trigger_func_op27/28
    // (tiles.c:404-437) -> unk1C = ±4 (empenya el jugador). Al port el
    // push es calcula a cada frame si s_on_ground (main.c:1160 via bc_r).
    // Abans belt_push es perdia si s_on_ground==0 (salt/caiguda): el jugador
    // "deixava de ser arrossegat" sense motiu. Ara persisteix fins que surt
    // de la cinta (push==0) o no es a terra.
    if (s_on_ground) {
        bc_a = (u8)((px + 3) >> 3);
        bc_b = col;
        bc_c = (u8)((py + PH) >> 4);
        moving_bank_push();
        if (bc_r != 0) belt_push = bc_r;
        else belt_push = 0;
    } else {
        g_on_ice = 0;
    }
    // Fora de terra: mantenir l'ultim push (DOS unk1C persisteix).
    s_climb_prev = climbing;
    g_belt_push = belt_push;
    bc_r = belt_push;
}

void moving_bank_conveyor(void) {
    u8 page = (u8)bc_a;
    u8 s, c;

    // 1. Repintar spans animats visibles (cintes + àcid + aigua + vores).
    // Mateix indexat que el tick (stamp mod len per resta; vegeu anim_tick_c5).
    u8 cur_phase = s_conveyor_phase;
    u8 need_redraw = 0;
    if (page == 0) {
        if (s_page_conveyor_phase[0] != cur_phase) {
            s_page_conveyor_phase[0] = cur_phase;
            need_redraw = 1;
        }
    } else if (page == 1) {
        if (s_page_conveyor_phase[1] != cur_phase) {
            s_page_conveyor_phase[1] = cur_phase;
            need_redraw = 1;
        }
    }
    if (need_redraw) {
        const AnimSpan* sp = s_level_anim_spans;
        for (s = 0; s < LEVEL_ANIM_SPAN_COUNT; s++, sp++) {
            u8 tile;
            u8 qq, L, p;
            if ((u16)(((u16)sp->row << 1) - g_cam_row + 1) >= 21) continue;
            qq = sp->seq;
            L = s_anim_len[qq];
            p = cur_phase;
            while (p >= L) p -= L;
            tile = s_anim_data[s_anim_off[qq] + p];
            for (c = sp->col_start; c <= sp->col_end; c++) {
                if ((u16)(((u16)c << 1) - g_cam_x4 + 1) >= 41) continue;
                render_tile_world(tile, c, sp->row, g_cam_x4, g_cam_row);
            }
        }
    }

    // 2. Globus: vol lliure i POP només en tocar sostre dur real (op == 20..28) o sortida
#if LEVEL_HAS_BALLOON
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
#endif

    // 3. Reixes de primer pla dirigides pel TRIG compacte (avt 12..17)
    // 1:1 DOS level.c:2062 (foreground_tile_num -> sprite FG de l'AVT del
    // nivell). La LUT procedural actual (_grate_lut) és la reixa d'L1
    // (AVTMAG); a L2+ els mateixos índexs són altres gràfics (AVTENT...).
    // Fins tenir FG real per nivell, només L1 l'activa: a L2 no hi ha cap
    // reixa i pintar-hi la d'L1 és inventar.
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
