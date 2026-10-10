;; ============================================================
;; sprite.s - Rutines ultra-rapides en ASM Z80 per a sprites Mode 0
;; Amstrad CPC - SDCC 4.5 (__sdcccall 1)
;;
;; sprite_blit_player: Blit amb mascara + desat de fons simultani
;;                     Suporta reflexio horitzontal (H-flip) per Mode 0
;; sprite_restore_player: Restauracio rapida de fons amb LDIR
;; ============================================================

    .module sprite
    .optsdcc -mz80 sdcccall(1)

    .globl _sprite_blit_player
    .globl _sprite_restore_player
    .globl _sprite_balloon_init
    .globl _sprite_blit_balloon
    .globl _sprite_restore_balloon
    .globl _sprite_abort_balloon
    .globl _g_spr_y
    .globl _g_spr_x
    .globl _g_vram_base_hi
    .globl _g_vram_start
    .globl _scr_addr_table
    .globl _g_grate_enable
    .globl _g_grate_phase_x
    .globl _g_grate_base_y
    .globl _bank_set
    .globl _bank_restore
    .globl _g_bank

    ;; ============================================================
    ;; DADES DE TREBALL A _DATA
    ;; ============================================================
    .area _DATA

_g_grate_enable::   .db 0
_g_grate_phase_x::  .db 0
_g_grate_base_y::   .db 0
s_grate_cur_y:      .db 0
s_grate_ptr:        .dw 0

_g_spr_y::          .db 0
_g_spr_x::          .db 0
_g_vram_base_hi::   .db 0xC0
_g_vram_start::     .dw 0

_s_old_y_c0:        .db 0
_s_old_x_c0:        .db 0
_s_old_y_80:        .db 0
_s_old_x_80:        .db 0
s_cur_y:            .db 0
s_line_cnt:         .db 0
s_spr_ptr:          .dw 0
s_bg_read_ptr:      .dw 0
s_addr_segment:     .db 0
s_byte_cnt:         .db 0

_s_bloon_drawn_c0:  .db 0
_s_bloon_drawn_80:  .db 0
_s_bloon_old_y_c0:  .db 0
_s_bloon_old_x_c0:  .db 0
_s_bloon_old_y_80:  .db 0
_s_bloon_old_x_80:  .db 0
s_bloon_cur_x:      .db 0

;; Buffers de restauració de fons d'en Jake reubicats al Banc 7 (0x7520..0x76FF)
_s_player_bg_c0 = 0x7520
_s_player_bg_80 = 0x7610

;; Buffers de fons del globus al Banc 7 (0x7DE0..0x7EBF, 112 B per pàgina)
_s_bloon_bg_c0  = 0x7DE0
_s_bloon_bg_80  = 0x7E50



    ;; ============================================================
    ;; CODI A _CODE
    ;; ============================================================
    .area _CODE

;; ============================================================
;; void sprite_restore_player(void)
;;   Restaura el fons darrera del personatge dins la VRAM circular
;; ============================================================
_sprite_restore_player::
    ld      a, (_g_bank)
    push    af                  ;; desa banc anterior a la pila
    ld      a, #0xC7
    call    _bank_set           ;; commuta a Banc 7 (on viuen els buffers de fons)
    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 9$
    ld      a, (_s_old_y_c0)
    ld      (s_cur_y), a
    ld      hl, #_s_player_bg_c0
    ld      (s_bg_read_ptr), hl
    jr      8$
9$:
    ld      a, (_s_old_y_80)
    ld      (s_cur_y), a
    ld      hl, #_s_player_bg_80
    ld      (s_bg_read_ptr), hl
8$:
    ld      b, #30              ;; 30 linies
rst_line_loop:
    push    bc

    ;; Adreça base de línia i posició circular de càmera.
    ld      a, (s_cur_y)
    ld      l, a
    ld      h, #0
    add     hl, hl              ;; y * 2
    ld      de, #_scr_addr_table
    add     hl, de
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    call    sprite_map_line

    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 3$
    ld      a, (_s_old_x_c0)
    jr      4$
3$:
    ld      a, (_s_old_x_80)
4$:
    add     a, e
    ld      e, a
    ld      a, d
    adc     a, #0
    and     #0x07
    ld      d, a
    ld      a, (s_addr_segment)
    or      d                   ;; DE = adreça física, ajustada al ring
    ld      d, a
    ld      hl, (s_bg_read_ptr) ;; HL = buffer fons font

    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, rst_fast_copy
    ld      a, e
    cp      #0xF8
    jr      nc, rst_wrap_copy
rst_fast_copy:
    ld      bc, #8
    ldir
    jr      rst_copy_done
rst_wrap_copy:
    ld      b, #8
rst_byte_loop:
    ld      a, (hl)
    ld      (de), a
    inc     hl
    call    sprite_inc_de_ring
    djnz    rst_byte_loop
rst_copy_done:
    ld      (s_bg_read_ptr), hl

    ld      hl, #s_cur_y
    inc     (hl)

    pop     bc
    djnz    rst_line_loop
    pop     af
    call    _bank_restore       ;; restaura el banc anterior
    ret

;; DE = adreça de línia del mapa base. Retorna DE amb l'offset MA circular
;; incorporat, mantenint la pàgina i la línia de trama.
sprite_map_line:
    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      nz, 1$
    res     6, d
1$:
    ld      a, d
    and     #0xF8
    ld      (s_addr_segment), a
    ld      a, d
    and     #0x07
    ld      h, a
    ld      l, e
    ld      de, (_g_vram_start)
    ex      de, hl
    add     hl, hl              ;; paraules MA -> bytes dins del bloc 2 KB
    ex      de, hl
    add     hl, de
    ld      a, h
    and     #0x07               ;; wrap dins la mateixa línia de trama
    ld      h, a
    ld      a, (s_addr_segment)
    or      h
    ld      h, a
    ex      de, hl
    ret

;; Incrementa DE i torna al començament de la mateixa línia de trama al wrap.
sprite_inc_de_ring:
    inc     de
    ld      a, e
    or      a
    ret     nz
    ld      a, d
    and     #0x07
    ret     nz
    ld      a, (s_addr_segment)
    ld      d, a
    ret


    .globl _cpc_wait_vsync_start

;; ============================================================
;; void cpc_wait_vsync_start(void)
;;   Espera el comencament de la sincronitzacio vertical (Linia 240).
;; ============================================================
_cpc_wait_vsync_start::
    ld      b, #0xF5
1$:
    in      a, (c)
    rra
    jr      c, 1$               ;; Si ja estavem en VSYNC, esperar que surti
2$:
    in      a, (c)
    rra
    jr      nc, 2$              ;; Esperar el FLANC DE PUJADA (inici de VSYNC a la linia 240)
    ret


;; ============================================================
;; void sprite_blit_player(const u8* spr)
;;   HL = spr (punter al frame [inv_mask, img_masked])
;;   Rutina ultra-rapida sense branques (~21.000 T-states)
;; ============================================================
_sprite_blit_player::
    ld      (s_spr_ptr), hl

    ld      a, (_g_spr_y)
    ld      (s_cur_y), a

    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 1$
    ld      a, (_g_spr_y)
    ld      (_s_old_y_c0), a
    ld      a, (_g_spr_x)
    ld      (_s_old_x_c0), a
    ld      bc, #_s_player_bg_c0
    jr      2$
1$:
    ld      a, (_g_spr_y)
    ld      (_s_old_y_80), a
    ld      a, (_g_spr_x)
    ld      (_s_old_x_80), a
    ld      bc, #_s_player_bg_80
2$:
    ld      a, (_g_grate_enable)
    or      a
    jr      z, 3$
    ld      a, (_g_grate_base_y)
    ld      (s_grate_cur_y), a
3$:
    ld      a, #30              ;; 30 linies
    ld      (s_line_cnt), a

blit_line:
    push    bc

    ld      a, (s_cur_y)
    ld      l, a
    ld      h, #0
    add     hl, hl
    ld      de, #_scr_addr_table
    add     hl, de
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    call    sprite_map_line

    ld      a, (_g_spr_x)
    add     a, e
    ld      e, a
    ld      a, d
    adc     a, #0
    and     #0x07
    ld      d, a
    ld      a, (s_addr_segment)
    or      d
    ld      d, a
    ld      hl, (s_spr_ptr)     ;; HL = sprite [inv_mask, img_masked]

    pop     bc                  ;; Recuperar BC = bg_write_ptr

    ;; Comprovar si cal aplicar la reixa per sobre d'en Jake
    ld      a, (_g_grate_enable)
    or      a
    jr      nz, blit_grate_line

    ;; Camí normal (sense reixa)
    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, blit_fast_line
    ld      a, e
    cp      #0xF8
    jp      nc, blit_wrap_line
blit_fast_line:
    .rept 8
    ld      a, (de)             ;; Llegir pantalla original
    ld      (bc), a             ;; Desar al buffer de fons
    inc     bc
    and     (hl)                ;; A = pantalla & inv_mask
    inc     hl
    or      (hl)                ;; A = (pantalla & inv_mask) | img_masked
    inc     hl
    ld      (de), a             ;; Escriure a VRAM!
    inc     de
    .endm
    jp      blit_line_done

blit_wrap_line:
    ld      a, #8
    ld      (s_byte_cnt), a
blit_wrap_loop:
    ld      a, (de)
    ld      (bc), a
    inc     bc
    and     (hl)
    inc     hl
    or      (hl)
    inc     hl
    ld      (de), a
    call    sprite_inc_de_ring
    ld      a, (s_byte_cnt)
    dec     a
    ld      (s_byte_cnt), a
    jr      nz, blit_wrap_loop
    jp      blit_line_done

;; ------------------------------------------------------------
;; Línia amb reixa: dibuixa en Jake i aplica la reixa estrictament
;; a sobre dels píxels d'en Jake dins del mateix rectangle!
;; ------------------------------------------------------------
blit_grate_line:
    push    de
    ld      a, (s_grate_cur_y)
    and     #0x07
    add     a, a
    ld      e, a
    ld      a, (_g_grate_phase_x)
    and     #0x01
    or      e
    ld      l, a
    ld      h, #0
    add     hl, hl              ;; *2
    add     hl, hl              ;; *4
    add     hl, hl              ;; *8
    add     hl, hl              ;; *16
    ld      de, #_grate_lut
    add     hl, de
    ld      (s_grate_ptr), hl
    pop     de
    ld      hl, (s_spr_ptr)

    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, blit_grate_fast_line
    ld      a, e
    cp      #0xF8
    jp      nc, blit_grate_wrap_line

blit_grate_fast_line:
    push    ix
    ld      ix, (s_grate_ptr)
    .rept 8
    ld      a, (de)             ;; Llegir pantalla original
    ld      (bc), a             ;; Desar fons net!
    inc     bc
    and     (hl)                ;; A = pantalla & inv_mask
    inc     hl
    or      (hl)                ;; A = (pantalla & inv_mask) | img_masked
    inc     hl
    and     0(ix)               ;; Aplicar màscara de reixa
    or      8(ix)               ;; Afegir color de reixa
    inc     ix
    ld      (de), a             ;; Escriure a VRAM!
    inc     de
    .endm
    pop     ix
    jr      blit_grate_line_done

blit_grate_wrap_line:
    push    ix
    ld      ix, (s_grate_ptr)
    ld      a, #8
    ld      (s_byte_cnt), a
blit_grate_wrap_loop:
    ld      a, (de)
    ld      (bc), a
    inc     bc
    and     (hl)
    inc     hl
    or      (hl)
    inc     hl
    and     0(ix)
    or      8(ix)
    inc     ix
    ld      (de), a
    call    sprite_inc_de_ring
    ld      a, (s_byte_cnt)
    dec     a
    ld      (s_byte_cnt), a
    jr      nz, blit_grate_wrap_loop
    pop     ix

blit_grate_line_done:
    ld      (s_spr_ptr), hl
    ld      hl, #s_grate_cur_y
    inc     (hl)
    jr      blit_next_line

blit_line_done:
    ld      (s_spr_ptr), hl

blit_next_line:

    ld      hl, #s_cur_y
    inc     (hl)

    ld      hl, #s_line_cnt
    dec     (hl)
    jp      nz, blit_line
    ret

;; ============================================================
;; Taula de reixa periòdica (8 línies × 2 fases × 16 bytes = 256 bytes)
;; Cada entrada de 16 bytes conté: 8 bytes de màscara + 8 bytes de color
;; ============================================================
_grate_lut:
    .db #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF  ;; y=0, phase=0 masks
    .db #0x10, #0x00, #0x10, #0x00, #0x10, #0x00, #0x10, #0x00  ;; y=0, phase=0 vals
    .db #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA  ;; y=0, phase=1 masks
    .db #0x00, #0x10, #0x00, #0x10, #0x00, #0x10, #0x00, #0x10  ;; y=0, phase=1 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=1, phase=0 masks
    .db #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22  ;; y=1, phase=0 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=1, phase=1 masks
    .db #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22  ;; y=1, phase=1 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=2, phase=0 masks
    .db #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20  ;; y=2, phase=0 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=2, phase=1 masks
    .db #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20  ;; y=2, phase=1 vals
    .db #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA  ;; y=3, phase=0 masks
    .db #0x00, #0x11, #0x00, #0x11, #0x00, #0x11, #0x00, #0x11  ;; y=3, phase=0 vals
    .db #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF  ;; y=3, phase=1 masks
    .db #0x11, #0x00, #0x11, #0x00, #0x11, #0x00, #0x11, #0x00  ;; y=3, phase=1 vals
    .db #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA  ;; y=4, phase=0 masks
    .db #0x00, #0x10, #0x00, #0x10, #0x00, #0x10, #0x00, #0x10  ;; y=4, phase=0 vals
    .db #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF  ;; y=4, phase=1 masks
    .db #0x10, #0x00, #0x10, #0x00, #0x10, #0x00, #0x10, #0x00  ;; y=4, phase=1 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=5, phase=0 masks
    .db #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22  ;; y=5, phase=0 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=5, phase=1 masks
    .db #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22, #0x22  ;; y=5, phase=1 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=6, phase=0 masks
    .db #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20  ;; y=6, phase=0 vals
    .db #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55, #0x55  ;; y=6, phase=1 masks
    .db #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20, #0x20  ;; y=6, phase=1 vals
    .db #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF  ;; y=7, phase=0 masks
    .db #0x11, #0x00, #0x11, #0x00, #0x11, #0x00, #0x11, #0x00  ;; y=7, phase=0 vals
    .db #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA, #0xFF, #0xAA  ;; y=7, phase=1 masks
    .db #0x00, #0x11, #0x00, #0x11, #0x00, #0x11, #0x00, #0x11  ;; y=7, phase=1 vals


;; ============================================================
;; void sprite_balloon_init(void)
;;   Inicialitza els flags de globus dibuixat a 0
;; ============================================================
_sprite_balloon_init::
    xor     a
    ld      (_s_bloon_drawn_c0), a
    ld      (_s_bloon_drawn_80), a
    ret


;; ============================================================
;; void sprite_restore_balloon(void)
;;   Restaura el fons del globus per a la pàgina actual
;; ============================================================
_sprite_restore_balloon::
    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 1$
    ld      a, (_s_bloon_drawn_c0)
    or      a
    ret     z
    xor     a
    ld      (_s_bloon_drawn_c0), a
    ld      a, (_s_bloon_old_y_c0)
    ld      (s_cur_y), a
    ld      a, (_s_bloon_old_x_c0)
    ld      (s_bloon_cur_x), a
    ld      hl, #_s_bloon_bg_c0
    jr      2$
1$:
    ld      a, (_s_bloon_drawn_80)
    or      a
    ret     z
    xor     a
    ld      (_s_bloon_drawn_80), a
    ld      a, (_s_bloon_old_y_80)
    ld      (s_cur_y), a
    ld      a, (_s_bloon_old_x_80)
    ld      (s_bloon_cur_x), a
    ld      hl, #_s_bloon_bg_80
2$:
    ld      (s_bg_read_ptr), hl

    ld      a, (_g_bank)
    push    af
    ld      a, #0xC7
    call    _bank_set

    ld      b, #28              ;; 28 linies d'alcada
bloon_rst_line_loop:
    push    bc

    ld      a, (s_cur_y)
    ld      l, a
    ld      h, #0
    add     hl, hl              ;; y * 2
    ld      de, #_scr_addr_table
    add     hl, de
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    call    sprite_map_line

    ld      a, (s_bloon_cur_x)
    add     a, e
    ld      e, a
    ld      a, d
    adc     a, #0
    and     #0x07
    ld      d, a
    ld      a, (s_addr_segment)
    or      d
    ld      d, a
    ld      hl, (s_bg_read_ptr)

    .rept 4
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     de
    .endm

    ld      (s_bg_read_ptr), hl

    ld      hl, #s_cur_y
    inc     (hl)

    pop     bc
    djnz    bloon_rst_line_loop

    pop     af
    call    _bank_restore
    ret


;; ============================================================
;; void sprite_blit_balloon(void)
;;   Dibuixa el globus vermell autèntic (0x7D00 al Banc 7)
;;   a (g_spr_x + 2, g_spr_y - 27) i desa el fons net.
;; ============================================================
_sprite_blit_balloon::
    ld      a, (_g_spr_y)
    cp      #28
    ret     c                   ;; si g_spr_y < 28, fora per dalt
    sub     #28
    ld      (s_cur_y), a

    ld      a, (_g_spr_x)
    add     a, #2               ;; centrat (+2 bytes = +4 px Mode 0)
    ld      (s_bloon_cur_x), a

    ld      a, (_g_bank)
    push    af
    ld      a, #0xC7
    call    _bank_set

    ld      hl, #0x7D00         ;; BALLOON_SPRITE_FRAME al Banc 7
    ld      (s_spr_ptr), hl

    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 1$
    ld      a, (s_cur_y)
    ld      (_s_bloon_old_y_c0), a
    ld      a, (s_bloon_cur_x)
    ld      (_s_bloon_old_x_c0), a
    ld      a, #1
    ld      (_s_bloon_drawn_c0), a
    ld      bc, #_s_bloon_bg_c0
    jr      2$
1$:
    ld      a, (s_cur_y)
    ld      (_s_bloon_old_y_80), a
    ld      a, (s_bloon_cur_x)
    ld      (_s_bloon_old_x_80), a
    ld      a, #1
    ld      (_s_bloon_drawn_80), a
    ld      bc, #_s_bloon_bg_80
2$:

    ld      a, #28              ;; 28 linies
    ld      (s_line_cnt), a

bloon_blit_line:
    push    bc

    ld      a, (s_cur_y)
    ld      l, a
    ld      h, #0
    add     hl, hl
    ld      de, #_scr_addr_table
    add     hl, de
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    call    sprite_map_line

    ld      a, (s_bloon_cur_x)
    add     a, e
    ld      e, a
    ld      a, d
    adc     a, #0
    and     #0x07
    ld      d, a
    ld      a, (s_addr_segment)
    or      d
    ld      d, a

    ld      hl, (s_spr_ptr)
    pop     bc                  ;; BC = bg_write_ptr

    .rept 4
    ld      a, (de)             ;; llegeix fons net
    ld      (bc), a             ;; desa a buffer de fons
    inc     bc
    and     (hl)                ;; aplica inv_mask
    inc     hl
    or      (hl)                ;; aplica img_masked
    inc     hl
    ld      (de), a             ;; escriu a VRAM
    inc     de
    .endm

    ld      (s_spr_ptr), hl

    ld      hl, #s_cur_y
    inc     (hl)

    ld      a, (s_line_cnt)
    dec     a
    ld      (s_line_cnt), a
    jr      nz, bloon_blit_line

    pop     af
    call    _bank_restore
    ret


;; ============================================================
;; void sprite_abort_balloon(void)
;;   Restaura el globus de manera natural en els dos cicles de backbuffer
;; ============================================================
_sprite_abort_balloon::
    ret



;; ============================================================
;; Taula de 200 adreces de l'inici de linia a VRAM (0xC000..0xFFFF)
;; ============================================================
_scr_addr_table::
    .dw 0xC000, 0xC800, 0xD000, 0xD800, 0xE000, 0xE800, 0xF000, 0xF800
    .dw 0xC050, 0xC850, 0xD050, 0xD850, 0xE050, 0xE850, 0xF050, 0xF850
    .dw 0xC0A0, 0xC8A0, 0xD0A0, 0xD8A0, 0xE0A0, 0xE8A0, 0xF0A0, 0xF8A0
    .dw 0xC0F0, 0xC8F0, 0xD0F0, 0xD8F0, 0xE0F0, 0xE8F0, 0xF0F0, 0xF8F0
    .dw 0xC140, 0xC940, 0xD140, 0xD940, 0xE140, 0xE940, 0xF140, 0xF940
    .dw 0xC190, 0xC990, 0xD190, 0xD990, 0xE190, 0xE990, 0xF190, 0xF990
    .dw 0xC1E0, 0xC9E0, 0xD1E0, 0xD9E0, 0xE1E0, 0xE9E0, 0xF1E0, 0xF9E0
    .dw 0xC230, 0xCA30, 0xD230, 0xDA30, 0xE230, 0xEA30, 0xF230, 0xFA30
    .dw 0xC280, 0xCA80, 0xD280, 0xDA80, 0xE280, 0xEA80, 0xF280, 0xFA80
    .dw 0xC2D0, 0xCAD0, 0xD2D0, 0xDAD0, 0xE2D0, 0xEAD0, 0xF2D0, 0xFAD0
    .dw 0xC320, 0xCB20, 0xD320, 0xDB20, 0xE320, 0xEB20, 0xF320, 0xFB20
    .dw 0xC370, 0xCB70, 0xD370, 0xDB70, 0xE370, 0xEB70, 0xF370, 0xFB70
    .dw 0xC3C0, 0xCBC0, 0xD3C0, 0xDBC0, 0xE3C0, 0xEBC0, 0xF3C0, 0xFBC0
    .dw 0xC410, 0xCC10, 0xD410, 0xDC10, 0xE410, 0xEC10, 0xF410, 0xFC10
    .dw 0xC460, 0xCC60, 0xD460, 0xDC60, 0xE460, 0xEC60, 0xF460, 0xFC60
    .dw 0xC4B0, 0xCCB0, 0xD4B0, 0xDCB0, 0xE4B0, 0xECB0, 0xF4B0, 0xFCB0
    .dw 0xC500, 0xCD00, 0xD500, 0xDD00, 0xE500, 0xED00, 0xF500, 0xFD00
    .dw 0xC550, 0xCD50, 0xD550, 0xDD50, 0xE550, 0xED50, 0xF550, 0xFD50
    .dw 0xC5A0, 0xCDA0, 0xD5A0, 0xDDA0, 0xE5A0, 0xEDA0, 0xF5A0, 0xFDA0
    .dw 0xC5F0, 0xCDF0, 0xD5F0, 0xDDF0, 0xE5F0, 0xEDF0, 0xF5F0, 0xFDF0
    .dw 0xC640, 0xCE40, 0xD640, 0xDE40, 0xE640, 0xEE40, 0xF640, 0xFE40
    .dw 0xC690, 0xCE90, 0xD690, 0xDE90, 0xE690, 0xEE90, 0xF690, 0xFE90
    .dw 0xC6E0, 0xCEE0, 0xD6E0, 0xDEE0, 0xE6E0, 0xEEE0, 0xF6E0, 0xFEE0
    .dw 0xC730, 0xCF30, 0xD730, 0xDF30, 0xE730, 0xEF30, 0xF730, 0xFF30
    .dw 0xC780, 0xCF80, 0xD780, 0xDF80, 0xE780, 0xEF80, 0xF780, 0xFF80
