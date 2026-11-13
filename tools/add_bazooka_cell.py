import sys, os
sys.path.insert(0, 'tools')
sys.path.insert(0, 'tools/bbdata')
from sprites import load_sqv_frames
from gen_extra_frames import dos_to_cpc_pen
from graphics_tool import decode_enemy_pair, encode_enemy_pair, HW_TO_COLOR
from PIL import Image
import importlib

FRAME = 13          # el coet de la bazuka (ENEMI3.SQV)
CELL = 14           # primera cel·la lliure de L3
BIN = 'assets/bbdata/ENEMI3.BIN'
PNG = 'graphics_edit/level3_prison/edit/enemies_cpc.png'
ROW0 = 13           # fila on el posem (centrat verticalment)

frames = load_sqv_frames('assets/bbdata/ENEMI3.SQV')
w, h, px = frames[FRAME]
print('frame %d: %dx%d' % (FRAME, w, h))

# icona CPC de la cel·la (16x32), amb el mapatge semantic de gen_extra_frames
box = [[None] * 16 for _ in range(32)]
w_m0 = (w + 1) // 2
x_shift = (16 - w_m0) // 2
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
        box[ROW0 + y][xm] = dos_to_cpc_pen.get(val)

# bytes de la cel·la
raw = bytearray()
for y in range(32):
    for xb in range(8):
        inv, img = encode_enemy_pair(box[y][xb * 2], box[y][xb * 2 + 1])
        raw.append(inv)
        raw.append(img)
raw = bytes(raw)

# 1) escriure al binari
b = bytearray(open(BIN, 'rb').read())
assert len(b) == 8192
print('cell %d abans: buida? %s' % (CELL, all(v == 0 for v in b[CELL * 512:(CELL + 1) * 512])))
b[CELL * 512:(CELL + 1) * 512] = raw
open(BIN, 'wb').write(bytes(b))
print('escrit %s cell %d' % (BIN, CELL))

# 2) escriure al PNG master (cel·la 14 = col 2, fila 3)
pk = importlib.import_module('pack_level')
pal = pk.LEVEL_PALETTES[2]
rgb = [tuple(HW_TO_COLOR[h2]['rgb']) for h2 in pal]
im = Image.open(PNG).convert('RGBA')
p = im.load()
cx, cy = (CELL % 4) * 16, (CELL // 4) * 32
for y in range(32):
    for x in range(16):
        pen = box[y][x]
        p[cx + x, cy + y] = rgb[pen] + (255,) if pen is not None else (0, 0, 0, 0)
im.save(PNG)
print('escrit %s cell %d (%dx%d em) ' % (PNG, CELL, cx, cy))
