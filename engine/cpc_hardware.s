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
    .globl _cpc_bank_set
    .globl _cpc_bank_restore
    .globl _bank_set
    .globl _bank_restore
    .globl _bank_get
    .globl _call_banked
    .globl _g_bank

    .globl _cpct_keyboardStatusBuffer
    .globl _cpct_mode_rom_status

    .area _CODE

;; ============================================================
;; bank_set(u8 bank_val) / cpc_bank_set(u8 bank_val)
;; __sdcccall(1): A = nou banc (0xC4..0xC7). Retorna banc anterior en A.
;; ============================================================
_bank_set::
_cpc_bank_set::
    ld      hl, #_g_bank
    ld      e, (hl)             ;; E = banc anterior
    ld      (hl), a             ;; _g_bank = nou banc (PRIMER abans de l'OUT!)
    ld      bc, #0x7F00
    out     (c), a              ;; Commuta banc de maquinari Gate Array
    ld      a, e                ;; Retorna banc anterior
    ret

;; ============================================================
;; bank_restore(u8 prev_bank)
;; __sdcccall(1): A = prev_bank
;; ============================================================
_bank_restore::
    ld      hl, #_g_bank
    ld      (hl), a             ;; _g_bank = prev_bank
    ld      bc, #0x7F00
    out     (c), a
    ret

;; ============================================================
;; cpc_bank_restore(void) - compatibilitat històrica: restaura 0xC0
;; ============================================================
_cpc_bank_restore::
    ld      a, #0xC0
    jr      _bank_restore

;; ============================================================
;; bank_get(void) - retorna el banc actual actiu en A
;; ============================================================
_bank_get::
    ld      a, (_g_bank)
    ret

;; ============================================================
;; call_banked(u8 bank, void* fn_ptr)
;; __sdcccall(1): A = bank, DE = fn_ptr
;; Commuta a 'bank', crida 'fn_ptr', restaura el banc previ
;; i preserva tots els valors de retorn (A, HL).
;; ============================================================
_call_banked::
    ld      hl, #_g_bank
    ld      c, (hl)             ;; C = banc anterior
    push    bc                  ;; desa banc anterior a la pila (C = prev)
    ld      (hl), a             ;; _g_bank = nou banc
    ld      b, #0x7F
    out     (c), a              ;; out (0x7F00), a

    ld      hl, #banked_ret$
    push    hl                  ;; adreça de retorn a la pila
    push    de                  ;; adreça de la funció
    ret                         ;; salt a DE (call indirecte)

banked_ret$:
    pop     bc                  ;; C = prev_bank
    push    af                  ;; preserva retorn A / Flags
    push    hl                  ;; preserva retorn HL
    ld      a, c
    ld      hl, #_g_bank
    ld      (hl), a             ;; restaura _g_bank
    ld      b, #0x7F
    out     (c), a              ;; restaura maquinari Gate Array
    pop     hl                  ;; restaura retorn HL
    pop     af                  ;; restaura retorn A
    ret

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

.area _DATA
_g_bank::                    .db 0xC0
_cpct_keyboardStatusBuffer:: .ds 10
_cpct_mode_rom_status::      .db 0x8D
