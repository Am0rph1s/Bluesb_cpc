#!/usr/bin/env python3
"""
mode0.py - Conversio a Mode 0 del CPC (160x200, 16 colors, 2 pixels/byte).

En Mode 0 cada byte conte 2 pixels: nibble alt = pixel esquerre, nibble baix =
pixel dret. La pantalla es 80 bytes/linia x 200 = 16000 bytes, amb el mateix
layout interleaved que Mode 1 ((y&7)*0x800 + (y>>3)*80).
"""


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


def build_lut(palette, targets):
    return [nearest(p, targets) for p in palette]


def quantize(pixels, palette, targets):
    """pixels: llista de linies amb indexs de palette -> indexs 0..15 nous."""
    lut = build_lut(palette, targets)
    return [[lut[c] for c in row] for row in pixels]


def downsample2(row):
    """320 -> 160: agafa el pixel esquerre de cada parella (preserva el look
    perque els pixels de Mode 0 son 2x d'amples)."""
    return row[0::2]


def encode_mode0_byte(p0, p1):
    """Codifica 2 pixels (0..15) al format hardware de Mode 0 del CPC (interleaved):
    Bit 7: p0_0 | Bit 6: p1_0 | Bit 5: p0_2 | Bit 4: p1_2
    Bit 3: p0_1 | Bit 2: p1_1 | Bit 1: p0_3 | Bit 0: p1_3
    """
    p0 = int(p0) & 0x0F
    p1 = int(p1) & 0x0F
    return (
        ((p0 & 1) << 7) |
        ((p1 & 1) << 6) |
        (((p0 >> 2) & 1) << 5) |
        (((p1 >> 2) & 1) << 4) |
        (((p0 >> 1) & 1) << 3) |
        (((p1 >> 1) & 1) << 2) |
        (((p0 >> 3) & 1) << 1) |
        ((p1 >> 3) & 1)
    )


def decode_mode0_byte(b):
    """Descodifica un byte de Mode 0 del CPC als seus 2 pixels (p0, p1)."""
    p0_0 = (b >> 7) & 1
    p1_0 = (b >> 6) & 1
    p0_2 = (b >> 5) & 1
    p1_2 = (b >> 4) & 1
    p0_1 = (b >> 3) & 1
    p1_1 = (b >> 2) & 1
    p0_3 = (b >> 1) & 1
    p1_3 = b & 1
    p0 = p0_0 | (p0_1 << 1) | (p0_2 << 2) | (p0_3 << 3)
    p1 = p1_0 | (p1_1 << 1) | (p1_2 << 2) | (p1_3 << 3)
    return p0, p1


def to_mode0(indices):
    """indices: 200 linies x 160 columnes (0..15) -> bytearray 0x4000 (VRAM)."""
    vram = bytearray(0x4000)
    for y in range(200):
        row = indices[y]
        base = (y & 7) * 0x800 + (y >> 3) * 80
        for xb in range(80):
            left = row[xb * 2] & 0x0F
            right = row[xb * 2 + 1] & 0x0F
            vram[base + xb] = encode_mode0_byte(left, right)
    return vram


def mode0_to_indices(vram):
    """Invers: VRAM -> 200 linies x 160 indexs (per preview/test)."""
    out = []
    for y in range(200):
        base = (y & 7) * 0x800 + (y >> 3) * 80
        line = [0] * 160
        for xb in range(80):
            b = vram[base + xb]
            p0, p1 = decode_mode0_byte(b)
            line[xb * 2] = p0
            line[xb * 2 + 1] = p1
        out.append(line)
    return out


def tile_to_mode0(px, tx, ty, tw=8, th=8, transparent=0):
    """Extreu un tile de tw x th pixels (a la graella de 160 ample) i el
    retorna com th linies de (tw+1)//2 bytes en Mode 0. Transparent -> -1
    (marcador per mascara)."""
    out = []
    for j in range(th):
        y = ty * th + j
        row = []
        for xb in range((tw + 1) // 2):
            left = 0
            right = 0
            for k in range(2):
                x = tx * tw + xb * 2 + k
                c = px[y][x] if (0 <= y < len(px) and 0 <= x < len(px[0])) else transparent
                if k == 0:
                    left = c & 0x0F
                else:
                    right = c & 0x0F
            row.append(encode_mode0_byte(left, right))
        out.append(row)
    return out
