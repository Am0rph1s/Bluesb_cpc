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

extern u8 assets_fdc_load_generic(void);

u8 fdc_load_file(const DiskFileDesc* desc, u8 dest_bank, void* dest_addr) {
    g_fdc_ondisk_bytes = desc->ondisk_bytes;
    g_fdc_sector_count = desc->sector_count;
    g_fdc_chs_table    = desc->chs_table;
    g_fdc_dest_bank    = dest_bank;
    g_fdc_dest_addr    = dest_addr;
    return assets_fdc_load_generic();
}
