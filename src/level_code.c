// ============================================================
// level_code.c - Els ASCENSORS del nivell, al Banc 1 (C1)
// ------------------------------------------------------------
// Els ascensors son un objecte DEL NIVELL (el DOS nomes els te al nivell 1:
// el tipus 7 de level_objtypes), aixi que el seu codi no ha de viure al
// Bloc 0 resident, que ha de ser el motor generic.
//
// Aquest module s'enllaça dins el Banc 1, al mateix paquet que la musica,
// el HUD i les habitacions:
//   0x5000 musica, 0x6000 HUD, 0x6400 habitacions, 0x6800 portes,
//   0x6860 taula de restauracio de les habitacions, 0x6900 parametres,
//   0x6934 AQUEST CODI, 0x6E20 frame de l'ascensor, 0x7000 buffers de fons.
//
// COMPATIBILITAT: un codi bancat no pot commutar de banc (en commutar, el
// seu propi codi a 0x4000-0x7FFF desapareix). Aquest module, per tant, NO
// fa bank_set(): el Banc 1 ja ha de estar mapejat. Pot cridar codi RESIDENT
// (RAM baixa 0x0100-0x3880, sempre visible) i llegir els seus propis datos.
// ============================================================
#include "cpctelera.h"
#include "bank.h"
#include "moving.h"
#include "sprite.h"
#include "level_params.h"

// --- Dades del mateix Banc 1 --------------------------------------------
#define LC_ELEV_FRAMES  ((const u8*)0x6E20)   // ELEV.BIN: frame unic (14 files)
#define LC_ELEV_BG      ((u8*)0x7000)         // buffers de fons (2 pagines x 5)

// --- Codi resident cridat des d'aqui (declarat a moving.h) --------------

// Globals del resident (RAM baixa: visibles des de qualsevol banc)
extern u16 g_moving_dst;
extern u16 g_moving_background;
extern u16 g_moving_sprite;
extern u8  g_moving_span;
extern u8  g_moving_rows;
extern u8  g_moving_spr_skip;
extern MovingElevator g_mag_elevators[MAG_MOVER_COUNT];

// Destinacio VRAM dels blits (aqui viu: el draw i el restore son els seus
// unics usuaris, i el Banc 1 no pot veure la _DATA del resident).
static u16 s_elev_dst[2][MAG_ELEVATOR_COUNT];
extern LevelParams s_lv;          // parametres del nivell (RAM baixa)

#define LC_ELEV_BG_SIZE (ELEVATOR_W_BYTES * ELEVATOR_H)

// ============================================================
// void lc_elev_restore_c(void)
//   Restaura el fons dels ascensors (LIFO, com els enemics).
//   bc_a = page
// ============================================================
void lc_elev_restore_c(void) {
    u8 page = (u8)bc_a;
    u8 i;
    if (page > 1) return;
    for (i = MAG_ELEVATOR_COUNT; i > 0; i--) {
        u8 idx = (u8)(i - 1);
        MovingElevator* e = &g_mag_elevators[idx];
        if (!e->drawn[page]) continue;
        g_moving_dst = s_elev_dst[page][idx];
        g_moving_background = (u16)(LC_ELEV_BG + (u16)idx * 2u * LC_ELEV_BG_SIZE + (u16)page * LC_ELEV_BG_SIZE);
        g_moving_span = e->drawn_byte_count[page];
        g_moving_rows = e->drawn_row_count[page];
        moving_restore_box();
        e->drawn[page] = 0;
    }
}

// ============================================================
// void lc_elev_draw_c(void)
//   Dibuixa els ascensors visibles al backbuffer.
//   bc_a = page, bc_b = cam_x4, bc_c = cam_row
// ============================================================
void lc_elev_draw_c(void) {
    u8 page = (u8)bc_a;
    u16 cam_x4 = bc_b;
    u16 cam_row = bc_c;
    u8 i;
    i16 view_x = (i16)(cam_x4 << 2);
    i16 view_y = (i16)(cam_row << 3);
    if (page > 1) return;

    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        i16 world_x, world_y, clip_x0, clip_x1, clip_y0, clip_y1;
        u8 start_byte, byte_count, start_row, row_count;
        if (i >= s_lv.elev_count) break;   // el nivell diu quants n'hi ha
        if (e->drawn[page]) continue;
        world_x = (i16)(e->center_x - ELEVATOR_SPR_HALF_W);
        world_y = (i16)(e->y - ELEVATOR_OBJECT_H);
        clip_x0 = world_x > view_x ? world_x : view_x;
        clip_x1 = world_x + ELEVATOR_SPR_WIDTH_PX < view_x + 160 ?
                  (i16)(world_x + ELEVATOR_SPR_WIDTH_PX) : (i16)(view_x + 160);
        clip_y0 = world_y > view_y ? world_y : view_y;
        clip_y1 = world_y + ELEVATOR_H < view_y + 160 ?
                  (i16)(world_y + ELEVATOR_H) : (i16)(view_y + 160);
        if (clip_x0 >= clip_x1 || clip_y0 >= clip_y1) continue;

        start_byte = (u8)((clip_x0 - world_x) >> 1);
        byte_count = (u8)((clip_x1 - clip_x0) >> 1);
        start_row = (u8)(clip_y0 - world_y);
        row_count = (u8)(clip_y1 - clip_y0);
        if (!byte_count || !row_count) continue;

        g_moving_dst = (u16)ring_address(page, clip_x0, clip_y0);
        s_elev_dst[page][i] = g_moving_dst;
        g_moving_background = (u16)(LC_ELEV_BG + (u16)i * 2u * LC_ELEV_BG_SIZE + (u16)page * LC_ELEV_BG_SIZE);
        g_moving_sprite = (u16)(LC_ELEV_FRAMES + ((u16)start_row << 4) + (start_byte << 1));
        g_moving_span = byte_count;
        g_moving_rows = row_count;
        g_moving_spr_skip = (u8)(16 - (byte_count << 1));
        moving_blit_box();

        e->drawn_byte_count[page] = byte_count;
        e->drawn_row_count[page] = row_count;
        e->drawn[page] = 1;
    }
}
