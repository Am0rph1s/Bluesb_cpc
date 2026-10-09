;; ============================================================
;; bank5_table.s - Taula de salts fixa al Banc 5 (CP-2.2)
;; ------------------------------------------------------------
;; Aquest mòdul s'enllaça PRIMER del Banc 5 (@0x6E00): 7 slots de
;; 3 bytes (jp) a adreces FIXES per sempre (0x6E00+3k). El resident
;; hi crida via call_banked (slot, mai per nom). Afegir al FINAL.
;; Slots: 0 update, 1 restore, 2 draw, 3 push, 4 find, 5 init, 6 conv.
;; ============================================================
    .module bank5_table
    .optsdcc -mz80 sdcccall(1)

    .globl _moving_bank_update
    ;; CP-2.2b: restore/draw són residents (moving.c); els seus slots queden
    ;; com a RETs per conservar les adreces de la resta (cap crida els usa).
    .globl _moving_bank_push
    .globl _moving_bank_find
    .globl _moving_bank_init
    .globl _moving_bank_conveyor

    .area _CODE

_bc_update::
    jp      _moving_bank_update     ;; slot 0 -> 0x6E00
_bc_restore::
    ret                             ;; slot 1 (sense ús) -> 0x6E03
    nop
    nop
_bc_draw::
    ret                             ;; slot 2 (sense ús) -> 0x6E06
    nop
    nop
_bc_push::
    jp      _moving_bank_push       ;; slot 3 -> 0x6E09
_bc_find::
    jp      _moving_bank_find       ;; slot 4 -> 0x6E0C
_bc_init::
    jp      _moving_bank_init       ;; slot 5 -> 0x6E0F
_bc_conveyor::
    jp      _moving_bank_conveyor   ;; slot 6 -> 0x6E12
