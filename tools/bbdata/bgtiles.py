#!/usr/bin/env python3
"""
bgtiles.py - Extreu els tiles 16x16 de CK1 (tileset de fons) com a subtiles
8x8 en Mode 1 (2 bytes/linia x 8 = 16 bytes), per encaixar amb l'engine.

Us:
  py bgtiles.py --header ../src/tiles.h --count 16
  py bgtiles.py --preview out.png --count 32
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from unsqz import unsqz            # noqa: E402
from ilbm import read_ilbm         # noqa: E402
from mode1 import nearest          # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))
DEF_CK1 = os.path.join(PROJ, "assets", "bbdata", "MAG.CK1")

# Paleta del nivell 0 (level.c) 12-bit -> 8-bit
def level_pal():
    raw = [0x000, 0xc77, 0x989, 0x669, 0x147, 0xfda, 0xdb9, 0xf87,
           0x4af, 0x050, 0x091, 0x111, 0xbcf, 0xa20, 0x630, 0xfff]
    return [(((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17) for v in raw]


TARGETS = [(0, 0, 0), (0, 0, 200), (230, 230, 0), (240, 240, 240)]  # pen 0..3


def load_ck1(path):
    data = unsqz(open(path, 'rb').read())
    w, h, pl, pal, px = read_ilbm(data)
    return px  # px[y][x], 320x200, indexs 0..15


def subtile_mode1(px, tc, tr, qx, qy, lut):
    """8x8 subtile (quadrant qx,qy del tile a grid tc,tr) -> 16 bytes Mode1."""
    out = []
    for j in range(8):
        y = tr * 16 + qy * 8 + j
        b = 0
        for p in range(4):
            x = tc * 16 + qx * 8 + p
            c = lut[px[y][x]] if (0 <= y < len(px) and 0 <= x < len(px[0])) else 0
            b |= ((c >> 1) & 1) << (7 - p)
            b |= (c & 1) << (3 - p)
        # segon byte de la linia (pixels 4..7)
        b2 = 0
        for p in range(4):
            x = tc * 16 + qx * 8 + 4 + p
            c = lut[px[y][x]] if (0 <= y < len(px) and 0 <= x < len(px[0])) else 0
            b2 |= ((c >> 1) & 1) << (7 - p)
            b2 |= (c & 1) << (3 - p)
        out += [b, b2]
    return out


def build(path, count):
    px = load_ck1(path)
    pal = level_pal()
    lut = [nearest(pal[i], TARGETS) for i in range(16)]
    tiles = []
    for n in range(count):
        tr = n // 20
        tc = n % 20
        for qy in range(2):
            for qx in range(2):
                tiles.append(subtile_mode1(px, tc, tr, qx, qy, lut))
    return tiles


def write_header(path, tiles):
    lines = ['#ifndef TILES_H', '#define TILES_H', '', '#include "cpctelera.h"', '',
             '// Subtiles 8x8 Mode1 extrets de MAG.CK1 (index 0 = buit/negre).',
             '#define TILE_COUNT %d' % (len(tiles) + 1), '',
             'static const u8 g_tiles[TILE_COUNT][16] = {',
             '    { 0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0 },']
    for t in tiles:
        lines.append('    {' + ','.join('0x%02X' % b for b in t) + '},')
    lines.append('};')
    lines.append('')
    lines.append('#endif')
    open(path, 'w').write('\n'.join(lines) + '\n')


def preview(path, tiles):
    try:
        from PIL import Image, ImageDraw
        n = len(tiles)
        cols = 16
        cw = 8 * 6
        ch = 8 * 6 + 10
        rows = (n + cols - 1) // cols
        im = Image.new('RGB', (cols * cw, rows * ch), (40, 40, 40))
        dr = ImageDraw.Draw(im)
        # invers del mode1
        def px_of(byte, p):
            return ((byte >> (7 - p)) & 1) * 2 + ((byte >> (3 - p)) & 1)
        for i, t in enumerate(tiles):
            cx = (i % cols) * cw
            cy = (i // cols) * ch
            dr.text((cx + 2, cy), str(i + 1), fill=(255, 255, 0))
            for j in range(8):
                b0 = t[j * 2]
                b1 = t[j * 2 + 1]
                for p in range(8):
                    c = px_of(b0, p) if p < 4 else px_of(b1, p - 4)
                    col = TARGETS[c]
                    for yy in range(6):
                        for xx in range(6):
                            im.putpixel((cx + p * 6 + xx, cy + 10 + j * 6 + yy), col)
        im.save(path)
        print("preview", path)
    except Exception as e:
        print("sense preview:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ck1', default=DEF_CK1)
    ap.add_argument('--count', type=int, default=16)
    ap.add_argument('--header', default=None)
    ap.add_argument('--preview', default=None)
    args = ap.parse_args()
    tiles = build(args.ck1, args.count)
    print("%d subtiles (de %d tiles)" % (len(tiles), args.count))
    if args.header:
        write_header(args.header, tiles)
        print("escrit", args.header)
    if args.preview:
        preview(args.preview, tiles)


if __name__ == "__main__":
    main()
