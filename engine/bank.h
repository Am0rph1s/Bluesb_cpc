#ifndef BANK_H
#define BANK_H

#include "cpctelera.h"

// Variable ombra resident que reflecteix sempre l'estat del maquinari Gate Array
extern volatile u8 g_bank;

// Commuta al banc 'bank_val' (0xC4..0xC7) i RETORNA el banc anterior
u8 bank_set(u8 bank_val);

// Restaura el banc anterior (permet niuament segur de crides)
void bank_restore(u8 prev_bank);

// Retorna el banc actualment actiu a la finestra 0x4000..0x7FFF
u8 bank_get(void);

// Trampolí de crida inter-banc: commuta a 'bank', crida 'fn_ptr', i restaura
void call_banked(u8 bank, void* fn_ptr);

#endif
