#!/usr/bin/env python3
"""gen_map_sticker.py - icones del mapa DOS (SPRITE.SQV) -> Mode 0 CPC.

Font: SPRITE.SQV frames 125 (dash de ruta 16x6) i 126 (sticker nota
musical 48x34). Desti: assets/bbdata/MAPSTICK.BIN a la cua de FMAP.ZX0
(el depack l'ignora, com DANCE20 a FSELECT).

Format (parelles inv,img com DANCE20: dst=(dst&inv)|img), files
encoixinades a 8 parells (blitter f_olit_row d'una tirada):
- sticker 24x34 -> files de 16 parells (32 B, 8 reals + 8 no-op) x34
  = 1088 B a offset 0;
- dash 8x6 -> files de 8 parells (16 B, 4 reals + 4 no-op) x6 = 96 B
  a offset 1088. Total STICK_LEN = 1184 B.

Pens del MAPA existent (MAP.PALHW, sense tocar paleta). La nota va en
VERMELL FORT (contrast sobre l'edifici, 14/10/26) en comptes del cian
DOS: cos a pen 11 (255,0,0), ombres a pen 1 (128,0,0):
  EGA11 cian   -> pen 11 vermell fort
  EGA12 rosa   -> pen 11 vermell fort
  EGA4 vermell -> pen 11 vermell fort
  EGA2 verd    -> pen 1 vermell fosc
  EGA8 gris    -> pen 1 vermell fosc
  EGA13 magenta(255,85,255) -> pen 15 (255,128,255) (dash, intacte DOS)
Geometria: 48->24 / 16->8 (pixel esquerre, com gen_screens).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'bbdata'))
from sprites import load_sqv_frames
from PIL import Image

VMAP_NOTE = {0: None, 2: 1, 4: 11, 8: 1, 11: 11, 12: 11}
VMAP_DASH = {0: None, 11: 14, 13: 15}

STICK_W, STICK_H = 24, 34
DASH_W, DASH_H = 8, 6
STICK_LEN = 34 * 32 + 6 * 16  # 1184


def pack(a, b):
    """Byte Mode 0: pixel esq bits 7,5,3,1; dret 6,4,2,0 (com gen_screens)."""
    return (((a & 1) << 7) | (((a >> 1) & 1) << 3) | (((a >> 2) & 1) << 5) |
            (((a >> 3) & 1) << 1) | ((b & 1) << 6) | (((b >> 1) & 1) << 2) |
            (((b >> 2) & 1) << 4) | (((b >> 3) & 1) << 0))


def convert(w, h, px, vmap, pairs):
    """Sprite SQV -> files de `pairs' parells (inv,img), pad no-op a dreta."""
    assert w // 2 <= pairs * 2, (w, pairs)
    out = bytearray()
    cv = []
    for y in range(h):
        row = []
        for pi in range(pairs):
            cells = []
            for k in range(2):
                x = pi * 2 + k
                if x < w // 2:
                    v = px[y][x * 2] & 15
                    if v not in vmap:
                        raise SystemExit('color EGA %d no mapejat' % v)
                    cells.append(vmap[v])
                else:
                    cells.append(None)
            row.append(cells)
        cv.append(row)
        for (a, b) in row:
            out.append(pack(15 if a is None else 0, 15 if b is None else 0))
            out.append(pack(0 if a is None else a, 0 if b is None else b))
    return bytes(out), cv


def main():
    frames = load_sqv_frames(os.path.join(PROJ, 'assets', 'bbdata', 'SPRITE.SQV'))
    w, h, px = frames[126]
    assert (w, h) == (48, 34), (w, h)
    note, cvn = convert(w, h, px, VMAP_NOTE, 16)
    w, h, px = frames[125]
    assert (w, h) == (16, 6), (w, h)
    dash, cvd = convert(w, h, px, VMAP_DASH, 8)
    blob = note + dash
    assert len(blob) == STICK_LEN, len(blob)
    open(os.path.join(PROJ, 'assets', 'bbdata', 'MAPSTICK.BIN'), 'wb').write(blob)
    MPAL = {1: (128, 0, 0), 11: (255, 0, 0),
            14: (128, 255, 255), 15: (255, 128, 255)}
    prev = Image.new('RGB', (24 + 8 + 6, 34), (24, 24, 28))
    for y in range(STICK_H):
        for pi, (a, b) in enumerate(cvn[y]):
            for k, pen in ((0, a), (1, b)):
                if pen is not None:
                    prev.putpixel((pi * 2 + k, y), MPAL[pen])
    for y in range(DASH_H):
        for pi, (a, b) in enumerate(cvd[y]):
            for k, pen in ((0, a), (1, b)):
                if pen is not None:
                    prev.putpixel((24 + 6 + pi * 2 + k, y), MPAL[pen])
    prev = prev.resize((prev.size[0] * 8, prev.size[1] * 8), Image.NEAREST)
    prev.save(os.path.join('/Users', 'esquerra', 'AppData', 'Local', 'Temp',
                           'opencode', 'mapstick.png'))
    print('MAPSTICK.BIN: nota+dasha (%d B) + preview mapstick.png' % len(blob))


if __name__ == '__main__':
    main()
