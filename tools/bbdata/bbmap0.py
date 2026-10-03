#!/usr/bin/env python3
"""
bbmap0.py - Genera el nivell 1 (Magasin) en MODE 0 del CPC.

Geometria:
  - Origen: CK1/CK2 (320x200, 16 colors). Es downsample a 160x200 (pixels Mode 0
    son 2x d'amples, aixi es veu igual).
  - Un tile de 16x16 del DOS -> 8x16 pixels Mode 0 = 4 bytes/linia * 16 = 64 B.
  - 256 tiles (128 CK1 + 128 CK2) * 64 B = 16384 B (mateixa mida que Mode 1).
  - MAP (MAG.SQL) = 128x72 entrades, 1 byte per tile de 16x16.
  - TRIG (MAGASIN.BIN) = 256 * 10 B.

Sortida a assets/bbdata/: TILESET0.BIN, MAP0.BIN, TRIG0.BIN (+ preview PNG).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from unsqz import unsqz            # noqa: E402
from ilbm import read_ilbm         # noqa: E402
from mode0 import encode_mode0_byte # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))
BB = os.path.join(PROJ, "assets", "bbdata")

W_TILES = 128
H_TILES = 72


def level_pal():
    raw = [0x000, 0xc77, 0x989, 0x669, 0x147, 0xfda, 0xdb9, 0xf87,
           0x4af, 0x050, 0x091, 0x111, 0xbcf, 0xa20, 0x630, 0xfff]
    return [(((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17) for v in raw]


def load_ck(name):
    d = unsqz(open(os.path.join(BB, name), 'rb').read())
    w, h, pl, pal, px = read_ilbm(d)
    # downsample 320 -> 160
    return [row[0::2] for row in px]


def tile_bytes(px, tc, tr):
    """Tile 8x16 Mode 0 a (tc*8, tr*16) -> 64 bytes (top subtile + bottom subtile)."""
    out = bytearray()
    for j in range(16):
        y = tr * 16 + j
        for xb in range(4):
            left = px[y][tc * 8 + xb * 2] & 0x0F
            right = px[y][tc * 8 + xb * 2 + 1] & 0x0F
            out.append(encode_mode0_byte(left, right))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default='MAG', help='MAG/PRISON/VILLE/EGOU/ENT/CONCERT')
    ap.add_argument('--out', default=None)
    ap.add_argument('--preview', default=None)
    args = ap.parse_args()
    p = args.prefix

    ck = [load_ck('%s.CK1' % p), load_ck('%s.CK2' % p)]
    tileset = bytearray()
    for h in range(2):
        px = ck[h]
        for num in range(128):
            tr = num // 20
            tc = num % 20
            tileset += tile_bytes(px, tc, tr)
    out = args.out or os.path.join(BB, 'TILESET0.BIN')
    open(out, 'wb').write(tileset)
    print("TILESET0.BIN", len(tileset))

    sql = unsqz(open(os.path.join(BB, '%s.SQL' % p), 'rb').read())
    m = sql[:W_TILES * H_TILES]
    open(os.path.join(BB, 'MAP0.BIN'), 'wb').write(m)
    print("MAP0.BIN", len(m), "(sql", len(sql), ")")

    trigf = os.path.join(BB, '%s.BIN' % ('MAGASIN' if p == 'MAG' else p))
    if os.path.exists(trigf):
        open(os.path.join(BB, 'TRIG0.BIN'), 'wb').write(open(trigf, 'rb').read())
        print("TRIG0.BIN", os.path.getsize(trigf))

    if args.preview:
        from PIL import Image
        pal = level_pal()
        W = W_TILES * 8
        H = H_TILES * 16
        im = Image.new('RGB', (W, H))
        pxo = im.load()
        for my in range(H_TILES):
            for mx in range(W_TILES):
                t = m[my * W_TILES + mx]
                h = 0 if t < 128 else 1
                num = t % 128
                src = ck[h]
                tr = num // 20
                tc = num % 20
                for j in range(16):
                    for i in range(8):
                        c = src[tr * 16 + j][tc * 8 + i]
                        pxo[mx * 8 + i, my * 16 + j] = tuple(pal[c])
        # escala a la meitat per veure-ho sencer
        im.resize((W // 4, H // 4), Image.NEAREST).save(args.preview)
        print("preview", args.preview, "(%dx%d)" % (W, H))


if __name__ == '__main__':
    main()
