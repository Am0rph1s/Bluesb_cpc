#!/usr/bin/env python3
"""
compose_m0.py - Munta sprites de Jake/Elwood a partir de PECES (cap + cames/cos)
de les fulles C64 i els converteix a Mode 0 amb mascara, amb la taula
d'animacions del joc.

Model (C64): un personatge = 1 sprite de CAP + 1 sprite de CAMES, apilats en
vertical. Un cap serveix per a varies cames. Nedar/arrossegar-se = 2 meitats
en horitzontal (TODO).

Taula d'animacions (indexs de la fulla jake_00..63):
  idle   : cap 00 + cames 01
  walk   : cap 00 + cames 01,02,03
  jump   : cap 04 + peus 05
  crouch : TODO (15,16,17)
Sortida: binari Mode 0 [mask,img] + preview.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CW, CH = 24, 21
BG = (255, 251, 240)
BODY_OFF = 13          # on es col·loca l'sprite de cames respecte el cap
CHAR_H = BODY_OFF + CH  # alcada del personatge muntat

C64_COLORS = {(0, 0, 0): 0, (192, 192, 192): 15, (0, 0, 128): 1}


def load_sheet(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    px = im.load()
    return [[[px[c * CW + x, r * CH + y] for x in range(CW)] for y in range(CH)]
            for r in range(8) for c in range(8)]


def compose(sheet, head_i, body_i, off=BODY_OFF, h=CHAR_H):
    """Munta head_i (a dalt) + body_i (a off) -> llista de files de colors."""
    head = sheet[head_i]
    body = sheet[body_i]
    out = [[BG] * CW for _ in range(h)]
    for y in range(CH):
        for x in range(CW):
            c = head[y][x]
            if c != BG:
                out[y][x] = c
    for y in range(CH):
        Y = off + y
        if Y < h:
            for x in range(CW):
                c = body[y][x]
                if c != BG:
                    out[Y][x] = c
    return out


def to_m0(rows):
    """rows: llista de h files de colors -> bytes [mask,img] per 2 px (Mode 0 interleaved)."""
    data = bytearray()
    for y in range(len(rows)):
        for xb in range(CW // 2):
            img = 0
            mask = 0
            for k in range(2):
                col = rows[y][xb * 2 + k]
                if col == BG:
                    continue
                pen = C64_COLORS.get(col, 1) & 0x0F
                if k == 0:
                    mask |= 0xAA
                    img |= ((pen & 1) << 7) | (((pen >> 2) & 1) << 5) | (((pen >> 1) & 1) << 3) | (((pen >> 3) & 1) << 1)
                else:
                    mask |= 0x55
                    img |= ((pen & 1) << 6) | (((pen >> 2) & 1) << 4) | (((pen >> 1) & 1) << 2) | ((pen >> 3) & 1)
            data += bytes([mask, img])
    return data


ANIMS = [
    ('idle', [(0, 1)]),
    ('walk', [(0, 1), (0, 2), (0, 3)]),
    ('jump', [(4, 5)]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bmp')
    ap.add_argument('--prefix', default='jake')
    ap.add_argument('--frames-dir', default='assets/jake_elwood_sprites')
    ap.add_argument('--preview', default=None)
    args = ap.parse_args()

    sheet = load_sheet(args.bmp)
    os.makedirs(args.frames_dir, exist_ok=True)

    blob = bytearray()
    index = []
    from PIL import Image
    preview_rows = []
    for name, frames in ANIMS:
        for (hi, bi) in frames:
            rows = compose(sheet, hi, bi)
            blob += to_m0(rows)
            index.append((name, hi, bi))
            preview_rows.append(rows)
    out = os.path.join(args.frames_dir, '%s_composed_m0.bin' % args.prefix)
    open(out, 'wb').write(blob)
    print("binari:", out, len(blob), "bytes", "(%d frames x %d)" % (len(index), len(blob) // len(index)))

    if args.preview:
        pal = [(0, 0, 0), (0, 0, 170), (0, 170, 0), (0, 170, 170),
               (170, 0, 0), (170, 0, 170), (170, 85, 0), (170, 170, 170),
               (85, 85, 85), (0, 0, 255), (0, 255, 0), (0, 255, 255),
               (255, 85, 85), (255, 0, 255), (255, 255, 85), (255, 255, 255)]
        S = 4
        fw, fh = CW * S + 8, CHAR_H * S + 14
        im = Image.new('RGB', (len(preview_rows) * fw, fh), (120, 120, 160))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(im)
        for k, rows in enumerate(preview_rows):
            ox = k * fw
            dr.text((ox + 2, 2), index[k][0], fill=(255, 255, 0))
            for y in range(CHAR_H):
                for x in range(CW):
                    c = rows[y][x]
                    if c == BG:
                        continue
                    for yy in range(S):
                        for xx in range(S):
                            im.putpixel((ox + x * S + xx, 14 + y * S + yy), pal[C64_COLORS.get(c, 1)])
        im.save(args.preview)
        print("preview", args.preview)


if __name__ == '__main__':
    main()
