;; ============================================================
;; bank5_table.s - Taula de salts i rutines ASM del Banc 5 (CP-2.2)
;; ============================================================
    .module bank5_table
    .optsdcc -mz80 sdcccall(1)

    .globl _moving_bank_update
    .globl _moving_bank_popup_restore
    .globl _moving_bank_push
    .globl _moving_bank_find
    .globl _moving_bank_init
    .globl _moving_bank_conveyor
    .globl _moving_bank_respawn
    .globl _b5_trig_ptr
    .globl _b5_tile_type
    .globl _b5_set_tile
    .globl _b5_world_reset_tile
    .globl _s_lv
    .globl _s_popup_drawn
    .globl _s_popup_dst
    .globl _s_popup_bg
    .globl _s_rep_n
    .globl _s_rep_col
    .globl _s_rep_row
    .globl _s_rep_tile
    .globl _s_rep_pages
    .globl _bc_a
    .globl _bc_b
    .globl _bc_c
    .globl _bc_r
    .globl _g_moving_dst
    .globl _g_moving_background
    .globl _g_moving_span
    .globl _g_moving_rows
    .globl _moving_restore_box

    .area _CODE

_bc_update::
    jp      _moving_bank_update         ;; slot 0 -> 0x6E00
_bc_restore::
    jp      _moving_bank_popup_restore  ;; slot 1 -> 0x6E03
_bc_draw::
    ret                                 ;; slot 2 (sense ús) -> 0x6E06
    nop
    nop
_bc_push::
    jp      _moving_bank_push           ;; slot 3 -> 0x6E09
_bc_find::
    jp      _moving_bank_find           ;; slot 4 -> 0x6E0C
_bc_init::
    jp      _moving_bank_init           ;; slot 5 -> 0x6E0F
_bc_conveyor::
    jp      _moving_bank_conveyor       ;; slot 6 -> 0x6E12
_bc_respawn::
    jp      _moving_bank_respawn        ;; slot 7 -> 0x6E15 (reinici de nivell)

;; ============================================================
;; const u8* b5_trig_ptr(u8 col, u8 row)
;; Entrada: A = col, L = row. Sortida: DE = &TRIG_PTR[t * 10] o 0
;; ============================================================
_b5_trig_ptr::
    cp      #128
    jr      nc, trig_null$
    ld      c, a
    ld      a, l
    cp      #72
    jr      nc, trig_null$
    srl     a
    ld      h, a
    ld      a, #0
    rra
    or      c
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (row << 7) + col
    ld      l, (hl)             ;; L = tile id
    ld      h, #0
    ld      d, h
    ld      e, l                ;; DE = tile id
    add     hl, hl              ;; *2
    add     hl, hl              ;; *4
    add     hl, de              ;; *5 (TRIG compacte: 5 B/entrada)
    ld      de, (_s_lv + 69)    ;; DE = trig_off (dins C5; struct empaquetat)
    add     hl, de
    ex      de, hl
    ret
trig_null$:
    ld      de, #0
    ret

;; ============================================================
;; u8 b5_tile_type(u8 col, u8 row)
;; Entrada: A = col, L = row. Sortida: A = p ? p[0] : 0
;; ============================================================
_b5_tile_type::
    call    _b5_trig_ptr
    ld      a, d
    or      e
    ret     z
    ld      a, (de)
    ret

;; ============================================================
;; void b5_set_tile(u8 col, u8 row, u8 new_tile)
;; Entrada (__sdcccall 1): A = col, L = row, (sp+2) = new_tile
;; ============================================================
_b5_set_tile::
    pop     de                  ;; DE = return addr (SP apunta ara a new_tile)
    dec     sp
    pop     bc                  ;; B = new_tile, i SP avança +1B netejant l'argument!
    push    de
    ld      c, b                ;; C = new_tile
    ld      b, l                ;; B = row
    ld      e, a                ;; E = col
    ld      a, e
    cp      #128
    ret     nc
    ld      a, b
    cp      #72
    ret     nc
b5_set_tile_ebc$:
    ld      a, b
    srl     a
    ld      h, a
    ld      a, #0
    rra
    or      e
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (row << 7) + col
    ld      (hl), c             ;; MAP_MUT[...] = new_tile
    ld      a, (_s_rep_n)
    cp      #3
    ret     nc
    ld      l, a
    inc     a
    ld      (_s_rep_n), a
    ld      d, #0               ;; E = col
    ld      a, e                ;; A = col
    ld      e, l                ;; DE = i (0..2)
    ld      hl, #_s_rep_col
    add     hl, de
    ld      (hl), a             ;; s_rep_col[i] = col
    ld      hl, #_s_rep_row
    add     hl, de
    ld      (hl), b             ;; s_rep_row[i] = row
    ld      hl, #_s_rep_tile
    add     hl, de
    ld      (hl), c             ;; s_rep_tile[i] = new_tile
    ld      hl, #_s_rep_pages
    add     hl, de
    ld      (hl), #3            ;; s_rep_pages[i] = 3
    ret

;; ============================================================
;; void b5_world_reset_tile(u8 col, u8 row)
;; Entrada: A = col, L = row
;; ============================================================
_b5_world_reset_tile::
    cp      #128
    ret     nc
    ld      e, a                ;; E = col
    ld      a, l
    cp      #72
    ret     nc
    ld      b, a                ;; B = row
    srl     a
    ld      h, a
    ld      a, #0
    rra
    or      e
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (row << 7) + col
    ld      a, (hl)             ;; A = n = *mp
    push    hl
    ld      d, #8
1$:
    inc     hl                  ;; 1:1 DOS (level.c:832): cerca fons cap a la DRETA primer
    cp      (hl)
    jr      nz, 3$
    dec     d
    jr      nz, 1$
    pop     hl
    push    hl
    ld      d, #8
2$:
    dec     hl                  ;; Fallback cap a l'esquerra si a la dreta no hi ha fons
    cp      (hl)
    jr      nz, 3$
    dec     d
    jr      nz, 2$
3$:
    ld      c, (hl)             ;; C = m != n (fons trobat netament)
    pop     hl                  ;; equilibra pila
    jr      b5_set_tile_ebc$

;; ============================================================
;; void moving_bank_popup_restore(void)
;; ============================================================
_moving_bank_popup_restore::
    ld      a, (_bc_a)
    cp      #2
    ret     nc
    ld      c, a
    ld      b, #0
    ld      hl, #_s_popup_drawn
    add     hl, bc
    ld      a, (hl)
    or      a
    ret     z
    ld      (hl), #0
    ld      hl, #_s_popup_dst
    add     hl, bc
    add     hl, bc
    ld      e, (hl)
    inc     hl
    ld      d, (hl)
    ld      (_g_moving_dst), de
    ld      hl, #_s_popup_bg
    dec     c
    jr      nz, 1$
    ld      de, #28
    add     hl, de
1$:
    ld      (_g_moving_background), hl
    ld      a, #4
    ld      (_g_moving_span), a
    ld      a, #7
    ld      (_g_moving_rows), a
    jp      _moving_restore_box

;; ============================================================
;; void moving_bank_push(void)
;; ============================================================
_moving_bank_push::
    ld      a, (_bc_c)
    ld      l, a
    ld      a, (_bc_a)
    call    _b5_trig_ptr
    ld      a, d
    or      e
    jr      z, push_zero$
    inc     de
    inc     de
    ld      a, (de)
    push    af                  ;; B = op0
    ld      a, (_bc_c)
    ld      l, a
    ld      a, (_bc_b)
    call    _b5_trig_ptr
    pop     bc
    ld      a, d
    or      e
    jr      z, push_zero$
    inc     de
    inc     de
    ld      a, (de)
    ld      c, a                ;; C = op1

    ;; 1. Deteccio de gel (op=30 o rampes 32..35)
    ld      a, b
    cp      #30
    jr      z, ice_on$
    cp      #32
    jr      c, chk_c$
    cp      #36
    jr      c, ice_on$
chk_c$:
    ld      a, c
    cp      #30
    jr      z, ice_on$
    cp      #32
    jr      c, ice_off$
    cp      #36
    jr      c, ice_on$
ice_off$:
    xor     a
    jr      ice_set$
ice_on$:
    ld      a, #1
ice_set$:
    ld      (_g_on_ice), a

    ;; 2. Arrossegament de cintes (op 27/28) i lliscament de rampes (32..35)
    ld      hl, #0
    ld      a, b
    cp      #27
    jr      z, push_r$
    cp      #34
    jr      z, push_r$
    cp      #35
    jr      z, push_r$
    ld      a, c
    cp      #27
    jr      z, push_r$
    cp      #34
    jr      z, push_r$
    cp      #35
    jr      nz, chk_l$
push_r$:
    ld      hl, #16
chk_l$:
    ld      a, b
    cp      #28
    jr      z, push_l$
    cp      #32
    jr      z, push_l$
    cp      #33
    jr      z, push_l$
    ld      a, c
    cp      #28
    jr      z, push_l$
    cp      #32
    jr      z, push_l$
    cp      #33
    jr      nz, push_done$
push_l$:
    ld      de, #-16
    add     hl, de
push_done$:
    ld      (_bc_r), hl
    ret
push_zero$:
    ld      hl, #0
    ld      (_bc_r), hl
    xor     a
    ld      (_g_on_ice), a
    ret

