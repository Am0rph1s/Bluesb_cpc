;; ============================================================
;; isr.s - Vector d'interrupcio minim (IM 1) per al CPC
;; Cal instal.lar-lo ABANS de qualsevol 'ei' (p.ex. el carregador FDC)
;; perque el vector 0x0038 apunti a codi valid en RAM (lower ROM off).
;; ============================================================
    .module isr
    .optsdcc -mz80 sdcccall(1)

    .globl _cpc_install_isr
    .globl _g_ticks
    .globl _mus_play           ;; stub central (mus.s): ISR-only (ja DI)
    .globl _g_mus_ready        ;; main.c: 1 = player iniciat

;; HOLD musica: el motor FDC l'activa (1) en entrar i el neteja (0) en
;; sortir (exit i fail). Adreca ABSOLUTA compartida (no _DATA: el motor
;; corre en 3 links diferents amb _DATA diferents). La ISR salta el tick
;; si HOLD (lectura en curs o slot C1 a mig sobreescriure).
MUS_HOLD = 0xBA10

    .area _DATA
_g_ticks::
    .db 0
_mus_div::
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
    ;; Musica: 1 tick player cada 6 ticks ISR (300/6 = 50 Hz exactes),
    ;; independent del frame rate del joc. Salta si HOLD (motor FDC) o si
    ;; el player no esta iniciat (ready=0: C1 buit = reboot segur).
    ;; _mus_play preserva TOT (push propi); nomes cal af/hl del stub.
    ld      a, (MUS_HOLD)
    or      a
    jr      nz, isr_done
    ld      a, (_g_mus_ready)
    or      a
    jr      z, isr_done
    ld      hl, #_mus_div
    inc     (hl)
    ld      a, (hl)
    cp      #6
    jr      c, isr_done
    ld      (hl), #0
    call    _mus_play
isr_done:
    pop     hl
    pop     af
    ei
    reti
