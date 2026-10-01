    .module t2
    .optsdcc -mz80 sdcccall(1)
    .area _CODE
F::
    ld a, (W)
    dec a
    sub b
    push af
    pop af
    ret
    .area _DATA
W: .db 0
