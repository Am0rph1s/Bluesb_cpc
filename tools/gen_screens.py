#!/usr/bin/env python3
"""gen_screens.py - Pantalles fixes DOS VGA -> Mode 0 CPC (avaluacio F0.3).
SPLASH = PRES.SQZ meitat superior (logo), SELECT = CHOIX.SQZ, MAP = INTER.SQZ.
Sortida: .BIN (160x200 indices 0..15 empaquetats 2px/byte, 16000 B) + .PAL (RGB)
+ preview PNG. La paleta HW (INKR) s'assigna al cablejat (F2).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'bbdata'))
from unsqz import unsqz
from ilbm import read_ilbm
from PIL import Image

OUT = os.path.join('/Users', 'esquerra', 'AppData', 'Local', 'Temp', 'opencode')


def convert(name, src, y0, y1):
    w, h, pl, pal, px = read_ilbm(unsqz(open(src, 'rb').read()))
    rows = [row[0::2] for row in px[y0:y1]]  # 320 -> 160 (pixel esquerre)
    assert len(rows) == 200 and len(rows[0]) == 160, (len(rows), len(rows[0]))
    im = Image.new('RGB', (320, 200))
    d = im.load()
    for y in range(200):
        for x in range(320):
            d[x, y] = pal[px[y0 + y][x]]
    q = im.quantize(colors=16, method=Image.MEDIANCUT)
    qp = q.getpalette()[:48]
    pal16 = [tuple(qp[i * 3:i * 3 + 3]) for i in range(16)]
    qi = list(q.getdata())
    out = bytearray()
    for y in range(200):
        for xb in range(80):
            a = qi[y * 320 + xb * 2] & 0x0F
            b = qi[y * 320 + xb * 2 + 1] & 0x0F
            # Byte Mode 0: pixel esq bits 7,5,3,1; dret 6,4,2,0.
            out.append(((a & 1) << 7) | (((a >> 1) & 1) << 3) | (((a >> 2) & 1) << 5) |
                       (((a >> 3) & 1) << 1) | ((b & 1) << 6) | (((b >> 1) & 1) << 2) |
                       (((b >> 2) & 1) << 4) | (((b >> 3) & 1) << 0))
    assert len(out) == 16000
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.BIN'), 'wb') as f:
        f.write(bytes(out))
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.PAL'), 'wb') as f:
        for c in pal16:
            f.write(bytes(c))
    prev = Image.new('RGB', (160, 200))
    pd = prev.load()
    for y in range(200):
        for x in range(160):
            pd[x, y] = pal16[qi[y * 320 + x * 2]]
    prev.resize((480, 600), Image.NEAREST).save(os.path.join(OUT, name + '_m0.png'))
    print(f'{name}: {len(out)} B + paleta, preview {name}_m0.png')


if __name__ == '__main__':
    bb = os.path.join(PROJ, 'assets', 'bbdata')
    convert('SPLASH', os.path.join(bb, 'PRES.SQZ'), 0, 200)
    convert('SELECT', os.path.join(bb, 'CHOIX.SQZ'), 0, 200)
    convert('MAP', os.path.join(bb, 'INTER.SQZ'), 0, 200)
