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
    const u8* palhw;          // paleta 16 INKR (central)
    const DiskFileDesc* musbank; // MUSBANK (player+intro, central)
    u8 load_mus;              // 1 = carrega MUSBANK a C1 + mus_init (splash)
    u8 screen;                // 0=splash, 1=select, 2=mapa (depack des de
                              // RAM: sense FDC, musica intacta)
    const DiskFileDesc* splash; // FSPLASH.ZX0 (fixa 0x8400, EQU front_ext)
    const DiskFileDesc* sel;  // FSELECT.ZX0 (banc C4, EQU front_ext)
    const DiskFileDesc* map;  // FMAP.ZX0 (fixa darrere splash, EQU)
} FrontArgs;

extern FrontArgs g_front_args; // definit a main.c (central _DATA)

#define FRONT_BASE 0x4000 // slot unic: JP _front_run (el build ho verifica)
#define FRONT_RUN  0x4000

#endif // FRONT_H
