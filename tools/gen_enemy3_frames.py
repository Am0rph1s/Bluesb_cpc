#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI3.BIN per al nivell 3 (PRISON).

Mateixa cela 16x32 / 512 B que ENEMI1/ENEMI2.BIN. Les imatges surten de
ENEMI3.SQV. Els indexs de frame SON els del DOS: es treuen de
`animframes_059d` (staticres.c), on el frame del nivell = index - SPRITES_COUNT
(146). Vegeu tools/dump_level_sprites.py per veure les tires per tipus.

Celes (16):
  0,1,2  tipus 3 policia (op2)        frames 0,1,2 (walk A/B + tret)
  5..11  tipus 4 llançador (op3)       frames 5..11 (reservat; op3 pendent)
  12     projectils (copia d'ENEMI1.BIN: ou/bala/plat)
  13,14  tipus 6 gos (op1)             frames 26,27
  3,4,15 lliures

El tipus 5/op4 i el 23/op11 son movers, no walkers de C6 i no van en aquesta
taula.

Regenerar:
  py -3 tools/gen_enemy3_frames.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_enemy_frames import pack_cell  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI3.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI3.BIN")
L1_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.BIN")

# (cela, frame SQV)
CELLS = [
    (0, 0),    # tipus 3 walk A
    (1, 1),    # tipus 3 walk B
    (2, 2),    # tipus 3 tret (op2 special_anim)
    (5, 5),    # tipus 4 walk A (op3 pendent)
    (6, 6),    # tipus 4 walk B
    (7, 7),    # tipus 4
    (8, 8),    # tipus 4
    (9, 9),    # tipus 4
    (10, 10),  # tipus 4
    (11, 11),  # tipus 4
    (13, 26),  # tipus 6 walk A
    (14, 27),  # tipus 6 walk B
]


def crop_content(px, w, h):
    """Retalla al bbox del contingut real i l'ajusta a 16x32 (com L2)."""
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
    print("ENEMI3.SQV: %d frames" % len(frames))

    cells = [bytes(512) for _ in range(16)]
    for cell, idx in CELLS:
        w, h, px = frames[idx]
        px, w, h = crop_content(px, w, h)
        assert w <= 32 and h <= 32, (idx, w, h)
        cells[cell] = pack_cell(px, w, h)

    # Projectils: la cela 13 d'ENEMI1.BIN te ou/bala/plat alineats.
    l1 = open(L1_BIN, "rb").read()
    assert len(l1) >= 14 * 512, len(l1)
    cells[12] = l1[13 * 512:14 * 512]

    out = b"".join(cells)
    assert len(out) == 16 * 512
    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (16 celes)" % (OUT_BIN, len(out)))


if __name__ == "__main__":
    main()
