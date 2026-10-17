;; ============================================================
;; zx0_decompress.s - Descompressor ZX0 estàndard Z80 per SDCC
;; Core VERBATIM d'OLD_V1/dzx0_standard_CLASSIC.asm (Einar Saukas,
;; 69 bytes, format classic v1) — OJO: NO usar el dzx0_standard
;; actual (v2): el seu loop MSB espera bits INVERTITS i amb els
;; nostres .ZX0 (classic=True, MSB pla) descodifica escombraria a
;; partir de la primera gamma MSB multi-bit (V>=2). V1 i v2
;; coincideixen en literals/last-offset/longituds/MSB=1, per aixo
;; els primers blocs "semblaven" be.
;; Prototip C: void zx0_decompress(const void* src, void* dst);
;; (HL = src, DE = dst per __sdcccall(1)).
;; ============================================================

    .module zx0_decompress
    .optsdcc -mz80 sdcccall(1)
    .area   _CODE

_zx0_decompress::
    ;; En __sdcccall(1), HL = src, DE = dst directament
    ;; (OLD_V1/dzx0_standard_CLASSIC.asm verbatim; $ -> #0x per sdas)
dzx0_standard:
    ld      bc, #0xFFFF             ;; preserve default offset 1
    push    bc
    inc     bc
    ld      a, #0x80

dzx0s_literals:
    call    dzx0s_elias             ;; obtain length
    ldir                            ;; copy literals
    add     a, a                    ;; copy from last offset or new offset?
    jr      c, dzx0s_new_offset

    ;; copy from last offset (repeat string)
    call    dzx0s_elias             ;; obtain length
dzx0s_copy:
    ex      (sp), hl                ;; preserve source, restore offset
    push    hl                      ;; preserve offset
    add     hl, de                  ;; calculate destination - offset
    ldir                            ;; copy from offset
    pop     hl                      ;; restore offset
    ex      (sp), hl                ;; preserve offset, restore source
    add     a, a                    ;; copy from literals or new offset?
    jr      nc, dzx0s_literals

dzx0s_new_offset:
    call    dzx0s_elias             ;; obtain offset MSB (gamma pla v1)
    ex      af, af'
    pop     af                      ;; discard last offset
    xor     a                       ;; adjust for negative offset
    sub     c
    ret     z                       ;; check end marker (V==256 -> c==0)
    ld      b, a                    ;; b = -V
    ex      af, af'
    ld      c, (hl)                 ;; obtain offset LSB
    inc     hl
    rr      b                       ;; last offset bit becomes first length bit
    rr      c
    push    bc                      ;; preserve new offset
    ld      bc, #1                  ;; obtain length
    call    nc, dzx0s_elias_backtrack
    inc     bc
    jr      dzx0s_copy

dzx0s_elias:
    inc     c                       ;; interlaced Elias gamma coding
dzx0s_elias_loop:
    add     a, a
    jr      nz, dzx0s_elias_skip
    ld      a, (hl)                 ;; load another group of 8 bits
    inc     hl
    rla

dzx0s_elias_skip:
    ret     c
dzx0s_elias_backtrack:
    add     a, a
    rl      c
    rl      b
    jr      dzx0s_elias_loop
