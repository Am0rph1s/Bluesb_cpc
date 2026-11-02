#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI6.BIN per al nivell 6 (CONCERT).

Mateixa cel·la 16x32 / 512 B que ENEMI1..ENEMI5.BIN. Les imatges surten de ENEMI6.SQV.
Celes (16):
  0,1    tipus 3 guarda (op1): walk frames 0..1
  2,3,4  tipus 3 guarda (altres poses / gir: frames 2..4)
  5,6    tipus 4 policia (op2): walk frames 5..6
  7..10  tipus 4 policia (altres poses: frames 7..10)
  11     tipus 4 policia (tret: frame 11)
  12     tipus 4 policia (bala DOS frame 12)
  13     projectils composite (ou/bala/plat d'ENEMI1.BIN)
  14,15  lliures
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_enemy_frames import pack_cell  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI6.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI6.BIN")
L1_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.BIN")

CELLS = [
    (0, 0),    # tipus 3 guarda walk A
    (1, 1),    # tipus 3 guarda walk B
    (2, 2),    # tipus 3 guarda pose 2
    (3, 3),    # tipus 3 guarda pose 3
    (4, 4),    # tipus 3 guarda gir
    (5, 5),    # tipus 4 policia walk A
    (6, 6),    # tipus 4 policia walk B
    (7, 7),    # tipus 4 policia pose 7
    (8, 8),    # tipus 4 policia pose 8
    (9, 9),    # tipus 4 policia pose 9
    (10, 10),  # tipus 4 policia pose 10
    (11, 11),  # tipus 4 policia tret (aim)
    (12, 12),  # bala d'ENEMI6.SQV (frame 12)
]


def crop_content(px, w, h):
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
    print("ENEMI6.SQV: %d frames" % len(frames))

    cells = [bytes(512) for _ in range(16)]
    for cell, idx in CELLS:
        w, h, px = frames[idx]
        px, w, h = crop_content(px, w, h)
        assert w <= 32 and h <= 32, (idx, w, h)
        cells[cell] = pack_cell(px, w, h)

    # Projectils composite a cela 13: ou/bala/plat d'ENEMI1.BIN
    l1 = open(L1_BIN, "rb").read()
    assert len(l1) >= 14 * 512, len(l1)
    cells[13] = l1[13 * 512:14 * 512]

    out = b"".join(cells)
    assert len(out) == 16 * 512
    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (16 celes)" % (OUT_BIN, len(out)))


if __name__ == "__main__":
    main()
