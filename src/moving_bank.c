// ============================================================
// moving_bank.c - Lògica d'objectes mòbils al Banc 5 (CP-2.2)
// ------------------------------------------------------------
// Aquest mòdul s'enllaça A PART a 0x6E00 (finestra 0x4000, Banc 5) i
// s'hi crida via call_banked() amb bloc de paràmetres resident.
// Regles de disciplina (CRÍTIQUES):
// - Mai assumeixis banc mapejat: Bank 5 garantit per call_banked a l'entrada.
// - Les crides residents que toquen bancs (level_get_tile_type,
//   render_tile_world) són autocontingudes; en tornar, C5 segueix.
// - REGLE D'OR (CP-2.2b, després d'un crash sistèmic): el codi bancat MAI
//   pot commutar a un ALTRE banc (ni tan sols temporalment amb restore):
//   la CPU continua llegint 0x4000-0x7FFF, i en canviar el propi codi
//   desapareix (s'executen dades -> salt salvatge -> reboot/congelat).
//   Només el codi CENTRAL pot commutar bancs. El codi bancat només pot
//   tocar el banc d'entrada (C5-noop via bank_set(C5) és segur: no desmapeja)
//   i memòria sempre visible (central, VRAM). draw/restore (necessitaven C7)
//   són residents a moving.c per aquest motiu.
// - Cap dada pròpia: tot l'estat és resident (visible sempre).
// - En sortir, ha de quedar C5 mapejat (call_banked restaura el previ).
// ============================================================

#include "cpctelera.h"
#include "bank.h"
#include "moving.h"

#define MAP_PTR  ((const u8*)0x4000)
#define MAP_MUT  ((u8*)0x4000)
#define TRIG_PTR ((const u8*)0x6400)

#define ELEVATOR_WAIT 33
// DOS ±2px/f@30Hz (60px/s) -> 2.375px/f@25Hz (59.4px/s, -1% invisible):
// patró de 8 [3,3,3,2,2,2,2,2] via (anim_tick&7)<3 (barat, sense % ni lib).
// ELEVATOR_OBJECT_H ara a moving.h (compartit amb el draw resident).
// Alçada de l'objecte 14 = sprite sencer: en Jake va amb els peus a y-14,
// 1:1 amb DOS (ypos - level_obj_h[7]=15 + 1). Amb 30 flotava 1 tile amunt
// als dos extrems sense que les parades (triggers 1:1 DOS) tinguessin res.
// ELEVATOR_SPR_HALF_W ara a moving.h (compartit amb el draw resident).

// Frames d'ascensor al Banc 7 (ELEV.BIN carregat a 0x78E0, 2x224 B).
#define ELEVATOR_FRAMES_BASE ((const u8*)0x78E0)
#define ELEVATOR_FRAME_SIZE  224

// Posicions inicials DOS (slots 19..23 Magasin). Només les usa init.
static const i16 s_bank_start_x[MAG_ELEVATOR_COUNT] = { 760, 808, 760, 808, 304 };
static const i16 s_bank_start_y[MAG_ELEVATOR_COUNT] = { 384, 464, 592, 736, 784 };
static const u8 s_bank_map_col[MAG_ELEVATOR_COUNT] = { 95, 101, 95, 101, 38 };

// Bloc de paràmetres resident (moving.c) per crides amb args/retorn.
extern u16 bc_a, bc_b, bc_c, bc_d, bc_e;
extern i16 bc_r;

extern u8 level_get_tile_type(u16 col, u16 row);
extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);

void moving_bank_init(void) {
    u8 i;

    s_conveyor_phase = 0;
    s_conveyor_tick = 0;
    s_page_conveyor_phase[0] = s_page_conveyor_phase[1] = 0xFF;

    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
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
        e->drawn_frame[0] = e->drawn_frame[1] = 0;
        e->drawn_start_byte[0] = e->drawn_start_byte[1] = 0;
        e->drawn_byte_count[0] = e->drawn_byte_count[1] = 0;
        e->drawn_start_row[0] = e->drawn_start_row[1] = 0;
        e->drawn_row_count[0] = e->drawn_row_count[1] = 0;
        e->drawn_x[0] = e->drawn_x[1] = 0;
        e->drawn_y[0] = e->drawn_y[1] = 0;
    }
}

void moving_bank_update(void) {
    u8 i;
    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        MovingElevator* e = &g_mag_elevators[i];
        u16 row;

        e->delta_y = 0;
        e->frame = 0;

        if (e->wait < ELEVATOR_WAIT) {
            e->wait++;
            continue;
        }

        row = (u16)(e->y >> 4);
        // Pas 2/3 segons patró (mitjana 2.375px/f = DOS 60px/s a 25Hz).
        {
            i16 step = (((e->anim_tick & 7) < 3) ? 3 : 2);
            if (e->direction < 0) {
                if (row >= 4 && level_get_tile_type(e->map_col, (u16)(row - 4)) == 10) {
                    e->direction = 1;
                    e->wait = 1;
                    continue;
                }
                e->y = (i16)(e->y - step);
                e->delta_y = (i16)-step;
            } else {
                if (level_get_tile_type(e->map_col, (u16)(row + 1)) == 10) {
                    e->direction = -1;
                    e->wait = 1;
                    continue;
                }
                e->y = (i16)(e->y + step);
                e->delta_y = step;
            }
        }

        e->frame = (u8)((e->anim_tick >> 2) & 1);
        e->anim_tick++;
    }

    if (++s_conveyor_tick >= 4) {
        u8 b, c;
        s_conveyor_tick = 0;
        if (++s_conveyor_phase >= 3) {
            s_conveyor_phase = 0;
        }
        // C5 garantit per call_banked a l'entrada (sense restore: el
        // call_banked restaura el previ en sortir).
        cpc_bank_set(0xC5);
        for (b = 0; b < 4; b++) {
            u8 body_tile   = (s_belts[b].op == 27) ? s_belt_right_body[s_conveyor_phase]
                                                   : s_belt_left_body[s_conveyor_phase];
            u8 roller_tile = (s_belts[b].op == 27) ? s_belt_right_roller[s_conveyor_phase]
                                                   : s_belt_left_roller[s_conveyor_phase];
            u16 row_off = (u16)s_belts[b].row << 7;
            MAP_MUT[row_off + s_belts[b].col_start] = roller_tile;
            for (c = (u8)(s_belts[b].col_start + 1); c < s_belts[b].col_end; c++) {
                MAP_MUT[row_off + c] = body_tile;
            }
            MAP_MUT[row_off + s_belts[b].col_end] = roller_tile;
        }
    }
}

// NOTA CP-2.2b: moving_bank_restore/moving_bank_draw VIVIEN aquí fins que
// es va demostrar que el codi bancat MAI pot niuar a un altre banc (la CPU
// continua llegint 0x4000-0x7FFF: en canviar, el propi codi desapareix).
// Només el codi CENTRAL pot commutar bancs. S'han traslladat a moving.c
// (residents, amb els mateixos bank_set(C7) segurs). Slots 1-2 de la taula
// queden sense ús (es conserven per estabilitat d'adreces).

void moving_bank_conveyor(void) {
    u8 page = (u8)bc_a;
    u16 cam_x4 = bc_b;
    u16 cam_row = bc_c;
    u8 b, c;
    if (page > 1 || s_page_conveyor_phase[page] == s_conveyor_phase) return;

    for (b = 0; b < 4; b++) {
        u16 belt_subrow = (u16)s_belts[b].row << 1;
        if (belt_subrow + 2 <= cam_row || belt_subrow >= cam_row + 20) continue;

        {
            u8 body_tile   = (s_belts[b].op == 27) ? s_belt_right_body[s_conveyor_phase]
                                                   : s_belt_left_body[s_conveyor_phase];
            u8 roller_tile = (s_belts[b].op == 27) ? s_belt_right_roller[s_conveyor_phase]
                                                   : s_belt_left_roller[s_conveyor_phase];
            for (c = s_belts[b].col_start; c <= s_belts[b].col_end; c++) {
                u16 char_x = (u16)c << 1;
                if (char_x + 2 <= cam_x4 || char_x >= cam_x4 + 40) continue;
                u8 tile = (c == s_belts[b].col_start || c == s_belts[b].col_end) ? roller_tile : body_tile;
                render_tile_world(tile, c, s_belts[b].row, cam_x4, cam_row);
            }
        }
    }
    s_page_conveyor_phase[page] = s_conveyor_phase;
}

void moving_bank_push(void) {
    u16 col0 = bc_a;
    u16 col1 = bc_b;
    u16 row = bc_c;
    u8 op0, op1, tile;
    u16 off;
    i8 direction = 0;

    if (row >= 72 || col0 >= 128 || col1 >= 128) { bc_r = 0; return; }

    // C5 garantit per call_banked a l'entrada: llegir directament, sense
    // commutar (un restore cec a C0 trencaria el retorn al banc!).
    tile = MAP_PTR[(row << 7) + col0];
    off = (((u16)tile) << 3) + (((u16)tile) << 1);
    op0 = TRIG_PTR[off + 2];
    tile = MAP_PTR[(row << 7) + col1];
    off = (((u16)tile) << 3) + (((u16)tile) << 1);
    op1 = TRIG_PTR[off + 2];

    if (op0 == 27 || op1 == 27) direction++;
    if (op0 == 28 || op1 == 28) direction--;
    bc_r = (i16)(direction * 16);  // Original unk1C = +/-4 px/f; CPC x is 2x wide.
}

void moving_bank_find(void) {
    i16 player_x = (i16)bc_a;
    i16 previous_feet = (i16)bc_b;
    i16 current_feet = (i16)bc_c;
    i16 vy = (i16)bc_d;
    i16* player_top = (i16*)bc_e;
    u8 i;
    if (vy < 0) { bc_r = -1; return; }

    for (i = 0; i < MAG_ELEVATOR_COUNT; i++) {
        const MovingElevator* e = &g_mag_elevators[i];
        i16 left = (i16)(e->center_x - ELEVATOR_HALF_W);
        i16 right = (i16)(left + ELEVATOR_WIDTH_PX);
        i16 surface = (i16)(e->y - ELEVATOR_OBJECT_H);
        // Overlap EXACTE amb l'ample d'en Jake (PW=16): ha de coincidir amb el
        // test de persistència de main.c (px+PW). Amb +24 hi havia una franja
        // de 8px on aterrava 1 sol frame (flaix idle en caigudes del shaft).
        if ((i16)(player_x + 16) <= left || player_x >= right) continue;
        if (previous_feet <= (i16)(surface + 8) && current_feet >= surface) {
            *player_top = (i16)(surface - 30);
            bc_r = (i16)(i8)i;
            return;
        }
    }
    bc_r = -1;
}
