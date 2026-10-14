#ifndef CRT_ADDRS_H
#define CRT_ADDRS_H
// Generat per tools/build.py des de obj/bluesb.map. NO EDITAR.
#define CRT_DATA_START 0x3780
#define CRT_DATA_LEN 1115
#define CRT_IDATA_DST 0x3BDB
#define CRT_IDATA_SRC 0x3BDF
#define CRT_IDATA_LEN 4
// Adreca de _g_mus_hold (HOLD musica ISR): la neteja el GAME
// post-memset(0x8000) (era VRAM: 0xBA10 = drone, vist 13/10/26).
#define MUS_HOLD_ADDR 0x378E
#endif
