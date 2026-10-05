;; ============================================================
;; video.s - Inicialitzacio de video Mode 0 (feta des de zero)
;; Amstrad CPC - SDCC 4.5 (sdcccall 1)
;;
;; Protocol GA correcte:
;;   paleta:  out (0x7F00), 0x40|pen   ; seleccionar ink
;;            out (0x7F00), color      ; assignar color
;;   border:  out (0x7F00), 0x50       ; ink 16 = border
;;            out (0x7F00), color
;; ============================================================
    .module video
    .optsdcc -mz80 sdcccall(1)

    .globl _video_init
    .globl _crtc_set_display_start

    .area _CODE

;; ============================================================
;; void video_init(void)
;;   - RMR Mode 0 + ROMs desactivades (0x8C)
;;   - CRTC R0..R13 (timing estandard CPC, display start = 0x0000)
;;   - Border negre
;;   - Paleta 16 colors del nivell
;; Cal cridar-lo DESPRES del carregador FDC (que reseteja la GA).
;; ============================================================
_video_init::
    di

    ;; RMR: Mode 0 + ROMs desactivades (no canvia de mode)
    ld      bc, #0x7F8C
    out     (c), c

    ;; CRTC R0..R13
    ld      hl, #crtc_table
    ld      c, #0x00            ;; index de registre
1$:
    ld      b, #0xBC
    out     (c), c              ;; seleccionar registre
    ld      a, (hl)
    inc     hl
    ld      b, #0xBD
    out     (c), a              ;; valor
    inc     c
    ld      a, c
    cp      #0x0E               ;; 14 registres (R0..R13)
    jr      nz, 1$

    ;; Border (ink 16). Valor INKR cru de la GA (0x54 = negre)
    ld      bc, #0x7F00
    ld      a, #0x10            ;; 0x10 = PENR border
    out     (c), a
    ld      a, #0x54            ;; INKR negre
    out     (c), a

    ;; Paleta 16 colors. INKR = codi de color cru de la GA (0x40-base bit)
    ld      hl, #palette_table
    ld      c, #0x00            ;; pen
2$:
    ld      b, #0x7F
    ld      a, c
    out     (c), a              ;; PENR: seleccionar pen
    ld      a, (hl)
    inc     hl
    out     (c), a              ;; INKR: codi de color cru
    inc     c
    ld      a, c
    cp      #0x10
    jr      nz, 2$

    ret

;; ============================================================
;; void crtc_set_display_start(u16 ma)
;;   HL = adreça MA completa, incloent pàgina 0x2000/0x3000 i offset circular.
;; ============================================================
_crtc_set_display_start::
    ld      bc, #0xBC0D         ;; R13 = byte baix
    out     (c), c
    ld      a, l
    ld      b, #0xBD
    out     (c), a
    ld      bc, #0xBC0C         ;; R12 = byte alt
    out     (c), c
    ld      a, h
    ld      b, #0xBD
    out     (c), a
    ret

;; Taules (dins de _CODE perque el binari nomes carrega 0x0100-<fi de codi>)
;; R12=0x30: display start 0x3000 -> adreca fisica 0xC000
;; R13=0x00: sense scroll.
crtc_table:
    .db  0x3F, 0x28, 0x2E, 0x8E, 0x26, 0x00, 0x14, 0x1E
    .db  0x00, 0x07, 0x00, 0x00, 0x30, 0x00

;; Paleta Mode 0 (Amiga -> CPC hardware):
;;   pen 0 negre, 1 rosa, 2 gris, 3 gris, 4 blau pastel, 5 groc, 6 gris clar,
;;   7 rosa, 8 blau cel, 9 verd fosc, 10 verd, 11 negre, 12 blau clar,
;;   13 vermell fosc, 14 vermell fosc, 15 blanc
;; Paleta Mode 0 - codis de color crus de la GA del CPC:
;;   negre=0x54, rosa=0x47, blanc=0x40, blau=0x44, groc=0x5E,
;;   vermell brillant=0x4C, blau cel=0x57, verd=0x56, verd brillant=0x52,
;;   blau pastel=0x5F, vermell=0x5C
;; Paleta Mode 0 - codis INKR crus de la GA del CPC.
;; Referencia: negre=0x54, gris=0x40, blau=0x44, blau cel=0x57,
;;   vermell brillant=0x4C, verd=0x56, groc=0x5E, blanc=0x40(bright?)
palette_table:
    .db  0x54, 0x47, 0x40, 0x40, 0x44, 0x5E, 0x5E, 0x4C
    .db  0x57, 0x56, 0x52, 0x54, 0x5F, 0x5C, 0x5C, 0x40
