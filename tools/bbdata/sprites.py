#!/usr/bin/env python3
"""
sprites.py - Decodificador d'sprites .sqv de Blues Brothers (DOS).
Format: unsqz -> [count u16 LE] [ (h u16 LE, w u16 LE, planar h*w*4/8) ... ]
Planar de 4 bitplanes (16 colors). reverse=True -> pla 0 = bit menys significatiu.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unsqz import unsqz  # noqa: E402


def decode_sqv(data):
    count = int.from_bytes(data[0:2], 'little')
    ptr = 6
    frames = []
    for _ in range(count):
        h = int.from_bytes(data[ptr - 4:ptr - 2], 'little')
        w = int.from_bytes(data[ptr - 2:ptr], 'little')
        if w == 0 or h == 0:
            break
        size = (w * h * 4 + 7) // 8
        frames.append((w, h, data[ptr:ptr + size]))
        ptr += size + 4
    return frames


def decode_planar(planar, w, h, planes=4, reverse=True):
    wb = (w + 7) // 8
    plane_size = wb * h
    px = [[0] * w for _ in range(h)]
    for y in range(h):
        for xb in range(wb):
            for b in range(8):
                x = xb * 8 + b
                if x >= w:
                    break
                c = 0
                for p in range(planes):
                    off = p * plane_size + y * wb + xb
                    if off < len(planar) and (planar[off] & (1 << (7 - b))):
                        c |= 1 << (p if reverse else (planes - 1 - p))
                px[y][x] = c
    return px


def load_sqv_frames(path, reverse=False):
    data = unsqz(open(path, 'rb').read())
    raw = decode_sqv(data)
    return [(w, h, decode_planar(pl, w, h, 4, reverse)) for (w, h, pl) in raw]


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Projects\bluesb_cpc\assets\bbdata\SPRITE.SQV"
    frames = load_sqv_frames(path)
    print("frames:", len(frames))
    for i, (w, h, px) in enumerate(frames[:40]):
        print("  %2d: %dx%d" % (i, w, h))
