;; ============================================================
;; render.s - Rutines de render en ASM (Mode 1 del CPC)
;; ============================================================
;; Interface (sdcccall 1):
;;   void render_hud(u16 ma0);   HL = ma0
;; ============================================================

    .module render
    .optsdcc -mz80 sdcccall(1)

    .globl _render_hud

    .area _CODE

;; ------------------------------------------------------------
;; push_fill: HL = dest, DE = byte count (parell), A = valor
;; Omple amb el truc PUSH (2 bytes per PUSH). Cal interrupts OFF.
;; DESTRUCTIU: A, BC, DE, HL.
;; ------------------------------------------------------------
push_fill:
    ld      c, a
    ld      b, a
    add     hl, de
    ld      (D_sp), sp
    ld      sp, hl
    srl     d
    rr      e
    ld      a, d
    or      e
    jr      z, L_pf_end
L_pf_loop:
    push    bc
    dec     de
    ld      a, d
    or      e
    jr      nz, L_pf_loop
L_pf_end:
    ld      sp, (D_sp)
    ret

;; ------------------------------------------------------------
;; render_hud(HL = ma0)
;; ------------------------------------------------------------
_render_hud::
    di
    ld      (D_ma0), hl
    ld      a, #160
    ld      (D_y), a

L_loop:
    ;; v = (y < 162) ? 0xFF : 0xAA
    ld      a, (D_y)
    cp      #162
    ld      a, #0xAA
    jr      nc, L_v
    ld      a, #0xFF
L_v:
    ld      (D_v), a

    ;; ma_start = (ma0 + (y>>3)*40) & 0x3FF
    ld      a, (D_y)
    rrca
    rrca
    rrca
    and     #0x1F
    ld      l, a
    ld      h, #0
    add     hl, hl
    add     hl, hl
    add     hl, hl
    ld      d, h
    ld      e, l
    add     hl, hl
    add     hl, hl
    add     hl, de
    ld      de, (D_ma0)
    add     hl, de
    ld      a, h
    and     #0x03
    ld      h, a
    ld      (D_ma), hl

    ;; blk = (y & 7) << 3
    ld      a, (D_y)
    and     #7
    add     a, a
    add     a, a
    add     a, a
    ld      (D_blk), a

    ;; n1 = min(40, 0x400 - ma_start)
    ld      hl, #0x0400
    ld      de, (D_ma)
    or      a
    sbc     hl, de
    ld      a, h
    or      a
    jr      nz, L_cap
    ld      a, l
    cp      #41
    jr      c, L_n1
L_cap:
    ld      hl, #40
L_n1:
    ld      (D_n1), hl

    ;; A0 = 0xC000 | (blk<<8) | (ma_start<<1)
    ld      hl, (D_ma)
    add     hl, hl
    ld      a, (D_blk)
    or      h
    or      #0xC0           ;; base de pantalla del CPC
    ld      h, a
    ld      (D_a0), hl

    ;; primer fill
    ld      hl, (D_n1)
    add     hl, hl
    ex      de, hl
    ld      hl, (D_a0)
    ld      a, (D_v)
    call    push_fill

    ;; segon fill si n1 < 40
    ld      de, (D_n1)
    ld      hl, #40
    or      a
    sbc     hl, de
    jr      z, L_next
    add     hl, hl
    ex      de, hl
    ld      a, (D_blk)
    or      #0xC0           ;; base de pantalla del CPC
    ld      h, a
    ld      l, #0
    ld      a, (D_v)
    call    push_fill

L_next:
    ld      a, (D_y)
    inc     a
    ld      (D_y), a
    cp      #200
    jp      nz, L_loop
    ei
    ret

    .area _DATA
D_ma0:  .dw 0
D_ma:   .dw 0
D_n1:   .dw 0
D_a0:   .dw 0
D_v:    .db 0
D_blk:  .db 0
D_y:    .db 0
D_sp:   .dw 0
