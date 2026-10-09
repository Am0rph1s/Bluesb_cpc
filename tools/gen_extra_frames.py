#!/usr/bin/env python3
"""Genera assets/bbdata/EXTRA.BIN: frames extra al Banc 7 (0x79A0).
- DOS 39 (SPRITE.SQV #39, 32x31): pose braç amunt (globus/paraigua), 480 B.
- BOX (tile 19, 8x16 Mode 0 = 4B x 16): caixa volant opaca [inv=0,img]
  64 parells = 128 B.
Total 608 B (lliures 1120 -> en queden 512). Format = PFRAMES (blitter ASM).
Regenerar: py -3 tools/gen_extra_frames.py && git add -f assets/bbdata/EXTRA.BIN
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from sprites import load_sqv_frames  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "SPRITE.SQV")
TILESET = os.path.join(PROJ, "assets", "bbdata", "TILESET0.BIN")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "EXTRA.BIN")

dos_to_cpc_pen = {
    0: None, 1: 1, 2: 12, 3: 11, 4: 4, 5: 1, 6: 1, 7: 1,
    8: 0, 9: 9, 10: 10, 11: 11, 12: 0, 13: 13, 14: 13, 15: 0,
}


def encode_pair(pen0, pen1):
    mask = 0
    img = 0
    if pen0 is not None:
        mask |= 0xAA
        p = pen0 & 0x0F
        img |= ((p & 1) << 7) | (((p >> 2) & 1) << 5) | (((p >> 1) & 1) << 3) | (((p >> 3) & 1) << 1)
    if pen1 is not None:
        mask |= 0x55
        p = pen1 & 0x0F
        img |= ((p & 1) << 6) | (((p >> 2) & 1) << 4) | (((p >> 1) & 1) << 2) | ((p >> 3) & 1)
    return (~mask) & 0xFF, img & mask


def pack_frame(idx):
    frames = load_sqv_frames(SQV)
    w, h, px = frames[idx]
    w_m0 = 16
    x_shift = (w_m0 - ((w + 1) // 2)) // 2
    y_shift = 30 - h
    box = [[None] * 16 for _ in range(30)]
    for y in range(h):
        out_y = y + y_shift
        if 0 <= out_y < 30:
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
                box[out_y][xm] = dos_to_cpc_pen.get(val)
    raw = bytearray()
    for y in range(30):
        for xb in range(8):
            inv_mask, img = encode_pair(box[y][xb * 2], box[y][xb * 2 + 1])
            raw.append(inv_mask)
            raw.append(img)
    return bytes(raw)


def pack_box(tile_idx):
    ts = open(TILESET, "rb").read()
    blk = ts[tile_idx * 64:(tile_idx + 1) * 64]
    assert len(blk) == 64
    raw = bytearray()
    for b in blk:
        raw.append(0x00)  # inv_mask 0 = opac
        raw.append(b)
    return bytes(raw)


def main():
    dos39 = pack_frame(39)
    assert len(dos39) == 480, len(dos39)
    box = pack_box(19)
    assert len(box) == 128, len(box)
    open(OUT_BIN, "wb").write(dos39 + box)
    print("escrit %s: %d bytes (DOS39 480 + BOX 128)" % (OUT_BIN, 480 + 128))


if __name__ == "__main__":
    main()
