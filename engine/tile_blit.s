;; ------------------------------------------------------------
;; tile_blit.s - Copia ràpida d'un caràcter CRTC (4x8 px) al ring VRAM.
;; Entrada (__sdcccall 1): HL = 16 bytes font, global offset = MA*2.
;; ------------------------------------------------------------
    .module tile_blit
    .optsdcc -mz80 sdcccall(1)

    .globl _render_tile_fast
    .globl _render_column
    .globl _render_row
    .globl _g_render_tile_offset
    .globl _g_vram_base_hi
    .globl _cpc_bank_set
    .globl _cpc_bank_restore

    .area _DATA
s_tile_ids:     .ds 40
s_rc_char_x:    .dw 0
s_rc_subrow:    .dw 0

    .area _CODE

;; ============================================================
;; void render_tile_fast(const u8* tile)
;; Entrada (__sdcccall 1): HL = 16 bytes font, _g_render_tile_offset = MA*2.
;; ============================================================
_render_tile_fast::
    ld      de, (_g_render_tile_offset)
    ld      a, (_g_vram_base_hi)
    add     a, d
    ld      d, a                ;; DE = base page + byte offset, RA=0
_render_tile_fast_de:
    .rept 7
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     e
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     hl
    inc     hl
    dec     e
    ld      a, d
    add     a, #8
    ld      d, a
    .endm
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     e
    ld      a, (hl)
    ld      (de), a
    dec     e
    ld      a, d
    sub     #0x38               ;; Restaura DE a RA=0 (preserva BC i DE!)
    ld      d, a
    ret

;; ============================================================
;; Helper: calcula HL = TILESET (0x4000) + (A << 6) + C
;; IN:  A = tile_index, C = (tile_half_y << 5) | (tile_half_x << 1)
;; OUT: HL = adreça de la subcel·la 4x8 al Banc 4
;; Preserva BC i DE!
;; ============================================================
calc_tile_hl:
    rrca
    rrca
    ld      h, a
    and     #0xC0
    or      c
    ld      l, a
    ld      a, h
    and     #0x3F
    or      #0x40
    ld      h, a
    ret

;; ============================================================
;; Helper: calcula DE = (_g_vram_base_hi << 8) + ((((HL * 40) + DE) & 0x03FF) << 1)
;; IN:  HL = subrow, DE = char_x
;; OUT: DE = adreça física VRAM a RA=0 dins el ring de 2KB
;; ============================================================
calc_vram_de:
    add     hl, hl              ;; *2
    add     hl, hl              ;; *4
    ld      b, h
    ld      c, l                ;; BC = *4
    add     hl, hl              ;; *8
    add     hl, hl              ;; *16
    add     hl, bc              ;; *20
    add     hl, hl              ;; *40
    add     hl, de              ;; HL = subrow * 40 + char_x (ma)
    add     hl, hl              ;; HL = ma << 1
    ld      a, h
    and     #0x07
    ld      d, a
    ld      a, (_g_vram_base_hi)
    or      d
    ld      d, a
    ld      e, l
    ret

;; ============================================================
;; void render_column(u16 cam_x4, u16 cam_row, u16 sx)
;; __sdcccall(1): HL = cam_x4, DE = cam_row, (SP+2..3) = sx (2B callee cleanup)
;; ============================================================
_render_column::
    ld      c, l
    ld      b, h                ;; BC = cam_x4
    pop     hl                  ;; HL = adreça de retorn
    ex      (sp), hl            ;; HL = sx, (SP) = adreça de retorn (2B netejats!)

    ld      a, h
    or      a
    ret     nz
    ld      a, l
    cp      #40
    ret     nc

    add     hl, bc              ;; HL = cam_x4 + sx = world_char_x
    ld      (s_rc_char_x), hl
    ld      (s_rc_subrow), de

    ld      a, #0xC5
    call    _cpc_bank_set

    ;; GMAP ptr = 0x4000 + ((cam_row >> 1) << 7) + (world_char_x >> 1)
    ld      a, (s_rc_char_x)
    srl     a
    ld      c, a                ;; C = map_col (0..127)
    ld      a, (s_rc_subrow)
    ld      b, a                ;; B = cam_row_lo
    srl     a
    ld      l, a                ;; L = map_row (0..62)
    xor     a
    srl     l
    rra                         ;; L = map_row >> 1, A = (map_row & 1) << 7
    or      c                   ;; A = ((map_row & 1) << 7) | map_col
    ld      h, l
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (map_row << 7) + map_col

    ld      de, #s_tile_ids
    ld      c, b                ;; C = cam_row_lo
    ld      b, #20              ;; 20 files
rc_map_loop$:
    ld      a, (hl)
    ld      (de), a
    inc     de
    bit     0, c
    jr      z, 1$
    ld      a, l
    add     a, #0x80            ;; següent map_row (+128)
    ld      l, a
    jr      nc, 1$
    inc     h
1$:
    inc     c
    djnz    rc_map_loop$

    ld      a, #0xC4
    call    _cpc_bank_set

    ld      hl, (s_rc_subrow)
    ld      de, (s_rc_char_x)
    call    calc_vram_de        ;; DE = adreça física VRAM inicial

    ;; C = ((cam_row & 1) << 5) | ((world_char_x & 1) << 1)
    ld      a, (s_rc_subrow)
    and     #1
    rrca
    rrca
    rrca                        ;; (cam_row & 1) << 5 (0x00 o 0x20)
    ld      c, a
    ld      a, (s_rc_char_x)
    and     #1
    add     a, a                ;; (world_char_x & 1) << 1 (0x00 o 0x02)
    or      c
    ld      c, a

    ld      hl, #s_tile_ids
    ld      b, #20
rc_draw_loop$:
    ld      a, (hl)
    inc     hl
    push    hl
    call    calc_tile_hl
    call    _render_tile_fast_de
    pop     hl
    ld      a, c
    xor     #0x20               ;; alterna tile_half_y (0 <-> 0x20)
    ld      c, a
    ld      a, e
    add     a, #0x50            ;; ma += 40 (+80 bytes al ring de 2KB)
    ld      e, a
    jr      nc, 2$
    inc     d
    res     3, d
2$:
    djnz    rc_draw_loop$

    jp      _cpc_bank_restore

;; ============================================================
;; void render_row(u16 cam_x4, u16 cam_row, u16 sy)
;; __sdcccall(1): HL = cam_x4, DE = cam_row, (SP+2..3) = sy (2B callee cleanup)
;; ============================================================
_render_row::
    ld      c, l
    ld      b, h                ;; BC = cam_x4
    pop     hl                  ;; HL = adreça de retorn
    ex      (sp), hl            ;; HL = sy, (SP) = adreça de retorn (2B netejats!)

    ld      a, h
    or      a
    ret     nz
    ld      a, l
    cp      #20
    ret     nc

    add     hl, de              ;; HL = cam_row + sy = world_subrow
    ld      (s_rc_subrow), hl
    ld      (s_rc_char_x), bc

    ld      a, #0xC5
    call    _cpc_bank_set

    ;; GMAP ptr = 0x4000 + ((world_subrow >> 1) << 7) + (cam_x4 >> 1)
    ld      a, (s_rc_char_x)
    srl     a
    ld      c, a                ;; C = map_col (0..127)
    ld      a, (s_rc_subrow)
    srl     a
    ld      l, a                ;; L = map_row (0..71)
    xor     a
    srl     l
    rra
    or      c
    ld      h, l
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (map_row << 7) + map_col

    ld      de, #s_tile_ids
    ld      a, (s_rc_char_x)
    ld      c, a                ;; C = cam_x4_lo
    ld      b, #40              ;; 40 columnes
rr_map_loop$:
    ld      a, (hl)
    ld      (de), a
    inc     de
    bit     0, c
    jr      z, 1$
    inc     hl                  ;; següent map_col (+1)
1$:
    inc     c
    djnz    rr_map_loop$

    ld      a, #0xC4
    call    _cpc_bank_set

    ld      hl, (s_rc_subrow)
    ld      de, (s_rc_char_x)
    call    calc_vram_de        ;; DE = adreça física VRAM inicial

    ;; C = ((world_subrow & 1) << 5) | ((cam_x4 & 1) << 1)
    ld      a, (s_rc_subrow)
    and     #1
    rrca
    rrca
    rrca
    ld      c, a
    ld      a, (s_rc_char_x)
    and     #1
    add     a, a
    or      c
    ld      c, a

    ld      hl, #s_tile_ids
    ld      b, #40
rr_draw_loop$:
    ld      a, (hl)
    inc     hl
    push    hl
    call    calc_tile_hl
    call    _render_tile_fast_de
    pop     hl
    ld      a, c
    xor     #0x02               ;; alterna tile_half_x (0 <-> 0x02)
    ld      c, a
    inc     de
    inc     de                  ;; ma += 1 (+2 bytes al ring de 2KB)
    res     3, d
    djnz    rr_draw_loop$

    jp      _cpc_bank_restore

;; ============================================================
;; void hud_copy_strip(u16 src, u16 dst)
;; Copia el HUD (2 files de caracters = 16 scanlines de 80 B) d'una
;; pagina de VRAM a l'altra. Les scanlines d'una fila de caracters son
;; a passos de 0x800 (interleavejat CPC), per aixo el bucle.
;; __sdcccall(1): HL = src, DE = dst
;; ============================================================
_hud_copy_strip::
    ld      c, #2                 ;; 2 files de caracters (20 i 21)
hcs_row$:
    push    bc
    ld      b, #8                 ;; 8 scanlines per fila de caracters
hcs_sl$:
    push    bc
    ld      bc, #80
    ldir                          ;; HL += 80, DE += 80
    ld      bc, #(0x800-80)
    add     hl, bc                ;; seguent scanline (+0x800)
    ex      de, hl
    add     hl, bc
    ex      de, hl
    pop     bc
    djnz    hcs_sl$
    ;; Despres de 8 scanlines HL/DE han avancat 8*0x800 = 0x4000; la fila
    ;; seguent comenca a +80: restem 0x3F80 (sumem 0xC080 en 16 bits).
    ld      bc, #0xC080
    add     hl, bc
    ex      de, hl
    add     hl, bc
    ex      de, hl
    pop     bc
    dec     c
    jr      nz, hcs_row$
    ret
