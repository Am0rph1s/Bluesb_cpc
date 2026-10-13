#ifndef MUS_H
#define MUS_H

#include "cpctelera.h"

// ============================================================
// mus.h - Musica AT3 AKG (banc C1: player + canco a l'slot).
// Stubs centrals (engine/mus.s): paginen C1, criden, restauren.
// _akg_init/_akg_play/_akg_stop son EQU del mapa de musica (mus_ext.s).
// init/stop: context EI (fan DI/EI). play: ISR-ONLY (la ISR ja es DI).
// ============================================================

#define MUS_BANK 0xC1
#define MUS_SONG_SLOT 0x5000

// HOLD musica ISR (byte a _DATA, isr.s): 1 = motor FDC en lectura (dest
// bancable). El motor hi escriu via EQU (fdc_hold.s); la ISR el llegeix.
extern volatile u8 g_mus_hold;

void mus_init(void); // (re)inicia la canco actual de l'slot (subsongo 0)
void mus_play(void); // ISR-ONLY: avanca 1 tick (la ISR el crida a 50 Hz)
void mus_stop(void); // silencia AY (posicio intacta: la ISR repren on era)

#endif // MUS_H
