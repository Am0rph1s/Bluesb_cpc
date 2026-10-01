#!/usr/bin/env python3
"""
bbconvert.py - Converteix grafics de Blues Brothers (DOS/Amiga) a Mode 1 del CPC.

Us:
  py bbconvert.py <input> [-o out.bin] [--colors "0,0,0;255,0,0;0,255,0;255,255,255"]
                   [--dither] [--preview out.png]

Input pot ser: .sqz (SQZ comprimit), .lbm/.iff (IFF ILBM) o .png (amb Pillow).
Sortida: fitxer binari de 0x4000 bytes (VRAM Mode 1) llest per carregar a 0xC000.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ilbm import read_ilbm          # noqa: E402
from unsqz import unsqz            # noqa: E402
from mode1 import quantize, to_mode1  # noqa: E402


def load_image(path):
    data = open(path, 'rb').read()
    if data[:4] != b'FORM' and not path.lower().endswith('.png'):
        try:
            data = unsqz(data)
        except Exception:
            pass
    if data[:4] == b'FORM':
        w, h, planes, palette, pixels = read_ilbm(data)
        return w, h, palette, pixels
    # prova PNG via Pillow
    try:
        from PIL import Image
        im = Image.open(path).convert('P')
        pal = im.getpalette()
        palette = [(pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]) for i in range(256)]
        pixels = [list(im.crop((0, y, im.width, y + 1)).getdata()) for y in range(im.height)]
        return im.width, im.height, palette, pixels
    except Exception as e:
        raise SystemExit("Format no reconegut: %s (%s)" % (path, e))


def parse_colors(s):
    cols = []
    for part in s.split(';'):
        r, g, b = [int(v) for v in part.split(',')]
        cols.append((r, g, b))
    if len(cols) != 4:
        raise SystemExit("Calen exactament 4 colors (separats per ';')")
    return cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('-o', '--output', default=None)
    ap.add_argument('--colors', default='0,0,0;255,0,0;0,200,0;255,255,255')
    ap.add_argument('--dither', action='store_true')
    ap.add_argument('--preview', default=None)
    args = ap.parse_args()

    w, h, palette, pixels = load_image(args.input)
    print("Imatge %dx%d, %d colors de paleta" % (w, h, len(palette)))
    if w != 320 or h < 200:
        raise SystemExit("Cal una imatge 320x200 (o mes alta)")

    targets = parse_colors(args.colors)
    idx = quantize(pixels[:200], palette, targets, dither=args.dither)
    vram = to_mode1(idx)

    out = args.output or (os.path.splitext(args.input)[0] + '.m1.bin')
    open(out, 'wb').write(vram)
    print("Escrit", out, len(vram), "bytes  (VRAM Mode 1, carregar a 0xC000)")

    if args.preview:
        try:
            from PIL import Image
            im = Image.new('RGB', (320, 200))
            px = im.load()
            for y in range(200):
                for x in range(320):
                    px[x, y] = targets[idx[y][x]]
            im.save(args.preview)
            print("Preview", args.preview)
        except Exception as e:
            print("Sense preview:", e)


if __name__ == "__main__":
    main()
