#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI2.BIN per al nivell 2 (ENT).

Mateixa cela 16x32 / 512 B que ENEMI1.BIN. Les imatges surten de
ENEMI2.SQV (35 frames). Els indexs de frame SON els del DOS: es treuen de
`animframes_059d` (staticres.c), on el frame del nivell = index - SPRITES_COUNT
(146). Vegeu tools/dump_level_sprites.py per veure les tires per tipus.

Celes (16):
  0,1    tipus 11 walk (op1, científic)           frames 0,1
  2,3    tipus 12 walk (op1)                      frames 6,8
  4,5    tipus 13 walk (op7, llança)              frames 12,14
  6      tipus 13 llançament                      frame 17
  7,8    tipus 14 walk (op10)                     frames 21,23
  9      tipus 14 llançament                      frame 26
  10,11  tipus 21 walk (op10)                     frames 28,29
  12     tipus 21 llançament                      frame 31
  13     projectils (plat de kind 9, files 19..31)
  14,15  lliures

El tipus 22 (premsa hidràulica, frame 33) no hi cap: és un objecte de 37 px
(op11) i va en un subsistema propi.

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

# (cela, frame SQV)
CELLS = [
    (0, 0),    # tipus 11 walk A (científic dret)
    (1, 1),    # tipus 11 walk B (científic pas)
    (2, 6),    # tipus 12 walk A
    (3, 8),    # tipus 12 walk B
    (4, 12),   # tipus 13 walk A
    (5, 14),   # tipus 13 walk B
    (6, 17),   # tipus 13 llançament
    (7, 21),   # tipus 14 walk A
    (8, 23),   # tipus 14 walk B
    (9, 26),   # tipus 14 llançament
    (10, 28),  # tipus 21 walk A (frame 28 dret)
    (11, 29),  # tipus 21 walk B (frame 29 pas)
    (12, 31),  # tipus 21 llançament
]


def pack_projectiles_cell(frames):
    """Empaqueta els 3 projectils 1:1 de DOS del Nivell 2 a la cela 13 (512 B Mode 0):
      - files  0..6  (h=7):  frame 32 SQV (1:1 DOS frame 178 - tipus 21 noi gorra)
      - files  7..15 (h=9):  frame 18 SQV (1:1 DOS frame 164 - tipus 13 mecànic)
      - files 16..26 (h=11): frame 34 SQV (1:1 DOS frame 180 - tipus 14 obrer)
      - files 27..31: lliures (zeros)
    """
    from gen_extra_frames import encode_pair, dos_to_cpc_pen
    box = [[None] * 16 for _ in range(32)]
    projs = [
        (32, 0),   # 1:1 DOS frame 178 (SQV 32, tipus 21) a files 0..6 (h=7)
        (18, 7),   # 1:1 DOS frame 164 (SQV 18, tipus 13) a files 7..15 (h=9)
        (34, 16),  # 1:1 DOS frame 180 (SQV 34, tipus 14) a files 16..26 (h=11)
    ]
    for sqv_idx, row_start in projs:
        w, h, px = frames[sqv_idx]
        w_m0 = (w + 1) // 2
        x_shift = (16 - w_m0) // 2
        for y in range(h):
            oy = row_start + y
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
                if val != 0:
                    box[oy][xm] = dos_to_cpc_pen.get(val)
    raw = bytearray()
    for y in range(32):
        for xb in range(8):
            inv, img = encode_pair(box[y][xb * 2], box[y][xb * 2 + 1])
            raw.append(inv)
            raw.append(img)
    return bytes(raw)


def crop_content(px, w, h):
    """Retalla el frame al bbox del contingut real (la tela del SQV pot ser
    mes ampla que el dibuix: a L2 hi ha frames de 48 px amb el personatge
    ocupant 32-33 px) i l'ajusta a la cel·la de 16x32:
      - ample: 33 -> 32 px, es perd la columna DRETA
      - alçada: 33 -> 32 px, es perd la fila de DALT (els peus es queden al
        terra, com al DOS, on el sprite s'ancla pel peu)
    """
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
    print("ENEMI2.SQV: %d frames" % len(frames))

    cells = [bytes(512) for _ in range(16)]
    for cell, idx in CELLS:
        w, h, px = frames[idx]
        px, w, h = crop_content(px, w, h)
        assert w <= 32 and h <= 32, (idx, w, h)
        cells[cell] = pack_cell(px, w, h)

    # Projectils: la cela 13 conté els projectils reals de L2 (dard, clau, pot d'oli)
    cells[13] = pack_projectiles_cell(frames)

    out = b"".join(cells)
    assert len(out) == 16 * 512
    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (16 celes)" % (OUT_BIN, len(out)))


if __name__ == "__main__":
    main()
