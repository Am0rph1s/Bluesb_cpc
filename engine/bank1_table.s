;; ============================================================
;; bank1_table.s - Taula de salts del Banc 1 (codi del nivell)
;; ------------------------------------------------------------
;; El codi del nivell viu al Banc 1, dins el mateix paquet
;; que la musica, el HUD i les habitacions. El Bloc 0 resident ha de
;; quedar nomes amb el motor generic.
;;
;; El codi bancat no pot commutar de banc: el Banc 1 ja ha de estar
;; mapejat quan cridem aquests slots.
;; ============================================================
    .module bank1_table
    .optsdcc -mz80 sdcccall(1)

    .globl _lc_elev_draw
    .globl _lc_elev_restore
    .globl _lc_conveyor_draw

    .globl _lc_elev_draw_c
    .globl _lc_elev_restore_c
    .globl _lc_conveyor_draw_c

    .area _CODE

_lc_elev_draw::
    jp      _lc_elev_draw_c        ;; slot 0 -> base + 0
_lc_elev_restore::
    jp      _lc_elev_restore_c     ;; slot 1 -> base + 3
_lc_conveyor_draw::
    jp      _lc_conveyor_draw_c    ;; slot 2 -> base + 6
