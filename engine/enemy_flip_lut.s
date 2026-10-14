;; ============================================================
;; enemy_flip_lut.s - LUT mirror Mode 0 pels walkers (banc C6)
;; ------------------------------------------------------------
;; S'enllaca PRIMER del modul (davant enemy_table.s): _DATA comenca
;; aqui (ENEMY_DATA=0x6500 alineat a 256: HI constant 0x65, llegit
;; via _g_flip_lut_hi pel blit amb flip de moving_blit.s).
;; L'omple en2_init a runtime (sense crt0 al banc, .ds no viatja).
;; ============================================================
    .module enemy_flip_lut

    .area _DATA

    .globl _s_flip_lut
_s_flip_lut::
    .ds 256
