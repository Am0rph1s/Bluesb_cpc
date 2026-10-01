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

// Llegeix un fitxer del disc i el desa al banc de RAM indicat.
// Retorna 1 (OK) o 0 (error).
u8 fdc_load_file(const DiskFileDesc* desc, u8 dest_bank, void* dest_addr);

#endif // FDC_H
