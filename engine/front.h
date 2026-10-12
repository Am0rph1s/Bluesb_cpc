#ifndef FRONT_H
#define FRONT_H

#include "fdc.h"

// ============================================================
// front.h - FRONT banked (C4:0x4000, overlay d'arrencada).
// El GAME central no te marge (_CODE 91 B) per show+key+pal (~250 B)
// + SELECT/MAP. Aquestes funcions nomes toquen RAM central, VRAM,
// PPI i Gate Array (mai la finestra bancable): corren igual al
// banc C4, i el TILESET les sobreescriu quan acaba el FRONT.
// Args per MEMORIA central (patro motor FDC): el caller central els
// omple ABANS de paginar C4 (cap ABI fragil a traves del banc).
// ============================================================

typedef struct {
    u8 home;                  // 0xC4 (el motor hi restaura en sortir)
    const DiskFileDesc* desc; // .ZX0 (central: llegible des del banc)
    const u8* palhw;          // paleta 16 INKR (central)
} FrontArgs;

extern FrontArgs g_front_args; // definit a main.c (central _DATA)

#define FRONT_BASE 0x4000 // slot unic: JP _front_run (el build ho verifica)
#define FRONT_RUN  0x4000

#endif // FRONT_H
