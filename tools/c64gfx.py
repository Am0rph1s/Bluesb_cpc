#!/usr/bin/env python3
"""
c64gfx.py - Visualitza dades C64 (VIC-II) com a imatges per identificar grafics.

Modes:
  bitmap <file> <off> [--bmp-off N] [--bg N] [--cr N] [-o out.png] [--hires]
      Render 320x200. Per defecte screen=file[off:off+1000], bitmap a bmp_off
      (per defecte off+1000) de 8000 bytes. --hires = bitmap monocrom (1 bit/px).
  chars <file> <off> <count> [-o out.png] [--fg N] [--bg N]
      Render un joc de caracters 8x8 (multicolor es deixa en blanc).
  sprite <file> <off> <count> [-o out.png] [--multicolor]
      Render sprites 24x21.
  tiles <file> <off> <count> [-o out.png] [--mc] [--cols N]
      Render blocs 8x8 (count) com a contacte.
"""
import argparse
import os
import sys

# Paleta C64 (Pepto)
PAL = [
    (0, 0, 0), (255, 255, 255), (136, 0, 0), (170, 255, 238),
    (204, 68, 204), (0, 204, 85), (0, 0, 170), (238, 238, 119),
    (221, 136, 85), (102, 68, 0), (255, 119, 119), (51, 51, 51),
    (119, 119, 119), (170, 255, 102), (0, 136, 255), (187, 187, 187),
]


def load(path):
    d = open(path, 'rb').read()
    return d


def render_bitmap(data, off, bmp_off, bg, cr, hires, out):
    from PIL import Image
    screen = data[off:off + 1000]
    bitmap = data[bmp_off:bmp_off + 8000]
    if len(bitmap) < 8000:
        raise SystemExit("no hi ha prou bytes per al bitmap (cal 8000)")
    # color RAM desconegut: si no es dona, es fa servir 11 (gris clar)
    if cr is None:
        cr = 11
    im = Image.new('RGB', (320, 200))
    px = im.load()
    for cy in range(25):
        for cx in range(40):
            sc = screen[cy * 40 + cx]
            hi = (sc >> 4) & 0x0F
            lo = sc & 0x0F
            for j in range(8):
                b = bitmap[(cy * 8 + j) * 40 + cx]
                for p in range(4):
                    if hires:
                        bits = (b >> (7 - p * 2)) & 0x03
                        col = PAL[hi] if (bits & 0x02) else PAL[lo]
                        # hires: 1 bit -> foreground=hi? Aproximacio
                        col = PAL[hi] if ((b >> (7 - p)) & 1) else PAL[bg]
                        x = cx * 8 + p
                    else:
                        bits = (b >> (6 - p * 2)) & 0x03
                        c = bg if bits == 0 else (hi if bits == 1 else (lo if bits == 2 else cr))
                        col = PAL[c]
                        x = cx * 8 + p * 2
                    y = cy * 8 + j
                    px[x, y] = col
                    if not hires:
                        px[x + 1, y] = col
    im.save(out)
    print("escrit", out)


def render_chars(data, off, count, out, fg=1, bg=0):
    """Joc de caracters: count blocs de 8 bytes. Asumeix 1bpp (hires)."""
    from PIL import Image, ImageDraw
    cols = 16
    cw, ch = 8 * 3, 8 * 3 + 12
    rows = (count + cols - 1) // cols
    im = Image.new('RGB', (cols * cw, rows * ch), (30, 30, 30))
    dr = ImageDraw.Draw(im)
    for i in range(count):
        base = off + i * 8
        if base + 8 > len(data):
            break
        ox = (i % cols) * cw
        oy = (i // cols) * ch
        dr.text((ox + 2, oy), hex(i), fill=(255, 255, 0))
        for j in range(8):
            b = data[base + j]
            for p in range(8):
                if (b >> (7 - p)) & 1:
                    for yy in range(3):
                        for xx in range(3):
                            im.putpixel((ox + p * 3 + xx, oy + 12 + j * 3 + yy), PAL[fg])
    im.save(out)
    print("escrit", out)


def render_tiles(data, off, count, out, mc, cols=16, bg=0, cr=11, fg=1):
    from PIL import Image, ImageDraw
    cw, ch = 8 * 4, 8 * 4 + 12
    rows = (count + cols - 1) // cols
    im = Image.new('RGB', (cols * cw, rows * ch), (30, 30, 30))
    dr = ImageDraw.Draw(im)
    step = 8
    for i in range(count):
        base = off + i * step
        if base + step > len(data):
            break
        ox = (i % cols) * cw
        oy = (i // cols) * ch
        dr.text((ox + 2, oy), hex(i), fill=(255, 255, 0))
        for j in range(8):
            b = data[base + j]
            for p in range(4 if mc else 8):
                if mc:
                    bits = (b >> (6 - p * 2)) & 0x03
                    col = PAL[bg] if bits == 0 else (PAL[fg] if bits == 1 else (PAL[
                        (b >> 4) & 0x0F] if False else PAL[7]))
                    col = PAL[bg] if bits == 0 else (PAL[fg] if bits == 1 else PAL[7])
                    xs = p * 2
                    w = 2
                else:
                    if not ((b >> (7 - p)) & 1):
                        continue
                    col = PAL[fg]
                    xs = p
                    w = 1
                for yy in range(4):
                    for xx in range(w * 4):
                        px_ = ox + xs * 4 + xx
                        py_ = oy + 12 + j * 4 + yy
                        if 0 <= px_ < im.width and 0 <= py_ < im.height:
                            im.putpixel((px_, py_), col)
    im.save(out)
    print("escrit", out)


def render_sprites(data, off, count, out, mc, cols=8):
    from PIL import Image, ImageDraw
    cw, ch = 24 * 2, 21 * 2 + 12
    rows = (count + cols - 1) // cols
    im = Image.new('RGB', (cols * cw, rows * ch), (30, 30, 30))
    dr = ImageDraw.Draw(im)
    for i in range(count):
        base = off + i * 64
        if base + 64 > len(data):
            break
        ox = (i % cols) * cw
        oy = (i // cols) * ch
        dr.text((ox + 2, oy), str(i), fill=(255, 255, 0))
        for j in range(21):
            b0 = data[base + j * 3]
            b1 = data[base + j * 3 + 1]
            b2 = data[base + j * 3 + 2]
            word = (b0 << 16) | (b1 << 8) | b2
            for p in range(12 if mc else 24):
                if mc:
                    bits = (word >> (22 - p * 2)) & 0x03
                    col = PAL[0] if bits == 0 else (PAL[1] if bits == 1 else PAL[7])
                    xs = p * 2
                    w = 2
                else:
                    if not ((word >> (23 - p)) & 1):
                        continue
                    col = PAL[1]
                    xs = p
                    w = 1
                for yy in range(2):
                    for xx in range(w * 2):
                        px_ = ox + xs * 2 + xx
                        py_ = oy + 12 + j * 2 + yy
                        if 0 <= px_ < im.width and 0 <= py_ < im.height:
                            im.putpixel((px_, py_), col)
    im.save(out)
    print("escrit", out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('bitmap')
    p.add_argument('file')
    p.add_argument('off', type=lambda s: int(s, 0))
    p.add_argument('--bmp-off', type=lambda s: int(s, 0), default=None)
    p.add_argument('--bg', type=int, default=0)
    p.add_argument('--cr', type=int, default=None)
    p.add_argument('--hires', action='store_true')
    p.add_argument('-o', default='c64_bitmap.png')
    p.set_defaults(func=lambda a: render_bitmap(
        load(a.file), a.off, a.bmp_off if a.bmp_off is not None else a.off + 1000,
        a.bg, a.cr, a.hires, a.o))

    p = sub.add_parser('chars')
    p.add_argument('file')
    p.add_argument('off', type=lambda s: int(s, 0))
    p.add_argument('count', type=int, nargs='?', default=256)
    p.add_argument('--fg', type=int, default=1)
    p.add_argument('--bg', type=int, default=0)
    p.add_argument('-o', default='c64_chars.png')
    p.set_defaults(func=lambda a: render_chars(load(a.file), a.off, a.count, a.o, a.fg, a.bg))

    p = sub.add_parser('tiles')
    p.add_argument('file')
    p.add_argument('off', type=lambda s: int(s, 0))
    p.add_argument('count', type=int)
    p.add_argument('--mc', action='store_true')
    p.add_argument('--cols', type=int, default=16)
    p.add_argument('--fg', type=int, default=1)
    p.add_argument('--bg', type=int, default=0)
    p.add_argument('-o', default='c64_tiles.png')
    p.set_defaults(func=lambda a: render_tiles(load(a.file), a.off, a.count, a.o, a.mc, a.cols, a.bg, 11, a.fg))

    p = sub.add_parser('sprite')
    p.add_argument('file')
    p.add_argument('off', type=lambda s: int(s, 0))
    p.add_argument('count', type=int)
    p.add_argument('--multicolor', action='store_true')
    p.add_argument('--cols', type=int, default=8)
    p.add_argument('-o', default='c64_sprites.png')
    p.set_defaults(func=lambda a: render_sprites(load(a.file), a.off, a.count, a.o, a.multicolor, a.cols))

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
