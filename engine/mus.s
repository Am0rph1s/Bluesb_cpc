    .module mus
    .globl _mus_init
    .globl _mus_play
    .globl _akg_init
    .globl _akg_play
    .globl _bank_set
    .globl _bank_restore
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
    ei
    ret

;; mus_play: avanca 1 tick de 50 Hz.
_mus_play::
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
    call    _akg_play
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
