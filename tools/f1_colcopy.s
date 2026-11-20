;; ============================================================
;; f1_colcopy.s - Mesura la copia d'una columna (320 B) entre
;; les pagines 0xC000 i 0x8000 amb el ring CRTC.
;; RAM0:0x3C00, nomes registres principals (l'ISR no preserva AF').
;; 10 iteracions, delta de g_ticks a 0x3F00.
;; ============================================================
    .module f1_colcopy
    .optsdcc -mz80

    .area _CODE

_start::
    ld      sp, #0x3FFE
    ei

    ld      a, #10
    ld      (0x3F30), a
    ld      a, (0x360C)
    ld      (0x3F10), a

iter_loop:
    call    colcopy
    ld      a, (0x3F30)
    dec     a
    ld      (0x3F30), a
    jr      nz, iter_loop

    ld      a, (0x360C)
    ld      l, a
    ld      a, (0x3F10)
    ld      h, a
    ld      a, l
    sub     h
    ld      (0x3F00), a

forever:
    jr      forever

;; Copia 20 files x 8 blocs x 2 bytes = 320 B de 0xC000 a 0x8000.
colcopy:
    ld      hl, #0xC000
    ld      de, #0x8000
    ld      a, #8
    ld      (0x3F21), a        ;; comptador de blocs a memoria
cb_block:
    ld      a, #20
    ld      (0x3F20), a
cb_row:
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     de
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     de
    ld      bc, #78            ;; seguent fila (+80 - 2)
    add     hl, bc
    ex      de, hl
    add     hl, bc
    ex      de, hl
    ld      a, (0x3F20)
    dec     a
    ld      (0x3F20), a
    jr      nz, cb_row
    ld      bc, #0x01C0        ;; seguent bloc (+0x800 - 20*80)
    add     hl, bc
    ex      de, hl
    add     hl, bc
    ex      de, hl
    ld      a, (0x3F21)
    dec     a
    ld      (0x3F21), a
    jr      nz, cb_block
    ret
