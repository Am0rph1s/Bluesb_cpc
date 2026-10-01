#include "cpctelera.h"
#include "audio.h"
#include "fdc.h"
#include "scroll.h"
#include "sprite_update.h"
#include "player_sprite.h"
#include "player_frames.h"
#include "disk_tables.h"

// ============================================================
// BLUES BROTHERS CPC - prototip d'engine
// ------------------------------------------------------------
// Mode 1 (320x200, 4 colors). Area de joc 320x160 (20 files) + HUD 40 px.
// Scroll horitzontal per MAQUINARI (CRTC R12/R13) + camera amb zona morta.
// Fisica: gravetat, salt i col·lisions AABB contra el tilemap (level_tile).
// ============================================================

#define VRAM        ((u8*)0xC000)
#define VRAM_SIZE   0x4000
#define VIEW_BYTES  80          // 320 px Mode 1
#define PLAY_H      160         // alcada de l'area de joc

#define HW_BLACK    0x14
#define HW_WHITE    0x0B
#define HW_GREEN    0x06
#define HW_YELLOW   0x1A
#define HW_RED      0x1C
#define HW_BLUE     0x04

static const u8 g_palette[4] = { HW_BLACK, HW_BLUE, HW_RED, HW_WHITE };

#define PW          PLAYER_SPR_W_BYTES   // amplada sprite en bytes (16 px)
#define PH          PLAYER_SPR_H         // alcada sprite en linies (16 px)

#define START_SX    40
#define START_PY    (152 - PH)           // peus a terra (fila 19 = linia 152)
#define SPEED_X     2                    // bytes/frame (1 byte = 4 px)
#define GRAV        1
#define VY_MAX      6
#define JUMP_VY     8

#define DEAD_L      16                   // llindars de zona (unitats de 4 px)
#define DEAD_R      72
#define JUMP_U      56                   // salt de zona en unitats de 4 px
#define DEAD_T      48      // zona morta vertical (linies)
#define DEAD_B      112

extern void cpc_install_isr(void);   // engine/isr.s

static u8 s_anim_idx;    // index dins g_walk_seq
static u8 s_anim_timer;
static u8 s_face;        // 0 = dreta, 1 = esquerra (H-flip)

// Comptador de frames (debug via ZRCP). Volatile perque no l'optimitzi.
volatile u8 g_frame_count;
volatile u8 g_loop_marker;
volatile u16 g_c_hud;
volatile u16 g_c_col;
volatile u16 g_c_row;
volatile u16 g_c_spr;

// Ultim estat dibuixat de l'sprite, per no redibuixar-lo si no ha canviat
// (evita el parpalleig restore+blit en repòs).
volatile i16 s_last_dsx, s_last_dsy;
volatile u16 s_last_ma;
volatile u8  s_last_frame, s_last_face;
volatile u8  s_last_rect_w, s_last_rect_h;
volatile u8  s_have_drawn;    // inicialitzat explicitament (BSS no es neteja)

typedef struct { u16 wx; u16 py; } BoxArgs;
extern u8 asm_box_solid(const BoxArgs* a);  // engine/level.s

volatile i16 s_wx;       // posicio X del jugador (bytes de MON)  [global x debug]
volatile i16 s_wy;       // posicio Y del jugador (linies de MON)
static i8  s_vy;
volatile u8  s_on_ground;

void init_display(void) {
    cpct_disableFirmware();
    cpct_setVideoMode(1);
    cpct_setBorder(HW_BLACK);
    cpct_setPalette(g_palette, 4);
    memset(VRAM, 0x00, VRAM_SIZE);
}

// Comprova si la caixa del jugador [wx, wx+PW) x [py, py+PH) toca algun tile solid.
static u8 box_solid(i16 wx, i16 py) {
    BoxArgs b;
    if (py < 0) return 0;
    if (wx < 0) wx = 0;
    b.wx = (u16)wx;
    b.py = (u16)py;
    return asm_box_solid(&b);
}

void main(void);
void start(void) {
    __asm
        ld      sp, #0xBFFE
    __endasm;
    main();
}

void main(void) {
    init_display();
    cpc_install_isr();          // vector d'interrupcio valid (abans de tocar el FDC)
    audio_init();

    // --- Pantalla de titol: carregada del disc (FDC raw) a la VRAM 0xC000 ---
    {
        static const u8 title_pal[4] = { HW_BLACK, HW_BLUE, HW_RED, HW_WHITE };
        cpct_setPalette(title_pal, 4);
        if (!fdc_load_file(&g_file_title, 0xC0, (void*)0xC000)) {
            cpct_setBorder(HW_RED);          // error FDC: border vermell i penjar
            while (1) { }
        }
        cpct_waitVSYNC();
        while (1) {                          // esperar una tecla
            cpct_scanKeyboard_f();
            if (cpct_isKeyPressed(Key_Space) || cpct_isKeyPressed(Joy0_Fire1)) break;
            cpct_waitVSYNC();
        }
    }

    // --- Nivell real: tileset + mapa + triggers des del disc ---
    if (!fdc_load_file(&g_file_tiles, 0xC0, (void*)0x3000) ||
        !fdc_load_file(&g_file_map,   0xC0, (void*)0x7000) ||
        !fdc_load_file(&g_file_trig,  0xC0, (void*)0x9400)) {
        cpct_setBorder(HW_RED);
        while (1) { }
    }

    g_cam_subrow = CAM_SUBROW_MAX;   // comença mostrant la part baixa
    scroll_init();
    hud_draw();
    sprite_update_init();
    s_have_drawn = 0;
    s_anim_idx = 0;
    s_anim_timer = 0;

    s_wx = (i16)(2 * (i16)scroll_get_offset() + START_SX);
    s_wy = (i16)(1136 - PH);          // peus a la linia de terra del nivell
    s_vy = 0;
    s_on_ground = 1;

    while (1) {
        i8  move = 0;
        u8  jump = 0;
        i16 cam, cam_before, sx;

        cpct_waitVSYNC();
        g_frame_count++;              // debug: frames reals mostrats
        cpct_scanKeyboard_f();
        if (cpct_isKeyPressed(Key_CursorLeft) || cpct_isKeyPressed(Key_Q) ||
            cpct_isKeyPressed(Joy0_Left)) {
            move = -SPEED_X;
            s_face = 1;
        }
        if (cpct_isKeyPressed(Key_CursorRight) || cpct_isKeyPressed(Key_S) ||
            cpct_isKeyPressed(Joy0_Right)) {
            move = +SPEED_X;
            s_face = 0;
        }
        if (cpct_isKeyPressed(Key_Space) || cpct_isKeyPressed(Key_CursorUp) ||
            cpct_isKeyPressed(Joy0_Fire1)) {
            jump = 1;
        }

        // --- Horitzontal: sense caixa de paret (com l'original). El jugador
        //     camina lliurement; el terra es resol a la fase vertical, de manera
        //     que pot pujar esglaons baixos automaticament. Nomes limits del nivell.
        {
            i16 nx = (i16)(s_wx + move);
            if (nx < 0) nx = 0;
            if (nx > 512 - PW) nx = (i16)(512 - PW);   // limits del nivell (128 tiles)
            s_wx = nx;
        }

        // --- Vertical: gravetat + aterratge pel tile dels PEUS (MON) ---
        // El terra del tile es (tile_row<<4) + yoff, amb yoff = op_table1[x&15]-1
        // (taula segons l'op_func del tile). Aixi la caixa es trepitja on toca.
        s_vy = (i8)(s_vy + GRAV);
        if (s_vy > VY_MAX) s_vy = VY_MAX;
        if (jump && s_on_ground) s_vy = (i8)(-JUMP_VY);
        {
            i16 nwy = (i16)(s_wy + s_vy);
            i16 feet = (i16)(nwy + PH);
            u16 ftile = (u16)(feet >> 4);           // fila de tile dels peus
            u16 fpx = (u16)((feet >> 1) & 15);      // pixel x dins el tile (4px/subtile)
            u8 yoff = level_floor_yoff((u16)(s_wx >> 1), (u16)((nwy + PH) >> 3), (u8)fpx);
            if (s_vy >= 0 && yoff != 0xFF) {
                s_wy = (i16)(((ftile << 4) + yoff) - PH);   // reposa sobre el terra del tile
                s_vy = 0;
            } else {
                s_wy = nwy;
            }
        }
        if (s_wy < 0) { s_wy = 0; s_vy = 0; }
        {
            u16 feet = (u16)(s_wy + PH);
            u16 fpx = (u16)((feet >> 1) & 15);
            s_on_ground = (u8)(level_floor_yoff((u16)(s_wx >> 1), (u16)(feet >> 3), (u8)fpx) != 0xFF);
        }

        // --- Camera: VERTICAL primer, despres HORITZONTAL (zona morta) ---
        {
            i16 py = (i16)(s_wy - (i16)(g_cam_subrow * 8));
            while (py > DEAD_B && scroll_step_v(+1)) py = (i16)(py - 8);
            while (py < DEAD_T && scroll_step_v(-1)) py = (i16)(py + 8);
        }
        // Camera CONTINUA: desplacament de 8 px per pas (zona morta).
        cam = (i16)scroll_get_hpos();          // camera en unitats de 4 px
        cam_before = cam;
        sx = (i16)(s_wx - cam);
        while (sx > DEAD_R) { scroll_step_dir(+1); cam = (i16)(cam + 2); sx = (i16)(sx - 2); }
        while (sx < DEAD_L) { scroll_step_dir(-1); cam = (i16)(cam - 2); sx = (i16)(sx + 2); }
        if (cam != cam_before) hud_draw();

        // --- Render: unio del rect vell (desplacat per la camera) i el nou ---
        // --- Animacio: escollir frame ---
        {
            u8 cur;
            const PSprFrame* fr;
            i16 dsx, dsy, spy;
            if (!s_on_ground) {
                cur = 4;                       // salt (frame 7)
            } else if (move != 0) {
                s_anim_timer++;
                if (s_anim_timer >= 2) {
                    s_anim_timer = 0;
                    s_anim_idx++;
                    if (s_anim_idx >= 6) s_anim_idx = 0;
                }
                cur = g_walk_seq[s_anim_idx];
            } else {
                cur = 1;                       // idle (frame 1)
                s_anim_idx = 0;
                s_anim_timer = 0;
            }
            fr = &g_player_frames[cur];
            spy = (i16)(s_wy - (i16)(g_cam_subrow * 8));   // Y de pantalla
            dsy = (i16)(spy + (PH - fr->h));               // peus alineats
            dsx = (i16)((s_wx - cam) + ((PW - fr->wb) >> 1)); // centrat

            {
                u16 ma = scroll_get_ma();
                u8 redraw = (!s_have_drawn || dsx != s_last_dsx || dsy != s_last_dsy ||
                             ma != s_last_ma || cur != s_last_frame || s_face != s_last_face);
                if (redraw) {
                    // Sempre es passa el rect vell per esborrar-lo (evita rastres
                    // quan canvia la mida de frame o el flip). Nomes es reutilitza
                    // el fons desat si el mapeig MA no ha canviat.
                    Rect old_rect;
                    u8 reuse;
                    if (s_have_drawn) {
                        old_rect.sy = (u16)s_last_dsy;
                        old_rect.sx = (u16)s_last_dsx;
                        old_rect.w  = s_last_rect_w;
                        old_rect.h  = s_last_rect_h;
                    } else {
                        old_rect.sy = 0; old_rect.sx = 0;
                        old_rect.w = 0; old_rect.h = 0;
                    }
                    reuse = (u8)(s_have_drawn && ma == s_last_ma);

                    g_c_spr++;
                    sprite_update(
                        fr->data, (u16)dsy, (u16)dsx, fr->wb, fr->h, ma, s_face,
                        &old_rect, reuse);

                    s_last_dsx = dsx; s_last_dsy = dsy; s_last_ma = ma;
                    s_last_frame = cur; s_last_face = s_face;
                    s_last_rect_w = fr->wb; s_last_rect_h = fr->h;
                    s_have_drawn = 1;
                }
            }
        }

        audio_update();
    }
}
