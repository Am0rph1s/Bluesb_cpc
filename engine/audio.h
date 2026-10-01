#ifndef AUDIO_H
#define AUDIO_H

#include <cpctelera.h>

// Efectes de so del gameplay. Cada efecte es una taula de passos
// (període, volum, durada) que sona a un canal lliure dels 3 del PSG.
#define SFX_SWING   0   // espasa/thrust (heroi i soldats cos-a-cos)
#define SFX_WHOOSH  1   // projectil (fletxes, pedres de gambutzi)
#define SFX_IMPACT  2   // cop donat a un enemic
#define SFX_DEATH   3   // mort d'enemic
#define SFX_DOOR    4   // porta tancant (marca l'inici de sala)
#define SFX_ENERGY  5   // projectil magic (bruixa i dimoni escuat)
#define SFX_BITE    6   // mos/atac cos-a-cos sense arma (gossos, senglar...)
#define SFX_SQUEAK  7   // xisclet agut (rata)
#define SFX_COIN    8   // moneda recollida (piticlin)

// Inicialitza el PSG (silencio total) i l'estat del modul.
void audio_init(void);

// Dispara un efecte a un canal lliure; si tots estan ocupats,
// talla el mes antic. No bloqueja.
void sfx_play(u8 sfx_id);

// Avanca el so un frame. Cridar cada frame des del main loop.
void audio_update(void);

// Jingle de 3 veus (sala neta, joc aturat). Atura els SFX actius.
void fanfare_play(void);

#endif
