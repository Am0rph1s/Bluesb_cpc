#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI5.BIN per al nivell 5 (VILLE - Ciutat).

Mateixa cela 16x32 / 512 B que ENEMI1/ENEMI2/ENEMI3/ENEMI4.BIN.
Les imatges surten d'ENEMI5.SQV.

Celes (16):
  0, 1      tipus 4 policia (op2): walk 5/7
  2         tipus 4 policia (op2): shoot/aim 10
  3, 4      tipus 21 cambrera (op10): walk 27/29
  5         tipus 21 cambrera (op10): throw 31
  6, 7      tipus 36 llançador (op10): walk 14/16
  8         tipus 36 llançador (op10): throw 2
  9, 10     tipus 37 patruller (op0): walk 18/20
  11, 12    tipus 39 walker atac (op1): walk 22/24
  13        projectils composite (bala SQV 32 r13..18, ampolla/projectil SQV 4 r0..14, plat SQV 12 r19..29)
  14, 15    tipus 38 gos saltador (op18): walk/jump 34/36

Regenerar:
  py -3 tools/gen_enemy5_frames.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_enemy_frames import pack_cell, CELL_W, CELL_H, encode_pair, dos_to_cpc_pen  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI5.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI5.BIN")

# (cela, frame SQV)
CELLS = [
    (0, 5),    # tipus 4 policia walk A
    (1, 7),    # tipus 4 policia walk B
    (2, 10),   # tipus 4 policia shoot/aim
    (3, 27),   # tipus 21 cambrera walk A
    (4, 29),   # tipus 21 cambrera walk B
    (5, 31),   # tipus 21 cambrera throw
    (6, 14),   # tipus 36 llançador walk A
    (7, 16),   # tipus 36 llançador walk B
    (8, 2),    # tipus 36 llançador throw
    (9, 18),   # tipus 37 patruller walk A
    (10, 20),  # tipus 37 patruller walk B
    (11, 22),  # tipus 39 walker walk A
    (12, 24),  # tipus 39 walker walk B
    (14, 34),  # tipus 38 gos walk/jump A
    (15, 36),  # tipus 38 gos walk/jump B
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


def pack_l5_projectiles(frames):
    box = [[None] * CELL_W for _ in range(CELL_H)]
    # SQV 4: ampolla/projectil tipus 36 (w=32, h=15) a r0..14
    # SQV 32: bala tipus 4 (w=16, h=5) a r13..18
    # SQV 12: plat/projectil tipus 21 (w=32, h=14) a r19..29
    projs = [
        (4, 0),    # ampolla/projectil a files 0..14 (h=15)
        (32, 13),  # Bala (kind 4) a files 13..18 (h=5..6)
        (12, 19),  # Plat a files 19..29 (h=11..14)
    ]
    for sqv_idx, row_start in projs:
        w, h, px = frames[sqv_idx]
        px, w, h = crop_content(px, w, h)
        w_m0 = (w + 1) // 2
        x_shift = (CELL_W - w_m0) // 2
        for y in range(min(h, CELL_H - row_start)):
            oy = row_start + y
            for xm in range(CELL_W):
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
    for y in range(CELL_H):
        for xb in range(CELL_W // 2):
            inv, img = encode_pair(box[y][xb * 2], box[y][xb * 2 + 1])
            raw.append(inv)
            raw.append(img)
    return bytes(raw)


def main():
    frames = load_sqv_frames(SQV)
    print("ENEMI5.SQV: %d frames" % len(frames))

    cells = [bytes(512) for _ in range(16)]
    for cell, idx in CELLS:
        w, h, px = frames[idx]
        px, w, h = crop_content(px, w, h)
        assert w <= 32 and h <= 32, (idx, w, h)
        cells[cell] = pack_cell(px, w, h)

    # Projectils composite a cela 13
    cells[13] = pack_l5_projectiles(frames)

    out = b"".join(cells)
    assert len(out) == 16 * 512
    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (16 celes)" % (OUT_BIN, len(out)))


if __name__ == "__main__":
    main()
