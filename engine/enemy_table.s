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

    .area _CODE

_en_update::
    jp      _en2_update             ;; slot 0 -> 0x5200
_en_restore::
    jp      _en2_restore            ;; slot 1 -> 0x5203
_en_draw::
    jp      _en2_draw               ;; slot 2 -> 0x5206
_en_init::
    jp      _en2_init               ;; slot 3 -> 0x5209
