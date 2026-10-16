#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI1.BIN (slice 1: walkers kinds 8/15/19, op1 DOS):
- Cela fixa 16x32 px Mode 0 = 8 parells x 2 B x 32 files = 512 B/frame.
- Ordre: kind8 {2,14}, kind15 {3,4}, kind19 {15,16,17,18,19} (SQV ENEMI1.SQV).
- Total 9 x 512 = 4608 B -> C2:0x4000 (banc lliure).
Regenerar: py -3 tools/gen_enemy_frames.py && git add -f assets/bbdata/ENEMI1.BIN
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from sprites import load_sqv_frames  # noqa: E402
from gen_extra_frames import encode_pair, dos_to_cpc_pen  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.BIN")

# (kind, sqv_idx) en ordre de cela
CELLS = [
    (8, 2),               # 0: Peix (dreta; esquerra es flip)
    (15, 3), (15, 4),     # 1, 2: Iaia walk
    (4, 5), (4, 6),       # 3, 4: Policia walk
    (19, 18), (19, 19),   # 5, 6: Ocell fly
    (18, 27), (18, 28),   # 7, 8: Granger walk
    (17, 35), (17, 36),   # 9, 10: Cambrera walk
    (20, 41), (20, 42),   # 11, 12: Rocker walk
]
# Cela 13: composite projectils (Ou r0..12, Bala r13..18, Plat r19..29)

CELL_W, CELL_H = 16, 32


def pack_cell(px, w, h):
    # Centrat horitzontal (parells DOS -> px Mode 0) + peu avall (aliniat terra)
    w_m0 = (w + 1) // 2
    x_shift = (CELL_W - w_m0) // 2
    y_shift = CELL_H - h
    box = [[None] * CELL_W for _ in range(CELL_H)]
    for y in range(h):
        oy = y + y_shift
        if 0 <= oy < CELL_H:
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
                box[oy][xm] = dos_to_cpc_pen.get(val)
    raw = bytearray()
    for y in range(CELL_H):
        for xb in range(CELL_W // 2):
            inv, img = encode_pair(box[y][xb * 2], box[y][xb * 2 + 1])
            raw.append(inv)
            raw.append(img)
    return bytes(raw)


def pack_projectiles_cell(frames):
    box = [[None] * CELL_W for _ in range(CELL_H)]
    projs = [
        (20, 0),   # Ou (kind 19) a files 0..12 (h=13)
        (12, 13),  # Bala (kind 4) a files 13..18 (h=6)
        (40, 19),  # Plat (kind 17) a files 19..29 (h=11)
    ]
    for sqv_idx, row_start in projs:
        w, h, px = frames[sqv_idx]
        w_m0 = (w + 1) // 2
        x_shift = (CELL_W - w_m0) // 2
        for y in range(h):
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
    out = bytearray()
    for kind, idx in CELLS:
        w, h, px = frames[idx]
        assert w <= 32 and h <= 32, (idx, w, h)
        out += pack_cell(px, w, h)
    out += pack_projectiles_cell(frames)
    total_cells = len(CELLS) + 1
    assert len(out) == total_cells * 512, len(out)
    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (%d celes 512 B)" % (OUT_BIN, len(out), total_cells))

    # Preview: renderitza les celes com Mode 0 amb paleta MAG
    try:
        from PIL import Image
        HW = {0x54: (0, 0, 0), 0x44: (0, 0, 128), 0x55: (0, 0, 255), 0x5C: (128, 0, 0),
              0x58: (128, 0, 128), 0x5D: (128, 0, 255), 0x4C: (255, 0, 0), 0x45: (255, 0, 128),
              0x4D: (255, 0, 255), 0x56: (0, 128, 0), 0x46: (0, 128, 128), 0x57: (0, 128, 255),
              0x5E: (128, 128, 0), 0x40: (128, 128, 128), 0x5F: (128, 128, 255),
              0x4E: (255, 128, 0), 0x47: (255, 128, 128), 0x4F: (255, 128, 255),
              0x52: (0, 255, 0), 0x42: (0, 255, 128), 0x53: (0, 255, 255), 0x5A: (128, 255, 0),
              0x59: (128, 255, 128), 0x5B: (128, 255, 255), 0x4A: (255, 255, 0),
              0x43: (255, 255, 128), 0x4B: (255, 255, 255)}
        pal = list(open(os.path.join(PROJ, "assets", "bbdata", "SELECT.PALHW"), "rb").read())
        # Paleta nivell MAG (video.s palette_table)
        pal = [0x4B, 0x47, 0x40, 0x40, 0x44, 0x5E, 0x5E, 0x4C,
               0x57, 0x56, 0x52, 0x54, 0x5F, 0x5C, 0x5C, 0x40]
        RGB = [HW[b] for b in pal]

        def d0(b):
            return ((b >> 7) & 1) | (((b >> 3) & 1) << 1) | (((b >> 5) & 1) << 2) | (((b >> 1) & 1) << 3)

        def d1(b):
            return ((b >> 6) & 1) | (((b >> 2) & 1) << 1) | (((b >> 4) & 1) << 2) | (((b >> 0) & 1) << 3)
        im = Image.new("RGB", (total_cells * CELL_W, CELL_H), (255, 0, 255))
        for c in range(total_cells):
            base = c * 512
            for y in range(CELL_H):
                for xb in range(8):
                    inv = out[base + y * 16 + xb * 2]
                    img = out[base + y * 16 + xb * 2 + 1]
                    # inv=1 -> transparent (magenta); sino pen img
                    m0 = (inv >> 7) & 1
                    m1 = (inv >> 6) & 1
                    c0 = (255, 0, 255) if m0 else RGB[d0(img)]
                    c1 = (255, 0, 255) if m1 else RGB[d1(img)]
                    im.putpixel((c * CELL_W + xb * 2, y), c0)
                    im.putpixel((c * CELL_W + xb * 2 + 1, y), c1)
        im = im.resize((im.size[0] * 4, im.size[1] * 4), Image.NEAREST)
        im.save(os.path.join(HERE, "enemi1_walkers_preview.png"))
        print("preview: tools/enemi1_walkers_preview.png")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
