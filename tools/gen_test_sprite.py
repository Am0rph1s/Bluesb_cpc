#!/usr/bin/env python3
"""Genera src/player_sprite.h: rombe 16x16 Mode 1, interleaved [mask,img]."""
import os

W, H = 16, 16
NB = W // 4

data = []
for ly in range(H):
    for bx in range(NB):
        img = 0
        for p in range(4):
            px = bx * 4 + p
            inside = abs(px - 7.5) + abs(ly - 7.5) <= 7.5
            if inside:
                img |= (0x80 >> p) | (0x08 >> p)
        mask = 0xFF ^ img
        data.append(mask)
        data.append(img)

lines = []
for i in range(0, len(data), 8):
    lines.append("    " + ", ".join("0x%02X" % b for b in data[i:i + 8]) + ",")

hdr = (
    "#ifndef PLAYER_SPRITE_H\n"
    "#define PLAYER_SPRITE_H\n\n"
    '#include "cpctelera.h"\n\n'
    "// Sprite de prova 16x16 Mode 1, format interleaved [mask,img] per byte.\n"
    "#define PLAYER_SPR_W_BYTES 4\n"
    "#define PLAYER_SPR_H 16\n\n"
    "static const u8 g_player_spr[%d] = {\n%s\n};\n\n"
    "#endif\n"
) % (len(data), "\n".join(lines))

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "player_sprite.h")
with open(out, "w") as f:
    f.write(hdr)
print("escrit", out, "bytes=", len(data))
