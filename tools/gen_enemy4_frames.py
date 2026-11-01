#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI4.BIN per al nivell 4 (EGOU - Clavegueram).

Mateixa cela 16x32 / 512 B que ENEMI1/ENEMI2/ENEMI3.BIN.
Les imatges surten d'ENEMI4.SQV.

Celes (16):
  0, 1      tipus 25 policia (op2): walk 0/1
  2, 3      tipus 28 patruller (op1): walk 15/16
  4, 5      tipus 34 / 26 peix gran d'aigua (op16/op6): swim 6/7 (fa mal)
  6, 7      tipus 27 rata gran (op13): walk 9/10
  8         tipus 29 rata petita (op13): walk 18
  9         tipus 30 estatic (op14): pose 13
  10, 11    tipus 31 walker mitja (op13): walk 20/21
  12        tipus 32 aranya (op15): pose 23
  13        projectils (copia d'ENEMI1.BIN: ou/bala/plat)
  14, 15    tipus 33 peix petit d'aigua (op16): swim 25/26 (decoratiu, class 0)

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
    (0, 0),    # tipus 25 policia walk A
    (1, 1),    # tipus 25 policia walk B
    (2, 15),   # tipus 28 patruller walk A
    (3, 16),   # tipus 28 patruller walk B
    (4, 6),    # tipus 34 / 26 peix gran / monstre walk A
    (5, 7),    # tipus 34 / 26 peix gran / monstre walk B
    (6, 9),    # tipus 27 rata gran walk A
    (7, 10),   # tipus 27 rata gran walk B
    (8, 18),   # tipus 29 rata petita
    (9, 13),   # tipus 30 estatic
    (10, 20),  # tipus 31 walker mitja walk A
    (11, 21),  # tipus 31 walker mitja walk B
    (12, 23),  # tipus 32 aranya
    (14, 25),  # tipus 33 peix petit decoratiu swim A
    (15, 26),  # tipus 33 peix petit decoratiu swim B
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
