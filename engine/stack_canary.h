#ifndef STACK_CANARY_H
#define STACK_CANARY_H

#include "cpctelera.h"

// Canari de pila resident per detectar desbordaments de SP cap a _DATA.
// S'ubica a 0x3C40: per sobre de _DATA (fi actual ~0x3B33) i per sota de
// la pila SP ~0x3FFE. NO fixar-lo mes avall: _DATA creix amb el projecte
// i trepitjaria el canari (falsa alarma permanent + corrupcio de variables).
// build.py avorta (FATAL) si _DATA arriba a 0x3C40.
#define CANARY_ADDR   0x3C40
#define CANARY_MAGIC  0xAA55
#define CANARY_WORDS  8

static inline void stack_canary_init(void) {
    u16* p = (u16*)CANARY_ADDR;
    u8 i;
    for (i = 0; i < CANARY_WORDS; i++) {
        p[i] = CANARY_MAGIC;
    }
}

static u8 stack_canary_ok(void) __naked {
    /* Comprova els CANARY_WORDS (8) parells 0x55 0xAA a CANARY_ADDR (0x3C40)
       en ASM pur per evitar suposicions d'offset de pila del compilador SDCC. */
    __asm
        ld   hl, #0x3C40
        ld   b, #8
    sc_chk_loop$:
        ld   a, (hl)
        cp   #0x55
        jr   nz, sc_chk_fail$
        inc  hl
        ld   a, (hl)
        cp   #0xAA
        jr   nz, sc_chk_fail$
        inc  hl
        djnz sc_chk_loop$
        ld   a, #1
        ret
    sc_chk_fail$:
        xor  a
        ret
    __endasm;
}

#endif
