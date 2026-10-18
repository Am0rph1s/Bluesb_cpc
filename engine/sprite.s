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
    .globl _sprite_blit_umbrella
    .globl _sprite_restore_umbrella
    .globl _sprite_abort_balloon
    .globl _g_spr_y
    .globl _g_spr_x
    .globl _g_vram_base_hi
    .globl _g_vram_start
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

;; Buffers de restauració de fons d'en Jake reubicats al Banc 7 (0x7660..0x783F)
_s_player_bg_c0 = 0x7660
_s_player_bg_80 = 0x7750

;; Buffers de restauració de fons per a objectes portats (globus i paraigües) a _DATA resident:
;; 10 bytes x 32 linies = 320 bytes per pagina (total 640 B). Mai col·lideix amb frames de Jake!
_s_carry_bg_c0::    .ds 320
_s_carry_bg_80::    .ds 320



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
    ld      a, (_s_old_x_c0)
    ld      (s_cur_y), a        ;; reutilitzat temporalment per x
    ld      a, (_s_old_y_c0)
    ld      hl, #_s_player_bg_c0
    jr      8$
9$:
    ld      a, (_s_old_x_80)
    ld      (s_cur_y), a
    ld      a, (_s_old_y_80)
    ld      hl, #_s_player_bg_80
8$:
    ld      (s_bg_read_ptr), hl
    call    sprite_calc_de      ;; A = y, (s_cur_y) = x -> DE = VRAM física
    ld      hl, (s_bg_read_ptr)
    ld      b, #30              ;; 30 linies
rst_line_loop:
    push    bc
    push    de

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
    pop     de
    call    sprite_step_de
    pop     bc
    djnz    rst_line_loop
    pop     af
    call    _bank_restore       ;; restaura el banc anterior
    ret

;; ============================================================
;; Calcula l'adreça física VRAM mapejada al ring per a la 1a línia:
;; IN: A = y (0..199), (s_cur_y) = x en bytes (0..79)
;; OUT: DE = adreça física VRAM mapejada
;; ============================================================
sprite_calc_de:
    call    scr_raw_first
    call    sprite_map_line
    ld      a, (s_cur_y)
    add     a, e
    ld      e, a
    ld      a, d
    adc     a, #0
    and     #0x07
    ld      d, a
    ld      a, (s_addr_segment)
    or      d
    ld      d, a
    ret

;; Avança DE (adreça física mapejada) 1 scanline cap avall dins el ring CRTC.
;; Clobbers: A, D, E. Preserva BC i HL!
sprite_step_de:
    ld      a, d
    and     #0x38
    cp      #0x38
    jr      z, 1$
    ld      a, d
    add     a, #0x08
    ld      d, a
    ret
1$:
    ld      a, e
    add     a, #0x50
    ld      e, a
    ld      a, d
    adc     a, #0xC8            ;; +0x08 - 0x40 = -0x38 (+ carry)
    and     #0xC7               ;; manté pàgina (0xC0/0x80), RA=0 i wrap 2KB
    ld      d, a
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

;; IN: A = y. OUT: DE = adreca crua.
;; Clobbers: A,B,C,H,L.
scr_raw_first:
    push    bc
    ld      c, a
    and     #0x07
    rlca
    rlca
    rlca                  ;; A = (y&7)*8
    or      #0xC0
    ld      d, a
    ld      a, c
    and     #0xF8
    rrca
    rrca
    rrca                  ;; A = y>>3 (0..24)
    ld      l, a
    ld      h, #0
    add     hl, hl         ;; x2
    ld      b, h
    ld      c, l           ;; BC = x2
    add     hl, hl         ;; x4
    add     hl, hl         ;; x8
    push    hl
    add     hl, hl         ;; x16
    add     hl, hl         ;; x32
    add     hl, hl         ;; x64
    pop     bc             ;; BC = x8
    add     hl, bc         ;; x72
    add     hl, bc         ;; x80
    ld      a, h
    add     a, d
    ld      d, a
    ld      e, l
    pop     bc
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
    ld      a, d
    sub     #0x08
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
    push    bc
    ld      a, (_g_spr_x)
    ld      (s_cur_y), a
    ld      a, (_g_spr_y)
    call    sprite_calc_de      ;; DE = adreça física VRAM de la 1a línia
    pop     bc

blit_line:
    push    de                  ;; Desa DE d'inici de línia
    ld      hl, (s_spr_ptr)     ;; HL = sprite [inv_mask, img_masked]

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
    pop     de                  ;; Recupera DE d'inici de línia
    call    sprite_step_de      ;; Avança 1 scanline (preserva BC!)

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
;; void sprite_restore_umbrella(void)
;; void sprite_restore_carry(void)
;;   Restaura el fons del globus (1) o paraigua (2) segons estigui actiu
;; ============================================================
_sprite_restore_umbrella::
_sprite_restore_balloon::
_sprite_restore_carry::
    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 1$
    ld      a, (_s_bloon_drawn_c0)
    or      a
    ret     z
    ld      c, a                ;; C = 1 (globus) o 2 (paraigua)
    xor     a
    ld      (_s_bloon_drawn_c0), a
    ld      a, (_s_bloon_old_y_c0)
    ld      (s_cur_y), a
    ld      a, (_s_bloon_old_x_c0)
    ld      (s_bloon_cur_x), a
    ld      hl, #_s_carry_bg_c0
    jr      2$
1$:
    ld      a, (_s_bloon_drawn_80)
    or      a
    ret     z
    ld      c, a
    xor     a
    ld      (_s_bloon_drawn_80), a
    ld      a, (_s_bloon_old_y_80)
    ld      (s_cur_y), a
    ld      a, (_s_bloon_old_x_80)
    ld      (s_bloon_cur_x), a
    ld      hl, #_s_carry_bg_80
2$:
    ld      (s_bg_read_ptr), hl

    dec     c
    jr      nz, umbr_rst_start

    ;; Ballon restore: 28 linies, 4 bytes
    call    carry_calc_first
    ld      hl, (s_bg_read_ptr)
    ld      b, #28
bloon_rst_line_loop:
    push    bc
    push    de
    ldi
    ldi
    ldi
    ldi
    pop     de
    call    sprite_step_de
    pop     bc
    djnz    bloon_rst_line_loop
    ret

umbr_rst_start:
    ;; Umbrella restore: 32 linies, 10 bytes
    call    carry_calc_first
    ld      hl, (s_bg_read_ptr)
    ld      b, #32
umbr_rst_line_loop:
    push    bc
    push    de
    ld      bc, #10
    ldir
    pop     de
    call    sprite_step_de
    pop     bc
    djnz    umbr_rst_line_loop
    ret


;; Calcula el DE inicial per a carry (globus/paraigua) a (s_bloon_cur_x, s_cur_y + 1):
carry_calc_first:
    ld      a, (s_cur_y)
    inc     a
    ld      e, a
    ld      a, (s_bloon_cur_x)
    ld      (s_cur_y), a
    ld      a, e
    jp      sprite_calc_de


;; ============================================================
;; void sprite_blit_balloon(void)
;;   Dibuixa el globus vermell autèntic (0x7B20 al Banc 7)
;;   a (g_spr_x + 2, g_spr_y - 28) i desa el fons net (4B x 28 linies).
;; ============================================================
_sprite_blit_balloon::
    ld      a, (_g_spr_y)
    sub     #28
    jr      nc, 4$
    xor     a
4$:
    ld      (s_cur_y), a

    ld      a, (_g_spr_x)
    add     a, #2               ;; centrat (+2 bytes = +4 px Mode 0)
    ld      (s_bloon_cur_x), a

    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 1$
    ld      a, (s_cur_y)
    ld      (_s_bloon_old_y_c0), a
    ld      a, (s_bloon_cur_x)
    ld      (_s_bloon_old_x_c0), a
    ld      a, #1
    ld      (_s_bloon_drawn_c0), a
    jr      2$
1$:
    ld      a, (s_cur_y)
    ld      (_s_bloon_old_y_80), a
    ld      a, (s_bloon_cur_x)
    ld      (_s_bloon_old_x_80), a
    ld      a, #1
    ld      (_s_bloon_drawn_80), a
2$:

    ld      a, (_g_bank)
    push    af
    ld      a, #0xC7
    call    _bank_set

    call    carry_calc_first

    ld      a, (_g_vram_base_hi)
    cp      #0x80
    ld      bc, #_s_carry_bg_c0
    jr      nz, 3$
    ld      bc, #_s_carry_bg_80
3$:

    ld      hl, #0x7AA0         ;; BALLOON_SPRITE_FRAME al Banc 7 (0x7A20+128)
    ld      a, #28              ;; 28 linies
    ld      (s_line_cnt), a

bloon_blit_line:
    push    de

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

    pop     de
    call    sprite_step_de

    ld      a, (s_line_cnt)
    dec     a
    ld      (s_line_cnt), a
    jr      nz, bloon_blit_line

    pop     af
    call    _bank_restore
    ret


;; ============================================================
;; void sprite_blit_umbrella(void)
;;   Dibuixa el paraigües obert autèntic (0x7C00 al Banc 7)
;;   a (g_spr_x - 1, g_spr_y - 31) i desa el fons net (10B x 32 linies).
;; ============================================================
_sprite_blit_umbrella::
    ld      a, (_g_spr_y)
    sub     #31
    jr      nc, 4$
    xor     a
4$:
    ld      (s_cur_y), a

    ld      a, (_g_spr_x)
    or      a
    jr      z, 5$
    dec     a                   ;; centrat: Jake=8B, Umbrella=10B -> x-1
5$:
    ld      (s_bloon_cur_x), a

    ld      a, (_g_vram_base_hi)
    cp      #0x80
    jr      z, 1$
    ld      a, (s_cur_y)
    ld      (_s_bloon_old_y_c0), a
    ld      a, (s_bloon_cur_x)
    ld      (_s_bloon_old_x_c0), a
    ld      a, #2               ;; 2 = paraigua
    ld      (_s_bloon_drawn_c0), a
    jr      2$
1$:
    ld      a, (s_cur_y)
    ld      (_s_bloon_old_y_80), a
    ld      a, (s_bloon_cur_x)
    ld      (_s_bloon_old_x_80), a
    ld      a, #2               ;; 2 = paraigua
    ld      (_s_bloon_drawn_80), a
2$:

    ld      a, (_g_bank)
    push    af
    ld      a, #0xC7
    call    _bank_set

    call    carry_calc_first

    ld      a, (_g_vram_base_hi)
    cp      #0x80
    ld      bc, #_s_carry_bg_c0
    jr      nz, 6$
    ld      bc, #_s_carry_bg_80
6$:

    ld      hl, #0x7B80         ;; UMBRELLA_FRAME al Banc 7 (0x7A20+128+224)
    ld      a, #32              ;; 32 linies
    ld      (s_line_cnt), a

umbr_blit_line:
    push    de

    ld      a, #10
    ld      (s_byte_cnt), a
1$:
    ld      a, (de)             ;; llegeix fons net
    ld      (bc), a             ;; desa a buffer de fons
    inc     bc
    and     (hl)                ;; aplica inv_mask
    inc     hl
    or      (hl)                ;; aplica img_masked
    inc     hl
    ld      (de), a             ;; escriu a VRAM
    inc     de
    ld      a, (s_byte_cnt)
    dec     a
    ld      (s_byte_cnt), a
    jr      nz, 1$

    pop     de
    call    sprite_step_de

    ld      a, (s_line_cnt)
    dec     a
    ld      (s_line_cnt), a
    jr      nz, umbr_blit_line

    pop     af
    call    _bank_restore
    ret


;; ============================================================
;; void sprite_abort_balloon(void)
;; void sprite_abort_carry(void)
;;   Restaura els flags de dibuix en avortar carry
;; ============================================================
_sprite_abort_carry::
_sprite_abort_balloon::
    xor     a
    ld      (_s_bloon_drawn_c0), a
    ld      (_s_bloon_drawn_80), a
    ret

