#ifndef LEVEL_PARAMS_H
#define LEVEL_PARAMS_H

#include "cpctelera.h"

// ============================================================
// Parametres del NIVELL (runtime)
// ------------------------------------------------------------
// Tot el que es del nivell (geometria del mapa, de les habitacions, tiles
// dels items, posicio inicial, checkpoint, parametres de camera) llegeix
// el resident del PAQUET del nivell (Banc C1:0x6900) en carregar: el Bloc 0
// no ha de tenir cap constant del nivell 1 compilada.
//
// El packer els emit a assets/bbdata/LEVELPARM<n>.BIN i el build els
// encosta dins del paquet; el resident en fa un memcpy sencer al bloc
// s_lv i hi accedeix com a camps (cap cost de codi extra).
// ============================================================

typedef struct {
    u8  magic;
    u8  version;
    u8  room_count;
    u8  room_cols;
    u8  room_rows;
    u8  room_row0;
    u8  room_floor_row;
    u8  room_total_cols;
    u8  room_cam_row;
    u8  tile_vinyl;
    u8  tile_instr;
    u8  tile_empty;
    u8  elev_count;
    u8  level_id;
    u16 room_rowoff[10];// offsets de fila dins el mapa de les habitacions
    i16 start_px;
    i16 start_py;
    i16 cam0_x4;
    i16 cam0_row;
    i16 chk_px;
    i16 chk_py;
    i16 chk_cam_x4;
    i16 chk_cam_row;
    u16 max_cam_row;
    // --- v2 (Fase 3 del pla universal): geometria i offsets dels blocs ---
    u8  map_w;          // ample visible (columnes)
    u8  map_h;          // alcada visible (files)
    u8  map_rows;       // files reals del mapa (amb el bloc de sales)
    u8  door_count;     // nombre de portes
    u16 rooms_off;      // adreca del bloc de sales dins el seu banc
    u16 doors_off;      // adreca de la taula de portes (C1)
    u16 restore_off;    // adreca de la taula de restauracio de sales (C1)
    // Valors derivats (precalculats al paquet: el resident no fa matematiques)
    u16 map_w_px;       // map_w * 8
    u16 map_w_x2;       // map_w * 2  (limits de camera en unitats x4)
    u16 cam_max_x4;     // map_w * 2 - 20
    u8  room_row_last;  // room_row0 + room_rows - 1 (terra de la sala)
    u16 code_exc_off;   // adreca del codi d'excepcions del nivell (C1)
} LevelParams;

extern LevelParams s_lv;

// Llegeix el bloc de parametres del paquet (crida'l DESPRES de carregar el
// paquet del nivell: es llegeix del Banc C1).
void level_params_load(void);

#endif
