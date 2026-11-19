// ============================================================
// BLUES BROTHERS CPC - Motor Genèric Resident (Bloc 0)
// ============================================================
//   - video_init(): RMR Mode 0 + CRTC + paleta (protocol GA correcte)
//   - Scroll CRTC en anell de 16 KB (single buffer a 0xC000; RAM 2 és utilitat).
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

#include "level_params.h"

extern void video_init(void);
extern void render_all(u16 cam_col, u16 cam_row);
extern void render_column(u16 cam_col, u16 cam_row, u16 sx);
extern void render_column_to_buf(u16 cam_col, u16 cam_row, u16 sx);
extern void copy_column_from_buf(u16 cam_col, u16 cam_row, u16 sx);
extern void render_row(u16 cam_col, u16 cam_row, u16 sy);
extern void restore_world_scroll(u8 mode);
extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);
extern void hud_init(void);
extern void hud_render(u8 full_v, u8 force);
extern void crtc_set_display_start(u16 ma);
extern void cpc_install_isr(void);
extern volatile u8 g_ticks;
extern volatile u8 g_irq_phase;
extern volatile u8 g_split_en;
extern volatile u16 g_play_ma;

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
#define VY_MAX_UP   (21 * SUB)
#define GRAV        16
#define JUMP_VY     (-112)
#define DEAD_L      48
#define DEAD_R      89
#define DEAD_T      32
#define DEAD_B      116
#define CRATE_FLY_FRAME ((const u8*)0x7A20)

static const u8 s_crate_walk[6] = { 14, 12, 13, 15, 12, 13 };
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

// Caché lookahead de la columna de scroll (320 B a RAM 2: 0xBC00 + 0xBD00).
// S'omple al final del frame per a la columna que exposarà el frame següent.
static __at(0x9E58) u8  s_col_cache_valid;
static __at(0x9E59) u16 s_col_cache_x4;
static __at(0x9E5B) u16 s_col_cache_row;
static __at(0x9E5D) u8  s_col_cache_col;

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
// ============================================================
// Dades fredes residents reubicades als gaps de RAM 2.
// Aquestes zones les trepitja el pak de nivell (0x8320..0xB7FF):
// tot el que hi visqui s'ha de reinicialitzar DESPRES de la carrega.
//  0x8600  s_carry_bg_c0       (320 B, scratch globus/paraigua)
//  0x8E80  s_lv                (93 B, level_params_load)
//  0x9600  g_mag_elevators     (80 B, moving_init; ldir de 128 B)
//  0x9E00  s_mn_* + s_cd_* + s_rep_* + s_carry_* (estat de frame)
//  0xBE10  s_chs_buf/s_lvl_desc/s_lp_* (carrega; FORA del scratch del pak)
// ============================================================
__at(0x9E50) u8 s_carry_drawn[2];
static __at(0x9E52) u8 s_carry_drawn_span;
static __at(0x9E53) u8 s_carry_drawn_rows;
static __at(0x9E56) u16 s_carry_dst;
// Buffers de fons de caixes al Banc 7 dins del gap lliure (0x7DE0..0x7EFF):
// 64 B per pagina (0x7E00 per p=0, 0x7E40 per p=1). No col·lideix amb els frames d'en Jake!
#define CRATE_BG_PAGE(p) ((u16)(0x7E00 + ((u16)(p) << 6)))

i8  s_ground_elevator = -1;
u8  g_face;
u8  s_anim_idx, s_anim_timer;
u8  s_dazed_timer;
u8  s_dying_timer;
u8  s_invuln_timer;

static __at(0x9E54) u8 s_have_drawn;
static u8 s_hflip_cur = 0xFF;
static u8 s_prev_jdsx, s_prev_jdsy;
static u8 s_prev_jcur = 0xFF, s_prev_jface, s_prev_jgrate, s_prev_jcarry;

__at(0x9E40) u8 s_rep_n;
__at(0x9E41) u8 s_rep_col[4];
__at(0x9E45) u8 s_rep_row[4];
__at(0x9E49) u8 s_rep_tile[4];

static u8 s_complete_wait;

void main(void);

extern void render_room(u8 room_idx);
extern void palette_black(void);
extern void palette_restore(void);
extern u8 palette_table[16];

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
__at(0x8E80) LevelParams s_lv;

void level_params_load(void) {
    // El bloc de parametres del nivell es llegeix del paquet (Banc C1:0x7680)
    // i es queda al resident: la part u8 (geometria, tiles, mides) es usa a
    // cada frame; els valors de 16 bits (start, checkpoint, camera) tambe.
    u8 prev = bank_set(0xC1);
    cpct_memcpy(&s_lv, (const void*)0x7680, sizeof(LevelParams));
    bank_restore(prev);
}

// get_trig_byte, tile_type, tile_flags i is_floor_solid viuen en ASM natiu
// a engine/tile_blit.s (0 B d'IX frame).
extern u8 get_trig_byte(u16 col, u16 row, u8 offset);
extern u8 tile_type(u16 col, u16 row);
extern u8 tile_flags(u16 col, u16 row);
extern u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch);
#define is_ceiling_solid(col, row) is_floor_solid((col), (row), -1, 0)

static void world_flush_repaints(void) {
    u8 i = 0;
    while (i < s_rep_n) {
        render_tile_world(s_rep_tile[i], s_rep_col[i], s_rep_row[i],
                          g_cam_x4, g_cam_row);
        s_rep_n--;
        if (i != s_rep_n) {
            s_rep_col[i] = s_rep_col[s_rep_n];
            s_rep_row[i] = s_rep_row[s_rep_n];
            s_rep_tile[i] = s_rep_tile[s_rep_n];
        }
    }
}

static u16 camera_ma(u16 x4, u16 row) {
    return (u16)((row * 40 + x4) & 0x03FF);
}

static void repaint_screen(void) {
    s_col_cache_valid = 0;
    g_vram_start = camera_ma(g_cam_x4, g_cam_row);
    if (s_in_room) render_room(0);
    else render_all(g_cam_x4, g_cam_row);
    hud_render(1, 1);
    crtc_set_display_start((u16)(0x3000 + g_vram_start));
}

static void draw_movers_now(void);

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

    if (dst_row >= s_lv.room_row0) {
        // Entering Room (sense __divuchar ni __mulint)
        u8 base_col = 0;
        while ((u8)(base_col + s_lv.room_cols) <= dst_col) {
            base_col += s_lv.room_cols;
        }
        s_in_room = 1;
        s_scrolling_locked = 1;
        g_cam_x4 = (u16)base_col << 1;
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
    s_have_drawn = 0;
    s_hflip_cur = 0xFF;
    s_carry_drawn[0] = 0;
    {
        u8 m;
        for (m = 0; m < MAG_MOVER_COUNT; m++) g_mag_elevators[m].drawn[0] = 0;
    }
    s_rep_n = 0;
    s_col_cache_valid = 0;

    repaint_screen();
    if (!s_in_room) {
        draw_movers_now();
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



static void draw_movers_now(void) {
    bc_a = 0;
    moving_draw(0, g_cam_x4, g_cam_row);
}

static void sync_backbuffer(i8 dx, u16 target_x4, u16 target_row) {
    u8 col = (u8)(dx > 0 ? 39 : 0);
    dbg_border(0x4C);
    if (dx > 1) render_column(target_x4, target_row, 38);
    if (s_col_cache_valid && s_col_cache_x4 == target_x4 &&
        s_col_cache_row == target_row && s_col_cache_col == col) {
        copy_column_from_buf(target_x4, target_row, col);
        s_col_cache_valid = 0;
    } else {
        render_column(target_x4, target_row, col);
    }
    if (dx < -1) render_column(target_x4, target_row, 1);
}

static void render_rows_edge(u8 n, u8 from_bottom) {
    u8 i;
    for (i = 0; i < n && i < 4; i++) {
        render_row(g_cam_x4, g_cam_row, (u8)(from_bottom ? (19 - i) : i));
    }
}

static void carry_restore(void) __naked {
    __asm
        ld   hl, #0x9E50            ;; _s_carry_drawn
        ld   a, (hl)
        or   a
        ret  z
        ld   (hl), #0
        ld   a, #0xC7
        call _bank_set
        push af
        ld   hl, (0x9E56)           ;; _s_carry_dst
        ld   (_g_moving_dst), hl
        ld   hl, #0x7E00
        ld   (_g_moving_background), hl
        ld   hl, (0x9E52)           ;; L=_s_carry_drawn_span, H=_s_carry_drawn_rows
        ld   (_g_moving_span), hl
        call _moving_restore_box
        pop  af
        jp   _bank_restore
    __endasm;
}

static void carry_draw(void) __naked {
    __asm
        ld   a, (_s_carry_kind)
        dec  a
        ret  nz

        ld   a, (_s_carry_state)
        or   a
        jr   nz, cd_thrown$
        ld   a, (_s_invuln_timer)
        bit  1, a
        ret  nz
        ld   hl, (_s_px8)
        sra  h
        rr   l
        sra  h
        rr   l
        sra  h
        rr   l
        ld   de, #4
        add  hl, de
        res  0, l
        push hl                     ;; (SP) = cx
        ld   hl, (_s_py8)
        sra  h
        rr   l
        sra  h
        rr   l
        sra  h
        rr   l
        ld   de, #-16
        add  hl, de                 ;; HL = cy (16 rows: py-16..py-1, disjunt de Jake)
        jr   cd_coords_ok$

    cd_thrown$:
        ld   hl, (_s_carry_x)
        sra  h
        rr   l
        sra  h
        rr   l
        sra  h
        rr   l
        res  0, l
        push hl                     ;; (SP) = cx
        ld   hl, (_s_carry_y)
        sra  h
        rr   l
        sra  h
        rr   l
        sra  h
        rr   l                      ;; HL = cy

    cd_coords_ok$:
        ;; Y clipping: view_y = g_cam_row << 3
        ex   de, hl                 ;; DE = cy
        ld   hl, (_g_cam_row)
        add  hl, hl
        add  hl, hl
        add  hl, hl                 ;; HL = view_y
        ld   b, h
        ld   c, l                   ;; BC = view_y
        ld   h, d
        ld   l, e                   ;; HL = cy
        or   a
        sbc  hl, bc                 ;; HL = dy = cy - view_y
        push hl                     ;; save dy
        ld   de, #15
        add  hl, de
        ld   de, #175
        or   a
        sbc  hl, de
        pop  hl                     ;; HL = dy
        jr   c, cd_y_vis$
        pop  hl                     ;; discard cx
        ret

    cd_y_vis$:
        bit  7, h
        jr   z, cd_y_nonneg$
        ;; dy < 0 (-15..-1): clip_y0 = view_y (BC), start_row = -dy, row_count = 16 + dy
        xor  a
        sub  l
        ld   d, a                   ;; D = start_row
        ld   a, #16
        add  a, l
        ld   e, a                   ;; E = row_count
        push bc                     ;; stack: cx, clip_y0
        jr   cd_y_done$

    cd_y_nonneg$:
        ;; dy >= 0 (0..159): clip_y0 = cy (view_y + dy)
        push hl
        add  hl, bc                 ;; HL = clip_y0
        ex   (sp), hl               ;; HL = dy, (SP) = clip_y0
        ld   d, #0                  ;; D = start_row = 0
        ld   a, l
        cp   #145
        jr   c, cd_y_full$
        ld   a, #160
        sub  l
        ld   e, a                   ;; E = 160 - dy
        jr   cd_y_done$
    cd_y_full$:
        ld   e, #16                 ;; E = row_count = 16

    cd_y_done$:
        ;; stack: cx, clip_y0; D = start_row, E = row_count
        pop  bc                     ;; BC = clip_y0
        pop  hl                     ;; HL = cx
        push de                     ;; stack: D=start_row, E=row_count
        push bc                     ;; stack: row_pair, clip_y0
        push hl                     ;; stack: row_pair, clip_y0, cx

        ;; X clipping: view_x = g_cam_x4 << 2
        ld   de, (_g_cam_x4)
        ex   de, hl
        add  hl, hl
        add  hl, hl                 ;; HL = view_x
        ld   b, h
        ld   c, l                   ;; BC = view_x
        pop  hl                     ;; HL = cx
        push hl                     ;; stack: row_pair, clip_y0, cx
        or   a
        sbc  hl, bc                 ;; HL = dx = cx - view_x
        push hl
        ld   de, #7
        add  hl, de
        ld   de, #167
        or   a
        sbc  hl, de
        pop  hl                     ;; HL = dx
        jr   c, cd_x_vis$
        pop  hl
        pop  hl
        pop  hl
        ret

    cd_x_vis$:
        bit  7, h
        jr   z, cd_x_nonneg$
        ;; dx < 0 (-6..-2): clip_x0 = view_x (BC), start_byte = (-dx)>>1, byte_count = 4 - start_byte
        xor  a
        sub  l
        srl  a                      ;; A = start_byte
        ld   h, a                   ;; H = start_byte
        ld   a, #4
        sub  h
        ld   l, a                   ;; L = byte_count
        pop  de                     ;; discard cx
        ld   d, b
        ld   e, c                   ;; DE = clip_x0 = view_x
        jr   cd_x_done$

    cd_x_nonneg$:
        ;; dx >= 0 (0..158): clip_x0 = cx
        ld   a, l
        cp   #154
        jr   c, cd_x_full$
        ld   a, #160
        sub  l
        srl  a
        ld   l, a                   ;; L = byte_count
        jr   cd_x_set$
    cd_x_full$:
        ld   l, #4
    cd_x_set$:
        ld   h, #0                  ;; H = start_byte = 0
        pop  de                     ;; DE = clip_x0 = cx

    cd_x_done$:
        ;; stack: row_pair (D=start_row, E=row_count), clip_y0
        ;; DE = clip_x0, H = start_byte, L = byte_count
        pop  bc                     ;; BC = clip_y0
        ex   (sp), hl               ;; (SP) = H:start_byte, L:byte_count; HL = D:start_row, E:row_count
        push hl                     ;; stack: byte_pair, row_pair

        ;; ring_address(0, clip_x0, clip_y0): A=0, DE=clip_x0, (SP)=clip_y0
        push bc                     ;; arg y = clip_y0 (callee-cleaned by _ring_address)
        xor  a
        call _ring_address          ;; DE = dst
        ld   (_g_moving_dst), de
        ld   (0x9E56), de           ;; _s_carry_dst

        ld   a, #0xC7
        call _bank_set
        push af                     ;; stack: byte_pair, row_pair, prev_bank

        ld   hl, #0x7E00
        ld   (_g_moving_background), hl

        pop  af                     ;; A = prev_bank
        pop  bc                     ;; B = start_row, C = row_count
        pop  de                     ;; D = start_byte, E = byte_count
        push af                     ;; stack: prev_bank

        ld   a, e
        ld   (0x9E52), a            ;; _s_carry_drawn_span
        ld   (_g_moving_span), a
        ld   a, c
        ld   (0x9E53), a            ;; _s_carry_drawn_rows
        ld   (_g_moving_rows), a

        ld   a, e
        add  a, a
        ld   c, a
        ld   a, #8
        sub  c
        ld   (_g_moving_spr_skip), a

        ;; sprite = 0x7A20 + (start_row << 3) + (start_byte << 1)
        ld   l, b
        ld   h, #0
        add  hl, hl
        add  hl, hl
        add  hl, hl
        sla  d
        ld   e, d
        ld   d, #0
        add  hl, de
        ld   de, #0x7A20
        add  hl, de
        ld   (_g_moving_sprite), hl

        call _moving_blit_box
        pop  af
        call _bank_restore
        ld   a, #1
        ld   (0x9E50), a            ;; _s_carry_drawn[0] = 1
        ret
    __endasm;
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
            return anim_step(4, 2) ? 5 : 9;
        }
        s_anim_timer = 0;
        return 5;
    }
    if (climbing == 2) {
        if (move != 0) {
            return (u8)(21 + anim_step(4, 3));
        }
        if (jump || crouch) {
            return anim_step(4, 2) ? 24 : 21;
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
        // 1:1 DOS: repòs amb caixa/paraigües = animframes_ptr[44/4] =
        // animframe_00c7 = [5, 14,14,14,14,14] (SQV 14 -> cel·la 13).
        return 13;
    }
    if (!s_on_ground || (u16)(bsy + 30) > 160) {
        return 4;
    }
    if (crouch) {
        if (move != 0) {
            return anim_step(6, 2) ? 8 : 7;
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

static i16 s_ps_px, s_ps_py, s_ps_evx, s_ps_prev_feet, s_ps_curr_feet, s_ps_elev_top;
static u16 s_ps_prev_head, s_ps_c_mid1, s_ps_c_mid2, s_ps_feet_row, s_ps_head_row, s_ps_top_row, s_ps_col;
static u8  s_ps_climbing, s_ps_jump, s_ps_crouch, s_ps_landed;

// Col·lisió dels ítems de les sales: gestionada 1:1 per b5_check_bonus_triggers().

static void player_physics_step(i16 belt_push, u8 climbing, u8 jump, u8 crouch) {
    s_ps_climbing = climbing;
    s_ps_jump = jump;
    s_ps_crouch = crouch;
    s_ps_px = (i16)(s_px8 >> 3);
    s_ps_py = (i16)(s_py8 >> 3);
    s_ps_evx = (i16)(s_vx + belt_push);

    if (s_carry_kind == 1 && s_carry_state) {
        i16 cx, cy, sx, sy;
        u8 tt;
        s_carry_x = (i16)(s_carry_x + s_carry_vx);
        cx = (i16)(s_carry_x >> 3);
        cy = (i16)(s_carry_y >> 3);
        sx = (i16)((cx - (i16)(g_cam_x4 * 4)) >> 1);
        sy = (i16)(cy - (i16)(g_cam_row * 8));
        s_ps_col = (u16)(((s_carry_vx > 0) ? (cx + 8) : cx) >> 3);
        s_ps_feet_row = (u16)((cy + 6) >> 4);
        tt = tile_type(s_ps_col, s_ps_feet_row);
        if (sx < -4 || sx > 76 || sy < -16 || sy > 160 || cx < 16 || cx > (i16)(s_lv.map_w_px - 24) ||
            tt == 6 || enemy_check_crate_hit(cx, cy, s_carry_vx)) {
            carry_abort();
        }
    }

    // --- Moviment horitzontal i col·lisió de parets ---
    {
        s_ps_feet_row = (u16)((s_ps_py + 28) >> 4);
        s_ps_head_row = (u16)((s_ps_py + 16) >> 4);
        s_ps_top_row  = (u16)(s_ps_py >> 4);
        if (s_ps_evx > 0) {
            u16 next_px = (u16)((s_px8 + s_ps_evx) >> 3);
            u8 fl;
            s_ps_col = (u16)((next_px + 11) >> 3);
            fl = tile_flags(s_ps_col, s_ps_feet_row);
            if (!s_ps_crouch && s_ps_climbing != 2) fl |= (tile_flags(s_ps_col, s_ps_head_row) | tile_flags(s_ps_col, s_ps_top_row));
            if (fl & 1) {
                s_vx = 0;
            } else {
                s_px8 = (i16)(s_px8 + s_ps_evx);
            }
        } else if (s_ps_evx < 0) {
            u16 next_px = (u16)((s_px8 + s_ps_evx) >> 3);
            u8 fl;
            s_ps_col = (u16)((next_px + 4) >> 3);
            fl = tile_flags(s_ps_col, s_ps_feet_row);
            if (!s_ps_crouch && s_ps_climbing != 2) fl |= (tile_flags(s_ps_col, s_ps_head_row) | tile_flags(s_ps_col, s_ps_top_row));
            if (fl & 2) {
                s_vx = 0;
            } else {
                s_px8 = (i16)(s_px8 + s_ps_evx);
            }
        }
    }
    {
        i16 min_x = s_in_room ? (i16)(g_cam_x4 << 5) : 0;
        i16 max_x = s_in_room ? (i16)(min_x + 1152) : (i16)((s_lv.map_w_px - PW) * SUB);
        if (s_px8 < min_x) { s_px8 = min_x; s_vx = 0; }
        else if (s_px8 > max_x) { s_px8 = max_x; s_vx = 0; }
    }
    s_ps_px = (i16)(s_px8 >> 3);

    // --- Moviment vertical i gravetat ---
    {
        u8 h_off = s_ps_crouch ? 13 : 0;
        s_ps_prev_feet = (i16)(s_ps_py + PH);
        s_ps_prev_head = (u16)((s_ps_py + h_off) >> 4);
        if (!s_ps_climbing) {
            if (s_carry_kind == 2 && !s_carry_state) {
                s_vy = -8;
                s_on_ground = 0;
                s_ground_elevator = -1;
            } else {
                if (!s_on_ground) {
                    s_vy = (i16)(s_vy + GRAV);
                    if (s_vy > VY_MAX) s_vy = VY_MAX;
                    if (s_vy < -VY_MAX_UP) s_vy = -VY_MAX_UP;
                } else {
                    s_vy = 0;
                }
                if (s_ps_jump && !s_jump_prev && s_on_ground) {
                    u8 di, si;
                    s_ps_col = (u16)((s_ps_px + 5) >> 3);
                    s_ps_feet_row = (u16)((s_ps_py + 28) >> 4);
                    di = (s_ps_feet_row >= 2) ? tile_type(s_ps_col, (u16)(s_ps_feet_row - 2)) : 0;
                    si = tile_type(s_ps_col, s_ps_feet_row);
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
        s_jump_prev = s_ps_jump;

        s_py8 = (i16)(s_py8 + s_vy);
        s_ps_py = (i16)(s_py8 >> 3);

        {
            s_ps_curr_feet = (i16)(s_ps_py + PH);
            s_ps_c_mid1 = (u16)((s_ps_px + 5) >> 3);
            s_ps_c_mid2 = (u16)((s_ps_px + 8) >> 3);
            s_ps_landed = 0;

            if (s_vy >= 0 && s_ps_climbing != 1 && g_on_ice != 2) {
                i8 elevator_id;
                bc_a = (u16)s_ps_px; bc_b = (u16)s_ps_prev_feet; bc_c = (u16)s_ps_curr_feet;
                bc_d = (u16)s_vy; bc_e = (u16)&s_ps_elev_top;
                elevator_id = moving_find_landing();
                if (elevator_id >= 0) {
                    s_ps_py = s_ps_elev_top;
                    s_py8 = (i16)(s_ps_py * SUB);
                    s_vy = 0;
                    s_on_ground = 1;
                    s_ground_elevator = elevator_id;
                    s_ps_landed = 1;
                }
                {
                    u16 max_r = s_in_room ? (u16)(s_lv.room_row0 + s_lv.room_rows) : s_lv.map_h;
                    s_ps_feet_row = (u16)(s_ps_curr_feet >> 4);
                    if (!s_ps_landed && s_ps_feet_row < max_r) {
                        i16 surf = (i16)(s_ps_feet_row << 4);
                        if (s_ps_prev_feet <= surf && s_ps_curr_feet >= surf) {
                            u8 s = is_floor_solid(s_ps_c_mid1, s_ps_feet_row, s_vy, s_ps_crouch) |
                                   is_floor_solid(s_ps_c_mid2, s_ps_feet_row, s_vy, s_ps_crouch);
                            if (s) {
                                s_ps_py = (i16)(surf - PH);
                                s_py8 = (i16)(s_ps_py * SUB);
                                if (s & 2) {
                                    s_vy = (i16)(-(s_vy + (6 * SUB)));
                                    if (s_vy < -VY_MAX_UP) s_vy = -VY_MAX_UP;
                                    s_on_ground = 0;
                                } else {
                                    s_vy = 0;
                                    s_on_ground = 1;
                                }
                                s_ground_elevator = -1;
                                s_ps_landed = 1;
                            }
                        }
                    }
                }
                if (!s_ps_landed) {
                    s_on_ground = 0;
                    s_ground_elevator = -1;
                }
            } else if (s_vy < 0) {
                u16 r = s_ps_prev_head;
                u8 n = 0;
                s_ps_head_row = (u16)((s_ps_py + h_off) >> 4);
                while (r >= s_ps_head_row && n < 4) {
                    if (is_ceiling_solid(s_ps_c_mid1, r)) {
                        s_ps_head_row = r;
                        break;
                    }
                    if (r == 0) break;
                    r--; n++;
                }
                if (is_ceiling_solid(s_ps_c_mid1, s_ps_head_row)) {
                    s_ps_py = (i16)(((s_ps_head_row + 1) << 4) - h_off);
                    s_py8 = (i16)(s_ps_py * SUB);
                    s_vy = 0;
                }
                s_on_ground = 0;
                s_ground_elevator = -1;
            }
        }
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
static __at(0xBE50) const DiskFileDesc* s_lp_f;
static __at(0xBE52) u16 s_lp_crc;
static __at(0xBE54) u16 s_lp_dst;
static __at(0xBE56) u16 s_lp_off;
static __at(0xBE58) u16 s_lp_len;
static __at(0xBE5A) u8 s_lp_t;
static __at(0xBE5B) u8 s_lp_ok;
static __at(0xBE5C) u8 s_lp_n;
static __at(0xBE5D) u8 s_lp_i;
static __at(0xBE5E) u8 s_lp_prev;
static __at(0xBE5F) const u8* s_lp_d;

static u8 load_package(const DiskFileDesc* f, u16 crc) {
    const u8* pak = (const u8*)0x8320;
    s_lp_f = f;
    s_lp_crc = crc;
    s_lp_ok = 0;

    for (s_lp_t = 0; s_lp_t < 3 && !s_lp_ok; s_lp_t++) {
        if (!fdc_load_file(0xC0, s_lp_f, 0xC0, (void*)0x8320)) continue;
        if (fdc_crc16(pak, (u16)(s_lp_f->ondisk_bytes - 128)) == s_lp_crc) s_lp_ok = 1;
    }
    if (!s_lp_ok) return 0;
    if (pak[0] != 0x42 || pak[1] != 1) return 0;

    s_lp_n = pak[6];
    for (s_lp_i = 0; s_lp_i < s_lp_n; s_lp_i++) {
        s_lp_d = pak + 16 + (u16)s_lp_i * 8;
        s_lp_dst = (u16)(s_lp_d[2] | ((u16)s_lp_d[3] << 8));
        s_lp_off = (u16)(s_lp_d[4] | ((u16)s_lp_d[5] << 8));
        s_lp_len = (u16)(s_lp_d[6] | ((u16)s_lp_d[7] << 8));
        s_lp_prev = bank_set(s_lp_d[0]);
        if (s_lp_d[1] & 1) {
            zx0_decompress(pak + s_lp_off, (void*)s_lp_dst);
        } else {
            cpct_memcpy((void*)s_lp_dst, pak + s_lp_off, s_lp_len);
        }
        bank_restore(s_lp_prev);
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

static __at(0xBE10) u8 s_chs_buf[56];
static __at(0xBE48) DiskFileDesc s_lvl_desc;

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
        cpct_memcpy((void*)0xB800u, (const void*)0x6030u, 0x0400u);
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
        // L3 i L5 porten la imatge C1 en un paquet separat (L3C1.PAK, L5C1.PAK) per no
        // excedir els 28 sectors de WORLD. Els altres nivells la duen dins.
        if ((lvl == 2 || lvl == 4) && !load_level_file(lvl, 2)) {
            cpct_setBorder(0x44); while (1) { }
        }
        // Parametres del nivell (geometria, tiles, start, checkpoint...).
        // IMPORTANT: s_lv viu a 0x8E80, dins del scratch del pak (0x8320..0xB7FF).
        // Els ENEMI es carreguen DESPRES del WORLD i el trepitgen; per tant
        // s'ha de recopiar AQUI, despres de totes les carregues.
        if (lvl != 0) {
            // Carrega SEMPRE el codi compartit de C6 (L1ENEMI). La
            // comprovacio "0x5A00 == 0xC3" es fragil: aquest byte pot
            // ser 0xC3 per RAM inicialitzada o per un preview del FRONT,
            // i llavors se saltava la carrega i s'executava brossa a
            // 0x5A00 (freeze/reset en carregar L2-L6).
            if (!load_level_file(0, 1)) {
                cpct_setBorder(0x43); while (1) { }
            }
        }
        if (!load_level_file(lvl, 1)) {
            cpct_setBorder(0x43); while (1) { }
        }
        level_params_load();
        cpct_memcpy(palette_table, s_lv.palette, 16);
    }

    // Aturar motor FDC un cop acabada la carrega de tots els paquets
    fdc_motor_off();

    video_init();

    {
        u8* t19 = (u8*)0x8320;
        u8 i;
        u8* dst;
        u8 t_crate = 19;
        u8 prev = bank_set(0xC5);
        for (i = 0; i < 220; i++) {
            if (((const u8*)s_lv.trig_off)[(u16)i * 5] == 5) {
                t_crate = i;
                break;
            }
        }
        bank_restore(prev);

        prev = bank_set(0xC4);
        cpct_memcpy(t19, (const void*)(0x4000 + ((u16)t_crate << 6)), 64);
        bank_restore(prev);

        prev = bank_set(0xC7);
        dst = (u8*)CRATE_FLY_FRAME;
        for (i = 0; i < 64; i++) {
            *dst++ = 0x00;
            *dst++ = t19[i];
        }
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
    const u8* e = ENEMY_RESTORE_TABLE;
    u16 n = *(const u16*)e;
    e += 2;
    while (n--) {
        u8 col = e[0];
        u8 row = e[1];
        u8 tile = e[2];
        e += 3;
        bank_set(0xC5);
        ((u8*)0x4000)[((u16)row << 7) + col] = tile;
        bank_set(0xC6);
    }

    bank_set(0xC1);
    e = (const u8*)(u16)s_lv.restore_off;
    n = *(const u16*)e;
    e += 2;
    while (n--) {
        u16 off = *(const u16*)e;
        u8 tile = e[2];
        e += 3;
        bank_set(0xC5);
        ((u8*)(u16)s_lv.rooms_off)[off] = tile;
        bank_set(0xC1);
    }
    bank_restore(prev);
}

// GAME OVER: codi comu al Banc 1 (src/hud_bank.c, MUSBANK). Escriu VRAM -> 0xC0.
extern void gameover_o(void);
static void draw_gameover_banner(void) {
    bc_a = 0;
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

static __at(0x9E00) u8 s_mn_sv_lives;
static __at(0x9E01) u8 s_mn_sv_hearts;
static __at(0x9E02) u8 s_mn_sv_vinyls;
static __at(0x9E03) u8 s_mn_sv_keep;
static __at(0x9E04) u8 s_mn_last_ticks;
static __at(0x9E05) i8 s_mn_move;
static __at(0x9E06) i8 s_mn_move_x;
static __at(0x9E07) i8 s_mn_move_y;
static __at(0x9E08) i8 s_mn_page_dx;
static __at(0x9E09) i8 s_mn_page_dy;
static __at(0x9E0A) u8 s_mn_jump;
static __at(0x9E0B) u8 s_mn_crouch;
static __at(0x9E0C) u8 s_mn_grab;
static __at(0x9E0D) u8 s_mn_cur;
static __at(0x9E0E) u8 s_mn_up_key;
static __at(0x9E0F) u16 s_mn_dsx;
static __at(0x9E11) u16 s_mn_dsy;
static __at(0x9E13) u16 s_mn_old_ma;
static __at(0x9E15) u16 s_mn_new_ma;

static void restore_fg_sprites(void) {
    if (s_have_drawn) {
        sprite_restore_player();
        s_have_drawn = 0;
    }
    sprite_restore_balloon();
    carry_restore();
}

static void draw_jake_now(u8 jake_vis) {
    g_spr_y = (u8)s_mn_dsy;
    g_spr_x = (u8)s_mn_dsx;
    if (jake_vis) {
        const u8* fr_addr = (g_face == 0)
            ? (const u8*)(u16)(PLAYER_FRAMES_BASE + ((u16)s_mn_cur << 9) - ((u16)s_mn_cur << 5))
            : (const u8*)0x7840;
        u8 prev_b = bank_set(PLAYER_FRAMES_BANK);
        sprite_blit_player(fr_addr);
        bank_restore(prev_b);
        s_have_drawn = 1;
        s_prev_jdsx = (u8)s_mn_dsx;
        s_prev_jdsy = (u8)s_mn_dsy;
        s_prev_jcur = s_mn_cur;
        s_prev_jface = g_face;
        s_prev_jgrate = g_grate_enable;
        s_prev_jcarry = s_carry_kind;
    } else {
        s_have_drawn = 0;
    }
}

static void draw_carry_only(void) {
    carry_draw();
    if (s_carry_kind == 2) {
        if (!s_carry_state) {
            g_spr_y = (u8)s_mn_dsy;
            g_spr_x = (u8)s_mn_dsx;
            sprite_blit_balloon();
        } else {
            i16 bx = (i16)(( (s_carry_x >> 3) - (i16)(g_cam_x4 * 4) ) >> 1);
            i16 by = (i16)((s_carry_y >> 3) - (i16)(g_cam_row * 8));
            if (bx >= 0 && bx <= (80 - SPR_WB) && by >= 28 && by <= 160) {
                g_spr_x = (u8)bx;
                g_spr_y = (u8)by;
                sprite_blit_balloon();
            } else {
                s_carry_kind = 0;
                s_carry_state = 0;
            }
        }
    } else if (s_carry_kind == 8) {
        g_spr_y = (u8)s_mn_dsy;
        g_spr_x = (u8)s_mn_dsx;
        sprite_blit_umbrella();
    }
}

static u8 restore_fg_swap(void) {
    g_vram_start = s_mn_old_ma;
    restore_fg_sprites();
    g_vram_start = s_mn_new_ma;
    return 1;
}

static void moving_restore_swap(u8 force) {
    g_vram_start = s_mn_old_ma;
    moving_restore(0, force);
    g_vram_start = s_mn_new_ma;
}

static void world_restore_swap(u8 mode) {
    g_vram_start = s_mn_old_ma;
    restore_world_scroll(mode);
    g_vram_start = s_mn_new_ma;
}

static void render_rows_edge_dy(void) {
    if (s_mn_page_dy) {
        render_rows_edge((u8)(s_mn_page_dy < 0 ? -s_mn_page_dy : s_mn_page_dy),
                         (u8)(s_mn_page_dy > 0));
    }
}

static void draw_fg_sprites(u8 jake_vis) {
    draw_carry_only();
    draw_jake_now(jake_vis);
}

static void fg_atomic_jake(u8 jake_vis) {
    if (s_have_drawn) {
        g_vram_start = s_mn_old_ma;
        sprite_restore_player();
        s_have_drawn = 0;
        g_vram_start = s_mn_new_ma;
    }
    draw_jake_now(jake_vis);
}

static void fg_restore_carry(void) {
    g_vram_start = s_mn_old_ma;
    sprite_restore_balloon();
    carry_restore();
    g_vram_start = s_mn_new_ma;
}

static void draw_fg_atomic(u8 jake_vis) {
    u8 up = (u8)(s_mn_page_dy < 0 || (!s_mn_page_dy && (u8)s_mn_dsy < s_prev_jdsy));
    if (s_carry_kind >= 2 && (u8)s_mn_dsy < 32) {
        restore_fg_swap();
        draw_fg_sprites(jake_vis);
        return;
    }
    if (up) fg_restore_carry();
    fg_atomic_jake(jake_vis);
    if (!up) fg_restore_carry();
    draw_carry_only();
}

static void pre_render_next_column(void) {
    u16 nx4;
    u8 col;
    if (!s_mn_page_dx || s_mn_page_dy) {
        s_col_cache_valid = 0;
        return;
    }
    nx4 = (u16)(g_cam_x4 + s_mn_page_dx);
    col = (u8)(s_mn_page_dx > 0 ? 39 : 0);
    render_column_to_buf(nx4, g_cam_row, col);
    s_col_cache_x4 = nx4;
    s_col_cache_row = g_cam_row;
    s_col_cache_col = col;
    s_col_cache_valid = 1;
}

static void sync_backbuffer_now(void) {
    sync_backbuffer(s_mn_page_dx, g_cam_x4, g_cam_row);
}

static void render_frame(void) {
    u8 do_scroll = (u8)(s_mn_page_dx != 0 || s_mn_page_dy != 0);
    u8 wmode = (u8)(s_rep_n ? 0 : (s_mn_page_dx ? 1 : 2));
    u8 jake_vis = (u8)(s_climb_prev != 3 && (s_dying_timer || !(s_invuln_timer & 2)));
    u8 elev_near = 0;
    u8 en_near_jake = (u8)(g_jake_en_near & 1);
    u8 en_near_elev = (u8)(g_jake_en_near & 2);
    u8 keep_jake, early_jake, conv_jake, early_elev, no_ov;
    u8 fg_restored = 0, elev_done = 0;

    s_mn_old_ma = g_vram_start;
    s_mn_new_ma = camera_ma(g_cam_x4, g_cam_row);

    // 0. Latch R12/R13 IMMEDIATAMENT a l'inici del VBLANK (abans de la línia 312 / VCC=0)
    if (do_scroll) {
        crtc_set_display_start((u16)(0x3000 + s_mn_new_ma));
    }

    if (!s_in_room) {
        const MovingElevator* ev = g_mag_elevators;
        u8 k;
        for (k = MAG_MOVER_COUNT; k; k--, ev++) {
            if (ev->drawn[0] &&
                (u16)(ev->center_x - s_ps_px + 16) < 48 &&
                (u16)(ev->y - s_ps_py + 20) < 84) {
                elev_near = 1;
                break;
            }
        }
    }

    no_ov = (u8)(!en_near_jake && !s_carry_state && !(elev_near && en_near_elev));
    conv_jake = s_page_conveyor_phase[1];
    s_page_conveyor_phase[1] = 0;
    keep_jake = (u8)(!do_scroll && no_ov && !elev_near && !s_rep_n && s_have_drawn && jake_vis &&
                     !s_invuln_timer && !g_grate_enable && !conv_jake &&
                     s_carry_kind == s_prev_jcarry &&
                     (u8)s_mn_dsx == s_prev_jdsx && (u8)s_mn_dsy == s_prev_jdsy &&
                     s_mn_cur == s_prev_jcur && g_face == s_prev_jface &&
                     g_grate_enable == s_prev_jgrate);

    early_jake = (u8)(!keep_jake && no_ov && !s_rep_n && !elev_near && !conv_jake &&
                      !g_grate_enable && (u8)s_mn_dsy < 96 &&
                      (!s_mn_page_dx || ((u8)(s_prev_jdsx - 4) <= 64 && (u8)((u8)s_mn_dsx - 4) <= 64)));

    early_elev = (u8)(!s_in_room && !s_rep_n && !en_near_elev && !s_mn_page_dy &&
                      (early_jake || !elev_near));

    // 1. Restauracions d'objectes que toquen la vora ABANS de render_rows_edge / sync_backbuffer
    //    (al ring circular de 2KB, dibuixar noves files/columnes abans de restaurar provoca
    //    que el restore posterior trepitgi el cel o tiles nous amb fons antic).
    {
        u8 world_done = 0;
        u8 en_restored = s_rep_n;
        if (early_jake && !s_in_room) {
            g_vram_start = s_mn_new_ma;
            render_rows_edge_dy();
            if (s_mn_page_dx) {
                g_vram_start = s_mn_old_ma;
                enemy_restore(2);
                g_vram_start = s_mn_new_ma;
                sync_backbuffer_now();
            }
            dbg_border(0x52);
            draw_fg_atomic(jake_vis);
            fg_restored = 1;
            keep_jake = 1;
            if (do_scroll) {
                world_restore_swap(2);
                world_done = 1;
            } else if (early_elev) {
                moving_restore_swap(0);
            }
        } else if (do_scroll && !s_in_room) {
            if (!keep_jake && (s_rep_n || s_carry_state ||
                (elev_near && !early_elev) ||
                (s_mn_page_dx && ((u8)s_prev_jdsx < 8 || (u8)s_prev_jdsx >= 68)))) {
                fg_restored = restore_fg_swap();
            }
            world_restore_swap(wmode);
            world_done = 1;
            render_rows_edge_dy();
            if (s_mn_page_dx) sync_backbuffer_now();
        } else if (early_elev) {
            moving_restore_swap((u8)(elev_near || (s_carry_kind && s_carry_state)));
        } else {
            g_vram_start = s_mn_new_ma;
        }

        // 2. Restauracions restants i tiles animats (sense esborrar enemics per endavant!)
        if (!keep_jake && !fg_restored &&
            (conv_jake || s_rep_n || (!early_elev && elev_near) || s_carry_state)) {
            dbg_border(0x55);
            fg_restored = restore_fg_swap();
        }
        if (!s_in_room && !world_done) {
            restore_world_scroll((u8)(wmode | (early_elev ? 0x80 : 0)));
        }
        if (s_rep_n) world_flush_repaints();
        dbg_border(0x4E);
        if (!s_in_room && (s_page_conveyor_phase[0] != s_conveyor_phase || g_grate_enable)) {
            bc_a = 0;
            moving_draw_conveyor_tiles();
        }
        if (early_elev) {
            draw_movers_now();
            elev_done = 1;
        }
        if (!keep_jake && fg_restored && no_ov && (elev_done || !elev_near)) {
            dbg_border(0x52);
            draw_fg_sprites(jake_vis);
            keep_jake = 1;
        }

        // 6. Dibuix d'enemics (atomic restore->blit) i Jake a meitat inferior / solapat
        if (!keep_jake && !fg_restored && !no_ov) {
            fg_restored = restore_fg_swap();
        }
        if (!s_in_room) {
            if (!en_restored) enemy_restore(0);
            enemy_draw(0);
            if (!elev_done) draw_movers_now();
        }
    }

    if (!keep_jake) {
        dbg_border(0x52);
        if (!fg_restored && no_ov) {
            draw_fg_atomic(jake_vis);
        } else {
            if (!fg_restored) restore_fg_swap();
            draw_fg_sprites(jake_vis);
        }
    } else {
        g_spr_y = (u8)s_mn_dsy;
        g_spr_x = (u8)s_mn_dsx;
    }

    hud_render(0, 0);

    if (s_dying_timer && g_lives_count <= 1) {
        draw_gameover_banner();
    }

    // Pre-renderitza la columna que exposarà el frame següent. Només escriu
    // RAM 2 (0xBC00/0xBD00), mai VRAM: no pot trencar el camp actual.
    pre_render_next_column();

    dbg_border(0x54);
}

void main(void) {
    cpct_memset((void*)CRT_DATA_START, 0, CRT_DATA_LEN);
    g_bank = 0xC0;
    cpct_memcpy((void*)CRT_IDATA_DST, (void*)CRT_IDATA_SRC, CRT_IDATA_LEN);
    stack_canary_init();
    cpc_install_isr();

    fdc_motor_off();
    fdc_load_file(0xC0, 0, 0, 0);

    g_map_level = 0;
    g_front_map_only = 0;
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

    cpct_scanKeyboard_f();
    if (cpct_isKeyPressed(Key_1)) g_map_level = 0;
    else if (cpct_isKeyPressed(Key_2)) g_map_level = 1;
    else if (cpct_isKeyPressed(Key_3)) g_map_level = 2;
    else if (cpct_isKeyPressed(Key_4)) g_map_level = 3;
    else if (cpct_isKeyPressed(Key_5)) g_map_level = 4;
    else if (cpct_isKeyPressed(Key_6)) g_map_level = 5;

    load_level_packages();

    // El pak de nivell trepitja els gaps de RAM 2 on viu estat fred.
    // s_rep_n viu a 0x9E40: sense aquest reset, un valor vell faria
    // repintar tiles amb coordenades del nivell anterior.
    s_rep_n = 0;

    g_mus_hold = 0;
    mus_init();

    cpct_memset((void*)0xC000, 0xFF, 0x4000);
    init_tile_props();

    s_mn_sv_lives = g_lives_count; s_mn_sv_hearts = g_hearts_count; s_mn_sv_vinyls = g_vinyls_count;
    s_mn_sv_keep = g_keep_counters;
    g_keep_counters = 0;
    moving_init();
    if (s_mn_sv_keep) {
        g_lives_count = s_mn_sv_lives;
        g_hearts_count = s_mn_sv_hearts;
        g_vinyls_count = s_mn_sv_vinyls;
    }
    enemy_init();
    hud_init();
    repaint_screen();
    draw_movers_now();
    cpc_wait_vsync_start();
    crtc_set_display_start((u16)(0x3000 + g_vram_start));
    while (g_irq_phase != 5) {}
    g_split_en = 1;

    s_vx = 0; s_vy = 0;
    s_on_ground = 1; g_face = 0;
    s_jump_prev = 0; s_climb_prev = 0;
    s_carry_kind = 0; s_grab_prev = 0;
    s_carry_state = 0; s_carry_drawn[0] = 0;
    s_anim_idx = 0; s_anim_timer = 0;
    s_dazed_timer = 0;
    s_dying_timer = 0;
    s_invuln_timer = 0;
    s_have_drawn = 0;
    s_hflip_cur = 0xFF;
    sprite_balloon_init();
    cpc_wait_vsync_start();
    s_mn_last_ticks = g_ticks;

    while (1) {
        dbg_border(0x5E);
        if (!stack_canary_ok()) {
            cpct_setBorder(0x4C);
        }
        s_mn_move = 0; s_mn_move_x = 0; s_mn_move_y = 0;
        s_mn_jump = 0; s_mn_crouch = 0; s_mn_grab = 0;

        cpct_scanKeyboard_f();
#define KEY_DOWN(k) ((u8)(~cpct_keyboardStatusBuffer[(u8)(k)] & (u8)((u16)(k) >> 8)))
        if (KEY_DOWN(Key_CursorLeft) || KEY_DOWN(Key_Q) || KEY_DOWN(Joy0_Left)) {
            s_mn_move = -1; g_face = 1;
        }
        if (KEY_DOWN(Key_CursorRight) || KEY_DOWN(Key_S) || KEY_DOWN(Joy0_Right)) {
            s_mn_move = +1; g_face = 0;
        }
        if (KEY_DOWN(Key_Space) || KEY_DOWN(Key_X) || KEY_DOWN(Joy0_Fire1) || KEY_DOWN(Joy0_Fire2)) {
            s_mn_grab = 1;
        }
        if (KEY_DOWN(Key_CursorDown) || KEY_DOWN(Key_Z) || KEY_DOWN(Joy0_Down)) {
            s_mn_crouch = 1;
        }
        {
            s_mn_up_key = (u8)(KEY_DOWN(Key_CursorUp) || KEY_DOWN(Joy0_Up));
            if (s_mn_up_key && !s_mn_grab) { s_mn_jump = 1; }

            // 1:1 DOS Door Trigger: SPACE + UP (level.c:1210)
            if (s_mn_grab && s_mn_up_key && !s_up_prev && !s_climb_prev) {
                check_doors();
            }
            s_up_prev = s_mn_up_key;
        }
#undef KEY_DOWN

        if (s_dazed_timer || s_dance_timer || s_dying_timer) {
            if (s_dazed_timer) s_dazed_timer--;
            s_mn_move = 0;
            s_mn_jump = 0;
            s_mn_crouch = 0;
            s_mn_grab = 0;
            s_vx = 0;
        }

        // Acceleració horitzontal 1:1 DOS (level.c:1724-1760)
        // g_on_ice: 0=normal (MOVE_ACC), 1=gel (acc=1), 2=rampa (acc=0, només unk2F)
        {
            i16 max_spd = s_on_ground ? SPEED_MAX : SPEED_AIR;
            u8 acc = (!s_on_ground || !g_on_ice) ? MOVE_ACC : (u8)(2 - g_on_ice);
            if (s_mn_move > 0)      { s_vx = (i16)(s_vx + acc); if (s_vx >  max_spd) s_vx =  max_spd; }
            else if (s_mn_move < 0) { s_vx = (i16)(s_vx - acc); if (s_vx < -max_spd) s_vx = -max_spd; }
            else {
                if (s_vx > 0) { s_vx = (i16)(s_vx - acc); if (s_vx < 0) s_vx = 0; }
                else if (s_vx < 0) { s_vx = (i16)(s_vx + acc); if (s_vx > 0) s_vx = 0; }
            }
        }

        // 1. Lògica d'entitats i efectes de tiles al Banc 5 (ascensors, aigua, escala, objectes)
        bc_b = s_mn_jump;
        bc_c = s_mn_crouch;
        bc_d = s_mn_grab;
        dbg_border(0x40);
        moving_update();
        if (!s_in_room) {
            dbg_border(0x5E);
            enemy_update();
        } else {
            g_jake_en_near = 0;
        }

        // 1:1 DOS Col·lisió Jake <-> Enemics / Projectils / Premses (level.c:1583-1658)
        if (s_invuln_timer) {
            s_invuln_timer--;
        } else if (!s_in_room && !s_dying_timer) {
            u8 hit = 0;
            s_ps_px = (i16)(s_px8 >> 3);
            s_ps_py = (i16)(s_py8 >> 3);
            if ((g_jake_en_near & 1) && enemy_check_player_hit(s_ps_px, s_ps_py, s_mn_crouch)) {
                hit = 1;
            } else if (s_lv.level_id == 1) {
                const MovingElevator* pe = &g_mag_elevators[MAG_ELEVATOR_COUNT];
                i16 jtop = (i16)(s_ps_py + ((s_mn_crouch || s_crouch_hold || s_climb_prev == 2) ? 16 : 4));
                i16 jbot = (i16)(s_ps_py + PH);
                u8 pk;
                for (pk = s_lv.elev_count; pk; pk--, pe++) {
                    if ((u16)(pe->center_x - s_ps_px + 2) < 21 &&
                        jbot >= (i16)(pe->y - PRESS_OBJECT_H) &&
                        pe->y >= jtop) {
                        hit = 1;
                        break;
                    }
                }
            }
            if (hit) {
                if (g_hearts_count > 0) g_hearts_count--;
                s_invuln_timer = 75; // 1:1 DOS blinking_counter = 75
                if (s_carry_kind) carry_abort();
                if (g_hearts_count == 0) {
                    s_dying_timer = 64; // 1:1 DOS death dance (~1.3s a 50Hz)
                    s_dazed_timer = 0;
                    s_invuln_timer = 255;
                } else {
                    if (s_climb_prev != 2) {
                        s_dazed_timer = 20;  // 1:1 DOS special_anim = 18 (estrelletes al cap)
                    }
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
                    video_init();
                    palette_black();
                    crtc_set_display_start(0x3000);
                    load_front_bank();
                    g_map_level = 0;
                    g_front_map_only = 0;
                    break;
                }
                g_lives_count--;
                g_hearts_count = 3;
                g_vinyls_count = 0;
                restore_level_tiles();
                moving_respawn();
                enemy_init();
                if (g_checkpoint) {
                    // Punt real on es va tocar el checkpoint (terra valid).
                    s_px8 = g_chk_px8;
                    s_py8 = g_chk_py8;
                    g_cam_x4 = g_chk_cam_x4;
                    g_cam_row = g_chk_cam_row;
                } else {
                    s_px8 = (i16)(s_lv.start_px * SUB);
                    s_py8 = (i16)(s_lv.start_py * SUB);
                    g_cam_x4 = (u16)s_lv.cam0_x4;
                    g_cam_row = (u16)s_lv.cam0_row;
                }
                s_col_cache_valid = 0;
                s_vx = 0; s_vy = 0;
                s_crouch_hold = 0;
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
                s_have_drawn = 0;
                s_hflip_cur = 0xFF;
                s_rep_n = 0;
                enemy_room_exit(0, 0);
                palette_black();
                repaint_screen();
                moving_draw(0, g_cam_x4, g_cam_row);
                palette_restore();
            }
        }

        if (s_on_ground && s_ground_elevator >= 0) {
            MovingElevator* e = &g_mag_elevators[(u8)s_ground_elevator];
            s_ps_px = (i16)(s_px8 >> 3);
            if (s_ps_px + 8 >= e->center_x - ELEVATOR_HALF_W &&
                s_ps_px + 5 <= e->center_x + ELEVATOR_HALF_W) {
                i16 next_py = (i16)((s_py8 + e->delta_y * SUB) >> 3);
                s_ps_head_row = (u16)(next_py >> 4);
                s_ps_col = (u16)((s_ps_px + 5) >> 3);
                if (e->delta_y < 0 && is_ceiling_solid(s_ps_col, s_ps_head_row)) {
                    s_ground_elevator = -1;
                    s_on_ground = 0;
                } else {
                    s_py8 = (i16)(s_py8 + e->delta_y * SUB);
                }
            } else {
                s_ground_elevator = -1;
                s_on_ground = 0;
            }
        }

        // 2. Pas de física genèrica de col·lisió sòlida al motor resident
        dbg_border(0x57);
        if (s_climb_prev != 3) {
            player_physics_step(g_belt_push, s_climb_prev, s_mn_jump, (u8)(s_mn_crouch || s_crouch_hold));
        }

        // 3. Càmera i deadzone
        {
            s_ps_px = (i16)(s_px8 >> 3);
            s_ps_py = (i16)(s_py8 >> 3);
            if (!s_scrolling_locked && !s_dying_timer) {
                i16 sy = (i16)(s_ps_py - (i16)(g_cam_row * 8));
                i16 sx = (i16)(s_ps_px - (i16)(g_cam_x4 * 4));
                if (sx > DEAD_R && g_cam_x4 < (u16)(s_lv.map_w_x2 - PLAY_CHARS)) {
                    g_cam_x4++;
                    s_mn_move_x = 1;
                } else if (sx < DEAD_L && g_cam_x4 > 0) {
                    g_cam_x4--;
                    s_mn_move_x = -1;
                }
                if (sy > DEAD_B) {
                    u16 d = ((u16)(sy - DEAD_B) + 7) >> 3;
                    if (d > 2) d = 2;
                    if (g_cam_row + d > s_lv.max_cam_row) d = s_lv.max_cam_row - g_cam_row;
                    g_cam_row += d;
                    s_mn_move_y = (i8)d;
                } else if (sy < DEAD_T && g_cam_row > 0) {
                    u16 d = ((u16)(DEAD_T - sy) + 7) >> 3;
                    if (d > 2) d = 2;
                    if (d > g_cam_row) d = g_cam_row;
                    g_cam_row -= (u16)d;
                    s_mn_move_y = (i8)(-(i8)d);
                }
            }
            {
                i16 screen_x = (i16)((s_ps_px - (i16)(g_cam_x4 * 4)) >> 1);
                i16 screen_y = (i16)(s_ps_py - (i16)(g_cam_row * 8));
                if (screen_x < 0) screen_x = 0;
                if (screen_x > (80 - SPR_WB)) screen_x = (80 - SPR_WB);
                if (screen_y < 0) screen_y = 0;
                if (screen_y > (160 - PH)) screen_y = (160 - PH);
                s_mn_dsx = (u16)screen_x;
                s_mn_dsy = (u16)screen_y;
            }
        }

        s_mn_page_dx = s_mn_move_x;
        s_mn_page_dy = s_mn_move_y;
        s_mn_cur = select_player_anim(s_climb_prev, s_mn_move, s_mn_jump, (u8)(s_mn_crouch || s_crouch_hold), (i16)s_mn_dsy);

        // Pre-calcular el frame d'en Jake (inclòs H-flip) ABANS del VSYNC per no gastar temps dins el VBLANK
        {
            const u8* fr_raw = (const u8*)(u16)(PLAYER_FRAMES_BASE + ((u16)s_mn_cur << 9) - ((u16)s_mn_cur << 5));
            if (g_face != 0 && s_climb_prev != 3 && (s_dying_timer || !(s_invuln_timer & 2)) && s_hflip_cur != s_mn_cur) {
                u8 prev_b = bank_set(PLAYER_FRAMES_BANK);
                sprite_hflip(fr_raw, (u8*)0x7840);
                bank_restore(prev_b);
                s_hflip_cur = s_mn_cur;
            }
        }

        // Offset MA del frame ANTERIOR per restaurar els sprites exactament on es van dibuixar
        g_vram_start = camera_ma((u16)(g_cam_x4 - s_mn_page_dx),
                                 (u16)(g_cam_row - s_mn_page_dy));

        dbg_border(0x54);
        while ((u8)(g_ticks - s_mn_last_ticks) < 10) {}
        while (g_irq_phase != 3) {}
        s_mn_last_ticks = g_ticks;
        render_frame();

        // 1:1 DOS (level.c): 50 frames de celebracio i despres mapa/nivell
        // seguent; al darrer nivell es torna al primer.
        if (g_level_complete) {
            if (s_complete_wait < 50) {
                s_complete_wait++;
            } else {
                s_complete_wait = 0;
                g_level_complete = 0;
                if (g_map_level < 5) {
                    g_map_level++;
                    g_front_map_only = 1;
                } else {
                    g_map_level = 0;
                    g_front_map_only = 0;
                }
                mus_stop();
                g_mus_hold = 1;
                palette_black();
                video_init();
                palette_black();
                crtc_set_display_start(0x3000);
                load_front_bank();
                g_keep_counters = 1;   // el nivell seguent hereta comptadors
                break;
            }
        }
    }
    }
}



