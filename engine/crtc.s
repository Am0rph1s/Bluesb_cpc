;; ============================================================
;; crtc.s - Escriptura de registres CRTC per a scroll per maquinari
;; Blues Brothers CPC (SDCC 4.5, sdcccall 1)
;; ============================================================
;; El CRTC del CPC es programa via port 0xBC00 (seleccio de registre)
;; i 0xBD00 (escriptura de valor).
;; ============================================================

    .module crtc
    .optsdcc -mz80 sdcccall(1)

    .globl _crtc_set_scroll
    .globl _crtc_set_r3

    .area _CODE

;; ============================================================
;; void crtc_set_scroll(u16 word_off)
;;   HL = desplacament en UNITATS DE PARAULA del display start
;;        (0..1023). 1 unitat = 2 bytes = 1 caracter CRTC.
;;   Base de pantalla fixada a 0xC000 (MA13=MA12=1, nibble 0x30).
;; ============================================================
_crtc_set_scroll::
    ;; R13 (Display Start Address Low)
    ld      bc, #0xBC0D
    out     (c), c          ;; seleccionar R13
    ld      a, l
    ld      b, #0xBD
    out     (c), a          ;; R13 = byte baix del desplacament

    ;; R12 (Display Start Address High)
    ld      bc, #0xBC0C
    out     (c), c          ;; seleccionar R12
    ld      a, h
    or      #0x30           ;; base de pantalla 0xC000
    ld      b, #0xBD
    out     (c), a          ;; R12
    ret

;; ============================================================
;; void crtc_set_r3(u8 val)
;;   L = valor de R3 (amplada HSYNC/VSYNC). Per al scroll fi de
;;   mig caracter (4 px en Mode 1) s'usa 0xF5 o 0xF6.
;; ============================================================
_crtc_set_r3::
    ld      bc, #0xBC03
    out     (c), c          ;; seleccionar R3
    ld      b, #0xBD
    out     (c), l          ;; R3 = valor
    ret
