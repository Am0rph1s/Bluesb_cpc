// ============================================================
// BLUES BROTHERS CPC - Motor Genèric Resident (Bloc 0)
// ============================================================
//   - video_init(): RMR Mode 0 + CRTC + paleta (protocol GA correcte)
//   - Scroll CRTC en ring de 16 KB, amb passos horitzontals de 4 px i render
//     incremental del caràcter/fila que entra.
//   - Doble buffer per maquinari (0xC000 / 0x8000) a 25 Hz sense flicker.
//   - Totes les dades específiques del nivell, ascensors, spans animats
//     (cintes + peixeres), efectes de tiles i reixes de primer pla viuen
//     al paquet del Banc 5 (src/moving_bank.c + src/level_pkg.h).
// ============================================================

#include "cpctelera.h"
#include "fdc.h"
#include "front.h"
#include "mus.h"
#include "disk_tables.h"
#include "sprite.h"
#include "moving.h"
#include "enemy.h"
#include "bank.h"
#include "player_frames.h"
#include "stack_canary.h"
#include "crt_addrs.h"

#define LEVEL_PKG_DEFS_ONLY
#include "level_pkg.h"

extern void video_init(void);
extern void render_all(u16 cam_col, u16 cam_row);
extern void render_column(u16 cam_col, u16 cam_row, u16 sx);
extern void render_row(u16 cam_col, u16 cam_row, u16 sy);
extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);
extern void hud_init(void);
extern void hud_render(u8 page, u8 force);
extern void crtc_set_display_start(u16 ma);
extern void cpc_install_isr(void);
extern volatile u8 g_ticks;

#define MAP_PTR     ((const u8*)0x4000)
#define TRIG_PTR    ((const u8*)0x6400)
#define PLAY_CHARS  40
#define SUB         8
#define PH          30
#define PW          16
#define SPR_WB      8
#define SPEED_MAX   30
#define SPEED_AIR   24
#define MOVE_ACC    7
#define VY_MAX      (15 * SUB)
#define GRAV        24
#define JUMP_VY     (-150)
#define DEAD_L      48
#define DEAD_R      88
#define DEAD_T      32
#define DEAD_B      116
#define CRATE_FLY_FRAME ((const u8*)0x7A20)

static const u8 s_crate_walk[6] = { 15, 13, 14, 16, 13, 14 };
static const u8 s_walk[6] = { 1, 2, 0, 3, 2, 0 };

// Estat compartit resident (actualitzat des del mòdul de nivell al Banc 5):
u16 g_cam_x4;
u16 g_cam_row;

i16 s_px8, s_py8;
i16 s_vx, s_vy;
u8  s_on_ground;
u8  s_jump_prev;
u8  s_climb_prev;
u8  s_carry_kind;
u8  s_grab_prev;
u8  s_up_prev;
u8  s_in_room;
u8  s_scrolling_locked;
u8  s_carry_state;
i16 s_carry_x, s_carry_y;
i16 s_carry_vx;
u8  s_carry_drawn[2];
static u8  s_carry_drawn_span[2];
static u8  s_carry_drawn_rows[2];
static u16 s_carry_dst[2];
#define CRATE_BG_PAGE(p) ((u16)(0x7380 + ((u16)(p) << 6)))

i8  s_ground_elevator = -1;
u8  g_face;
u8  s_anim_idx, s_anim_timer;
u8  s_dazed_timer;
u8  s_invuln_timer;

static u8  s_have_drawn[2];
static i8  s_pending_x, s_pending_y;

u8  s_rep_n;
u8  s_rep_col[4], s_rep_row[4], s_rep_tile[4], s_rep_pages[4];

static u8 s_back_page = 1;

void main(void);

extern void render_room(u8 room_idx);
extern void palette_black(void);
extern void palette_restore(void);

typedef struct {
    u8 src_col;
    u8 src_row;
    u8 dst_col;
    u8 dst_row;
} LevelDoor;

const u16 g_crc_fdc = CRC_FDC; // stub FDC: verifica l'scratch (moving.c)
const u16 g_len_fdc = 785; // FDC.BIN sencer (sense header); ha de coincidir
                           // amb l'obj generat (si el motor creix i el CRC
                           // falla -> white-hang: actualitzar aqui)

void start(void) {
    __asm
        ld      sp, #0x3FFE
    __endasm;
    main();
}

static const u16 s_row100[10] = { 0, 100, 200, 300, 400, 500, 600, 700, 800, 900 };

static u8 get_tile_at(u16 col, u16 row) {
    u8 prev, t;
    if (row >= 74 && row < 84 && col < 100) {
        prev = bank_set(0xC1);
        t = ((const u8*)0x6400)[s_row100[row - 74] + col];
        bank_restore(prev);
        return t;
    }
    if (col >= LEVEL_MAP_W || row >= LEVEL_MAP_H) return 0xFF;
    prev = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    bank_restore(prev);
    return t;
}

static u8 get_trig_byte(u16 col, u16 row, u8 offset) {
    u8 prev, t = get_tile_at(col, row);
    if (t == 0xFF) return 0xFF;
    prev = bank_set(0xC5);
    t = TRIG_PTR[((u16)t) * 10 + offset];
    bank_restore(prev);
    return t;
}

u8 tile_type(u16 col, u16 row) {
    u8 t = get_trig_byte(col, row, 0);
    return (t == 0xFF) ? 1 : t;
}

u8 tile_flags(u16 col, u16 row) {
    u8 t = get_trig_byte(col, row, 1);
    return (t == 0xFF) ? 0 : t;
}

u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch) {
    u8 op;
    if (row >= 74) {
        if (row >= 83) return (vy >= 0);
    } else if (row >= (LEVEL_MAP_H - 1)) {
        return (vy >= 0);
    }
    op = get_trig_byte(col, row, 2);
    if (op == 0xFF) return 0;
    if (op == 20 || op == 21 || op == 27 || op == 28) return 1;
    if (vy >= 0) {
        if (op == 14 || op == 15) return !crouch;
        if (op >= 31 && op <= 39) return 1;
    }
    return 0;
}
#define is_ceiling_solid(col, row) is_floor_solid((col), (row), -1, 0)

static void world_flush_repaints(void) {
    u8 i = 0;
    while (i < s_rep_n) {
        if (s_rep_pages[i] & (u8)((u8)1 << s_back_page)) {
            render_tile_world(s_rep_tile[i], s_rep_col[i], s_rep_row[i],
                              g_cam_x4, g_cam_row);
            s_rep_pages[i] &= (u8)~((u8)1 << s_back_page);
        }
        if (s_rep_pages[i] == 0) {
            s_rep_n--;
            if (i != s_rep_n) {
                s_rep_col[i] = s_rep_col[s_rep_n];
                s_rep_row[i] = s_rep_row[s_rep_n];
                s_rep_tile[i] = s_rep_tile[s_rep_n];
                s_rep_pages[i] = s_rep_pages[s_rep_n];
            }
        } else {
            i++;
        }
    }
}

static u16 camera_ma(u16 x4, u16 row) {
    return (u16)((row * 40 + x4) & 0x03FF);
}

static void repaint_both_buffers(void) {
    u8 p;
    g_vram_start = camera_ma(g_cam_x4, g_cam_row);
    s_pending_x = 0;
    s_pending_y = 0;
    for (p = 0; p < 2; p++) {
        g_vram_base_hi = p ? 0x80 : 0xC0;
        if (s_in_room) render_room((u8)(g_cam_x4 / 40));
        else render_all(g_cam_x4, g_cam_row);
        hud_render(p, 1);
    }
    crtc_set_display_start((u16)(0x3000 + g_vram_start));
    s_back_page = 1;
}

static void enter_door(u8 dst_col, u8 dst_row) {
    palette_black();

    // 1:1 DOS: convert dst tile to CPC coordinates
    s_px8 = (i16)(((u16)dst_col << 6) - 32);
    s_py8 = (i16)(((u16)(dst_row + 1) << 7) - 240);
    s_vx = 0;
    s_vy = 0;
    s_on_ground = 1;
    s_dazed_timer = 0;
    s_jump_prev = 0;

    if (dst_row >= 72) {
        // Entering Room
        u8 room_idx = (u8)(dst_col / 20);
        s_in_room = 1;
        s_scrolling_locked = 1;
        g_cam_x4 = (u16)(room_idx * 40);
        g_cam_row = 148;
        enemy_room_exit(0, 0);
    } else {
        // Exiting Room to main level
        i16 cam_col = (i16)dst_col - 10;
        i16 cam_r = (i16)dst_row - 6;
        s_in_room = 0;
        s_scrolling_locked = 0;

        if (cam_col < 0) cam_col = 0;
        if (cam_col > (LEVEL_MAP_W - 20)) cam_col = LEVEL_MAP_W - 20;
        g_cam_x4 = (u16)(cam_col << 1);

        if (cam_r < 0) cam_r = 0;
        if (cam_r > (LEVEL_MAX_CAM_ROW >> 1)) cam_r = (LEVEL_MAX_CAM_ROW >> 1);
        g_cam_row = (u16)(cam_r << 1);
        enemy_room_exit((i16)(s_px8 >> 3), (i16)(s_py8 >> 3));
    }
    s_have_drawn[0] = 0;
    s_have_drawn[1] = 0;
    s_carry_drawn[0] = 0;
    s_carry_drawn[1] = 0;
    s_rep_n = 0;

    repaint_both_buffers();
    if (!s_in_room) {
        moving_draw(0, g_cam_x4, g_cam_row);
        moving_draw(1, g_cam_x4, g_cam_row);
    }

    palette_restore();
}

static void check_doors(void) {
    u8 j_col = (u8)(((s_px8 >> 3) + 8) >> 3);
    u8 j_row = (u8)(((s_py8 >> 3) + 29) >> 4);
    u8 i, prev;
    const LevelDoor* d;
    prev = bank_set(0xC1);
    d = (const LevelDoor*)0x6800;
    for (i = 0; i < 23; i++, d++) {
        if (d->src_col == j_col && d->src_row == j_row) {
            u8 dc = d->dst_col;
            u8 dr = d->dst_row;
            bank_restore(prev);
            enter_door(dc, dr);
            return;
        }
    }
    bank_restore(prev);
}

static void check_room_bonus(u8 col, u8 feet_row) {
    u8 r, prev, t;
    if (col >= 100) return;
    for (r = feet_row; r >= (feet_row - 2) && r >= 74; r--) {
        if (r >= 84) continue;
        u16 off = s_row100[r - 74] + col;
        prev = bank_set(0xC1);
        t = ((const u8*)0x6400)[off];
        if (t == 208) {
            if (g_vinyls_count < 99) g_vinyls_count++;
        } else if (t == 159) {
            g_has_instrument = LEVEL_ID + 1;
        } else {
            bank_restore(prev);
            continue;
        }
        ((u8*)0x6400)[off] = 96;
        bank_restore(prev);
        if (s_rep_n < 4) {
            s_rep_col[s_rep_n] = col;
            s_rep_row[s_rep_n] = r;
            s_rep_tile[s_rep_n] = 96;
            s_rep_pages[s_rep_n] = 3;
            s_rep_n++;
        }
        break;
    }
}

static void sync_backbuffer(i8 dx, i8 dy, u16 target_x4, u16 target_row) {
    if (dx > 0) {
        if (dx > 1) render_column(target_x4, target_row, 38);
        render_column(target_x4, target_row, 39);
    } else if (dx < 0) {
        render_column(target_x4, target_row, 0);
        if (dx < -1) render_column(target_x4, target_row, 1);
    }

    if (dy > 0) {
        if (dy > 1) render_row(target_x4, target_row, 18);
        render_row(target_x4, target_row, 19);
    } else if (dy < 0) {
        render_row(target_x4, target_row, 0);
        if (dy < -1) render_row(target_x4, target_row, 1);
    }
}

static void carry_restore(u8 page) {
    u8 prev;
    if (!s_carry_drawn[page]) return;
    prev = bank_set(0xC7);
    g_moving_dst = s_carry_dst[page];
    g_moving_background = CRATE_BG_PAGE(page);
    g_moving_span = s_carry_drawn_span[page];
    g_moving_rows = s_carry_drawn_rows[page];
    moving_restore_box();
    bank_restore(prev);
    s_carry_drawn[page] = 0;
}

static void carry_draw(u8 page) {
    u8 prev;
    i16 cx, cy;
    i16 view_x, view_y, clip_x0, clip_x1, clip_y0, clip_y1;
    u8 start_byte, byte_count, start_row, row_count;

    if (s_carry_kind != 1) return;
    if (s_carry_state == 0) {
        if (s_invuln_timer & 2) return; // Parpelleig amb en Jake
        // 1:1 DOS: centrat sobre el cap (px + 4) i recolzat a les mans (py - 15)
        // Snapping horitzontal parell (& ~1) per alinear amb el byte de Mode 0 (2 px/byte)
        cx = (i16)(((s_px8 >> 3) + 4) & ~1);
        cy = (i16)((s_py8 >> 3) - 15);
    } else {
        cx = (i16)((s_carry_x >> 3) & ~1);
        cy = (i16)(s_carry_y >> 3);
    }

    view_x = (i16)(g_cam_x4 << 2);
    view_y = (i16)(g_cam_row << 3);
    clip_x0 = cx > view_x ? cx : view_x;
    clip_x1 = (i16)(cx + 8) < (i16)(view_x + 160) ? (i16)(cx + 8) : (i16)(view_x + 160);
    clip_y0 = cy > view_y ? cy : view_y;
    clip_y1 = (i16)(cy + 16) < (i16)(view_y + 160) ? (i16)(cy + 16) : (i16)(view_y + 160);

    if (clip_x0 >= clip_x1 || clip_y0 >= clip_y1) return;

    start_byte = (u8)((clip_x0 - cx) >> 1);
    byte_count = (u8)((clip_x1 - clip_x0) >> 1);
    start_row = (u8)(clip_y0 - cy);
    row_count = (u8)(clip_y1 - clip_y0);
    if (!byte_count || !row_count) return;

    prev = bank_set(0xC7);
    g_moving_dst = (u16)ring_address(page, clip_x0, clip_y0);
    s_carry_dst[page] = g_moving_dst;
    s_carry_drawn_span[page] = byte_count;
    s_carry_drawn_rows[page] = row_count;
    g_moving_background = CRATE_BG_PAGE(page);
    g_moving_sprite = (u16)(CRATE_FLY_FRAME + ((u16)start_row << 3) + (start_byte << 1));
    g_moving_span = byte_count;
    g_moving_rows = row_count;
    g_moving_spr_skip = (u8)(8 - (byte_count << 1));
    moving_blit_box();
    bank_restore(prev);
    s_carry_drawn[page] = 1;
}

void carry_abort(void) {
    s_carry_kind = 0;
    s_carry_state = 0;
    sprite_abort_balloon();
}

static u8 anim_step(u8 speed, u8 max_idx) {
    s_anim_timer++;
    if (s_anim_timer >= speed) {
        s_anim_timer = 0;
        s_anim_idx++;
        if (s_anim_idx >= max_idx) s_anim_idx = 0;
    }
    return s_anim_idx;
}

static u8 select_player_anim(u8 climbing, i8 move, u8 jump, u8 crouch, i16 bsy) {
    if (s_dazed_timer) {
        // Frames 26, 27, 28 (dazed1, dazed2, dazed3): estrelletes autèntiques DOS girant sobre el cap!
        u8 f = (u8)(s_dazed_timer >> 2);
        while (f >= 3) f -= 3;
        return (u8)(26 + f);
    }
    if (s_dance_timer) {
        return (s_dance_timer & 8) ? 10 : 11;
    }
    if (climbing == 1) {
        if (jump || crouch || move != 0) {
            s_anim_timer++;
            if (s_anim_timer >= 4) {
                s_anim_timer = 0;
                s_anim_idx ^= 1;
            }
            return s_anim_idx ? 5 : 9;
        }
        s_anim_timer = 0;
        return 5;
    }
    if (climbing == 2) {
        if (move != 0) {
            return (u8)(21 + anim_step(4, 3));
        }
        if (jump || crouch) {
            s_anim_timer++;
            if (s_anim_timer >= 4) {
                s_anim_timer = 0;
                s_anim_idx ^= 1;
            }
            return s_anim_idx ? 24 : 21;
        }
        s_anim_timer = 0;
        return s_on_ground ? 25 : 21;
    }
    if (s_carry_kind == 2 && !s_carry_state) {
        return 20;
    }
    if (s_carry_kind == 8) {
        if (!s_on_ground) return 20; // Planejar amb paraigües a l'aire (sempre frame 20)
        if (move != 0) {
            return s_crate_walk[anim_step(2, 4)];
        }
        s_anim_timer = 0;
        return 13; // Peus ferms a terra agafant el paraigües
    }
    if (s_carry_kind == 1 && !s_carry_state) {
        if (!s_on_ground) return 16;
        if (move != 0) {
            return s_crate_walk[anim_step(2, 6)];
        }
        s_anim_idx = 0;
        s_anim_timer = 0;
        return 14; // 1:1 DOS animframe_00c7 = 0x0E (14)
    }
    if (!s_on_ground || (u16)(bsy + 30) > 160) {
        return 4;
    }
    if (crouch) {
        if (move != 0) {
            s_anim_timer++;
            if (s_anim_timer >= 6) {
                s_anim_timer = 0;
                s_anim_idx ^= 1;
            }
            return s_anim_idx ? 8 : 7;
        }
        s_anim_timer = 0;
        return 6;
    }
    if (move != 0) {
        return s_walk[anim_step(2, 6)];
    }
    s_anim_idx = 0;
    s_anim_timer = 0;
    return 0;
}

static void player_physics_step(i16 belt_push, u8 climbing, u8 jump, u8 crouch) {
    i16 px = (i16)(s_px8 >> 3);
    i16 py = (i16)(s_py8 >> 3);
    i16 effective_vx = (i16)(s_vx + belt_push);

    if (s_carry_kind == 1 && s_carry_state) {
        i16 cx, cy, sx, sy;
        u16 ncol, nrow;
        u8 tt;
        s_carry_x = (i16)(s_carry_x + s_carry_vx);
        cx = (i16)(s_carry_x >> 3);
        cy = (i16)(s_carry_y >> 3);
        sx = (i16)((cx - (i16)(g_cam_x4 * 4)) >> 1);
        sy = (i16)(cy - (i16)(g_cam_row * 8));
        ncol = (u16)(((s_carry_vx > 0) ? (cx + 8) : cx) >> 3);
        nrow = (u16)((cy + 6) >> 4);
        tt = tile_type(ncol, nrow);
        if (sx < -4 || sx > 76 || sy < -16 || sy > 160 || cx < 16 || cx > (i16)(LEVEL_W_PX - 24) ||
            tt == 6 || enemy_check_crate_hit(cx, cy, s_carry_vx)) {
            carry_abort();
        }
    }

    // --- Moviment horitzontal i col·lisió de parets ---
    if (effective_vx > 0) {
        u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
        u16 c_right = (u16)((next_px + 10) >> 3);
        u8 fl = tile_flags(c_right, (u16)((py + 16) >> 4)) |
                tile_flags(c_right, (u16)(py >> 4));
        if (fl & 1) {
            s_vx = 0;
            s_px8 = (i16)(((c_right << 3) - 11) * SUB);
        } else {
            s_px8 = (i16)(s_px8 + effective_vx);
        }
    } else if (effective_vx < 0) {
        u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
        u16 c_left  = (u16)((next_px + 1) >> 3);
        u8 fl = tile_flags(c_left, (u16)((py + 16) >> 4)) |
                tile_flags(c_left, (u16)(py >> 4));
        if (fl & 2) {
            s_vx = 0;
            s_px8 = (i16)(((c_left << 3) + 8 - 1) * SUB);
        } else {
            s_px8 = (i16)(s_px8 + effective_vx);
        }
    }
    {
        i16 min_x = s_in_room ? (i16)(g_cam_x4 << 5) : 0;
        i16 max_x = s_in_room ? (i16)(min_x + 1152) : (i16)((LEVEL_W_PX - PW) * SUB);
        if (s_px8 < min_x) { s_px8 = min_x; s_vx = 0; }
        else if (s_px8 > max_x) { s_px8 = max_x; s_vx = 0; }
    }
    px = (i16)(s_px8 >> 3);

    // --- Moviment vertical i gravetat ---
    {
        i16 prev_feet = (i16)(py + PH);
        u16 prev_head = (u16)(py >> 4);
        if (!climbing) {
            if (s_carry_kind == 2 && !s_carry_state) {
                s_vy = -8;
                s_on_ground = 0;
                s_ground_elevator = -1;
            } else {
                if (!s_on_ground) {
                    s_vy = (i16)(s_vy + GRAV);
                    if (s_vy > VY_MAX) s_vy = VY_MAX;
                } else {
                    s_vy = 0;
                }
                if (jump && !s_jump_prev && s_on_ground) {
                    u16 c_mid = (u16)((px + 5) >> 3);
                    u16 feet_row = (u16)((py + 29) >> 4);
                    u8 di = (feet_row >= 2) ? tile_type(c_mid, (u16)(feet_row - 2)) : 0;
                    u8 si = tile_type(c_mid, feet_row);
                    if (di == 10 && (si == 0 || si == 1)) {
                        s_dazed_timer = 24;
                        s_vy = 0;
                        s_vx = 0;
                        if (s_carry_kind == 1 && !s_carry_state) carry_abort();
                    } else {
                        s_vy = (s_carry_kind == 1 && !s_carry_state) ? -96 : JUMP_VY;
                        s_on_ground = 0;
                        s_ground_elevator = -1;
                    }
                }
                if (s_carry_kind == 8 && s_vy > 8) s_vy = 8;
            }
        }
        s_jump_prev = jump;

        s_py8 = (i16)(s_py8 + s_vy);
        py = (i16)(s_py8 >> 3);

        {
            i16 curr_feet = (i16)(py + PH);
            u16 c_mid1 = (u16)((px + 3) >> 3);
            u16 c_mid2 = (u16)((px + 8) >> 3);
            u8 landed = 0;

            if (s_vy >= 0 && climbing != 1) {
                i16 elevator_top;
                i8 elevator_id;
                bc_a = (u16)px; bc_b = (u16)prev_feet; bc_c = (u16)curr_feet;
                bc_d = (u16)s_vy; bc_e = (u16)&elevator_top;
                elevator_id = moving_find_landing();
                if (elevator_id >= 0) {
                    py = elevator_top;
                    s_py8 = (i16)(py * SUB);
                    s_vy = 0;
                    s_on_ground = 1;
                    s_ground_elevator = elevator_id;
                    landed = 1;
                }
                {
                    u16 max_r = s_in_room ? 84 : LEVEL_MAP_H;
                    u16 target_row = (u16)(curr_feet >> 4);
                    if (!landed && target_row < max_r) {
                        i16 surf = (i16)(target_row << 4);
                        if (is_floor_solid(c_mid1, target_row, s_vy, crouch) ||
                            is_floor_solid(c_mid2, target_row, s_vy, crouch)) {
                            if (prev_feet <= (surf + 8) && curr_feet >= surf) {
                                py = (i16)(surf - PH);
                                s_py8 = (i16)(py * SUB);
                                s_vy = 0;
                                s_on_ground = 1;
                                s_ground_elevator = -1;
                                landed = 1;
                            }
                        }
                    }
                    if (!landed) {
                        u16 feet_under = (u16)((curr_feet + 1) >> 4);
                        if (feet_under < max_r) {
                            i16 surf_u = (i16)(feet_under << 4);
                            if (is_floor_solid(c_mid1, feet_under, s_vy, crouch) ||
                                is_floor_solid(c_mid2, feet_under, s_vy, crouch)) {
                                if (prev_feet <= (surf_u + 6) && curr_feet >= (surf_u - 2)) {
                                    py = (i16)(surf_u - PH);
                                    s_py8 = (i16)(py * SUB);
                                    s_vy = 0;
                                    s_on_ground = 1;
                                    s_ground_elevator = -1;
                                    landed = 1;
                                }
                            }
                        }
                    }
                }
                if (!landed) {
                    s_on_ground = 0;
                    s_ground_elevator = -1;
                }
            } else if (s_vy < 0) {
                u16 head_row = (u16)(py >> 4);
                u16 c_mid = (u16)((px + 5) >> 3);
                u16 r = prev_head;
                u8 n = 0;
                while (r >= head_row && n < 4) {
                    if (is_ceiling_solid(c_mid, r)) {
                        head_row = r;
                        break;
                    }
                    if (r == 0) break;
                    r--; n++;
                }
                if (is_ceiling_solid(c_mid, head_row)) {
                    py = (i16)((head_row + 1) << 4);
                    s_py8 = (i16)(py * SUB);
                    s_vy = 0;
                }
                s_on_ground = 0;
                s_ground_elevator = -1;
            }
        }
    }
    if (s_in_room) {
        check_room_bonus((u8)(((s_px8 >> 3) + 8) >> 3), (u8)(((s_py8 >> 3) + 28) >> 4));
    }
}

extern void zx0_decompress(const void* src, void* dst);

volatile u8 g_player_choice; // 0=Jake, 1=Elwood (l'escriu el FRONT al
                    // select via EQU; el loop la llegeix)
volatile u8 g_map_level; // 0..5 (el GAME l'escriu abans del mapa; el FRONT
                    // hi pinta sticker nota + ruta statica DOS via EQU)
u8 g_mus_ready = 0; // 1 = player iniciat (la ISR pot sonar). 0 fins al
                    // primer mus_init: evita Play sobre C1 buit (reboot).

void main(void) {
    cpct_memset((void*)CRT_DATA_START, 0, CRT_DATA_LEN);
    cpct_memcpy((void*)CRT_IDATA_DST, (void*)CRT_IDATA_SRC, CRT_IDATA_LEN);
    stack_canary_init();
    cpc_install_isr();

    fdc_motor_off();
    fdc_load_file(0xC0, 0, 0, 0);

    g_map_level = 0;
    {
        u8 prev = bank_set(0xC4);
        ((void(*)(void))FRONT_RUN)();
        bank_restore(prev);
    }

    mus_stop();
    g_mus_hold = 1;

    // Carrega rapida i seqüencial dels paquets de dades a 0x8320 (2a pagina oculta)
    // El motor FDC es mante ences durant la sequencia per evitar aturades/engegades.
    fdc_set_stay_on(1);

    // 1. Personatge: JAKE.ZX0 o ELWOOD.ZX0 segons g_player_choice -> Banc C7 (0x4000)
    {
        const DiskFileDesc* pdesc = g_player_choice ? &g_file_elwood : &g_file_jake;
        u16 pcrc = g_player_choice ? CRC_ELWOOD : CRC_JAKE;
        u8 ok = 0, t;
        for (t = 0; t < 3 && !ok; t++) {
            if (!fdc_load_file(0xC0, pdesc, 0xC0, (void*)0x8320)) continue;
            if (fdc_crc16((const u8*)0x8320, (u16)(pdesc->ondisk_bytes - 128)) == pcrc) ok = 1;
        }
        if (!ok) { cpct_setBorder(0x41); while (1) { } }
        {
            u8 prev = bank_set(0xC7);
            zx0_decompress((const void*)0x8320, (void*)0x4000);
            bank_restore(prev);
        }
    }

    // 2. Món Nivell 1: L1WORLD.PAK -> 4 sub-blocs descomprimits als seus respectius bancs
    {
        u8 ok = 0, t;
        for (t = 0; t < 3 && !ok; t++) {
            if (!fdc_load_file(0xC0, &g_file_l1world, 0xC0, (void*)0x8320)) continue;
            if (fdc_crc16((const u8*)0x8320, (u16)(g_file_l1world.ondisk_bytes - 128)) == CRC_L1WORLD) ok = 1;
        }
        if (!ok) { cpct_setBorder(0x42); while (1) { } }
        {
            const u8* pak = (const u8*)0x8320;
            u16 off_bank5 = (u16)(pak[0] | (pak[1] << 8));
            u16 off_mus   = (u16)(pak[2] | (pak[3] << 8));
            u16 off_elev  = (u16)(pak[4] | (pak[5] << 8));
            u8 prev;

            // Sub-bloc 1: Tileset (Mode 0) -> Banc C4:0x4000
            prev = bank_set(0xC4);
            zx0_decompress((const void*)(pak + 6), (void*)0x4000);
            bank_restore(prev);

            // Sub-bloc 2: Mapa + Triggers + Codi Banc 5 -> Banc C5:0x4000
            prev = bank_set(0xC5);
            zx0_decompress((const void*)(pak + off_bank5), (void*)0x4000);
            bank_restore(prev);

            // Sub-bloc 3: Musica + HUD + Rooms + Doors -> Banc C1:0x5000
            prev = bank_set(0xC1);
            zx0_decompress((const void*)(pak + off_mus), (void*)0x5000);
            bank_restore(prev);

            // Sub-bloc 4: Frames Ascensor -> Banc C0:0x7000
            prev = bank_set(0xC0);
            zx0_decompress((const void*)(pak + off_elev), (void*)0x7000);
            bank_restore(prev);
        }
    }

    // 3. Enemics Nivell 1: L1ENEMI.ZX0 -> Banc C6:0x4000
    {
        u8 ok = 0, t;
        for (t = 0; t < 3 && !ok; t++) {
            if (!fdc_load_file(0xC0, &g_file_l1enemi, 0xC0, (void*)0x8320)) continue;
            if (fdc_crc16((const u8*)0x8320, (u16)(g_file_l1enemi.ondisk_bytes - 128)) == CRC_L1ENEMI) ok = 1;
        }
        if (!ok) { cpct_setBorder(0x43); while (1) { } }
        {
            u8 prev = bank_set(0xC6);
            zx0_decompress((const void*)0x8320, (void*)0x4000);
            bank_restore(prev);
        }
    }

    // Aturar motor FDC un cop acabada la càrrega de tots els paquets
    fdc_motor_off();

    // MUSICA nivell 1: MUSMAIN ja es a l'slot C1:0x5000: obrir so i
    // (re)iniciar el tema.
    g_mus_hold = 0;
    mus_init();

    video_init();

    {
        u8 prev = bank_set(0xC7);
        sprite_hflip_init_lut((u8*)0x7F00);
        bank_restore(prev);
    }

    cpct_memset((void*)0xC000, 0xFF, 0x4000);
    cpct_memset((void*)0x8000, 0xFF, 0x4000);
    // (El blindatge HOLD=0 d'aqui era mort: 561 sempre l'ha netejat abans i
    // cap codi entremig l'escriu. Fora, 14/10/26: Bloc0 just.)

    // Inicialitza posició d'inici, càmera i entitats des del paquet de nivell (Banc 5)
    moving_init();
    // Walkers C6: init runtime (slot 3) post-carrega (sense crt0 al banc,
    // els inicialitzadors statics no arriben; vist 10/26).
    enemy_init();
    hud_init();
    repaint_both_buffers();
    moving_draw(0, g_cam_x4, g_cam_row);
    moving_draw(1, g_cam_x4, g_cam_row);

    s_vx = 0; s_vy = 0;
    s_on_ground = 1; g_face = 0;
    s_jump_prev = 0; s_climb_prev = 0;
    s_carry_kind = 0; s_grab_prev = 0;
    s_carry_state = 0; s_carry_drawn[0] = 0; s_carry_drawn[1] = 0;
    s_anim_idx = 0; s_anim_timer = 0;
    s_dazed_timer = 0;
    s_invuln_timer = 0;
    s_have_drawn[0] = 0;
    s_have_drawn[1] = 0;
    sprite_balloon_init();
    u8 last_ticks = g_ticks;

    while (1) {
        if (!stack_canary_ok()) {
            cpct_setBorder(0x4C);
        }
        i8 move = 0, move_x = 0, move_y = 0, page_dx, page_dy;
        u8 jump = 0, crouch = 0, grab = 0, cur;
        u16 dsx, dsy;

        cpct_scanKeyboard_f();
        if (cpct_isKeyPressed(Key_CursorLeft) || cpct_isKeyPressed(Key_Q) ||
            cpct_isKeyPressed(Joy0_Left))  { move = -1; g_face = 1; }
        if (cpct_isKeyPressed(Key_CursorRight) || cpct_isKeyPressed(Key_S) ||
            cpct_isKeyPressed(Joy0_Right)) { move = +1; g_face = 0; }
        if (cpct_isKeyPressed(Key_Space) || cpct_isKeyPressed(Key_X) ||
            cpct_isKeyPressed(Joy0_Fire1) || cpct_isKeyPressed(Joy0_Fire2)) { grab = 1; }
        if (cpct_isKeyPressed(Key_CursorDown) || cpct_isKeyPressed(Key_Z) ||
            cpct_isKeyPressed(Joy0_Down))  { crouch = 1; }
        {
            u8 up_key = (cpct_isKeyPressed(Key_CursorUp) || cpct_isKeyPressed(Joy0_Up));
            if (up_key && !grab) { jump = 1; }

            // 1:1 DOS Door Trigger: SPACE + UP (level.c:1210)
            if (grab && up_key && !s_up_prev && !s_climb_prev) {
                check_doors();
            }
            s_up_prev = up_key;
        }

        if (s_dazed_timer) {
            s_dazed_timer--;
            move = 0;
            jump = 0;
            crouch = 0;
            grab = 0;
            s_vx = 0;
        }

        // Acceleració horitzontal
        {
            i16 max_spd = s_on_ground ? SPEED_MAX : SPEED_AIR;
            if (move > 0)      { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx >  max_spd) s_vx =  max_spd; }
            else if (move < 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < -max_spd) s_vx = -max_spd; }
            else {
                if (s_vx > 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < 0) s_vx = 0; }
                else if (s_vx < 0) { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx > 0) s_vx = 0; }
            }
        }

        // 1. Lògica d'entitats i efectes de tiles al Banc 5 (ascensors, aigua, escala, objectes)
        bc_b = jump;
        bc_c = crouch;
        bc_d = grab;
        moving_update();
        if (!s_in_room) {
            enemy_update();
        }

        // 1:1 DOS Col·lisió Jake <-> Enemics / Projectils (level.c:1583-1658)
        if (s_invuln_timer) {
            s_invuln_timer--;
        } else if (!s_in_room) {
            i16 px = (i16)(s_px8 >> 3);
            i16 py = (i16)(s_py8 >> 3);
            if (enemy_check_player_hit(px, py, crouch)) {
                if (g_hearts_count > 0) g_hearts_count--;
                s_invuln_timer = 75; // 1:1 DOS blinking_counter = 75
                s_dazed_timer = 20;  // 1:1 DOS special_anim = 18 (estrelletes al cap)
                if (s_carry_kind) carry_abort();
                if (g_hearts_count == 0) {
                    if (g_lives_count > 0) g_lives_count--;
                    if (g_lives_count == 0) {
                        moving_init();
                        enemy_init();
                    }
                    g_hearts_count = 3;
                    s_px8 = (i16)(LEVEL_START_PX * SUB);
                    s_py8 = (i16)(LEVEL_START_PY * SUB);
                    s_vx = 0; s_vy = 0;
                    s_on_ground = 1;
                    s_ground_elevator = -1;
                    g_cam_x4 = LEVEL_CAM0_X4;
                    g_cam_row = LEVEL_CAM0_ROW;
                    s_invuln_timer = 75;
                    s_dazed_timer = 0;
                    s_in_room = 0;
                    s_scrolling_locked = 0;
                    s_carry_kind = 0;
                    s_carry_state = 0;
                    s_carry_drawn[0] = 0;
                    s_carry_drawn[1] = 0;
                    s_have_drawn[0] = 0;
                    s_have_drawn[1] = 0;
                    s_rep_n = 0;
                    enemy_room_exit(0, 0);
                    palette_black();
                    repaint_both_buffers();
                    moving_draw(0, g_cam_x4, g_cam_row);
                    moving_draw(1, g_cam_x4, g_cam_row);
                    palette_restore();
                }
            }
        }

        if (s_on_ground && s_ground_elevator >= 0) {
            MovingElevator* e = &g_mag_elevators[(u8)s_ground_elevator];
            i16 px = (i16)(s_px8 >> 3);
            if (px + PW > e->center_x - ELEVATOR_HALF_W &&
                px < e->center_x + ELEVATOR_HALF_W) {
                s_py8 = (i16)(s_py8 + e->delta_y * SUB);
            } else {
                s_ground_elevator = -1;
                s_on_ground = 0;
            }
        }

        // 2. Pas de física genèrica de col·lisió sòlida al motor resident
        player_physics_step(bc_r, s_climb_prev, jump, crouch);

        // 3. Càmera i deadzone
        {
            i16 px = (i16)(s_px8 >> 3);
            i16 py = (i16)(s_py8 >> 3);
            if (!s_scrolling_locked) {
                i16 sy = (i16)(py - (i16)(g_cam_row * 8));
                i16 sx = (i16)(px - (i16)(g_cam_x4 * 4));
                if (sx > DEAD_R && g_cam_x4 < ((LEVEL_W_PX / 4) - PLAY_CHARS)) {
                    g_cam_x4++;
                    move_x = 1;
                } else if (sx < DEAD_L && g_cam_x4 > 0) {
                    g_cam_x4--;
                    move_x = -1;
                }
                if (sy > DEAD_B && g_cam_row < LEVEL_MAX_CAM_ROW) {
                    g_cam_row++;
                    move_y = 1;
                } else if (sy < DEAD_T && g_cam_row > 0) {
                    g_cam_row--;
                    move_y = -1;
                }
            }
            {
                i16 screen_x = (i16)((px - (i16)(g_cam_x4 * 4)) >> 1);
                i16 screen_y = (i16)(py - (i16)(g_cam_row * 8));
                if (screen_x < 0) screen_x = 0;
                if (screen_x > (80 - SPR_WB)) screen_x = (80 - SPR_WB);
                if (screen_y < 0) screen_y = 0;
                if (screen_y > (160 - PH)) screen_y = (160 - PH);
                dsx = (u16)screen_x;
                dsy = (u16)screen_y;
            }
        }

        page_dx = (i8)(s_pending_x + move_x);
        page_dy = (i8)(s_pending_y + move_y);
        g_vram_start = camera_ma((u16)(g_cam_x4 - page_dx),
                                 (u16)(g_cam_row - page_dy));

        // --- Restaurar el fons al BACKBUFFER (LIFO) ---
        carry_restore(s_back_page);
        sprite_restore_umbrella();
        sprite_restore_balloon();
        if (s_have_drawn[s_back_page]) {
            sprite_restore_player();
            s_have_drawn[s_back_page] = 0;
        }
        // Restore LIFO (invers al draw world->enemic->jugador):
        // l'enemic abans que els ascensors (els dibuixa a sobre).
        if (!s_in_room) {
            enemy_restore(s_back_page);
            moving_restore(s_back_page, (move_x != 0 || move_y != 0));
            moving_popup_restore(s_back_page);
            sync_backbuffer(page_dx, page_dy, g_cam_x4, g_cam_row);
            bc_a = s_back_page;
            moving_draw_conveyor_tiles();
        }
        world_flush_repaints();
        g_vram_start = camera_ma(g_cam_x4, g_cam_row);
        hud_render(s_back_page, (page_dx != 0 || page_dy != 0));
        cur = select_player_anim(s_climb_prev, move, jump, crouch, (i16)dsy);

        // Dibuixar objectes mòbils i sprites sobre el fons actualitzat
        if (!s_in_room) {
            moving_draw(s_back_page, g_cam_x4, g_cam_row);
            enemy_draw(s_back_page);
        }

        g_spr_y = (u8)dsy;
        g_spr_x = (u8)dsx;

        if (!(s_invuln_timer & 2)) {
            u16 spr_addr = (u16)(PLAYER_FRAMES_BASE + ((u16)cur << 9) - ((u16)cur << 5));
            const u8* fr_addr = (const u8*)spr_addr;
            u8 prev_b = bank_set(PLAYER_FRAMES_BANK);
            // Contracte hflip (verificat en viu): C7 paginat als dos costats.
            // flip escriu i blit llegeix C7:0x7840 (gap lliure fins EXTRA 0x7A20);
            // la LUT es llegeix de C7:0x7F00 (B=0x7F).
            if (g_face == 0) {
                sprite_blit_player(fr_addr);
            } else {
                sprite_hflip(fr_addr, (u8*)0x7840);
                sprite_blit_player((const u8*)0x7840);
            }
            bank_restore(prev_b);
            s_have_drawn[s_back_page] = 1;
        } else {
            s_have_drawn[s_back_page] = 0;
        }

        carry_draw(s_back_page);
        if (s_carry_kind == 2) {
            if (!s_carry_state) {
                sprite_blit_balloon();
            } else {
                i16 bx = (i16)(( (s_carry_x >> 3) - (i16)(g_cam_x4 * 4) ) >> 1);
                i16 by = (i16)((s_carry_y >> 3) - (i16)(g_cam_row * 8));
                if (bx >= 0 && bx <= (80 - SPR_WB) && by >= 28 && by < 180) {
                    g_spr_x = (u8)bx;
                    g_spr_y = (u8)by;
                    sprite_blit_balloon();
                    g_spr_x = (u8)dsx;
                    g_spr_y = (u8)dsy;
                } else {
                    s_carry_kind = 0;
                    s_carry_state = 0;
                }
            }
        }
        else if (s_carry_kind == 8) sprite_blit_umbrella();

                // Sincronització vertical fluida a 25 Hz (2 VSYNCs = 40 ms)
        cpc_wait_vsync_start();
        if ((u8)(g_ticks - last_ticks) < 10) {
            cpc_wait_vsync_start();
        }
        last_ticks = g_ticks;
        crtc_set_display_start((u16)((s_back_page == 1 ? 0x2000 : 0x3000) + g_vram_start));

        s_back_page ^= 1;
        g_vram_base_hi = (s_back_page == 1) ? 0x80 : 0xC0;
        s_pending_x = move_x;
        s_pending_y = move_y;
    }
}
