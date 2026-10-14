;; Masked elevator row blitter for the CRTC ring.
;; The C caller sets destination, background, sprite and byte count globals.
    .module moving_blit
    .optsdcc -mz80 sdcccall(1)

    .globl _moving_blit_span
    .globl _moving_blit_span_hflip
    .globl _moving_restore_span
    .globl _g_moving_dst
    .globl _g_moving_background
    .globl _g_moving_sprite
    .globl _g_moving_span
    .globl _g_flip_lut_hi

    .area _CODE

;; Save background, apply (screen & inv_mask) | image, and advance through
;; the same 2 KB raster segment, wrapping DE at its boundary.
_moving_blit_span::
    ld      hl, (_g_moving_sprite)
    ld      de, (_g_moving_dst)
    ld      bc, (_g_moving_background)
    ld      a, (_g_moving_span)
    or      a
    ret     z
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
    ld      a, (_g_moving_span)
    dec     a
    ld      (_g_moving_span), a
    jr      nz, 1$
    ret

;; Restore the saved background span, with the same ring-segment wrap.
_moving_restore_span::
    ld      hl, (_g_moving_background)
    ld      de, (_g_moving_dst)
    ld      a, (_g_moving_span)
    or      a
    ret     z
3$:
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     de
    ld      a, d
    and     #0x07
    or      e
    jr      nz, 4$
    ld      a, d
    sub     #0x08
    ld      d, a
4$:
    ld      a, (_g_moving_span)
    dec     a
    ld      (_g_moving_span), a
    jr      nz, 3$
    ret

;; Variante amb h-flip per als walkers del banc C6 (mateix contracte
;; que moving_blit_span, pero g_moving_sprite = PRIMER parell i el
;; recorregut es de dreta a esquerra amb mirror per byte via LUT).
;; La LUT de 256 B viu al mateix banc (s_flip_lut @0x6500, HI via
;; _g_flip_lut_hi = 0x65): llegible amb C6 paginat.
;; Contracte: cridar NOMES amb C6 paginat (src + LUT hi viuen).
_moving_blit_span_hflip::
    ld      hl, (_g_moving_sprite)
    ld      de, (_g_moving_dst)
    ld      a, (_g_moving_span)
    or      a
    ret     z
    dec     a
    ld      c, a
    ld      b, #0
    add     hl, bc
    add     hl, bc          ;; HL = darrer parell (sprite+(span-1)*2)
    ld      bc, (_g_moving_background)
    push    bc              ;; [sp] = bg (BC lliure per la LUT)
    ld      a, (_g_flip_lut_hi)
    ld      b, a            ;; B = HI LUT
    ;; HL = parell actual (-2/iter), DE = dst (+1/iter + wrap)
5$:
    ld      a, (de)         ;; pantalla
    pop     bc              ;; BC = bg
    ld      (bc), a         ;; salva fons
    inc     bc
    push    bc              ;; bg avancat
    push    af              ;; pantalla
    ld      a, (hl)         ;; mask raw
    ld      c, a
    ld      a, (bc)         ;; A = mask'
    ex      af, af'         ;; A' = mask'
    inc     hl
    ld      a, (hl)         ;; img raw
    ld      c, a
    ld      a, (bc)         ;; A = img'
    dec     hl
    dec     hl              ;; parell anterior
    ex      af, af'         ;; A = mask'
    ld      c, a            ;; C = mask'
    pop     af              ;; A = pantalla
    and     c               ;; pantalla & mask'
    ld      c, a            ;; C = combinat
    ex      af, af'         ;; A = img'
    or      c               ;; A = sortida
    ld      (de), a
    inc     de
    ld      a, d
    and     #0x07
    or      e
    jr      nz, 6$
    ld      a, d
    sub     #0x08
    ld      d, a
6$:
    ld      a, (_g_moving_span)
    dec     a
    ld      (_g_moving_span), a
    jr      nz, 5$
    pop     bc              ;; neteja [sp] = bg
    ret
