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

    .area _B5TBL (ABS)
    .org  0x7FE8

_bc_update::
    jp      _moving_bank_update         ;; slot 0 -> 0x7FE8
_bc_restore::
    jp      _moving_bank_popup_restore  ;; slot 1 -> 0x7FEB
_bc_draw::
    ret                                 ;; slot 2 (sense us) -> 0x7FEE
    nop
    nop
_bc_push::
    jp      _moving_bank_push           ;; slot 3 -> 0x7FF1
_bc_find::
    jp      _moving_bank_find           ;; slot 4 -> 0x7FF4
_bc_init::
    jp      _moving_bank_init           ;; slot 5 -> 0x7FF7
_bc_conveyor::
    jp      _moving_bank_conveyor       ;; slot 6 -> 0x7FFA
_bc_respawn::
    jp      _moving_bank_respawn        ;; slot 7 -> 0x7FFD (reinici de nivell)

    .area _CODE

;; ============================================================
;; const u8* b5_trig_ptr(u8 col, u8 row)
;; Entrada: A = col, L = row. Sortida: DE = &TRIG_PTR[t * 5] o 0
;; ============================================================
_b5_trig_ptr::
    call    b5_cell_ptr$
    jr      c, trig_null$
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
;; b5_cell_ptr$ (Helper intern)
;; Resol l'adreça de la cel·la a C5 tant per al món com per a sales
;; Entrada: A = col, L = row
;; Sortida: CF = 0 i HL = adreça de la cel·la a C5 (0x4000..0x7FFF)
;;          CF = 1 si fora de límits
;; Modifica: AF, BC, HL
;; ============================================================
b5_cell_ptr$:
    ld      c, a                ;; C = col
    ld      a, (_s_lv + 5)      ;; A = room_row0
    cp      #255
    jr      z, cell_world$
    ld      b, a                ;; B = room_row0
    ld      a, l                ;; A = row
    sub     b                   ;; A = row - room_row0
    jr      c, cell_world$      ;; si row < room_row0 -> món
    ;; --- Dins de sales ---
    ld      b, a                ;; B = r_rel
    ld      hl, #(_s_lv + 4)
    ld      a, (hl)             ;; A = room_rows
    cp      b
    jr      z, cell_err$
    jr      c, cell_err$
    inc     hl
    inc     hl
    inc     hl                  ;; HL = _s_lv + 7
    ld      a, (hl)             ;; A = room_total_cols
    cp      c
    jr      z, cell_err$
    jr      c, cell_err$
    ld      a, b                ;; A = r_rel (0..9)
    add     a, a                ;; r_rel * 2
    ld      hl, #(_s_lv + 14)   ;; &s_lv.room_rowoff[0]
    add     a, l
    ld      l, a
    jr      nc, 1$
    inc     h
1$:
    ld      a, (hl)
    inc     hl
    ld      h, (hl)
    ld      l, a                ;; HL = s_lv.room_rowoff[r_rel]
    ld      b, #0               ;; BC = col
    add     hl, bc              ;; HL += col
    ld      bc, (_s_lv + 56)    ;; BC = s_lv.rooms_off
    add     hl, bc              ;; HL += rooms_off
    or      a                   ;; CF = 0
    ret
cell_world$:
    ld      a, c                ;; A = col
    cp      #128
    jr      nc, cell_err$
    ld      a, l                ;; A = row
    cp      #100
    jr      nc, cell_err$
    srl     a
    ld      h, a
    ld      a, #0
    rra
    or      c
    ld      l, a
    set     6, h                ;; HL = 0x4000 + (row << 7) + col
    or      a                   ;; CF = 0
    ret
cell_err$:
    scf                         ;; CF = 1
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
    push    bc                  ;; save new_tile in C
    ld      e, a                ;; E = col
    ld      b, l                ;; B = row
    push    de                  ;; save col in E
    push    bc                  ;; save row in B
    call    b5_cell_ptr$
    jr      nc, 1$
    pop     bc
    pop     de
    pop     bc
    ret
1$:
    pop     bc                  ;; B = row
    pop     de                  ;; E = col
    pop     af                  ;; A = new_tile (salvat abans)
    ld      c, a                ;; C = new_tile
    jr      b5_write_and_repaint$

;; ============================================================
;; void b5_world_reset_tile(u8 col, u8 row)
;; Entrada: A = col, L = row
;; ============================================================
_b5_world_reset_tile::
    ld      e, a                ;; E = col
    ld      b, l                ;; B = row
    push    de                  ;; save col in E
    push    bc                  ;; save row in B
    call    b5_cell_ptr$
    jr      nc, 10$
    pop     bc
    pop     de
    ret
10$:
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
    ld      a, (hl)             ;; A = m != n (fons trobat netament)
    pop     hl                  ;; HL = cell ptr original
    pop     bc                  ;; B = row
    pop     de                  ;; E = col
    ld      c, a                ;; C = background tile (després de restaurar BC)
    ;; cau a b5_write_and_repaint$

;; Entrada: HL = adreça cel·la C5, E = col, B = row, C = new_tile
b5_write_and_repaint$:
    ld      (hl), c             ;; MAP_MUT[...] o ROOMS[...] = new_tile
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

    ;; 1. Deteccio de gel (op=30 o rampes 32..35 i gel 36..39)
    ld      a, b
    cp      #30
    jr      z, ice_on$
    cp      #32
    jr      c, chk_c$
    cp      #40
    jr      c, ice_on$
chk_c$:
    ld      a, c
    cp      #30
    jr      z, ice_on$
    cp      #32
    jr      c, ice_off$
    cp      #40
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

