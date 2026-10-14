// ============================================================
// enemy.c - Walkers del nivell 1 (kinds DOS 8/15/19 -> op1), BANC C6
// ------------------------------------------------------------
// S'enllaça a 0x5200 (darrere els frames a 0x4000) amb taula de
// salts fixa (engine/enemy_table.s): el resident hi crida via
// call_banked(0xC6, slot). El banc es C6 (no C2/C3): OUT(0x7F00,0xC2)
// penja la maquina i C3 reboota (vist 10/26); la imatge hi arriba
// per LDIR central, no pel motor. Les consultes de mapa son helpers
// CENTRALS (enemy_wall_q/enemy_floor_q a moving.c): el codi banked
// no pot niuar de banc (CP-2.2).
// OJO 10/26: sense crt0 al banc, els inicialitzadors statics NO
// s'instal.len (el blob es packed: _INITIALIZED no cau a _DATA).
// Tot l'estat mutable es ZERO (sense init) i en2_init (slot 3, 1
// crida post-carrega des del resident) omple spawn+owners.
// Patrulla horitzontal (6 px/frame = DOS 5 px/f @30fps a 25 Hz) +
// gravetat (mirall d'en Jake) + gir en paret + snap. Fons
// save/restore en POOL de 6 slots (3 per pagina): mai hi ha mes
// de 3 walkers visibles (mapa 1024 px, vista 160); si s'exhaureix
// es salta el draw (segur). Sense tret ni colisio (slice 2).
// ============================================================
#include "cpctelera.h"
#include "moving.h"
#include "sprite.h"
#include "enemy.h"
#include "level_pkg.h"

#define ENEMY_VX 48 // 6 px/frame @SUB8 (DOS 40>>3=5 px/f @30fps -> 150 px/s)
#define ENEMY_SUB 8
#define ENEMY_GRAV 24
#define ENEMY_VYMAX (15 * 8)

#define BG_SLOTS 6
#define BG_PAGESLOTS 3

typedef struct {
    i16 x;          // esquerra, px mon Mode 0
    i16 y8;         // cap, subpixels (SUB8)
    i8 dir;         // +1 dreta, -1 esquerra (DOS moving_direction ^ 1)
    i16 vy;         // subpixels/frame
    u8 on_ground;
    u8 tick;
    u8 kind;        // DOS 8/15/19
    i8 slot[2];     // slot de fons per pagina (-1 = no dibuixat)
    u8 drawn_start_byte[2];
    u8 drawn_byte_count[2];
    u8 drawn_start_row[2];
    u8 drawn_row_count[2];
    i16 drawn_x[2];
    i16 drawn_y[2];
    i16 sx;         // spawn centre x (DOS level_xpos/2): bbox activacio
    i16 sy;         // spawn peus y (DOS level_ypos): bbox activacio
} Enemy;

// LUT mirror Mode 0 (256 B a _DATA: engine/enemy_flip_lut.s, primer del
// link -> 0x6500 alineat; HI 0x65 via _g_flip_lut_hi). L'omple en2_init.
extern u8 s_flip_lut[256];

// Estat a ZERO (sense init: veure capcalera) i en2_init (slot 3)
// omple l'spawn a runtime: left=dos_x/2, y8=(dos_y-32)*8; dir=1
// (dreta DOS); slot {-1,-1} lliure; owners -1.
static Enemy s_enemies[ENEMY_N];
static u8 s_bg_mem[BG_SLOTS][ENEMY_FRAME_SIZE];
static i8 s_bg_owner[BG_SLOTS];

// Taula d'spawn a CODE (5 B/fila: x, top=y8>>3, kind; dir sempre 1).
// left=dos_x/2-8 (dos_xpos es el CENTRE: el draw centra l'sprite),
// top=dos_y-32 (dos_ypos son els peus). Slots DOS L1 1,2,5,11,12,
// 24,25,26,27,28 (staticres.c).
static const u8 s_spawn[ENEMY_N * 5] = {
    200, 1,  64, 4, 15,   // s1 (456, top 1088, k15)
    112, 2,  64, 4, 15,   // s2 (624, top 1088, k15)
     80, 2, 192, 3, 15,   // s5 (592, top 960, k15)
    112, 1, 240, 1,  8,   // s11 (368, top 496, k8)
     64, 2, 240, 1,  8,   // s12 (544, top 496, k8)
    168, 1, 224, 1,  8,   // s24 (424, top 480, k8)
    184, 1, 224, 1,  8,   // s25 (440, top 480, k8)
    232, 0,  64, 0, 19,   // s26 (232, top 64, k19)
      0, 2,  48, 0, 19,   // s27 (512, top 48, k19)
     40, 3,  64, 0, 19,   // s28 (808, top 64, k19)
};

void en2_init(void) {
    u8 i;
    u16 k;
    // LUT mirror (mateixa formula que sprite_hflip_init_lut).
    for (k = 0; k < 256; k++)
        s_flip_lut[k] = (u8)(((k & 0xAA) >> 1) | ((k & 0x55) << 1));
    for (i = 0; i < ENEMY_N; i++) {
        Enemy* e = &s_enemies[i];
        const u8* s = s_spawn + (u16)i * 5;
        e->x = (i16)((u16)s[0] + ((u16)s[1] << 8));
        e->y8 = (i16)(((u16)s[2] + ((u16)s[3] << 8)) << 3);
        e->sx = (i16)(e->x + 8);            // centre (DOS level_xpos/2)
        e->sy = (i16)(((u16)s[2] + ((u16)s[3] << 8)) + 32); // peus
        e->dir = 1;
        e->vy = 0;
        e->on_ground = 0;
        e->tick = 0;
        e->kind = s[4];
        e->slot[0] = -1;
        e->slot[1] = -1;
        e->drawn_row_count[0] = 0;
        e->drawn_row_count[1] = 0;
    }
    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
}

// Cela base per kind (walk): k8 {0,1}, k15 {2,3}, k19 {7,8} (SQV 2/14,
// 3/4, 18/19).
static u8 en2_cell_base(u8 kind) {
    if (kind == 8) return 0;
    if (kind == 19) return 7;
    return 2;
}

void en2_update(void) {
    u8 i;
    // Finestra camera (mateixa que en2_draw): el bbox d'activacio DOS
    // la necessita (level.c: bounding_box).
    i16 view_x = (i16)(g_cam_x4 << 2);
    i16 view_y = (i16)(g_cam_row << 3);
    for (i = 0; i < ENEMY_N; i++) {
        Enemy* e = &s_enemies[i];
        i16 y;
        i16 nx;
        i16 prev_feet, feet;
        u16 c1, c2;
        // Bbox DOS (origens DOS/2 en x, igual en y; spawn, no posicio):
        // x [xo-140,xo+320+140], y [yo-100,yo+160+190]. Fora: congelat
        // (visible=0: ni IA, ni gravetat, ni anim).
        if (e->sx < (i16)(view_x - 70) || e->sx > (i16)(view_x + 230) ||
            e->sy < (i16)(view_y - 100) || e->sy > (i16)(view_y + 350))
            continue;
        y = (i16)(e->y8 >> 3);
        // X: patrulla + gir en paret (DOS fixup: sonda a centre+-13 px =
        // L+14/L+1, files peus i peus-1; bits 1=dreta, 2=esquerra).
        nx = (i16)(e->x + (i16)(e->dir * 6));
        if (nx < 0) { nx = 0; e->dir = 1; }
        if (nx > (i16)(LEVEL_W_PX - ENEMY_W)) { nx = (i16)(LEVEL_W_PX - ENEMY_W); e->dir = -1; }
        {
            u16 acol = (u16)((e->dir > 0 ? (nx + 14) : (nx + 1)) >> 3);
            u8 fl = (u8)(tile_flags(acol, (u16)((y + 8) >> 4)) |
                         tile_flags(acol, (u16)((y + 24) >> 4)));
            if (fl & (e->dir > 0 ? 1 : 2)) {
                e->dir = (i8)-e->dir;
            } else {
                e->x = nx;
            }
        }
        // Y: gravetat + snap (mateix que en Jake, alcada 32)
        if (!e->on_ground) {
            e->vy = (i16)(e->vy + ENEMY_GRAV);
            if (e->vy > ENEMY_VYMAX) e->vy = ENEMY_VYMAX;
        } else {
            e->vy = 0;
        }
        prev_feet = (i16)(y + ENEMY_HT);
        e->y8 = (i16)(e->y8 + e->vy);
        y = (i16)(e->y8 >> 3);
        feet = (i16)(y + ENEMY_HT);
        c1 = (u16)((e->x + 3) >> 3);
        c2 = (u16)((e->x + 12) >> 3);
        if (e->vy >= 0) {
            u16 trow = (u16)(feet >> 4);
            if (trow < LEVEL_MAP_H) {
                i16 surf = (i16)(trow << 4);
                if (is_floor_solid(c1, trow, e->vy, 0) || is_floor_solid(c2, trow, e->vy, 0)) {
                    if (prev_feet <= (surf + 8) && feet >= surf) {
                        e->y8 = (i16)((surf - ENEMY_HT) * ENEMY_SUB);
                        e->vy = 0;
                        e->on_ground = 1;
                    } else {
                        e->on_ground = 0;
                    }
                } else {
                    e->on_ground = 0;
                }
            }
        }
        e->tick++;
    }
}

// Reserva slot de fons per (enemic, pagina): existent o lliure; -1 si ple.
static i8 en2_slot(i8 idx, u8 page) {
    u8 k;
    i8 s = s_enemies[(u8)idx].slot[page];
    if (s >= 0) return s;
    for (k = 0; k < BG_PAGESLOTS; k++) {
        s = (i8)(page * BG_PAGESLOTS + k);
        if (s_bg_owner[(u8)s] < 0) {
            s_bg_owner[(u8)s] = idx;
            s_enemies[(u8)idx].slot[page] = s;
            return s;
        }
    }
    return -1;
}

void en2_restore(void) {
    u8 page = (u8)bc_a;
    u8 k, y;
    if (page > 1) return;
    for (k = 0; k < BG_PAGESLOTS; k++) {
        i8 s = (i8)(page * BG_PAGESLOTS + k);
        i8 idx = s_bg_owner[(u8)s];
        Enemy* e;
        if (idx < 0) continue;
        e = &s_enemies[(u8)idx];
        for (y = 0; y < e->drawn_row_count[page]; y++) {
            u8 sprite_row = (u8)(e->drawn_start_row[page] + y);
            u16 bg_off = (u16)sprite_row * ENEMY_WB + e->drawn_start_byte[page];
            g_moving_dst = (u16)ring_address(page,
                (i16)(e->drawn_x[page] + e->drawn_start_byte[page] * 2),
                (i16)(e->drawn_y[page] + sprite_row));
            g_moving_background = (u16)(s_bg_mem[(u8)s] + bg_off);
            g_moving_span = e->drawn_byte_count[page];
            moving_restore_span();
        }
        e->slot[page] = -1;
        s_bg_owner[(u8)s] = -1;
    }
}

void en2_draw(void) {
    u8 page = (u8)bc_a;
    u8 i, y;
    // Camera directa (globals residents via EQU): estalvia bc_b/bc_c.
    i16 view_x = (i16)(g_cam_x4 << 2);
    i16 view_y = (i16)(g_cam_row << 3);
    if (page > 1) return;
    for (i = 0; i < ENEMY_N; i++) {
        Enemy* e = &s_enemies[i];
        i16 world_x, world_y, clip_x0, clip_x1, clip_y0, clip_y1;
        u8 start_byte, byte_count, start_row, row_count;
        const u8* frame;
        i8 s;
        if (e->slot[page] >= 0) continue; // ja dibuixat (no cal repintar)
        world_x = e->x;
        world_y = (i16)(e->y8 >> 3);
        clip_x0 = world_x > view_x ? world_x : view_x;
        clip_x1 = world_x + ENEMY_W < view_x + 160 ?
                  (i16)(world_x + ENEMY_W) : (i16)(view_x + 160);
        clip_y0 = world_y > view_y ? world_y : view_y;
        clip_y1 = world_y + ENEMY_HT < view_y + 160 ?
                  (i16)(world_y + ENEMY_HT) : (i16)(view_y + 160);
        if (clip_x0 >= clip_x1 || clip_y0 >= clip_y1) continue;
        s = en2_slot((i8)i, page);
        if (s < 0) continue; // pool ple: segur (l'enemic no es veu 1 frame)
        start_byte = (u8)((clip_x0 - world_x) >> 1);
        byte_count = (u8)((clip_x1 - clip_x0) >> 1);
        start_row = (u8)(clip_y0 - world_y);
        row_count = (u8)(clip_y1 - clip_y0);
        frame = ENEMY_FRAMES_BASE +
                (u16)(en2_cell_base(e->kind) + ((e->tick >> 3) & 1)) * ENEMY_FRAME_SIZE;
        // DOS: facing_left -> xflip (mateix frame mirroritzat). Les celes
        // miren a la dreta; dir<0 dibuixa amb el blit amb flip (LUT C6).
        if (e->dir < 0) {
            u16 rev = (u16)((u16)start_byte + (u16)byte_count - 1u) << 1;
            for (y = 0; y < row_count; y++) {
                u8 sprite_row = (u8)(start_row + y);
                u16 bg_off = (u16)sprite_row * ENEMY_WB + start_byte;
                g_moving_dst = (u16)ring_address(page, clip_x0, (i16)(clip_y0 + y));
                g_moving_background = (u16)(s_bg_mem[(u8)s] + bg_off);
                g_moving_sprite = (u16)(frame + (u16)((u16)sprite_row * 16u + rev));
                g_moving_span = byte_count;
                moving_blit_span_hflip();
            }
        } else {
        for (y = 0; y < row_count; y++) {
            u8 sprite_row = (u8)(start_row + y);
            u16 bg_off = (u16)sprite_row * ENEMY_WB + start_byte;
            u16 frame_off = bg_off << 1;
            g_moving_dst = (u16)ring_address(page, clip_x0, (i16)(clip_y0 + y));
            g_moving_background = (u16)(s_bg_mem[(u8)s] + bg_off);
            g_moving_sprite = (u16)(frame + frame_off);
            g_moving_span = byte_count;
            moving_blit_span();
        }
        }
        e->drawn_start_byte[page] = start_byte;
        e->drawn_byte_count[page] = byte_count;
        e->drawn_start_row[page] = start_row;
        e->drawn_row_count[page] = row_count;
        e->drawn_x[page] = world_x;
        e->drawn_y[page] = world_y;
    }
}
