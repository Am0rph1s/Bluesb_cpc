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
    jp      _en_dispatch6           ;; slot 6 -> 0x5A12 (room_exit o HUD copy)
_en_sprkey::
    jp      _spr_key_ops            ;; slot 7 -> 0x5A15 (M1: dirty-flag)

;; ============================================================
;; M1-HUD: dispatcher del slot 6. El HUD (banc C1) crida aquest slot amb
;; _bc_b = 0xA5 per copiar el HUD des de la pagina oposada; enemy_room_exit
;; hi arriba amb _bc_b = part alta de la coordenada (0 o 0xFF), mai 0xA5.
;; ============================================================
_en_dispatch6:
    ld      a, (_bc_b)
    cp      #0xA5
    jp      z, _hud_copy
    jp      _en2_room_exit

;; ============================================================
;; _hud_copy: copia el HUD (2 files x 8 blocs de 2 KB) des de la pagina
;; oposada. IX = base de la pagina font (0x80/0xC0) | offset en paraules
;; (0..0x3FF). El desti es la pagina actual amb g_vram_start. S'executa
;; amb C6 mapejat (call_banked); retorna directament a banked_ret$.
;; ============================================================
_hud_copy:
    push    ix
    pop     hl                  ;; H = base font + off>>8, L = off&0xFF
    ld      a, h
    and     #0xFC
    ld      b, a                ;; B = base de la pagina font
    ld      a, h
    and     #0x03
    ld      h, a                ;; HL = offset (0..0x3FF)
    ld      de, #800
    add     hl, de
    ld      a, h
    and     #0x03
    ld      h, a
    add     hl, hl
    ld      a, b
    add     a, h
    ld      h, a                ;; HL = src20
    push    hl                  ;; (SP) = src20
    ;; desti: base de la pagina oposada + g_vram_start
    ld      a, b
    cp      #0x80
    ld      a, #0xC0
    jr      z, hc_dstbase$
    ld      a, #0x80
hc_dstbase$:
    ld      b, a
    ld      hl, (_g_vram_start)
    ld      de, #800
    add     hl, de
    ld      a, h
    and     #0x03
    ld      h, a
    add     hl, hl
    ld      a, b
    add     a, h
    ld      h, a                ;; HL = dst20
    ex      de, hl              ;; DE = dst20
    pop     hl                  ;; HL = src20
    push    de
    push    hl
    call    hc_copy8$           ;; fila 20
    pop     hl
    pop     de
    ld      bc, #80
    add     hl, bc
    res     3, h
    ex      de, hl
    add     hl, bc
    res     3, h
    ex      de, hl
    call    hc_copy8$           ;; fila 21
    ret

hc_copy8$:
    ld      a, h
    and     #0x07
    cp      #0x07
    jr      nz, hc_chk_de$
    ld      a, l
    cp      #0xB1
    jr      nc, hc_wrap$
hc_chk_de$:
    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, hc_fast$
    ld      a, e
    cp      #0xB1
    jr      nc, hc_wrap$
hc_fast$:
    ld      b, #8
hc_c8_loop$:
    push    bc
    ld      bc, #80
    ldir
    ld      bc, #0x7B0          ;; seguent bloc (0x800 - 80)
    add     hl, bc
    ex      de, hl
    add     hl, bc
    ex      de, hl
    pop     bc
    djnz    hc_c8_loop$
    ret

hc_wrap$:
    ld      b, #8
hc_w_row$:
    push    bc
    ld      (s_hud_row_src), hl
    ld      (s_hud_row_dst), de
    ld      de, #s_hud_copy_buf

    ;; Font -> scratch lineal. Si creua el wrap, fan falta 2 LDIR.
    ld      a, h
    and     #0x07
    cp      #0x07
    jr      nz, hc_src_fast$
    ld      a, l
    cp      #0xB1
    jr      c, hc_src_fast$
    ld      a, l
    neg                     ;; primera part = 256 - L
    ld      c, a
    ld      b, #0
    push    bc
    ldir
    ld      a, h
    sub     #8
    ld      h, a
    pop     bc
    ld      a, #80
    sub     c
    ld      c, a
    ld      b, #0
    ldir
    jr      hc_src_done$
hc_src_fast$:
    ld      bc, #80
    ldir
hc_src_done$:
    ld      hl, (s_hud_row_dst)
    ex      de, hl
    ld      hl, #s_hud_copy_buf

    ;; Scratch -> desti. El desti també pot creuar el wrap.
    ld      a, d
    and     #0x07
    cp      #0x07
    jr      nz, hc_dst_fast$
    ld      a, e
    cp      #0xB1
    jr      c, hc_dst_fast$
    ld      a, e
    neg
    ld      c, a
    ld      b, #0
    push    bc
    ldir
    ld      a, d
    sub     #8
    ld      d, a
    pop     bc
    ld      a, #80
    sub     c
    ld      c, a
    ld      b, #0
    ldir
    jr      hc_dst_done$
hc_dst_fast$:
    ld      bc, #80
    ldir
hc_dst_done$:
    ld      hl, (s_hud_row_dst)
    ex      de, hl
    ld      hl, (s_hud_row_src)
    ld      a, h
    add     a, #8
    ld      h, a
    ld      a, d
    add     a, #8
    ld      d, a
    pop     bc
    djnz    hc_w_row$
    ret


;; ============================================================
;; M1: la LUT de H-Flip ELIMINADA. El gir Mode 0 es un swap de pixels
;; interleaved: flip(b) = ((b & 0x55) << 1) | ((b & 0xAA) >> 1) —
;; EXACTAMENT la formula que en2_init_lut precomputava a la LUT. La
;; formula s'inline dins el bucle per estalviar CALL/RET per byte sense
;; reservar una LUT de 256 B; el codi C6 conserva el marge al pool.
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
    ld      b, a
    and     #0x55
    add     a, a
    ld      c, a
    ld      a, b
    and     #0xAA
    rrca
    or      c
    ld      (de), a
    inc     de
    inc     hl
    ld      a, (hl)                 ;; imatge font
    ld      b, a
    and     #0x55
    add     a, a
    ld      c, a
    ld      a, b
    and     #0xAA
    rrca
    or      c
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
    .globl _bc_b
    .globl _g_vram_start
    .globl _s_mn_move, _s_mn_jump, _s_mn_page_dx, _s_mn_page_dy, _s_back_page
    .globl _s_carry_kind, _s_carry_drawn
    .globl _s_invuln_timer, _s_dazed_timer, _s_dying_timer, _s_dance_timer
    .globl _g_en_overlap
    .globl _s_proj, _g_en_jake_x, _g_en_jake_y
    .globl _s_mn_dsx, _s_mn_dsy, _g_face
    .globl _s_spr_last_k0, _s_spr_last_k1, _s_spr_clean
    .globl _s_enemies, _g_en_view_x
    .globl _s_en_visible, _en2_build_visible

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
    ;; M1 v5: guard de CARRY. Amb una caixa (o globus/paraigues) activa, o
    ;; encara dibuixada a alguna pagina (carry_abort posa s_carry_kind=0 abans
    ;; que una o totes dues pagines facin el restore LIFO), cal restaurar
    ;; Jake abans de carry_restore o el _s_player_bg sobreescriu la linia inferior.
    ld      hl, (_s_carry_drawn)
    ld      a, (_s_carry_kind)
    or      l
    or      h
    ret     nz
    ;; M1 v10: amb invulnerabilitat (parpalleig), mareig (estrelletes), mort o
    ;; ball actius, cal flux complet perquè no quedi un segon Jake al fons.
    ld      hl, (_s_dazed_timer)    ;; L = s_dazed_timer, H = s_dying_timer
    ld      a, (_s_invuln_timer)
    or      l
    or      h
    ld      hl, #_s_dance_timer
    or      (hl)
    ret     nz
    ;; M1 v6: guard d'enemics sobre Jake. en2_update marca _g_en_overlap si un
    ;; enemic trepitja la caixa del Jake; llavors cal el flux original
    ;; (restore+blit) o el save/restore creuat deixa l'error persistent al
    ;; lloc de la colisio (vist en test real 21/11). Cost: 1 byte, no un
    ;; recorregut de 26 enemics al frame quiet.
    ld      a, (_g_en_overlap)
    or      a
    ret     nz
    ;; M1 v10b: mentre hi hagi un projectil actiu (kind != 0) o encara
    ;; dibuixat a qualsevol de les dues pagines (drawn_row_count[0..1] != 0
    ;; fins que en2_restore el netegi), cal flux complet per evitar que
    ;; _s_player_bg capturi una bala al passar sobre en Jake ajupit.
    ld      a, (_s_proj + 9)        ;; kind (0 = inactiu)
    ld      hl, (_s_proj + 16)      ;; drawn_row_count[0..1]
    or      l
    or      h
    ret     nz
spk_proj_ok$:
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

;; ============================================================
;; Broadphase ASM per a en2_draw. Mantem exactament el filtre C:
;;   dead != 2, slot[page] < 0 i (u16)(x - view_x + 15) < 175.
;; Sortida: A = nombre de candidats, indices a _s_en_visible.
;; El scratch va dins l'area CODE perquè C6 te el DATA praticament ple.
;; ============================================================
_s_en_visible:
    .ds     32

;; Scratch lineal per a la copia HUD amb wrap: una fila de 80 B i els
;; inici de font/desti per avançar exactament 0x800 a la seguent scanline.
s_hud_copy_buf:
    .ds     80
s_hud_row_src:
    .ds     2
s_hud_row_dst:
    .ds     2

;; Parametres del hit-check a l'scratch de CODE (DATA de C6 esta ple).
_s_hit_xmin::
    .ds     2
_s_hit_ymin::
    .ds     2
_s_hit_ymax::
    .ds     2
_s_hit_xw::
    .ds     1
_s_hit_use_he::
    .ds     1

_en2_build_visible::
    push    ix
    push    iy
    ld      ix, #_s_enemies
    ld      iy, #_s_en_visible
    ld      b, #26
    ld      c, #0
    ld      d, #0
ev_loop$:
    ld      a, 10(ix)
    cp      #2
    jr      z, ev_next$
    ld      a, (_bc_a)
    bit     0, a
    ld      a, 11(ix)
    jr      z, ev_slot_ready$
    ld      a, 12(ix)
ev_slot_ready$:
    bit     7, a
    jr      z, ev_next$
    ld      l, 0(ix)
    ld      h, 1(ix)
    push    de
    ld      a, (_g_en_view_x)
    ld      e, a
    ld      a, (_g_en_view_x + 1)
    ld      d, a
    or      a
    sbc     hl, de
    ld      de, #15
    add     hl, de
    ld      de, #175
    or      a
    sbc     hl, de
    pop     de
    jr      nc, ev_next$
    ld      a, c
    ld      (iy), a
    inc     iy
    inc     d
ev_next$:
    .db     0xDD, 0x7D          ;; ld a, ixl
    add     a, #13
    .db     0xDD, 0x6F          ;; ld ixl, a
    jr      nc, ev_advance$
    .db     0xDD, 0x24          ;; inc ixh
ev_advance$:
    inc     c
    djnz    ev_loop$
    ld      a, d
    pop     iy
    pop     ix
    ret

;; ============================================================
;; Hit-box ASM per a en2_hit_box. Entrades via s_hit_*:
;;   xmin, xw, ymin, ymax, use_he. No toca bc_*.
;; Sortida: A=index (0..25) o FF. Mante exactement el filtre C.
;; ============================================================
    .globl _en2_hit_box_fast
    .globl _s_hit_xmin, _s_hit_xw, _s_hit_ymin, _s_hit_ymax, _s_hit_use_he
    .globl _s_enemies
_en2_hit_box_fast::
    push    ix
    push    iy
    ld      ix, #_s_enemies
    ld      iy, #0x4B14           ;; s_spawn
    ld      c, #0                 ;; index

hb_loop$:
    ld      a, 10(ix)
    or      a
    jr      nz, hb_next$

    ;; (u16)(e->x - xmin) < xw
    ld      l, 0(ix)
    ld      h, 1(ix)
    ld      a, (_s_hit_xmin)
    ld      e, a
    ld      a, l
    sub     e
    ld      l, a
    ld      a, (_s_hit_xmin + 1)
    ld      e, a
    ld      a, h
    sbc     e
    ld      h, a
    jr      nz, hb_next$
    ld      a, (_s_hit_xw)
    ld      b, a
    ld      a, l
    cp      b                   ;; dx - xw: Carry=1 sii dx < xw (HIT)
    jr      nc, hb_next$        ;; dx >= xw -> fora (igual que el C)

    ;; kind 8 = peix decoratiu, mai no col·lisiona.
    ld      a, 4(iy)
    cp      #8
    jr      z, hb_next$

    ;; E = 32 - h. Valors del C original (use_he=0 -> h=16).
    ld      e, #16
    ld      a, (_s_hit_use_he)
    or      a
    jr      z, hb_have_top$
    ld      a, 4(iy)
    cp      #24
    jr      z, hb_top22$
    cp      #25
    jr      z, hb_top14$
    cp      #19
    jr      z, hb_have_top$
    cp      #4
    jr      z, hb_top4$
    ld      e, #2
    jr      hb_have_top$
hb_top22$:
    ld      e, #22
    jr      hb_have_top$
hb_top14$:
    ld      e, #14
    jr      hb_have_top$
hb_top4$:
    ld      e, #4
hb_have_top$:
    ;; ey = e->y8 >> 3 (arithmetic)
    ld      l, 2(ix)
    ld      h, 3(ix)
    sra     h
    rr      l
    sra     h
    rr      l
    sra     h
    rr      l
    push    hl                  ;; desa ey
    ld      d, #0
    add     hl, de              ;; ey + (32-h)
    ld      de, (_s_hit_ymax)
    call    hb_signed_lt
    jr      nc, hb_y_fail$
    pop     hl                  ;; ey
    ld      de, #32
    add     hl, de              ;; ey + 32
    ld      de, (_s_hit_ymin)
    call    hb_signed_lt
    jr      c, hb_next$          ;; ey+32 < ymin -> no hit
    ld      a, c
    jr      hb_return$

hb_y_fail$:
    pop     hl
hb_next$:
    .db     0xDD, 0x7D          ;; ld a, ixl
    add     a, #13
    .db     0xDD, 0x6F          ;; ld ixl, a
    jr      nc, hb_spawn_advance$
    .db     0xDD, 0x24          ;; inc ixh
hb_spawn_advance$:
    .db     0xFD, 0x7D          ;; ld a, iyl
    add     a, #9
    .db     0xFD, 0x6F          ;; ld iyl, a
    jr      nc, hb_index_advance$
    .db     0xFD, 0x24          ;; inc iyh
hb_index_advance$:
    inc     c
    ld      a, c
    cp      #26
    jp      c, hb_loop$
    ld      a, #0xFF
hb_return$:
    pop     iy
    pop     ix
    ret

;; HL < DE, signed 16. Sortida Carry=1 si HL<DE. Preserva C/IX/IY.
hb_signed_lt:
    ld      a, h
    xor     d
    and     #0x80
    jr      nz, hb_sign_diff$
    sbc     hl, de              ;; AND ha netejat Carry
    ret
hb_sign_diff$:
    ld      a, h
    rla                         ;; Carry = signe de HL
    ret
