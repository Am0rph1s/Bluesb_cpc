;; ------------------------------------------------------------
;; tile_blit.s - Copia ràpida d'un caràcter CRTC (4x8 px) al ring VRAM.
;; Entrada (__sdcccall 1): HL = 16 bytes font, global offset = MA*2.
;; ------------------------------------------------------------
    .module tile_blit
    .optsdcc -mz80 sdcccall(1)

    .globl _render_tile_fast
    .globl _hud_blit_col
    .globl _g_render_tile_offset
    .globl _g_vram_base_hi

    .area _CODE

_render_tile_fast::
    ld      de, (_g_render_tile_offset)
    ld      a, (_g_vram_base_hi)
    add     a, d
    ld      d, a                 ;; DE = base page + byte offset, RA=0
    .rept 7
    push    de                  ;; conservar columna/offset en cada raster
    .rept 2
    ldi                         ;; 2 bytes = un caràcter CRTC = 4 px Mode 0
    .endm
    inc     hl                  ;; saltar l'altra meitat horitzontal del tile
    inc     hl
    pop     de
    ld      a, d
    add     a, #8                ;; següent banc RA
    ld      d, a
    .endm
    .rept 2
    ldi
    .endm
    ret

;; ============================================================
;; void hud_blit_col(const u8* strip24, u16 ma20)
;;   HL = strip24 (24 bytes: 12B per sy=20 ra=2..7, 12B per sy=21 ra=0..5)
;;   DE = ma20 (0..0x03FF, adreça MA de la fila sy=20 per a aquesta columna)
;; ============================================================
_hud_blit_col::
    push    de
    ex      de, hl
    add     hl, hl
    ld      a, (_g_vram_base_hi)
    add     a, h
    ld      h, a
    ex      de, hl

    ld      a, #0xFF
    ld      (de), a
    inc     e
    ld      (de), a
    dec     e
    ld      a, d
    add     a, #8
    ld      d, a
    ld      a, #0xFF
    ld      (de), a
    inc     e
    ld      (de), a
    dec     e
    ld      a, d
    add     a, #8
    ld      d, a

    ld      b, #6
1$:
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     e
    ld      a, (hl)
    ld      (de), a
    inc     hl
    dec     e
    ld      a, d
    add     a, #8
    ld      d, a
    djnz    1$

    pop     de
    push    hl
    ld      hl, #40
    add     hl, de
    ld      a, h
    and     #0x03
    ld      h, a
    add     hl, hl
    ld      a, (_g_vram_base_hi)
    add     a, h
    ld      d, a
    ld      e, l
    pop     hl

    ld      b, #6
2$:
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     e
    ld      a, (hl)
    ld      (de), a
    inc     hl
    dec     e
    ld      a, d
    add     a, #8
    ld      d, a
    djnz    2$

    ld      a, #0xFF
    ld      (de), a
    inc     e
    ld      (de), a
    dec     e
    ld      a, d
    add     a, #8
    ld      d, a
    ld      a, #0xFF
    ld      (de), a
    inc     e
    ld      (de), a
    ret
