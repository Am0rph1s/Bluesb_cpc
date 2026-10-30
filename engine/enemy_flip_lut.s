;; ============================================================
;; enemy_flip_lut.s - LUT mirror Mode 0 pels walkers (banc C6)
;; ------------------------------------------------------------
;; Historicament definia _s_flip_lut (LUT de flip a _DATA del banc C6),
;; pero el flip es fa amb la LUT de C6:0x4E00 (en2_flip_cell), aixi que
;; aquest modul ja no aporta cap dada.
;; ============================================================
;; (10/30/26) _s_flip_lut (256 B de _DATA) ELIMINAT: no hi havia cap
;; referencia des de l'ATLAS ni des del blit (el flip es fa amb la LUT de
;; 0x4E00 via en2_flip_cell). Allibera 256 B de _DATA del banc C6, que
;; permeten baixar ENEMY_BASE i donar 256 B mes de codi a C6.
    .module enemy_flip_lut
