#ifndef FDC_H
#define FDC_H

#include "cpctelera.h"

// ============================================================
// fdc.h - Accés FDC raw (NEC uPD765) per CHS
// Capa comuna extreta de Desperta Ferro (SDCC 4.5, sdcccall 1)
// ============================================================

// Descriptor d'un fitxer resident a la disquetera.
//   ondisk_bytes : mida total al disc (dades + 128 bytes de capçalera AMSDOS)
//   sector_count : nombre de sectors físics de 512 B que ocupa
//   chs_table    : taula plana [track, head, sector_id] de 3 bytes per sector
typedef struct {
    u16 ondisk_bytes;
    u8  sector_count;
    const u8* chs_table;
} DiskFileDesc;

// home_bank PRIMER (no darrer): SDCC classic passa el 1r param u8 a A
// (patro bank_set, provat en verd) i el shim el desa al byte
// g_fdc_home_bank d'entrada (NO AF': EX es SWAP). 0xC0 = GAME/STARTER
// (central); C4 = FRONT banked.
u8 fdc_load_file(u8 home_bank, const DiskFileDesc* desc, u8 dest_bank, void* dest_addr);

#endif // FDC_H
