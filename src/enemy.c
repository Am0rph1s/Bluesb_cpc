// ============================================================
// enemy.c - Walkers del nivell 1 (kinds DOS 8/15/19 -> op1), BANC C6
// ------------------------------------------------------------
// S'enllaÃ§a a 0x5A00 (darrere els frames a 0x4000) amb taula de
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
// Flip dinÃ mic sota demanda en ASM (estalvia 2.560 B de RAM).
// ============================================================
#include "cpctelera.h"
#include "moving.h"
#include "enemy.h"
#include "level_params.h"
#include "bank.h"

extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);

#define ENEMY_VX 24 // 3 px/frame @SUB8 (DOS 40>>3=5 DOSpx/f @30fps = 150 px/s; 3*2*25 = 150)
#define ENEMY_SUB 8
#define ENEMY_GRAV 24
#define ENEMY_VYMAX (15 * 8)

#define BG_SLOTS 3
#define BG_PAGESLOTS 3

typedef struct {
    i16 x;          // esquerra, px mon Mode 0
    i16 y8;         // cap, subpixels (SUB8)
    i8 dir;         // +1 dreta, -1 esquerra
    i16 vy;         // subpixels/frame
    u8 on_ground;
    u8 tick;
    u8 shoot_timer; // aturat per disparar (1:1 DOS)
    u8 dead;        // 0=viu, 1=tocat per caixa (cau lliure), 2=fora de pantalla
    // Slot de fons per pagina, empaquetat en 1 byte per encabir ENEMY_N=27
    // als 512 B de _DATA del C6: nibble baix = pagina 0, alt = pagina 1;
    // 0xF = no dibuixat (abans slot[2] de -1).
    u8 slot_bits;
} Enemy;

typedef struct {
    i16 x;
    i16 y8;
    u8 kind;
    u8 vx;
    u8 base_cell;
    u8 aim_cell;    // pose de tret (kind 4)
    u8 throw_cell;  // pose de llançament (kind 17)
} Spawn;

typedef struct {
    i16 x;
    i16 y8;
    i8 dir;         // REUTILITZAT: offset horitzontal dins la fila (0 o 4)
    i16 vx;
    i16 vy;
    u8 kind;        // 0=inactiu, 4=bala, 9=plat, 10=ou, 26=coet L3, 27=bola L3
    u8 ht;          // alÃ§ada (bala=6, plat=11, ou=13)
    u8 row_offset;  // a la cela (bala=13, plat=19, ou=0)
    u8 cell;        // cela del projectil (13 = ou/bala/plat, 14 = coet, 15 = bola)
    u8 cooldown;
    u8 drawn_byte_count[2];
    u8 drawn_row_count[2];
    u16 drawn_dst[2];
} Projectile;

// Estat a ZERO (sense init: veure capcalera) i en2_init (slot 3)
// omple l'spawn a runtime.
static Enemy s_enemies[ENEMY_N];
static Projectile s_proj;
static u8 s_proj_bg[1][56];

#define SLOT_NONE 0x0F

#if LEVEL_ID == 2
// L3: els tiles de barana/plataforma son foreground (DOS byte >= 0x80).
// El runtime nomes te el tile CK2 (blau + barana); falta la base CK1 (terra).
// Abans de dibuixar l'enemic, pintem la base sota els peus. Son els compact
// IDs de L3: 0x9A->0x1A, 0x82->0x02, 0x84->0x04.
static u8 en2_l3_base_tile(u8 t) {
    if (t == 144) return 26;
    if (t == 121) return 2;
    if (t == 123) return 4;
    return 0;
}

static void en2_l3_draw_base(i16 x, i16 y8) {
    u16 col = (u16)((x + 8) >> 3);
    u16 row = (u16)(((y8 >> 3) + ENEMY_HT) >> 4);
    u8 prev, t, b;

    if (col >= s_lv.map_w || row >= s_lv.map_h) return;
    prev = bank_set(0xC5);
    t = ((const u8*)0x4000)[(u16)(row * 128) + col];
    bank_restore(prev);
    b = en2_l3_base_tile(t);
    if (b) {
        render_tile_world(b, col, row, g_cam_x4, g_cam_row);
    }
}
#endif

// Pool de fons a BANC C6 0x7A00 (6x256 = 1536 B, 0x7A00..0x7FFF).
#define BG_BASE ((u16)0x7A00)
#define BG_SLOT(s) (BG_BASE + (((u16)((u8)(s))) << 8))
static i8 s_bg_owner[BG_SLOTS];
static u16 s_slot_dst[BG_SLOTS];
static u8 s_slot_span[BG_SLOTS];
static u8 s_slot_rows[BG_SLOTS];
static u8 s_slot_pend;

// (10/30/26 P3) Els sprites girats JA NO fan servir un buffer de flip
// dedicat: la cela girada es desa a la MATEIXA cache ZX0 amb la clau
// 'cela | 0x80'. Aixi dos enemics girats amb celes diferents conviuen
// sense trepitjar-se i no es re-flipeja cap cela a cada frame.

extern u8 tile_type(u16 col, u16 row);
extern u8 tile_flags(u16 col, u16 row);
extern u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch);

// Rutines rapides en ASM per flipejar una cela dins la cache (engine/enemy_table.s):
extern void en2_init_lut(void);
extern void en2_flip_cell(const u8* src, u8* dst);

// Descompressor ZX0 resident (Bloc 0; sempre mapejat, es pot cridar des de C6).
extern void zx0_decompress(const void* src, void* dst);

// ============================================================
// CelÂ·les d'enemic COMPRIMIDES amb ZX0 + cache de 4 slots (C6).
// Layout generat per tools/build.py (build_enemybank):
//   0x4000  taula de 16 punters absoluts (2 B per cela; 14 usades)
//   0x4040  blocs ZX0, un flux INDEPENDENT per cela (permte salt directe)
//   0x5000  cache: 4 slots de 512 B (scratch)
//   0x5800  estat: cela dins cada slot (0xFF = buit), next i comptador
// El codi i les dades de C6 no es mouen; s'alliberen ~2,5 KB de frames.
// Cost: ~3,5 ms per cela descomprimida (ldir 21 T/byte a 4 MHz), pero
// nomes en fallada de cache (comptador a 0x5818 per mesurar-ho a l'emu).
// ============================================================
#define ENEMY_CELLS        16
#define ENEMY_CELL_SIZE    512
#define SHOOT_CYCLE_FRAMES 24   // cicle complet 1:1 DOS (48 bucles DOS = 24 frames CPC @ 25 Hz)
#define AIM_FRAMES         12   // duracio de la pose de tret (~0,5 s a 25 Hz)
#define ENEMY_CELL_TABLE   ((const u8*)0x4000)
#define ENEMY_BBOX_ADDR    ((u8*)0xB700)
#define ENEMY_CACHE_SLOTS  5
static u8 s_cache_who[ENEMY_CACHE_SLOTS];
static u8 s_cache_next;
static const u8 s_cell_hi[16] = {
    0x80, 0x82, 0x84, 0x88, 0x8A, 0x8C,
    0x90, 0x92, 0x94, 0x98, 0x9A, 0x9C,
    0xA0, 0xA2, 0xA4, 0xA8
};
static const u8 s_cache_hi[5] = {
    0xAA, 0xAC, 0xB0, 0xB2, 0xB4
};
#define CELL_PTR(c)  ((u8*)((u16)s_cell_hi[c] << 8))
#define CACHE_PTR(s) ((u8*)((u16)s_cache_hi[s] << 8))
// Single Buffer + CRTC Split: totes 16 celes viuen als primers 1536 B de cada
// bloc 2KB de RAM 2 (deixant +0x760..+0x7FF lliure per al HUD fix a 0x8760).
static const u8* en2_cell(u8 cell, u8 flip) {
    u8 s;
    if (cell >= ENEMY_CELLS) cell = 0;
    if (!flip) return CELL_PTR(cell);
    for (s = 0; s < ENEMY_CACHE_SLOTS; s++) {
        if (s_cache_who[s] == cell)
            return CACHE_PTR(s);
    }
    s = s_cache_next;
    s_cache_next = (u8)((s + 1 >= ENEMY_CACHE_SLOTS) ? 0 : (s + 1));
    en2_flip_cell(CELL_PTR(cell), CACHE_PTR(s));
    s_cache_who[s] = cell;
    g_enemy_decomp_cnt++;
    return CACHE_PTR(s);
}

// Taula d'spawn (20 slots L1). VALORS = FORMULA OFICIAL
// (docs/DOS_CPC_COORDINATES.md / AGENTS.md regla 4):
//   cpc_x = dos_x / 2 - 8   (vora esquerra; dos_x es el CENTRE a DOS)
//   cpc_y = dos_y - 32      (top; dos_y es la base dels peus a DOS)
// Generada amb `py -3 tools/dos_coord_converter.py --level 0`; el camp
// "slot DOS" del comentario es l'index de staticres.c del qual surt.
// Aterratge validat amb `py -3 tools/sim_enemies.py` (MAP0/TRIG0 reals).
// 3 iaies, 5 policies, 2 peixos, 3 ocells, 2 grangers, 1 cambrera, 4 rockers.
#define s_spawn ((const Spawn*)0x4B20)




static u16 s_prev_cx;
static u16 s_prev_cr;
static u8  s_prev_conv;

void en2_init(void) {
    u8 i;
    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    en2_init_lut();
    {
        const u16* pt = (const u16*)ENEMY_CELL_TABLE;
        u8* bb = ENEMY_BBOX_ADDR;
        for (i = 0; i < ENEMY_CELLS; i++, pt++, bb += 4) {
            u8* dst = CELL_PTR(i);
            const u8* p;
            u8 r, col, x0 = 7, x1 = 0, y0 = 32, y1 = 0;
            zx0_decompress((const void*)(*pt), dst);
            p = dst;
            for (r = 0; r < 32; r++) {
                for (col = 0; col < 8; col++, p += 2) {
                    if (*p != 0xFF) {
                        if (col < x0) x0 = col;
                        if (col > x1) x1 = col;
                        if (y0 > 31) y0 = r;
                        y1 = r;
                    }
                }
            }
            if (x0 > x1) { x0 = 0; x1 = 0; y0 = 0; y1 = 0; }
            bb[0] = x0;
            bb[1] = (u8)(x1 - x0 + 1);
            bb[2] = y0;
            bb[3] = (u8)(y1 - y0 + 1);
        }
    }
    for (i = 0; i < ENEMY_CACHE_SLOTS; i++) s_cache_who[i] = 0xFF;
    s_cache_next = 0;
    g_enemy_decomp_cnt = 0;
    s_prev_cx = 0xFFFF;
    s_prev_conv = 0xFF;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        e->x = sp->x;
        e->y8 = sp->y8;
        e->dir = (sp->vx == 0) ? -1 : 1;
        e->vy = 0;
        // Els estatics tambe han de CAURE al terra (DOS: tots els objectes
        // tenen yacc=2). El tipus 4 amb vx=0 (pistola de L3) naixia flotant
        // i podia quedar encastat dins un mur.
        e->on_ground = (sp->kind == 8 || sp->kind == 19) ? 1 : 0;
        e->tick = 0;
        e->shoot_timer = 0;
        e->dead = 0;
        e->slot_bits = 0xFF;
    }
    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
    s_slot_pend = 0;
    s_proj.kind = 0;
    s_proj.cooldown = 0;
    s_proj.cell = 13;
    
    s_proj.drawn_row_count[0] = 0;
}

// Y: gravetat + snap al terra (mateix que en Jake, alcada 32). Retorna la
// nova y en pixels. Es treu del bucle per poder-lo reutilitzar pels enemics
// estatics (tipus 11 de L2), que no es mouen en X pero si que cauen.
static i16 en2_fall(Enemy* e, i16 y, u8 kind) {
    if (!e->on_ground) {
        i16 prev_feet = (i16)(y + ENEMY_HT);
        i16 feet;
        u8 trow;
        e->vy = (i16)(e->vy + ENEMY_GRAV);
        if (e->vy > ENEMY_VYMAX) e->vy = ENEMY_VYMAX;
        e->y8 = (i16)(e->y8 + e->vy);
        y = (i16)(e->y8 >> 3);
        feet = (i16)(y + ENEMY_HT);
        trow = (u8)(feet >> 4);
        if (trow < s_lv.map_h) {
            // Columna del CENTRE (xpos16 a DOS), no les del cos.
            u16 cc = (u16)((e->x + 8) >> 3);
            i16 surf = (i16)(trow << 4);
            u8 tp = tile_props_at(cc, trow);
            if ((tp & 0x08) &&
                (prev_feet < surf || (prev_feet <= (surf + 8) && (tp & 0x40))) &&
                feet >= surf) {
                e->y8 = (i16)((surf - ENEMY_HT) << 3);
                if (kind == 25) {
                    // 1:1 DOS object_func_op18: yfriction = 2 (hop continu)
                    e->vy = -16;
                    e->on_ground = 0;
                } else {
                    e->vy = 0;
                    e->on_ground = 1;
                }
            }
        }
    } else if ((e->tick & 3) == 0) {
        u8 trow = (u8)((y + ENEMY_HT) >> 4);
        if (trow < s_lv.map_h) {
            u16 cc = (u16)((e->x + 8) >> 3);
            if (!(tile_props_at(cc, trow) & 0x08)) {
                e->on_ground = 0;
            }
        }
    }
    return y;
}

static u8           s_ed_n;
static u8           s_ed_i;
static Enemy*       s_ed_e;
static const Spawn* s_ed_sp;

void en2_update_vis(void) {
    Enemy* e = s_ed_e;
    const Spawn* sp = s_ed_sp;
    u8 in_range = 0;

    if (e->dead) {
        if (e->dead == 1) {
            e->x = (i16)(e->x + (e->dir > 0 ? 3 : -3));
            e->vy = (i16)(e->vy + ENEMY_GRAV);
            e->y8 = (i16)(e->y8 + e->vy);
            if ((i16)(e->y8 >> 3) > (g_en_view_y + 180)) {
                e->dead = 2;
            }
        }
        return;
    }

    g_en_y = (i16)(e->y8 >> 3);
        if (sp->kind == 4 || sp->kind == 17 || sp->kind == 21 || sp->kind == 23 || sp->kind == 26) {
            // 1:1 DOS: op2 (policia), op10 (cambrera/llançador), op7, op4 (bazuka L3)
            // i op11 (presidiari L3, via throw_cell == 10)
            g_en_dy = g_en_jake_y - g_en_y;
            g_en_dx_jake = g_en_jake_x - e->x;
            i16 abs_dx = (g_en_dx_jake >= 0) ? g_en_dx_jake : -g_en_dx_jake;
            u8 is_cop = (sp->kind == 4);
            u8 is_throw = (sp->kind == 21);
            i16 max_y = (is_cop || sp->kind == 23) ? 20 : 10;
            i16 min_y = is_cop ? -60 : -30;
            i16 max_x = is_cop ? 40 : (is_throw ? 40 : 80);
            u8 facing_jake = (e->dir > 0) ? (g_en_dx_jake >= 0) : (g_en_dx_jake <= 0);
            if (sp->kind == 26 || sp->throw_cell == 10) {
                // 1:1 DOS object_func_op3 / op10: no exigeix encarament previ.
                max_y = (sp->kind == 26) ? 20 : 10;
                min_y = -160;
                max_x = 160;
                facing_jake = 1;
            }
            if (facing_jake && g_en_dy <= max_y && g_en_dy >= min_y && abs_dx < max_x) {
                in_range = 1;
                // 1:1 DOS: gira encarant en Jake immediatament quan entra en rang
                e->dir = (g_en_dx_jake >= 0) ? 1 : -1;
                if (!e->shoot_timer) {
                    e->shoot_timer = (!s_proj.kind && !s_proj.cooldown) ? SHOOT_CYCLE_FRAMES : 1;
                }
            }
        }

        if (e->shoot_timer) {
            e->shoot_timer--;
            g_en_dx = 0;
            g_en_nx = e->x;
            if (e->shoot_timer == (SHOOT_CYCLE_FRAMES - (AIM_FRAMES / 2))) {
                if (!s_proj.kind && !s_proj.cooldown) {
                    u8 p_k = 9, p_h = 11, p_ro = 19, p_dy = 8;
                    s_proj.cell = 13;
#if LEVEL_ID == 2
                    if (sp->kind == 26) {
                        // 1:1 DOS do_level_update_projectile default:
                        // ypos = peus - 18 es la BASE del projectil (h=10).
                        // El port desa el TOP: peus - 28 = (g_en_y + 4).
                        // El coet (cela 14, files 13..22) surt HORITZONTAL:
                        // l'estat unk42==2 del DOS posa yvelocity = 0.
                        s_proj.cell = 14;
                        p_k = 26; p_h = 10; p_ro = 13; p_dy = 4;
                    } else
#endif
                    if (sp->throw_cell == 10) {
                        // 1:1 DOS grab_type 12: ypos = peus - 3 (base) i
                        // yvelocity = 0. La bola viu a la cela 13 (files 9..17),
                        // no a la 15 (buida): abans era invisible.
                        p_k = 27; p_h = 9; p_ro = 9; p_dy = 20;
                    } else if (sp->kind == 4) {
                        p_k = 4; p_h = 6; p_ro = 13;
                    } else if (sp->throw_cell == 12) {
                        // Tipus 21 (obrer pistola pneumàtica): 1:1 DOS frame 178 (SQV 32, 16x7 px)
                        p_k = 21; p_h = 7; p_ro = 0;
                    } else if (sp->throw_cell == 6) {
                        // Tipus 13 (mecanic): 1:1 DOS frame 164 (SQV 18, 16x9 px)
                        p_k = 13; p_h = 9; p_ro = 7; p_dy = 5;
                    } else if (sp->throw_cell == 9) {
                        // Tipus 14 (obrer): 1:1 DOS frame 180 (SQV 34, 16x11 px)
                        p_k = 14; p_h = 11; p_ro = 16; p_dy = 3;
                    }
                    s_proj.kind = p_k;
                    s_proj.ht = p_h;
                    s_proj.row_offset = p_ro;
                    s_proj.y8 = (i16)((g_en_y + p_dy) << 3);
                    s_proj.x = (i16)(e->x + ((e->dir > 0) ? 16 : 0));
                    {
                        i16 pv = (sp->kind == 27) ? 32 : 64;
                        s_proj.vx = (e->dir > 0) ? pv : (i16)-pv;
                    }
                    s_proj.vy = 0;
                    s_proj.cooldown = (SHOOT_CYCLE_FRAMES - (AIM_FRAMES / 2));
                }
            }
        } else if (in_range) {
            g_en_dx = 0;
            g_en_nx = e->x;
        } else {
            g_en_dx = (i16)(sp->vx >> 3);
            if (e->dir < 0) g_en_dx = (i16)-g_en_dx;
            g_en_nx = (i16)(e->x + g_en_dx);
        }

        if (sp->kind == 22) {
            // Estatic pur (type 11 de L2 / cambrera estatica de L1)
        } else if (sp->vx == 0) {
            // Estatic (ex: policia repla ascensors)
            g_en_dy = g_en_jake_y - g_en_y;
            if (g_en_dy >= -24 && g_en_dy <= 32) {
                g_en_dx_jake = g_en_jake_x - e->x;
                if (g_en_dx_jake < -16) e->dir = -1;
                else if (g_en_dx_jake > 16) e->dir = 1;
            } else if ((e->tick & 127) == 0) {
                e->dir = (i8)-e->dir;
            }
        } else if ((sp->kind & ~1) == 8 || sp->kind == 19) {
            if (sp->kind != 19) {
                u16 frow = (u16)((g_en_y + ENEMY_HT - 4) >> 4);
                u16 cchk = (u16)((g_en_nx + 8 + (e->dir > 0 ? 8 : -8)) >> 3);
                if (!(tile_props_at(cchk, frow) & 0x80)) {
                    e->dir = (i8)-e->dir;
                } else {
                    e->x = g_en_nx;
                }
            } else {
                u16 frow = (u16)((g_en_y + ENEMY_HT) >> 4);
                u16 cchk = (u16)((e->x + 8 + (e->dir << 4)) >> 3);
                if (!(tile_props_at(cchk, frow) & 0x01)) e->dir = (i8)-e->dir;
                e->x = (i16)(e->x + (i16)(e->dir * 3));
            }
            e->on_ground = 1;
            e->vy = 0;
        } else {
            // WALKERS (Iaia 15, Policia 4, Granger 18, Cambrera 17, Rocker 20):
            if (g_en_nx < 0) { g_en_nx = 0; e->dir = 1; }
            if (g_en_nx > (i16)(s_lv.map_w_px - ENEMY_W)) { g_en_nx = (i16)(s_lv.map_w_px - ENEMY_W); e->dir = -1; }
            if (!e->shoot_timer && !in_range) {
                u16 ccol = (u16)((u16)(e->x + 8) >> 3);
                u16 fy = (u16)(g_en_y + ENEMY_HT);
                g_en_clip_x0 = (i16)(ccol + (e->dir > 0 ? 2 : -2));
                g_en_clip_x1 = (i16)((u16)(g_en_nx + (e->dir > 0 ? ENEMY_W - 1 : 0)) >> 3);
                g_en_start_byte = (u8)(fy >> 4);
                g_en_byte_count = (u8)((fy - 1) >> 4);
                g_en_start_row = (u8)((fy - 2) >> 4);
                g_en_row_count = (u8)((u16)(g_en_y + 8) >> 4);
                bc_a = (u16)((e->dir > 0 ? 0x11 : 0x21) | (sp->kind == 21 ? 0x02 : 0));
                if (walker_sense()) {
                    e->dir = (i8)-e->dir;
                } else {
                    e->x = g_en_nx;
                }
            }
            g_en_y = en2_fall(e, g_en_y, sp->kind);
        }

        if (sp->kind == 22 || sp->vx == 0) {
            g_en_y = en2_fall(e, g_en_y, sp->kind);
        }

        if (sp->kind == 19 && !s_proj.kind && !s_proj.cooldown) {
            if (g_en_jake_y > g_en_y && (g_en_jake_y - g_en_y) < 130) {
                i16 diff = g_en_jake_x - e->x;
                if (diff > -16 && diff < 16) {
                    s_proj.kind = 10;
                    s_proj.ht = 13;
                    s_proj.row_offset = 0;
                    s_proj.x = (i16)(e->x + 4);
                    s_proj.y8 = (i16)((g_en_y + 16) << 3);
                    s_proj.vx = 0;
                    s_proj.vy = 16;
                    s_proj.cooldown = 40;
                }
            }
        }

    if ((u16)(e->x - g_en_jake_x + 22) < 44 &&
        (u16)(g_en_y - g_en_jake_y + 58) < 104) {
        g_jake_en_near = 1;
    }
    e->tick++;
}

void en2_update(void) {
    g_en_view_x = (i16)(g_cam_x4 << 2);
    g_en_view_y = (i16)(g_cam_row << 3);
    g_en_jake_x = (i16)(s_px8 >> 3);
    g_en_jake_y = (i16)(s_py8 >> 3);
    g_jake_en_near = (u8)(s_proj.kind != 0 &&
                          (u16)(s_proj.x - g_en_jake_x + 20) < 40 &&
                          (u16)((s_proj.y8 >> 3) - g_en_jake_y + 32) < 76);
    g_en_act_xmin = (i16)(g_en_view_x - 78);
    g_en_act_ymin8 = (i16)((g_en_view_y - 80) << 3);
    s_ed_n = ENEMY_N;
    s_ed_e = s_enemies;
    __asm
        push ix
        push iy
        ld   a, (_s_ed_n)
        or   a
        jr   z, 09804$
        ld   b, a
        ld   ix, (_s_ed_e)
        ld   iy, #0x4B20
    09801$:
        ld   l, 0(iy)
        ld   h, 1(iy)
        ld   de, (_g_en_act_xmin)
        or   a
        sbc  hl, de
        ld   de, #301
        or   a
        sbc  hl, de
        jr   nc, 09803$
        ld   l, 2(iy)
        ld   h, 3(iy)
        ld   de, (_g_en_act_ymin8)
        or   a
        sbc  hl, de
        ld   de, #0x0A01
        or   a
        sbc  hl, de
        jr   nc, 09803$
        ld   (_s_ed_e), ix
        ld   (_s_ed_sp), iy
        push bc
        push ix
        push iy
        call _en2_update_vis
        pop  iy
        pop  ix
        pop  bc
    09803$:
        ld   de, #12
        add  ix, de
        ld   de, #9
        add  iy, de
        djnz 09801$
    09804$:
        pop  iy
        pop  ix
    __endasm;

    if (s_proj.cooldown) s_proj.cooldown--;
    if (s_proj.kind) {
        s_proj.x = (i16)(s_proj.x + (s_proj.vx >> 3));
        s_proj.y8 = (i16)(s_proj.y8 + s_proj.vy);
        if (s_proj.kind == 10) {
            s_proj.vy = (i16)(s_proj.vy + 8);
            if (s_proj.vy > 64) s_proj.vy = 64;
        }
        {
            g_en_y = (i16)(s_proj.y8 >> 3);
            if ((u16)(s_proj.x - g_en_view_x + 16) > 192 ||
                (u16)(g_en_y - g_en_view_y + 16) > 176) {
                s_proj.kind = 0;
            } else if (s_proj.kind == 10) {
                u16 trow = (u16)((g_en_y + s_proj.ht) >> 4);
                u16 tcol = (u16)((s_proj.x + 4) >> 3);
                if (trow < s_lv.map_h && (tile_props_at(tcol, trow) & 0x08)) {
                    s_proj.kind = 0;
                }
            }
        }
    }
}

// Reserva slot de fons per (enemic, pagina): existent o lliure; -1 si ple.
static i8 en2_slot(i8 idx) {
    u8 k;
    i8 s = (i8)s_enemies[(u8)idx].slot_bits;
    if (s >= 0) return s;
    for (k = 0; k < BG_PAGESLOTS; k++) {
        if (s_bg_owner[k] < 0) {
            s_bg_owner[k] = idx;
            s_enemies[(u8)idx].slot_bits = (u8)k;
            return (i8)k;
        }
    }
    return -1;
}

static Enemy* s_slot_ptr[BG_PAGESLOTS];
static const Spawn* s_slot_sp[BG_PAGESLOTS];
static i16 s_slot_ex[BG_PAGESLOTS];
static i16 s_slot_ey8[BG_PAGESLOTS];
static u8  s_slot_key[BG_PAGESLOTS];

static u8 en2_frame_key(const Enemy* e, const Spawn* sp) {
    u8 is_aiming = (e->shoot_timer > (SHOOT_CYCLE_FRAMES - AIM_FRAMES));
    u8 step = (e->dead || sp->vx == 0 || e->shoot_timer || sp->base_cell == sp->aim_cell) ? 0 : (u8)((e->tick >> 2) & 1);
    u8 cell = (u8)(sp->base_cell + step);
    if (is_aiming) {
        if (sp->kind == 4 || sp->kind == 26) cell = sp->aim_cell;
        else if (sp->kind == 17 || sp->kind == 21 || sp->kind == 23) cell = sp->throw_cell;
    }
    return (u8)((cell << 1) | (e->dir < 0 ? 1 : 0));
}

static u8 en2_ov(u8 a, u8 b) {
    if (s_bg_owner[a] < 0 || s_bg_owner[b] < 0) return 0;
    return (u8)((u16)(s_slot_ex[a] - s_slot_ex[b] + 23) < 47 &&
                (u16)(s_slot_ey8[a] - s_slot_ey8[b] + (39 << 3)) < (79 << 3));
}

static void en2_restore_slot(u8 k) {
    g_moving_dst = s_slot_dst[k];
    g_moving_background = BG_SLOT(k);
    g_moving_span = s_slot_span[k];
    g_moving_rows = s_slot_rows[k];
    moving_restore_box();
    s_slot_ptr[k]->slot_bits = 0xFF;
    s_bg_owner[k] = -1;
}

void en2_restore(void) {
    u8 k, b, full, keep_mask, any_dirty, was_proj, ov_mask;
    if (bc_a == 1) return;

    if (bc_a == 2) {
        i16 vx = (i16)((g_cam_x4 << 2) + 8);
        for (k = 0; k < BG_SLOTS; k++) {
            if (s_bg_owner[k] >= 0 && (u16)(s_slot_ex[k] - vx) >= 129) {
                en2_restore_slot(k);
            }
        }
        return;
    }

    s_slot_pend = 0;

    // 1. Restaura projectil (ordre LIFO: ultim dibuixat, primer restaurat):
    was_proj = s_proj.drawn_row_count[0];
    if (was_proj) {
        g_moving_dst = s_proj.drawn_dst[0];
        g_moving_background = (u16)s_proj_bg[0];
        g_moving_span = s_proj.drawn_byte_count[0];
        g_moving_rows = was_proj;
        moving_restore_box();
        s_proj.drawn_row_count[0] = 0;
    }

    keep_mask = 0;
    any_dirty = 0;
    ov_mask = 0;
    full = (u8)(was_proj || (u16)(g_cam_x4 - s_prev_cx + 1) > 2 ||
                g_cam_row != s_prev_cr ||
                s_rep_n || s_conveyor_phase != s_prev_conv ||
                s_carry_drawn[0] || s_carry_state);
#if (LEVEL_ELEVATOR_COUNT + LEVEL_PRESS_COUNT + LEVEL_SCAFFOLD_COUNT) > 0
    if (!full) {
        MovingElevator* ev = g_mag_elevators;
        for (k = MAG_MOVER_COUNT; k; k--, ev++) {
            if (ev->drawn[0] && ev->delta_y) { full = 1; break; }
        }
    }
#endif
    if (!full) {
        u8 hscroll = (u8)(g_cam_x4 != s_prev_cx);
        i16 vx4 = (i16)((g_cam_x4 << 2) + 4);
        for (k = 0, b = 1; k < 3; k++, b += b) {
            if (s_bg_owner[k] >= 0) {
                const Enemy* e = s_slot_ptr[k];
                if (!(hscroll && (u16)(s_slot_ex[k] - vx4) >= 137) &&
                    e->dead != 2 &&
                    e->x == s_slot_ex[k] && e->y8 == s_slot_ey8[k] &&
                    en2_frame_key(e, s_slot_sp[k]) == s_slot_key[k]) {
                    keep_mask |= b;
                } else {
                    any_dirty = 1;
                }
            }
        }
        if (en2_ov(0, 1)) ov_mask |= 3;
        if (en2_ov(0, 2)) ov_mask |= 5;
        if (en2_ov(1, 2)) ov_mask |= 6;
        if (any_dirty && (keep_mask & ov_mask)) {
            keep_mask &= (u8)~ov_mask;
        }
    }

    // 2. Restaura walkers LIFO (o difereix a atomic restore->draw si no se solapen):
    for (k = 2, b = 4; b; k--, b >>= 1) {
        if (s_bg_owner[k] < 0 || (keep_mask & b)) continue;
        if (full || (ov_mask & b) || s_slot_ptr[k]->dead == 2) {
            en2_restore_slot(k);
        } else {
            s_slot_pend |= b;
            s_slot_ptr[k]->slot_bits = (u8)(0x80 | k);
        }
    }
}

static i16    s_ed_min_x;
static i16    s_ed_min_y8;

extern u8 ram2_en2_clip(i16 x, i16 y);
#define en2_clip(x, y, w, h) (g_en_byte_count = (w), g_en_row_count = (h), ram2_en2_clip((x), (y)))

void en2_draw_vis(void) {
    Enemy* e = s_ed_e;
    const Spawn* sp = s_ed_sp;
    const u8* frame;
    const u8* bb;
    i8 s;
    u8 key, cell, bx0, bw, by0, bh, ww;
    i16 wx, wy;

    g_en_y = (i16)(e->y8 >> 3);
    key = en2_frame_key(e, sp);
    cell = (u8)(key >> 1);
    bb = ENEMY_BBOX_ADDR + (cell << 2);
    bw = bb[1];
    bx0 = (key & 1) ? (u8)(8 - bb[0] - bw) : bb[0];
    by0 = bb[2];
    bh = bb[3];
    wx = (i16)(e->x + (bx0 << 1));
    wy = (i16)(g_en_y + by0);
    ww = (u8)(bw << 1);

    if (!en2_clip(wx, wy, ww, bh)) return;
    g_en_start_byte += bx0;
    g_en_start_row += by0;
    frame = en2_cell(cell, (u8)(key & 1));

    {
        u8 pk = (u8)(e->slot_bits & 0x7F);
        if (pk < BG_SLOTS) {
            u8 m = (u8)(pk == 2 ? 4 : (pk + 1));
            if (s_slot_pend & m) {
                s_slot_pend &= (u8)~m;
                en2_restore_slot(pk);
            }
        }
    }
    s = en2_slot((i8)s_ed_i);
    if (s < 0) return;

#if LEVEL_ID == 2
    en2_l3_draw_base(e->x, e->y8);
#endif

    g_moving_dst = (u16)ring_address(0, g_en_clip_x0, g_en_clip_y0);
    s_slot_dst[(u8)s] = g_moving_dst;
    g_moving_background = BG_SLOT(s);
    g_moving_sprite = (u16)(frame + ((u16)g_en_start_row << 4) + (g_en_start_byte << 1));
    g_moving_span = g_en_byte_count;
    g_moving_rows = g_en_row_count;
    g_moving_spr_skip = (u8)(16 - (g_en_byte_count << 1));
    moving_blit_box();

    s_slot_span[(u8)s] = g_en_byte_count;
    s_slot_rows[(u8)s] = g_en_row_count;
    s_slot_ptr[(u8)s] = e;
    s_slot_sp[(u8)s] = sp;
    s_slot_ex[(u8)s] = e->x;
    s_slot_ey8[(u8)s] = e->y8;
    s_slot_key[(u8)s] = key;
}

void en2_draw(void) {
    g_en_view_x = (i16)(g_cam_x4 << 2);
    g_en_view_y = (i16)(g_cam_row << 3);
    if (bc_a) return;

    s_ed_n = ENEMY_N;
    s_ed_min_x = (i16)(g_en_view_x - 15);
    s_ed_min_y8 = (i16)((g_en_view_y - (ENEMY_HT - 1)) << 3);
    s_ed_e = s_enemies;
    __asm
        push ix
        push iy
        ld   a, (_s_ed_n)
        or   a
        jr   z, 09904$
        ld   b, a
        ld   c, #0
        ld   ix, (_s_ed_e)
        ld   iy, #0x4B20
    09901$:
        ld   a, 10(ix)
        cp   #2
        jr   z, 09903$
        bit  7, 11(ix)
        jr   z, 09903$
        ld   l, 0(ix)
        ld   h, 1(ix)
        ld   de, (_s_ed_min_x)
        or   a
        sbc  hl, de
        ld   de, #175
        or   a
        sbc  hl, de
        jr   nc, 09903$
        ld   l, 2(ix)
        ld   h, 3(ix)
        ld   de, (_s_ed_min_y8)
        or   a
        sbc  hl, de
        ld   de, #0x05F8
        or   a
        sbc  hl, de
        jr   nc, 09903$
        ld   a, c
        ld   (_s_ed_i), a
        ld   (_s_ed_e), ix
        ld   (_s_ed_sp), iy
        push bc
        push ix
        push iy
        call _en2_draw_vis
        pop  iy
        pop  ix
        pop  bc
    09903$:
        ld   de, #12
        add  ix, de
        ld   de, #9
        add  iy, de
        inc  c
        djnz 09901$
    09904$:
        pop  iy
        pop  ix
    __endasm;

    // Si algun enemic pendent va sortir fora de pantalla, restaura'l ara:
    if (s_slot_pend) {
        u8 k, b;
        for (k = 0, b = 1; k < BG_SLOTS; k++, b += b) {
            if (s_slot_pend & b) en2_restore_slot(k);
        }
        s_slot_pend = 0;
    }

    // 2. Dibuixa projectil si esta actiu:
    if (s_proj.kind && !s_proj.drawn_row_count[0]) {
        u8 is_ball = (s_proj.kind == 27);
        g_en_y = (i16)(s_proj.y8 >> 3);
        if (en2_clip(s_proj.x, g_en_y, (u8)(is_ball ? 12 : 8), s_proj.ht)) {
            const u8* frame = en2_cell(s_proj.cell, (u8)(s_proj.vx < 0))
                + (((u16)s_proj.row_offset + g_en_start_row) << 4)
                + (is_ball ? 2 : 4) + (g_en_start_byte << 1);

            g_moving_dst = (u16)ring_address(0, g_en_clip_x0, g_en_clip_y0);
            s_proj.drawn_dst[0] = g_moving_dst;
            g_moving_background = (u16)s_proj_bg[0];
            g_moving_sprite = (u16)frame;
            g_moving_span = g_en_byte_count;
            g_moving_rows = g_en_row_count;
            g_moving_spr_skip = (u8)(16 - (g_en_byte_count << 1));
            moving_blit_box();

            s_proj.drawn_byte_count[0] = g_en_byte_count;
            s_proj.drawn_row_count[0] = g_en_row_count;
        }
    }
    s_prev_cx = g_cam_x4;
    s_prev_cr = g_cam_row;
    s_prev_conv = s_conveyor_phase;
}

static u8 en2_he(u8 k) {
    if (k == 24) return 10; // 1:1 DOS level_obj_h[6] = 10 (rata)
    if (k == 25) return 18;
    if (k == 8 || k == 19) return 16;
    if (k == 4) return 28;
    return 30;
}

static i8 en2_hit_box(i16 xmin, u8 xw, i16 top, i16 bot) {
    u8 i;
    const Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        u8 k;
        i16 e_bot;
        if (e->dead) continue;
        if ((u16)(e->x - xmin) >= (u16)xw) continue;
        k = sp->kind;
        if (k == 8) continue; // peix (decoracio DOS op1)
        e_bot = (i16)((e->y8 >> 3) + ENEMY_HT);
        if (e_bot > top && (i16)(e_bot - en2_he(k)) < bot) {
            return (i8)i;
        }
    }
    return -1;
}

void en2_check_player_hit(void) {
    i16 jake_top, jake_bottom;

    bc_r = 0;
    jake_top = (u8)bc_c ? (i16)((i16)bc_b + 16) : (i16)((i16)bc_b + 4);
    jake_bottom = (i16)((i16)bc_b + 30);

    // 1. Projectil (bala, plat, ou):
    if (s_proj.kind) {
        if ((u16)(s_proj.x - (i16)bc_a + 8) < 24) {
            i16 proj_y = (i16)(s_proj.y8 >> 3);
            i16 proj_bottom = (i16)(proj_y + s_proj.ht);
            if (proj_bottom > jake_top && proj_y < (i16)((i16)bc_b + 32)) {
                s_proj.kind = 0;
                bc_r = 1;
                return;
            }
        }
    }

    // 2. Walkers / Enemics (peus a (e->y8>>3) + ENEMY_HT, alçada real he).
    if (en2_hit_box((i16)((i16)bc_a - 9), 19, jake_top, jake_bottom) >= 0) {
        bc_r = 1;
    }
}

void en2_check_crate_hit(void) {
    i8 idx = en2_hit_box((i16)((i16)bc_a - 16), 32, (i16)bc_b, (i16)((i16)bc_b + 16));
    bc_r = 0;
    if (idx >= 0) {
        Enemy* e = &s_enemies[(u8)idx];
        e->dead = 1;
        e->dir = ((i16)bc_c > 0) ? 1 : -1;
        e->vy = -48; // Impuls vertical amunt 1:1 DOS yfriction=12 (6 px/frame)
        e->on_ground = 0;
        bc_r = 1;
    }
}

void en2_room_exit(void) {
    u8 i;
    Enemy* e = s_enemies;

    // No es teletransporta cap enemic en entrar/sortir de la sala: el
    // reposicionament a bc_a +/- 80 podia deixar la rata dins una paret,
    // on el patrol girava el dir cada frame (pivotant al mateix punt).
    // Els enemics es queden al seu lloc de patrol valid.
    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
    for (i = 0; i < ENEMY_N; i++, e++) {
        e->slot_bits = 0xFF;
    }
    s_proj.drawn_row_count[0] = 0;
    s_proj.kind = 0;
    s_prev_cx = 0xFFFF;
    s_prev_conv = 0xFF;
}
