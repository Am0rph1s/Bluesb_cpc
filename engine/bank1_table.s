;; ============================================================
;; bank1_table.s - Taula de salts del Banc 1 (codi del nivell 1)
;; ------------------------------------------------------------
;; El codi del nivell (ascensors) i el HUD/GAME OVER viuen al Banc 1, dins el
;; mateix paquet que la musica, el HUD i les habitacions. El Bloc 0 resident
;; ha de quedar nomes amb el motor generic.
;;
;; Els codi bancat no pot commutar de banc: el Banc 1 ja ha de estar mapejat
;; quan cridem aquests slots. Els que escriuen a VRAM es criden amb 0xC0.
;; Slots de 3 bytes (jp): +0 draw, +3 restore, +6 hud_init, +9 hud_render,
;; +12 gameover.
;; ============================================================
    .module bank1_table
    .optsdcc -mz80 sdcccall(1)

    .globl _lc_elev_draw
    .globl _lc_elev_restore
    .globl _lc_hud_init
    .globl _lc_hud_render
    .globl _lc_gameover

    .area _CODE

_lc_elev_draw::
    jp      _lc_elev_draw_c        ;; slot 0 -> base+0
_lc_elev_restore::
    jp      _lc_elev_restore_c     ;; slot 1 -> base+3
_lc_hud_init::
    jp      _hud_init_b            ;; slot 2 -> base+6
_lc_hud_render::
    jp      _hud_render_b          ;; slot 3 -> base+9
_lc_gameover::
    jp      _gameover_banner_b     ;; slot 4 -> base+12
