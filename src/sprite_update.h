#ifndef SPRITE_UPDATE_H
#define SPRITE_UPDATE_H

#include "cpctelera.h"

// Rect en coords de pantalla: sy/sx en linies/bytes; w bytes d'ample; h linies.
typedef struct { u16 sy, sx; u8 w, h; } Rect;

// Inicialitza els buffers interns (cridar un cop a l'inici).
void sprite_update_init(void);

// Actualitzacio d'sprite amb dirty-rect d'una passada (sense forat ni rastres).
//   spr/sy/sx/w/h/ma0/flip : sprite nou.
//   oldr (NULL si no n'hi ha): rect del frame anterior (sempre s'esborra el vell).
//   reuse : 1 = reutilitza el fons desat a la interseccio (mateix mapeig MA).
void sprite_update(
    const u8* spr, u16 sy, u16 sx, u8 w, u8 h, u16 ma0, u8 flip,
    const Rect* oldr, u8 reuse);

#endif // SPRITE_UPDATE_H
