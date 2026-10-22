;; ============================================================
;; mover_gen.s - prototip ASM del mover generic (FASE 4, NO LINKAT)
;; ------------------------------------------------------------
;; Cobreix: vertical + tile17 + horitzontal + find + respawn.
;; NO s'enllaca al build de L1: el C d'op4 es mes petit. Es el
;; punt de partida per als nivells 2-6 (op11/17/19, horitzontals).
;; sdasz80 d'aquest entorn peta amb (ix+d)/(iy+d): cal HL/DE.
;; Els simbols tile_type/tile_set son stubs de mesura; a la
;; integracio real s'han de canviar per _b5_tile_type/_b5_set_tile.
;; Per mesurar: py -3 tools/measure_mover_sizes.py
;; ============================================================
    .module mover_gen
    .optsdcc -mz80 sdcccall(1)
    .area _CODE

    .globl _mover_gen_update_all
    .globl _mover_gen_find
    .globl _mover_gen_respawn_all

_mover_gen_update_all:
    ld      a,b
    or      a
    ret     z
1$:
    push    bc
    push    de
    push    hl
    call    mover_update_one
    pop     hl
    pop     de
    pop     bc
    ld      a,l
    add     a,#12
    ld      l,a
    jr      nc,2$
    inc     h
2$:
    ld      a,e
    add     a,#16
    ld      e,a
    jr      nc,3$
    inc     d
3$:
    djnz    1$
    ret

mover_update_one:
    ld      (s_ptr),hl
    push    hl
    push    de
    pop     hl              ;; HL = def
    ld      de,#4
    add     hl,de           ;; def+4
    ld      de,#sdef
    ld      bc,#12
    ldir
    pop     hl              ;; HL = estat
    ld      de,#sstate
    ld      bc,#12
    ldir

    ;; flags & VERT?
    ld      a,(sdef+1)
    and     #2
    jp      z,horz

    ;; dir
    ld      a,(sstate+5)
    or      a
    jp      m,up
down:
    ld      a,(sstate+6)
    ld      b,a
    ld      a,(sdef+2)      ;; wait
    cp      b
    ld      a,b
    jr      nc,down_go
    inc     a
    ld      (sstate+6),a
    xor     a
    ld      (sstate+4),a
    jp      done
down_go:
    ld      bc,(sstate+2)   ;; y
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    ld      a,c             ;; row
    ld      b,a
    ld      a,(sdef+6)      ;; down_off
    add     a,b
    ld      l,a
    ld      a,(sdef+0)      ;; col
    call    tile_type
    ld      b,a
    ld      a,(sdef+7)      ;; stop_op
    cp      b
    jr      nz,down_cont
    ld      a,#-1
    ld      (sstate+5),a
    ld      a,#1
    ld      (sstate+6),a
down_cont:
    ld      a,(sdef+3)      ;; vy_down
    ld      (sstate+4),a
    ;; tile17 avall: (y-12)&15 == 0
    ld      bc,(sstate+2)
    ld      a,c
    sub     #12
    and     #15
    jr      nz,down_add
    ld      bc,(sstate+2)
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    ld      l,c
    ld      a,(sdef+0)
    call    tile_set
    ld      l,c
    ld      a,(sdef+0)
    dec     a
    call    tile_set
down_add:
    call    add_vy
    jp      done

up:
    ld      a,(sstate+6)
    ld      b,a
    ld      a,(sdef+2)
    cp      b
    ld      a,b
    jr      nc,up_go
    inc     a
    ld      (sstate+6),a
    xor     a
    ld      (sstate+4),a
    jp      done
up_go:
    ld      bc,(sstate+2)
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    ld      a,c
    ld      b,a
    ld      a,(sdef+5)      ;; up_off
    add     a,b
    ld      l,a
    ld      a,(sdef+0)
    call    tile_type
    ld      b,a
    ld      a,(sdef+7)
    cp      b
    jr      nz,up_cont
    ld      a,#1
    ld      (sstate+5),a
    ld      a,#1
    ld      (sstate+6),a
up_cont:
    ld      a,(sdef+4)      ;; vy_up
    ld      (sstate+4),a
    ;; tile17 amunt: y&15 == 0
    ld      a,(sstate+2)
    and     #15
    jr      nz,up_add
    ld      bc,(sstate+2)
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    dec     c
    ld      l,c
    ld      a,(sdef+0)
    call    tile_set
    ld      l,c
    ld      a,(sdef+0)
    dec     a
    call    tile_set
up_add:
    call    add_vy

horz:
    ;; row = y>>4
    ld      bc,(sstate+2)
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    srl     b
    rr      c
    ;; col = (x>>3) + (dir ? -4 : +4)
    ld      de,(sstate+0)
    srl     d
    rr      e
    srl     d
    rr      e
    srl     d
    rr      e
    ld      a,(sstate+5)
    or      a
    jr      z,1$
    ld      a,e
    sub     #4
    ld      e,a
    jr      2$
1$:
    ld      a,e
    add     a,#4
    ld      e,a
2$:
    ld      a,e
    ld      l,c
    call    tile_type
    ld      b,a
    ld      a,(sdef+11)
    cp      b
    jr      nz,done
    ld      a,(sstate+5)
    xor     #1
    ld      (sstate+5),a

done:
    ld      hl,#sstate
    ld      de,(s_ptr)
    ld      bc,#12
    ldir
    ret

add_vy:
    ld      a,(sstate+4)
    ld      e,a
    ld      d,#0
    bit     7,e
    jr      z,1$
    ld      d,#0xFF
1$:
    ld      bc,(sstate+2)
    ld      a,c
    add     a,e
    ld      c,a
    ld      a,b
    adc     a,d
    ld      b,a
    ld      (sstate+2),bc
    ret

tile_type:
    ld      a,#0
    ret
tile_set:
    ret

;; ---- find: HL=estat, B=count, DE=px; py/out a memoria ----
_mover_gen_find:
    ld      a,b
    or      a
    jp      z,find_none
    ld      (find_cnt),a
    xor     a
    ld      (find_idx),a
find_loop:
    ld      c,(hl)
    inc     hl
    ld      b,(hl)
    dec     hl
    ld      a,c
    sub     e
    ld      c,a
    ld      a,b
    sbc     a,d
    ld      b,a
    ld      a,c
    add     a,#8
    ld      c,a
    ld      a,b
    adc     a,#0
    ld      b,a
    ld      a,b
    or      a
    jr      nz,find_next
    ld      a,c
    cp      #33
    jr      nc,find_next
    ;; surface = y - 14
    inc     hl
    inc     hl
    ld      c,(hl)
    inc     hl
    ld      b,(hl)
    dec     hl
    dec     hl
    dec     hl
    ld      a,c
    sub     #14
    ld      c,a
    ld      a,b
    sbc     a,#0
    ld      b,a
    ;; py - surface entre 0 i 8
    ld      a,(find_py)
    sub     c
    ld      e,a
    ld      a,(find_py+1)
    sbc     a,b
    ld      d,a
    bit     7,d
    jr      nz,find_next
    ld      a,d
    or      a
    jr      nz,find_next
    ld      a,e
    cp      #9
    jr      nc,find_next
    ;; out = surface - 30
    ld      a,c
    sub     #30
    ld      (find_out),a
    ld      a,b
    sbc     a,#0
    ld      (find_out+1),a
    ld      a,(find_idx)
    ret
find_next:
    ld      a,(find_idx)
    inc     a
    ld      (find_idx),a
    ld      a,l
    add     a,#12
    ld      l,a
    jr      nc,1$
    inc     h
1$:
    ld      a,(find_cnt)
    dec     a
    ld      (find_cnt),a
    jr      nz,find_loop
find_none:
    ld      a,#0xFF
    ret

;; ---- respawn: HL=estat, DE=defs, B=count ----
_mover_gen_respawn_all:
    ld      a,b
    or      a
    ret     z
1$:
    ld      a,(de)
    ld      (hl),a
    inc     de
    inc     hl
    ld      a,(de)
    ld      (hl),a
    inc     de
    inc     hl
    ld      a,(de)
    ld      (hl),a
    inc     de
    inc     hl
    ld      a,(de)
    ld      (hl),a
    inc     de
    inc     hl
    xor     a
    ld      (hl),a          ;; vy
    inc     hl
    ld      a,#-1
    ld      (hl),a          ;; dir
    inc     hl
    xor     a
    ld      (hl),a          ;; wait
    inc     hl
    ld      a,(de)          ;; map_col
    ld      (hl),a
    inc     de
    inc     hl
    ld      a,(de)          ;; flags
    ld      (hl),a
    inc     de
    inc     hl
    xor     a
    ld      (hl),a          ;; phase
    inc     hl
    ld      (hl),a          ;; d51
    inc     hl
    inc     hl              ;; pad
    ld      a,e
    add     a,#10
    ld      e,a
    jr      nc,2$
    inc     d
2$:
    djnz    1$
    ret

find_cnt:
    .db 0
find_idx:
    .db 0
find_py:
    .dw 0
find_out:
    .dw 0

s_ptr:
    .dw 0
sstate:
    .ds 12
sdef:
    .ds 12

    .area _DATA
    .db 0
