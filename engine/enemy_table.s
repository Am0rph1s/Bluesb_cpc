;; ============================================================
;; enemy_table.s - Taula de salts fixa al Banc C6 (walkers L1)
;; ------------------------------------------------------------
;; S'enllaca PRIMER del modul C6 (@0x5A00, darrere les dades):
;; 8 slots de 3 bytes (jp) a adreces FIXES per sempre
;; (0x5A00+3k). El resident hi crida via call_banked(0xC6, slot).
;; Slots: 0 update, 1 restore, 2 draw, 3 init, 4/5 hit, 6 room_exit,
;; 7 spr_key (M1). Afegir al FINAL.
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
    .globl _en2_flip_cell

    .area _CODE

_en_update::
    jp      _en2_update             ;; slot 0 -> 0x5A00
_en_restore::
    jp      _en2_restore            ;; slot 1 -> 0x5A03
_en_draw::
    jp      _en2_draw               ;; slot 2 -> 0x5A06
_en_init::
    jp      _en2_init               ;; slot 3 -> 0x5A09
_en_check_player_hit::
    jp      _en2_check_player_hit   ;; slot 4 -> 0x5A0C
_en_check_crate_hit::
    jp      _en2_check_crate_hit    ;; slot 5 -> 0x5A0F
_en_room_exit::
    jp      _en2_room_exit          ;; slot 6 -> 0x5A12
_en_sprkey::
    jp      _spr_key_ops            ;; slot 7 -> 0x5A15 (M1: dirty-flag)


;; ============================================================
;; M1: la LUT de H-Flip ELIMINADA. El gir Mode 0 es un swap de pixels
;; interleaved: flip(b) = ((b & 0x55) << 1) | ((b & 0xAA) >> 1) —
;; EXACTAMENT la formula que en2_init_lut precomputava a la LUT. La
;; dansa directa (sk_flip$, ~48 T/byte) viu al cami fred de la cache
;; (nomes en fallada) i allibera els 256 B de la zona 0x7900..0x79FF:
;; el sostre del codi C6 passa de 0x7900 al POOL DE FONS (0x7A00).
;; ============================================================
_en2_flip_cell::
    ld      bc, #14                 ;; offset al parell 7 (últim parell de la fila 0)
    add     hl, bc
    ld      a, #32                  ;; 32 files
1$:
    push    af                      ;; desa comptador de files (segur amb ISR)
    ld      a, #8                   ;; M1: 8 parells per fila en LOOP (abans
    push    af                      ;; .rept 8: -75 B de pak; el flip omple la
2$:                                 ;; cache (cami fred), no es cami calent
    ld      a, (hl)                 ;; màscara font
    call    sk_flip$
    ld      (de), a
    inc     de
    inc     hl
    ld      a, (hl)                 ;; imatge font
    call    sk_flip$
    ld      (de), a
    inc     de
    dec     hl
    dec     hl
    dec     hl                      ;; HL = màscara del parell anterior
    pop     af                      ;; comptador de parells via pila (A queda
    dec     a                       ;; lliure dins del parell per la dansa)
    push    af
    jr      nz, 2$
    pop     af                      ;; neteja el comptador de parells (=0)

    ;; Avança HL de (src - 2) a (src + 16 + 14) = +32
    ld      a, #32
    add     a, l
    ld      l, a
    jr      nc, 3$
    inc     h
3$:
    pop     af
    dec     a
    jr      nz, 1$
    ret

;; sk_flip$: A = ((A & 0x55) << 1) | ((A & 0xAA) >> 1)
;; El swap de pixels interleaved del Mode 0 (la formula antiga de la
;; LUT, calculada al moment). Temporals B/C (lliures: eren la pagina
;; i l'index de la LUT).
sk_flip$:
    ld      b, a
    and     #0x55
    add     a, a
    ld      c, a
    ld      a, b
    and     #0xAA
    rrca
    or      c
    ret

;; ============================================================
;; M1: _spr_key_ops (slot 7 -> 0x5A15). Dirty-flag del
;; sprite_restore_player (disseny i analisi al CHANGELOG 20/11: en C
;; costava +223 B al bucle de main() per re-flow de l'allocator).
;;
;; bc_a = 0 (check, ABANS dels restores): compara POSICIO de pantalla
;;   i SENTIT del frame amb la clau desada d'AQUESTA pagina ->
;;   _s_spr_clean = 1 si res no ha canviat. L'ANIM NO es compara aqui
;;   (encara no s'ha seleccionat: seria stale): el compare d'anim el
;;   fa el C al draw site (s_mn_cur fresc) via l'heal tarda. Aixo
;;   arregla el bug de test real 20/11: caminant amb la camera fent
;;   tracking 1:1 la dsx es CONSTANT -> la clau de posicio coincidia
;;   amb el darrer frame de caminar -> les pagines congelaven poses
;;   diferents del cicle i les intercalaven (parpalleig).
;;   Guards: mn_move/mn_jump != 0. La resta d'estats (dying/dazed/
;;   dance/crouch/carry/climb) tenen anims DIFFERENTS -> el compare
;;   d'anim del draw site els captura i fa l'heal tarda.
;; bc_a = 1 (save, just despres del draw del jugador): desa la clau.
;;
;; Clau: k0 = dsx.lo | dsy.lo<<8; k1 = face (u16, hi = 0)
;; ============================================================
    .globl _bc_a
    .globl _s_mn_move, _s_mn_jump, _s_mn_page_dx, _s_mn_page_dy, _s_back_page
    .globl _s_carry_kind
    .globl _s_mn_dsx, _s_mn_dsy, _g_face
    .globl _s_spr_last_k0, _s_spr_last_k1, _s_spr_clean

_spr_key_ops::
    ld      a, (_bc_a)
    or      a
    jp      nz, sk_save$

    ;; ---- mode 0: check ----
    ld      hl, #_s_spr_clean
    ld      (hl), #0x00
    ld      a, (_s_mn_move)
    or      a
    ret     nz
    ld      a, (_s_mn_jump)
    or      a
    ret     nz
    ;; M1 v4: guard de SCROLL. Amb scroll el frame te DUES bases (cam -
    ;; page_dx pels restores, cam pel draw) i l'heal tarda restauraria amb
    ;; la base del draw = adreça equivocada -> artefacte congelat a l'aturar
    ;; (vist en test real 20/11). Amb scroll: flux original (dirty).
    ld      a, (_s_mn_page_dx)
    or      a
    ret     nz
    ld      a, (_s_mn_page_dy)
    or      a
    ret     nz
    ;; M1 v5: guard de CARRY. Amb una caixa (o globus/paraigues) activa, el
    ;; carry_draw desa el fons DESPRES del punt on Jake hauria d'haver estat
    ;; restaurat (1237): amb l'skip, el seu save captura el propi Jake i el
    ;; heal captura la caixa -> remanents (vist en test real: 9 B al lloc de
    ;; l'throw). Amb carry actiu: flux original (dirty).
    ld      a, (_s_carry_kind)
    or      a
    ret     nz
    ;; pagina -> DE = page*2
    ld      a, (_s_back_page)
    add     a, a
    ld      e, a
    ld      d, #0x00
    ;; k0 (posicio de pantalla)
    ld      hl, #_s_spr_last_k0
    add     hl, de
    ld      a, (_s_mn_dsx + 0)
    cp      (hl)
    ret     nz
    inc     hl
    ld      a, (_s_mn_dsy + 0)
    cp      (hl)
    ret     nz
    ;; k1 (sentit del frame)
    ld      a, (_g_face)
    ld      hl, #_s_spr_last_k1
    add     hl, de
    cp      (hl)
    ret     nz
    ;; posicio i sentit iguals: el draw site decideix amb l'anim
    ld      hl, #_s_spr_clean
    inc     (hl)
    ret

    ;; ---- mode 1: save ----
sk_save$:
    ld      a, (_s_back_page)
    add     a, a
    ld      e, a
    ld      d, #0x00
    ld      hl, #_s_spr_last_k0
    add     hl, de
    ld      a, (_s_mn_dsx + 0)
    ld      (hl), a
    inc     hl
    ld      a, (_s_mn_dsy + 0)
    ld      (hl), a
    ld      a, (_g_face)
    ld      hl, #_s_spr_last_k1
    add     hl, de
    ld      (hl), a
    inc     hl
    ld      (hl), #0x00
    ret
