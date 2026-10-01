#!/usr/bin/env python3
"""
bbmap.py - Genera els binaris del nivell real (magasin) per al CPC:
  TILESET.BIN : 1024 subtiles 8x8 Mode1 (half*512 + tile*4 + quad) -> 16384 B
  MAP.BIN     : mapa descomprimit (MAG.SQL) retallat a W*H tiles       -> W*H
  TRIG.BIN    : taula de triggers (MAGASIN.BIN, 256 x 10 bytes)        -> 2560 B
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from unsqz import unsqz            # noqa: E402
from ilbm import read_ilbm         # noqa: E402
from mode1 import nearest          # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))
BB = os.path.join(PROJ, "assets", "bbdata")

W_TILES = 128
H_TILES = 72

TARGETS = [(0, 0, 0), (0, 0, 200), (230, 230, 0), (240, 240, 240)]


def level_pal():
    raw = [0x000, 0xc77, 0x989, 0x669, 0x147, 0xfda, 0xdb9, 0xf87,
           0x4af, 0x050, 0x091, 0x111, 0xbcf, 0xa20, 0x630, 0xfff]
    return [(((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17) for v in raw]


def load_ck(name):
    d = unsqz(open(os.path.join(BB, name), 'rb').read())
    w, h, pl, pal, px = read_ilbm(d)
    return px


def subtile(px, tr, tc, qy, qx, lut):
    out = []
    for j in range(8):
        y = tr * 16 + qy * 8 + j
        byte = 0
        for half in range(2):
            b = 0
            for p in range(4):
                x = tc * 16 + qx * 8 + half * 4 + p
                c = lut[px[y][x]] if (0 <= y < len(px) and 0 <= x < len(px[0])) else 0
                b |= ((c >> 1) & 1) << (7 - p)
                b |= (c & 1) << (3 - p)
            out.append(b)
    return out


def main():
    pal = level_pal()
    lut = [nearest(pal[i], TARGETS) for i in range(16)]
    ck = [load_ck("MAG.CK1"), load_ck("MAG.CK2")]

    tileset = bytearray()
    for h in range(2):
        px = ck[h]
        for num in range(128):
            tr = num // 20
            tc = num % 20
            for qy in range(2):
                for qx in range(2):
                    tileset += bytes(subtile(px, tr, tc, qy, qx, lut))
    open(os.path.join(BB, "TILESET.BIN"), 'wb').write(tileset)
    print("TILESET.BIN", len(tileset))

    sql = unsqz(open(os.path.join(BB, "MAG.SQL"), 'rb').read())
    m = sql[:W_TILES * H_TILES]
    open(os.path.join(BB, "MAP.BIN"), 'wb').write(m)
    print("MAP.BIN", len(m), " (sql descomprimit", len(sql), ")")

    trig = open(os.path.join(BB, "MAGASIN.BIN"), 'rb').read()
    open(os.path.join(BB, "TRIG.BIN"), 'wb').write(trig)
    print("TRIG.BIN", len(trig))


if __name__ == "__main__":
    main()
