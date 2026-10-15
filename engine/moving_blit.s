;; Masked elevator row blitter for the CRTC ring.
;; The C caller sets destination, background, sprite and byte count globals.
    .module moving_blit
    .optsdcc -mz80 sdcccall(1)

    .globl _moving_blit_span
    .globl _moving_restore_span
    .globl _g_moving_dst
    .globl _g_moving_background
    .globl _g_moving_sprite
    .globl _g_moving_span

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
