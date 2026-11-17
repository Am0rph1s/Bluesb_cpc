;; ============================================================
;; ram2_code.s - Rutines critiques permanents a RAM 2 (0xB200..0xB5FF)
;; Sempre mapejades (0x8000..0xBFFF) en tots els bancs (C0/C4/C5/C6/C7).
;; Carregat un sol cop a l'inici des de MUSBANK (C1:0x6030 -> 0xB200).
;; ============================================================
    .module ram2_code
    .optsdcc -mz80 sdcccall(1)

    .globl _ring_address
    .globl _moving_blit_box
    .globl _moving_restore_box
    .globl _ram2_hud_copy
    .globl _ram2_en2_clip

    .globl _g_vram_start
    .globl _g_moving_sprite
    .globl _g_moving_dst
    .globl _g_moving_background
    .globl _g_moving_span
    .globl _g_moving_rows
    .globl _g_moving_spr_skip
    .globl _g_en_view_x
    .globl _g_en_view_y
    .globl _g_en_clip_x0
    .globl _g_en_clip_x1
    .globl _g_en_clip_y0
    .globl _g_en_clip_y1
    .globl _g_en_start_byte
    .globl _g_en_byte_count
    .globl _g_en_start_row
    .globl _g_en_row_count

    .area _DATA
    .area _CODE

;; ============================================================
;; u8* ring_address(u8 page, i16 x, i16 y) __sdcccall(1)
;;   A = page (0->0xC000, 1->0x8000), DE = x, (SP+2) = y -> DE = VRAM
;; ============================================================
_ring_address::
    pop     bc
    pop     hl
    push    bc

    or      a
    ld      a, #0xC0
    jr      z, ra_pg$
    ld      a, #0x80
ra_pg$:
    ld      b, a
    ld      a, l
    and     #0x07
    rlca
    rlca
    rlca
    or      b
    push    af

    sra     d
    rr      e

    sra     h
    rr      l
    sra     h
    rr      l
    sra     h
    rr      l

    add     hl, hl
    add     hl, hl
    ld      b, h
    ld      c, l
    add     hl, hl
    add     hl, hl
    add     hl, bc
    add     hl, hl
    add     hl, hl
    add     hl, de

    ld      a, h
    and     #0x07
    pop     bc
    or      b
    ld      d, a
    ld      e, l
    ret

;; ============================================================
;; void moving_blit_box(void)
;; ============================================================
_moving_blit_box::
    ld      a, (_g_moving_rows)
    or      a
    ret     z
    ld      h, a                ;; H = rows
    ld      a, (_g_moving_span)
    or      a
    ret     z
    cp      #13
    ret     nc
    ld      a, (_g_moving_spr_skip)
    ld      l, a                ;; L = spr_skip
    push    ix
    push    hl
    pop     ix                  ;; IXH = rows, IXL = spr_skip
    ld      a, (_g_moving_span)
    neg
    add     a, #12
    ld      e, a
    add     a, a
    add     a, a
    add     a, a
    add     a, e                ;; *9
    ld      e, a
    ld      d, #0
    ld      iy, #blit_fast_12$
    add     iy, de
    ld      hl, (_g_moving_sprite)
    ld      de, (_g_moving_dst)
    ld      bc, (_g_moving_background)

blit_box_row$:
    push    de
    ld      a, e
    cp      #0xF4
    jr      c, blit_fast_row$
    ld      a, d
    and     #0x07
    cp      #0x07
    jr      z, blit_wrap_row$

blit_fast_row$:
    jp      (iy)

blit_wrap_row$:
    ld      a, (_g_moving_span)
    ld      (s_mov_cnt$), a
1$:
    ld      a, (de)
    ld      (bc), a
    inc     bc
    and     (hl)
    inc     hl
    or      (hl)
    inc     hl
    ld      (de), a
    inc     de
    ld      a, d
    and     #0x07
    or      e
    jr      nz, 2$
    ld      a, d
    sub     #0x08
    ld      d, a
2$:
    ld      a, (s_mov_cnt$)
    dec     a
    ld      (s_mov_cnt$), a
    jr      nz, 1$
    jr      blit_row_done$

blit_fast_12$:
    .rept 12
    ld      a, (de)
    ld      (bc), a
    inc     bc
    and     (hl)
    inc     hl
    or      (hl)
    inc     hl
    ld      (de), a
    inc     de
    .endm

blit_row_done$:
    .db     0xDD, 0x7D          ;; ld a, ixl (spr_skip)
    add     a, l
    ld      l, a
    jr      nc, 3$
    inc     h
3$:
    pop     de
    ld      a, d
    add     a, #0x08
    ld      d, a
    jr      nc, 4$
    ld      a, e
    add     a, #0x50
    ld      e, a
    ld      a, d
    adc     a, #0xC0
    and     #0xC7
    ld      d, a
4$:
    .db     0xDD, 0x25          ;; dec ixh
    jp      nz, blit_box_row$
    pop     ix
    ret

;; ============================================================
;; void moving_restore_box(void)
;; ============================================================
_moving_restore_box::
    ld      a, (_g_moving_rows)
    or      a
    ret     z
    ld      h, a                ;; H = row_count
    ld      a, (_g_moving_span)
    or      a
    ret     z
    cp      #13
    ret     nc
    push    ix
    push    hl
    pop     ix                  ;; IXH = row_count
    neg
    add     a, #12
    add     a, a
    ld      e, a
    ld      d, #0
    ld      iy, #rst_fast_12$
    add     iy, de
    ld      hl, (_g_moving_background)
    ld      de, (_g_moving_dst)

rst_box_row$:
    push    de
    ld      a, e
    cp      #0xF0
    jr      c, rst_fast_row$
    ld      a, d
    and     #0x07
    cp      #0x07
    jr      z, rst_wrap_row$

rst_fast_row$:
    jp      (iy)

rst_fast_12$:
    .rept 12
    ldi
    .endm
    jr      rst_row_done$

rst_wrap_row$:
    ld      a, (_g_moving_span)
    ld      b, a
1$:
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     de
    ld      a, d
    and     #0x07
    or      e
    jr      nz, 2$
    ld      a, d
    sub     #0x08
    ld      d, a
2$:
    djnz    1$

rst_row_done$:
    pop     de
    ld      a, d
    add     a, #0x08
    ld      d, a
    jr      nc, 3$
    ld      a, e
    add     a, #0x50
    ld      e, a
    ld      a, d
    adc     a, #0xC0
    and     #0xC7
    ld      d, a
3$:
    .db     0xDD, 0x25          ;; dec ixh
    jp      nz, rst_box_row$
    pop     ix
    ret

;; ============================================================
;; void ram2_hud_copy(u8 full_v) __sdcccall(1)
;;   A = full_v (0: nomes banda interior + extrems; !=0: 16 linies completes)
;; ============================================================
_ram2_hud_copy::
    ld      (s_hb_full$), a
    ld      hl, (_g_vram_start)
    ld      de, #800
    add     hl, de
    ld      a, h
    and     #0x03
    ld      h, a
    push    hl                  ;; (SP) = ma20

    ld      a, (s_hb_full$)
    or      a
    jr      nz, hcv_rows$

    call    hcv_ma_de$
    call    hcv_ff2_ra01$
    pop     hl
    push    hl
    ld      de, #39
    add     hl, de
    call    hcv_ma_de$
    call    hcv_ff2_ra01$
    pop     hl
    push    hl
    ld      de, #40
    add     hl, de
    call    hcv_ma_de$
    set     4, d
    set     5, d
    call    hcv_ff2_ra01$
    pop     hl
    push    hl
    ld      de, #79
    add     hl, de
    call    hcv_ma_de$
    set     4, d
    set     5, d
    call    hcv_ff2_ra01$

hcv_rows$:
    pop     hl
    push    hl
    ld      de, #0x8760
    ld      (s_hb_src$), de
    ld      a, (s_hb_full$)
    or      a
    ld      bc, #0x0008
    jr      nz, 1$
    ld      bc, #0x1006
1$:
    call    hcv_copy_row$

    pop     hl
    ld      de, #40
    add     hl, de
    ld      a, h
    and     #0x03
    ld      h, a
    ld      de, #0x87B0
    ld      (s_hb_src$), de
    ld      a, (s_hb_full$)
    or      a
    ld      bc, #0x0008
    jr      nz, 2$
    ld      bc, #0x0006
2$:
hcv_copy_row$:
    ld      a, c
    ld      (s_hb_cnt$), a
    add     hl, hl
    ld      a, h
    or      #0xC0
    ld      d, a
    ld      e, l
    ld      (s_hb_dst$), de
    ld      a, h
    cp      #0x07
    jr      c, hcv_nowrap$
    ld      a, l
    cp      #0xB1
    jr      c, hcv_nowrap$
    neg
    jr      hcv_gotn1$
hcv_nowrap$:
    ld      a, #80
hcv_gotn1$:
    ld      (s_hb_n1$), a

hcv_line_loop$:
    ld      hl, (s_hb_src$)
    ld      a, h
    or      b
    ld      h, a
    ld      de, (s_hb_dst$)
    ld      a, d
    or      b
    ld      d, a
    ld      a, (s_hb_n1$)
    cp      #80
    jr      nz, hcv_wrap_line$
    push    bc
    call    hcv_ldi_40$
    call    hcv_ldi_40$
    pop     bc
    jr      hcv_line_next$
hcv_wrap_line$:
    push    bc
    call    hcv_ldi_any$
    ld      a, d
    sub     #0x08
    ld      d, a
    ld      e, #0
    ld      a, (s_hb_n1$)
    neg
    add     a, #80
    call    hcv_ldi_any$
    pop     bc
hcv_line_next$:
    ld      a, b
    add     a, #8
    ld      b, a
    ld      hl, #s_hb_cnt$
    dec     (hl)
    jr      nz, hcv_line_loop$
    ret

hcv_ma_de$:
    ld      a, h
    and     #0x03
    ld      h, a
    add     hl, hl
    ld      a, h
    or      #0xC0
    ld      d, a
    ld      e, l
    ret

hcv_ff2_ra01$:
    ld      a, #0xFF
    ld      (de), a
    inc     e
    ld      (de), a
    set     3, d
    ld      (de), a
    dec     e
    ld      (de), a
    ret

hcv_ldi_any$:
    cp      #41
    jr      c, hcv_le40$
    push    af
    call    hcv_ldi_40$
    pop     af
    sub     #40
hcv_le40$:
    neg
    add     a, #40
    add     a, a
    ld      c, a
    ld      b, #0
    push    hl
    ld      hl, #hcv_ldi_40$
    add     hl, bc
    ex      (sp), hl
    ret
hcv_ldi_40$:
    .rept 40
    ldi
    .endm
    ret

;; ============================================================
;; u8 ram2_en2_clip(i16 x, i16 y) __sdcccall(1)
;;   Entrada: HL = x, DE = y, (_g_en_byte_count) = w, (_g_en_row_count) = h
;;   Sortida: A = 1 si visible, 0 si fora de pantalla
;; ============================================================
_ram2_en2_clip::
    ld      (s_rc_x$), hl
    ld      (s_rc_y$), de
    push    de                  ;; desa y

    ld      de, (_g_en_view_x)
    call    rc_cmp_hl_de$
    jr      nc, 1$
    ex      de, hl
1$:
    ld      (_g_en_clip_x0), hl

    ld      hl, (s_rc_x$)
    ld      a, (_g_en_byte_count)
    ld      c, a
    ld      b, #0
    add     hl, bc              ;; HL = x + w
    push    hl
    ld      hl, (_g_en_view_x)
    ld      de, #160
    add     hl, de
    ex      de, hl              ;; DE = view_x + 160
    pop     hl
    call    rc_cmp_hl_de$
    jr      c, 2$
    ex      de, hl
2$:
    ld      (_g_en_clip_x1), hl

    ex      de, hl              ;; DE = x1
    ld      hl, (_g_en_clip_x0)
    call    rc_cmp_hl_de$
    jr      c, 3$
    pop     de
    xor     a
    ret
3$:
    ld      hl, (_g_en_clip_x0)
    ld      de, (s_rc_x$)
    or      a
    sbc     hl, de
    srl     h
    rr      l
    ld      a, l
    ld      (_g_en_start_byte), a

    ld      hl, (_g_en_clip_x1)
    ld      de, (_g_en_clip_x0)
    or      a
    sbc     hl, de
    srl     h
    rr      l
    ld      a, l
    or      a
    jr      nz, 4$
    pop     de
    ret
4$:
    ld      (_g_en_byte_count), a

    pop     hl                  ;; HL = y
    ld      de, (_g_en_view_y)
    call    rc_cmp_hl_de$
    jr      nc, 5$
    ex      de, hl
5$:
    ld      (_g_en_clip_y0), hl

    ld      hl, (s_rc_y$)
    ld      a, (_g_en_row_count)
    ld      c, a
    ld      b, #0
    add     hl, bc              ;; HL = y + h
    push    hl
    ld      hl, (_g_en_view_y)
    ld      de, #160
    add     hl, de
    ex      de, hl              ;; DE = view_y + 160
    pop     hl
    call    rc_cmp_hl_de$
    jr      c, 6$
    ex      de, hl
6$:
    ld      (_g_en_clip_y1), hl

    ex      de, hl              ;; DE = y1
    ld      hl, (_g_en_clip_y0)
    call    rc_cmp_hl_de$
    jr      c, 7$
    xor     a
    ret
7$:
    ld      hl, (_g_en_clip_y0)
    ld      de, (s_rc_y$)
    or      a
    sbc     hl, de
    ld      a, l
    ld      (_g_en_start_row), a

    ld      hl, (_g_en_clip_y1)
    ld      de, (_g_en_clip_y0)
    or      a
    sbc     hl, de
    ld      a, l
    ld      (_g_en_row_count), a
    or      a
    ret     z
    ld      a, #1
    ret

;; Carry = 1 si signed HL < DE; Carry = 0 si signed HL >= DE (preserva HL, DE)
rc_cmp_hl_de$:
    ld      a, h
    xor     d
    jp      m, 1$
    ld      a, h
    cp      d
    ret     nz
    ld      a, l
    cp      e
    ret
1$:
    ld      a, h
    rla
    ret

;; Variables scratch dins RAM 2 (sense consum de Bloc 0)
s_mov_cnt$:     .db 0
s_hb_full$:     .db 0
s_hb_cnt$:      .db 0
s_hb_n1$:       .db 0
s_hb_src$:      .dw 0
s_hb_dst$:      .dw 0
s_rc_x$:        .dw 0
s_rc_y$:        .dw 0
