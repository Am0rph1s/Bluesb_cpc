;; ============================================================
;; isr.s - Vector d'interrupcio minim (IM 1) per al CPC
;; Cal instal.lar-lo ABANS de qualsevol 'ei' (p.ex. el carregador FDC)
;; perque el vector 0x0038 apunti a codi valid en RAM (lower ROM off).
;; ============================================================
    .module isr
    .optsdcc -mz80 sdcccall(1)

    .globl _cpc_install_isr
    .globl _g_ticks

    .area _DATA
_g_ticks::
    .db 0

    .area _CODE

_cpc_install_isr::
    di
    ld      a, #0xC3            ;; JP
    ld      (0x0038), a
    ld      hl, #isr_stub
    ld      (0x0039), hl
    ei
    ret

isr_stub:
    push    af
    push    hl
    ld      hl, #_g_ticks
    inc     (hl)
    pop     hl
    pop     af
    ei
    reti
