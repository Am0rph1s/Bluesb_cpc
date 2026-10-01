#!/usr/bin/env python3
"""Test del pipeline amb un ILBM sintetic (sense fitxers del joc)."""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ilbm import read_ilbm            # noqa: E402
from mode1 import quantize, to_mode1, mode1_to_indices, build_lut  # noqa: E402


def make_ilbm(w, h, planes, palette, pixels):
    row_bytes = ((w + 15) // 16) * 2 * planes
    plane_size = row_bytes // planes
    body = bytearray()
    for y in range(h):
        row = bytearray(row_bytes)
        for xb in range(plane_size):
            for b in range(8):
                x = xb * 8 + b
                if x >= w:
                    break
                c = pixels[y][x]
                for p in range(planes):
                    if c & (1 << p):
                        row[p * plane_size + xb] |= (1 << (7 - b))
        i = 0
        while i < len(row):
            n = min(128, len(row) - i)
            body.append(n - 1)
            body += row[i:i + n]
            i += n
    bmhd = struct.pack('>HHhhBBBBHBBhh', w, h, 0, 0, planes, 0, 1, 0, 0, 0, 0, w, h)
    cmap = b''.join(bytes(rgb) for rgb in palette)
    inner = b'ILBM' + b'BMHD' + struct.pack('>I', len(bmhd)) + bmhd
    inner += b'CMAP' + struct.pack('>I', len(cmap)) + cmap
    inner += b'BODY' + struct.pack('>I', len(body)) + bytes(body)
    return b'FORM' + struct.pack('>I', len(inner)) + inner


def main():
    W, H = 320, 200
    planes = 4
    # paleta de 16 colors sintetica
    palette = [(i * 17, (15 - i) * 17, (i * 7) % 256) for i in range(16)]
    # imatge: franges verticals + gradient horitzontal
    pixels = [[(x // 16 + y // 16) & 15 for x in range(W)] for y in range(H)]

    raw = make_ilbm(W, H, planes, palette, pixels)
    w, h, pl, pal, px = read_ilbm(raw)
    assert (w, h, pl) == (W, H, planes), (w, h, pl)
    assert pal == palette, "paleta CMAP incorrecta"
    # comprova que el decodificat planar == original
    ok = all(px[y][x] == pixels[y][x] for y in range(H) for x in range(W))
    print("ILBM decode OK:", ok, " planes:", pl, " mida CMAP:", len(pal))

    # conversio a Mode 1 amb 4 colors objectiu
    targets = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 255)]
    idx = quantize(px, pal, targets, dither=False)
    vram = to_mode1(idx)
    assert len(vram) == 0x4000

    # invers i comprovacio
    back = mode1_to_indices(vram)
    lut = build_lut(pal, targets)
    bad = 0
    for y in range(H):
        for x in range(W):
            if back[y][x] != lut[px[y][x]]:
                bad += 1
    print("Mode1 round-trip errors:", bad, " VRAM:", len(vram), "bytes")
    print("OK" if (ok and bad == 0) else "FALLADA")


if __name__ == "__main__":
    main()
