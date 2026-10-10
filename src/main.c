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
#include "bank.h"

extern void video_init(void);
extern void render_all(u16 cam_col, u16 cam_row);
extern void render_column(u16 cam_col, u16 cam_row, u16 sx);
extern void render_row(u16 cam_col, u16 cam_row, u16 sy);
extern void crtc_set_display_start(u16 ma);
extern void cpc_install_isr(void);
extern volatile u8 g_ticks;

#define SUB         8
#define PH          30
#define PW          16
#define SPR_WB      8
// Paritat DOS 30Hz -> CPC 25Hz (factor 1.2, distàncies en tiles idèntiques):
// DOS: xmax=48 (6px/f), grav=2, salt v0=-14 => 56px alt, 84px DOS (=42px M0) llarg.
// M0 halva X (320->160): 3px/f DOS = 3.6px/f @25Hz => SPEED_MAX 30 (3.75px/f).
#define SPEED_MAX   30
#define SPEED_AIR   24
#define MOVE_ACC    7
#define VY_MAX      (15 * SUB)
#define GRAV        24
#define JUMP_VY     (-150)

#define LEVEL_W_PX  (128 * 8)
#define DEAD_L      48
#define DEAD_R      88
#define DEAD_T      32
#define DEAD_B      116
#define START_PX 184
#define START_PY 860
#define CAM0_X4     0
#define CAM0_ROW    124
#define PLAY_CHARS  40

static u16 g_cam_x4;
static u16 g_cam_row;

static i16 s_px8, s_py8;
static i16 s_vx, s_vy;
static u8  s_on_ground;
static u8  s_jump_prev;
static u8  s_climb_prev;
// Carry (obj37 DOS): 0=res, 1=caixa, 2=globus, 8=paraigua (grab_type DOS).
static u8  s_carry_kind;
static u8  s_grab_prev;
// Vol caixa llançada (estat 1): recte sense gravetat (DOS yacc=0).
static u8  s_carry_state;
static i16 s_carry_x, s_carry_y; // SUB
static i16 s_carry_vx;           // SUB/f (±154 = DOS ±128 @30Hz)
static u8  s_carry_drawn[2];
static i16 s_carry_dx[2], s_carry_dy[2]; // world px dibuixats (restore), PER PAGINA
static u8  s_crate_bg[2][64];      // fons 4B x 16 linies x 2 pagines
// Globus portat (visual DOS obj37): sobre 8x16 del TILESET (cella 156)
// convertit a parells [inv=0,img] al grab; segueix en Jake a (px+4,py-17).
// El fons fa servir s_crate_bg (excloent amb la caixa volant: kind es unic).
// Seqüència caminar amb caixa DOS 00cd = [15,13,14,16] -> índexs nostres.
static const u8 g_crate_walk[4] = { 14, 12, 13, 15 };
static i8  s_ground_elevator = -1;
u8 g_face;
static u8  s_anim_idx, s_anim_timer;

static u8  s_have_drawn[2];
static i8  s_pending_x, s_pending_y;
// Repintats pendents de tiles mutats (forats de reset): el restore del
// fons de l'sprite (stale) taparia el repintat si es fes a l'input; per
// aixo s'encua i es pinta DESPRES del restore, abans del save+draw.
// (max 2/frame: globus/paraigua; 3 per marge). pages = bitmask 0b11.
static u8  s_rep_n;
static u8  s_rep_col[3], s_rep_row[3], s_rep_tile[3], s_rep_pages[3];

static u8 s_back_page = 1;  // 1 -> pàgina B; 0 -> pàgina A

// Sequencia de caminar original de Titus 1.EXE: [2, 0, 1, 3, 0, 1]
// Mapat als frames: 1(walk1/DOS 2), 2(walk2/DOS 0), 0(idle/DOS 1), 3(walk3/DOS 3)
static const u8 g_walk[6] = { 1, 2, 0, 3, 2, 0 };

#include "player_frames.h"
#include "stack_canary.h"
#include "crt_addrs.h"

void main(void);

void start(void) {
    __asm
        ld      sp, #0x3FFE
    __endasm;
    main();
}

#define MAP_PTR   ((const u8*)0x4000)
#define MAP_MUT   ((u8*)0x4000)
#define TRIG_PTR  ((const u8*)0x6400)

extern void render_tile_world(u8 tile_index, u16 col, u16 row,
                              u16 cam_x4, u16 cam_row);

static void world_set_tile(u16 col, u16 row, u8 tile); // definit a sota

// Llegeix el NUMERO de tile actual (veu mutacions: forats, portes).
static u8 get_tile_num(u16 col, u16 row) {
    u8 t, prev_b;
    if (col >= 128 || row >= 72) return 0;
    prev_b = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    bank_restore(prev_b);
    return t;
}

// DOS do_level_reset_tiles: el forat NO va a tile 0 (blau lleig); s'omple
// amb el primer tile de la dreta amb next-num diferent (amb next-nums
// identitat = primer numero diferent: el fons gris s'esten sobre el forat).
static void world_reset_tile(u16 col, u16 row) {
    u8 n, m = 0;
    u16 c;
    if (col >= 128 || row >= 72) return;
    n = get_tile_num(col, row);
    c = (u16)(col + 1);
    while (c < 128) {
        m = get_tile_num(c, row);
        if (m != n) break;
        c++;
    }
    if (c >= 128) return; // sense veí: no tocar (DOS llegiria fora fila)
    world_set_tile(col, row, m);
}

// Marca una casella del mapa (MAP_MUT, logic immediat) i encua el seu
// repintat a les DUES pagines VRAM. El repintat es fa a la fase de draw
// (world_flush_repaints, despres del restore d'sprites, amb camera fresca)
// perque el fons desat (stale, amb la caixa) no el Ressusciti.
static void world_set_tile(u16 col, u16 row, u8 tile) {
    u8 prev_b;
    if (col >= 128 || row >= 72) return;
    prev_b = bank_set(0xC5);
    MAP_MUT[(row << 7) + col] = tile;
    bank_restore(prev_b);
    if (s_rep_n < 3) {
        s_rep_col[s_rep_n] = (u8)col;
        s_rep_row[s_rep_n] = (u8)row;
        s_rep_tile[s_rep_n] = tile;
        s_rep_pages[s_rep_n] = 3;
        s_rep_n++;
    } else {
        // Ple (no hauria de passar: max 2/frame): repintat immediat antic.
        u8 save_hi = g_vram_base_hi;
        g_vram_base_hi = 0xC0;
        render_tile_world(tile, col, row, g_cam_x4, g_cam_row);
        g_vram_base_hi = 0x80;
        render_tile_world(tile, col, row, g_cam_x4, g_cam_row);
        g_vram_base_hi = save_hi;
    }
}

// Pinta els repintats pendents de la pagina back (g_vram_base_hi ja hi
// apunta). Crida despres dels restores i abans del save+draw d'sprites.
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

// NOTA: get_tile() eliminat (mort, mai cridat) per recuperar ~30B de _CODE
// després del reescalat DOS 30Hz->25Hz. get_tile_flags/op segueixen intactes.

static u8 get_tile_flags(u16 col, u16 row) {
    u8 t, fl, prev_b;
    u16 off;
    if (col >= 128 || row >= 72) return 0;
    prev_b = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    off = (((u16)t) << 3) + (((u16)t) << 1);
    fl = TRIG_PTR[off + 1];
    bank_restore(prev_b);
    return fl;
}

static u8 get_tile_op(u16 col, u16 row) {
    u8 t, op, prev_b;
    u16 off;
    if (col >= 128 || row >= 72) return 0;
    prev_b = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    off = (((u16)t) << 3) + (((u16)t) << 1);
    op = TRIG_PTR[off + 2];
    bank_restore(prev_b);
    return op;
}

u8 level_get_tile_type(u16 col, u16 row); // definit a sota (usat per is_floor_solid)

// Sòls DOS: bidireccionals (peus+cap) 20,21,27,28 (+0,1,2,29,40 altres nivells).
// One-way DOS (només peus quan vy>=0 + DROP amb avall): 14,15 (+16,22,30,31-39).
static u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch) {
    u8 op;
    if (row >= 71) return 1;
    op = get_tile_op(col, row);
    if (op == 20 || op == 21 || op == 27 || op == 28) return 1;
    if (vy >= 0 && (op == 14 || op == 15)) {
        // DROP-THROUGH (unk2B DOS): avall travessa TOTES les one-way,
        // caixes incloses (s'agafen des de terra, mai des de sobre).
        if (crouch) return 0;
        return 1; // caixa = plataforma (s'hi pot estar dret)
    }
    if (op >= 31 && op <= 39 && vy >= 0) return 1;
    return 0;
}

static u8 is_ceiling_solid(u16 col, u16 row) {
    u8 op;
    if (row >= 72) return 0;
    op = get_tile_op(col, row);
    // DOS: 20,21,27,28 (+0,1,2,29,40). 14/15 = one-way (cap amunt lliure).
    if (op == 20 || op == 21 || op == 27 || op == 28) return 1;
    return 0;
}

static u16 camera_ma(u16 x4, u16 row) {
    return (u16)((row * 40 + x4) & 0x03FF);
}

u8 level_get_tile_type(u16 col, u16 row) {
    u8 t, type, prev_b;
    u16 off;
    if (col >= 128 || row >= 72) return 0;
    prev_b = bank_set(0xC5);
    t = MAP_PTR[(row << 7) + col];
    off = (((u16)t) << 3) + (((u16)t) << 1);
    type = TRIG_PTR[off];
    bank_restore(prev_b);
    return type;
}

// La pàgina que toca mostrar rep només les tires noves; la pàgina alterna es
// posa al dia al fotograma següent, abans de tornar-la a mostrar.
static void sync_backbuffer(i8 dx, i8 dy, u16 target_x4, u16 target_row) {
    u16 row_before = (u16)(target_row - dy);

    // move_x avança un caràcter CRTC (4 px); move_y avança un subtile (8 px).
    // dx/dy són la suma del pendent de l'altra pàgina + el pas actual.
    // El bucle generalitza a |dy|<=4 (el codi només genera ±2 amb move ±1).
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

    // Files: refresca les tires revelades (slot-absolut). Camina de la més
    // baixa cap amunt perquè la cantonada quedi amb la dada més nova.
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

// Caixa volant: restore (abans sync, com ascensors) + integra/dibuixa
// (després sync). Caixa 8x16 opaca (BOX a EXTRA): 4B/fila x 16, span 4.
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
    i16 cx, cy, sx, sy;
    u8 prev, r;
    if (s_carry_kind != 1 || !s_carry_state) return;
    s_carry_x = (i16)(s_carry_x + s_carry_vx);
    cx = (i16)(s_carry_x >> 3); cy = (i16)(s_carry_y >> 3);
    sx = (i16)((cx - (i16)(g_cam_x4 * 4)) >> 1);
    sy = (i16)(cy - (i16)(g_cam_row * 8));
    if (sx < 0 || sx > 72 || sy < 0 || sy > 144) {
        carry_restore(page); carry_restore((u8)(page ^ 1));
        s_carry_kind = 0; s_carry_state = 0; // vora pantalla: vanish (DOS)
        return;
    }
    {
        // Mur al morro: vanish (millora vs DOS, que el travessa).
        u16 ncol = (u16)(((s_carry_vx > 0) ? (cx + 8) : (cx - 1)) >> 3);
        u16 nrow = (u16)((cy + 8) >> 4);
        if (is_floor_solid(ncol, nrow, 0, 0)) {
            carry_restore(page); carry_restore((u8)(page ^ 1));
            s_carry_kind = 0; s_carry_state = 0;
            return;
        }
    }
    prev = bank_set(0xC7);
    for (r = 0; r < 16; r++) {
        g_moving_dst = (u16)ring_address(page, cx, (i16)(cy + r));
        g_moving_background = (u16)(s_crate_bg[page] + ((u16)r << 2));
        g_moving_sprite = (u16)(CRATE_FLY_FRAME + ((u16)r << 3));
        g_moving_span = 4;
        moving_blit_span();
    }
    bank_restore(prev);
    s_carry_drawn[page] = 1; s_carry_dx[page] = cx; s_carry_dy[page] = cy;
}

// Avorta qualsevol carry (inclòs vol): restaura les DUES pàgines i neteja.
// Crides quan en Jake puja a l'escala o toca aigua amb caixa volant.
static void carry_abort(void) {
    carry_restore(s_back_page);
    carry_restore((u8)(s_back_page ^ 1));
    sprite_abort_balloon();
    s_carry_kind = 0; s_carry_state = 0;
}

void main(void) {
    // CRT manual: el start propi (LD SP + JP main) salta la llibreria, així
    // que _DATA (BSS) queda amb brossa de power-on. Netejar BSS ABANS de res.
    // La plantilla _INITIALIZED ve dins GAME.BIN (imatge completa carregada
    // pel starter) i es copia a la seva RAM. Adreces generades (crt_addrs.h).
    cpct_memset((void*)CRT_DATA_START, 0, CRT_DATA_LEN);
    cpct_memcpy((void*)CRT_IDATA_DST, (void*)CRT_IDATA_SRC, CRT_IDATA_LEN);
    stack_canary_init();
    cpc_install_isr();

    // Carregar fitxers als Bancs 4/5/7 amb CRC16 + 3 reintents: el FDC de
    // vegades llegeix un sector malament; sense verify el joc mor en brossa.
    // Falla total = vora 0x40+i + spin (net).
    {
        static const u8 v_bank[7] = { 0xC4, 0xC5, 0xC5, 0xC7, 0xC7, 0xC7, 0xC5 };
        static const u16 v_addr[7] = { 0x4000, 0x4000, 0x6400, 0x4000, 0x7AA0, 0x78E0, 0x6E00 };
        static const u16 v_len[7] = { 16384, 9216, 2560, 12480, 832, 448, 4096 };
        static const u16 v_crc[7] = { CRC_TILES, CRC_MAP, CRC_TRIG, CRC_PFRAMES, CRC_EXTRA, CRC_ELEV, CRC_BANK5 };
        static const DiskFileDesc* const v_desc[7] = { &g_file_tiles, &g_file_map, &g_file_trig, &g_file_pframes, &g_file_extra, &g_file_elev, &g_file_bank5 };
        u8 i, t;
        for (i = 0; i < 7; i++) {
            u8 ok = 0;
            for (t = 0; t < 3 && !ok; t++) {
                u8 prev;
                const u8* p;
                u16 crc, n;
                if (!fdc_load_file(v_desc[i], v_bank[i], (void*)v_addr[i])) continue;
                prev = bank_set(v_bank[i]);
                p = (const u8*)v_addr[i];
                crc = 0xFFFF; n = v_len[i];
                while (n--) {
                    u8 k;
                    crc ^= (u16)(*p++) << 8;
                    for (k = 0; k < 8; k++)
                        crc = (crc & 0x8000) ? (u16)((crc << 1) ^ 0x1021) : (u16)(crc << 1);
                }
                bank_restore(prev);
                if (crc == v_crc[i]) ok = 1;
            }
            if (!ok) { cpct_setBorder((u8)(0x40 + i)); while (1) { } }
        }
    }

    video_init();

    // Inicialitzar la taula de H-FLIP ràpid al Banc 7 (0x7F00)
    {
        u8 prev = bank_set(0xC7);
        sprite_hflip_init_lut((u8*)0x7F00);
        bank_restore(prev);
    }

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
            cpct_setBorder(0x4C); // Alarma: canari de pila trepitjat (restablert)
        }
        i8  move = 0;
        i8  move_x = 0;
        i8  move_y = 0;
        i8  page_dx, page_dy;
        u8  jump = 0;
        u8  climbing = 0;
        u8  grab = 0;
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

        u8  crouch = 0;
        cpct_scanKeyboard_f();
        if (cpct_isKeyPressed(Key_CursorLeft) || cpct_isKeyPressed(Key_Q) ||
            cpct_isKeyPressed(Joy0_Left))  { move = -1; g_face = 1; }
        if (cpct_isKeyPressed(Key_CursorRight) || cpct_isKeyPressed(Key_S) ||
            cpct_isKeyPressed(Joy0_Right)) { move = +1; g_face = 0; }
        // Controls DOS 1:1: SPACE = acció (agafar/llençar), UP = salt.
        // X extra + Fire1/Fire2 = acció (comoditat CPC/joystick).
        if (cpct_isKeyPressed(Key_Space) || cpct_isKeyPressed(Key_X) ||
            cpct_isKeyPressed(Joy0_Fire1) || cpct_isKeyPressed(Joy0_Fire2)) { grab = 1; }
        if (cpct_isKeyPressed(Key_CursorDown) || cpct_isKeyPressed(Key_Z) ||
            cpct_isKeyPressed(Joy0_Down))  { crouch = 1; }
        // Salt inhibit amb SPACE aguantat (DOS: inp_key_up && !inp_key_space).
        if ((cpct_isKeyPressed(Key_CursorUp) || cpct_isKeyPressed(Joy0_Up)) &&
            !grab) { jump = 1; }

        {
            i16 max_spd;
            // L'original no alenteix ajupit: crawl == walk (a peu).
            if (!s_on_ground) max_spd = SPEED_AIR;
            else              max_spd = SPEED_MAX;

            if (move > 0)      { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx >  max_spd) s_vx =  max_spd; }
            else if (move < 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < -max_spd) s_vx = -max_spd; }
            else {
                if (s_vx > 0) { s_vx = (i16)(s_vx - MOVE_ACC); if (s_vx < 0) s_vx = 0; }
                else if (s_vx < 0) { s_vx = (i16)(s_vx + MOVE_ACC); if (s_vx > 0) s_vx = 0; }
            }
        }

        py = (i16)(s_py8 >> 3);
        px = (i16)(s_px8 >> 3);

        // --- Escala (tile type 7, DOS sprite_type 2) ---
        // Overlap = climb (fins i tot quiet: hover sense gravetat).
        // Pujar: -19 dins / -10 sortint; baixar: +19; neutre: manté vy.
        // Fora de l'escala: física normal (en sortir, cau si hi ha aire).
        {
            u16 lcol = (u16)((px + 8) >> 3);
            u16 lrow = (u16)((py + PH) >> 4);
            if (level_get_tile_type(lcol, lrow) == 7) {
                climbing = 1;
                if (s_carry_kind) carry_abort(); // DOS: a l'escala es deixa anar
                if (!s_climb_prev) { // snap en entrar (centra a la columna)
                    px = (i16)((lcol << 3) - 4);
                    s_px8 = (i16)(px * SUB);
                }
                if (jump) {
                    u16 arow = (u16)((py - 2) >> 4);
                    s_vy = (level_get_tile_type(lcol, arow) == 7) ? -19 : -10;
                } else if (crouch) {
                    s_vy = 19;
                }
                s_on_ground = 0;
                s_ground_elevator = -1;
            }
        }

        belt_push = 0;
        // --- Grab / release (DOS) ---
        // GLOBUS/PARAIGUA: AUTOMATICS en tocar (DOS: _si==8/9 sense
        // carry_crate_flag). CAIXA: AJUPIT a TERRA + flanc SPACE.
        // Mostreig DOS 1:1 (xpos16,ypos16, ypos=snap peus-1): fila peus-1
        // al centre del Jake. Forat = reset_tiles DOS (veí dret, mai blau).
        // LLENÇAR/ALLIBERAR: nomes flanc SPACE.
        if (!s_carry_kind && !climbing) {
            u16 gcol = (u16)((px + 8) >> 3);
            u16 grow = (u16)((py + PH - 1) >> 4); // DOS ypos = peus-1
            u8 gtype = level_get_tile_type(gcol, grow);
            if (gtype == 8 || gtype == 9) {
                world_reset_tile(gcol, grow);
                if (grow > 0) world_reset_tile(gcol, (u16)(grow - 1));
                s_carry_kind = (gtype == 8) ? 2 : 8;
            }
        }
        if (grab && !s_grab_prev && !climbing) {
            if (s_carry_kind == 1 && !s_carry_state) {
                // LLANÇAR (DOS throw): vol recte ±154, sense gravetat.
                s_carry_x = s_px8;
                s_carry_y = (i16)(s_py8 - 20 * SUB);
                s_carry_vx = (g_face == 0) ? 154 : -154;
                s_carry_drawn[0] = 0; s_carry_drawn[1] = 0;
                s_carry_state = 1;
            } else if (s_carry_kind == 2 || s_carry_kind == 8) {
                sprite_abort_balloon();
                s_carry_kind = 0; // allibera globus/paraigua (pop)
            } else if (!s_carry_kind && crouch && s_on_ground) {
                // ADQUIRIR caixa (només ajupit a terra).
                u16 gcol = (u16)((px + 8) >> 3);
                u16 grow = (u16)((py + PH - 1) >> 4);
                if (level_get_tile_type(gcol, grow) == 5) {
                    world_reset_tile(gcol, grow);
                    s_carry_kind = 1; s_carry_state = 0;
                    s_anim_idx = 0; s_anim_timer = 0;
                }
            }
        }
        s_grab_prev = grab;
        if (s_on_ground) {
            u16 row = (u16)((py + PH) >> 4);
            u16 col0 = (u16)((px + 3) >> 3);
            u16 col1 = (u16)((px + 8) >> 3);
            belt_push = 0;
            { bc_a = col0; bc_b = col1; bc_c = row; moving_conveyor_push(); belt_push = bc_r; }
            // DOS 1:1: la cinta arrossega (unk1C a la velocitat) però NO
            // força animació ni direcció (direction_lr ve de l'input: quiet
            // = idle lliscant, mai walk). Abans forçàvem move/g_face aquí.
        }
        effective_vx = (i16)(s_vx + belt_push);

        // --- Moviment horitzontal i col·lisió de parets 1:1 ---
        if (effective_vx > 0) {
            u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
            u16 c_right = (u16)((next_px + 10) >> 3);
            u16 r_waist = (u16)((py + 16) >> 4);
            u16 r_head  = (u16)(py >> 4);
            u8 fl = get_tile_flags(c_right, r_waist) |
                    get_tile_flags(c_right, r_head);
            if (fl & 1) {
                s_vx = 0;
                s_px8 = (i16)(((c_right << 3) - 11) * SUB);
            } else {
                s_px8 = (i16)(s_px8 + effective_vx);
            }
        } else if (effective_vx < 0) {
            u16 next_px = (u16)((s_px8 + effective_vx) >> 3);
            u16 c_left  = (u16)((next_px + 1) >> 3);
            u16 r_waist = (u16)((py + 16) >> 4);
            u16 r_head  = (u16)(py >> 4);
            u8 fl = get_tile_flags(c_left, r_waist) |
                    get_tile_flags(c_left, r_head);
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

        // --- Moviment vertical i gravetat 1:1 ---
        // En escala: vy ja ve del climb (sense gravetat, sense aterratge,
        // sense takeoff: la tecla de salt puja). El sostre sí aplica.
        {
            i16 prev_feet = (i16)(py + PH);
            u16 prev_head = (u16)(py >> 4);
            if (!climbing) {
                // Globus portat: pujada constant 1px/f (unk3D=2 DOS).
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
                    // Salt per flanc de pujada (com DOS: cal prémer de nou;
                    // mantenir premut no repeteix i no frena les caigudes).
                    // Amb caixa: salt feble (DOS yfriction 9 vs 14).
                    if (jump && !s_jump_prev && s_on_ground) {
                        s_vy = (s_carry_kind == 1 && !s_carry_state) ? -96 : JUMP_VY;
                        s_on_ground = 0;
                        s_ground_elevator = -1;
                    }
                    // Paraigua: caiguda lenta 1px/f (unk3D=1 DOS).
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

                // En escala no s'aterra (DOS: sprite 2 salta el trigger
                // de peus); el sostre sí aplica (puja per lintels).
                if (s_vy >= 0 && !climbing) {
                    i16 elevator_top;
                    i8 elevator_id;
                    bc_a = (u16)px; bc_b = (u16)prev_feet; bc_c = (u16)curr_feet;
                    bc_d = (u16)s_vy; bc_e = (u16)&elevator_top;
                    moving_find_landing();
                    elevator_id = (i8)bc_r;
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
                        if (is_floor_solid(c_mid1, target_row, s_vy, crouch) || is_floor_solid(c_mid2, target_row, s_vy, crouch)) {
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
                            if (is_floor_solid(c_mid1, feet_under, s_vy, crouch) || is_floor_solid(c_mid2, feet_under, s_vy, crouch)) {
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
                    // Escombrat anti-tunneling (salt -18.75px/f vs files 16px):
                    // revisa totes les files travessades pel cap i atura a la
                    // sòlida més propera (la de més avall). Màx ~3 files.
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

        // A l'aigua es deixa anar (nedar = fase amb frames propis).
        if (s_carry_kind) {
            u16 wcol = (u16)((px + 8) >> 3);
            u16 wrow = (u16)((py + PH) >> 4);
            if (get_tile_op(wcol, wrow) == 23) carry_abort();
        }
        // Globus: POP de sostre DOS (obj37 toca type>5 2 files amunt o y<32):
        // el sobre peta (sense anim: vanish) i en Jake cau.
        if (s_carry_kind == 2) {
            i16 bb = (i16)((s_py8 >> 3) - 1); // fons del sobre (DOS obj37 ypos)
            u8 pop = (bb < 32);
            if (!pop) {
                u16 bcol = (u16)(((s_px8 >> 3) + 8) >> 3);
                u16 brow = (u16)((bb >> 4) - 2);
                pop = (level_get_tile_type(bcol, brow) > 5);
            }
            if (pop) {
                sprite_abort_balloon();
                s_carry_kind = 0;
                s_vy = 0;
            }
        }

        // --- Camera: zones uniformes 116/32 en aire i terra ---
        // Es PUJA (l'àpex mana) i es BAIXA (la caiguda mana): resposta
        // immediata als dos costats, sense congelar mai. Les zones amples
        // fan que els salts en pla típics (sy0>=91: àpex>=32, retorn<=116)
        // siguin 0 tires i sense drift (s'autolimita: provat per construcció).
        // Les caigudes fondes segueixen amb lag (1 fila/f, transitori lent:
        // límit de pressupost, perf pendent), però MAI congelades: l'aterratge
        // ja no passa fora de pantalla en silenci.
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
        // Coherència visual: el walk exigeix terra, però si els peus són
        // fora del viewport (terra invisible per lag de càmera) no afirmem
        // groundedness: jump fins que el terra es vegi. Física intacta.
        // (bsy local curt: el rang de vida llarg embogeix l'assignador.
        //  Una sola comparació sense signe cobreix els dos costats.)
        u8 cur;
        i16 bsy = (i16)(py - (i16)(g_cam_row * 8));
        if (climbing) {
            // DOS 00b8 = {9,9,8,8}: puja amb DOS 9/8, quiet amb DOS 8.
            if (jump || crouch || move != 0) {
                s_anim_timer++;
                if (s_anim_timer >= 6) {
                    s_anim_timer = 0;
                    s_anim_idx ^= 1;
                }
                cur = s_anim_idx ? 5 : 9;
            } else {
                cur = 5;
                s_anim_timer = 0;
            }
        } else if (s_carry_kind == 1 && !s_carry_state) {
            // Amb caixa: aire DOS 17, camina DOS [15,13,14,16], quiet DOS 14.
            if (!s_on_ground) cur = 16;
            else if (move != 0) {
                s_anim_timer++;
                if (s_anim_timer >= 2) {
                    s_anim_timer = 0;
                    s_anim_idx++;
                    if (s_anim_idx >= 4) s_anim_idx = 0;
                }
                cur = g_crate_walk[s_anim_idx];
            } else cur = 13;
        } else if (!s_on_ground || (u16)(bsy + 30) > 160) {
            // DOS 1:1 (cyxx case0 / animframe_00ab = {1,0x07}): en aire SEMPRE
            // el salt cames obertes + barret. Mai back-view (DOS 8 = escala 00b8)
            // ni walk: el DOS només usa el frame 0x2C en caiguda extrema (>10).
            cur = 4;
        } else if (crouch) {
            if (move != 0) {
                s_anim_timer++;
                if (s_anim_timer >= 6) { // crawl DOS 16f@30Hz=533ms -> 12f@25Hz=480ms
                    s_anim_timer = 0;
                    s_anim_idx ^= 1;
                }
                cur = s_anim_idx ? 8 : 7; // crawl: alternança crouch3 / crouch2
            } else {
                cur = 6; // crouch1: ajupit aturat
                s_anim_timer = 0;
            }
        } else if (move != 0) {
            s_anim_timer++;
            if (s_anim_timer >= 2) { // walk DOS 6f@30Hz=200ms -> 12f@25Hz=480ms fluid M0
                s_anim_timer = 0;
                s_anim_idx++;
                if (s_anim_idx >= 6) s_anim_idx = 0;
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

        // --- Restaurar el fons del personatge al BACKBUFFER (LIFO) ---
        sprite_restore_balloon();
        if (s_have_drawn[s_back_page]) {
            sprite_restore_player();
            s_have_drawn[s_back_page] = 0;
        }
        moving_restore(s_back_page, (move_x != 0 || move_y != 0));
        carry_restore(s_back_page);
        world_flush_repaints(); // forats post-restore (el stale no els tapa)

        // Dibuixar les tires noves al ring buffer, sense copiar la pantalla.
        sync_backbuffer(page_dx, page_dy, g_cam_x4, g_cam_row);
        g_vram_start = camera_ma(g_cam_x4, g_cam_row);
        bc_a = s_back_page; bc_b = g_cam_x4; bc_c = g_cam_row;
        moving_draw_conveyor_tiles();

        // Redraw moving objects over the updated background.
        moving_draw(s_back_page, g_cam_x4, g_cam_row);
        carry_fly_draw(s_back_page);

        // --- Dibuix d'Sprite al BACKBUFFER (fora de pantalla, 0 flicker!) ---
        g_spr_y = (u8)dsy;
        g_spr_x = (u8)dsx;

        // Comprovar si en Jake és dins d'una zona de reixa (Magasin)
        if ((px >= 392 && px <= 630 && py >= 608 && py <= 644) ||
            (px >= 392 && px <= 494 && py >= 704 && py <= 740)) {
            g_grate_enable = 1;
            g_grate_phase_x = (u8)((px >> 1) & 1);
            g_grate_base_y = (u8)(py & 7);
        } else {
            g_grate_enable = 0;
        }

        {
            const PSprFrame* frame = &g_player_frames_r[cur];
            u16 spr_addr = (u16)(PLAYER_FRAMES_BASE + frame->offset);
            const u8* fr_addr = (const u8*)spr_addr;
            u8 prev_b = bank_set(PLAYER_FRAMES_BANK);
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

        // --- Sincronització fixa a 25 Hz (12 ticks = 40 ms) i canvi de pàgina ---
        while ((u8)(g_ticks - last_ticks) < 12) {
        }
        last_ticks = g_ticks;

        cpc_wait_vsync_start();
        crtc_set_display_start((u16)((s_back_page == 1 ? 0x2000 : 0x3000) + g_vram_start));

        // --- Invertir pàgines: el que era front ara és backbuffer ---
        s_back_page ^= 1;
        g_vram_base_hi = (s_back_page == 1) ? 0x80 : 0xC0;
        s_pending_x = move_x;
        s_pending_y = move_y;
        s_climb_prev = climbing;
    }
}
