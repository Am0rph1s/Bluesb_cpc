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
#include "level_params.h"

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
#define TRIG_STRIDE 5
#define PLAY_CHARS  40
#define SUB         8
#define PH          30
#define PW          16
#define SPR_WB      8
#define SPEED_MAX   30
#define SPEED_AIR   24
#define MOVE_ACC    7
#define VY_MAX      (15 * SUB)
#define GRAV        16
#define JUMP_VY     (-112)
#define DEAD_L      48
#define DEAD_R      88
#define DEAD_T      32
#define DEAD_B      116
#define CRATE_FLY_FRAME ((const u8*)0x7A20)

static const u8 s_crate_walk[6] = { 15, 13, 14, 16, 13, 14 };
static const u8 s_walk[6] = { 1, 2, 0, 3, 2, 0 };

#define PROFILE_BORDER 0
#if PROFILE_BORDER
static void dbg_border(u8 col) {
    __asm
        ld      bc, #0x7F10
        out     (c), c
        ld      c, a
        out     (c), c
    __endasm;
}
#else
#define dbg_border(col) ((void)0)
#endif

// Estat compartit resident (actualitzat des del mòdul de nivell al Banc 5):
u16 g_cam_x4;
u16 g_cam_row;

i16 s_px8, s_py8;
i16 s_vx, s_vy;
u8  s_on_ground;
u8  s_jump_prev;
u8  s_climb_prev;
u8  s_climb_t6;    // 1 = l'escala actual es una reixa (tile 6, L3)
u8  s_crouch_hold; // 1 = ajupit que continua fins poder aixecar-se (DOS unk2E==0)
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
// Buffers de fons de caixes al Banc 7 dins del gap lliure (0x7DE0..0x7EFF):
// 64 B per pagina (0x7E00 per p=0, 0x7E40 per p=1). No col·lideix amb els frames d'en Jake!
#define CRATE_BG_PAGE(p) ((u16)(0x7E00 + ((u16)(p) << 6)))

i8  s_ground_elevator = -1;
u8  g_face;
u8  s_anim_idx, s_anim_timer;
u8  s_dazed_timer;
u8  s_dying_timer;
u8  s_invuln_timer;

static u8  s_have_drawn[2];
static i8  s_pending_x, s_pending_y;

u8  s_rep_n;
u8  s_rep_col[4], s_rep_row[4], s_rep_tile[4], s_rep_pages[4];

static u8 s_back_page = 1;
static u8 s_complete_wait;

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

// --- Parametres del NIVELL (runtime; venen del paquet) -------------------
// El bloc sencer del paquet (C1:0x7680) es copia aqui i s'hi accedeix
// amb les macros de level_params.h: cap constant del nivell 1 al Bloc 0
// i cap cost de codi extra per llegir-los.
LevelParams s_lv;

void level_params_load(void) {
    // El bloc de parametres del nivell es llegeix del paquet (Banc C1:0x7680)
    // i es queda al resident: la part u8 (geometria, tiles, mides) es usa a
    // cada frame; els valors de 16 bits (start, checkpoint, camera) tambe.
    u8 prev = bank_set(0xC1);
    cpct_memcpy(&s_lv, (const void*)0x7680, sizeof(LevelParams));
    bank_restore(prev);
}

static u8 get_tile_at(u16 col, u16 row) {
    u8 prev, t;
    if (row >= s_lv.room_row0 && row < (u16)(s_lv.room_row0 + s_lv.room_rows) &&
        col < s_lv.room_total_cols) {
        prev = bank_set(0xC5);
        t = ((const u8*)(u16)s_lv.rooms_off)[s_lv.room_rowoff[row - s_lv.room_row0] + col];
        bank_restore(prev);
        return t;
    }
    if (col >= s_lv.map_w || row >= s_lv.map_h) return 0xFF;
    prev = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    bank_restore(prev);
    return t;
}

static u8 get_trig_byte(u16 col, u16 row, u8 offset) {
    u8 prev, t = get_tile_at(col, row);
    if (t == 0xFF) return 0xFF;
    prev = bank_set(0xC5);
    t = ((const u8*)(u16)s_lv.trig_off)[((u16)t) * TRIG_STRIDE + offset];
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
    if (row >= s_lv.room_row0) {
        if (row >= s_lv.room_row_last) return (vy >= 0);
    } else if (row >= (u16)(s_lv.map_h - 1)) {
        return (vy >= 0);
    }
    op = get_trig_byte(col, row, 2);
    if (op == 0xFF) return 0;
    // 1:1 DOS: el SOSTRE el decideix l'OP del trigger, no el "type". Les ops
    // 0/2/3/20/21/27/28/29 són les de plataforma (trigger_func_opX: el
    // jugador s'hi recoloca a sobre). A L1 només hi ha 20/21/27/28; a L2
    // hi ha 29 (64 tiles del terra), 0, 2 i 3.
    if (op == 0 || op == 1 || op == 2 || op == 3 || op == 20 || op == 21 || op == 27 ||
        op == 28 || op == 29) return 1;
    if (vy >= 0) {
        if (op == 14 || op == 15) return !crouch;
        if (op >= 30 && op <= 39) return 1;
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
    s_dying_timer = 0;
    s_jump_prev = 0;

    if (dst_row >= 72) {
        // Entering Room
        u8 room_idx = (u8)(dst_col / s_lv.room_cols);
        s_in_room = 1;
        s_scrolling_locked = 1;
        g_cam_x4 = (u16)(room_idx * ((u16)s_lv.room_cols << 1));
        g_cam_row = s_lv.room_cam_row;
        enemy_room_exit(0, 0);
    } else {
        // Exiting Room to main level
        i16 cam_col = (i16)dst_col - 10;
        i16 cam_r = (i16)dst_row - 6;
        s_in_room = 0;
        s_scrolling_locked = 0;

        if (cam_col < 0) cam_col = 0;
        if (cam_col > (i16)s_lv.cam_max_x4) cam_col = (i16)s_lv.cam_max_x4;
        g_cam_x4 = (u16)(cam_col << 1);

        if (cam_r < 0) cam_r = 0;
        if (cam_r > (i16)(s_lv.max_cam_row >> 1)) cam_r = (i16)(s_lv.max_cam_row >> 1);
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
    d = (const LevelDoor*)(u16)s_lv.doors_off;
    for (i = 0; i < s_lv.door_count; i++, d++) {
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
    u8 row_last = (u8)(s_lv.room_row0 + s_lv.room_rows);
    if (col >= s_lv.room_total_cols) return;
    for (r = feet_row; r >= (feet_row - 2) && r >= s_lv.room_row0; r--) {
        if (r >= row_last) continue;
        u16 off = s_lv.room_rowoff[r - s_lv.room_row0] + col;
        prev = bank_set(0xC5);
        t = ((const u8*)(u16)s_lv.rooms_off)[off];
        if (t == s_lv.tile_vinyl) {
            if (g_vinyls_count < 99) g_vinyls_count++;
        } else if (t == s_lv.tile_instr) {
            g_has_instrument = s_lv.level_id + 1;
        } else {
            bank_restore(prev);
            continue;
        }
        ((u8*)(u16)s_lv.rooms_off)[off] = s_lv.tile_empty;
        bank_restore(prev);
        if (s_rep_n < 4) {
            s_rep_col[s_rep_n] = col;
            s_rep_row[s_rep_n] = r;
            s_rep_tile[s_rep_n] = s_lv.tile_empty;
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

    // La camera pot fer 2 files per frame (16 px, el ritme de la caiguda
    // maxima) i el backbuffer nomes te 2 frames de retard: cal repintar
    // fins a 4 files noves.
    if (dy > 0) {
        u8 i;
        for (i = 0; i < (u8)dy && i < 4; i++) render_row(target_x4, target_row, (u8)(19 - i));
    } else if (dy < 0) {
        u8 i;
        for (i = 0; i < (u8)(-dy) && i < 4; i++) render_row(target_x4, target_row, i);
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
    // NO sprite_abort_balloon(): si nomes neteja els flags, el globus/
    // paraigües queda dibuixat a pantalla (el restore del frame seguent
    // ja el borra amb el fons correcte).
}

// 1:1 DOS tiles.c:907-919 + level.c:1583-1593 (kind=10, b6=2/3/4): l'àcid
// sempre fa mal (-1 cor, invuln 75, rebot). Cos a hud_bank.c (C1 compartit,
// amb marge); aquí només el wrapper (el resident també va just).
extern void acid_hurt_o(void);
void acid_hurt(i16 vy) {
    bc_a = (u16)vy;
    call_banked(0xC0, (void*)acid_hurt_o);
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
    if (s_dying_timer) {
        if (s_vy != 0 && !s_on_ground) return 4;
        return (s_dying_timer & 8) ? 10 : 11;
    }
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
                // s_anim_idx pot venir de walk (p. ex. 3): XOR 1 el deixava
                // a 2/3 i sempre es dibuixava el mateix frame. Forcem 0/1.
                s_anim_idx = (u8)((s_anim_idx + 1) & 1);
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
        // 1:1 DOS: repòs amb caixa = animframes_ptr[24/4] = animframe_00bd
        // = [1, 10] (Jake DOS 10 / Elwood 60). És el frame 17 de l'atlas.
        return 17;
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
        if (sx < -4 || sx > 76 || sy < -16 || sy > 160 || cx < 16 || cx > (i16)(s_lv.map_w_px - 24) ||
            tt == 6 || enemy_check_crate_hit(cx, cy, s_carry_vx)) {
            carry_abort();
        }
    }

    // --- Moviment horitzontal i col·lisió de parets ---
    // 1:1 DOS level.c:1770-1833: ajupit (unk2E==0 -> alçada 14) NOMES es
    // mira la fila de sota el cap; dret (alçada 26) també la de sobre. En CPC
    // la fila de peus no es pot consultar amb tile_flags (els tiles de terra
    // porten flags=7); per això s'usa la fila del cap (py+16) i, dret, la de
    // sobre (py). Això és el que permet passar per forats d'1 tile (L3 row 23).
    {
        u16 head_row = (u16)((py + 16) >> 4);
        u16 top_row = (u16)(py >> 4);
        if (effective_vx > 0) {
            u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
            u16 c_right = (u16)((next_px + 10) >> 3);
            u8 fl = tile_flags(c_right, head_row);
            if (!crouch) fl |= tile_flags(c_right, top_row);
            if (fl & 1) {
                s_vx = 0;
                s_px8 = (i16)(((c_right << 3) - 11) * SUB);
            } else {
                s_px8 = (i16)(s_px8 + effective_vx);
            }
        } else if (effective_vx < 0) {
            u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
            u16 c_left  = (u16)((next_px + 1) >> 3);
            u8 fl = tile_flags(c_left, head_row);
            if (!crouch) fl |= tile_flags(c_left, top_row);
            if (fl & 2) {
                s_vx = 0;
                s_px8 = (i16)(((c_left << 3) + 8 - 1) * SUB);
            } else {
                s_px8 = (i16)(s_px8 + effective_vx);
            }
        }
    }
    {
        i16 min_x = s_in_room ? (i16)(g_cam_x4 << 5) : 0;
        i16 max_x = s_in_room ? (i16)(min_x + 1152) : (i16)((s_lv.map_w_px - PW) * SUB);
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
                    // TUBERIA (op 17/18/19): el DOS posa yacc = -3 al trigger,
                    // o sea el jugador continua pujant (gravetat invertida).
                    if (s_pipe_up) {
                        s_vy = (i16)(s_vy - 24);
                    } else {
                        s_vy = (i16)(s_vy + GRAV);
                    }
                    if (s_vy > VY_MAX) s_vy = VY_MAX;
                    if (s_vy < -VY_MAX) s_vy = -VY_MAX;
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
                        s_vy = (s_carry_kind == 1 && !s_carry_state) ? -72 : JUMP_VY;
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
                bc_a = (u16)(px + (PW >> 1)); // centre del jugador (xpos DOS)
                bc_b = (u16)prev_feet; bc_c = (u16)curr_feet;
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
                    u16 max_r = s_in_room ? (u16)(s_lv.room_row0 + s_lv.room_rows) : s_lv.map_h;
                    u16 target_row = (u16)(curr_feet >> 4);
                    if (!landed && target_row < max_r) {
                        i16 surf = (i16)(target_row << 4);
                        if (is_floor_solid(c_mid1, target_row, s_vy, crouch) ||
                            is_floor_solid(c_mid2, target_row, s_vy, crouch)) {
                            // 1:1 DOS: només s'hi enganxa si els peus CREUEN
                            // la superfície dins del frame (abans hi havia un
                            // marge de +8 px que deixava pujar mig tile més).
                            if (prev_feet <= surf && curr_feet >= surf) {
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
                                if (prev_feet <= surf_u && curr_feet >= surf_u) {
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
static u8 g_front_map_only; // 1 = tornar al FRONT per la transicio de mapa
// 1:1 DOS (level.c init_level): en completar un nivell es conserven vides,
// cors i discos (nomes es reinicien a l'entrada del nivell 0 o en morir);
// l'instrument si que es reinicia (data5F = 0).
static u8 g_keep_counters; // 1 = la propera carrega conserva comptadors
u8 g_mus_ready = 0; // 1 = player iniciat (la ISR pot sonar). 0 fins al
                    // primer mus_init: evita Play sobre C1 buit (reboot).

// ============================================================
// Carregador generic de paquets de nivell (docs/LEVEL_PACKAGE.md)
// ------------------------------------------------------------
// Capcalera (16 B): magic 'B', version, level_id, flags, total_len,
//   n_sections, disc_id, hdr_crc, reserved.
// Seccio (8 B): bank, flags (bit0=ZX0), dest(u16), src_off(u16), src_len(u16).
// Retorna 1 si el fitxer s'ha llegit, el CRC es correcte i el manifest es valid.
// ============================================================
static u8 load_package(const DiskFileDesc* f, u16 crc) {
    const u8* pak = (const u8*)0x8320;
    u8 t, ok = 0, n, i;

    for (t = 0; t < 3 && !ok; t++) {
        if (!fdc_load_file(0xC0, f, 0xC0, (void*)0x8320)) continue;
        if (fdc_crc16(pak, (u16)(f->ondisk_bytes - 128)) == crc) ok = 1;
    }
    if (!ok) return 0;
    if (pak[0] != 0x42 || pak[1] != 1) return 0;

    n = pak[6];
    for (i = 0; i < n; i++) {
        const u8* d = pak + 16 + (u16)i * 8;
        u16 dst = (u16)(d[2] | ((u16)d[3] << 8));
        u16 off = (u16)(d[4] | ((u16)d[5] << 8));
        u16 len = (u16)(d[6] | ((u16)d[7] << 8));
        u8 prev = bank_set(d[0]);
        if (d[1] & 1) {
            zx0_decompress(pak + off, (void*)dst);
        } else {
            cpct_memcpy((void*)dst, pak + off, len);
        }
        bank_restore(prev);
    }
    return 1;
}


// ============================================================
// Carrega del nivell des del disc + reset de video.
// 1:1 DOS: el bucle principal de game.c crida load_level_data(g_vars.level)
// a CADA iteracio del bucle de nivell (game.c:344), o sigui tambe despres
// de morir. Aixo es el que fa que discos, cors, ulleres i interrogants
// tornin a apareixer: el MAPA es re-llegeix del disc.
// Reutilitzada a l'arrencada i al reinici per mort.
// ============================================================
// Taula de disc dels nivells incrustada a C1:0x4000 (MUSBANK permanent).
// Format (build.py): "LV", 1, 6 + 18 x <ondisk u16, sectors u8, crc u16>
// + pool [6][WORLD 56 B][ENEMI 32 B][C1 32 B]. Cap CHS de nivell al resident.
#define LVLCHS_N            6
#define LVLCHS_POOL_OFF     (4 + LVLCHS_N * 3 * 5)
#define LVLCHS_LEVEL_STRIDE (56 + 32 + 32)
#define LVLCHS_LEN          814

static u8 s_chs_buf[56];
static DiskFileDesc s_lvl_desc;

static u8 load_level_file(u8 lvl, u8 typ) {
    const u8* e;
    const u8* chs;
    u16 crc;
    u8 prev, n;
    u16 typ_stride;
    if (lvl >= LVLCHS_N) lvl = LVLCHS_N - 1;
    typ_stride = (typ == 0) ? 0 : ((typ == 1) ? 56 : 88);
    prev = bank_set(0xC1);
    if (*(const u8*)0x7C00u != 'L') {
        cpct_memcpy((void*)0x7C00u, (const void*)0x5D00u, LVLCHS_LEN);
    }
    e = (const u8*)(0x7C00u + 4u + (u16)(lvl * 3u + typ) * 5u);
    n = e[2];
    if (!n) { bank_restore(prev); return 0; }
    s_lvl_desc.ondisk_bytes = (u16)e[0] | ((u16)e[1] << 8);
    s_lvl_desc.sector_count = n;
    s_lvl_desc.chs_table = s_chs_buf;
    crc = (u16)e[3] | ((u16)e[4] << 8);
    chs = (const u8*)(0x7C00u + LVLCHS_POOL_OFF +
                      (u16)lvl * LVLCHS_LEVEL_STRIDE + typ_stride);
    cpct_memcpy(s_chs_buf, chs, (u16)n * 2u);
    bank_restore(prev);
    return load_package(&s_lvl_desc, crc);
}

static void load_level_packages(void) {
    // Carrega rapida i sequencial dels paquets de dades a 0x8320 (2a pagina oculta)
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

    // 2. Mon, C1 i Enemics: descriptors a la taula LVLCHS (C1:0x4000 de MUSBANK).
    // El resident no te cap taula CHS de nivell: afegeix un nivell = afegeix una entrada a LVLCHS.
    {
        u8 lvl = g_map_level;
        if (lvl >= LVLCHS_N) lvl = LVLCHS_N - 1;
        if (!load_level_file(lvl, 0)) {
            cpct_setBorder(0x42); while (1) { }
        }
        // L3 porta la imatge C1 en un paquet separat (L3C1.PAK) per no
        // excedir els 28 sectors de L3WORLD. Els altres nivells la duen dins.
        if (lvl == 2 && !load_level_file(lvl, 2)) {
            cpct_setBorder(0x44); while (1) { }
        }
        // Parametres del nivell (geometria, tiles, start, checkpoint...)
        level_params_load();
        if (!load_level_file(lvl, 1)) {
            cpct_setBorder(0x43); while (1) { }
        }
    }

    // Aturar motor FDC un cop acabada la carrega de tots els paquets
    fdc_motor_off();

    video_init();

    {
        u8 prev = bank_set(0xC7);
        sprite_hflip_init_lut((u8*)0x7F00);
        bank_restore(prev);
    }
}

// 1:1 DOS (game.c:344 -> load_level_data a cada reinici): al morir, el mapa
// torna a l'estat inicial i discos, cors, ulleres i interrogants reapareixen.
// El DOS ho fa rellegint el mapa del disc; aqui n'hi ha prou de tornar a
// escriure els tiles que poden canviar (taula generada per tools/pack_level.py
// i incrustada a la imatge del banc C6). L'item secret NO es restaura: el seu
// estat persisteix entre morts (com al DOS).
static void restore_level_tiles(void) {
    u8 prev = bank_set(0xC6);
    const u8* tbl = ENEMY_RESTORE_TABLE;
    u16 n = (u16)(tbl[0] | (tbl[1] << 8));
    u16 i;
    for (i = 0; i < n; i++) {
        const u8* e = tbl + 2 + (u16)(i * 3);
        u8 col = e[0];
        u8 row = e[1];
        u8 tile = e[2];
        bank_restore(prev);
        prev = bank_set(0xC5);
        ((u8*)0x4000)[((u16)row << 7) + col] = tile;
        bank_restore(prev);
        prev = bank_set(0xC6);
    }
    bank_restore(prev);

    // Les HABITACIONS (sales a C5 des de la Fase 3.2) tenen els seus propis
    // items consumibles (els discs de les sales). Al DOS el paquet de nivell
    // es rellegeix a cada mort, aixi que a les sales tambe tornen a
    // aparaitre. La taula (C1, restore_off) diu quines posicions dins el bloc
    // de sales tenen un disc i quin es el seu tile inicial: la taula viu a C1
    // i les dades a C5, per tant es commuta per entrada.
    // L'instrument (tile 159) NO hi es: l'item secret persisteix (1:1 DOS).
    prev = bank_set(0xC1);
    tbl = (const u8*)(u16)s_lv.restore_off;
    n = (u16)(tbl[0] | (tbl[1] << 8));
    bank_restore(prev);
    for (i = 0; i < n; i++) {
        const u8* e;
        u16 off;
        u8 tile, prev5;
        prev = bank_set(0xC1);
        e = (const u8*)(u16)s_lv.restore_off + 2 + (u16)(i * 3);
        off = (u16)(e[0] | (e[1] << 8));
        tile = e[2];
        prev5 = bank_set(0xC5);
        ((u8*)(u16)s_lv.rooms_off)[off] = tile;
        bank_restore(prev5);
        bank_restore(prev);
    }
}

// GAME OVER: codi comu al Banc 1 (src/hud_bank.c, MUSBANK). Escriu VRAM -> 0xC0.
extern void gameover_o(void);
static void draw_gameover_banner(u8 page) {
    bc_a = page;
    call_banked(0xC0, (void*)gameover_o);
}

// El FRONT viu a C4 i el nivell hi carrega el tileset a sobre. Cal recarregar
// FRONT.BIN abans de tornar-lo a cridar (game over o nivell completat).
static void load_front_bank(void) {
    u8 ok = 0, t;
    for (t = 0; t < 3 && !ok; t++) {
        if (!fdc_load_file(0xC0, &g_file_front, 0xC4, (void*)0x4000)) continue;
        ok = 1;
    }
    if (!ok) { cpct_setBorder(0x4C); while (1) { } }
}

void main(void) {
    u8 sv_lives, sv_hearts, sv_vinyls, sv_keep;
    cpct_memset((void*)CRT_DATA_START, 0, CRT_DATA_LEN);
    g_bank = 0xC0;
    cpct_memcpy((void*)CRT_IDATA_DST, (void*)CRT_IDATA_SRC, CRT_IDATA_LEN);
    stack_canary_init();
    cpc_install_isr();

    fdc_motor_off();
    fdc_load_file(0xC0, 0, 0, 0);

    g_map_level = 0;
    g_front_map_only = 0;
    // Drecera de test (no afecta el joc normal): si en arrencar es manté
    // premut el '2', el FRONT mostra el mapa amb la ruta de l'L2 i s'hi
    // entra directe. Cal passar per FRONT_RUN perquè és qui carrega MUSBANK
    // (front.c:466); FRONT_MAP sol el pressuposa carregat i peta en fred.
    // El '3' fa el mateix amb l'L3 (prison) per poder-lo verificar.
    cpct_scanKeyboard_f();
    if (cpct_isKeyPressed(Key_2)) {
        g_map_level = 1;
    } else if (cpct_isKeyPressed(Key_3)) {
        g_map_level = 2;
    }
    while (1) {
        {
            u8 prev = bank_set(0xC4);
            if (g_front_map_only) {
                g_front_map_only = 0;
                ((void(*)(void))FRONT_MAP)();
            } else {
                ((void(*)(void))FRONT_RUN)();
            }
            bank_restore(prev);
        }

    mus_stop();
    g_mus_hold = 1;

    load_level_packages();

    // MUSICA nivell 1: MUSMAIN ja es a l'slot C1:0x5000: obrir so i
    // (re)iniciar el tema.
    g_mus_hold = 0;
    mus_init();

    // Neteja de les dues pagines de video (nomes a l'arrencada: al reinici
    // per mort ja ho fa repaint_both_buffers() i aqui no volem tocar la
    // pagina 2, on viu la imatge del motor FDC).
    cpct_memset((void*)0xC000, 0xFF, 0x4000);
    cpct_memset((void*)0x8000, 0xFF, 0x4000);

    // (video_init + LUT d'hflip + neteja de les dues pagines ja els fa
    //  load_level_packages(), que tambe s'usa al reinici per mort.)

    // Inicialitza posició d'inici, càmera i entitats des del paquet de nivell (Banc 5).
    // Si venim d'una transicio de nivell completat, moving_init() reseteja els
    // comptadors i els restaurem aqui (1:1 DOS: init_level nomes els toca a
    // l'entrada del nivell 0 o en morir; l'instrument queda a 0, com al DOS).
    sv_lives = g_lives_count; sv_hearts = g_hearts_count; sv_vinyls = g_vinyls_count;
    sv_keep = g_keep_counters;
    g_keep_counters = 0;
    moving_init();
    if (sv_keep) {
        g_lives_count = sv_lives;
        g_hearts_count = sv_hearts;
        g_vinyls_count = sv_vinyls;
    }
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
    s_dying_timer = 0;
    s_invuln_timer = 0;
    s_have_drawn[0] = 0;
    s_have_drawn[1] = 0;
    sprite_balloon_init();
    u8 last_ticks = g_ticks;

    while (1) {
        dbg_border(0x5E);
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

        if (s_dazed_timer || s_dance_timer || s_dying_timer) {
            if (s_dazed_timer) s_dazed_timer--;
            move = 0;
            jump = 0;
            crouch = 0;
            grab = 0;
            s_vx = 0;
        }

        // Acceleració horitzontal
        {
            i16 max_spd = s_on_ground ? SPEED_MAX : SPEED_AIR;
            u8 acc = (s_on_ground && g_on_ice) ? 2 : MOVE_ACC;
            if (move > 0)      { s_vx = (i16)(s_vx + acc); if (s_vx >  max_spd) s_vx =  max_spd; }
            else if (move < 0) { s_vx = (i16)(s_vx - acc); if (s_vx < -max_spd) s_vx = -max_spd; }
            else {
                if (s_vx > 0) { s_vx = (i16)(s_vx - acc); if (s_vx < 0) s_vx = 0; }
                else if (s_vx < 0) { s_vx = (i16)(s_vx + acc); if (s_vx > 0) s_vx = 0; }
            }
        }

        // 1. Lògica d'entitats i efectes de tiles al Banc 5 (ascensors, aigua, escala, objectes)
        bc_b = jump;
        bc_c = crouch;
        bc_d = grab;
        dbg_border(0x40);
        moving_update();
        if (!s_in_room) {
            dbg_border(0x5E);
            enemy_update();
        }

        // 1:1 DOS Col·lisió Jake <-> Enemics / Projectils (level.c:1583-1658)
        if (s_invuln_timer) {
            s_invuln_timer--;
        } else if (!s_in_room && !s_dying_timer) {
            i16 px = (i16)(s_px8 >> 3);
            i16 py = (i16)(s_py8 >> 3);
            if (enemy_check_player_hit(px, py, crouch)) {
                if (g_hearts_count > 0) g_hearts_count--;
                s_invuln_timer = 75; // 1:1 DOS blinking_counter = 75
                if (s_carry_kind) carry_abort();
                if (g_hearts_count == 0) {
                    s_dying_timer = 64; // 1:1 DOS death dance (~1.3s a 50Hz)
                    s_dazed_timer = 0;
                    s_invuln_timer = 255;
                } else {
                    s_dazed_timer = 20;  // 1:1 DOS special_anim = 18 (estrelletes al cap)
                }
            }
        }

        if (s_dying_timer) {
            s_dying_timer--;
            if (s_dying_timer == 0) {
                if (g_lives_count <= 1) {
                    g_lives_count = 0;
                    g_checkpoint = 0;
                    mus_stop();
                    g_mus_hold = 1;
                    g_mus_ready = 0;
                    palette_black();
                    crtc_set_display_start(0x3000);
                    load_front_bank();
                    s_back_page = 1;
                    g_vram_base_hi = 0x80;
                    g_map_level = 0;   // game over -> tornar al nivell inicial
                    g_front_map_only = 0;
                    break;
                }
                g_lives_count--;
                // 1:1 DOS init_level() (restart_level_flag != 0): cors = 3,
                // discos = 0. I el mapa torna a l'estat inicial (els items
                // reapareixen) menys l'item secret, que persisteix.
                g_hearts_count = 3;
                g_vinyls_count = 0;
                restore_level_tiles();     // consumibles (mapa + habitacions) -> estat inicial
                moving_respawn();          // objectes mobils a l'estat inicial
                enemy_init();              // enemics a la seva posicio inicial
                if (g_checkpoint) {
                    s_px8 = (i16)(s_lv.chk_px * SUB);
                    s_py8 = (i16)(s_lv.chk_py * SUB);
                    g_cam_x4 = (u16)s_lv.chk_cam_x4;
                    g_cam_row = (u16)s_lv.chk_cam_row;
                } else {
                    s_px8 = (i16)(s_lv.start_px * SUB);
                    s_py8 = (i16)(s_lv.start_py * SUB);
                    g_cam_x4 = (u16)s_lv.cam0_x4;
                    g_cam_row = (u16)s_lv.cam0_row;
                }
                s_vx = 0; s_vy = 0;
                s_crouch_hold = 0;
                // El update del Banc 5 retorna aviat mentre mor, aixi que
                // aquests edge-detectors es queden amb l'ultim valor. Cal
                // reiniciar-los com al DOS en entrar de nou al nivell.
                s_jump_prev = 0;
                s_climb_prev = 0;
                s_grab_prev = 0;
                s_up_prev = 0;
                s_on_ground = 1;
                s_ground_elevator = -1;
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

        if (s_on_ground && s_ground_elevator >= 0) {
            MovingElevator* e = &g_mag_elevators[(u8)s_ground_elevator];
            i16 px = (i16)(s_px8 >> 3);
            // 1:1 DOS (do_level_handle_object_bonus_collision): compara el
            // CENTRE del jugador (xpos) amb el centre de l'objecte +/-
            // level_obj_w[type]:
            //   ascensor (type 7)  w=18 px DOS -> 9 px CPC
            //   premsa   (type 22) w=10 px DOS -> 5 px CPC
            // Abans es comparava la vora esquerra (px) amb +/-9, o sigui una
            // finestra real de +/-17 sobre el centre: Jake podia anar-hi
            // penjat mig cos fora i el pujaven dins la paret.
            {
                i16 pcx = (i16)(px + (PW >> 1));
                i16 half = (s_ground_elevator >= MAG_ELEVATOR_COUNT)
                               ? PRESS_HALF_W : ELEVATOR_HALF_W;
                if (pcx > (i16)(e->center_x - half) &&
                    pcx < (i16)(e->center_x + half)) {
                    s_py8 = (i16)(s_py8 + e->delta_y * SUB);
                } else {
                    s_ground_elevator = -1;
                    s_on_ground = 0;
                }
            }
        }

        // 2. Pas de física genèrica de col·lisió sòlida al motor resident
        dbg_border(0x57);
        player_physics_step(g_belt_push, s_climb_prev, jump, (u8)(crouch || s_crouch_hold));

        // 3. Càmera i deadzone
        {
            i16 px = (i16)(s_px8 >> 3);
            i16 py = (i16)(s_py8 >> 3);
            if (!s_scrolling_locked && !s_dying_timer) {
                i16 sy = (i16)(py - (i16)(g_cam_row * 8));
                i16 sx = (i16)(px - (i16)(g_cam_x4 * 4));
                if (sx > DEAD_R && g_cam_x4 < (u16)(s_lv.map_w_x2 - PLAY_CHARS)) {
                    g_cam_x4++;
                    move_x = 1;
                } else if (sx < DEAD_L && g_cam_x4 > 0) {
                    g_cam_x4--;
                    move_x = -1;
                }
                // 1:1 DOS (level.c: do_level_update_scrolling2, scroll suau): el
                // origen Y de la pantalla segueix EXACTAMENT la posicio del
                // jugador (screen_tilemap_yorigin += dy, sense limit de
                // velocitat). Abans la camera nomes baixava 1 fila (8 px) per
                // frame, mes lent que la caiguda maxima (15 px/frame com al
                // DOS: ymaxvelocity=15): el terra trigava a fer-se visible i
                // Jake "aterritava" a les fos. Fins a 2 files per frame (16 px).
                if (sy > DEAD_B) {
                    // 1:1 DOS (level.c: do_level_update_scrolling2, scroll
                    // suau): el origen Y de la pantalla segueix el jugador
                    // SENSE limit de velocitat. Abans la camera nomes
                    // baixava 1 fila (8 px) per frame, mes lent que la
                    // caiguda maxima (15 px/frame com al DOS:
                    // ymaxvelocity=15): el terra trigava a fer-se visible i
                    // Jake "aterritava" a les fos. Ara la fila objectiu es
                    // calcula exactament (fins a 2 files per frame = 16 px).
                    u16 d = ((u16)(sy - DEAD_B) + 7) >> 3;
                    if (d > 2) d = 2;
                    if (g_cam_row + d > s_lv.max_cam_row) d = s_lv.max_cam_row - g_cam_row;
                    g_cam_row += d;
                    move_y = (i8)d;
                } else if (sy < DEAD_T && g_cam_row > 0) {
                    // 1:1 DOS: simètric a la baixada (fins a 2 files/frame).
                    // Abans només pujava 1 fila/frame i la tuberia (op17/18/19,
                    // tiles.c:305-333, sense scroll propi) no deixava veure
                    // l'obrer de dalt abans d'entrar-hi. Sense auto-scroll ni
                    // congelar l'obrer (el DOS no ho fa: level.c:1861-1864).
                    u16 d = ((u16)(DEAD_T - sy) + 7) >> 3;
                    if (d > 2) d = 2;
                    if (d > g_cam_row) d = g_cam_row;
                    g_cam_row -= (u16)d;
                    move_y = (i8)(-(i8)d);
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

        dbg_border(0x4C);
        // --- Restaurar el fons al BACKBUFFER (LIFO) ---
        // Ordre de dibuix: caixa -> Jake -> globus/paraigües. El restore va
        // al revés: globus/paraigües -> Jake -> caixa.
        sprite_restore_umbrella();
        sprite_restore_balloon();
        if (s_have_drawn[s_back_page]) {
            sprite_restore_player();
            s_have_drawn[s_back_page] = 0;
        }
        carry_restore(s_back_page);
        // Restore LIFO (invers al draw world->enemic->jugador):
        // l'enemic abans que els ascensors (els dibuixa a sobre).
        if (!s_in_room) {
            enemy_restore(s_back_page);
            moving_restore(s_back_page, (move_x != 0 || move_y != 0));
            moving_popup_restore(s_back_page);
            dbg_border(0x57);
            sync_backbuffer(page_dx, page_dy, g_cam_x4, g_cam_row);
            bc_a = s_back_page;
            moving_draw_conveyor_tiles();
        }
        world_flush_repaints();
        g_vram_start = camera_ma(g_cam_x4, g_cam_row);
        dbg_border(0x47);
        hud_render(s_back_page, (page_dx != 0 || page_dy != 0));
        cur = select_player_anim(s_climb_prev, move, jump, (u8)(crouch || s_crouch_hold), (i16)dsy);

        dbg_border(0x52);
        // Dibuixar objectes mòbils i sprites sobre el fons actualitzat
        if (!s_in_room) {
            moving_draw(s_back_page, g_cam_x4, g_cam_row);
            enemy_draw(s_back_page);
        }

        // 1:1 DOS: la caixa portada es dibuixa ABANS del jugador (objectes
        // 35/37 abans del 39), així en Jake queda per davant i no sembla que
        // estiguin en plans diferents. El restore va en ordre invers (LIFO).
        carry_draw(s_back_page);

        g_spr_y = (u8)dsy;
        g_spr_x = (u8)dsx;

        if (s_dying_timer || !(s_invuln_timer & 2)) {
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

        if (s_dying_timer && g_lives_count <= 1) {
            draw_gameover_banner(s_back_page);
        }

                dbg_border(0x54);
        // Sincronització vertical fluida a 25 Hz (2 VSYNCs = 40 ms)
        cpc_wait_vsync_start();
        if ((u8)(g_ticks - last_ticks) < 2) {
            cpc_wait_vsync_start();
        }
        last_ticks = g_ticks;
        crtc_set_display_start((u16)((s_back_page == 1 ? 0x2000 : 0x3000) + g_vram_start));

        s_back_page ^= 1;
        g_vram_base_hi = (s_back_page == 1) ? 0x80 : 0xC0;
        s_pending_x = move_x;
        s_pending_y = move_y;

        // 1:1 DOS (level.c): 50 frames de celebracio i despres mapa/nivell
        // seguent; al darrer nivell es torna al primer.
        if (g_level_complete) {
            if (s_complete_wait < 50) {
                s_complete_wait++;
            } else {
                s_complete_wait = 0;
                g_level_complete = 0;
                if (g_map_level < 5) g_map_level++;
                else g_map_level = 0;
                mus_stop();
                g_mus_hold = 1;
                palette_black();
                crtc_set_display_start(0x3000);
                load_front_bank();
                s_back_page = 1;
                g_vram_base_hi = 0x80;
                g_front_map_only = 1;
                g_keep_counters = 1;   // el nivell seguent hereta comptadors
                break;
            }
        }
    }
    }
}



