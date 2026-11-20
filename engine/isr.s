;; ============================================================
;; isr.s - Vector d'interrupcio minim (IM 1) per al CPC
;; Cal instal.lar-lo ABANS de qualsevol 'ei' (p.ex. el carregador FDC)
;; perque el vector 0x0038 apunti a codi valid en RAM (lower ROM off).
;; ------------------------------------------------------------
;; F1 (portat de la linia master, 19/11): eliminat _mus_div (divisor
;; lliure que derivava del VSYNC) i sincronitzat el tick de musica a
;; _g_irq_phase == 2, lligada al VSYNC via el PPI (0xF5 bit 0).
;; ============================================================
    .module isr
    .optsdcc -mz80 sdcccall(1)

    .globl _cpc_install_isr
    .globl _g_ticks
    .globl _g_mus_hold           ;; _DATA: 1 = motor FDC en lectura (pausa tick)
    .globl _mus_play           ;; stub central (mus.s): ISR-only (ja DI)
    .globl _g_mus_ready        ;; main.c: 1 = player iniciat

;; HOLD: ABANS era un absolut 0xBA10 (VRAM pag.2!). El memset(0x8000) del
;; GAME el posava a 0xFF i el render el trepitjava = la ISR no sonava mai
;; mes al joc + AY congelat = drone persistent (vist 13/10/26). Ara viu a
;; _DATA (byte propi): el motor (3 links) hi escriu via EQU generat
;; (obj/fdc_hold.s, patro front_ext) i la ISR el llegeix com a simbol.

    .area _DATA
_g_ticks::
    .db 0
_g_irq_phase::
    .db 0
_g_mus_hold::
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
    push    bc
    ld      hl, #_g_ticks
    inc (hl)
    ;; M0.1/F1 (port de la linia master): sincronitza el tick de musica al
    ;; VSYNC en comptes d'un divisor lliure (_mus_div derivava respecte el
    ;; frame amb les finestres DI de la carrega FDC i sonava a qualsevol
    ;; punt del frame). _g_irq_phase es lligada al VSYNC via el PPI
    ;; (0xF5 bit 0 == 1 -> fase 0; altrament +1): 50 Hz EXACTES en un punt
    ;; deterministic del frame, independent del frame rate del joc.
    ;; Mesurat 19/11 al master: fase==2 a 16/16 mostres, deltas de 6 ticks.
    ld      bc, #0xF500
    in      a, (c)
    rrca
    ld      hl, #_g_irq_phase
    jr      nc, isr_phase_inc
    ld      (hl), #0
    jr      isr_phase_done
isr_phase_inc:
    inc     (hl)
isr_phase_done:
    ;; Musica: 1 tick player a _g_irq_phase == 2. Salta si HOLD (motor FDC)
    ;; o si el player no esta iniciat (ready=0: C1 buit = reboot segur).
    ;; _mus_play preserva TOT (push propi); nomes cal af/bc/hl del stub.
    ld      a, (_g_mus_hold)
    or      a
    jr      nz, isr_done
    ld      a, (_g_mus_ready)
    or      a
    jr      z, isr_done
    ld      a, (_g_irq_phase)
    cp      #2
    call    z, _mus_play
isr_done:
    pop     bc
    pop     hl
    pop     af
    ei
    reti
