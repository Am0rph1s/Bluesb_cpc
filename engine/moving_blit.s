;; ============================================================
;; moving_blit.s - Box Blitter & Ring Address en Z80 ASM pur
;; Amstrad CPC Mode 0 - Ring CRTC de 16 KB (0xC000 / 0x8000)
;; ============================================================
    .module moving_blit
    .optsdcc -mz80 sdcccall(1)

    .globl _ring_address
    .globl _moving_blit_box
    .globl _moving_restore_box
    .globl _enemy_probe_turn
    .globl _enemy_probe_floor
    .globl _g_moving_dst
    .globl _g_moving_background
    .globl _g_moving_sprite
    .globl _g_moving_span
    .globl _g_moving_rows
    .globl _g_moving_spr_skip
    .globl _bank_set
    .globl _bank_restore
    .globl _g_bank

    .area _DATA
_g_moving_dst::         .dw 0
_g_moving_background::  .dw 0
_g_moving_sprite::      .dw 0
_g_moving_span::        .db 0
_g_moving_rows::        .db 0
_g_moving_spr_skip::    .db 0
s_mov_rows:             .db 0
s_mov_cnt:              .db 0

    .area _CODE

;; ============================================================
;; u8* ring_address(u8 page, i16 x, i16 y)
;; Entrada (__sdcccall 1):
;;   A      = page (0 -> 0xC000, 1 -> 0x8000)
;;   DE     = x (px Mode 0)
;;   (SP+2) = y (px)
;; Sortida:
;;   DE     = adreça VRAM dins el ring CRTC (neteja els 2B de pila)
;; ============================================================
_ring_address::
    pop     bc                  ;; BC = adreça de retorn
    pop     hl                  ;; HL = y
    push    bc                  ;; restaura adreça de retorn (callee cleanup)

    or      a
    ld      a, #0xC0
    jr      z, 1$
    ld      a, #0x80
1$:
    ld      b, a
    ld      a, l
    and     #0x07
    rlca
    rlca
    rlca                        ;; A = (y & 7) << 3
    or      b                   ;; A = base_hi | ((y & 7) << 3)
    push    af                  ;; desa byte alt base + scanline

    ;; DE = x >> 1 (x_byte)
    sra     d
    rr      e

    ;; HL = y >> 3
    sra     h
    rr      l
    sra     h
    rr      l
    sra     h
    rr      l

    ;; HL = (y >> 3) * 80 + x_byte
    add     hl, hl              ;; *2
    add     hl, hl              ;; *4
    ld      b, h
    ld      c, l                ;; BC = *4
    add     hl, hl              ;; *8
    add     hl, hl              ;; *16
    add     hl, bc              ;; *20
    add     hl, hl              ;; *40
    add     hl, hl              ;; *80
    add     hl, de              ;; HL = (y >> 3) * 80 + x_byte

    ld      a, h
    and     #0x07               ;; offset & 0x07FF
    pop     bc                  ;; B = base_hi | ((y & 7) << 3)
    or      b
    ld      d, a
    ld      e, l                ;; DE = adreça VRAM final
    ret

;; ============================================================
;; void moving_blit_box(void)
;; Dibuixa _g_moving_rows línies de _g_moving_span bytes amb màscara,
;; desant el fons de manera contigua a _g_moving_background i avançant
;; DE pel ring CRTC (+0x0800 per scanline, +80 al canvi de fila).
;; ============================================================
_moving_blit_box::
    ld      a, (_g_moving_rows)
    or      a
    ret     z
    ld      (s_mov_rows), a
    ld      a, (_g_moving_span)
    or      a
    ret     z
    ld      hl, (_g_moving_sprite)
    ld      de, (_g_moving_dst)
    ld      bc, (_g_moving_background)

blit_box_row$:
    push    de                  ;; desa DE = inici de fila a VRAM

    ;; Comprovar si estem prop del límit circular 0x07FF ((D & 7) == 7 i E >= 0xF8)
    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, blit_try_fast$
    ld      a, e
    cp      #0xF8
    jr      nc, blit_wrap_row$

blit_try_fast$:
    ld      a, (_g_moving_span)
    cp      #8
    jr      z, blit_fast_8$
    cp      #4
    jr      z, blit_fast_4$

blit_wrap_row$:
    ld      a, (_g_moving_span)
    ld      (s_mov_cnt), a
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
    ld      a, (s_mov_cnt)
    dec     a
    ld      (s_mov_cnt), a
    jr      nz, 1$
    jr      blit_row_done$

blit_fast_8$:
    .rept 4
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
blit_fast_4$:
    .rept 4
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
    ld      a, (_g_moving_spr_skip)
    or      a
    jr      z, 3$
    add     a, l
    ld      l, a
    jr      nc, 3$
    inc     h
3$:
    pop     de                  ;; recupera DE = inici de fila a VRAM
    ;; Avançar DE 1 scanline avall en el ring CRTC:
    ld      a, d
    add     a, #0x08
    ld      d, a
    and     #0x38
    jr      nz, 4$
    ld      a, d
    sub     #0x40
    ld      d, a
    ld      a, e
    add     a, #0x50
    ld      e, a
    jr      nc, 4$
    ld      a, d
    inc     a
    and     #0xC7
    ld      d, a
4$:
    ld      a, (s_mov_rows)
    dec     a
    ld      (s_mov_rows), a
    jp      nz, blit_box_row$
    ret

;; ============================================================
;; void moving_restore_box(void)
;; Restaura _g_moving_rows línies de _g_moving_span bytes des de
;; _g_moving_background cap a _g_moving_dst usant LDIR en el cas ràpid.
;; ============================================================
_moving_restore_box::
    ld      a, (_g_moving_rows)
    or      a
    ret     z
    ld      b, a                ;; B = row_count
    ld      hl, (_g_moving_background)
    ld      de, (_g_moving_dst)

rst_box_row$:
    push    bc                  ;; desa B = row_count
    push    de                  ;; desa DE = inici de fila a VRAM
    ld      a, (_g_moving_span)
    ld      c, a

    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, rst_fast_row$
    ld      a, e
    cp      #0xF8
    jr      nc, rst_wrap_row$

rst_fast_row$:
    ld      b, #0               ;; BC = span (1..8)
    ldir                        ;; restauració directa en bloc!
    jr      rst_row_done$

rst_wrap_row$:
    ld      b, c
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
    pop     de                  ;; recupera DE = inici de fila a VRAM
    ld      a, d
    add     a, #0x08
    ld      d, a
    and     #0x38
    jr      nz, 3$
    ld      a, d
    sub     #0x40
    ld      d, a
    ld      a, e
    add     a, #0x50
    ld      e, a
    jr      nc, 3$
    ld      a, d
    inc     a
    and     #0xC7
    ld      d, a
3$:
    pop     bc
    djnz    rst_box_row$
    ret

;; ============================================================
;; Helper intern (amb Banc C5 ja paginat!):
;; IN: E = col, L = row, C = off (0..2)
;; OUT: A = TRIG_PTR[MAP_PTR[(row << 7) + col] * 10 + off] (o 0xFF si OOB)
;; Preserva BC i DE!
;; ============================================================
b5_trig_asm:
    ld      a, e
    cp      #128
    jr      nc, trig_oob$
    ld      a, l
    cp      #72
    jr      nc, trig_oob$
    xor     a
    srl     l
    rra                         ;; L = row >> 1, A = (row & 1) << 7
    or      e                   ;; A = ((row & 1) << 7) | col
    ld      h, l
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (row << 7) + col
    ld      l, (hl)             ;; L = tile_id
    ld      h, #0
    add     hl, hl              ;; *2
    push    de
    ld      d, h
    ld      e, l                ;; DE = *2
    add     hl, hl              ;; *4
    add     hl, hl              ;; *8
    add     hl, de              ;; *10
    ld      d, #0x64
    ld      e, c                ;; DE = 0x6400 + off
    add     hl, de              ;; HL = 0x6400 + tile_id * 10 + off
    pop     de
    ld      a, (hl)
    ret
trig_oob$:
    ld      a, #0xFF
    ret


;; ============================================================
;; u8 enemy_probe_floor(u8 c1, u8 c2, u8 trow)
;; __sdcccall(1): A = c1, L = c2, (SP+2) = trow (1B callee cleanup)
;; ============================================================
_enemy_probe_floor::
    ld      e, a                ;; E = c1
    ld      d, l                ;; D = c2
    pop     hl                  ;; HL = adreça de retorn
    dec     sp
    pop     bc                  ;; B = trow (neteja 1B de pila!)
    push    hl

    ld      a, b
    cp      #71
    jr      nc, epf_ret1_direct$       ;; trow >= 71 -> solid = 1

    push    bc                  ;; B = trow
    push    de                  ;; E = c1, D = c2
    ld      a, (_g_bank)
    push    af
    ld      a, #0xC5
    call    _bank_set
    pop     af
    pop     de
    pop     bc
    push    af                  ;; desa prev_bank a la pila

    ld      l, b                ;; L = trow, E = c1
    ld      c, #2
    call    b5_trig_asm
    call    epf_check_op$
    jr      nz, epf_ret1$

    ld      a, e
    cp      d                   ;; si c1 == c2, no cal segona sonda!
    jr      z, epf_ret0$

    ld      e, d                ;; E = c2
    ld      l, b                ;; L = trow
    ld      c, #2
    call    b5_trig_asm
    call    epf_check_op$
    jr      nz, epf_ret1$

epf_ret0$:
    pop     af
    call    _bank_restore
    xor     a
    ret
epf_ret1$:
    pop     af
    call    _bank_restore
    ld      a, #1
    ret
epf_ret1_direct$:
    ld      a, #1
    ret

;; Comprova si A (op) és sòlid per a un enemic/projectil (Z=0 si sòlid, Z=1 si no)
epf_check_op$:
    cp      #20
    jr      z, 1$
    cp      #21
    jr      z, 1$
    cp      #27
    jr      z, 1$
    cp      #28
    jr      z, 1$
    sub     #14
    cp      #2
    jr      c, 1$
    sub     #17
    cp      #9
    jr      c, 1$
    xor     a                   ;; Z = 1 (no sòlid)
    ret
1$:
    or      #1                  ;; Z = 0 (sòlid)
    ret

;; ============================================================
;; u8 enemy_probe_turn(u8 acol, u8 lcol, u8 r_feet, u8 r_floor, u8 r_head, u8 bit, u8 on_ground)
;; __sdcccall(1): A = acol, L = lcol, (SP+2..6) = r_feet, r_floor, r_head, bit, on_ground
;; Neteja 5B de pila. Retorna A (0 o 1).
;; ============================================================
_enemy_probe_turn::
    push    ix
    ld      ix, #0
    add     ix, sp
    ld      d, a                ;; D = acol
    ld      e, l                ;; E = lcol

    push    de
    ld      a, (_g_bank)
    push    af
    ld      a, #0xC5
    call    _bank_set
    pop     af
    pop     de
    push    af                  ;; desa prev_bank

    ld      a, 8(ix)            ;; on_ground
    or      a
    jr      z, ept_walls$

    ;; b5_trig(lcol, r_floor, 0) == 1
    ld      l, 5(ix)            ;; L = r_floor, E = lcol
    ld      c, #0
    call    b5_trig_asm
    dec     a
    jr      z, ept_turn1$

    ;; b5_trig(acol, r_feet, 0) == 1
    ld      e, d                ;; E = acol
    ld      l, 4(ix)            ;; L = r_feet
    ld      c, #0
    call    b5_trig_asm
    dec     a
    jr      z, ept_turn1$

    ;; b5_trig(acol, r_head, 0) == 1 (Row 61 Col 33 pel policia 1r pis)
    ld      e, d                ;; E = acol
    ld      l, 6(ix)            ;; L = r_head
    ld      c, #0
    call    b5_trig_asm
    dec     a
    jr      z, ept_turn1$

ept_walls$:
    ld      e, d                ;; E = acol
    ld      l, 4(ix)            ;; L = r_feet
    ld      c, #1
    call    b5_trig_asm
    cp      #0xFF
    jr      nz, 1$
    xor     a
1$:
    ld      b, a                ;; B = fl
    ld      l, 6(ix)            ;; L = r_head
    ld      c, #1
    call    b5_trig_asm
    cp      #0xFF
    jr      nz, 2$
    xor     a
2$:
    or      b                   ;; fl | fh
    and     7(ix)               ;; & bit
    jr      nz, ept_turn1$
    ld      b, #0
    jr      ept_done$
ept_turn1$:
    ld      b, #1
ept_done$:
    pop     af
    call    _bank_restore
    ld      a, b
    pop     ix
    pop     hl                  ;; adreça de retorn
    inc     sp
    inc     sp
    inc     sp
    inc     sp
    inc     sp                  ;; neteja 5 bytes de pila
    jp      (hl)


