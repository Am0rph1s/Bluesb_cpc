#!/usr/bin/env python3
"""
add_l3_projectiles.py - Afegeix els projectils de L3 a les cel·les 14 i 15.

Els sprites surten de l'SQV de L3 (els mateixos que fa servir el DOS com a
"grab_type" dels projectils de `do_level_update_projectile`):

  - cel·la 14: COET de la bazuka (tipus 5/op4) -> grab_type 5 -> frame SQV 25
  - cel·la 15: BOLA del presidiari (tipus 23/op11) -> grab_type 12 -> frame SQV 22

Les cel·les 14 i 15 eren transparents. S'escriuen al binari ENEMI3.BIN i al
PNG master graphics_edit/level3_prison/edit/enemies_cpc.png.

Us: py -3 tools/add_l3_projectiles.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from sprites import load_sqv_frames          # noqa: E402
from gen_extra_frames import dos_to_cpc_pen  # noqa: E402
from graphics_tool import encode_enemy_pair, HW_TO_COLOR  # noqa: E402
from PIL import Image                        # noqa: E402
import importlib                             # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI3.SQV")
BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI3.BIN")
PNG = os.path.join(PROJ, "graphics_edit", "level3_prison", "edit", "enemies_cpc.png")

# (cel·la, frame SQV, fila on comença el contingut, x_shift en px Mode 0)
# El blitter de projectils llegeix a partir del byte 4 (px 8) de cada fila
# (+4 al punter), per tant el coet (8 px) es col·loca a px 8..15. La bola es
# mes ampla (16 px) i es dibuixa amb h_off=0 des del byte 0.
CELLS = [
    (14, 25, 13, 8),   # coet de la bazuka (16x9 DOS -> 8 px)
    (15, 22, 13, 8),   # bola del presidiari: la bola (32x7) a la meitat dreta
]

pk = importlib.import_module('pack_level')
PAL = pk.LEVEL_PALETTES[2]
RGB = [tuple(HW_TO_COLOR[h]['rgb']) for h in PAL]
frames = load_sqv_frames(SQV)
raw = bytearray(open(BIN, 'rb').read())
assert len(raw) == 8192

im = Image.open(PNG).convert('RGBA')
p = im.load()

for cell, fidx, row0, x_shift in CELLS:
    w, h, px = frames[fidx]
    box = [[None] * 16 for _ in range(32)]
    if x_shift is None:
        x_shift = (16 - (w + 1) // 2) // 2
    for y in range(h):
        for xm in range(16):
            xdos = (xm - x_shift) * 2
            p0 = px[y][xdos] if 0 <= xdos < w else 0
            p1 = px[y][xdos + 1] if 0 <= (xdos + 1) < w else 0
            val = 0
            if p0 != 0 and p1 != 0:
                val = p0 if p0 not in (3, 11) else p1
            elif p0 != 0:
                val = p0
            elif p1 != 0:
                val = p1
            box[row0 + y][xm] = dos_to_cpc_pen.get(val)

    data = bytearray()
    for y in range(32):
        for xb in range(8):
            inv, img = encode_enemy_pair(box[y][xb * 2], box[y][xb * 2 + 1])
            data.append(inv)
            data.append(img)
    raw[cell * 512:(cell + 1) * 512] = data

    cx, cy = (cell % 4) * 16, (cell // 4) * 32
    for y in range(32):
        for x in range(16):
            pen = box[y][x]
            p[cx + x, cy + y] = RGB[pen] + (255,) if pen is not None else (0, 0, 0, 0)
    print("cell %d <- frame SQV %d (%dx%d)" % (cell, fidx, w, h))

open(BIN, 'wb').write(bytes(raw))
im.save(PNG)
print("escrit %s i %s" % (BIN, PNG))
