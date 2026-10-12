#ifndef MUS_H
#define MUS_H

#include "cpctelera.h"

// ============================================================
// mus.h - Musica AT3 AKG (banc C1: player + canco a l'slot).
// Stubs centrals (engine/mus.s): paginen C1, criden, restauren.
// _akg_init/_akg_play son EQU del mapa de musica (obj/mus_ext.s).
// Crida SEMPRE amb EI (els stubs fan DI/EI: el player usa l'stack).
// ============================================================

#define MUS_BANK 0xC1
#define MUS_SONG_SLOT 0x5000

void mus_init(void); // (re)inicia la canco actual de l'slot (subsongo 0)
void mus_play(void); // avanca 1 tick (50 Hz: 2 cops per frame de 25 Hz)

#endif // MUS_H
