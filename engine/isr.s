;; ============================================================
;; isr.s - Vector d'interrupcio minim (IM 1) per al CPC
;; Cal instal.lar-lo ABANS de qualsevol 'ei' (p.ex. el carregador FDC)
;; perque el vector 0x0038 apunti a codi valid en RAM (lower ROM off).
;; ============================================================
    .module isr
    .optsdcc -mz80 sdcccall(1)

    .globl _cpc_install_isr
    .globl _g_ticks
    .globl _g_irq_phase
    .globl _g_mus_hold           ;; _DATA: 1 = motor FDC en lectura (pausa tick)
    .globl _mus_play           ;; stub central (mus.s): ISR-only (ja DI)
    .globl _g_mus_ready        ;; main.c: 1 = player iniciat
    .globl _g_split_en         ;; 1 = split CRTC actiu (playfield C000 + HUD 8760)
    .globl _g_play_ma          ;; MA del playfield (0x3000 + offset)

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
_g_split_en::
    .db 0
_g_play_ma::
    .dw 0x3000

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
    inc     (hl)
    ;; Sincronitza _g_irq_phase amb VSYNC (PPI 0xF5 bit 0 == 1 -> fase 0; altres -> +1)
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
    ;; Split CRTC hardware (playfield 0xC000 + HUD fix RAM 2 0x8760, MA=0x23B0):
    ;;   R7=13 al bloc inferior -> VSYNC a linia 264 -> INT0=266, INT1=6,
    ;;   INT2=58, INT3=110, INT4=162, INT5=214. Zero esperes dins la ISR!
    ld      a, (_g_split_en)
    or      a
    jr      z, isr_split_done
    ld      a, (_g_irq_phase)
    or      a
    jr      z, isr_sp_ph0
    cp      #1
    jr      z, isr_sp_ph1
    cp      #3
    jr      z, isr_sp_ph3
    cp      #4
    jr      nz, isr_split_done
    ;; INT4 (linia ~162, VCC=0 del bloc inferior): R4=18, R6=2, R7=13
    ld      hl, #sp_bot_tbl
    jr      isr_sp_tbl
isr_sp_ph0:
    ;; INT0 (linia ~266): prepara R12/R13 = _g_play_ma per a linia 312
    ld      hl, (_g_play_ma)
    jr      isr_sp_ma
isr_sp_ph1:
    ;; INT1 (linia ~6, VCC=0 del bloc superior): R4=19, R6=20, R7=255
    ld      hl, #sp_top_tbl
isr_sp_tbl:
    push    de
    ld      e, #3
1$:
    ld      b, #0xBC
    ld      a, (hl)
    inc     hl
    out     (c), a
    inc     b
    ld      a, (hl)
    inc     hl
    out     (c), a
    dec     e
    jr      nz, 1$
    pop     de
    jr      isr_split_done
sp_top_tbl:
    .db 4, 19, 6, 20, 7, 255
sp_bot_tbl:
    .db 4, 18, 6, 2, 7, 13
isr_sp_ph3:
    ;; INT3 (linia ~110): prepara R12/R13 = 0x23B0 per a linia 160 (HUD)
    ld      hl, #0x23B0
isr_sp_ma:
    ld      bc, #0xBC0D
    out     (c), c
    ld      b, #0xBD
    out     (c), l
    ld      bc, #0xBC0C
    out     (c), c
    ld      b, #0xBD
    out     (c), h
isr_split_done:
    ;; Musica: 1 tick player cada VSYNC frame a INT2 (_g_irq_phase == 2, 50 Hz exactes),
    ;; fora de render_frame() (que comenca a ph=3). Salta si HOLD o !ready.
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
