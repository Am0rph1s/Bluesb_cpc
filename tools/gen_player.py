#!/usr/bin/env python3
"""Generate CPC Mode 0 Jake frames and the bank-7 runtime asset."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BIN = os.path.join(PROJ, 'assets', 'jake_elwood_sprites', 'jake_composed_m0.bin')
OUT = os.path.join(PROJ, 'src', 'player_frames.h')
OUT_BIN = os.path.join(PROJ, 'assets', 'bbdata', 'PFRAMES.BIN')

W_BYTES = 6
H = 30
FRAME = W_BYTES * 2 * H   # 360 bytes


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
    right = [to_fast_format(data[f * FRAME:(f + 1) * FRAME]) for f in range(n)]
    left = [flip_frame(frame) for frame in right]
    with open(OUT_BIN, 'wb') as f:
        f.write(b''.join(right + left))

    lines = ['#ifndef PLAYER_FRAMES_H', '#define PLAYER_FRAMES_H', '',
             '#include "cpctelera.h"', '',
             '// Jake frames reside in bank 7; the blitter reads them while mapped.',
             '#define PLAYER_FRAMES_BANK 0xC7',
             '#define PLAYER_FRAMES_BASE 0x4000',
             '#define PLAYER_FRAME_SIZE %d' % FRAME, '',
             'typedef struct { u16 offset; u8 wb; u8 h; } PSprFrame;']
    lines.append('static const PSprFrame g_player_frames_r[%d] = {' % n)
    for f in range(n):
        lines.append('    { %d, %d, %d },' % (f * FRAME, W_BYTES, H))
    lines.append('};')
    lines.append('')
    lines.append('static const PSprFrame g_player_frames_l[%d] = {' % n)
    for f in range(n):
        lines.append('    { %d, %d, %d },' % ((n + f) * FRAME, W_BYTES, H))
    lines.append('};')
    lines.append('')
    lines.append('#endif')
    open(OUT, 'w').write('\n'.join(lines) + '\n')
    print("wrote %s (%d frames R + %d frames L)" % (OUT_BIN, n, n))
    print("wrote", OUT)


if __name__ == '__main__':
    main()
