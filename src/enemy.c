// ============================================================
// enemy.c - Walkers del nivell 1 (kinds DOS 8/15/19 -> op1), BANC C6
// ------------------------------------------------------------
// S'enllaÃ§a a 0x5C00 (darrere els frames a 0x4000) amb taula de
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
    i8 dir;
    i16 vx;
    i16 vy;
    u8 kind;        // 0=inactiu, 4=bala, 9=plat, 10=ou
    u8 ht;          // alÃ§ada (bala=6, plat=11, ou=13)
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
static u16 s_slot_dst[BG_SLOTS];
static u8 s_slot_span[BG_SLOTS];
static u8 s_slot_rows[BG_SLOTS];

// Buffer dinÃ mic de flip sota demanda per a enemics encarats a l'esquerra:
static u8 s_flip_buffer[ENEMY_FRAME_SIZE];
static u8 s_flipped_cell;

extern u8 tile_type(u16 col, u16 row);
extern u8 tile_flags(u16 col, u16 row);
extern u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch);

// Rutines rÃ pides en ASM per flipejar la cela a s_flip_buffer (engine/enemy_table.s):
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
#define AIM_FRAMES         12   // duracio de la pose (~0,5 s a 25 Hz; DOS la soste 6-10 passos)
#define ENEMY_CELL_TABLE   ((const u8*)0x4000)
#define ENEMY_CACHE_BASE   ((u8*)0x5000)
#define ENEMY_CACHE_SLOTS  4
#define ENEMY_CACHE_WHO    ((u8*)0x5800)
#define ENEMY_CACHE_NEXT   (*(u8*)0x5810)
// comptador real resident (diagnostic; es pot llegir des de l'emu)

static const u8* en2_cell(u8 cell) {
    u8 s;
    if (cell >= ENEMY_CELLS) cell = 0;
    for (s = 0; s < ENEMY_CACHE_SLOTS; s++) {
        if (ENEMY_CACHE_WHO[s] == cell)
            return ENEMY_CACHE_BASE + ((u16)s << 9);
    }
    s = ENEMY_CACHE_NEXT;
    ENEMY_CACHE_NEXT = (u8)((s + 1) & (ENEMY_CACHE_SLOTS - 1));
    zx0_decompress((const void*)(*(const u16*)
                   (ENEMY_CELL_TABLE + ((u16)cell << 1))),
                   ENEMY_CACHE_BASE + ((u16)s << 9));
    ENEMY_CACHE_WHO[s] = cell;
    g_enemy_decomp_cnt++;
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
#if LEVEL_ID == 0
static const Spawn s_spawn[ENEMY_N] = {
    // 3 Iaies (kind 15, DOS op0): slots 1, 2, 5
    { 456, 1088 << 3, 15, 36,  1 , 14, 15 }, //  0: Iaia 1 (PB Store)
    { 624, 1088 << 3, 15, 36,  1 , 14, 15 }, //  1: Iaia 2 (PB Bar)
    { 592,  960 << 3, 15, 36,  1 , 14, 15 }, //  2: Iaia 3 (1r pis botiga)

    // 5 Policies (kind 4, DOS op2): slots 3, 0, 7, 29, 18
    { 744, 1088 << 3,  4, 24,  3 , 14, 15 }, //  3: Policia 1 (PB dreta botigues) [slot 3]
    { 280, 1088 << 3,  4, 24,  3 , 14, 15 }, //  4: Policia 2 (carrer, PB Store) [slot 0]
                                   //     Abans hi havia (816,784) vx=0, fila sense
                                   //     parell a staticres.c: on_ground=1 inicial ->
                                   //     no queia mai i pivotava al replÃ  d'ascensors.
    { 272,  960 << 3,  4, 24,  3 , 14, 15 }, //  5: Policia 3 (1r pis sota escala) [slot 7]
    { 768,  496 << 3,  4,  0,  3 , 14, 15 }, //  6: Policia 4 (2n pis replÃ  ascensors) [slot 29]
    { 688,  320 << 3,  4, 24,  3 , 14, 15 }, //  7: Policia 5 (3r pis) [slot 18]

    // 2 Peixos (kind 8, DOS op0): slots 24 i 12 dels 4 oficials (11/12/24/25)
    { 428,  480 << 3,  8, 16,  0 , 14, 15 }, //  8: Peix 1 (Peixera 1) [slot 24]
    { 548,  496 << 3,  8, 16,  0 , 14, 15 }, //  9: Peix 2 (Peixera 2) [slot 12]

    // 3 Ocells (kind 19, DOS op8): slots 26, 27, 28
    { 232,   64 << 3, 19, 32,  5 , 14, 15 }, // 10: Ocell 1 (NÃºvols esquerra) [slot 26]
    { 512,   48 << 3, 19, 32,  5 , 14, 15 }, // 11: Ocell 2 (NÃºvols centre) [slot 27]
    { 808,   64 << 3, 19, 32,  5 , 14, 15 }, // 12: Ocell 3 (NÃºvols dreta) [slot 28]

    // 2 Grangers (kind 18, DOS op1): slots 16, 17
    { 352,  320 << 3, 18, 24,  7 , 14, 15 }, // 13: Granger 1 (escala vinils esq) [slot 16]
    { 496,  320 << 3, 18, 24,  7 , 14, 15 }, // 14: Granger 2 (escala vinils dreta) [slot 17]

    // 1 Cambrera (kind 17, DOS op10): slot 10
    {  72,  592 << 3, 17, 20,  9 , 14, 15 }, // 15: Cambrera (Bar/Restaurant) [slot 10]

    // 4 Rockers (kind 20, DOS op1): slots 6, 15, 9, 13
    // (els slots 4 i 8 son dins d'habitacions, files 80: no a l'exterior)
    { 432,  960 << 3, 20, 24, 11 , 14, 15 }, // 16: Rocker 1 (1r pis davant botiga) [slot 6]
    { 624,  768 << 3, 20, 24, 11 , 14, 15 }, // 17: Rocker 2 (2n pis dreta) [slot 15]
    {  72,  464 << 3, 20, 24, 11 , 14, 15 }, // 18: Rocker 3 (prop Bar/Restaurant) [slot 9]
    { 584,  720 << 3, 20, 24, 11 , 14, 15 }, // 19: Rocker 4 (2n pis) [slot 13]
    { -1000, 0, 19, 0, 5, 14, 15 }, // inactiu (ENEMY_N=22)
    { -1000, 0, 19, 0, 5, 14, 15 }, // inactiu (ENEMY_N=22)
};
#else
#include "enemy_spawn.h"
#endif


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
    for (i = 0; i < 16; i++) ENEMY_CACHE_WHO[i] = 0xFF;
    ENEMY_CACHE_NEXT = 0;
    g_enemy_decomp_cnt = 0;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        e->x = sp->x;
        e->y8 = sp->y8;
        e->dir = (sp->vx == 0) ? -1 : 1;
        e->vy = 0;
        // El tipus 22 (estatic, tipus 11 de L2) ha de CAURE al terra: no neix
        // flotant com els altres estatics (vx == 0).
        e->on_ground = (sp->kind == 8 || sp->kind == 19 || sp->kind == 17 ||
                        (sp->vx == 0 && sp->kind != 22)) ? 1 : 0;
        e->tick = 0;
        e->shoot_timer = 0;
        e->dead = 0;
        e->slot[0] = -1;
        e->slot[1] = -1;
    }
    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
    s_proj.kind = 0;
    s_proj.cooldown = 0;
    s_proj.drawn_row_count[0] = 0;
    s_proj.drawn_row_count[1] = 0;
}

// Y: gravetat + snap al terra (mateix que en Jake, alcada 32). Retorna la
// nova y en pixels. Es treu del bucle per poder-lo reutilitzar pels enemics
// estatics (tipus 11 de L2), que no es mouen en X pero si que cauen.
static i16 en2_fall(Enemy* e, i16 y) {
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
        if (trow < LEVEL_MAP_H) {
            // Columna del CENTRE (xpos16 a DOS), no les del cos.
            u16 cc = (u16)((e->x + 8) >> 3);
            i16 surf = (i16)(trow << 4);
            if (is_floor_solid(cc, trow, 0, 0) &&
                prev_feet <= (surf + 8) && feet >= surf) {
                e->y8 = (i16)((surf - ENEMY_HT) << 3);
                e->vy = 0;
                e->on_ground = 1;
            }
        }
    } else if ((e->tick & 3) == 0) {
        u8 trow = (u8)((y + ENEMY_HT) >> 4);
        if (trow < LEVEL_MAP_H) {
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
    i16 view_x = (i16)(g_cam_x4 << 2);
    i16 view_y = (i16)(g_cam_row << 3);
    i16 jake_x = (i16)(s_px8 >> 3);
    i16 jake_y = (i16)(s_py8 >> 3);

    Enemy* e = s_enemies;
    const Spawn* sp = s_spawn;
    for (i = 0; i < ENEMY_N; i++, e++, sp++) {
        i16 y;
        i16 nx, dx;

        if (sp->x < (i16)(view_x - 78) || sp->x > (i16)(view_x + 222) ||
            sp->y8 < (i16)((view_y - 132) << 3) || sp->y8 > (i16)((view_y + 318) << 3))
            continue;

        if (e->dead) {
            if (e->dead == 1) {
                e->x = (i16)(e->x + (e->dir > 0 ? 3 : -3));
                e->vy = (i16)(e->vy + ENEMY_GRAV);
                e->y8 = (i16)(e->y8 + e->vy);
                if ((i16)(e->y8 >> 3) > (view_y + 180)) {
                    e->dead = 2;
                }
            }
            continue;
        }

        y = (i16)(e->y8 >> 3);

        if (sp->kind == 4 || sp->kind == 17 || sp->kind == 21) {
            // 1:1 DOS object_func_op2 (policia), op10 (cambrera) i op7
            // (llançador de L2). Distancies de DOS (level.c
            // do_level_update_object_bounds):
            //   player_xdist = centre_jugador - centre_objecte
            //   player_ydist = peus_jugador - peus_objecte
            //   policia  (op2): player_ydist <= 20 && |player_xdist| < 80
            //   cambrera (op10): player_ydist <= 10 && |player_xdist| < 160
            //   llançador(op7): player_ydist <= 10 && |player_xdist| < 80
            // (el DOS no posa limit inferior a ydist; direction_ud > -30 es
            // sempre cert per a un walker de terra -> s'omet.)
            i16 dy = jake_y - y;               // cap-cap = peus-peus (mateixa alcada)
            i16 dx_jake = jake_x - e->x;
            i16 abs_dx = (dx_jake >= 0) ? dx_jake : -dx_jake;
            u8 is_cop = (sp->kind == 4);
            u8 is_throw = (sp->kind == 21);
            i16 max_y = is_cop ? 20 : 10;
            i16 max_x = is_cop ? 80 : (is_throw ? 80 : 160);
            if (dy <= max_y && abs_dx < max_x) {
                e->dir = (dx_jake >= 0) ? 1 : -1;
                // 1:1 DOS: en rang de tir es PARA (direction_lr = 0) i fa la
                // pose d'accio; el projectil es crea a l'inici de la sequencia.
                if (!e->shoot_timer) e->shoot_timer = AIM_FRAMES;
                if (!s_proj.kind && !s_proj.cooldown) {
                    // 1:1 DOS do_level_update_projectile (cas default, que es
                    // el dels tipus 4 i 17):
                    //   xpos = centre_objecte +- 32 DOS px -> +-16 CPC px
                    //   ypos = obj_ypos - 18   (ATENCIO: al DOS ypos es la
                    //     BASE de la caixa, no el cap). La caixa del projectil
                    //     es [ypos-10, ypos] = [peus-28, peus-18].
                    // Escalat: l'ample DOS->CPC es 2:1 pero l'ALCADA es 1:1.
                    // La nostra bala fa 6 px i aqui `s_proj.y8>>3` es el CAP,
                    // aixi que per deixar la BASE a peus-18: cap+6 = y+32-18
                    //  ->  sy = y + 8.
                    // Amb aixo: caixa [y+8, y+14]; el Jake AJUPIT (top py+18)
                    // la veu passar de llarg (14 <= 18) i el Jake dret (top
                    // py+4) la rep.
                    i16 sx = (i16)(e->x + 8 + ((e->dir > 0) ? 16 : -16));
                    i16 sy = (i16)(y + 8);
                    i16 sgn = (e->dir > 0) ? 1 : -1;
                    // El llançador (op7) al DOS llança l'objecte "grab_type 6"
                    // (sprite que encara no tenim); fem servir la bala, que es
                    // la mateixa arithmetica (cas default de
                    // do_level_update_projectile).
                    en2_spawn_proj(is_cop ? 4 : 9, is_cop ? 6 : 11, is_cop ? 13 : 19,
                                   sx, sy, (i16)(sgn * 64), 0, 24);
                }
            }
        }

        if (e->shoot_timer) {
            e->shoot_timer--;
            dx = 0;
            nx = e->x;
        } else {
            dx = (i16)(sp->vx >> 3);
            if (e->dir < 0) dx = (i16)-dx;
            nx = (i16)(e->x + dx);
        }

        if (sp->vx == 0) {
            // EstÃ tic (ex: policia replÃ  ascensors): gira encarant Jake o periÃ²dicament
            i16 dy = jake_y - y;
            if (dy >= -24 && dy <= 32) {
                i16 dx_jake = jake_x - e->x;
                if (dx_jake < -16) e->dir = -1;
                else if (dx_jake > 16) e->dir = 1;
            } else if ((e->tick & 127) == 0) {
                e->dir = (i8)-e->dir;
            }
        } else if (sp->kind == 8 || sp->kind == 19) {
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
// Tiles: DOS mira SEMPRE la columna del centre (xpos16), mai les
            // del cos. En CPC el centre es x+8 (mitja amplada de 16 px).
            //   penya-segat (op0/op8): tile_type==1 (aire) a centre+-2,
            //     a la fila de peus i la de sobre.
            //   paret (fixup_xpos16): flags bit 1/2 a (nx+-4)>>3, files
            //     peus-1 i peus-2 (unk2E 1/2). NO la fila de peus: al
            //     L1 les rajoles del terra (op20) tenen flags=3 a tot
            //     arreu i hi farien girar sempre (pivot en punt fixe).
            {
                u8 frow = (u8)((y + ENEMY_HT) >> 4);
                u8 brow = (u8)((y + ENEMY_HT - 1) >> 4);
                u8 c2row = (u8)((y + ENEMY_HT - 2) >> 4);
                u16 ccol = (u16)((e->x + 8) >> 3);          // centre = xpos16
                u16 pcol = (u16)(ccol + (e->dir > 0 ? 2 : -2));
                // Vora de davant de l'sprite (16 px): no nomes un punt interior.
                // Amb +12/+2 el cos s'encastava 2-3 px dins les parets i podia
                // travessar oques estretes (reixat de L3).
                u16 acol = (u16)((nx + (e->dir > 0 ? ENEMY_W - 1 : 0)) >> 3);
                u8 bit = (u8)(e->dir > 0 ? 1 : 2);
                // op7 (llançador de L2): al DOS gira quan el tile DAVANT es
                // de tipus 12 (no pas aire com a op0/op8).
                u8 hit12 = (sp->kind == 21) &&
                    (tile_type(pcol, frow) == 12 || tile_type(pcol, brow) == 12);
                // Parets per op de plataforma (is_floor_solid amb vy<0): el
                // cos sencer (cap, mig i peus-1/peus-2) no pot entrar en un
                // tile solid, tant si el flag de paret es 0 com si no.
                u8 hrow = (u8)((y + 8) >> 4);
                u8 solid_side = is_floor_solid(acol, brow, -1, 0) ||
                    is_floor_solid(acol, c2row, -1, 0) ||
                    is_floor_solid(acol, hrow, -1, 0);
                if (hit12 || tile_type(pcol, frow) == 1 || tile_type(pcol, brow) == 1 ||
                    solid_side ||
                    (tile_flags(acol, brow) & bit) ||
                    (tile_flags(acol, c2row) & bit)) {
e->dir = (i8)-e->dir;   // penya-segat o paret (DOS op0/op8)
                } else {
                    e->x = nx;
                }
            }
            // Y: gravetat + snap (mateix que en Jake, alcada 32)
            y = en2_fall(e, y);
        }

        // Tipus 11 de L2: op7 NO te case al switch del DOS (default) -> l'objecte
        // no es mou ni mira el jugador, pero ha de caure al terra (gravetat).
        if (sp->kind == 22) {
            y = en2_fall(e, y);
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
            }
        }

        e->tick++;
    }

    // ActualitzaciÃ³ del projectil actiu:
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
        if (e->dead == 2 || e->slot[page] >= 0) continue; // eliminat o ja dibuixat
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
        if (!byte_count || !row_count) continue;

        // SelecciÃ³ de cela i flip dinÃ mic amb cache de cela:
        {
            u8 step = (e->dead || sp->kind == 8 || sp->vx == 0) ? 0 : (u8)((e->tick >> 2) & 1);
            u8 cell = (u8)(sp->base_cell + step);
            if (e->shoot_timer) {
                if (sp->kind == 4) cell = sp->aim_cell;              // pose de tret
                else if (sp->kind == 17 || sp->kind == 21) cell = sp->throw_cell;  // llançament
            }
            const u8* src = en2_cell(cell);
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
        s_slot_dst[(u8)s] = g_moving_dst;
        g_moving_background = BG_SLOT(s);
        g_moving_sprite = (u16)(frame + ((u16)start_row << 4) + (start_byte << 1));
        g_moving_span = byte_count;
        g_moving_rows = row_count;
        g_moving_spr_skip = (u8)(16 - (byte_count << 1));
        moving_blit_box();

        s_slot_span[(u8)s] = byte_count;
        s_slot_rows[(u8)s] = row_count;
    }

    // 2. Dibuixa projectil si estÃ  actiu:
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
            if (byte_count && row_count) {
                // Cela 13: base + offset files projectil + 4 (centrat horitzontal 8 px Mode 0)
                const u8* frame;
                if (s_proj.vx < 0) {
                    if (s_flipped_cell != 13) {
                        en2_flip_cell(en2_cell(13), s_flip_buffer);
                        s_flipped_cell = 13;
                    }
                    frame = s_flip_buffer + (((u16)s_proj.row_offset + start_row) << 4) + 4 + (start_byte << 1);
                } else {
                    frame = en2_cell(13) + (((u16)s_proj.row_offset + start_row) << 4) + 4 + (start_byte << 1);
                }

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
}

// 1:1 DOS level_obj_type[] (staticres.c): 0 = sense colisio, 1 = bonus,
// 2 = fa mal. Dels kinds que fem servir, NOMES el peix (kind 8) es classe 0:
// al DOS es decoracio pura (op1, anims locals 2/14 que son identiques) i no
// pot tocar ni Jake ni la caixa. La resta de walkers son classe 2.
static u8 en2_collide_class(u8 kind) {
    return (kind == 8) ? 0 : 2;
}

void en2_check_player_hit(void) {
    i16 px = (i16)bc_a;
    i16 py = (i16)bc_b;
    u8 crouch = (u8)bc_c;
    u8 i;
    Enemy* e;

    bc_r = 0;

    // 1. Projectil (bala, plat, ou):
    if (s_proj.kind) {
        if ((u16)(s_proj.x - px + 6) < 14) {
            i16 proj_y = (i16)(s_proj.y8 >> 3);
            i16 jake_top = crouch ? (i16)(py + 18) : (i16)(py + 4);
            i16 jake_bottom = (i16)(py + 32);
            i16 proj_bottom = (i16)(proj_y + s_proj.ht);
            if (proj_bottom > jake_top && proj_y < jake_bottom) {
                s_proj.kind = 0;
                bc_r = 1;
                return;
            }
        }
    }

    // 2. Walkers / Enemics (nomes els de classe 2: el peix es decoracio):
    e = s_enemies;
    for (i = 0; i < ENEMY_N; i++, e++) {
        if (e->dead) continue;
        if (en2_collide_class(s_spawn[i].kind) != 2) continue;
        if ((u16)(e->x - px + 6) < 16 &&
            (u16)((e->y8 >> 3) - py + 24) < 50) {
            bc_r = 1;
            return;
        }
    }
}

void en2_check_crate_hit(void) {
    i16 cx = (i16)bc_a;
    i16 cy = (i16)bc_b;
    i16 cvx = (i16)bc_c;
    u8 i;
    Enemy* e = s_enemies;

    bc_r = 0;
    for (i = 0; i < ENEMY_N; i++, e++) {
        if (e->dead) continue;
        if (en2_collide_class(s_spawn[i].kind) != 2) continue;
        if ((u16)(e->x - cx + 6) < 20 &&
            (u16)((e->y8 >> 3) - cy + 12) < 36) {
            e->dead = 1;
            e->dir = (cvx > 0) ? 1 : -1;
            e->vy = -48; // Impuls vertical amunt 1:1 DOS yfriction=12 (6 px/frame)
            e->on_ground = 0;
            bc_r = 1;
            return;
        }
    }
}

void en2_room_exit(void) {
    i16 px = (i16)bc_a;
    i16 py = (i16)bc_b;
    u8 i;
    Enemy* e = s_enemies;

    for (i = 0; i < BG_SLOTS; i++) s_bg_owner[i] = -1;
    for (i = 0; i < ENEMY_N; i++, e++) {
        e->slot[0] = -1;
        e->slot[1] = -1;

        if (!e->dead && (px || py)) {
            i16 dx = (i16)(e->x - px);
            if ((u16)(dx + 72) < 144 && (u16)((e->y8 >> 3) - py + 24) < 48) {
                e->dir = (dx >= 0) ? 1 : -1;
                e->x = (i16)(px + ((dx >= 0) ? 80 : -80));
            }
        }
    }
    s_proj.drawn_row_count[0] = 0;
    s_proj.drawn_row_count[1] = 0;
    s_proj.kind = 0;
}


