#include "sprite_update.h"

// ============================================================
// sprite_update.c - Dirty-rect d'una passada per a l'sprite.
// ------------------------------------------------------------
// Objectiu: eliminar el parpalleig del classic "esborra tot + dibuixa tot".
// Metode:
//   1) Restaura el fons VELL nomeS on queda FORA del rect nou.
//   2) Recorre el rect NOU: si un byte se solapa amb el vell, reutilitza el
//      fons ja desat (mai queda forat); si es nou, desa el fons actual.
// El buffer de sortida te EXACTAMENT w*h entrades.
// Els buffers son interns per evitar crides amb massa arguments (SDCC).
// ============================================================

#define VRAM        ((u8*)0xC000)
#define MA_MASK     0x03FF
#define SPR_SAVE_MAX 256

// Taula de mirall horitzo (256 bytes) definida a engine/sprite.s.
extern const u8 FLIPTAB[256];

static u16 g_cur_addr[SPR_SAVE_MAX];
static u8  g_cur_byte[SPR_SAVE_MAX];
static u16 g_nxt_addr[SPR_SAVE_MAX];
static u8  g_nxt_byte[SPR_SAVE_MAX];
static u16 g_cur_cnt;

void sprite_update_init(void) {
    g_cur_cnt = 0;
}

// Adreca del byte (y linia, bx byte horitzontal) amb base MA ma0 (Mode 1 CPC).
static u16 spr_addr(u16 ma0, u16 sx, u16 y, u8 bx) {
    u16 x = (u16)(sx + bx);
    u16 block = (u16)((y & 7) << 11);
    u16 ma_row = (u16)((ma0 + (y >> 3) * 40) & MA_MASK);
    u16 ma = (u16)((ma_row + (x >> 1)) & MA_MASK);
    return (u16)(0xC000 | block | (ma << 1) | (x & 1));
}

void sprite_update(
    const u8* spr, u16 sy, u16 sx, u8 w, u8 h, u16 ma0, u8 flip,
    const Rect* oldr, u8 reuse)
{
    u16 i, n;
    u8 ly, bx;
    u16 yend, xend;

    yend = (u16)(sy + h);
    xend = (u16)(sx + w);

    // ---- Pas 1: restaura el fons vell fora del rect nou ----
    if (oldr && oldr->w && oldr->h) {
        u16 oy = oldr->sy;
        i = 0;
        for (ly = 0; ly < oldr->h; ly++) {
            u16 x = oldr->sx;
            for (bx = 0; bx < oldr->w; bx++) {
                if (!(oy >= sy && oy < yend && x >= sx && x < xend)) {
                    VRAM[g_cur_addr[i]] = g_cur_byte[i];
                }
                i++;
                x++;
            }
            oy++;
        }
    }

    // ---- Pas 2: desa fons + blit del rect nou ----
    n = 0;
    for (ly = 0; ly < h; ly++) {
        u16 y = (u16)(sy + ly);
        u16 rowoff = 0xFFFF;
        if (oldr && oldr->w && oldr->h && y >= oldr->sy && y < (u16)(oldr->sy + oldr->h)) {
            rowoff = (u16)((y - oldr->sy) * oldr->w);
        }
        for (bx = 0; bx < w; bx++) {
            u16 x = (u16)(sx + bx);
            u16 a = spr_addr(ma0, sx, y, bx);
            u8 bg;
            u8 sxb;
            const u8* p;
            u8 mask, img;

            if (reuse && rowoff != 0xFFFF &&
                x >= oldr->sx && x < (u16)(oldr->sx + oldr->w)) {
                bg = g_cur_byte[rowoff + (u16)(x - oldr->sx)];
            } else {
                bg = VRAM[a];
            }

            g_nxt_addr[n] = a;
            g_nxt_byte[n] = bg;
            n++;

            sxb = flip ? (u8)(w - 1 - bx) : bx;
            p = spr + (((u16)ly * w + sxb) << 1);
            mask = p[0];
            img  = p[1];
            if (flip) {
                mask = FLIPTAB[mask];
                img  = FLIPTAB[img];
            }
            VRAM[a] = (u8)((bg & mask) | img);
        }
    }

    // Intercanvia cur <-> nxt perque nxt sigui el fons del proper frame.
    {
        u16 j;
        for (j = 0; j < n; j++) {
            u16 ta = g_cur_addr[j]; g_cur_addr[j] = g_nxt_addr[j]; g_nxt_addr[j] = ta;
            u8  tb = g_cur_byte[j]; g_cur_byte[j] = g_nxt_byte[j]; g_nxt_byte[j] = tb;
        }
    }
    g_cur_cnt = n;
}
