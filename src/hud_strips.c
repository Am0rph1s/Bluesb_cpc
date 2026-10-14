// hud_strips.c - Tires del HUD al banc C2 (dieta Bloc 0, 10/26)
// ------------------------------------------------------------
// s_hud_strips (39x24 = 936 B, generat per tools/pack_level.py) vivia
// al _CODE resident; ara s'enllaca a la imatge C2 i render.c hi
// accedeix via EQU (obj/enemy_ext.s) amb bank_set(0xC2).
// Per nivell (L2+): regenerar hud_pkg.h = noves tires al mateix slot.
#include "cpctelera.h"
#include "hud_pkg.h"
