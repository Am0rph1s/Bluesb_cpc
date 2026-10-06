;; ============================================================
;; sprite_hflip.s - Gir horitzontal ultraràpid per a frames Mode 0
;; Inverteix un frame d'en Jake (12 bytes/línia x 30 línies = 360 bytes)
;; Prototip C: void sprite_hflip_init_lut(u8* lut_256_aligned);
;;             void sprite_hflip(const u8* src, u8* dst);
;; SDCC 4.5+ (__sdcccall 1): HL = src, DE = dst
;; ============================================================

    .module sprite_hflip
    .optsdcc -mz80 sdcccall(1)

    .globl _sprite_hflip
    .globl _sprite_hflip_init_lut
    .globl _g_hflip_lut_hi

    .area _DATA
_g_hflip_lut_hi::  .db 0x7F        ;; Per defecte apunta a 0x7F00 (Banc 7)

    .area _CODE

;; ============================================================
;; _sprite_hflip_init_lut(u8* lut_page_aligned)
;; HL = adreça de la LUT (ha d'estar alineada a 256 bytes!)
;; Omple la taula de 256 valors amb el swap de píxels Mode 0:
;; ((b & 0xAA) >> 1) | ((b & 0x55) << 1)
;; ============================================================
_sprite_hflip_init_lut::
    ld      a, h
    ld      (_g_hflip_lut_hi), a    ;; Desa el byte alt de la LUT
    ld      b, #0                   ;; B = 0 .. 255 (256 iteracions)
init_loop$:
    ld      a, b
    and     #0xAA
    rrca
    ld      c, a                    ;; C = (B & 0xAA) >> 1
    ld      a, b
    and     #0x55
    rlca
    or      c                       ;; A = C | ((B & 0x55) << 1)
    ld      (hl), a                 ;; Desa a lut[B]
    inc     l
    djnz    init_loop$
    ret

;; ============================================================
;; _sprite_hflip(const u8* src, u8* dst)
;; HL = src (360 bytes, 30 línies x 12 bytes [6 parells m,i])
;; DE = dst (360 bytes)
;;
;; Distribució òptima de registres:
;; Conjunt Principal : HL = punter font (src)
;; Conjunt Ombra     : HL' = punter LUT (0x7F00 + index)
;;                     DE' = punter destí (dst)
;; ============================================================
_sprite_hflip::
    ;; Inicialitzar conjunt ombra: H' = lut_hi, DE' = dst
    ld      a, (_g_hflip_lut_hi)
    push    de
    exx
    pop     de                      ;; DE' = dst (punter destí)
    ld      h, a                    ;; H' = lut_hi (p.ex. 0x7F)
    exx

    ld      b, #30                  ;; 30 línies de trama
hflip_line_loop$:
    push    bc

    ;; Per a la línia actual, avancem HL al final de la línia (src + 11)
    ld      bc, #11
    add     hl, bc                  ;; HL apunta a img5 (darrer byte de la línia)

    ld      c, #6                   ;; 6 parells [mask, img] per línia
hflip_pair_loop$:
    ld      b, (hl)                 ;; B = img font (7 T)
    dec     hl                      ;;              (6 T)
    ld      a, (hl)                 ;; A = mask font(7 T)
    dec     hl                      ;;              (6 T)

    exx                             ;; Switch a conjunt ombra! (4 T)
    ;; Al conjunt ombra: H' = lut_hi, DE' = destí
    ld      l, a                    ;; L' = mask font (4 T)
    ld      a, (hl)                 ;; A' = flip(mask)(7 T)
    ld      (de), a                 ;; Escriu mask!   (7 T)
    inc     de                      ;;                (6 T)

    ld      l, b                    ;; L' = img font  (4 T)
    ld      a, (hl)                 ;; A' = flip(img) (7 T)
    ld      (de), a                 ;; Escriu img!    (7 T)
    inc     de                      ;;                (6 T)
    exx                             ;; Retorna a principal! (4 T)

    dec     c                       ;; Comptador de parells (4 T)
    jr      nz, hflip_pair_loop$    ;; (12/7 T)

    ;; Ara HL ha quedat a src - 1 (inici de la línia font - 1).
    ;; Per anar a l'inici de la següent línia font (src + 12):
    ld      bc, #13
    add     hl, bc

    pop     bc
    djnz    hflip_line_loop$

    ret
