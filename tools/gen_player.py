#!/usr/bin/env python3
"""
gen_player.py - Genera src/player_frames.h (Mode 0) des del binari compost
de Jake (assets/jake_elwood_sprites/jake_composed_m0.bin).

Format: cada frame = 34 linies x 24 bytes ([inv_mask, img_masked] interleaved per 2 px).
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
H = 30
FRAME = W_BYTES * 2 * H   # 720 bytes


def flip_m0_byte(b):
    return ((b & 0xAA) >> 1) | ((b & 0x55) << 1)


def flip_frame(data, w_bytes=W_BYTES, h=H):
    out = bytearray()
    for y in range(h):
        line = data[y * w_bytes * 2 : (y + 1) * w_bytes * 2]
        for xb in range(w_bytes - 1, -1, -1):
            mask = line[xb * 2]
            img = line[xb * 2 + 1]
            out.append(flip_m0_byte(mask))
            out.append(flip_m0_byte(img))
    return bytes(out)


def to_fast_format(blob):
    out = bytearray()
    for i in range(0, len(blob), 2):
        mask = blob[i]
        img = blob[i + 1]
        inv_mask = (~mask) & 0xFF
        img_masked = img & mask
        out.append(inv_mask)
        out.append(img_masked)
    return bytes(out)


def main():
    data = open(BIN, 'rb').read()
    assert len(data) % FRAME == 0, len(data)
    n = len(data) // FRAME
    lines = ['#ifndef PLAYER_FRAMES_H', '#define PLAYER_FRAMES_H', '',
             '#include "cpctelera.h"', '',
             '// Frames de Jake en Mode 0 (pre-mirallats dreta i esquerra).',
             '// Format ultra-ràpid: [inv_mask, img_masked] per píxel interleaved.',
             '// Generat per tools/gen_player.py', '']
    # Frames Dreta
    for f in range(n):
        raw = data[f * FRAME:(f + 1) * FRAME]
        blob = to_fast_format(raw)
        lines.append('static const u8 g_pf_r_%d[%d] = {' % (f, FRAME))
        for i in range(0, FRAME, 12):
            lines.append('    ' + ','.join('0x%02X' % b for b in blob[i:i + 12]) + ',')
        lines.append('};')
        lines.append('')
    # Frames Esquerra (pre-mirallats)
    for f in range(n):
        raw = data[f * FRAME:(f + 1) * FRAME]
        blob = flip_frame(to_fast_format(raw))
        lines.append('static const u8 g_pf_l_%d[%d] = {' % (f, FRAME))
        for i in range(0, FRAME, 12):
            lines.append('    ' + ','.join('0x%02X' % b for b in blob[i:i + 12]) + ',')
        lines.append('};')
        lines.append('')
    lines.append('typedef struct { const u8* data; u8 wb; u8 h; } PSprFrame;')
    lines.append('static const PSprFrame g_player_frames_r[%d] = {' % n)
    for f in range(n):
        lines.append('    { g_pf_r_%d, %d, %d },' % (f, W_BYTES, H))
    lines.append('};')
    lines.append('')
    lines.append('static const PSprFrame g_player_frames_l[%d] = {' % n)
    for f in range(n):
        lines.append('    { g_pf_l_%d, %d, %d },' % (f, W_BYTES, H))
    lines.append('};')
    lines.append('')
    # walk cycle: 1, 2, 3, 2 (frame 0 = idle)
    lines.append('static const u8 g_walk_seq[4] = { 1, 2, 3, 2 };')
    lines.append('')
    lines.append('#endif')
    open(OUT, 'w').write('\n'.join(lines) + '\n')
    print("escrit", OUT, "(%d frames R + %d frames L)" % (n, n))


if __name__ == '__main__':
    main()
