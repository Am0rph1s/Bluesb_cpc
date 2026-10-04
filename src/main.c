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
#define PH          30
#define PW          24
#define SPR_WB      12
#define SPEED_MAX   24
#define MOVE_ACC    4
#define VY_MAX      (15 * SUB)
#define GRAV        3
#define JUMP_VY     (-52)

#define LEVEL_W_PX  (128 * 8)
#define DEAD_L      48
#define DEAD_R      88
#define DEAD_T      32
#define DEAD_B      116
#define SHIFT_X     1
#define SHIFT_Y     1

#define START_PX    32
#define START_PY    1106
#define CAM0_COL    0
#define CAM0_ROW    124
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

static u8  s_have_drawn[2];
static u8  s_last_x, s_last_y, s_last_cur, s_last_face;

u8* g_backbuffer = (u8*)0x8000;
static u8 s_back_page = 1;  // 1 -> back is 0x8000 (front 0xC000, R12=0x30); 0 -> back is 0xC000 (front 0x8000, R12=0x20)

static const u8 g_walk[4] = { 0, 1, 2, 1 };

#include "player_frames.h"

void main(void);

void start(void) {
    __asm
        ld      sp, #0x3FFE
    __endasm;
    main();
}

#define MAP_PTR   ((const u8*)0x4000)
#define TRIG_PTR  ((const u8*)0x6400)

static u8 get_tile(u16 col, u16 row) {
    u8 t;
    if (col >= 128 || row >= 72) return 0;
    cpc_bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    cpc_bank_restore();
    return t;
}

static u8 get_tile_flags(u16 col, u16 row) {
    u8 t, fl;
    u16 off;
    if (col >= 128 || row >= 72) return 0;
    cpc_bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    off = (((u16)t) << 3) + (((u16)t) << 1);
    fl = TRIG_PTR[off + 1];
    cpc_bank_restore();
    return fl;
}

static u8 get_tile_op(u16 col, u16 row) {
    u8 t, op;
    u16 off;
    if (col >= 128 || row >= 72) return 0;
    cpc_bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    off = (((u16)t) << 3) + (((u16)t) << 1);
    op = TRIG_PTR[off + 2];
    cpc_bank_restore();
    return op;
}

static u8 is_floor_solid(u16 col, u16 row, i16 vy) {
    u8 op;
    if (row >= 71) return 1;
    op = get_tile_op(col, row);
    if (op == 20 || op == 14 || op == 15 || op == 21 || op == 27 || op == 28) return 1;
    if (op >= 31 && op <= 39 && vy >= 0) return 1;
    return 0;
}

static u8 is_ceiling_solid(u16 col, u16 row) {
    u8 op;
    if (row >= 72) return 0;
    op = get_tile_op(col, row);
    if (op == 20) return 1;
    return 0;
}

// Actualitza el display start del CRTC. Model simple: display start fix a 0
// (el render dibuixa el viewport a 0xC000 o 0x8000).
static void update_scroll(void) {
    scroll_set(0);
    crtc_set_scroll(0);
}

void main(void) {
    cpc_install_isr();

    // Carregar fitxers directament als Bancs 4 i 5 de la RAM estesa de 128 KB
    if (!fdc_load_file(&g_file_tiles, 0xC4, (void*)0x4000) ||
        !fdc_load_file(&g_file_map,   0xC5, (void*)0x4000) ||
        !fdc_load_file(&g_file_trig,  0xC5, (void*)0x6400)) {
        while (1) { }
    }

    video_init();
    // Netejar les dues pàgines de VRAM (0xC000 i 0x8000)
    cpct_memset((void*)0xC000, 0, 0x4000);
    cpct_memset((void*)0x8000, 0, 0x4000);

    g_cam_col = CAM0_COL;
    g_cam_row = CAM0_ROW;
    update_scroll();

    // Inicialitzar la primera pàgina visible (0xC000)
    g_backbuffer = (u8*)0xC000;
    g_vram_base_hi = 0xC0;
    render_all(g_cam_col, g_cam_row);
    crtc_set_page(0x30); // Mostrar 0xC000

    // I preparar el backbuffer a 0x8000 amb el mateix fons
    g_backbuffer = (u8*)0x8000;
    g_vram_base_hi = 0x80;
    render_all(g_cam_col, g_cam_row);
    s_back_page = 1; // El proper frame actiu serà a 0x8000

    s_px8 = (i16)(START_PX * SUB);
    s_py8 = (i16)(START_PY * SUB);
    s_vx = 0; s_vy = 0;
    s_on_ground = 1; s_face = 0;
    s_anim_idx = 0; s_anim_timer = 0;
    s_have_drawn[0] = 0;
    s_have_drawn[1] = 0;
    s_last_x = 255; s_last_y = 255; s_last_cur = 255; s_last_face = 255;

    while (1) {
        i8  move = 0;
        u8  jump = 0;
        i16 px, py;
        u16 dsx, dsy;

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

        py = (i16)(s_py8 >> 3);

        // --- Moviment horitzontal i col·lisió de parets 1:1 ---
        if (s_vx > 0) {
            u16 next_px = (u16)((s_px8 + s_vx) >> 3);
            u16 c_right = (u16)((next_px + 18) >> 3);
            u16 r_waist = (u16)((py + 16) >> 4);
            u16 r_head  = (u16)(py >> 4);
            u8 fl = get_tile_flags(c_right, r_waist) |
                    get_tile_flags(c_right, r_head);
            if (fl & 1) {
                s_vx = 0;
                s_px8 = (i16)(((c_right << 3) - 19) * SUB);
            } else {
                s_px8 = (i16)(s_px8 + s_vx);
            }
        } else if (s_vx < 0) {
            u16 next_px = (u16)((s_px8 + s_vx) >> 3);
            u16 c_left  = (u16)((next_px + 5) >> 3);
            u16 r_waist = (u16)((py + 16) >> 4);
            u16 r_head  = (u16)(py >> 4);
            u8 fl = get_tile_flags(c_left, r_waist) |
                    get_tile_flags(c_left, r_head);
            if (fl & 2) {
                s_vx = 0;
                s_px8 = (i16)(((c_left << 3) + 8 - 5) * SUB);
            } else {
                s_px8 = (i16)(s_px8 + s_vx);
            }
        }
        if (s_px8 < 0) { s_px8 = 0; s_vx = 0; }
        if (s_px8 > (i16)((LEVEL_W_PX - PW) * SUB)) { s_px8 = (i16)((LEVEL_W_PX - PW) * SUB); s_vx = 0; }
        px = (i16)(s_px8 >> 3);

        // --- Moviment vertical i gravetat 1:1 ---
        {
            i16 prev_feet = (i16)(py + PH);
            if (!s_on_ground) {
                s_vy = (i16)(s_vy + GRAV);
                if (s_vy > VY_MAX) s_vy = VY_MAX;
            } else {
                s_vy = 0;
            }
            if (jump && s_on_ground) {
                s_vy = JUMP_VY;
                s_on_ground = 0;
            }

            s_py8 = (i16)(s_py8 + s_vy);
            py = (i16)(s_py8 >> 3);

            {
                i16 curr_feet = (i16)(py + PH);
                u16 c_mid1 = (u16)((px + 7) >> 3);
                u16 c_mid2 = (u16)((px + 16) >> 3);
                u8 landed = 0;

                if (s_vy >= 0) {
                    u16 target_row = (u16)(curr_feet >> 4);
                    if (target_row < 72) {
                        i16 surf = (i16)(target_row << 4);
                        if (is_floor_solid(c_mid1, target_row, s_vy) || is_floor_solid(c_mid2, target_row, s_vy)) {
                            if (prev_feet <= (surf + 8) && curr_feet >= surf) {
                                py = (i16)(surf - PH);
                                s_py8 = (i16)(py * SUB);
                                s_vy = 0;
                                s_on_ground = 1;
                                landed = 1;
                            }
                        }
                    }
                    if (!landed) {
                        u16 feet_under = (u16)((curr_feet + 1) >> 4);
                        if (feet_under < 72) {
                            i16 surf_u = (i16)(feet_under << 4);
                            if (is_floor_solid(c_mid1, feet_under, s_vy) || is_floor_solid(c_mid2, feet_under, s_vy)) {
                                if (prev_feet <= (surf_u + 6) && curr_feet >= (surf_u - 2)) {
                                    py = (i16)(surf_u - PH);
                                    s_py8 = (i16)(py * SUB);
                                    s_vy = 0;
                                    s_on_ground = 1;
                                    landed = 1;
                                }
                            }
                        }
                    }
                    if (!landed) {
                        s_on_ground = 0;
                    }
                } else {
                    u16 head_row = (u16)(py >> 4);
                    u16 c_mid = (u16)((px + 11) >> 3);
                    if (is_ceiling_solid(c_mid, head_row)) {
                        py = (i16)((head_row + 1) << 4);
                        s_py8 = (i16)(py * SUB);
                        s_vy = 0;
                    }
                    s_on_ground = 0;
                }
            }
        }

        // --- Camera: seguiment continu de personatge (estil C64 / Amiga) ---
        i8 move_x = 0;
        i8 move_y = 0;
        {
            i16 sy = (i16)(py - (i16)(g_cam_row * 8));
            i16 sx = (i16)(px - (i16)(g_cam_col * 8));
            if (sx > DEAD_R && g_cam_col < (128 - PLAY_COLS)) {
                g_cam_col++;
                move_x = +1;
            } else if (sx < DEAD_L && g_cam_col > 0) {
                g_cam_col--;
                move_x = -1;
            }

            if (sy > DEAD_B && g_cam_row < 124) {
                g_cam_row++;
                move_y = +1;
            } else if (sy < DEAD_T && g_cam_row > 0) {
                g_cam_row--;
                move_y = -1;
            }
        }

        // --- Animacio ---
        u8 cur;
        if (!s_on_ground) {
            cur = 3;
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
        {
            i16 screen_x = (i16)((px - (i16)(g_cam_col * 8)) >> 1);
            i16 screen_y = (i16)(py - (i16)(g_cam_row * 8));
            if (screen_x < 0) screen_x = 0;
            if (screen_x > (80 - SPR_WB)) screen_x = (80 - SPR_WB);
            if (screen_y < 0) screen_y = 0;
            if (screen_y > (200 - PH)) screen_y = (200 - PH);
            dsx = (u16)screen_x;
            dsy = (u16)screen_y;
        }

        // --- Restaurar fons del personatge al BACKBUFFER si estava dibuixat ---
        if (s_have_drawn[s_back_page]) {
            sprite_restore_player();
            s_have_drawn[s_back_page] = 0;
        }

        // --- Shift de VRAM i render de vores si hi ha hagut scroll ---
        if (move_x != 0 || move_y != 0) {
            if (move_x == 1) {
                scroll_shift_left_4();
                render_column(g_cam_col, g_cam_row, 19);
            } else if (move_x == -1) {
                scroll_shift_right_4();
                render_column(g_cam_col, g_cam_row, 0);
            }
            if (move_y == 1) {
                scroll_shift_up_8();
                render_row(g_cam_col, g_cam_row, 19);
            } else if (move_y == -1) {
                scroll_shift_down_8();
                render_row(g_cam_col, g_cam_row, 0);
            }
        }

        // --- Dibuix d'Sprite al BACKBUFFER (fora de pantalla, 0 flicker!) ---
        g_spr_y = (u8)dsy;
        g_spr_x = (u8)dsx;
        {
            const u8* spr_data = (s_face == 0) ? g_player_frames_r[cur].data : g_player_frames_l[cur].data;
            sprite_blit_player(spr_data);
        }
        s_have_drawn[s_back_page] = 1;

        // --- Sincronització amb VSYNC i Commutació de Pàgina de Vídeo (CRTC R12) ---
        cpc_wait_vsync_start();
        crtc_set_page(s_back_page == 1 ? 0x20 : 0x30);

        // --- Invertir pàgines: el que era front ara és backbuffer ---
        s_back_page ^= 1;
        g_backbuffer = (s_back_page == 1) ? (u8*)0x8000 : (u8*)0xC000;
        g_vram_base_hi = (s_back_page == 1) ? 0x80 : 0xC0;

        // Si hi ha hagut moviment de càmera en aquest frame, l'altre buffer
        // també ha de rebre el mateix desplaçament perquè tots dos quedin sincronitzats!
        if (move_x != 0 || move_y != 0) {
            if (s_have_drawn[s_back_page]) {
                sprite_restore_player();
                s_have_drawn[s_back_page] = 0;
            }
            if (move_x == 1) {
                scroll_shift_left_4();
                render_column(g_cam_col, g_cam_row, 19);
            } else if (move_x == -1) {
                scroll_shift_right_4();
                render_column(g_cam_col, g_cam_row, 0);
            }
            if (move_y == 1) {
                scroll_shift_up_8();
                render_row(g_cam_col, g_cam_row, 19);
            } else if (move_y == -1) {
                scroll_shift_down_8();
                render_row(g_cam_col, g_cam_row, 0);
            }
        }
    }
}
