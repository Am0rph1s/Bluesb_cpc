// ============================================================
// enemy.c - Walkers del nivell 1 (kinds DOS 8/15/19 -> op1), BANC C6
// ------------------------------------------------------------
// S'enllaça a 0x5C00 (darrere els frames a 0x4000) amb taula de
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
// es salta el draw (segur).
// Subsistema de projectils integrat (ou, bala, plat) amb buffer propi.
// Flip dinàmic sota demanda en ASM (estalvia 2.560 B de RAM).
// ============================================================
#include "cpctelera.h"
#include "moving.h"
#include "enemy.h"
#define LEVEL_PKG_DEFS_ONLY
#include "level_pkg.h"

#define ENEMY_VX 24 // 3 px/frame @SUB8 (DOS 40>>3=5 DOSpx/f @30fps = 150 px/s; 3*2*25 = 150)
#define ENEMY_SUB 8
#define ENEMY_GRAV 24
#define ENEMY_VYMAX (15 * 8)

#define BG_SLOTS 6
#define BG_PAGESLOTS 3

typedef struct {
    i16 x;          // esquerra, px mon Mode 0
    i16 y8;         // cap, subpixels (SUB8)
    i8 dir;         // +1 dreta, -1 esquerra
    i16 vy;         // subpixels/frame
    u8 on_ground;
    u8 tick;
    i8 slot[2];     // slot de fons per pagina (-1 = no dibuixat)
    u8 drawn_byte_count[2];
    u8 drawn_row_count[2];
    u16 drawn_dst[2];
} Enemy;

typedef struct {
    i16 x;
    i16 y8;
    i16 sy;
    u8 kind;
    u8 vx;
    u8 base_cell;
} Spawn;

typedef struct {
    i16 x;
    i16 y8;
    i8 dir;
    i16 vx;
    i16 vy;
    u8 kind;        // 0=inactiu, 4=bala, 9=plat, 10=ou
    u8 ht;          // alçada (bala=6, plat=11, ou=13)
    u8 row_offset;  // a cela 13 (bala=13, plat=19, ou=0)
    u8 cooldown;
    u8 drawn_byte_count[2];
    u8 drawn_row_count[2];
    u16 drawn_dst[2];
} Projectile;

// Estat a ZERO (sense init: veure capcalera) i en2_init (slot 3)
// omple l'spawn a runtime.
static Enemy s_enemies[ENEMY_N];
static Projectile s_proj;
static u8 s_proj_bg[2][64];

// Pool de fons a BANC C6 0x7A00 (6x256 = 1536 B, 0x7A00..0x7FFF).
#define BG_BASE ((u16)0x7A00)
#define BG_SLOT(s) (BG_BASE + (((u16)((u8)(s))) << 8))
static i8 s_bg_owner[BG_SLOTS];

// Buffer dinàmic de flip sota demanda per a enemics encarats a l'esquerra:
static u8 s_flip_buffer[ENEMY_FRAME_SIZE];
static u8 s_flipped_cell;

extern u8 tile_type(u16 col, u16 row);
extern u8 tile_flags(u16 col, u16 row);
extern u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch);

// Rutines ràpides en ASM per flipejar la cela a s_flip_buffer (engine/enemy_table.s):
extern void en2_init_lut(void);
extern void en2_flip_cell(const u8* src, u8* dst);

// Taula d'spawn precalculada (20 slots L1):
// 3 iaies, 5 policies, 2 peixos, 3 ocells, 2 grangers, 1 cambrera, 4 rockers.
static const Spawn s_spawn[ENEMY_N] = {
    // 3 Iaies (kind 15):
    { 464, 1104 << 3, 1136, 15, 36,  1 }, //  0: Iaia 1 (PB Store)
    { 632, 1104 << 3, 1136, 15, 36,  1 }, //  1: Iaia 2 (PB Bar)
    { 600,  976 << 3, 1008, 15, 36,  1 }, //  2: Iaia 3 (1r pis botiga)

    // 5 Policies (kind 4):
    { 288, 1104 << 3, 1136,  4, 24,  3 }, //  3: Policia 1 (PB esquerra prop escala)
    { 752, 1104 << 3, 1136,  4, 24,  3 }, //  4: Policia 2 (PB dreta botigues)
    { 280,  976 << 3, 1008,  4, 24,  3 }, //  5: Policia 3 (1r pis sota escala)
    { 776,  512 << 3,  544,  4, 24,  3 }, //  6: Policia 4 (2n pis replà entre ascensors)
    { 696,  336 << 3,  368,  4, 24,  3 }, //  7: Policia 5 (3r pis replà superior ascensors)

    // 2 Peixos (kind 8):
    { 416,  512 << 3,  544,  8, 16,  0 }, //  8: Peix 1 (Peixera 1)
    { 584,  512 << 3,  544,  8, 16,  0 }, //  9: Peix 2 (Peixera 2)

    // 3 Ocells (kind 19):
    { 240,   48 << 3,   80, 19, 32,  5 }, // 10: Ocell 1 (Núvols esquerra)
    { 520,   48 << 3,   80, 19, 32,  5 }, // 11: Ocell 2 (Núvols centre)
    { 816,   48 << 3,   80, 19, 32,  5 }, // 12: Ocell 3 (Núvols dreta)

    // 2 Grangers (kind 18):
    { 360,  336 << 3,  368, 18, 24,  7 }, // 13: Granger 1 (escala vinils esq)
    { 504,  336 << 3,  368, 18, 24,  7 }, // 14: Granger 2 (escala vinils dreta)

    // 1 Cambrera (kind 17):
    {  80,  624 << 3,  656, 17, 20,  9 }, // 15: Cambrera (Bar/Restaurant 1r pis)

    // 4 Rockers (kind 20):
    { 440,  976 << 3, 1008, 20, 24, 11 }, // 16: Rocker 1 (1r pis davant botiga)
    { 632,  784 << 3,  816, 20, 24, 11 }, // 17: Rocker 2 (2n pis dreta)
    {  80,  480 << 3,  512, 20, 24, 11 }, // 18: Rocker 3 (prop Bar/Restaurant)
    { 592,  736 << 3,  768, 20, 24, 11 }, // 19: Rocker 4 (2n pis)
};

static void en2_spawn_proj(u8 kind, u8 ht, u8 row_off, i16 x, i16 y, i16 vx, i16 vy, u8 cd) {
    s_proj.kind = kind;
    s_proj.ht = ht;
    s_proj.row_offset = row_off;
    s_proj.x = x;
    s_proj.y8 = (i16)(y << 3);
    s_proj.vx = vx;
    s_proj.vy = vy;
    s_proj.cooldown = cd;
}

void en2_init(void) {
    u8 i;
    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    en2_init_lut();
    s_flipped_cell = 0xFF;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        e->x = sp->x;
        e->y8 = sp->y8;
        e->dir = 1;
        e->vy = 0;
        e->on_ground = (sp->kind == 8 || sp->kind == 19) ? 1 : 0;
        e->tick = 0;
        e->slot[0] = -1;
        e->slot[1] = -1;
        e->drawn_row_count[0] = 0;
        e->drawn_row_count[1] = 0;
    }
    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
    s_proj.kind = 0;
    s_proj.cooldown = 0;
    s_proj.drawn_row_count[0] = 0;
    s_proj.drawn_row_count[1] = 0;
}

void en2_update(void) {
    u8 i;
    i16 view_x = (i16)(g_cam_x4 << 2);
    i16 view_y = (i16)(g_cam_row << 3);
    i16 jake_x = (i16)(s_px8 >> 3);
    i16 jake_y = (i16)(s_py8 >> 3);

    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        i16 y;
        i16 nx, dx;

        if (sp->x < (i16)(view_x - 70) || sp->x > (i16)(view_x + 230) ||
            sp->sy < (i16)(view_y - 100) || sp->sy > (i16)(view_y + 350))
            continue;

        y = (i16)(e->y8 >> 3);

        dx = (i16)(sp->vx >> 3);
        if (e->dir < 0) dx = (i16)-dx;
        nx = (i16)(e->x + dx);

        if (sp->kind == 8 || sp->kind == 19) {
            i16 min_x, max_x;
            if (sp->kind == 8) {
                min_x = (sp->x < 500) ? 388 : 564;
                max_x = (i16)(min_x + 48);
            } else {
                min_x = (i16)(sp->x - 96);
                max_x = (i16)(sp->x + 96);
            }
            if (nx < min_x) { e->x = min_x; e->dir = 1; }
            else if (nx > max_x) { e->x = max_x; e->dir = -1; }
            else { e->x = nx; }
            e->on_ground = 1;
            e->vy = 0;
        } else {
            // WALKERS (Iaia 15, Policia 4, Granger 18, Cambrera 17, Rocker 20):
            if (nx < 0) { nx = 0; e->dir = 1; }
            if (nx > (i16)(LEVEL_W_PX - ENEMY_W)) { nx = (i16)(LEVEL_W_PX - ENEMY_W); e->dir = -1; }
            {
                u16 frow = (u16)(((i16)(y + ENEMY_HT)) >> 4);
                u16 brow = (u16)(((i16)(y + ENEMY_HT - 1)) >> 4);
                u16 pcol = (u16)(((e->x >> 3) + (e->dir > 0 ? 2 : -2)));
                u16 acol = (u16)(((nx + (e->dir > 0 ? 12 : 2)) >> 3));
                u8 bit = (u8)(e->dir > 0 ? 1 : 2);
                if (tile_type(pcol, brow) == 1 || tile_type(pcol, frow) == 1) {
                    e->dir = (i8)-e->dir;   // trigger Titus DOS o fi de terra
                } else if ((tile_flags(acol, brow) & bit) || (brow > 0 && (tile_flags(acol, (u16)(brow - 1)) & bit))) {
                    e->dir = (i8)-e->dir;   // paret davant
                } else {
                    e->x = nx;
                }
            }
            // Y: gravetat + snap (mateix que en Jake, alcada 32)
            if (!e->on_ground) {
                i16 prev_feet = (i16)(y + ENEMY_HT);
                i16 feet;
                u16 c1, c2, trow;
                e->vy = (i16)(e->vy + ENEMY_GRAV);
                if (e->vy > ENEMY_VYMAX) e->vy = ENEMY_VYMAX;
                e->y8 = (i16)(e->y8 + e->vy);
                y = (i16)(e->y8 >> 3);
                feet = (i16)(y + ENEMY_HT);
                c1 = (u16)((e->x + 3) >> 3);
                c2 = (u16)((e->x + 12) >> 3);
                trow = (u16)(feet >> 4);
                if (trow < LEVEL_MAP_H) {
                    i16 surf = (i16)(trow << 4);
                    if ((is_floor_solid(c1, trow, 0, 0) || is_floor_solid(c2, trow, 0, 0)) &&
                        prev_feet <= (surf + 8) && feet >= surf) {
                        e->y8 = (i16)((surf - ENEMY_HT) << 3);
                        e->vy = 0;
                        e->on_ground = 1;
                    }
                }
            } else if ((e->tick & 3) == 0) {
                u16 c1 = (u16)((e->x + 3) >> 3);
                u16 c2 = (u16)((e->x + 12) >> 3);
                u16 trow = (u16)((y + ENEMY_HT) >> 4);
                if (trow < LEVEL_MAP_H && !is_floor_solid(c1, trow, 0, 0) && !is_floor_solid(c2, trow, 0, 0)) {
                    e->on_ground = 0;
                }
            }
        }

        // Triggers de projectil (ou, bala, plat):
        if (!s_proj.kind && !s_proj.cooldown) {
            if (sp->kind == 19) {
                // Ocell: deixa caure un ou si en Jake passa per sota
                if (jake_y > y && (jake_y - y) < 130) {
                    i16 diff = jake_x - e->x;
                    if (diff > -16 && diff < 16) {
                        en2_spawn_proj(10, 13, 0, (i16)(e->x + 4), (i16)(y + 16), 0, 16, 40);
                    }
                }
            } else if (sp->kind == 4 || sp->kind == 17) {
                // Policia / Cambrera: dispara bala o llança plat si en Jake està al davant
                i16 dy = jake_y - y;
                if (dy >= -16 && dy <= 24) {
                    i16 dx = jake_x - e->x;
                    if ((e->dir > 0 && dx > 0 && dx < 75) ||
                        (e->dir < 0 && dx < 0 && dx > -75)) {
                        i16 sx = (e->dir > 0) ? (i16)(e->x + 14) : (i16)(e->x - 6);
                        if (sp->kind == 4) {
                            en2_spawn_proj(4, 6, 13, sx, (i16)(y + 14), (e->dir > 0) ? 64 : -64, 0, 50);
                        } else {
                            en2_spawn_proj(9, 11, 19, sx, (i16)(y + 12), (e->dir > 0) ? 40 : -40, 0, 50);
                        }
                    }
                }
            }
        }

        e->tick++;
    }

    // Actualització del projectil actiu:
    if (s_proj.cooldown) s_proj.cooldown--;
    if (s_proj.kind) {
        s_proj.x = (i16)(s_proj.x + (s_proj.vx >> 3));
        s_proj.y8 = (i16)(s_proj.y8 + s_proj.vy);
        if (s_proj.kind == 10) {
            s_proj.vy = (i16)(s_proj.vy + 8);
            if (s_proj.vy > 64) s_proj.vy = 64;
        }
        {
            i16 py = (i16)(s_proj.y8 >> 3);
            if (s_proj.x < (i16)(view_x - 16) || s_proj.x > (i16)(view_x + 176) ||
                py < (i16)(view_y - 16) || py > (i16)(view_y + 160)) {
                s_proj.kind = 0;
            } else if (s_proj.kind == 10) {
                u16 trow = (u16)((py + s_proj.ht) >> 4);
                u16 tcol = (u16)((s_proj.x + 4) >> 3);
                if (trow < LEVEL_MAP_H && is_floor_solid(tcol, trow, 0, 0)) {
                    s_proj.kind = 0;
                }
            }
        }
    }
}

// Reserva slot de fons per (enemic, pagina): existent o lliure; -1 si ple.
static i8 en2_slot(i8 idx, u8 page) {
    u8 k;
    i8 s = s_enemies[(u8)idx].slot[page];
    if (s >= 0) return s;
    for (k = 0; k < BG_PAGESLOTS; k++) {
        s = (i8)((page ? 3 : 0) + k);
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
    u8 k;
    if (page > 1) return;

    // 1. Restaura projectil:
    if (s_proj.drawn_row_count[page]) {
        g_moving_dst = s_proj.drawn_dst[page];
        g_moving_background = (u16)(&s_proj_bg[page][0]);
        g_moving_span = s_proj.drawn_byte_count[page];
        g_moving_rows = s_proj.drawn_row_count[page];
        moving_restore_box();
        s_proj.drawn_row_count[page] = 0;
    }

    // 2. Restaura walkers LIFO:
    for (k = BG_PAGESLOTS; k > 0; k--) {
        i8 s = (i8)((page ? 3 : 0) + (k - 1));
        i8 idx = s_bg_owner[(u8)s];
        Enemy* e;
        if (idx < 0) continue;
        e = &s_enemies[(u8)idx];
        g_moving_dst = e->drawn_dst[page];
        g_moving_background = BG_SLOT(s);
        g_moving_span = e->drawn_byte_count[page];
        g_moving_rows = e->drawn_row_count[page];
        moving_restore_box();
        e->slot[page] = -1;
        s_bg_owner[(u8)s] = -1;
    }
}

void en2_draw(void) {
    u8 page = (u8)bc_a;
    u8 i;
    i16 view_x = (i16)(g_cam_x4 << 2);
    i16 view_y = (i16)(g_cam_row << 3);
    if (page > 1) return;

    // 1. Dibuixa walkers:
    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        i16 world_x, world_y, clip_x0, clip_x1, clip_y0, clip_y1;
        u8 start_byte, byte_count, start_row, row_count;
        const u8* frame;
        i8 s;
        if (e->slot[page] >= 0) continue; // ja dibuixat
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
        if (s < 0) continue; // pool ple: segur
        start_byte = (u8)((clip_x0 - world_x) >> 1);
        byte_count = (u8)((clip_x1 - clip_x0) >> 1);
        start_row = (u8)(clip_y0 - world_y);
        row_count = (u8)(clip_y1 - clip_y0);

        // Selecció de cela i flip dinàmic amb cache de cela:
        {
            u8 step = (sp->kind == 8) ? 0 : (u8)((e->tick >> 3) & 1);
            u8 cell = (u8)(sp->base_cell + step);
            const u8* src = ENEMY_FRAMES_BASE + ((u16)cell << 9);
            if (e->dir < 0) {
                if (s_flipped_cell != cell) {
                    en2_flip_cell(src, s_flip_buffer);
                    s_flipped_cell = cell;
                }
                frame = s_flip_buffer;
            } else {
                frame = src;
            }
        }

        g_moving_dst = (u16)ring_address(page, clip_x0, clip_y0);
        e->drawn_dst[page] = g_moving_dst;
        g_moving_background = BG_SLOT(s);
        g_moving_sprite = (u16)(frame + ((u16)start_row << 4) + (start_byte << 1));
        g_moving_span = byte_count;
        g_moving_rows = row_count;
        g_moving_spr_skip = (u8)(16 - (byte_count << 1));
        moving_blit_box();

        e->drawn_byte_count[page] = byte_count;
        e->drawn_row_count[page] = row_count;
    }

    // 2. Dibuixa projectil si està actiu:
    if (s_proj.kind && !s_proj.drawn_row_count[page]) {
        i16 world_x = s_proj.x;
        i16 world_y = (i16)(s_proj.y8 >> 3);
        i16 clip_x0 = world_x > view_x ? world_x : view_x;
        i16 clip_x1 = world_x + 8 < view_x + 160 ? (i16)(world_x + 8) : (i16)(view_x + 160);
        i16 clip_y0 = world_y > view_y ? world_y : view_y;
        i16 clip_y1 = world_y + s_proj.ht < view_y + 160 ? (i16)(world_y + s_proj.ht) : (i16)(view_y + 160);
        if (clip_x0 < clip_x1 && clip_y0 < clip_y1) {
            u8 start_byte = (u8)((clip_x0 - world_x) >> 1);
            u8 byte_count = (u8)((clip_x1 - clip_x0) >> 1);
            u8 start_row = (u8)(clip_y0 - world_y);
            u8 row_count = (u8)(clip_y1 - clip_y0);
            // Cela 13: base + offset files projectil + 4 (centrat horitzontal 8 px Mode 0)
            const u8* frame = ENEMY_FRAMES_BASE + (13 << 9) + (((u16)s_proj.row_offset + start_row) << 4) + 4 + (start_byte << 1);

            g_moving_dst = (u16)ring_address(page, clip_x0, clip_y0);
            s_proj.drawn_dst[page] = g_moving_dst;
            g_moving_background = (u16)(&s_proj_bg[page][0]);
            g_moving_sprite = (u16)frame;
            g_moving_span = byte_count;
            g_moving_rows = row_count;
            g_moving_spr_skip = (u8)(16 - (byte_count << 1));
            moving_blit_box();

            s_proj.drawn_byte_count[page] = byte_count;
            s_proj.drawn_row_count[page] = row_count;
        }
    }
}
