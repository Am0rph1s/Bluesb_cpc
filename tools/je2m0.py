#!/usr/bin/env python3
"""
je2m0.py - Converteix les fulles d'sprites del C64 (Jake/Elwood) a Mode 0 del CPC.

Cada BMP = graella 8x8 de sprites 24x21 (mida VIC-II). Cada pixel BMP equival
1:1 a un pixel de Mode 0.

Colors d'entrada (C64 extret): crema (255,251,240)=transparent; negre, gris, blau.
Sortida: sprites Mode 0 amb MASCARA (nibble): per cada byte -> [mask, img].
  blit Z80: scr = (scr & ~mask) | (img & mask)
  mask byte = 0xF0 si el pixel esquerre es opac, 0x0F si ho es el dret.

Us:
  py je2m0.py <fitxer.bmp> --prefix jake --frames dir --preview out.png
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CW, CH = 24, 21
COLS, ROWS = 8, 8
TRANSPARENT = (255, 251, 240)

# colors C64 extrets -> pen CPC
C64_COLORS = {
    (0, 0, 0): 0,          # negre  -> pen 0 (negre)   [vestit]
    (192, 192, 192): 15,   # gris   -> pen 15 (blanc)  [camisa]
    (0, 0, 128): 4,        # blau   -> pen 4 (blau)
}


def load_frames(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    px = im.load()
    frames = []
    for r in range(ROWS):
        for c in range(COLS):
            cell = [[px[c * CW + x, r * CH + y] for x in range(CW)] for y in range(CH)]
            frames.append(cell)
    return frames


def frame_to_m0(cell):
    """Retorna llista de bytes interleaved [mask, img] (21 linies x 12 bytes -> 504 B)."""
    data = bytearray()
    for y in range(CH):
        for xb in range(CW // 2):
            img = 0
            mask = 0
            for k in range(2):
                x = xb * 2 + k
                col = cell[y][x]
                if col == TRANSPARENT:
                    pen = 0
                else:
                    pen = C64_COLORS.get(col, 1)
                pen &= 0x0F
                if col != TRANSPARENT:
                    if k == 0:
                        mask |= 0xAA
                        img |= ((pen & 1) << 7) | (((pen >> 2) & 1) << 5) | (((pen >> 1) & 1) << 3) | (((pen >> 3) & 1) << 1)
                    else:
                        mask |= 0x55
                        img |= ((pen & 1) << 6) | (((pen >> 2) & 1) << 4) | (((pen >> 1) & 1) << 2) | ((pen >> 3) & 1)
            data += bytes([mask, img])
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bmp')
    ap.add_argument('--prefix', default='spr')
    ap.add_argument('--frames', default=None)
    ap.add_argument('--preview', default=None)
    args = ap.parse_args()

    frames = load_frames(args.bmp)
    print("frames:", len(frames))

    blob = bytearray()
    for cell in frames:
        blob += frame_to_m0(cell)

    if args.frames:
        os.makedirs(args.frames, exist_ok=True)
        out = os.path.join(args.frames, '%s_m0.bin' % args.prefix)
        open(out, 'wb').write(blob)
        print("binari Mode 0:", out, len(blob), "bytes (%d x %d)" % (len(frames), len(blob) // len(frames)))

    if args.preview:
        from PIL import Image
        pal = [(0, 0, 0), (0, 0, 170), (0, 170, 0), (0, 170, 170),
               (170, 0, 0), (170, 0, 170), (170, 85, 0), (170, 170, 170),
               (85, 85, 85), (0, 0, 255), (0, 255, 0), (0, 255, 255),
               (255, 85, 85), (255, 0, 255), (255, 255, 85), (255, 255, 255)]
        cw, ch = CW * 3, CH * 3
        im = Image.new('RGB', (8 * cw, 8 * ch), (120, 120, 160))
        for i, cell in enumerate(frames):
            ox = (i % 8) * cw; oy = (i // 8) * ch
            for y in range(CH):
                for x in range(CW):
                    col = cell[y][x]
                    if col == TRANSPARENT:
                        continue
                    c = pal[C64_COLORS.get(col, 1)]
                    for yy in range(3):
                        for xx in range(3):
                            im.putpixel((ox + x * 3 + xx, oy + y * 3 + yy), c)
        im.save(args.preview)
        print("preview", args.preview)


if __name__ == '__main__':
    main()
