;; ============================================================
;; enemy_table.s - Taula de salts fixa al Banc C6 (walkers L1)
;; ------------------------------------------------------------
;; S'enllaca PRIMER del modul C6 (@0x5200, darrere els frames):
;; 4 slots de 3 bytes (jp) a adreces FIXES per sempre
;; (0x5200+3k). El resident hi crida via call_banked(0xC6, slot).
;; Slots: 0 update, 1 restore, 2 draw, 3 init. Afegir al FINAL.
;; (init restaurat 10/26: sense crt0 al banc, els inicialitzadors
;; statics NO arriben a _DATA (el blob es packed); en2_init omple
;; l'spawn a runtime, 1 crida post-carrega.)
;; ============================================================
    .module enemy_table
    .optsdcc -mz80 sdcccall(1)

    .globl _en2_update
    .globl _en2_restore
    .globl _en2_draw
    .globl _en2_init
    .globl _en2_check_player_hit
    .globl _en2_check_crate_hit
    .globl _en2_room_exit
    .globl _en2_init_lut
    .globl _en2_flip_cell

    .area _CODE

_en_update::
    jp      _en2_update             ;; slot 0 -> 0x5C00
_en_restore::
    jp      _en2_restore            ;; slot 1 -> 0x5C03
_en_draw::
    jp      _en2_draw               ;; slot 2 -> 0x5C06
_en_init::
    jp      _en2_init               ;; slot 3 -> 0x5C09
_en_check_player_hit::
    jp      _en2_check_player_hit   ;; slot 4 -> 0x5C0C
_en_check_crate_hit::
    jp      _en2_check_crate_hit    ;; slot 5 -> 0x5C0F
_en_room_exit::
    jp      _en2_room_exit          ;; slot 6 -> 0x5C12


;; ============================================================
;; void en2_init_lut(void)
;; Inicialitza la LUT de H-Flip de 256 B al SCRATCH CENTRAL 0x8620
;; (lliure en runtime; a C6 no hi cab perquè les dades ocupen
;; 0x7820.. i el pool de fons 0x7A00).
;; ============================================================
_en2_init_lut::
    ld      hl, #0x8620
1$:
    ld      a, l
    and     #0xAA
    rrca
    ld      c, a
    ld      a, l
    and     #0x55
    rlca
    or      c
    ld      (hl), a
    inc     l
    jr      nz, 1$
    ret

;; ============================================================
;; void en2_flip_cell(const u8* src, u8* dst)
;; sdcccall(1): HL = src, DE = dst
;; Mirall horitzontal d'una cela 16 px Mode 0 x 32 files (512 B)
;; usant la LUT al scratch central 0x8620 (B = 0x86 constant).
;; ============================================================
_en2_flip_cell::
    ld      bc, #14                 ;; offset al parell 7 (últim parell de la fila 0)
    add     hl, bc
    ld      b, #0x86                ;; B = 0x86 (pàgina LUT a 0x8620)
    ld      a, #32                  ;; 32 files
1$:
    push    af                      ;; desa comptador de files (segur amb ISR)

    .rept 8
    ld      c, (hl)                 ;; C = màscara font
    inc     hl
    ld      a, (bc)                 ;; A = flip(màscara)
    ld      (de), a
    inc     de
    ld      c, (hl)                 ;; C = imatge font
    dec     hl
    dec     hl
    dec     hl                      ;; HL = màscara del parell anterior
    ld      a, (bc)                 ;; A = flip(imatge)
    ld      (de), a
    inc     de
    .endm

    ;; Avança HL de (src - 2) a (src + 16 + 14) = +32
    ld      a, #32
    add     a, l
    ld      l, a
    jr      nc, 2$
    inc     h
2$:
    pop     af
    dec     a
    jr      nz, 1$
    ret
