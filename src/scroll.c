#include "scroll.h"

// ============================================================
// scroll.c - Render del NIVELL REAL de Blues Brothers + scroll per maquinari
// ------------------------------------------------------------
// Les dades del nivell es carreguen del disc (FDC) a adreces fixes:
//   0x3000 TILESET (1024 subtiles 8x8 Mode1: half*512 + tile*4 + quad)
//   0x7000 MAP     (128 x 72 bytes; byte: bit7=half, bits0-6=tile num)
//   0x9400 TRIG    (256 tr -> 10 bytes: byte0 = tile_type, per a solidesa)
//
// HUD i columna entrant => ASM (engine/render.s, engine/level.s).
// Sprite (bg_rect + blit) => C (validat).
// ============================================================

#define VRAM        ((u8*)0xC000)
#define VIEW_BYTES  80
#define TILE_BYTES  2
#define TILE_H      8
#define PLAY_ROWS   20
#define HUD_TOP     160
#define COLS        40
#define MA_MASK     0x03FF

#define LEVEL_W_TILES  128
#define LEVEL_H_TILES  72
#define LEVEL_SCOLS    (LEVEL_W_TILES * 2)     // 256 subtiles d'ample
#define LEVEL_SROWS    (LEVEL_H_TILES * 2)     // 144 subtiles d'alt
#define S_STEP_MAX     (LEVEL_SCOLS - COLS)    // 216

#define TILESET  ((const u8*)0x3000)
#define GMAP     ((const u8*)0x7000)
#define GTRIG    ((const u8*)0x9400)

static const u8 g_blank[16] = { 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0 };

static u16 s_step;
static u8  s_half;           // mig caracter (4 px): 0 = R3 normal, 1 = R3 desplacat
u16 g_cam_subrow = 124;      // subtile row que es mostra a dalt de tot
static u16 s_ma_base;        // (s_step + 40*g_cam_subrow) & 0x3FF : offset CRTC real

// ASM entry points
typedef struct { u16 ma0; u16 col; u8 c_off; } ColArgs;
typedef struct { u16 row_ma; u16 col0; u16 srow; } RowArgs;
extern void asm_column(const ColArgs* a);   // engine/level.s
extern void asm_row(const RowArgs* a);      // engine/level.s
extern void render_hud(u16 ma0);            // engine/render.s

// Recalcula l'offset MA combinat (horitzontal + vertical) que cal usar
// tant al CRTC (R12/R13) com a TOTES les escriptures a VRAM.
// El contingut del nivell (R,C) sempre acaba a MA = 40R+C (mod 1024).
volatile u16 g_dbg_ma;
volatile u16 g_dbg_step;
volatile u16 g_dbg_camrow;

static void upd_ma(void) {
    s_ma_base = (u16)((s_step + (u16)(g_cam_subrow * 40)) & MA_MASK);
    g_dbg_ma = s_ma_base;
    g_dbg_step = s_step;
    g_dbg_camrow = g_cam_subrow;
}

// Adreça d'un subtile 8x8 Mode1 donat (scol,srow) al nivell.
static const u8* subtile_ptr(u16 scol, u16 srow) {
    u16 tcol, trow;
    u8 b, num, half, quad;
    if (scol >= LEVEL_SCOLS || srow >= LEVEL_SROWS) return g_blank;
    tcol = (u16)(scol >> 1);
    trow = (u16)(srow >> 1);
    b = GMAP[trow * LEVEL_W_TILES + tcol];
    num = (u8)(b & 0x7F);
    half = (u8)(b >> 7);
    quad = (u8)(((srow & 1) << 1) | (scol & 1));
    return TILESET + (((u16)half * 512 + (u16)num * 4 + quad) << 4);
}

// Solidesa pel CAP: op_func de terra (14/20/31/34/36/38). El jugador no pot
// travessar aquests tiles per dalt. 25 = buit.
u8 level_solid(u16 scol, u16 srow) {
    u16 tcol, trow;
    u8 b, op;
    if (scol >= LEVEL_SCOLS || srow >= LEVEL_SROWS) return 0;
    if (srow >= LEVEL_SROWS - 1) return 1;   // terra de seguretat (última fila)
    tcol = (u16)(scol >> 1);
    trow = (u16)(srow >> 1);
    b = GMAP[trow * LEVEL_W_TILES + tcol];
    op = GTRIG[(b & 0x7F) * 10 + 2];   // op_func del trigger
    return (u8)(op == 14 || op == 20 || op == 31 || op == 34 || op == 36 || op == 38);
}

// Offset de terra del tile (subtile scol,srow): la superficie dels tiles de
// terra es al capdamunt del tile, aixi que l'offset es 0. 0xFF = no solid.
// (El xpix es mante a la signatura per si cal afinar superficies inclinades.)
u8 level_floor_yoff(u16 scol, u16 srow, u8 xpix) {
    u16 tcol, trow;
    u8 b, num, op;
    (void)xpix;
    if (scol >= LEVEL_SCOLS || srow >= LEVEL_SROWS) return 0xFF;
    tcol = (u16)(scol >> 1);
    trow = (u16)(srow >> 1);
    b = GMAP[trow * LEVEL_W_TILES + tcol];
    num = (u8)(b & 0x7F);
    op = GTRIG[num * 10 + 2];            // op_func del trigger
    if (op == 14 || op == 20 || op == 31 || op == 34 || op == 36 || op == 38)
        return 0;                        // terra: superficie al capdamunt
    return 0xFF;                         // no es terra
}

// Redibuixa tota l'area de joc (20 files x 41 columnes) des del tilemap.
static void redraw_play(void) {
    u16 row;
    for (row = 0; row < PLAY_ROWS; row++) {
        RowArgs ra;
        ra.row_ma = (u16)((s_ma_base + row * 40) & MA_MASK);
        ra.col0 = s_step;
        ra.srow = (u16)(row + g_cam_subrow);
        asm_row(&ra);
    }
}

void scroll_init(void) {
    s_step = 0;
    s_half = 0;
    upd_ma();
    redraw_play();
    hud_draw();
    crtc_set_scroll(s_ma_base);
    crtc_set_r3(0x8E);          // R3 per defecte (sense desplacament fi)
}

// Scroll horitzontal CONTINU: pas de 8 px (1 subtile). Redibuixa la columna
// que entra pel voral i reprograma R12/R13. Sense artefactes.
void scroll_step_dir(i8 dir) {
    u16 ma0;
    u8 c_off;

    if (dir == 0) return;
    if (dir > 0 && s_step >= S_STEP_MAX) return;
    if (dir < 0 && s_step == 0) return;

    s_step = (u16)(s_step + dir);
    upd_ma();
    ma0 = s_ma_base;

    if (dir > 0) c_off = 39; else c_off = 0;

    {
        ColArgs ca;
        ca.ma0 = ma0;
        ca.col = (u16)(s_step + c_off);
        ca.c_off = c_off;
        asm_column(&ca);
    }

    crtc_set_scroll(ma0);
}

void scroll_jump(i16 dstep) { (void)dstep; }   // (no usat)

// Posicio de camera horitzontal en unitats de 4 px (per a l'sprite).
u16 scroll_get_hpos(void) { return (u16)(2 * s_step); }

void scroll_step(void) { scroll_jump(1); }

// Vertical per maquinari: R12/R13 += 40 desplaça tota la pantalla una fila.
// Nomes cal redibuixar la fila que entra pel voral (a baix o a dalt) + el HUD.
u8 scroll_step_v(i8 dir) {
    RowArgs ra;
    if (dir == 0) return 0;
    if (dir > 0 && g_cam_subrow >= CAM_SUBROW_MAX) return 0;
    if (dir < 0 && g_cam_subrow == 0) return 0;
    g_cam_subrow = (u16)(g_cam_subrow + dir);
    upd_ma();
    if (dir > 0) {
        ra.row_ma = (u16)((s_ma_base + (PLAY_ROWS - 1) * 40) & MA_MASK);
        ra.col0 = s_step;
        ra.srow = (u16)(g_cam_subrow + PLAY_ROWS - 1);
    } else {
        ra.row_ma = s_ma_base;
        ra.col0 = s_step;
        ra.srow = g_cam_subrow;
    }
    asm_row(&ra);
    crtc_set_scroll(s_ma_base);
    hud_draw();
    return 1;
}

void screen_bg_rect(u16 sy, u16 sx, u8 w, u8 h) {
    u16 ma0 = s_ma_base;
    u8 ly, bx;
    for (ly = 0; ly < h; ly++) {
        u16 y = (u16)(sy + ly);
        u16 block = (u16)((y & 7) << 11);
        u16 ma_row = (u16)((ma0 + (y >> 3) * 40) & MA_MASK);
        for (bx = 0; bx < w; bx++) {
            u16 x = (u16)(sx + bx);
            const u8* tile = subtile_ptr((u16)(s_step + (x >> 1)), (u16)((y >> 3) + g_cam_subrow));
            u16 ma = (u16)((ma_row + (x >> 1)) & MA_MASK);
            VRAM[(u16)(block | (ma << 1) | (x & 1))] = tile[(y & 7) * TILE_BYTES + (x & 1)];
        }
    }
}

void screen_blit_sprite(const u8* spr, u16 sy, u16 sx, u8 w, u8 h) {
    u16 ma0 = s_ma_base;
    u8 ly, bx;
    for (ly = 0; ly < h; ly++) {
        u16 y = (u16)(sy + ly);
        u16 block = (u16)((y & 7) << 11);
        u16 ma_row = (u16)((ma0 + (y >> 3) * 40) & MA_MASK);
        for (bx = 0; bx < w; bx++) {
            u16 x = (u16)(sx + bx);
            u16 ma = (u16)((ma_row + (x >> 1)) & MA_MASK);
            u16 a = (u16)(block | (ma << 1) | (x & 1));
            const u8* p = spr + (((u16)ly * w + bx) << 1);
            VRAM[a] = (u8)((VRAM[a] & p[0]) | p[1]);
        }
    }
}

extern volatile u16 g_c_hud;
void hud_draw(void) {
    g_c_hud++;
    render_hud(s_ma_base);
}

u16 scroll_get_offset(void) { return s_step; }

// Offset MA real per a l'sprite (inclou el desplaçament vertical).
u16 scroll_get_ma(void) { return s_ma_base; }
