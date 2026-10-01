;; ============================================================
;; level.s - Redibuix de la columna de tiles entrant, en ASM (Mode 1)
;; Interface (sdcccall 1): void asm_column(const ColArgs* a);
;;   ColArgs: { u16 ma0@0; u16 col@2; u8 c_off@4; }
;;   Redibuixa 20 files (srow = row + 124) del subtile de la columna
;;   (col) a les 8 linies de cada fila, a x = c_off (0 o 39).
;; ============================================================

    .module level
    .optsdcc -mz80 sdcccall(1)

    .globl _asm_column
    .globl _asm_row
    .globl _asm_box_solid

    .area _CODE

;; ============================================================
;; asm_box_solid: u8 asm_box_solid(const BoxArgs* a)
;;   BoxArgs: { u16 wx@0; u16 py@2; }
;;   Mirall de box_solid()/level_solid(): retorna 1 si la caixa
;;   [wx,wx+7]x[py,py+30] toca un tile solid (trig tile_type 2/3/14/15
;;   o la fila de seguretat 143).
;; ============================================================
_asm_box_solid::
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (B_wx), de
    inc     hl
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (B_py), de

    ;; c0 = wx>>1 ; c1 = (wx+7)>>1
    ld      hl, (B_wx)
    srl     h
    rr      l
    ld      a, l
    ld      (B_c0), a
    ld      hl, (B_wx)
    ld      de, #7
    add     hl, de
    srl     h
    rr      l
    ld      a, l
    ld      (B_c1), a

    ;; r0 = py>>3 ; r1 = (py+30)>>3
    ld      hl, (B_py)
    srl     h
    rr      l
    srl     h
    rr      l
    srl     h
    rr      l
    ld      a, l
    ld      (B_r0), a
    ld      hl, (B_py)
    ld      de, #30
    add     hl, de
    srl     h
    rr      l
    srl     h
    rr      l
    srl     h
    rr      l
    ld      a, l
    ld      (B_r1), a

    ld      a, (B_r0)
    ld      (B_r), a
K_row:
    ld      a, (B_r)
    ld      b, a
    ld      a, (B_r1)
    cp      b
    jp      c, K_none          ;; r1 < r -> cap solid
    ld      a, (B_r)
    add     a, #124
    ld      (B_srow), a
    cp      #144
    jp      nc, K_rownext      ;; per sota del nivell -> no solid
    cp      #143
    jp      z, K_solid         ;; fila de seguretat -> solid

    ld      a, (B_c0)
    ld      (B_c), a
K_col:
    ld      a, (B_c)
    ld      b, a
    ld      a, (B_c1)
    cp      b
    jp      c, K_rownext
    ;; offset = (srow>>1)*128 + (c>>1)   dins GMAP (0x7000)
    ld      a, (B_srow)
    srl     a
    ld      l, a
    ld      h, #0
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl              ;; (srow>>1)*128
    ld      a, (B_c)
    srl     a
    ld      e, a
    ld      d, #0
    add     hl, de
    ld      de, #0x7000
    add     hl, de
    ld      a, (hl)
    and     #0x7F
    ;; *10 = *8 + *2
    ld      l, a
    ld      h, #0
    add     hl, hl              ;; *2
    push    hl
    add     hl, hl
    add     hl, hl              ;; *8
    pop     de                  ;; DE = *2
    add     hl, de              ;; *10
    ld      de, #0x9400
    add     hl, de
    inc     hl
    inc     hl                  ;; +2 -> op_func
    ld      a, (hl)
    cp      #25
    jp      nz, K_solid         ;; op_func != 25 -> solid (terra)
    ld      a, (B_c)
    inc     a
    ld      (B_c), a
    jp      K_col
K_rownext:
    ld      a, (B_r)
    inc     a
    ld      (B_r), a
    jp      K_row
K_solid:
    ld      a, #1
    ret
K_none:
    xor     a
    ret

;; subptr: entrada HL = scol, A = srow ; sortida HL = punter al subtile 8x8
;;   TILESET=0x3000, GMAP=0x7000
subptr:
    ld      c, a                ;; C = srow
    and     #1
    ld      (P_sr0), a          ;; srow & 1
    ld      a, l
    and     #1
    ld      (P_co), a           ;; scol & 1
    srl     h
    rr      l                   ;; HL = tcol = scol>>1
    ld      a, c
    srl     a
    ld      (P_tr), a           ;; trow
    ld      d, h
    ld      e, l                ;; DE = tcol
    ld      a, (P_tr)
    ld      l, a
    ld      h, #0
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl              ;; *128
    add     hl, de              ;; + tcol
    ld      de, #0x7000
    add     hl, de
    ld      a, (hl)             ;; b
    ld      c, a
    and     #0x7F
    ld      e, a                ;; num
    ld      a, c
    rlca
    and     #1
    ld      d, a                ;; half
    ;; quad = ((srow&1)<<1)|(scol&1)
    ld      a, (P_sr0)
    add     a, a
    ld      c, a
    ld      a, (P_co)
    or      c
    ld      (P_quad), a
    ;; idx = half*512 + num*4 + quad
    ld      a, d
    ld      l, a
    ld      h, #0
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl              ;; half*512
    ld      a, e
    ld      c, a
    ld      b, #0
    add     hl, bc
    add     hl, bc
    add     hl, bc
    add     hl, bc              ;; + num*4
    ld      a, (P_quad)
    ld      c, a
    ld      b, #0
    add     hl, bc              ;; + quad
    add     hl, hl
    add     hl, hl
    add     hl, hl
    add     hl, hl              ;; idx*16
    ld      de, #0x3000
    add     hl, de
    ret

_asm_column::
    push    hl
    ld      hl, (_g_c_col)
    inc     hl
    ld      (_g_c_col), hl
    pop     hl
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (C_ma0), de
    inc     hl
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (C_col), de
    inc     hl
    ld      a, (hl)
    ld      (C_coff), a

    xor     a
    ld      (C_row), a
K_loo:
    ld      a, (C_row)
    cp      #20
    jp      z, K_done
    ld      c, a
    ld      a, (_g_cam_subrow)
    add     a, c                ;; srow = row + g_cam_subrow
    ld      hl, (C_col)
    call    subptr
    ld      (C_tile), hl

    ;; base = ((ma0 + row*40 + c_off) & 0x3FF) << 1
    ld      a, (C_row)
    ld      l, a
    ld      h, #0
    add     hl, hl
    add     hl, hl
    add     hl, hl
    ld      d, h
    ld      e, l
    add     hl, hl
    add     hl, hl
    add     hl, de              ;; *40
    ld      a, (C_coff)
    ld      e, a
    ld      d, #0
    add     hl, de
    ld      de, (C_ma0)
    add     hl, de
    ld      a, h
    and     #3
    ld      h, a
    add     hl, hl              ;; << 1 = base
    ld      (C_base), hl

    ld      a, #0
    ld      (C_i), a
K_i:
    ;; addr = 0xC000 | (i<<11) | base
    ld      a, (C_i)
    add     a, a
    add     a, a
    add     a, a                ;; i*8
    ld      h, a
    ld      a, (C_base+1)
    or      h
    or      #0xC0
    ld      h, a
    ld      a, (C_base)
    ld      l, a
    ld      (C_addr), hl

    ;; tile[i*2], tile[i*2+1]
    ld      a, (C_i)
    add     a, a
    ld      e, a
    ld      d, #0
    ld      hl, (C_tile)
    add     hl, de
    ld      a, (hl)
    ld      hl, (C_addr)
    ld      (hl), a
    inc     hl
    ld      a, (C_i)
    add     a, a
    inc     a
    ld      e, a
    ld      d, #0
    ld      hl, (C_tile)
    add     hl, de
    ld      a, (hl)
    ld      hl, (C_addr)
    inc     hl
    ld      (hl), a

    ld      a, (C_i)
    inc     a
    ld      (C_i), a
    cp      #8
    jp      nz, K_i

    ld      a, (C_row)
    inc     a
    ld      (C_row), a
    jp      K_loo
K_done:
    ret

;; ============================================================
;; asm_row: redibuixa UNA fila sencera (40 subtiles) en ASM.
;; Interface (sdcccall 1): void asm_row(const RowArgs* a);
;;   RowArgs: { u16 row_ma@0; u16 col0@2; u16 srow@4; }
;;   row_ma = (s_ma_base + scr_row*40) & 0x3FF
;;   col0   = s_step (columna de nivell de la columna 0 de pantalla)
;;   srow   = fila de nivell (subtile) a mostrar
;; ============================================================
_asm_row::
    push    hl
    ld      hl, (_g_c_row)
    inc     hl
    ld      (_g_c_row), hl
    pop     hl
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (R_rma), de
    inc     hl
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (R_col0), de
    inc     hl
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (R_srow), de

    xor     a
    ld      (R_col), a
R_loop:
    ld      a, (R_col)
    cp      #41                ;; 41 columnes: cobreix tambe el mig caracter de R3
    jp      z, R_done
    ld      e, a
    ld      d, #0
    ld      hl, (R_col0)
    add     hl, de
    ld      a, (R_srow)
    call    subptr
    ld      (R_tile), hl

    ;; base = ((row_ma + col) & 0x3FF) << 1
    ld      a, (R_col)
    ld      e, a
    ld      d, #0
    ld      hl, (R_rma)
    add     hl, de
    ld      a, h
    and     #3
    ld      h, a
    add     hl, hl
    ld      (R_base), hl

    xor     a
    ld      (R_i), a
R_ln:
    ld      a, (R_i)
    add     a, a
    add     a, a
    add     a, a
    ld      h, a
    ld      a, (R_base+1)
    or      h
    or      #0xC0
    ld      h, a
    ld      a, (R_base)
    ld      l, a
    ld      (R_addr), hl

    ld      a, (R_i)
    add     a, a
    ld      e, a
    ld      d, #0
    ld      hl, (R_tile)
    add     hl, de
    ld      a, (hl)
    ld      hl, (R_addr)
    ld      (hl), a
    inc     hl
    ld      a, (R_i)
    add     a, a
    inc     a
    ld      e, a
    ld      d, #0
    ld      hl, (R_tile)
    add     hl, de
    ld      a, (hl)
    ld      hl, (R_addr)
    inc     hl
    ld      (hl), a

    ld      a, (R_i)
    inc     a
    ld      (R_i), a
    cp      #8
    jp      nz, R_ln

    ld      a, (R_col)
    inc     a
    ld      (R_col), a
    jp      R_loop
R_done:
    ret

    .area _DATA
C_ma0:  .dw 0
C_col:  .dw 0
C_coff: .db 0
C_row:  .db 0
C_i:    .db 0
C_base: .dw 0
C_tile: .dw 0
C_addr: .dw 0
P_co:   .db 0
P_tr:   .db 0
P_sr0:  .db 0
P_quad: .db 0
B_wx:   .dw 0
B_py:   .dw 0
B_c0:   .db 0
B_c1:   .db 0
B_r0:   .db 0
B_r1:   .db 0
B_r:    .db 0
B_c:    .db 0
B_srow: .db 0
R_rma:  .dw 0
R_col0: .dw 0
R_srow: .dw 0
R_col:  .db 0
R_i:    .db 0
R_base: .dw 0
R_tile: .dw 0
R_addr: .dw 0
