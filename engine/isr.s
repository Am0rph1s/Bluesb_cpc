;; ============================================================
;; isr.s - Vector d'interrupcio minim (IM 1) per al CPC
;; Cal instal.lar-lo ABANS de qualsevol 'ei' (p.ex. el carregador FDC)
;; perque el vector 0x0038 apunti a codi valid en RAM (lower ROM off).
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
_mus_div::
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
    ld      hl, #_g_ticks
    inc     (hl)
    ;; Musica: 1 tick player cada 6 ticks ISR (300/6 = 50 Hz exactes),
    ;; independent del frame rate del joc. Salta si HOLD (motor FDC) o si
    ;; el player no esta iniciat (ready=0: C1 buit = reboot segur).
    ;; _mus_play preserva TOT (push propi); nomes cal af/hl del stub.
    ld      a, (_g_mus_hold)
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
