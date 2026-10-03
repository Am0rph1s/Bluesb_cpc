#!/usr/bin/env python3
"""
mo0img.py - Converteix una imatge ILBM/SQZ del joc (320x200, 16 colors) a
Mode 0 del CPC (160x200, pixels 2x d'amples) i en fa un preview.

Us:
  py mo0img.py --ck1 ../../assets/bbdata/MAG.CK1 --preview out.png
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from unsqz import unsqz        # noqa: E402
from ilbm import read_ilbm     # noqa: E402
from mode0 import to_mode0, mode0_to_indices  # noqa: E402

PROJ = os.path.dirname(os.path.dirname(HERE))


def load(path):
    data = open(path, 'rb').read()
    if data[:4] != b'FORM':
        data = unsqz(data)
    return read_ilbm(data)   # (w, h, planes, palette, pixels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ck1', default=os.path.join(PROJ, 'assets', 'bbdata', 'MAG.CK1'))
    ap.add_argument('--preview', default='mo0_preview.png')
    args = ap.parse_args()

    w, h, planes, palette, px = load(args.ck1)
    print("origen %dx%d, %d planes" % (w, h, planes))

    # downsample 320 -> 160 (pixels 2x d'amples en Mode 0)
    px160 = [row[0::2] for row in px[:200]]
    vram = to_mode0(px160)
    print("VRAM Mode 0:", len(vram), "bytes")

    # preview: original 320 + mode0 160 (escalat x2 horitzontal)
    try:
        from PIL import Image
        # original
        imo = Image.new('RGB', (w, min(h, 200)))
        for y in range(min(h, 200)):
            for x in range(w):
                imo.putpixel((x, y), tuple(palette[px[y][x]]))
        # mode 0 re-render
        idx = mode0_to_indices(vram)
        imm = Image.new('RGB', (160, 200))
        for y in range(200):
            for x in range(160):
                c = idx[y][x]
                imm.putpixel((x, y), tuple(palette[c]))
        imm2 = imm.resize((320, 200), Image.NEAREST)
        out = Image.new('RGB', (320, 410), (0, 0, 0))
        out.paste(imo, (0, 0))
        out.paste(imm2, (0, 205))
        out.save(args.preview)
        print("preview", args.preview)
    except Exception as e:
        print("sense preview:", e)


if __name__ == '__main__':
    main()
