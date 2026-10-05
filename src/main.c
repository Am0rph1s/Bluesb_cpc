// ============================================================
// BLUES BROTHERS CPC - Motor Mode 0 (fet des de zero)
// ============================================================
//   - video_init(): RMR Mode 0 + CRTC + paleta (protocol GA correcte)
//   - Scroll CRTC en ring de 16 KB, amb passos horitzontals de 4 px i render
//     incremental del caràcter/fila que entra.
//   - Física sub-pixel (1/8 px) com el motor de Titus (cyxx/blues)
//   - Sprite de Jake amb mascara + desat de fons (flicker-free)
// ============================================================

#include "cpctelera.h"
#include "fdc.h"
#include "disk_tables.h"
#include "sprite.h"
#include "moving.h"

extern void video_init(void);
extern void render_all(u16 cam_col, u16 cam_row);
extern void render_column(u16 cam_col, u16 cam_row, u16 sx);
extern void render_row(u16 cam_col, u16 cam_row, u16 sy);
extern void crtc_set_display_start(u16 ma);
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
#define START_PX    32
#define START_PY    1106
#define CAM0_X4     0
#define CAM0_ROW    124
#define PLAY_CHARS  40

static u16 g_cam_x4;
static u16 g_cam_row;

static i16 s_px8, s_py8;
static i16 s_vx, s_vy;
static u8  s_on_ground;
static i8  s_ground_elevator = -1;
static u8  s_face;
static u8  s_anim_idx, s_anim_timer;

static u8  s_have_drawn[2];
static i8  s_pending_x, s_pending_y;

static u8 s_back_page = 1;  // 1 -> pàgina B; 0 -> pàgina A

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

static u16 camera_ma(u16 x4, u16 row) {
    return (u16)((row * 40 + x4) & 0x03FF);
}

u8 level_get_tile_type(u16 col, u16 row) {
    u8 t, type;
    u16 off;
    if (col >= 128 || row >= 72) return 0;
    cpc_bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    off = (((u16)t) << 3) + (((u16)t) << 1);
    type = TRIG_PTR[off];
    cpc_bank_restore();
    return type;
}

// La pàgina que toca mostrar rep només les tires noves; la pàgina alterna es
// posa al dia al fotograma següent, abans de tornar-la a mostrar.
static void sync_backbuffer(i8 dx, i8 dy, u16 target_x4, u16 target_row) {
    u16 row_before = (u16)(target_row - dy);

    // move_x avança un caràcter CRTC (4 px); move_y avança un subtile (8 px).
    // El buffer altern pot anar un pas més endarrerit: dx/dy són [-2, 2].
    if (dx == 2) {
        render_column((u16)(target_x4 - 1), row_before, 39);
    }
    if (dx > 0) {
        render_column(target_x4, row_before, 39);
    } else if (dx == -2) {
        render_column((u16)(target_x4 + 1), row_before, 0);
    }
    if (dx < 0) {
        render_column(target_x4, row_before, 0);
    }

    if (dy == 2) {
        render_row(target_x4, (u16)(target_row - 1), 19);
    }
    if (dy > 0) {
        render_row(target_x4, target_row, 19);
    } else if (dy == -2) {
        render_row(target_x4, (u16)(target_row + 1), 0);
    }
    if (dy < 0) {
        render_row(target_x4, target_row, 0);
    }
}

void main(void) {
    cpc_install_isr();

    // Carregar fitxers directament als Bancs 4 i 5 de la RAM estesa de 128 KB
    if (!fdc_load_file(&g_file_tiles, 0xC4, (void*)0x4000) ||
        !fdc_load_file(&g_file_map,   0xC5, (void*)0x4000) ||
        !fdc_load_file(&g_file_trig,  0xC5, (void*)0x6400) ||
        !fdc_load_file(&g_file_pframes, PLAYER_FRAMES_BANK,
                       (void*)PLAYER_FRAMES_BASE)) {
        while (1) { }
    }

    video_init();
    // Netejar les dues pàgines de VRAM (0xC000 i 0x8000)
    cpct_memset((void*)0xC000, 0, 0x4000);
    cpct_memset((void*)0x8000, 0, 0x4000);

    g_cam_x4 = CAM0_X4;
    g_cam_row = CAM0_ROW;
    g_vram_start = camera_ma(g_cam_x4, g_cam_row);
    s_pending_x = 0;
    s_pending_y = 0;
    moving_init();

    // Inicialitzar la primera pàgina visible (0xC000)
    g_vram_base_hi = 0xC0;
    render_all(g_cam_x4, g_cam_row);
    moving_draw(0, g_cam_x4, g_cam_row);
    crtc_set_display_start((u16)(0x3000 + g_vram_start));

    // I preparar el backbuffer a 0x8000 amb el mateix fons
    g_vram_base_hi = 0x80;
    render_all(g_cam_x4, g_cam_row);
    moving_draw(1, g_cam_x4, g_cam_row);
    s_back_page = 1; // El proper frame actiu serà a 0x8000

    s_px8 = (i16)(START_PX * SUB);
    s_py8 = (i16)(START_PY * SUB);
    s_vx = 0; s_vy = 0;
    s_on_ground = 1; s_face = 0;
    s_anim_idx = 0; s_anim_timer = 0;
    s_have_drawn[0] = 0;
    s_have_drawn[1] = 0;

    while (1) {
        i8  move = 0;
        i8  move_x = 0;
        i8  move_y = 0;
        i8  page_dx, page_dy;
        u8  jump = 0;
        i16 px, py, effective_vx, belt_push;
        u16 dsx, dsy;

        moving_update();
        if (s_on_ground && s_ground_elevator >= 0) {
            MovingElevator* e = &g_mag_elevators[(u8)s_ground_elevator];
            px = (i16)(s_px8 >> 3);
            if (px + PW > e->center_x - ELEVATOR_HALF_W &&
                px < e->center_x + ELEVATOR_HALF_W) {
                s_py8 = (i16)(s_py8 + e->delta_y * SUB);
            } else {
                s_ground_elevator = -1;
                s_on_ground = 0;
            }
        }

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
        px = (i16)(s_px8 >> 3);

        belt_push = 0;
        if (s_on_ground) {
            u16 row = (u16)((py + PH) >> 4);
            u16 col0 = (u16)((px + 7) >> 3);
            u16 col1 = (u16)((px + 16) >> 3);
            belt_push = moving_conveyor_push(col0, col1, row);
            if (move == 0 && belt_push != 0) {
                move = belt_push > 0 ? 1 : -1;
                s_face = belt_push > 0 ? 0 : 1;
            }
        }
        effective_vx = (i16)(s_vx + belt_push);

        // --- Moviment horitzontal i col·lisió de parets 1:1 ---
        if (effective_vx > 0) {
            u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
            u16 c_right = (u16)((next_px + 18) >> 3);
            u16 r_waist = (u16)((py + 16) >> 4);
            u16 r_head  = (u16)(py >> 4);
            u8 fl = get_tile_flags(c_right, r_waist) |
                    get_tile_flags(c_right, r_head);
            if (fl & 1) {
                s_vx = 0;
                s_px8 = (i16)(((c_right << 3) - 19) * SUB);
            } else {
                s_px8 = (i16)(s_px8 + effective_vx);
            }
        } else if (effective_vx < 0) {
            u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
            u16 c_left  = (u16)((next_px + 5) >> 3);
            u16 r_waist = (u16)((py + 16) >> 4);
            u16 r_head  = (u16)(py >> 4);
            u8 fl = get_tile_flags(c_left, r_waist) |
                    get_tile_flags(c_left, r_head);
            if (fl & 2) {
                s_vx = 0;
                s_px8 = (i16)(((c_left << 3) + 8 - 5) * SUB);
            } else {
                s_px8 = (i16)(s_px8 + effective_vx);
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
                s_ground_elevator = -1;
            }

            s_py8 = (i16)(s_py8 + s_vy);
            py = (i16)(s_py8 >> 3);

            {
                i16 curr_feet = (i16)(py + PH);
                u16 c_mid1 = (u16)((px + 7) >> 3);
                u16 c_mid2 = (u16)((px + 16) >> 3);
                u8 landed = 0;

                if (s_vy >= 0) {
                    i16 elevator_top;
                    i8 elevator_id = moving_find_landing(px, prev_feet, curr_feet,
                                                        s_vy, &elevator_top);
                    if (elevator_id >= 0) {
                        py = elevator_top;
                        s_py8 = (i16)(py * SUB);
                        s_vy = 0;
                        s_on_ground = 1;
                        s_ground_elevator = elevator_id;
                        landed = 1;
                    }
                    u16 target_row = (u16)(curr_feet >> 4);
                    if (!landed && target_row < 72) {
                        i16 surf = (i16)(target_row << 4);
                        if (is_floor_solid(c_mid1, target_row, s_vy) || is_floor_solid(c_mid2, target_row, s_vy)) {
                            if (prev_feet <= (surf + 8) && curr_feet >= surf) {
                                py = (i16)(surf - PH);
                                s_py8 = (i16)(py * SUB);
                                s_vy = 0;
                                s_on_ground = 1;
                                s_ground_elevator = -1;
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
                                    s_ground_elevator = -1;
                                    landed = 1;
                                }
                            }
                        }
                    }
                    if (!landed) {
                        s_on_ground = 0;
                        s_ground_elevator = -1;
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
                    s_ground_elevator = -1;
                }
            }
        }

        // --- Camera: seguiment continu de personatge (estil C64 / Amiga) ---
        {
            i16 sy = (i16)(py - (i16)(g_cam_row * 8));
            i16 sx = (i16)(px - (i16)(g_cam_x4 * 4));
            if (sx > DEAD_R && g_cam_x4 < ((LEVEL_W_PX / 4) - PLAY_CHARS)) {
                g_cam_x4++;
                move_x = 1;
            } else if (sx < DEAD_L && g_cam_x4 > 0) {
                g_cam_x4--;
                move_x = -1;
            }

            if (sy > DEAD_B && g_cam_row < 124) {
                g_cam_row++;
                move_y = 1;
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
            i16 screen_x = (i16)((px - (i16)(g_cam_x4 * 4)) >> 1);
            i16 screen_y = (i16)(py - (i16)(g_cam_row * 8));
            if (screen_x < 0) screen_x = 0;
            if (screen_x > (80 - SPR_WB)) screen_x = (80 - SPR_WB);
            if (screen_y < 0) screen_y = 0;
            if (screen_y > (160 - PH)) screen_y = (160 - PH);
            dsx = (u16)screen_x;
            dsy = (u16)screen_y;
        }

        page_dx = (i8)(s_pending_x + move_x);
        page_dy = (i8)(s_pending_y + move_y);
        g_vram_start = camera_ma((u16)(g_cam_x4 - page_dx),
                                 (u16)(g_cam_row - page_dy));

        // --- Restaurar el fons del personatge al BACKBUFFER ---
        if (s_have_drawn[s_back_page]) {
            sprite_restore_player();
            s_have_drawn[s_back_page] = 0;
        }
        moving_restore(s_back_page, (move_x != 0 || move_y != 0));

        // Dibuixar les tires noves al ring buffer, sense copiar la pantalla.
        sync_backbuffer(page_dx, page_dy, g_cam_x4, g_cam_row);
        g_vram_start = camera_ma(g_cam_x4, g_cam_row);

        // Redraw moving objects over the updated background.
        moving_draw(s_back_page, g_cam_x4, g_cam_row);

        // --- Dibuix d'Sprite al BACKBUFFER (fora de pantalla, 0 flicker!) ---
        g_spr_y = (u8)dsy;
        g_spr_x = (u8)dsx;
        {
            const PSprFrame* frame = (s_face == 0) ?
                &g_player_frames_r[cur] : &g_player_frames_l[cur];
            u16 spr_addr = (u16)(PLAYER_FRAMES_BASE + frame->offset);
            cpc_bank_set(PLAYER_FRAMES_BANK);
            sprite_blit_player((const u8*)spr_addr);
            cpc_bank_restore();
        }
        s_have_drawn[s_back_page] = 1;

        // --- Sincronització amb VSYNC i Commutació de Pàgina de Vídeo (CRTC R12) ---
        cpc_wait_vsync_start();
        crtc_set_display_start((u16)((s_back_page == 1 ? 0x2000 : 0x3000) + g_vram_start));

        // --- Invertir pàgines: el que era front ara és backbuffer ---
        s_back_page ^= 1;
        g_vram_base_hi = (s_back_page == 1) ? 0x80 : 0xC0;
        s_pending_x = move_x;
        s_pending_y = move_y;
    }
}
