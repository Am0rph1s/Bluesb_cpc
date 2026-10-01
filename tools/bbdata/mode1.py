#!/usr/bin/env python3
"""
mode1.py - Conversio d'una imatge indexada (320x200) a Mode 1 del CPC
(4 colors, split-nibble, layout de pantalla interleaved del CPC).

Els 4 colors objectiu son RGB (0..255). Es mapeja cada color d'origen al
mes proper, opcionalment amb dithering ordenat 2x2 (Bayer).
"""

BAYER2 = [[0, 2], [3, 1]]  # matriu de dithering 2x2 (0..3)


def _dist2(a, b):
    dr = a[0] - b[0]; dg = a[1] - b[1]; db = a[2] - b[2]
    return dr * dr + dg * dg + db * db


def nearest(c, targets):
    best = 0
    bd = 1 << 30
    for i, t in enumerate(targets):
        d = _dist2(c, t)
        if d < bd:
            bd = d
            best = i
    return best


def two_nearest(c, targets):
    order = sorted(range(len(targets)), key=lambda i: _dist2(c, targets[i]))
    return order[0], order[1]


def build_lut(palette, targets):
    return [nearest(p, targets) for p in palette]


def quantize(pixels, palette, targets, dither=False):
    """Retorna llista de linies amb indexs 0..3."""
    lut = build_lut(palette, targets)
    out = []
    for y, row in enumerate(pixels):
        o = [0] * len(row)
        for x, c in enumerate(row):
            if dither:
                i0, i1 = two_nearest(palette[c], targets)
                # llindar segons el patro Bayer i la distancia relativa
                d0 = _dist2(palette[c], targets[i0])
                d1 = _dist2(palette[c], targets[i1])
                # tria i1 si estem mes a prop de i1 que el llindar
                t = BAYER2[y & 1][x & 1] / 4.0
                o[x] = i1 if (d0 / (d0 + d1 + 1e-6)) > t else i0
            else:
                o[x] = lut[c]
        out.append(o)
    return out


def to_mode1(indices):
    """indices: 200 linies x 320 columnes amb valors 0..3 -> bytearray 0x4000."""
    vram = bytearray(0x4000)
    for y in range(200):
        row = indices[y]
        base = (y & 7) * 0x800 + (y >> 3) * 80
        for xb in range(80):
            b = 0
            for p in range(4):
                c = row[xb * 4 + p]
                b |= ((c >> 1) & 1) << (7 - p)
                b |= (c & 1) << (3 - p)
            vram[base + xb] = b
    return vram


def mode1_to_indices(vram):
    """Invers: VRAM 0x4000 -> 200 linies x 320 indexs 0..3 (per preview/test)."""
    out = []
    for y in range(200):
        base = (y & 7) * 0x800 + (y >> 3) * 80
        line = [0] * 320
        for xb in range(80):
            b = vram[base + xb]
            for p in range(4):
                hi = (b >> (7 - p)) & 1
                lo = (b >> (3 - p)) & 1
                line[xb * 4 + p] = (hi << 1) | lo
        out.append(line)
    return out
