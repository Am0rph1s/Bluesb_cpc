#!/usr/bin/env python3
"""
gen_player.py - Genera src/player_frames.h (Mode 0) des del binari compost
de Jake (assets/jake_elwood_sprites/jake_composed_m0.bin).

Format: cada frame = 34 linies x 24 bytes ([mask,img] interleaved per 2 px).
w = 12 bytes de pantalla, h = 34.
Ordre: 0 idle, 1..3 walk, 4 jump.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BIN = os.path.join(PROJ, 'assets', 'jake_elwood_sprites', 'jake_composed_m0.bin')
OUT = os.path.join(PROJ, 'src', 'player_frames.h')

W_BYTES = 12
H = 34
FRAME = W_BYTES * 2 * H   # 816


def main():
    data = open(BIN, 'rb').read()
    assert len(data) % FRAME == 0, len(data)
    n = len(data) // FRAME
    lines = ['#ifndef PLAYER_FRAMES_H', '#define PLAYER_FRAMES_H', '',
             '#include "cpctelera.h"', '',
             '// Frames de Jake en Mode 0 (24x34, [mask,img] per 2 px).',
             '// Generat per tools/gen_player.py', '']
    for f in range(n):
        blob = data[f * FRAME:(f + 1) * FRAME]
        lines.append('static const u8 g_pf_%d[%d] = {' % (f, FRAME))
        for i in range(0, FRAME, 12):
            lines.append('    ' + ','.join('0x%02X' % b for b in blob[i:i + 12]) + ',')
        lines.append('};')
        lines.append('')
    lines.append('typedef struct { const u8* data; u8 wb; u8 h; } PSprFrame;')
    lines.append('static const PSprFrame g_player_frames[%d] = {' % n)
    for f in range(n):
        lines.append('    { g_pf_%d, %d, %d },' % (f, W_BYTES, H))
    lines.append('};')
    lines.append('')
    # walk cycle: 1,2,3,2 (frame 0 = idle)
    lines.append('static const u8 g_walk_seq[4] = { 1, 2, 3, 2 };')
    lines.append('')
    lines.append('#endif')
    open(OUT, 'w').write('\n'.join(lines) + '\n')
    print("escrit", OUT, "(%d frames)" % n)


if __name__ == '__main__':
    main()
