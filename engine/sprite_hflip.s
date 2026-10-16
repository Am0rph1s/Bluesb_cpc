;; ============================================================
;; sprite_hflip.s - Gir horitzontal ultraràpid per a frames Mode 0
;; Inverteix un frame d'en Jake (16 bytes/línia x 30 línies = 480 bytes)
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
s_last_hflip_src:  .dw 0           ;; Cache de l'últim frame girat a 0x7700

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
    ld      l, #0                   ;; L comença a 0 (adreça de pàgina alineada)
init_loop$:
    ld      a, l
    and     #0xAA
    rrca
    ld      c, a                    ;; C = (L & 0xAA) >> 1
    ld      a, l
    and     #0x55
    rlca
    or      c                       ;; A = C | ((L & 0x55) << 1)
    ld      (hl), a                 ;; Desa a lut[L]
    inc     l
    jr      nz, init_loop$          ;; 256 iteracions (0..255)
    ld      hl, #0
    ld      (s_last_hflip_src), hl  ;; Invalida el cache de frame girat
    ret

;; ============================================================
;; _sprite_hflip(const u8* src, u8* dst)
;; HL = src (480 bytes, 30 línies x 16 bytes [8 parells m,i])
;; DE = dst (480 bytes)
;;
;; Algorisme directe amb taula BC (B = 0x7F constant):
;; ld c, (hl) -> ld a, (bc) [LUT lookup ultra-ràpid, 7 T]
;; Cacheja l'últim src girat per estalviar 11.500 T-states quan
;; es repeteix el mateix frame (segona pàgina o frame estàtic).
;; ============================================================
_sprite_hflip::
    ld      a, (s_last_hflip_src)
    cp      l
    jr      nz, 0$
    ld      a, (s_last_hflip_src + 1)
    cp      h
    ret     z                       ;; Ja està girat a 0x7700!
0$:
    ld      (s_last_hflip_src), hl

    ;; Ajustar HL a la primera màscara 7 (src + 14)
    ld      bc, #14
    add     hl, bc

    ld      a, (_g_hflip_lut_hi)
    ld      b, a                    ;; B = 0x7F (byte alt de la LUT constant!)

    ld      a, #30                  ;; 30 línies de trama

hflip_line_loop$:
    push    af                      ;; Desa comptador (segur davant ISR AKG)

    .rept 8
    ld      c, (hl)                 ;; C = mask font
    inc     hl                      ;; HL = img font
    ld      a, (bc)                 ;; A = flip(mask) de la LUT
    ld      (de), a                 ;; Escriu mask a dst
    inc     de
    ld      c, (hl)                 ;; C = img font
    dec     hl
    dec     hl
    dec     hl                      ;; HL = mask de la columna anterior
    ld      a, (bc)                 ;; A = flip(img) de la LUT
    ld      (de), a                 ;; Escriu img a dst
    inc     de
    .endm

    ;; Avançar HL a la màscara 7 de la següent línia font ((src - 2) + 32 = src + 30)
    ld      a, #32
    add     a, l
    ld      l, a
    jr      nc, 1$
    inc     h
1$:
    pop     af
    dec     a
    jr      nz, hflip_line_loop$
    ret

