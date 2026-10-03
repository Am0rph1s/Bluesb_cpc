;; ============================================================
;; cpc_hardware.s - Implementació nativa de maquinari Amstrad CPC
;; Compatible SDCC 4.5+ (__sdcccall 1)
;; ============================================================

    .module cpc_hardware
    .optsdcc -mz80 sdcccall(1)

    .globl _cpct_disableFirmware
    .globl _cpct_setVideoMode
    .globl _cpct_setBorder
    .globl _cpct_setPALColour
    .globl _cpct_waitVSYNC
    .globl _cpct_scanKeyboard_f
    .globl _cpct_isKeyPressed
    .globl _cpct_drawSpriteMasked

    .globl _cpct_keyboardStatusBuffer
    .globl _cpct_mode_rom_status

    .area _CODE

;; ============================================================
;; cpct_disableFirmware
;; RMR 0x8C = Mode 0 + ROMs desactivades (sense canviar de mode).
;; ============================================================
_cpct_disableFirmware::
    di
    ld      bc, #0x7F8C
    out     (c), c
    ei
    ret

;; ============================================================
;; cpct_setVideoMode(u8 mode)
;; mode in A
;; ============================================================
_cpct_setVideoMode::
    and     #0x03
    or      #0x8C
    ld      bc, #0x7F00
    out     (c), a
    ret

;; ============================================================
;; cpct_setBorder(u8 hw_color)
;; hw_color in L (sdcccall1)
;; Protocol GA (firmware): out ink(16) -> out 0x40|color
;; ============================================================
_cpct_setBorder::
    ld      bc, #0x7F00
    ld      a, #0x10            ;; ink 16 = border
    out     (c), a
    ld      a, l
    or      #0x40
    out     (c), a
    ret

;; ============================================================
;; cpct_setPALColour(u8 pen, u8 hw_color)
;; pen in A, hw_color in L
;; Protocol GA (firmware): out ink -> out 0x40|color
;; ============================================================
_cpct_setPALColour::
    ld      bc, #0x7F00
    out     (c), a              ;; seleccionar ink (pen cru)
    ld      a, l
    or      #0x40               ;; 0x40|color
    out     (c), a
    ret

;; ============================================================
;; cpct_waitVSYNC
;; ============================================================
_cpct_waitVSYNC::
    ld      b, #0xF5
00001$:
    in      a, (c)
    rra
    jr      nc, 00001$
00002$:
    in      a, (c)
    rra
    jr      c, 00002$
    ret

;; ============================================================
;; cpct_scanKeyboard_f
;; ============================================================
_cpct_scanKeyboard_f::
    di
    ld      bc, #0xF782
    out     (c), c
    ld      bc, #0xF40E
    ld      e, b
    out     (c), c
    ld      bc, #0xF6C0
    ld      d, b
    out     (c), c
    .dw     #0x71ED             ;; out (c), 0
    ld      bc, #0xF792
    out     (c), c

    ld      a, #0x40
    ld      hl, #_cpct_keyboardStatusBuffer

    .rept   9
    ld      b, d
    out     (c), a
    ld      b, e
    ini
    inc     a
    .endm

    ld      b, d
    out     (c), a
    ld      b, e
    ini

    ld      bc, #0xF782
    out     (c), c
    ei
    ret

;; ============================================================
;; cpct_isKeyPressed(i16 key_id)
;; key_id in HL (L = line, H = mask)
;; returns result in A
;; ============================================================
_cpct_isKeyPressed::
    ld      a, h                ;; mask
    ld      d, a
    ld      h, #0
    ld      bc, #_cpct_keyboardStatusBuffer
    add     hl, bc
    xor     (hl)
    and     d
    ld      l, a
    ret

;; ============================================================
;; cpct_drawSpriteMasked(const void* sprite, void* memory, u8 width, u8 height)
;; sprite in HL, memory in DE, width/height packed on stack
;; ============================================================
_cpct_drawSpriteMasked::
    pop     iy                  ;; return address
    pop     bc                  ;; C = width, B = height
    ld      a, c
    ld      (s_dsm_w), a

00010$:                         ;; height loop
    push    de

00011$:                         ;; width loop
    ld      a, (de)
    and     (hl)
    inc     hl
    or      (hl)
    ld      (de), a
    inc     de
    inc     hl
    dec     c
    jr      nz, 00011$

    pop     de
    dec     b
    jr      z, 00019$           ;; end

    ld      a, (s_dsm_w)
    ld      c, a

    ld      a, d
    add     #0x08
    ld      d, a
    and     #0x38
    jr      nz, 00010$

    ;; boundary crossed
    ld      a, e
    add     #0x50
    ld      e, a
    ld      a, d
    adc     #0xC0
    ld      d, a
    jr      00010$

00019$:
    jp      (iy)

s_dsm_w: .db 0

.area _DATA
_cpct_keyboardStatusBuffer:: .ds 10
_cpct_mode_rom_status::      .db 0x8D
