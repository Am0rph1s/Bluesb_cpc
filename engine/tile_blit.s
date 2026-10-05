;; ------------------------------------------------------------
;; tile_blit.s - Copia ràpida d'un caràcter CRTC (4x8 px) al ring VRAM.
;; Entrada (__sdcccall 1): HL = 16 bytes font, global offset = MA*2.
;; ------------------------------------------------------------
    .module tile_blit
    .optsdcc -mz80 sdcccall(1)

    .globl _render_tile_fast
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
