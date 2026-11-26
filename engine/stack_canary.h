#ifndef STACK_CANARY_H
#define STACK_CANARY_H

#include "cpctelera.h"

// Canari de pila resident per detectar desbordaments de SP cap a _DATA.
// Amb _DATA a 0x3800, el canari es deixa a 0x3D80: hi ha ~80 B de separacio
// i queden ~622 B de pila util fins a SP=0x3FFE. El watermark de L1 amb
// scroll+enemics ha mesurat un maxim de 83 B; cal repetir la prova a tots
// els nivells abans de tornar a apretar aquest valor.
#define CANARY_ADDR   0x3D80
#define CANARY_MAGIC  0xAA55
#define CANARY_WORDS  8

static inline void stack_canary_init(void) {
    u16* p = (u16*)CANARY_ADDR;
    u8 i;
    for (i = 0; i < CANARY_WORDS; i++) {
        p[i] = CANARY_MAGIC;
    }
}

static inline u8 stack_canary_ok(void) {
    u16* p = (u16*)CANARY_ADDR;
    u8 i;
    for (i = 0; i < CANARY_WORDS; i++) {
        if (p[i] != CANARY_MAGIC) return 0;
    }
    return 1;
}

#endif
