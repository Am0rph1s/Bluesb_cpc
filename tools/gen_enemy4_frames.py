#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI4.BIN per al nivell 4 (EGOU - Clavegueram).

Mateixa cela 16x32 / 512 B que ENEMI1/ENEMI2/ENEMI3.BIN.
Les imatges surten d'ENEMI4.SQV.

Celes (16):
  0, 1, 2   tipus 25 policia (op2): walk 0/1, tret 2
  3, 4, 5   tipus 28 walker (op1): walk 15/16, atac 17
  6, 7, 8   tipus 34 walker (op16): walk 6/7, pose 8
  9, 10     tipus 32 walker (op15): walk 23/24
  11        tipus 33 walker (op16): walk 25/26
  12        projectils (copia d'ENEMI1.BIN: ou/bala/plat)
  13, 14, 15 lliures

Regenerar:
  py -3 tools/gen_enemy4_frames.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_enemy_frames import pack_cell  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI4.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI4.BIN")
L1_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.BIN")

# (cela, frame SQV)
CELLS = [
    (0, 0),    # tipus 25 walk A
    (1, 1),    # tipus 25 walk B
    (2, 2),    # tipus 25 tret
    (3, 15),   # tipus 28 walk A
    (4, 16),   # tipus 28 walk B
    (5, 17),   # tipus 28 pose
    (6, 6),    # tipus 34 walk A
    (7, 7),    # tipus 34 walk B
    (8, 8),    # tipus 34 pose
    (9, 23),   # tipus 32 walk A
    (10, 24),  # tipus 32 walk B
    (11, 25),  # tipus 33 walk A
    (12, 26),  # tipus 33 walk B
]


def crop_content(px, w, h):
    """Retalla al bbox del contingut real i l'ajusta a 16x32."""
    xs = [x for y in range(h) for x in range(w) if px[y][x] != 0]
    ys = [y for y in range(h) for x in range(w) if px[y][x] != 0]
    if not xs:
        return px, w, h
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 - x0 + 1 > 32:
        x1 -= (x1 - x0 + 1) - 32
    if y1 - y0 + 1 > 32:
        y0 += (y1 - y0 + 1) - 32
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    out = [[0] * cw for _ in range(ch)]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            out[y - y0][x - x0] = px[y][x]
    return out, cw, ch


def main():
    frames = load_sqv_frames(SQV)
    print("ENEMI4.SQV: %d frames" % len(frames))

    cells = [bytes(512) for _ in range(16)]
    for cell, idx in CELLS:
        w, h, px = frames[idx]
        px, w, h = crop_content(px, w, h)
        assert w <= 32 and h <= 32, (idx, w, h)
        cells[cell] = pack_cell(px, w, h)

    # Projectils: la cela 13 d'ENEMI1.BIN te ou/bala/plat alineats.
    l1 = open(L1_BIN, "rb").read()
    assert len(l1) >= 14 * 512, len(l1)
    cells[13] = l1[13 * 512:14 * 512]

    out = b"".join(cells)
    assert len(out) == 16 * 512
    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (16 celes)" % (OUT_BIN, len(out)))


if __name__ == "__main__":
    main()
