// ============================================================
// BLUES BROTHERS CPC - Motor Genèric Resident (Bloc 0)
// ============================================================
//   - video_init(): RMR Mode 0 + CRTC + paleta (protocol GA correcte)
//   - Scroll CRTC en ring de 16 KB, amb passos horitzontals de 4 px i render
//     incremental del caràcter/fila que entra.
//   - Doble buffer per maquinari (0xC000 / 0x8000) a 25 Hz sense flicker.
//   - Totes les dades específiques del nivell, ascensors, spans animats
//     (cintes + peixeres), efectes de tiles i reixes de primer pla viuen
//     al paquet del Banc 5 (src/moving_bank.c + src/level_pkg.h).
// ============================================================

#include "cpctelera.h"
#include "fdc.h"
#include "front.h"
#include "mus.h"
#include "disk_tables.h"
#include "sprite.h"
#include "moving.h"
#include "bank.h"
#include "player_frames.h"
#include "stack_canary.h"
#include "crt_addrs.h"

#define LEVEL_PKG_DEFS_ONLY
#include "level_pkg.h"

extern void video_init(void);
extern void render_all(u16 cam_col, u16 cam_row);
extern void render_column(u16 cam_col, u16 cam_row, u16 sx);
extern void render_row(u16 cam_col, u16 cam_row, u16 sy);
extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);
extern void hud_init(void);
extern void hud_render(u8 page, u8 force);
extern void crtc_set_display_start(u16 ma);
extern void cpc_install_isr(void);
extern volatile u8 g_ticks;

#define MAP_PTR     ((const u8*)0x4000)
#define TRIG_PTR    ((const u8*)0x6400)
#define PLAY_CHARS  40
#define SUB         8
#define PH          30
#define PW          16
#define SPR_WB      8
#define SPEED_MAX   30
#define SPEED_AIR   24
#define MOVE_ACC    7
#define VY_MAX      (15 * SUB)
#define GRAV        24
#define JUMP_VY     (-150)
#define DEAD_L      48
#define DEAD_R      88
#define DEAD_T      32
#define DEAD_B      116
#define CRATE_FLY_FRAME ((const u8*)0x7AA0)

static const u8 s_crate_walk[4] = { 14, 12, 13, 15 };
static const u8 s_walk[6] = { 1, 2, 0, 3, 2, 0 };

// Estat compartit resident (actualitzat des del mòdul de nivell al Banc 5):
u16 g_cam_x4;
u16 g_cam_row;

i16 s_px8, s_py8;
i16 s_vx, s_vy;
u8  s_on_ground;
u8  s_jump_prev;
u8  s_climb_prev;
u8  s_carry_kind;
u8  s_grab_prev;
u8  s_carry_state;
i16 s_carry_x, s_carry_y;
i16 s_carry_vx;
u8  s_carry_drawn[2];
static i16 s_carry_dx[2], s_carry_dy[2];
static u8  s_crate_bg[2][64];

i8  s_ground_elevator = -1;
u8  g_face;
u8  s_anim_idx, s_anim_timer;

static u8  s_have_drawn[2];
static i8  s_pending_x, s_pending_y;

u8  s_rep_n;
u8  s_rep_col[3], s_rep_row[3], s_rep_tile[3], s_rep_pages[3];

static u8 s_back_page = 1;

void main(void);

const u16 g_crc_fdc = CRC_FDC; // stub FDC: verifica l'scratch (moving.c)
const u16 g_len_fdc = 785; // FDC.BIN sencer (sense header); ha de coincidir
                           // amb l'obj generat (si el motor creix i el CRC
                           // falla -> white-hang: actualitzar aqui)

void start(void) {
    __asm
        ld      sp, #0x3FFE
    __endasm;
    main();
}

static u8 tile_flags(u16 col, u16 row) {
    u8 prev, t, f;
    if (col >= LEVEL_MAP_W || row >= LEVEL_MAP_H) return 0;
    prev = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    f = TRIG_PTR[(((u16)t) << 3) + (((u16)t) << 1) + 1];
    bank_restore(prev);
    return f;
}

static u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch) {
    u8 prev, t, op;
    if (row >= (LEVEL_MAP_H - 1)) return (vy >= 0);
    if (col >= LEVEL_MAP_W) return 0;
    prev = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    op = TRIG_PTR[(((u16)t) << 3) + (((u16)t) << 1) + 2];
    bank_restore(prev);
    if (op == 20 || op == 21 || op == 27 || op == 28) return 1;
    if (vy >= 0) {
        if (op == 14 || op == 15) return !crouch;
        if (op >= 31 && op <= 39) return 1;
    }
    return 0;
}

#define is_ceiling_solid(col, row) is_floor_solid((col), (row), -1, 0)

static void world_flush_repaints(void) {
    u8 i = 0;
    while (i < s_rep_n) {
        if (s_rep_pages[i] & (u8)((u8)1 << s_back_page)) {
            render_tile_world(s_rep_tile[i], s_rep_col[i], s_rep_row[i],
                              g_cam_x4, g_cam_row);
            s_rep_pages[i] &= (u8)~((u8)1 << s_back_page);
        }
        if (s_rep_pages[i] == 0) {
            s_rep_n--;
            if (i != s_rep_n) {
                s_rep_col[i] = s_rep_col[s_rep_n];
                s_rep_row[i] = s_rep_row[s_rep_n];
                s_rep_tile[i] = s_rep_tile[s_rep_n];
                s_rep_pages[i] = s_rep_pages[s_rep_n];
            }
        } else {
            i++;
        }
    }
}

static u16 camera_ma(u16 x4, u16 row) {
    return (u16)((row * 40 + x4) & 0x03FF);
}

static void sync_backbuffer(i8 dx, i8 dy, u16 target_x4, u16 target_row) {
    u16 row_before = (u16)(target_row - dy);

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

    if (dy > 0) {
        i8 k;
        for (k = 0; k < dy; k++) {
            render_row(target_x4, (u16)(target_row - k), 19);
        }
    } else if (dy < 0) {
        i8 k;
        for (k = 0; k < -dy; k++) {
            render_row(target_x4, (u16)(target_row + k), 0);
        }
    }
}

static void carry_restore(u8 page) {
    u8 r;
    if (!s_carry_drawn[page]) return;
    for (r = 0; r < 16; r++) {
        g_moving_dst = (u16)ring_address(page, s_carry_dx[page], (i16)(s_carry_dy[page] + r));
        g_moving_background = (u16)(s_crate_bg[page] + ((u16)r << 2));
        g_moving_span = 4;
        moving_restore_span();
    }
    s_carry_drawn[page] = 0;
}

static void carry_fly_draw(u8 page) {
    i16 cx, cy;
    u8 prev, r;
    if (s_carry_kind != 1 || !s_carry_state) return;
    cx = (i16)(s_carry_x >> 3);
    cy = (i16)(s_carry_y >> 3);
    prev = bank_set(0xC7);
    for (r = 0; r < 16; r++) {
        g_moving_dst = (u16)ring_address(page, cx, (i16)(cy + r));
        g_moving_background = (u16)(s_crate_bg[page] + ((u16)r << 2));
        g_moving_sprite = (u16)(CRATE_FLY_FRAME + ((u16)r << 3));
        g_moving_span = 4;
        moving_blit_span();
    }
    bank_restore(prev);
    s_carry_drawn[page] = 1;
    s_carry_dx[page] = cx;
    s_carry_dy[page] = cy;
}

void carry_abort(void) {
    carry_restore(s_back_page);
    carry_restore((u8)(s_back_page ^ 1));
    sprite_abort_balloon();
    s_carry_kind = 0;
    s_carry_state = 0;
}

static u8 select_player_anim(u8 climbing, i8 move, u8 jump, u8 crouch, i16 bsy) {
    if (s_dance_timer) {
        return (s_dance_timer & 4) ? 10 : 11;
    }
    if (climbing == 1) {
        if (jump || crouch || move != 0) {
            s_anim_timer++;
            if (s_anim_timer >= 6) {
                s_anim_timer = 0;
                s_anim_idx ^= 1;
            }
            return s_anim_idx ? 5 : 9;
        }
        s_anim_timer = 0;
        return 5;
    }
    if (climbing == 2) {
        if (move != 0) {
            s_anim_timer++;
            if (s_anim_timer >= 4) {
                s_anim_timer = 0;
                s_anim_idx++;
                if (s_anim_idx >= 3) s_anim_idx = 0;
            }
            return (u8)(21 + s_anim_idx);
        }
        if (jump || crouch) {
            s_anim_timer++;
            if (s_anim_timer >= 4) {
                s_anim_timer = 0;
                s_anim_idx ^= 1;
            }
            return s_anim_idx ? 24 : 21;
        }
        s_anim_timer = 0;
        return s_on_ground ? 25 : 21;
    }
    if (s_carry_kind == 2) {
        return 20;
    }
    if ((s_carry_kind == 1 && !s_carry_state) || s_carry_kind == 8) {
        if (s_carry_kind == 1 && !s_on_ground) return 16;
        if (move != 0) {
            s_anim_timer++;
            if (s_anim_timer >= 2) {
                s_anim_timer = 0;
                s_anim_idx++;
                if (s_anim_idx >= 4) s_anim_idx = 0;
            }
            return s_crate_walk[s_anim_idx];
        }
        return (s_carry_kind == 8) ? 20 : 13;
    }
    if (!s_on_ground || (u16)(bsy + 30) > 160) {
        return 4;
    }
    if (crouch) {
        if (move != 0) {
            s_anim_timer++;
            if (s_anim_timer >= 6) {
                s_anim_timer = 0;
                s_anim_idx ^= 1;
            }
            return s_anim_idx ? 8 : 7;
        }
        s_anim_timer = 0;
        return 6;
    }
    if (move != 0) {
        s_anim_timer++;
        if (s_anim_timer >= 2) {
            s_anim_timer = 0;
            s_anim_idx++;
            if (s_anim_idx >= 6) s_anim_idx = 0;
        }
        return s_walk[s_anim_idx];
    }
    s_anim_idx = 0;
    s_anim_timer = 0;
    return 0;
}

static void player_physics_step(i16 belt_push, u8 climbing, u8 jump, u8 crouch) {
    i16 px = (i16)(s_px8 >> 3);
    i16 py = (i16)(s_py8 >> 3);
    i16 effective_vx = (i16)(s_vx + belt_push);

    if (s_carry_kind == 1 && s_carry_state) {
        i16 cx, cy, sx, sy;
        u16 ncol, nrow;
        s_carry_x = (i16)(s_carry_x + s_carry_vx);
        cx = (i16)(s_carry_x >> 3); cy = (i16)(s_carry_y >> 3);
        sx = (i16)((cx - (i16)(g_cam_x4 * 4)) >> 1);
        sy = (i16)(cy - (i16)(g_cam_row * 8));
        ncol = (u16)(((s_carry_vx > 0) ? (cx + 8) : (cx - 1)) >> 3);
        nrow = (u16)((cy + 8) >> 4);
        if (sx < 0 || sx > 72 || sy < 0 || sy > 144 || is_floor_solid(ncol, nrow, 0, 0)) {
            carry_abort();
        }
    }

    // --- Moviment horitzontal i col·lisió de parets ---
    if (effective_vx > 0) {
        u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
        u16 c_right = (u16)((next_px + 10) >> 3);
        u8 fl = tile_flags(c_right, (u16)((py + 16) >> 4)) |
                tile_flags(c_right, (u16)(py >> 4));
        if (fl & 1) {
            s_vx = 0;
            s_px8 = (i16)(((c_right << 3) - 11) * SUB);
        } else {
            s_px8 = (i16)(s_px8 + effective_vx);
        }
    } else if (effective_vx < 0) {
        u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
        u16 c_left  = (u16)((next_px + 1) >> 3);
        u8 fl = tile_flags(c_left, (u16)((py + 16) >> 4)) |
                tile_flags(c_left, (u16)(py >> 4));
        if (fl & 2) {
            s_vx = 0;
            s_px8 = (i16)(((c_left << 3) + 8 - 1) * SUB);
        } else {
            s_px8 = (i16)(s_px8 + effective_vx);
        }
    }
    if (s_px8 < 0) { s_px8 = 0; s_vx = 0; }
    if (s_px8 > (i16)((LEVEL_W_PX - PW) * SUB)) { s_px8 = (i16)((LEVEL_W_PX - PW) * SUB); s_vx = 0; }
    px = (i16)(s_px8 >> 3);

    // --- Moviment vertical i gravetat ---
    {
        i16 prev_feet = (i16)(py + PH);
        u16 prev_head = (u16)(py >> 4);
        if (!climbing) {
            if (s_carry_kind == 2) {
                s_vy = -8;
                s_on_ground = 0;
                s_ground_elevator = -1;
            } else {
                if (!s_on_ground) {
                    s_vy = (i16)(s_vy + GRAV);
                    if (s_vy > VY_MAX) s_vy = VY_MAX;
                } else {
                    s_vy = 0;
                }
                if (jump && !s_jump_prev && s_on_ground) {
                    s_vy = (s_carry_kind == 1 && !s_carry_state) ? -96 : JUMP_VY;
                    s_on_ground = 0;
                    s_ground_elevator = -1;
                }
                if (s_carry_kind == 8 && s_vy > 8) s_vy = 8;
            }
        }
        s_jump_prev = jump;

        s_py8 = (i16)(s_py8 + s_vy);
        py = (i16)(s_py8 >> 3);

        {
            i16 curr_feet = (i16)(py + PH);
            u16 c_mid1 = (u16)((px + 3) >> 3);
            u16 c_mid2 = (u16)((px + 8) >> 3);
            u8 landed = 0;

            if (s_vy >= 0 && climbing != 1) {
                i16 elevator_top;
                i8 elevator_id;
                bc_a = (u16)px; bc_b = (u16)prev_feet; bc_c = (u16)curr_feet;
                bc_d = (u16)s_vy; bc_e = (u16)&elevator_top;
                elevator_id = moving_find_landing();
                if (elevator_id >= 0) {
                    py = elevator_top;
                    s_py8 = (i16)(py * SUB);
                    s_vy = 0;
                    s_on_ground = 1;
                    s_ground_elevator = elevator_id;
                    landed = 1;
                }
                {
                    u16 target_row = (u16)(curr_feet >> 4);
                    if (!landed && target_row < LEVEL_MAP_H) {
                        i16 surf = (i16)(target_row << 4);
                        if (is_floor_solid(c_mid1, target_row, s_vy, crouch) ||
                            is_floor_solid(c_mid2, target_row, s_vy, crouch)) {
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
                }
                if (!landed) {
                    u16 feet_under = (u16)((curr_feet + 1) >> 4);
                    if (feet_under < LEVEL_MAP_H) {
                        i16 surf_u = (i16)(feet_under << 4);
                        if (is_floor_solid(c_mid1, feet_under, s_vy, crouch) ||
                            is_floor_solid(c_mid2, feet_under, s_vy, crouch)) {
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
            } else if (s_vy < 0) {
                u16 head_row = (u16)(py >> 4);
                u16 c_mid = (u16)((px + 5) >> 3);
                u16 r = prev_head;
                u8 n = 0;
                while (r >= head_row && n < 4) {
                    if (is_ceiling_solid(c_mid, r)) {
                        head_row = r;
                        break;
                    }
                    if (r == 0) break;
                    r--; n++;
                }
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
}

// (zx0_decompress viu al FRONT.BIN banked; el GAME no el toca.)

// FRONT banked (C4:0x4000): args centrals + crida absoluta (patro motor).
// El TILESET sobreescriu C4 quan acaben les 3 pantalles.
FrontArgs g_front_args;
u8 g_mus_ready = 0; // 1 = player iniciat (la ISR pot sonar). 0 fins al
                    // primer mus_init: evita Play sobre C1 buit (reboot).
static void front_one(const DiskFileDesc* d, const u8* palhw, u8 load_mus) {
    u8 prev;
    g_front_args.home = 0xC4;
    g_front_args.desc = d;
    g_front_args.palhw = palhw;
    g_front_args.musbank = &g_file_musbank;
    g_front_args.load_mus = load_mus;
    prev = bank_set(0xC4);
    ((void(*)(void))FRONT_RUN)();
    bank_restore(prev);
}

void main(void) {
    cpct_memset((void*)CRT_DATA_START, 0, CRT_DATA_LEN);
    cpct_memcpy((void*)CRT_IDATA_DST, (void*)CRT_IDATA_SRC, CRT_IDATA_LEN);
    stack_canary_init();
    cpc_install_isr();

    // MUSICA (C1): C1 NO es pot paginar des de l'starter (viu a slot 3:
    // config C1 mapeja slot3->banc7 i l'starter desapareix = reboot) ni
    // directament des del FRONT (viu a slot 1: desapareix igual). El FRONT
    // (splash, load_mus=1) el carrega via stub central (trampoli segur),
    // muda cada lectura d'imatge (stop+HOLD) i inicia la intro despres
    // (mus_init EQU). Al foc del mapa: stop+HOLD fins al tema del nivell
    // (mus_init#2 post-carregues).

    // FRONT: SPLASH -> SELECT -> MAP (banked C4, args centrals). El display
    // apunta a 0xC000 (firmware), Mode 0 (starter): el depack hi es visible.
    // Nomes l'splash carrega MUSBANK (load_mus=1); els altres el reutilitzen.
    front_one(&g_file_fsplash, g_pal_fsplash, 1);
    front_one(&g_file_fselect, g_pal_fselect, 0);
    front_one(&g_file_fmap, g_pal_fmap, 0);

    // FOC AL MAPA = MUSICA FORA (HW real 13/10/26: les 8 carregues del
    // nivell amb la ISR sonant fan nota suspesa/interferencia, dramatic).
    // mus_stop = silenci immediat + HOLD = la ISR no fa Play (l'AKG
    // reprendria el so al tick seguent). El tema arrenca post-carregues.
    mus_stop();
    g_mus_hold = 1;

    // Carregar recursos del nivell als Bancs 4/5/7 amb verificació CRC16
    // (+ MUSMAIN a C1:0x5000: el tema del nivell 1). CRC inline (el helper
    // banked moria per ordre de carregues: slot2 encara no resident).
    {
        static const u8 v_bank[8] = { 0xC4, 0xC5, 0xC5, 0xC7, 0xC7, 0xC7, 0xC5, 0xC1 };
        static const u16 v_addr[8] = { 0x4000, 0x4000, 0x6400, 0x4000, 0x7AA0, 0x78E0, 0x6E00, 0x5000 };
        static const u16 v_crc[8] = { CRC_TILES, CRC_MAP, CRC_TRIG, CRC_PFRAMES, CRC_EXTRA, CRC_ELEV, CRC_BANK5, CRC_MUSMAIN };
        static const DiskFileDesc* const v_desc[8] = { &g_file_tiles, &g_file_map, &g_file_trig, &g_file_pframes, &g_file_extra, &g_file_elev, &g_file_bank5, &g_file_musmain };
        u8 i, t;
        // LOOP MUT (ve de dalt: stop+HOLD al foc del mapa). El motor nomes
        // toca HOLD en C1 (simetric); re-assegurem HOLD=1 despres de cada
        // lectura (la de MUSMAIN el netejaria en sortir i la ISR faria un
        // Play sobre canco no-iniciada abans del mus_init).
        for (i = 0; i < 8; i++) {
            u8 ok = 0;
            for (t = 0; t < 3 && !ok; t++) {
                u8 prev;
                // Home 0xC0: el GAME corre en central (mai paginat).
                if (!fdc_load_file(0xC0, v_desc[i], v_bank[i], (void*)v_addr[i])) continue;
                g_mus_hold = 1;
                prev = bank_set(v_bank[i]);
                if (fdc_crc16((const u8*)v_addr[i],
                              (u16)(v_desc[i]->ondisk_bytes - 128)) == v_crc[i]) ok = 1;
                bank_restore(prev);
            }
            if (!ok) { cpct_setBorder((u8)(0x40 + i)); while (1) { } }
        }
    }

    // MUSICA nivell 1: MUSMAIN ja es a l'slot C1:0x5000: obrir so i
    // (re)iniciar el tema.
    g_mus_hold = 0;
    mus_init();

    video_init();

    {
        u8 prev = bank_set(0xC7);
        sprite_hflip_init_lut((u8*)0x7F00);
        bank_restore(prev);
    }

    cpct_memset((void*)0xC000, 0xFF, 0x4000);
    cpct_memset((void*)0x8000, 0xFF, 0x4000);
    // Blindatge: si l'HOLD arriba a 1 fins aqui (p.ex. load interromput),
    // la ISR no sonaria mai mes. Cost 0, musica en 20 ms.
    g_mus_hold = 0;

    // Inicialitza posició d'inici, càmera i entitats des del paquet de nivell (Banc 5)
    moving_init();
    hud_init();
    g_vram_start = camera_ma(g_cam_x4, g_cam_row);
    s_pending_x = 0;
    s_pending_y = 0;

    g_vram_base_hi = 0xC0;
    render_all(g_cam_x4, g_cam_row);
    hud_render(0, 1);
    moving_draw(0, g_cam_x4, g_cam_row);
    crtc_set_display_start((u16)(0x3000 + g_vram_start));

    g_vram_base_hi = 0x80;
    render_all(g_cam_x4, g_cam_row);
    hud_render(1, 1);
    moving_draw(1, g_cam_x4, g_cam_row);
    s_back_page = 1;

    s_vx = 0; s_vy = 0;
    s_on_ground = 1; g_face = 0;
    s_jump_prev = 0; s_climb_prev = 0;
    s_carry_kind = 0; s_grab_prev = 0;
    s_carry_state = 0; s_carry_drawn[0] = 0; s_carry_drawn[1] = 0;
    s_anim_idx = 0; s_anim_timer = 0;
    s_have_drawn[0] = 0;
    s_have_drawn[1] = 0;
    sprite_balloon_init();
    u8 last_ticks = g_ticks;

    while (1) {
        if (!stack_canary_ok()) {
            cpct_setBorder(0x4C);
        }
        i8 move = 0, move_x = 0, move_y = 0, page_dx, page_dy;
        u8 jump = 0, crouch = 0, grab = 0, cur;
        u16 dsx, dsy;

        cpct_scanKeyboard_f();
        if (cpct_isKeyPressed(Key_CursorLeft) || cpct_isKeyPressed(Key_Q) ||
            cpct_isKeyPressed(Joy0_Left))  { move = -1; g_face = 1; }
        if (cpct_isKeyPressed(Key_CursorRight) || cpct_isKeyPressed(Key_S) ||
            cpct_isKeyPressed(Joy0_Right)) { move = +1; g_face = 0; }
        if (cpct_isKeyPressed(Key_Space) || cpct_isKeyPressed(Key_X) ||
            cpct_isKeyPressed(Joy0_Fire1) || cpct_isKeyPressed(Joy0_Fire2)) { grab = 1; }
        if (cpct_isKeyPressed(Key_CursorDown) || cpct_isKeyPressed(Key_Z) ||
            cpct_isKeyPressed(Joy0_Down))  { crouch = 1; }
        if ((cpct_isKeyPressed(Key_CursorUp) || cpct_isKeyPressed(Joy0_Up)) &&
            !grab) { jump = 1; }

        // Acceleració horitzontal
        {
            i16 max_spd = s_on_ground ? SPEED_MAX : SPEED_AIR;
            if (move > 0)      { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx >  max_spd) s_vx =  max_spd; }
            else if (move < 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < -max_spd) s_vx = -max_spd; }
            else {
                if (s_vx > 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < 0) s_vx = 0; }
                else if (s_vx < 0) { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx > 0) s_vx = 0; }
            }
        }

        // 1. Lògica d'entitats i efectes de tiles al Banc 5 (ascensors, aigua, escala, objectes)
        bc_b = jump;
        bc_c = crouch;
        bc_d = grab;
        moving_update();

        if (s_on_ground && s_ground_elevator >= 0) {
            MovingElevator* e = &g_mag_elevators[(u8)s_ground_elevator];
            i16 px = (i16)(s_px8 >> 3);
            if (px + PW > e->center_x - ELEVATOR_HALF_W &&
                px < e->center_x + ELEVATOR_HALF_W) {
                s_py8 = (i16)(s_py8 + e->delta_y * SUB);
            } else {
                s_ground_elevator = -1;
                s_on_ground = 0;
            }
        }

        // 2. Pas de física genèrica de col·lisió sòlida al motor resident
        player_physics_step(bc_r, s_climb_prev, jump, crouch);

        // 3. Càmera i deadzone
        {
            i16 px = (i16)(s_px8 >> 3);
            i16 py = (i16)(s_py8 >> 3);
            i16 sy = (i16)(py - (i16)(g_cam_row * 8));
            i16 sx = (i16)(px - (i16)(g_cam_x4 * 4));
            if (sx > DEAD_R && g_cam_x4 < ((LEVEL_W_PX / 4) - PLAY_CHARS)) {
                g_cam_x4++;
                move_x = 1;
            } else if (sx < DEAD_L && g_cam_x4 > 0) {
                g_cam_x4--;
                move_x = -1;
            }
            if (sy > DEAD_B && g_cam_row < LEVEL_MAX_CAM_ROW) {
                g_cam_row++;
                move_y = 1;
            } else if (sy < DEAD_T && g_cam_row > 0) {
                g_cam_row--;
                move_y = -1;
            }
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
        }

        page_dx = (i8)(s_pending_x + move_x);
        page_dy = (i8)(s_pending_y + move_y);
        g_vram_start = camera_ma((u16)(g_cam_x4 - page_dx),
                                 (u16)(g_cam_row - page_dy));

        // --- Restaurar el fons al BACKBUFFER (LIFO) ---
        sprite_restore_umbrella();
        sprite_restore_balloon();
        if (s_have_drawn[s_back_page]) {
            sprite_restore_player();
            s_have_drawn[s_back_page] = 0;
        }
        moving_restore(s_back_page, (move_x != 0 || move_y != 0));
        carry_restore(s_back_page);
        moving_popup_restore(s_back_page);
        world_flush_repaints();

        // Actualitzar tires d'scroll i spans animats del nivell + reixes de primer pla al Banc 5
        sync_backbuffer(page_dx, page_dy, g_cam_x4, g_cam_row);
        g_vram_start = camera_ma(g_cam_x4, g_cam_row);
        hud_render(s_back_page, (page_dx != 0 || page_dy != 0));
        bc_a = s_back_page;
        moving_draw_conveyor_tiles();
        cur = select_player_anim(s_climb_prev, move, jump, crouch, (i16)dsy);

        // Dibuixar objectes mòbils i sprites sobre el fons actualitzat
        moving_draw(s_back_page, g_cam_x4, g_cam_row);
        carry_fly_draw(s_back_page);

        g_spr_y = (u8)dsy;
        g_spr_x = (u8)dsx;

        {
            u16 spr_addr = (u16)(PLAYER_FRAMES_BASE + ((u16)cur << 9) - ((u16)cur << 5));
            const u8* fr_addr = (const u8*)spr_addr;
            u8 prev_b = bank_set(PLAYER_FRAMES_BANK);
            // Contracte hflip (verificat en viu): C7 paginat als dos costats.
            // flip escriu i blit llegeix C7:0x7700 (gap lliure 0x7120-0x78E0,
            // 480 B justos fins ELEV); la LUT es llegeix de C7:0x7F00 (B=0x7F).
            // NO cridar amb un altre banc paginat (llegiria LUT/dest brossa).
            if (g_face == 0) {
                sprite_blit_player(fr_addr);
            } else {
                sprite_hflip(fr_addr, (u8*)0x7700);
                sprite_blit_player((const u8*)0x7700);
            }
            bank_restore(prev_b);
        }
        s_have_drawn[s_back_page] = 1;
        if (s_carry_kind == 2) sprite_blit_balloon();
        else if (s_carry_kind == 8) sprite_blit_umbrella();

        // --- Sincronització fixa a 25 Hz (12 ticks = 40 ms) i canvi de pàgina ---
        while ((u8)(g_ticks - last_ticks) < 12) {
        }
        last_ticks = g_ticks;

        // MUSICA: la porta la ISR (50 Hz exactes, independent del frame
        // rate: moure en Jake ja no canvia el tempo). Res a fer aqui.

        cpc_wait_vsync_start();
        crtc_set_display_start((u16)((s_back_page == 1 ? 0x2000 : 0x3000) + g_vram_start));

        s_back_page ^= 1;
        g_vram_base_hi = (s_back_page == 1) ? 0x80 : 0xC0;
        s_pending_x = move_x;
        s_pending_y = move_y;
    }
}
