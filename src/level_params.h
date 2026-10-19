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
} LevelParams;

extern LevelParams s_lv;

// Llegeix el bloc de parametres del paquet (crida'l DESPRES de carregar el
// paquet del nivell: es llegeix del Banc C1).
void level_params_load(void);

#endif
