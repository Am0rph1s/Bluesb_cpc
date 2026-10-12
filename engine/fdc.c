#include "fdc.h"

// ============================================================
// fdc.c - Estat C del lector FDC raw (motor a assets_fdc.s)
// ============================================================

// Buffers de treball del controlador NEC765 en RAM base (no bancable).
// Adreces fixes referenciades per assets_fdc.s (ASSETS_FDC_BUF/WORK).
u8 __at(0xB800) g_fdc_buf[512];
u8 __at(0xBA00) g_fdc_work[16];

// Paràmetres compartits amb el mòdul ASM assets_fdc.s
u16 g_fdc_ondisk_bytes;
u8  g_fdc_sector_count;
const u8* g_fdc_chs_table;
volatile u8  g_fdc_dest_bank;
void* g_fdc_dest_addr;
// Home bank del caller (byte dedicat, NO AF': EX AF,AF' es un SWAP i els
// restores parells escopirien l'A vella; vist 12/10/26). El shim l'escriu
// a l'entrada; el motor el llegeix a cada restore (inclòs fail-path).
u8 g_fdc_home_bank;

extern u8 assets_fdc_load_generic(void);

u8 fdc_load_file(u8 home_bank, const DiskFileDesc* desc, u8 dest_bank, void* dest_addr) {
    // Desa home al byte dedicat ABANS que res el trepitgi (A = home a
    // l'entrada per ABI classic, pero no hi comptem: el C l'usa lliurement
    // despres; el byte es l'unica font de veritat pel restore).
    g_fdc_home_bank = home_bank;
    g_fdc_ondisk_bytes = desc->ondisk_bytes;
    g_fdc_sector_count = desc->sector_count;
    g_fdc_chs_table    = desc->chs_table;
    g_fdc_dest_bank    = dest_bank;
    g_fdc_dest_addr    = dest_addr;
    return assets_fdc_load_generic();
}
