// ============================================================
// BLUES BROTHERS CPC - Motor Mode 0 (fet des de zero)
// ============================================================
//   - video_init(): RMR Mode 0 + CRTC + paleta (protocol GA correcte)
//   - Scroll estil Titus: display start per CRTC (R12/R13) + ring de 16K
//     i render incremental de la columna/fila que entra.
//   - Física sub-pixel (1/8 px) com el motor de Titus (cyxx/blues)
//   - Sprite de Jake amb mascara + desat de fons (flicker-free)
// ============================================================

#include "cpctelera.h"
#include "fdc.h"
#include "disk_tables.h"
#include "sprite.h"

extern void video_init(void);
extern void render_all(u16 cam_col, u16 cam_row);
extern void render_column(u16 cam_col, u16 cam_row, u16 sx);
extern void render_row(u16 cam_col, u16 cam_row, u16 sy);
extern void scroll_set(u16 word_off);
extern u16  scroll_get(void);
extern void crtc_set_scroll(u16 word_off);
extern void cpc_install_isr(void);

#define SUB         8
#define PH          34
#define PW          24
#define SPR_WB      12
#define SPEED_MAX   48
#define MOVE_ACC    8
#define VY_MAX      15
#define GRAV        2
#define JUMP_VY     (-30)

#define LEVEL_W_PX  (128 * 8)
#define DEAD_L      40
#define DEAD_R      120
#define DEAD_T      40
#define DEAD_B      140

#define START_PX8   (32 * 8 * SUB)
#define CAM0_COL    22
#define CAM0_ROW    110
#define PLAY_COLS   20
#define PLAY_ROWS   20
#define WORDS_LINE  40

static u16 g_cam_col;
static u16 g_cam_row;

static i16 s_px8, s_py8;
static i16 s_vx, s_vy;
static u8  s_on_ground;
static u8  s_face;
static u8  s_anim_idx, s_anim_timer;

static u8  s_bg[SPR_WB * PH];
static u16 s_old_sy, s_old_sx;
static u8  s_have_drawn;

static const u8 g_walk[4] = { 1, 2, 3, 2 };

#include "player_frames.h"

void start(void) {
    __asm
        ld      sp, #0xBFFE
    __endasm;
    main();
}

static u8 level_solid(u16 scol, u16 srow) {
    if (srow >= 126) return 1;
    (void)scol;
    return 0;
}

// Actualitza el display start del CRTC. Model simple: display start fix a 0
// (el render dibuixa el viewport a 0xC000). El scroll fi el farem despres.
static void update_scroll(void) {
    scroll_set(0);
    crtc_set_scroll(0);
}

void main(void) {
    cpc_install_isr();

    if (!fdc_load_file(&g_file_tiles, 0xC0, (void*)0x3600) ||
        !fdc_load_file(&g_file_map,   0xC0, (void*)0x7600) ||
        !fdc_load_file(&g_file_trig,  0xC0, (void*)0x9A00)) {
        while (1) { }
    }

    video_init();
    g_cam_col = CAM0_COL;
    g_cam_row = CAM0_ROW;
    update_scroll();
    render_all(g_cam_col, g_cam_row);

    s_px8 = START_PX8;
    s_py8 = (i16)((CAM0_ROW + 6) * 8 * SUB);
    s_vx = 0; s_vy = 0;
    s_on_ground = 1; s_face = 0;
    s_anim_idx = 0; s_anim_timer = 0;
    s_have_drawn = 0;

    while (1) {
        i8  move = 0;
        u8  jump = 0;
        i16 px, py;
        u16 dsx, dsy;

        cpct_waitVSYNC();
        cpct_scanKeyboard_f();
        if (cpct_isKeyPressed(Key_CursorLeft) || cpct_isKeyPressed(Key_Q) ||
            cpct_isKeyPressed(Joy0_Left))  { move = -1; s_face = 1; }
        if (cpct_isKeyPressed(Key_CursorRight) || cpct_isKeyPressed(Key_S) ||
            cpct_isKeyPressed(Joy0_Right)) { move = +1; s_face = 0; }
        if (cpct_isKeyPressed(Key_Space) || cpct_isKeyPressed(Key_CursorUp) ||
            cpct_isKeyPressed(Joy0_Fire1)) { jump = 1; }

        if (move > 0)      { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx >  SPEED_MAX) s_vx =  SPEED_MAX; }
        else if (move < 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < -SPEED_MAX) s_vx = -SPEED_MAX; }
        else {
            if (s_vx > 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < 0) s_vx = 0; }
            else if (s_vx < 0) { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx > 0) s_vx = 0; }
        }

        s_vy = (i16)(s_vy + GRAV);
        if (s_vy > VY_MAX) s_vy = VY_MAX;
        if (jump && s_on_ground) s_vy = JUMP_VY;

        s_px8 = (i16)(s_px8 + s_vx);
        if (s_px8 < 0) { s_px8 = 0; s_vx = 0; }
        if (s_px8 > (LEVEL_W_PX - PW) * SUB) { s_px8 = (i16)((LEVEL_W_PX - PW) * SUB); s_vx = 0; }
        s_py8 = (i16)(s_py8 + s_vy);

        px = (i16)(s_px8 >> 3);
        py = (i16)(s_py8 >> 3);
        {
            u16 feet_srow = (u16)((py + PH) >> 3);
            if (s_vy >= 0 && level_solid((u16)(px >> 3), feet_srow) && s_py8 >= 0) {
                s_py8 = (i16)((i16)(feet_srow << 3) - PH) * SUB;
                s_vy = 0;
                py = (i16)(s_py8 >> 3);
            }
        }
        if (s_py8 < 0) { s_py8 = 0; s_vy = 0; py = 0; }
        s_on_ground = level_solid((u16)(px >> 3), (u16)((py + PH) >> 3));

        // --- Camera: movem per subtiles i re-renderitzem el viewport ---
        // (model robust; el scroll fi per CRTC vindra despres)
        {
            i16 sy = (i16)(py - (i16)(g_cam_row * 8));
            i16 sx = (i16)(px - (i16)(g_cam_col * 8));
            u8 moved = 0;
            while (sy > DEAD_B && g_cam_row < 124) { g_cam_row++; sy = (i16)(sy - 8); moved = 1; }
            while (sy < DEAD_T && g_cam_row > 0)   { g_cam_row--; sy = (i16)(sy + 8); moved = 1; }
            while (sx > DEAD_R && g_cam_col < 108) { g_cam_col++; sx = (i16)(sx - 8); moved = 1; }
            while (sx < DEAD_L && g_cam_col > 0)   { g_cam_col--; sx = (i16)(sx + 8); moved = 1; }
            if (moved) {
                update_scroll();
                render_all(g_cam_col, g_cam_row);
            }
        }

        // --- Animacio + sprite ---
        {
            u8 cur;
            if (!s_on_ground) {
                cur = 4;
            } else if (move != 0) {
                s_anim_timer++;
                if (s_anim_timer >= 4) {
                    s_anim_timer = 0;
                    s_anim_idx++;
                    if (s_anim_idx >= 4) s_anim_idx = 0;
                }
                cur = g_walk[s_anim_idx];
            } else {
                cur = 0; s_anim_idx = 0; s_anim_timer = 0;
            }

            // dsx en BYTES de pantalla (1 byte = 2 px en Mode 0)
            dsx = (u16)((px - (i16)(g_cam_col * 8)) >> 1);
            dsy = (u16)(py - (i16)(g_cam_row * 8));

            if (s_have_drawn) sprite_restore(s_bg, s_old_sy, s_old_sx, SPR_WB, PH);
            sprite_blit_bg(g_player_frames[cur].data, dsy, dsx, SPR_WB, PH, s_bg);
            s_old_sy = dsy; s_old_sx = dsx;
            s_have_drawn = 1;
        }
    }
}
