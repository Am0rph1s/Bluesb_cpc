#!/usr/bin/env python3
"""
bbspr.py - Converteix un frame de SPRITE.SQV a l'format d'sprite del nostre
engine (Mode 1, interleaved [mask,img] per byte, transparencia = color 0).

Us:
  py bbspr.py [frame] [--out src/player_sprite.h] [--preview out.png]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sprites import load_sqv_frames   # noqa: E402
from mode1 import nearest             # noqa: E402


def pal_level0():
    """Paleta del nivell 0 (magasin) de level.c (_colors_data), 12-bit -> 8-bit."""
    raw = [0x000, 0xc77, 0x989, 0x669, 0x147, 0xfda, 0xdb9, 0xf87,
           0x4af, 0x050, 0x091, 0x111, 0xbcf, 0xa20, 0x630, 0xfff]
    return [(((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17) for v in raw]


def convert(frame_index, targets, sqv):
    frames = load_sqv_frames(sqv, reverse=False)
    w, h, px = frames[frame_index]
    pal = pal_level0()
    lut = [None] + [nearest(pal[i], targets) for i in range(1, 16)]
    wb = (w + 3) // 4
    data = []
    for y in range(h):
        for xb in range(wb):
            mask = 0
            img = 0
            for p in range(4):
                x = xb * 4 + p
                c = px[y][x] if x < w else 0
                if c == 0:
                    mask |= (1 << (7 - p)) | (1 << (3 - p))   # transparent
                else:
                    col = lut[c]
                    img |= ((col >> 1) & 1) << (7 - p)
                    img |= (col & 1) << (3 - p)
            data += [mask, img]
    return w, h, wb, data


def write_header(path, wb, h, data):
    lines = ['#ifndef PLAYER_SPRITE_H', '#define PLAYER_SPRITE_H', '', '#include "cpctelera.h"', '',
             '// Sprite real de Blues Brothers (%d bytes x %d linies), interleaved [mask,img].' % (wb, h),
             '#define PLAYER_SPR_W_BYTES %d' % wb, '#define PLAYER_SPR_H %d' % h, '',
             'static const u8 g_player_spr[%d] = {' % len(data)]
    for i in range(0, len(data), 12):
        lines.append('    ' + ','.join('0x%02X' % b for b in data[i:i + 12]) + ',')
    lines.append('};')
    lines.append('')
    lines.append('#endif')
    open(path, 'w').write('\n'.join(lines) + '\n')


def preview(path, w, h, px, targets):
    try:
        from PIL import Image
        im = Image.new('RGB', (w, h), (24, 24, 24))
        pal = pal_level0()
        for y in range(h):
            for x in range(w):
                c = px[y][x]
                if c != 0:
                    im.putpixel((x, y), targets[nearest(pal[c], targets)])
        im.resize((w * 6, h * 6), Image.NEAREST).save(path)
        print("preview", path)
    except Exception as e:
        print("sense preview:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('frame', type=int, nargs='?', default=0)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(HERE), '..', 'src', 'player_sprite.h'))
    ap.add_argument('--preview', default=None)
    ap.add_argument('--colors', default='0,0,0;255,255,255;204,119,119;68,170,255')
    ap.add_argument('--sqv', default=os.path.join(os.path.dirname(HERE), '..', 'assets', 'bbdata', 'SPRITE.SQV'))
    args = ap.parse_args()
    targets = [tuple(int(v) for v in p.split(',')) for p in args.colors.split(';')]
    w, h, wb, data = convert(args.frame, targets, args.sqv)
    print("frame %d -> %dx%d (%d bytes/linia), %d bytes" % (args.frame, w, h, wb, len(data)))
    write_header(args.out, wb, h, data)
    print("escrit", args.out)
    if args.preview:
        frames = load_sqv_frames(args.sqv, reverse=False)
        preview(args.preview, w, h, frames[args.frame][2], targets)


if __name__ == "__main__":
    main()
