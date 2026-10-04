;; ============================================================
;; sprite.s - Rutines ultra-rapides en ASM Z80 per a sprites Mode 0
;; Amstrad CPC - SDCC 4.5 (__sdcccall 1)
;;
;; sprite_blit_player: Blit amb mascara + desat de fons simultani
;;                     Suporta reflexio horitzontal (H-flip) per Mode 0
;; sprite_restore_player: Restauracio rapida de fons amb LDIR
;; ============================================================

    .module sprite
    .optsdcc -mz80 sdcccall(1)

    .globl _sprite_blit_player
    .globl _sprite_restore_player
    .globl _g_spr_y
    .globl _g_spr_x
    .globl _g_spr_flip
    .globl _scr_addr_table

    ;; ============================================================
    ;; DADES DE TREBALL A _DATA
    ;; ============================================================
    .area _DATA

_g_spr_y::          .db 0
_g_spr_x::          .db 0
_g_spr_flip::       .db 0

_s_old_y:           .db 0
_s_old_x:           .db 0
s_cur_y:            .db 0
s_line_cnt:         .db 0
s_spr_ptr:          .dw 0
s_bg_read_ptr:      .dw 0

_s_player_bg:       .ds 360     ;; 12 bytes * 30 linies = 360 bytes


    ;; ============================================================
    ;; CODI A _CODE
    ;; ============================================================
    .area _CODE

;; ============================================================
;; void sprite_restore_player(void)
;;   Restaura el fons darrera del personatge usant LDIR
;; ============================================================
_sprite_restore_player::
    ld      a, (_s_old_y)
    ld      (s_cur_y), a
    ld      hl, #_s_player_bg
    ld      (s_bg_read_ptr), hl

    ld      b, #30              ;; 30 linies
rst_line_loop:
    push    bc

    ;; Adreca VRAM linia: DE = _scr_addr_table[s_cur_y] + _s_old_x
    ld      a, (s_cur_y)
    ld      l, a
    ld      h, #0
    add     hl, hl              ;; y * 2
    ld      de, #_scr_addr_table
    add     hl, de
    ld      e, (hl)
    inc     hl
    ld      d, (hl)             ;; DE = base scanline VRAM

    ld      a, (_s_old_x)
    add     a, e
    ld      e, a
    jr      nc, 1$
    inc     d
1$:                             ;; DE = adreca VRAM desti
    ld      hl, (s_bg_read_ptr) ;; HL = buffer fons font

    ld      bc, #12
    ldir                        ;; copiar 12 bytes! HL i DE avancen 12

    ld      (s_bg_read_ptr), hl

    ld      hl, #s_cur_y
    inc     (hl)

    pop     bc
    djnz    rst_line_loop
    ret


    .globl _cpc_wait_vsync_start

;; ============================================================
;; void cpc_wait_vsync_start(void)
;;   Espera el comencament de la sincronitzacio vertical (Linia 240).
;; ============================================================
_cpc_wait_vsync_start::
    ld      b, #0xF5
1$:
    in      a, (c)
    rra
    jr      c, 1$               ;; Si ja estavem en VSYNC, esperar que surti
2$:
    in      a, (c)
    rra
    jr      nc, 2$              ;; Esperar el FLANC DE PUJADA (inici de VSYNC a la linia 240)
    ret


;; ============================================================
;; void sprite_blit_player(const u8* spr)
;;   HL = spr (punter al frame [inv_mask, img_masked])
;;   Rutina ultra-rapida sense branques (~21.000 T-states)
;; ============================================================
_sprite_blit_player::
    ld      (s_spr_ptr), hl

    ld      a, (_g_spr_y)
    ld      (_s_old_y), a
    ld      (s_cur_y), a

    ld      a, (_g_spr_x)
    ld      (_s_old_x), a

    ld      bc, #_s_player_bg   ;; BC = punter desti de desat de fons

    ld      a, #30              ;; 30 linies
    ld      (s_line_cnt), a

blit_line:
    push    bc

    ld      a, (s_cur_y)
    ld      l, a
    ld      h, #0
    add     hl, hl
    ld      de, #_scr_addr_table
    add     hl, de
    ld      e, (hl)
    inc     hl
    ld      d, (hl)             ;; DE = adreca scanline VRAM

    ld      a, (_s_old_x)
    add     a, e
    ld      e, a
    jr      nc, 3$
    inc     d
3$:
    ld      hl, (s_spr_ptr)     ;; HL = sprite [inv_mask, img_masked]

    pop     bc                  ;; Recuperar BC = bg_write_ptr

    ;; 12 bytes desenrotllats (sense bucle, sense IY, sense branques!):
    .rept 12
    ld      a, (de)             ;; Llegir pantalla original
    ld      (bc), a             ;; Desar al buffer de fons
    inc     bc
    and     (hl)                ;; A = pantalla & inv_mask
    inc     hl
    or      (hl)                ;; A = (pantalla & inv_mask) | img_masked
    inc     hl
    ld      (de), a             ;; Escriure a VRAM!
    inc     de
    .endm

    ld      (s_spr_ptr), hl

    ld      hl, #s_cur_y
    inc     (hl)

    ld      hl, #s_line_cnt
    dec     (hl)
    jp      nz, blit_line
    ret


;; ============================================================
;; Taula de 200 adreces de l'inici de linia a VRAM (0xC000..0xFFFF)
;; ============================================================
_scr_addr_table::
    .dw 0xC000, 0xC800, 0xD000, 0xD800, 0xE000, 0xE800, 0xF000, 0xF800
    .dw 0xC050, 0xC850, 0xD050, 0xD850, 0xE050, 0xE850, 0xF050, 0xF850
    .dw 0xC0A0, 0xC8A0, 0xD0A0, 0xD8A0, 0xE0A0, 0xE8A0, 0xF0A0, 0xF8A0
    .dw 0xC0F0, 0xC8F0, 0xD0F0, 0xD8F0, 0xE0F0, 0xE8F0, 0xF0F0, 0xF8F0
    .dw 0xC140, 0xC940, 0xD140, 0xD940, 0xE140, 0xE940, 0xF140, 0xF940
    .dw 0xC190, 0xC990, 0xD190, 0xD990, 0xE190, 0xE990, 0xF190, 0xF990
    .dw 0xC1E0, 0xC9E0, 0xD1E0, 0xD9E0, 0xE1E0, 0xE9E0, 0xF1E0, 0xF9E0
    .dw 0xC230, 0xCA30, 0xD230, 0xDA30, 0xE230, 0xEA30, 0xF230, 0xFA30
    .dw 0xC280, 0xCA80, 0xD280, 0xDA80, 0xE280, 0xEA80, 0xF280, 0xFA80
    .dw 0xC2D0, 0xCAD0, 0xD2D0, 0xDAD0, 0xE2D0, 0xEAD0, 0xF2D0, 0xFAD0
    .dw 0xC320, 0xCB20, 0xD320, 0xDB20, 0xE320, 0xEB20, 0xF320, 0xFB20
    .dw 0xC370, 0xCB70, 0xD370, 0xDB70, 0xE370, 0xEB70, 0xF370, 0xFB70
    .dw 0xC3C0, 0xCBC0, 0xD3C0, 0xDBC0, 0xE3C0, 0xEBC0, 0xF3C0, 0xFBC0
    .dw 0xC410, 0xCC10, 0xD410, 0xDC10, 0xE410, 0xEC10, 0xF410, 0xFC10
    .dw 0xC460, 0xCC60, 0xD460, 0xDC60, 0xE460, 0xEC60, 0xF460, 0xFC60
    .dw 0xC4B0, 0xCCB0, 0xD4B0, 0xDCB0, 0xE4B0, 0xECB0, 0xF4B0, 0xFCB0
    .dw 0xC500, 0xCD00, 0xD500, 0xDD00, 0xE500, 0xED00, 0xF500, 0xFD00
    .dw 0xC550, 0xCD50, 0xD550, 0xDD50, 0xE550, 0xED50, 0xF550, 0xFD50
    .dw 0xC5A0, 0xCDA0, 0xD5A0, 0xDDA0, 0xE5A0, 0xEDA0, 0xF5A0, 0xFDA0
    .dw 0xC5F0, 0xCDF0, 0xD5F0, 0xDDF0, 0xE5F0, 0xEDF0, 0xF5F0, 0xFDF0
    .dw 0xC640, 0xCE40, 0xD640, 0xDE40, 0xE640, 0xEE40, 0xF640, 0xFE40
    .dw 0xC690, 0xCE90, 0xD690, 0xDE90, 0xE690, 0xEE90, 0xF690, 0xFE90
    .dw 0xC6E0, 0xCEE0, 0xD6E0, 0xDEE0, 0xE6E0, 0xEEE0, 0xF6E0, 0xFEE0
    .dw 0xC730, 0xCF30, 0xD730, 0xDF30, 0xE730, 0xEF30, 0xF730, 0xFF30
    .dw 0xC780, 0xCF80, 0xD780, 0xDF80, 0xE780, 0xEF80, 0xF780, 0xFF80
