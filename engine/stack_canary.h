#ifndef STACK_CANARY_H
#define STACK_CANARY_H

#include "cpctelera.h"

// Canari de pila resident per detectar desbordaments de SP cap a _DATA
// S'ubica a 0x3B40 (per sobre de _DATA/_INITIALIZED, que acaben a 0x3AE4,
// i per sota de la pila SP ~0x3FFE).
#define CANARY_ADDR   0x3B40
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
