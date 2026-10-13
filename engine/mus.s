    .module mus
    .globl _mus_init
    .globl _mus_play
    .globl _mus_stop
    .globl _akg_init
    .globl _akg_play
    .globl _akg_stop
    .globl _bank_set
    .globl _bank_restore
    .globl _g_mus_ready
    .area _CODE

;; ============================================================
;; mus.s - Stubs centrals del player AKG (banc C1, AT3).
;; Pagina C1, crida Init/Play, restaura el banc del caller (central o
;; FRONT banked: nest-safe via bank_set/bank_restore). Salva TOTS els
;; registres (el player optimitzat els trepitja) + DI/EI (el player juga
;; amb SP; la ISR usa la pila: amb EI rebentaria).
;; Crida SEMPRE amb EI (game loop i FRONT ho son).
;; MUS_SONG_SLOT ha de coincidir amb build.py (assert al link).
;; ============================================================

;; mus_init: HL = slot, A = subsongo 0; crida Init.
_mus_init::
    di
    push    af
    push    bc
    push    de
    push    hl
    push    ix
    push    iy
    ld      a, #0xC1
    call    _bank_set             ;; A = prev
    push    af
    ld      hl, #0x5000           ;; MUS_SONG_SLOT (cf. mus.h/build.py)
    xor     a                     ;; subsongo 0
    call    _akg_init
    pop     af
    call    _bank_restore
    pop     iy
    pop     ix
    pop     hl
    pop     de
    pop     bc
    pop     af
    ld      a, #1
    ld      (_g_mus_ready), a     ;; player llest: la ISR ja pot sonar
    ei
    ret

;; mus_play: avanca 1 tick de 50 Hz. ISR-ONLY (nomes la ISR el crida, que
;; ja entra en DI i fa ei/reti; el di/ei aqui re-activaria interrupcions en
;; plena ISR = ISR niuada + player reentrant = crash). Preserva TOT.
_mus_play::
    push    af
    push    bc
    push    de
    push    hl
    push    ix
    push    iy
    ld      a, #0xC1
    call    _bank_set             ;; A = prev
    push    af
    call    _akg_play
    pop     af
    call    _bank_restore
    pop     iy
    pop     ix
    pop     hl
    pop     de
    pop     bc
    pop     af
    ret

;; mus_stop: silencia l'AY (volums 0 + mixer off) SENSE tocar la posicio:
;; la ISR repren on era (HOLD net). Crida'l ABANS de lectures FDC (el HOLD
;; congela el player pero l'AY mantindria l'ultima nota = drone). Segur en
;; player no-iniciat (Stop nomes escriu regs + SaveSP, no llegeix canco).
_mus_stop::
    di
    push    af
    push    bc
    push    de
    push    hl
    push    ix
    push    iy
    ld      a, #0xC1
    call    _bank_set             ;; A = prev
    push    af
    call    _akg_stop
    pop     af
    call    _bank_restore
    pop     iy
    pop     ix
    pop     hl
    pop     de
    pop     bc
    pop     af
    ei
    ret
