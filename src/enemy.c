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
    u8 shoot_timer; // aturat per disparar (1:1 DOS)
    u8 dead;        // 0=viu, 1=tocat per caixa (cau lliure), 2=fora de pantalla
    i8 slot[2];     // slot de fons per pagina (-1 = no dibuixat)
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
Enemy s_enemies[ENEMY_N];
Projectile s_proj;
static u8 s_proj_bg[2][56];

// M1 v6: 1 si un enemic trepitja la caixa 16x30 del Jake. L'omple en2_update
// (que ja recorre els enemics actius) amb la posicio de pantalla del frame
// anterior (el marge de 15 px cobreix el lag) i el guard del dirty-flag el
// llegeix abans de saltar-se el restore+blit. Aixi evitem l'error persistent
// al lloc de la colisio (enemic dibuixat abans del Jake + save/restore creuat)
// amb ~0,05 ms en lloc de recórrer 26 enemics al frame quiet.
u8 g_en_overlap;

// Pool de fons a BANC C6 0x7A00 (6x256 = 1536 B, 0x7A00..0x7FFF).
#define BG_BASE ((u16)0x7A00)
#define BG_SLOT(s) (BG_BASE + (((u16)((u8)(s))) << 8))
static i8 s_bg_owner[BG_SLOTS];
static u16 s_slot_dst[BG_SLOTS];
static u8 s_slot_span[BG_SLOTS];
static u8 s_slot_rows[BG_SLOTS];

// (10/30/26 P3) Els sprites girats JA NO fan servir un buffer de flip
// dedicat: la cela girada es desa a la MATEIXA cache ZX0 amb la clau
// 'cela | 0x80'. Aixi dos enemics girats amb celes diferents conviuen
// sense trepitjar-se i no es re-flipeja cap cela a cada frame.

extern u8 tile_type(u16 col, u16 row);
extern u8 tile_flags(u16 col, u16 row);
extern u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch);
extern u8 tile_wall_probe(u16 col, u16 row);

// Rutines rapides en ASM (engine/enemy_table.s):
extern void en2_flip_cell(const u8* src, u8* dst);
extern u8 s_en_visible[32];
extern u8 en2_build_visible(void);

// Descompressor ZX0 resident (Bloc 0; sempre mapejat, es pot cridar des de C6).
extern void zx0_decompress(const void* src, void* dst);

// ============================================================
// Cel·les d'enemic COMPRIMIDES amb ZX0 + cache de 6 slots (C6).
// Layout generat per tools/build.py (build_enemybank):
//   0x4000  taula de 16 punters absoluts (2 B per cela; 14 usades)
//   0x4040  blocs ZX0, un flux INDEPENDENT per cela (permet salt directe)
//   0x4B14  s_spawn (234 B) fins 0x4BFD
//   0x4C00  cache: 6 slots de 512 B (scratch) fins 0x5800
//   0x5800  estat: cela dins cada slot (0xFF = buit), next i comptador
// El codi i les dades de C6 no es mouen; s'alliberen ~2,5 KB de frames.
// Cost: ~3,5 ms per cela descomprimida (ldir 21 T/byte a 4 MHz), pero
// nomes en fallada de cache (comptador a 0x39D9 per mesurar-ho a l'emu).
// ============================================================
#define ENEMY_CELLS        16
#define ENEMY_CELL_SIZE    512
#define SHOOT_CYCLE_FRAMES 24   // cicle complet 1:1 DOS (48 bucles DOS = 24 frames CPC @ 25 Hz)
#define AIM_FRAMES         12   // duracio de la pose de tret (~0,5 s a 25 Hz)
#define ENEMY_CELL_TABLE   ((const u8*)0x4000)
// M1 v7: 6 slots (0x4C00..0x57FF). Un shooter sol ja usa 4 claus
// (2 walk + aim + projectil); amb un altre enemic visible son 5-6 i la
// cache de 4 no donava cap hit (6 fallades/cicle, amb gir de 512 B).
// La taula de restore del nivell s'ha mogut a C1 per alliberar 0x4C00..0x5000.
#define ENEMY_CACHE_BASE   ((u8*)0x4C00)
#define ENEMY_CACHE_SLOTS  6
// Modul 6 sense `%` (car): inc + cp 6 + jr nz + xor a, com a sentencia
// (evita la doble avaluacio del ternari, que feia créixer 64 B el C6).
#define EN2_NEXT(v) do { (v)++; if ((v) == ENEMY_CACHE_SLOTS) (v) = 0; } while (0)
static u8 s_cache_who[ENEMY_CACHE_SLOTS];
static u8 s_cache_next;
// Retorna la cela 'cell', girada horitzontalment si flip != 0. Les celes
// girades es cachegen igual que les normals (clau = cell | 0x80), aixi que
// nomes es descomprimeixen i giren un cop; els frames seguents les troben
// a la cache. Si cal girar i no tenim la versio oposada, es descomprimeix
// la cela font a un slot lliure de la cache (t) i es gira directament
// cap al slot de desti s. El slot t queda registrat amb cell (sense flip).
static const u8* en2_cell(u8 cell, u8 flip) {
    u8 s, key, opp;
    if (cell >= ENEMY_CELLS) cell = 0;
    key = flip ? (u8)(cell | 0x80) : cell;
    opp = 0xFF;
    for (s = 0; s < ENEMY_CACHE_SLOTS; s++) {
        if (s_cache_who[s] == key)
            goto found;
        if (s_cache_who[s] == (u8)(key ^ 0x80)) opp = s;
    }
    s = s_cache_next;
    if (s == opp) EN2_NEXT(s);
    s_cache_next = s;
    EN2_NEXT(s_cache_next);
    if (opp != 0xFF) {
        // L'orientacio oposada ja es a la cache: nomes cal girar-la.
        en2_flip_cell(ENEMY_CACHE_BASE + ((u16)opp << 9),
                      ENEMY_CACHE_BASE + ((u16)s << 9));
    } else if (flip) {
        u8 t = s_cache_next;
        if (t == s) EN2_NEXT(t);
        s_cache_next = t;
        EN2_NEXT(s_cache_next);
        zx0_decompress((const void*)(*(const u16*)
                       (ENEMY_CELL_TABLE + ((u16)cell << 1))),
                       ENEMY_CACHE_BASE + ((u16)t << 9));
        s_cache_who[t] = cell;
        en2_flip_cell(ENEMY_CACHE_BASE + ((u16)t << 9),
                      ENEMY_CACHE_BASE + ((u16)s << 9));
    } else {
        zx0_decompress((const void*)(*(const u16*)
                       (ENEMY_CELL_TABLE + ((u16)cell << 1))),
                       ENEMY_CACHE_BASE + ((u16)s << 9));
    }
    s_cache_who[s] = key;
    g_enemy_decomp_cnt++;
found:
    return ENEMY_CACHE_BASE + ((u16)s << 9);
}

// Taula d'spawn (20 slots L1). VALORS = FORMULA OFICIAL
// (docs/DOS_CPC_COORDINATES.md / AGENTS.md regla 4):
//   cpc_x = dos_x / 2 - 8   (vora esquerra; dos_x es el CENTRE a DOS)
//   cpc_y = dos_y - 32      (top; dos_y es la base dels peus a DOS)
// Generada amb `py -3 tools/dos_coord_converter.py --level 0`; el camp
// "slot DOS" del comentario es l'index de staticres.c del qual surt.
// Aterratge validat amb `py -3 tools/sim_enemies.py` (MAP0/TRIG0 reals).
// 3 iaies, 5 policies, 2 peixos, 3 ocells, 2 grangers, 1 cambrera, 4 rockers.
// M1 v7: 0x4B14 (abans 0x4B20) per deixar 0x4C00..0x57FF als 6 slots.
// Els blocs mes grans (VILLE) acaben a 0x4B11; el spawn 0x4B14..0x4BFD.
#define s_spawn ((const Spawn*)0x4B14)




void en2_init(void) {
    u8 i;
    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    // M1: en2_init_lut() eliminat (la LUT de flip ja no existeix: el gir
    // es calcula al moment amb la mateixa formula — veure enemy_table.s).
    for (i = 0; i < ENEMY_CACHE_SLOTS; i++) s_cache_who[i] = 0xFF;
    s_cache_next = 0;
    g_enemy_decomp_cnt = 0;
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
        e->slot[0] = -1;
        e->slot[1] = -1;
    }
    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
    s_proj.kind = 0;
    s_proj.cooldown = 0;
    s_proj.cell = 13;
    
    s_proj.drawn_row_count[0] = 0;
    s_proj.drawn_row_count[1] = 0;
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
            if (is_floor_solid(cc, trow, 0, 0) &&
                prev_feet <= (surf + 8) && feet >= surf) {
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
            if (!is_floor_solid(cc, trow, 0, 0)) {
                e->on_ground = 0;
            }
        }
    }
    return y;
}

void en2_update(void) {
    u8 i;
    g_en_view_x = (i16)(g_cam_x4 << 2);
    g_en_view_y = (i16)(g_cam_row << 3);
    g_en_jake_x = (i16)(s_px8 >> 3);
    g_en_jake_y = (i16)(s_py8 >> 3);
    g_en_overlap = 0;

    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    g_en_act_xmin = (i16)(g_en_view_x - 78);
    g_en_act_ymin8 = (i16)((g_en_view_y - 132) << 3);

    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        if ((u16)(sp->x - g_en_act_xmin) > 300 ||
            (u16)(sp->y8 - g_en_act_ymin8) > (450 << 3))
            continue;

        // M1 v6: marca si aquest enemic trepitja la caixa del Jake.
        // Coordenades de MON pels dos (g_en_jake_x/y = s_px8>>3/s_py8>>3):
        // barrejar pantalla (s_mn_dsy) amb mon (e->y8>>3) feia que el check
        // Y no coincidis mai i el guard no s'activava (error persistent al
        // lloc de la colisio, vist en test real 21/11).
        if ((u16)(e->x - g_en_jake_x + 15) < 31u &&
            (u16)((e->y8 >> 3) - g_en_jake_y + 31) < 61u)
            g_en_overlap = 1;

        if (e->dead) {
            if (e->dead == 1) {
                e->x = (i16)(e->x + (e->dir > 0 ? 3 : -3));
                e->vy = (i16)(e->vy + ENEMY_GRAV);
                e->y8 = (i16)(e->y8 + e->vy);
                if ((i16)(e->y8 >> 3) > (g_en_view_y + 180)) {
                    e->dead = 2;
                }
            }
            continue;
        }

        g_en_y = (i16)(e->y8 >> 3);

        u8 in_range = 0;
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
            u8 facing_jake = (e->dir > 0 && g_en_dx_jake >= 0) || (e->dir < 0 && g_en_dx_jake <= 0);
            if (sp->kind == 26) {
                // 1:1 DOS object_func_op3 (op4, bazuka): ydist<=20 && >-160 &&
                // xdist<160; NO exigeix encarament previ.
                max_y = 20;
                min_y = -160;
                max_x = 160;
                facing_jake = 1;
            } else if (sp->throw_cell == 10) {
                // 1:1 DOS object_func_op10 (op11, presidiari): ydist<=10,
                // |xdist|<160; NO exigeix encarament previ.
                max_y = 10;
                min_y = -160;
                max_x = 160;
                facing_jake = 1;
            }
            if (facing_jake && g_en_dy <= max_y && g_en_dy >= min_y && abs_dx < max_x) {
                in_range = 1;
                // 1:1 DOS: gira encarant en Jake immediatament quan entra en rang
                e->dir = (g_en_dx_jake >= 0) ? 1 : -1;
                if (!e->shoot_timer) {
                    if (!s_proj.kind && !s_proj.cooldown) {
                        e->shoot_timer = SHOOT_CYCLE_FRAMES;
                    } else {
                        e->shoot_timer = 1;
                    }
                }
            }
        }

        if (e->shoot_timer) {
            e->shoot_timer--;
            g_en_dx = 0;
            g_en_nx = e->x;
            if (e->shoot_timer == (SHOOT_CYCLE_FRAMES - (AIM_FRAMES / 2))) {
                if (!s_proj.kind && !s_proj.cooldown) {
                    s_proj.cell = (sp->kind == 26) ? 14 : ((sp->throw_cell == 10) ? 15 : 13);
                    if (sp->kind == 26) {
                        // 1:1 DOS object_func_op3 + do_level_update_projectile:
                        // grab_type 5 -> coet de la bazuka (frame SQV 25).
                        s_proj.kind = 26;
                        s_proj.ht = 9;
                        s_proj.row_offset = 13;
                        s_proj.y8 = (i16)((g_en_y + 6) << 3);
                    } else if (sp->throw_cell == 10) {
                        // 1:1 DOS object_func_op10: grab_type 12 -> bola amb
                        // cadena (frame SQV 22), arran de terra.
                        s_proj.kind = 27;
                        s_proj.ht = 7;
                        s_proj.row_offset = 13;
                        s_proj.y8 = (i16)((g_en_y + 25) << 3);
                    } else if (sp->kind == 4) {
                        s_proj.kind = 4;
                        s_proj.ht = 6;
                        s_proj.row_offset = 13;
                        s_proj.y8 = (i16)((g_en_y + 8) << 3);
                    } else if (sp->throw_cell == 12) {
                        // Tipus 21 (obrer pistola pneumàtica): 1:1 DOS frame 178 (SQV 32, 16x7 px)
                        s_proj.kind = 21;
                        s_proj.ht = 7;
                        s_proj.row_offset = 0;
                        s_proj.y8 = (i16)((g_en_y + 8) << 3);
                    } else if (sp->throw_cell == 6) {
                        // Tipus 13 (mecanic): 1:1 DOS frame 164 (SQV 18, 16x9 px)
                        s_proj.kind = 13;
                        s_proj.ht = 9;
                        s_proj.row_offset = 7;
                        s_proj.y8 = (i16)((g_en_y + 5) << 3);
                    } else if (sp->throw_cell == 9) {
                        // Tipus 14 (obrer): 1:1 DOS frame 180 (SQV 34, 16x11 px)
                        s_proj.kind = 14;
                        s_proj.ht = 11;
                        s_proj.row_offset = 16;
                        s_proj.y8 = (i16)((g_en_y + 3) << 3);
                    } else {
                        // L1: 1:1 DOS frame 157 (SQV 11, plat 16x11 px)
                        s_proj.kind = 9;
                        s_proj.ht = 11;
                        s_proj.row_offset = 19;
                        s_proj.y8 = (i16)((g_en_y + 8) << 3);
                    }
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
                u16 frow = (u16)(((e->y8 >> 3) + ENEMY_HT - 4) >> 4);
                u16 cchk = (u16)((g_en_nx + 8 + (e->dir > 0 ? 8 : -8)) >> 3);
                u8 tt = (frow < s_lv.map_h && cchk < s_lv.map_w) ? tile_type(cchk, frow) : 1;
                if (tt != 11) {
                    e->dir = (i8)-e->dir;
                } else {
                    e->x = g_en_nx;
                }
            } else {
                u16 frow = (u16)(((e->y8 >> 3) + ENEMY_HT) >> 4);
                u16 cchk = (u16)((e->x + 8 + (e->dir << 4)) >> 3);
                if (tile_type(cchk, frow) != 1) e->dir = (i8)-e->dir;
                e->x = (i16)(e->x + (i16)(e->dir * 3));
            }
            e->on_ground = 1;
            e->vy = 0;
        } else {
            // WALKERS (Iaia 15, Policia 4, Granger 18, Cambrera 17, Rocker 20):
            if (g_en_nx < 0) { g_en_nx = 0; e->dir = 1; }
            if (g_en_nx > (i16)(s_lv.map_w_px - ENEMY_W)) { g_en_nx = (i16)(s_lv.map_w_px - ENEMY_W); e->dir = -1; }
            {
                u8 frow = (u8)((g_en_y + ENEMY_HT) >> 4);
                u8 brow = (u8)((g_en_y + ENEMY_HT - 1) >> 4);
                u8 c2row = (u8)((g_en_y + ENEMY_HT - 2) >> 4);
                u16 ccol = (u16)((e->x + 8) >> 3);
                u16 pcol = (u16)(ccol + (e->dir > 0 ? 2 : -2));
                u16 acol = (u16)((g_en_nx + (e->dir > 0 ? ENEMY_W - 1 : 0)) >> 3);
                u8 bit = (u8)(e->dir > 0 ? 1 : 2);
                u8 tt_pf = tile_type(pcol, frow);
                u8 tt_pb = tile_type(pcol, brow);
                u8 turn = (u8)(tt_pf == 1 || tt_pb == 1);
                if (sp->kind == 21 && (tt_pf == 12 || tt_pb == 12)) turn = 1;
                if (!turn) {
                    u8 p = tile_wall_probe(acol, brow);
                    if ((p & (u8)(0x80 | bit)) ||
                        (c2row != brow && (tile_wall_probe(acol, c2row) & (u8)(0x80 | bit))) ||
                        (tile_wall_probe(acol, (u8)((g_en_y + 8) >> 4)) & 0x80)) {
                        turn = 1;
                    }
                }
                if (!e->shoot_timer && !in_range) {
                    if (turn) {
                        e->dir = (i8)-e->dir;
                    } else {
                        e->x = g_en_nx;
                    }
                }
            }
            g_en_y = en2_fall(e, g_en_y, sp->kind);
        }

        if (sp->vx == 0 && sp->kind != 8 && sp->kind != 19) {
            g_en_y = en2_fall(e, g_en_y, sp->kind);
        }

        if (!s_proj.kind && !s_proj.cooldown) {
            if (sp->kind == 19) {
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
        }

        e->tick++;
    }

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
            if (s_proj.x < (i16)(g_en_view_x - 16) || s_proj.x > (i16)(g_en_view_x + 176) ||
                g_en_y < (i16)(g_en_view_y - 16) || g_en_y > (i16)(g_en_view_y + 160)) {
                s_proj.kind = 0;
            } else if (s_proj.kind == 10) {
                u16 trow = (u16)((g_en_y + s_proj.ht) >> 4);
                u16 tcol = (u16)((s_proj.x + 4) >> 3);
                if (trow < s_lv.map_h && is_floor_solid(tcol, trow, 0, 0)) {
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
        g_moving_background = (u16)s_proj_bg[page];
        g_moving_span = s_proj.drawn_byte_count[page];
        g_moving_rows = s_proj.drawn_row_count[page];
        moving_restore_box();
        s_proj.drawn_row_count[page] = 0;
    }

    // 2. Restaura walkers LIFO:
    for (k = BG_PAGESLOTS; k > 0; k--) {
        i8 s = (i8)((page ? 3 : 0) + (k - 1));
        i8 idx = s_bg_owner[(u8)s];
        if (idx < 0) continue;
        g_moving_dst = s_slot_dst[(u8)s];
        g_moving_background = BG_SLOT(s);
        g_moving_span = s_slot_span[(u8)s];
        g_moving_rows = s_slot_rows[(u8)s];
        moving_restore_box();
        s_enemies[(u8)idx].slot[page] = -1;
        s_bg_owner[(u8)s] = -1;
    }
}

void en2_draw(void) {
    u8 page = (u8)bc_a;
    u8 i, n, idx;
    Enemy* e;
    const Spawn* sp;
    g_en_view_x = (i16)(g_cam_x4 << 2);
    g_en_view_y = (i16)(g_cam_row << 3);
    if (page > 1) return;

    // 1. Dibuixa walkers. El broadphase de 26 entrades viu en ASM i
    // deixa nomes els candidats que superaven dead/slot/range-X en C.
    n = en2_build_visible();
    for (i = 0; i < n; i++) {
        const u8* frame;
        i8 s;
        idx = s_en_visible[i];
        e = &s_enemies[idx];
        sp = &s_spawn[idx];
        g_en_clip_x0 = e->x > g_en_view_x ? e->x : g_en_view_x;
        g_en_clip_x1 = e->x + ENEMY_W < g_en_view_x + 160 ?
                  (i16)(e->x + ENEMY_W) : (i16)(g_en_view_x + 160);
        g_en_y = (i16)(e->y8 >> 3);
        g_en_clip_y0 = g_en_y > g_en_view_y ? g_en_y : g_en_view_y;
        g_en_clip_y1 = g_en_y + ENEMY_HT < g_en_view_y + 160 ?
                  (i16)(g_en_y + ENEMY_HT) : (i16)(g_en_view_y + 160);
        if (g_en_clip_x0 >= g_en_clip_x1 || g_en_clip_y0 >= g_en_clip_y1) continue;
        g_en_start_byte = (u8)((g_en_clip_x0 - e->x) >> 1);
        g_en_byte_count = (u8)((g_en_clip_x1 - g_en_clip_x0) >> 1);
        g_en_start_row = (u8)(g_en_clip_y0 - g_en_y);
        g_en_row_count = (u8)(g_en_clip_y1 - g_en_clip_y0);
        if (!g_en_byte_count || !g_en_row_count) continue;
        s = en2_slot((i8)idx, page);
        if (s < 0) continue; // pool ple: segur

        // Seleccio de cela i flip dinamic amb cache de cela:
        {
            u8 is_aiming = (e->shoot_timer > (SHOOT_CYCLE_FRAMES - AIM_FRAMES));
            u8 step = (e->dead || sp->vx == 0 || e->shoot_timer || sp->base_cell == sp->aim_cell) ? 0 : (u8)((e->tick >> 2) & 1);
            u8 cell = (u8)(sp->base_cell + step);
            if (is_aiming) {
                if (sp->kind == 4 || sp->kind == 26) cell = sp->aim_cell;   // pose de tret
                else if (sp->kind == 17 || sp->kind == 21 || sp->kind == 23) cell = sp->throw_cell;
            }
            frame = en2_cell(cell, (u8)(e->dir < 0));
        }

        g_moving_dst = (u16)ring_address(page, g_en_clip_x0, g_en_clip_y0);
        s_slot_dst[(u8)s] = g_moving_dst;
        g_moving_background = BG_SLOT(s);
        g_moving_sprite = (u16)(frame + ((u16)g_en_start_row << 4) + (g_en_start_byte << 1));
        g_moving_span = g_en_byte_count;
        g_moving_rows = g_en_row_count;
        g_moving_spr_skip = (u8)(16 - (g_en_byte_count << 1));
        moving_blit_box();

        s_slot_span[(u8)s] = g_en_byte_count;
        s_slot_rows[(u8)s] = g_en_row_count;
    }

    // 2. Dibuixa projectil si esta actiu:
    if (s_proj.kind && !s_proj.drawn_row_count[page]) {
        g_en_clip_x0 = s_proj.x > g_en_view_x ? s_proj.x : g_en_view_x;
        g_en_clip_x1 = s_proj.x + 8 < g_en_view_x + 160 ? (i16)(s_proj.x + 8) : (i16)(g_en_view_x + 160);
        g_en_y = (i16)(s_proj.y8 >> 3);
        g_en_clip_y0 = g_en_y > g_en_view_y ? g_en_y : g_en_view_y;
        g_en_clip_y1 = g_en_y + s_proj.ht < g_en_view_y + 160 ? (i16)(g_en_y + s_proj.ht) : (i16)(g_en_view_y + 160);
        if (g_en_clip_x0 < g_en_clip_x1 && g_en_clip_y0 < g_en_clip_y1) {
            g_en_start_byte = (u8)((g_en_clip_x0 - s_proj.x) >> 1);
            g_en_byte_count = (u8)((g_en_clip_x1 - g_en_clip_x0) >> 1);
            g_en_start_row = (u8)(g_en_clip_y0 - g_en_y);
            g_en_row_count = (u8)(g_en_clip_y1 - g_en_clip_y0);
            if (g_en_byte_count && g_en_row_count) {
                // Cela 13: base + offset files projectil + 4 (centrat horitzontal 8 px Mode 0)
                const u8* frame = en2_cell(s_proj.cell, (u8)(s_proj.vx < 0))
                    + (((u16)s_proj.row_offset + g_en_start_row) << 4)
                    + 4 + (g_en_start_byte << 1);

                g_moving_dst = (u16)ring_address(page, g_en_clip_x0, g_en_clip_y0);
                s_proj.drawn_dst[page] = g_moving_dst;
                g_moving_background = (u16)s_proj_bg[page];
                g_moving_sprite = (u16)frame;
                g_moving_span = g_en_byte_count;
                g_moving_rows = g_en_row_count;
                g_moving_spr_skip = (u8)(16 - (g_en_byte_count << 1));
                moving_blit_box();

                s_proj.drawn_byte_count[page] = g_en_byte_count;
                s_proj.drawn_row_count[page] = g_en_row_count;
            }
        }
    }
}

static i8 en2_hit_box(i16 xmin, u8 xw, i16 ymin, i16 ymax, u8 use_he) {
    u8 i;
    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        u8 k, h;
        i16 ey;
        if (e->dead) continue;
        if ((u16)(e->x - xmin) >= (u16)xw) continue;
        k = sp->kind;
        if (k == 8) continue; // peix (decoracio DOS op1)
        if (use_he) {
            h = (k == 24) ? 10 : ((k == 25) ? 18 : ((k == 19) ? 16 : ((k == 4) ? 28 : 30)));
        } else {
            h = 16;
        }
        ey = (i16)(e->y8 >> 3);
        if ((i16)(ey + (ENEMY_HT - h)) < ymax && (i16)(ey + ENEMY_HT) >= ymin) {
            return (i8)i;
        }
    }
    return -1;
}

void en2_check_player_hit(void) {
    bc_r = 0;

    // 1. Projectil (bala, plat, ou):
    if (s_proj.kind) {
        if ((u16)(s_proj.x - (i16)bc_a + 8) < 24) {
            i16 proj_y = (i16)(s_proj.y8 >> 3);
            i16 jake_top = (u8)bc_c ? (i16)((i16)bc_b + 18) : (i16)((i16)bc_b + 4);
            i16 jake_bottom = (i16)((i16)bc_b + 32);
            i16 proj_bottom = (i16)(proj_y + s_proj.ht);
            if (proj_bottom > jake_top && proj_y < jake_bottom) {
                s_proj.kind = 0;
                bc_r = 1;
                return;
            }
        }
    }

    // 2. Walkers / Enemics (nomes els de classe 2: el peix es decoracio).
    if (en2_hit_box((i16)((i16)bc_a - 9), 19, (i16)((i16)bc_b + 4), (i16)((i16)bc_b + 30), 1) >= 0) {
        bc_r = 1;
    }
}

void en2_check_crate_hit(void) {
    i8 idx = en2_hit_box((i16)((i16)bc_a - 16), 32, (i16)bc_b, (i16)((i16)bc_b + 16), 1);
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

    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
    for (i = 0; i < ENEMY_N; i++, e++) {
        e->slot[0] = -1;
        e->slot[1] = -1;

        if (!e->dead && (bc_a || bc_b)) {
            g_en_dx = (i16)(e->x - (i16)bc_a);
            if ((u16)(g_en_dx + 72) < 144 && (u16)((e->y8 >> 3) - (i16)bc_b + 24) < 48) {
                e->dir = (g_en_dx >= 0) ? 1 : -1;
                e->x = (i16)((i16)bc_a + ((g_en_dx >= 0) ? 80 : -80));
            }
        }
    }
    s_proj.drawn_row_count[0] = 0;
    s_proj.drawn_row_count[1] = 0;
    s_proj.kind = 0;
}
