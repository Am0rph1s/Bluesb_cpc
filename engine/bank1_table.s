;; ============================================================
;; bank1_table.s - Taula de salts del Banc 1 (codi del nivell 1)
;; ------------------------------------------------------------
;; El codi del nivell (els ascensors) viu al Banc 1, dins el mateix paquet
;; que la musica, el HUD i les habitacions. El Bloc 0 resident ha de
;; quedar nomes amb el motor generic.
;;
;; Els codi bancat no pot commutar de banc: el Banc 1 ja ha de estar
;; mapejat quan cridem aquests slots.
;; ============================================================
    .module bank1_table
    .optsdcc -mz80 sdcccall(1)

    .globl _lc_elev_draw
    .globl _lc_elev_restore

    .area _CODE

_lc_elev_draw::
    jp      _lc_elev_draw_c        ;; slot 0 -> 0x6934
_lc_elev_restore::
    jp      _lc_elev_restore_c     ;; slot 1 -> 0x6937
