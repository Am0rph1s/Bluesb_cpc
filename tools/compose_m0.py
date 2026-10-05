#!/usr/bin/env python3
"""
compose_m0.py - Munta sprites de Jake a partir de les peces C64 (1.bmp).
Model C64: cap (00..04) + cames (01..05), BODY_OFF=13, CHAR_H=34.

Frames unics:
  0: idle / walk1 (cap 00 + cames 01)
  1: walk2        (cap 00 + cames 02)
  2: walk3        (cap 00 + cames 03)
  3: jump         (cap 04 + peus 05)
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CW, CH = 24, 21
CW_M0 = 12
BG_COLORS = {(255, 251, 240), (255, 0, 255)}
BODY_OFF = 13          # on es col·loca l'sprite de cames respecte el cap
CHAR_H = 30            # alcada real del personatge muntat (sense les 4 linies buides de sota)

C64_COLORS = {(0, 0, 0): 0, (192, 192, 192): 15, (0, 0, 128): 4}


def load_sheet(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    px = im.load()
    return [[[px[c * CW + x, r * CH + y] for x in range(CW)] for y in range(CH)]
            for r in range(8) for c in range(8)]


def compose(sheet, head_i, body_i, off=BODY_OFF, h=CHAR_H):
    """Munta head_i (a dalt) + body_i (a off) -> llista de files de colors (12 px M0)."""
    head = sheet[head_i]
    body = sheet[body_i]
    out = [[None] * CW_M0 for _ in range(h)]
    for y in range(CH):
        if y < h:
            for x in range(CW_M0):
                c = head[y][x * 2]
                if c not in BG_COLORS:
                    out[y][x] = c
    for y in range(CH):
        Y = off + y
        if Y < h:
            for x in range(CW_M0):
                c = body[y][x * 2]
                if c not in BG_COLORS:
                    out[Y][x] = c
    return out


def to_m0(rows, is_jump=False):
    """rows: llista de h files de colors -> bytes [mask,img] per 2 px (Mode 0 interleaved, 6 bytes/row)."""
    data = bytearray()
    for y in range(len(rows)):
        for xb in range(CW_M0 // 2):
            img = 0
            mask = 0
            for k in range(2):
                x = xb * 2 + k
                col = rows[y][x]
                if col is None or col in BG_COLORS:
                    continue
                if col == (0, 0, 0):
                    pen = 0
                elif col == (0, 0, 128):
                    pen = 4
                elif col == (192, 192, 192):
                    if is_jump and y < 3 and x >= 6:
                        pen = 1   # mà tocant el barret
                    elif y < 13:
                        pen = 1   # cara (pell)
                    else:
                        pen = 15  # camisa blanca
                else:
                    pen = 1
                pen &= 0x0F

                if k == 0:
                    mask |= 0xAA
                    img |= ((pen & 1) << 7) | (((pen >> 2) & 1) << 5) | (((pen >> 1) & 1) << 3) | (((pen >> 3) & 1) << 1)
                else:
                    mask |= 0x55
                    img |= ((pen & 1) << 6) | (((pen >> 2) & 1) << 4) | (((pen >> 1) & 1) << 2) | ((pen >> 3) & 1)
            data += bytes([mask, img])
    return data


UNIQUE_FRAMES = [
    ('idle_walk1', 0, 1),
    ('walk2', 0, 2),
    ('walk3', 0, 3),
    ('jump', 4, 5),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('bmp', nargs='?', default=r'assets\jake_elwood sprites\1.bmp')
    ap.add_argument('--prefix', default='jake')
    ap.add_argument('--frames-dir', default='assets/jake_elwood_sprites')
    ap.add_argument('--preview', default='tools/jake_composed_preview.png')
    args = ap.parse_args()

    sheet = load_sheet(args.bmp)
    os.makedirs(args.frames_dir, exist_ok=True)

    blob = bytearray()
    index = []
    from PIL import Image
    preview_rows = []
    for name, hi, bi in UNIQUE_FRAMES:
        rows = compose(sheet, hi, bi)
        blob += to_m0(rows, is_jump=(name == 'jump'))
        index.append((name, hi, bi))
        preview_rows.append(rows)
    out = os.path.join(args.frames_dir, '%s_composed_m0.bin' % args.prefix)
    open(out, 'wb').write(blob)
    print("binari:", out, len(blob), "bytes", "(%d frames x %d)" % (len(index), len(blob) // len(index)))

    if args.preview:
        pal = [(0, 0, 0), (255, 140, 140), (0, 0, 0), (0, 0, 0),
               (0, 0, 160), (0, 0, 0), (0, 0, 0), (0, 0, 0),
               (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0),
               (0, 0, 0), (0, 0, 0), (0, 0, 0), (255, 255, 255)]
        S = 4
        fw, fh = CW_M0 * S * 2 + 8, CHAR_H * S + 14
        im = Image.new('RGB', (len(preview_rows) * fw, fh), (120, 120, 160))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(im)
        for k, rows in enumerate(preview_rows):
            ox = k * fw
            dr.text((ox + 2, 2), index[k][0], fill=(255, 255, 0))
            is_jump = (index[k][0] == 'jump')
            for y in range(CHAR_H):
                for x in range(CW_M0):
                    c = rows[y][x]
                    if c is None or c in BG_COLORS:
                        continue
                    if c == (0, 0, 0): pen = 0
                    elif c == (0, 0, 128): pen = 4
                    elif c == (192, 192, 192):
                        if is_jump and y < 3 and x >= 6: pen = 1
                        elif y < 13: pen = 1
                        else: pen = 15
                    else: pen = 1
                    for yy in range(S):
                        for xx in range(S * 2):
                            im.putpixel((ox + x * S * 2 + xx, 14 + y * S + yy), pal[pen])
        im.save(args.preview)
        print("preview", args.preview)


if __name__ == '__main__':
    main()
