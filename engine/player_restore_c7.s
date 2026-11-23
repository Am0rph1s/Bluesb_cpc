;; ============================================================
;; player_restore_c7.s - bucle de restore del jugador al Banc 7
;; Es munta a C7:0x7E80 (128 B lliures entre el carry bg i la LUT).
;; Entrada: HL = buffer de fons (a C7), DE = VRAM de la primera linia.
;; Copia 30 linies de 8 bytes amb el ring CRTC (2 KB/bloc).
;; Nomes registres principals: l'ISR de la musica no preserva els alternats.
;; ============================================================
    .module player_restore_c7
    .optsdcc -mz80

    .area _CODE

_start::
    ld      a, d
    and     #0x07
    cp      #0x06
    jr      c, pr_ultra
    jr      nz, pr_slow
    ld      a, e
    cp      #0xB8
    jr      nc, pr_slow
pr_ultra:
    push    ix
    .db     0xDD, 0x26, 30      ;; ld ixh, #30
pr_u_loop:
    push    de
    .rept 8
    ldi
    .endm
    pop     de
    ld      a, d
    add     a, #0x08
    ld      d, a
    and     #0x38
    jr      nz, pr_u_next
    ld      a, e
    add     a, #0x50
    ld      e, a
    ld      a, d
    adc     a, #0xC0
    and     #0xC7
    ld      d, a
pr_u_next:
    .db     0xDD, 0x25          ;; dec ixh
    jr      nz, pr_u_loop
    pop     ix
    ret

pr_slow:
    ld      b, #30
pr_line:
    push    bc
    push    de
    ld      b, #8
pr_wloop:
    ld      a, (hl)
    ld      (de), a
    inc     hl
    inc     de
    ld      a, e
    or      a
    jr      nz, pr_wnext
    ld      a, d
    and     #0x07
    jr      nz, pr_wnext
    ld      a, d
    sub     #0x08
    ld      d, a
pr_wnext:
    djnz    pr_wloop
    pop     de
    ld      a, d
    add     a, #0x08
    ld      d, a
    and     #0x38
    jr      nz, pr_s_next
    ld      a, e
    add     a, #0x50
    ld      e, a
    ld      a, d
    adc     a, #0xC0
    and     #0xC7
    ld      d, a
pr_s_next:
    pop     bc
    djnz    pr_line
    ret

    .area _DATA
