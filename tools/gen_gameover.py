#!/usr/bin/env python3
"""
gen_gameover.py - Genera assets/bbdata/GAMEOVER.BIN a partir del frame 127 de SPRITE.SQV (DOS).
Extreu la pancarta 'GAME OVER' (160x34 VGA), aplica downsampling intel·ligent 2:1 a Mode 0 (80x34 px = 40x34 B = 1360 B)
amb la paleta exacta de Mode 0 del joc:
- Vermell brillant: Pen 7 (0x4C)
- Blanc: Pen 0 (0x4B)
- Negre: Pen 11 (0x54)
- Blau cel (fons): Pen 8 (0x57)
- Gris: Pen 2 (0x40)
- Blau pastel: Pen 12 (0x5F)
- Vermell fosc: Pen 13 (0x5C)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from bbdata.sprites import load_sqv_frames

SQV = os.path.join(PROJ, "assets", "bbdata", "SPRITE.SQV")
OUT = os.path.join(PROJ, "assets", "bbdata", "GAMEOVER.BIN")

dos_to_cpc = {
    0: 11,   # black
    4: 7,    # bright red
    15: 0,   # white
    8: 11,   # black / dark outline
    7: 2,    # grey
    5: 13,   # purple / dark red stripe
    3: 12,   # pastel blue
    11: 8,   # sky blue background
}

def pair_smart(c0, c1):
    p0 = dos_to_cpc.get(c0, 11)
    p1 = dos_to_cpc.get(c1, 11)
    if p0 == p1: return p0
    if p0 == 7 or p1 == 7: return 7
    if p0 == 0 or p1 == 0: return 0
    if (p0 == 11 and p1 in (8, 12, 13)) or (p1 == 11 and p0 in (8, 12, 13)): return 11
    if p0 == 2 or p1 == 2: return 2
    if p0 == 13 or p1 == 13: return 13
    return p0

def pack_mode0_byte(p0, p1):
    return (((p0 & 1) << 7) |
            ((p1 & 1) << 6) |
            (((p0 >> 2) & 1) << 5) |
            (((p1 >> 2) & 1) << 4) |
            (((p0 >> 1) & 1) << 3) |
            (((p1 >> 1) & 1) << 2) |
            (((p0 >> 3) & 1) << 1) |
            ((p1 >> 3) & 1))

def generate_gameover():
    frames = load_sqv_frames(SQV)
    w, h, px = frames[127]
    assert w == 160 and h == 34, (w, h)

    raw_bytes = bytearray()
    for y in range(34):
        for x in range(0, 80, 2):
            p0 = pair_smart(px[y][x*2], px[y][x*2 + 1])
            p1 = pair_smart(px[y][(x+1)*2], px[y][(x+1)*2 + 1])
            raw_bytes.append(pack_mode0_byte(p0, p1))

    assert len(raw_bytes) == 40 * 34
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "wb").write(raw_bytes)
    print(f"GAMEOVER: {len(raw_bytes)} bytes generats a {OUT}")
    return OUT

if __name__ == "__main__":
    generate_gameover()
