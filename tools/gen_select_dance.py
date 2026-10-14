#!/usr/bin/env python3
"""gen_select_dance.py - 20 frames ball select DOS (SPRITE.SQZ) -> Mode 0 CPC.

Font: SPRITE.SQV (sprites VGA 32px, 16 colors). Desti: 20 frames 16x30
(parelles inv,img mode0, 480 B/frame = 9600 B) a assets/bbdata/DANCE20.BIN.
Ordre cua: Jake dansa 0x21-26 (6) + Jake idle 0x15-17 (3) + Elwood dansa-A
0x33,0x47-49,0x64 (5) + Elwood dansa-B 0x53-58 (6). Mateixes taules DOS
(animframe_0135/00dd/01d5/022d de game.c): el FRONT les reprodueix tal qual.

Geometria: 32->16 (pixel esquerre, com gen_screens), 16->8 alineat esquerra,
alineat PEUS (files de sota): el que sobra es retalla de dalt, el que falta
s'omple de transparent per dalt. Pens ballarins 9-12 (negre, blanc, pell,
blau): el quadre SELECT usa 0-8,13,14 (SELECT.BIN nomes amb split de cons).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'bbdata'))
from sprites import load_sqv_frames
from PIL import Image

ORDER = [0x21, 0x22, 0x23, 0x24, 0x25, 0x26,          # Jake dansa (6)
         0x15, 0x16, 0x17,                            # Jake idle (3)
         0x33, 0x47, 0x48, 0x49, 0x64,                # Elwood dansa-A (5)
         0x53, 0x54, 0x55, 0x56, 0x57, 0x58]          # Elwood dansa-B (6)

# VGA -> pen ballari (0 transparent). Vistos als 20 sprites: nomes 2,4,5,7,8,11,12,15.
# Pens DEDICATS 9-12 (negre, blanc, pell, blau): el quadre SELECT es intacte
# (usa 0-8,13,14) i no hi ha col·lisions de tinta.
VMAP = {0: None, 11: 9, 4: 9, 2: 9, 12: 10, 15: 10, 5: 11, 7: 11, 8: 12}

W, H = 16, 30


def pack(a, b):
    """Byte Mode 0: pixel esq bits 7,5,3,1; dret 6,4,2,0 (com gen_screens)."""
    return (((a & 1) << 7) | (((a >> 1) & 1) << 3) | (((a >> 2) & 1) << 5) |
            (((a >> 3) & 1) << 1) | ((b & 1) << 6) | (((b >> 1) & 1) << 2) |
            (((b >> 2) & 1) << 4) | (((b >> 3) & 1) << 0))


def convert(w, h, px):
    """Un sprite SQV -> 480 B (inv,img). Retorna bytes + canvas de pens (debug)."""
    cv = [[None] * W for _ in range(H)]
    yoff = H - h  # >0: pad dalt; <0: retalla dalt (peus sempre a fila 29)
    for y in range(H):
        sy = y + yoff
        if 0 <= sy < H:
            for x in range(0, w, 2):
                v = px[y][x] & 15
                if v not in VMAP:
                    raise SystemExit('color VGA %d no mapejat' % v)
                cv[sy][x // 2] = VMAP[v]
    out = bytearray()
    for y in range(H):
        for xb in range(0, W, 2):
            a = cv[y][xb]
            b = cv[y][xb + 1]
            out.append(pack(15 if a is None else 0, 15 if b is None else 0))
            out.append(pack(0 if a is None else a, 0 if b is None else b))
    assert len(out) == 480, len(out)
    return bytes(out), cv


def main():
    frames = load_sqv_frames(os.path.join(PROJ, 'assets', 'bbdata', 'SPRITE.SQV'))
    assert len(ORDER) == 20
    blob = bytearray()
    DPAL = {9: (0, 0, 0), 10: (255, 255, 255), 11: (255, 178, 128),
            12: (0, 0, 255)}
    prev = Image.new('RGB', (10 * 20, 2 * 40), (24, 24, 28))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(prev)
    for k, idx in enumerate(ORDER):
        w, h, px = frames[idx]
        data, cv = convert(w, h, px)
        blob += data
        ox, oy = (k % 10) * 20 + 2, (k // 10) * 40 + 2
        dr.text((ox, oy), '#%d' % idx, fill=(255, 255, 0))
        for y in range(H):
            for x in range(W):
                pen = cv[y][x]
                if pen is not None:
                    prev.putpixel((ox + x, oy + 6 + y), DPAL[pen])
    assert len(blob) == 9600, len(blob)
    out_path = os.path.join(PROJ, 'assets', 'bbdata', 'DANCE20.BIN')
    open(out_path, 'wb').write(bytes(blob))
    prev = prev.resize((10 * 20 * 3, 2 * 40 * 3), Image.NEAREST)
    prev.save(os.path.join('/Users', 'esquerra', 'AppData', 'Local', 'Temp',
                           'opencode', 'sel20cpc.png'))
    print('DANCE20.BIN: 20 frames (%d B) + preview sel20cpc.png' % len(blob))


if __name__ == '__main__':
    main()
