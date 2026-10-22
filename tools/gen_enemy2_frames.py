#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI2.BIN per al nivell 2 (ENT).

Mateixa cela 16x32 / 512 B que ENEMI1.BIN. Les imatges surten de
ENEMI2.SQV (35 frames); els indexs son els del contacte de l'SQV.

Celes:
  1     tipus 12: pose de tret (frame 8, 32x32)
  2     tipus 14: pose de llançament (frame 23)
  15    tipus 21: pose de llançament (frame 30)
  5,6   tipus 12 walk (frames 8,9)
  7,8   tipus 13 walk (frames 14,15)
  9,10  tipus 14 walk (frames 21,22)
  11,12 tipus 21 walk (frames 27,28)
  13    projectils (copia coneguda de ENEMI1.BIN: ou/bala/plat)
La resta queden a zero. Els tipus 11 (48 px d'ample) i 22 (objecte) no
entren en aquesta atlas de 16 px.

Regenerar:
  py -3 tools/gen_enemy2_frames.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_enemy_frames import pack_cell  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI2.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI2.BIN")
L1_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.BIN")


def main():
    frames = load_sqv_frames(SQV)
    print("ENEMI2.SQV: %d frames" % len(frames))

    cells = [bytes(512) for _ in range(16)]

    def put(cell, idx):
        w, h, px = frames[idx]
        assert w <= 32 and h <= 32, (idx, w, h)
        cells[cell] = pack_cell(px, w, h)

    put(1, 8)      # tipus 12: pose de tret (fallback 32x)
    put(2, 23)     # tipus 14: pose de llancament
    put(5, 8)      # tipus 12 walk (home del paquet)
    put(6, 9)
    put(7, 14)     # tipus 13 walk (dona cistella)
    put(8, 15)
    put(9, 21)     # tipus 14 walk (dona bossa blava)
    put(10, 22)
    put(11, 27)    # tipus 21 walk (uniforme)
    put(12, 28)
    put(15, 30)    # tipus 21 pose de llancament

    # Projectils: la cela 13 d'ENEMI1.BIN ja te ou/bala/plat alineats.
    l1 = open(L1_BIN, "rb").read()
    assert len(l1) >= 14 * 512, len(l1)
    cells[13] = l1[13 * 512:14 * 512]

    out = b"".join(cells)
    assert len(out) == 16 * 512
    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (16 celes)" % (OUT_BIN, len(out)))


if __name__ == "__main__":
    main()
