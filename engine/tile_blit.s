;; ------------------------------------------------------------
;; tile_blit.s - Copia ràpida d'un caràcter CRTC (4x8 px) al ring VRAM.
;; Entrada (__sdcccall 1): HL = 16 bytes font, global offset = MA*2.
;; ------------------------------------------------------------
    .module tile_blit
    .optsdcc -mz80 sdcccall(1)

    .globl _render_tile_fast
    .globl _render_column
    .globl _render_row
    .globl _render_tile_world
    .globl _render_all
    .globl _render_room
    .globl _get_trig_byte
    .globl _tile_type
    .globl _tile_flags
    .globl _is_floor_solid
    .globl _anim_tick_c5
    .globl _fdc_crc16
    .globl _enemy_room_exit
    .globl _g_render_tile_offset
    .globl _g_vram_base_hi
    .globl _cpc_bank_set
    .globl _cpc_bank_restore
    .globl _bank_set
    .globl _bank_restore
    .globl _call_banked
    .globl _s_lv
    .globl _g_cam_x4
    .globl _s_conveyor_tick
    .globl _s_conveyor_phase
    .globl _s_anim_pos
    .globl _bc_a
    .globl _bc_b
    .globl _bc_c
    .globl _bc_d
    .globl _bc_e
    .globl _g_mag_elevators

    .area _DATA
s_tile_ids:     .ds 40
s_rc_char_x:    .dw 0
s_rc_subrow:    .dw 0
s_rtw_tile:     .db 0
s_rtw_prev_b:   .db 0
s_rtw_cx:       .dw 0
s_rtw_cy:       .dw 0
s_rtw_sx:       .dw 0
s_rtw_sy:       .dw 0
s_rr_base_col:  .dw 0
s_rr_r_off:     .dw 0
s_rr_r:         .db 0
s_rr_c:         .db 0
s_at_sp:        .dw 0
s_at_n:         .db 0

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
;; void render_all(u16 cam_x4, u16 cam_row)
;; __sdcccall(1): HL = cam_x4, DE = cam_row
;; ============================================================
_render_all::
    ld      bc, #0
ra_loop$:
    push    hl
    push    de
    push    bc
    push    bc                  ;; arg 3 (sx) a la pila (neteja 2B per _render_column)
    call    _render_column
    pop     bc
    pop     de
    pop     hl
    inc     c
    ld      a, c
    cp      #40
    jr      c, ra_loop$
    ret

;; ============================================================
;; void render_tile_world(u8 tile_index, u16 col, u16 row, u16 cam_x4, u16 cam_row)
;; __sdcccall(1): A = tile_index, DE = col,
;;                (SP+2..3) = row, (SP+4..5) = cam_x4, (SP+6..7) = cam_row
;; Callee neteja 6 B de la pila!
;; ============================================================
_render_tile_world::
    ld      (s_rtw_tile), a
    ex      de, hl
    add     hl, hl              ;; HL = cx = col << 1
    ld      (s_rtw_cx), hl

    pop     bc                  ;; BC = adreça de retorn
    pop     de                  ;; DE = row
    ex      de, hl              ;; DE = cx, HL = row
    add     hl, hl              ;; HL = cy = row << 1
    ld      (s_rtw_cy), hl

    pop     hl                  ;; HL = cam_x4
    ex      de, hl              ;; HL = cx, DE = cam_x4
    or      a
    sbc     hl, de              ;; HL = sx = cx - cam_x4
    ld      (s_rtw_sx), hl

    pop     de                  ;; DE = cam_row
    push    bc                  ;; Restaura adreça de retorn (6 B netejats!)
    ld      hl, (s_rtw_cy)
    or      a
    sbc     hl, de              ;; HL = sy = cy - cam_row
    ld      (s_rtw_sy), hl

    ld      a, #0xC4
    call    _bank_set
    ld      (s_rtw_prev_b), a

    ld      c, #0x00            ;; sub = 0 -> C = (0 << 5) = 0x00
    call    rtw_subrow$
    ld      hl, (s_rtw_sy)
    inc     hl
    ld      (s_rtw_sy), hl
    ld      hl, (s_rtw_cy)
    inc     hl
    ld      (s_rtw_cy), hl
    ld      c, #0x20            ;; sub = 1 -> C = (1 << 5) = 0x20
    call    rtw_subrow$

    ld      a, (s_rtw_prev_b)
    jp      _bank_restore

rtw_subrow$:
    ld      hl, (s_rtw_sy)
    bit     7, h
    ret     nz                  ;; sy < 0
    ld      a, h
    or      a
    ret     nz                  ;; sy >= 256
    ld      a, l
    cp      #20
    ret     nc                  ;; sy >= 20

    ld      hl, (s_rtw_cy)
    ld      de, (s_rtw_cx)
    push    bc
    call    calc_vram_de        ;; DE = adreça física VRAM per (cx, cy)
    pop     bc

    ;; Comprova sx >= 0 && sx < 40
    ld      hl, (s_rtw_sx)
    bit     7, h
    jr      nz, rtw_check_sx1$
    ld      a, h
    or      a
    jr      nz, rtw_check_sx1$
    ld      a, l
    cp      #40
    jr      nc, rtw_check_sx1$

    ld      a, (s_rtw_tile)
    call    calc_tile_hl        ;; preserva BC i DE
    call    _render_tile_fast_de ;; preserva BC i DE

rtw_check_sx1$:
    ld      hl, (s_rtw_sx)
    inc     hl                  ;; HL = sx + 1
    bit     7, h
    ret     nz
    ld      a, h
    or      a
    ret     nz
    ld      a, l
    cp      #40
    ret     nc

    inc     de
    inc     de                  ;; (ma + 1) & 0x03FF -> +2 bytes al ring de 2KB
    res     3, d
    inc     c
    inc     c                   ;; tile_half_x = 1 (+2)
    ld      a, (s_rtw_tile)
    call    calc_tile_hl
    jp      _render_tile_fast_de

;; ============================================================
;; void render_room(u8 room_idx)
;; __sdcccall(1): A = room_idx (ignorat: usa _g_cam_x4 directament!)
;; base_col = _g_cam_x4 >> 1, cam_x4 = _g_cam_x4
;; ============================================================
_render_room::
    ld      hl, (_g_cam_x4)
    srl     h
    rr      l                   ;; HL = base_col = _g_cam_x4 >> 1
    ld      (s_rr_base_col), hl
    xor     a
    ld      (s_rr_r), a
rr_row_loop$:
    ld      a, (s_rr_r)
    add     a, a
    ld      e, a
    ld      d, #0
    ld      hl, #(_s_lv + 14)   ;; s_lv.room_rowoff
    add     hl, de
    ld      e, (hl)
    inc     hl
    ld      d, (hl)             ;; DE = s_lv.room_rowoff[r]
    ld      hl, (s_rr_base_col)
    add     hl, de
    ld      (s_rr_r_off), hl
    xor     a
    ld      (s_rr_c), a
rr_col_loop$:
    ld      a, (_s_lv + 3)      ;; s_lv.room_cols
    ld      b, a
    ld      a, (s_rr_c)
    cp      b
    jr      nc, rr_next_row$

    ld      a, #0xC5
    call    _bank_set
    ld      b, a                ;; B = prev_b
    ld      hl, (_s_lv + 56)    ;; s_lv.rooms_off
    ld      de, (s_rr_r_off)
    add     hl, de
    ld      a, (s_rr_c)
    ld      e, a
    ld      d, #0
    add     hl, de
    ld      c, (hl)             ;; C = t (tile id)
    ld      a, b
    push    bc
    call    _bank_restore
    pop     bc                  ;; C = t

    ;; Crida render_tile_world(t, base_col + c, room_row0 + r, cam_x4, room_cam_row)
    ld      a, (_s_lv + 8)      ;; s_lv.room_cam_row
    ld      l, a
    ld      h, #0
    push    hl                  ;; arg 5: cam_row
    ld      hl, (_g_cam_x4)
    push    hl                  ;; arg 4: cam_x4
    ld      a, (_s_lv + 5)      ;; s_lv.room_row0
    ld      hl, #s_rr_r
    add     a, (hl)
    ld      l, a
    ld      h, #0
    push    hl                  ;; arg 3: row
    ld      hl, (s_rr_base_col)
    ld      a, (s_rr_c)
    ld      e, a
    ld      d, #0
    add     hl, de
    ex      de, hl              ;; DE = arg 2: col = base_col + c
    ld      a, c                ;; A = arg 1: tile_index = t
    call    _render_tile_world

    ld      hl, #s_rr_c
    inc     (hl)
    jr      rr_col_loop$

rr_next_row$:
    ld      hl, #s_rr_r
    inc     (hl)
    ld      a, (hl)
    cp      #10
    jr      c, rr_row_loop$
    ret

;; ============================================================
;; u8 get_trig_byte(u16 col, u16 row, u8 offset)
;; __sdcccall(1): HL = col, DE = row, (SP+2) = offset (1 B callee cleanup!)
;; Retorna A = byte del trigger (o 0xFF si fora de mapa / buit).
;; ============================================================
_get_trig_byte::
    pop     bc                  ;; BC = adreça de retorn
    dec     sp
    pop     af                  ;; A = offset (1 B netejat de la pila!)
    push    bc                  ;; Restaura adreça de retorn
    ld      c, a                ;; C = offset

    ;; Si H != 0 o D != 0 -> fora de mapa (0xFF)
    ld      a, h
    or      d
    jp      nz, gtb_ret_ff$

    ;; Ara L = col (0..255), E = row (0..255), C = offset
    ;; Comprova si som dins d'una habitació:
    ;; row >= room_row0 && row < room_row0 + room_rows && col < room_total_cols
    ld      a, (_s_lv + 5)      ;; A = room_row0
    ld      b, a
    ld      a, e
    sub     b                   ;; A = row - room_row0
    jr      c, gtb_main_map$    ;; row < room_row0 -> mapa principal
    ld      b, a                ;; B = row - room_row0
    ld      a, (_s_lv + 4)      ;; A = room_rows
    cp      b
    jr      c, gtb_main_map$
    jr      z, gtb_main_map$    ;; (row - room_row0) >= room_rows -> mapa principal
    ld      a, (_s_lv + 7)      ;; A = room_total_cols
    cp      l
    jr      c, gtb_main_map$
    jr      z, gtb_main_map$    ;; col >= room_total_cols -> mapa principal

    ;; Dins l'habitació: t = ((u8*)rooms_off)[room_rowoff[B] + L]
    push    bc                  ;; desa B = r_idx, C = offset
    ld      e, l                ;; E = col
    ld      a, #0xC5
    push    de
    call    _bank_set
    pop     de
    pop     bc
    ld      d, a                ;; D = prev_bank, E = col, B = r_idx, C = offset

    ld      a, b
    add     a, a                ;; r_idx * 2
    add     a, #<(_s_lv + 14)
    ld      l, a
    ld      a, #0
    adc     a, #>(_s_lv + 14)
    ld      h, a
    ld      a, (hl)
    inc     hl
    ld      h, (hl)
    add     a, e                ;; + col
    ld      l, a
    jr      nc, 1$
    inc     h
1$:
    push    de                  ;; desa D = prev_bank
    ld      de, (_s_lv + 56)    ;; s_lv.rooms_off
    add     hl, de
    ld      e, (hl)             ;; E = tile id
    pop     af                  ;; A = prev_bank (era D!)
    ld      d, a                ;; D = prev_bank
    jr      gtb_lookup_trig$

gtb_main_map$:
    ;; Comprova col < map_w && row < map_h
    ld      a, (_s_lv + 52)     ;; s_lv.map_w
    cp      l
    jr      c, gtb_ret_ff$
    jr      z, gtb_ret_ff$
    ld      a, (_s_lv + 53)     ;; s_lv.map_h
    cp      e
    jr      c, gtb_ret_ff$
    jr      z, gtb_ret_ff$

    push    bc                  ;; C = offset
    push    de                  ;; E = row
    push    hl                  ;; L = col
    ld      a, #0xC5
    call    _bank_set
    pop     hl                  ;; L = col
    pop     de                  ;; E = row
    pop     bc                  ;; C = offset
    ld      d, a                ;; D = prev_bank

    ;; HL = 0x4000 + (row << 7) + col
    ld      a, e
    srl     a
    ld      h, a
    ld      a, #0
    rra
    or      l
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (row << 7) + col
    ld      e, (hl)             ;; E = tile id

gtb_lookup_trig$:
    ;; E = tile id, D = prev_bank, C = offset
    ld      a, e
    cp      #0xFF
    jr      z, gtb_restore$
    ld      l, e
    ld      h, #0
    ld      b, h                ;; BC = offset (B=0, C=offset)
    add     hl, hl              ;; *2
    add     hl, hl              ;; *4
    add     hl, bc              ;; *4 + offset
    ld      c, e
    add     hl, bc              ;; *5 + offset
    ld      bc, (_s_lv + 69)    ;; s_lv.trig_off
    add     hl, bc
    ld      e, (hl)             ;; E = trig byte

gtb_restore$:
    ld      a, d                ;; A = prev_bank
    push    de                  ;; desa E = resultat
    call    _bank_restore
    pop     de
    ld      a, e
    ret

gtb_ret_ff$:
    ld      a, #0xFF
    ret

;; ============================================================
;; u8 tile_type(u16 col, u16 row)
;; __sdcccall(1): HL = col, DE = row -> retorna A
;; ============================================================
_tile_type::
    xor     a
    push    af
    inc     sp
    call    _get_trig_byte
    cp      #0xFF
    ret     nz
    ld      a, #1
    ret

;; ============================================================
;; u8 tile_flags(u16 col, u16 row)
;; __sdcccall(1): HL = col, DE = row -> retorna A
;; ============================================================
_tile_flags::
    ld      a, #1
    push    af
    inc     sp
    call    _get_trig_byte
    cp      #0xFF
    ret     nz
    xor     a
    ret

;; ============================================================
;; u8 is_floor_solid(u16 col, u16 row, i16 vy, u8 crouch)
;; __sdcccall(1): HL = col, DE = row, (SP+2..3) = vy, (SP+4) = crouch
;; Callee neteja 3 B de la pila! Retorna A.
;; ============================================================
_is_floor_solid::
    pop     iy                  ;; IY = adreça de retorn
    pop     bc                  ;; BC = vy (B = vy_hi)
    dec     sp
    pop     af                  ;; A = crouch
    push    iy                  ;; Restaura adreça de retorn (3 B netejats!)
    ld      c, a                ;; C = crouch, B = vy_hi

    ;; Calcula B_pos = (vy >= 0) ? 1 : 0
    ;; Comprova si row >= room_row0
    ld      a, d
    or      a
    jr      nz, ifs_ret_vy_ge0$ ;; row >= 256 -> sempre >= room_row_last
    ld      a, (_s_lv + 5)      ;; room_row0
    cp      e
    jr      z, ifs_in_room$
    jr      c, ifs_in_room$     ;; e >= room_row0

    ;; Mapa principal: if (row >= map_h - 1) return (vy >= 0);
    ld      a, (_s_lv + 53)     ;; map_h
    dec     a
    cp      e
    jr      z, ifs_ret_vy_ge0$
    jr      c, ifs_ret_vy_ge0$
    jr      ifs_check_op$

ifs_in_room$:
    ;; Habitació: if (row >= room_row_last) return (vy >= 0);
    ld      a, (_s_lv + 68)     ;; room_row_last
    cp      e
    jr      z, ifs_ret_vy_ge0$
    jr      c, ifs_ret_vy_ge0$

ifs_check_op$:
    push    bc                  ;; desa B = vy_hi, C = crouch
    ld      a, #2
    push    af
    inc     sp
    call    _get_trig_byte      ;; A = op
    pop     bc                  ;; B = vy_hi, C = crouch
    cp      #0xFF
    jr      z, ifs_ret_0$

    ;; Ops sòlides sempre: 0, 1, 2, 3, 20, 21, 27, 28, 29, 40
    cp      #4
    jr      c, ifs_ret_1$       ;; 0, 1, 2, 3
    cp      #20
    jr      z, ifs_ret_1$
    cp      #21
    jr      z, ifs_ret_1$
    cp      #27
    jr      z, ifs_ret_1$
    cp      #28
    jr      z, ifs_ret_1$
    cp      #29
    jr      z, ifs_ret_1$
    cp      #40
    jr      z, ifs_ret_1$

    ;; Si vy < 0 (bit 7 de B == 1), retorna 0
    bit     7, b
    jr      nz, ifs_ret_0$

    ;; vy >= 0:
    ;; if (op == 14 || op == 15 || op == 22) return !crouch;
    cp      #14
    jr      z, ifs_not_crouch$
    cp      #15
    jr      z, ifs_not_crouch$
    cp      #22
    jr      z, ifs_not_crouch$
    ;; if (op == 30) return 1; (op 32..39 son rampes diagonals gestionades per moving_bank)
    cp      #30
    jr      z, ifs_ret_1$
ifs_check_24$:
    cp      #24
    jr      nz, ifs_ret_0$
    ld      a, #2
    ret

ifs_not_crouch$:
    ld      a, c
    or      a
    jr      nz, ifs_ret_0$
ifs_ret_1$:
    ld      a, #1
    ret
ifs_ret_0$:
    xor     a
    ret
ifs_ret_vy_ge0$:
    bit     7, b
    jr      nz, ifs_ret_0$
    ld      a, #1
    ret

;; ============================================================
;; void anim_tick_c5(void)
;; Avança les seqüències d'animació de tiles del Banc 5 cada 4 ticks.
;; bc_a=sp, bc_b=n, bc_c=data, bc_d=offs, bc_e=lens.
;; 0 bytes d'IX stack frame!
;; ============================================================
_anim_tick_c5::
    ld      hl, #_s_conveyor_tick
    inc     (hl)
    ld      a, (hl)
    cp      #4
    ret     c
    ld      (hl), #0
    ld      hl, #_s_conveyor_phase
    inc     (hl)

    ;; 1. Avançar 1 pas cada seqüència (lens té sentinella 0)
    ld      hl, (_bc_e)         ;; HL = lens
    ld      de, #_s_anim_pos    ;; DE = s_anim_pos
at_seq_loop$:
    ld      a, (hl)
    or      a
    jr      z, at_seq_done$
    ld      c, a                ;; C = lens[q]
    ld      a, (de)
    inc     a
    cp      c
    jr      c, 1$
    xor     a
1$:
    ld      (de), a
    inc     hl
    inc     de
    jr      at_seq_loop$

at_seq_done$:
    ld      a, (_bc_b)
    or      a
    ret     z
    ld      (s_at_n), a
    ld      hl, (_bc_a)
    ld      (s_at_sp), hl

at_span_loop$:
    ld      iy, (s_at_sp)
    ;; seq = sp->seq (offset +3)
    ld      e, 3(iy)
    ld      d, #0
    ld      hl, (_bc_d)         ;; offs
    add     hl, de
    ld      a, (hl)             ;; A = offs[seq]
    ld      hl, #_s_anim_pos
    add     hl, de
    add     a, (hl)             ;; A = offs[seq] + s_anim_pos[seq]
    ld      e, a
    ld      hl, (_bc_c)         ;; data
    add     hl, de
    ld      c, (hl)             ;; C = tile

    ;; dst = 0x4000 + (sp->row << 7) + sp->col_start
    ld      a, 0(iy)            ;; sp->row
    srl     a
    ld      h, a
    ld      a, #0
    rra
    or      1(iy)               ;; | sp->col_start
    ld      l, a
    set     6, h                ;; HL = dst

    ld      a, (hl)
    cp      c
    jr      z, at_span_next$    ;; Si ja té aquest tile, saltar!

    ld      a, 2(iy)            ;; sp->col_end
    sub     1(iy)               ;; - sp->col_start
    inc     a
    ld      b, a                ;; B = count
at_fill_loop$:
    ld      (hl), c
    inc     hl
    djnz    at_fill_loop$

at_span_next$:
    ld      hl, (s_at_sp)
    ld      de, #4
    add     hl, de
    ld      (s_at_sp), hl
    ld      hl, #s_at_n
    dec     (hl)
    jr      nz, at_span_loop$
    ret

;; ============================================================
;; u16 fdc_crc16(const u8* p, u16 len)
;; __sdcccall(1): HL = p, DE = len -> retorna DE = crc
;; 0 bytes d'IX stack frame!
;; ============================================================
_fdc_crc16::
    ld      bc, #0xFFFF         ;; BC = crc
crc_byte_loop$:
    ld      a, d
    or      e
    jr      z, crc_done$
    dec     de
    ld      a, (hl)
    inc     hl
    xor     b
    ld      b, a
    push    hl
    ld      l, #8
crc_bit_loop$:
    sla     c
    rl      b
    jr      nc, 1$
    ld      a, c
    xor     #0x21
    ld      c, a
    ld      a, b
    xor     #0x10
    ld      b, a
1$:
    dec     l
    jr      nz, crc_bit_loop$
    pop     hl
    jr      crc_byte_loop$
crc_done$:
    ld      e, c
    ld      d, b
    ret

;; ============================================================
;; void enemy_room_exit(i16 px, i16 py)
;; __sdcccall(1): HL = px, DE = py
;; ============================================================
_enemy_room_exit::
    ld      (_bc_a), hl
    ld      (_bc_b), de
    ld      hl, #(_g_mag_elevators + 10)
    ld      de, #16
    ld      b, #8
    xor     a
ere_loop$:
    ld      (hl), a             ;; drawn[0] = 0
    inc     hl
    ld      (hl), a             ;; drawn[1] = 0
    dec     hl
    add     hl, de
    djnz    ere_loop$
    ld      de, #0x5A12         ;; EN_SLOT(6)
    ld      a, #0xC6
    jp      _call_banked


