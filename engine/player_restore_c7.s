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
    ld      b, #30
pr_line:
    push    bc
    push    de

    ;; Camí ràpid si no som al final del bloc de 2 KB
    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, pr_fast
    ld      a, e
    cp      #0xF8
    jr      nc, pr_wrap
pr_fast:
    ld      bc, #8
    ldir
    jr      pr_done

pr_wrap:
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

pr_done:
    pop     de
    call    pr_step
    pop     bc
    djnz    pr_line
    ret

;; Avança DE una scanline avall dins el ring (copia de sprite_step_de).
pr_step:
    ld      a, d
    and     #0x38
    cp      #0x38
    jr      z, pr_step_wrap
    ld      a, d
    add     a, #0x08
    ld      d, a
    ret
pr_step_wrap:
    ld      a, e
    add     a, #0x50
    ld      e, a
    ld      a, d
    adc     a, #0xC8
    and     #0xC7
    ld      d, a
    ret

    .area _DATA
