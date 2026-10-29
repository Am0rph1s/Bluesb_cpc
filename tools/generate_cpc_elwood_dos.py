# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, 'tools/bbdata')
from sprites import load_sqv_frames

frames = load_sqv_frames(r'assets/bbdata/SPRITE.SQV')

# Mateix mapatge DOS VGA -> Pen Mode 0 que Jake (generate_cpc_jake_dos.py):
# barret/vestit Elwood usen els mateixos pens DOS (3/11 negre, 4 blau...).
dos_to_cpc_pen = {
    0:  None,
    1:  1, 2: 12, 3: 11, 4: 4, 5: 1, 6: 1, 7: 1, 8: 0,
    9:  9, 10: 10, 11: 11, 12: 0, 13: 13, 14: 13, 15: 0,
}

def encode_pair(pen0, pen1):
    mask = 0
    img = 0
    if pen0 is not None:
        mask |= 0xAA
        p = pen0 & 0x0F
        img |= ((p & 1) << 7) | (((p >> 2) & 1) << 5) | (((p >> 1) & 1) << 3) | (((p >> 3) & 1) << 1)
    if pen1 is not None:
        mask |= 0x55
        p = pen1 & 0x0F
        img |= ((p & 1) << 6) | (((p >> 2) & 1) << 4) | (((p >> 1) & 1) << 2) | (((p >> 3) & 1) << 0)
    inv_mask = (~mask) & 0xFF
    img_masked = img & mask
    return inv_mask, img_masked

SWIM_SET = {95, 96, 97, 98, 99}
FLOAT_IDX = 89

def pack_standard_frame(idx):
    w, h, px = frames[idx]
    w_m0 = 16
    min_x, max_x = w, 0
    for y in range(h):
        for x in range(w):
            if px[y][x] != 0:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
    bw = max_x - min_x + 1 if max_x >= min_x else 0

    if idx in SWIM_SET:
        y_shift = (30 - h) // 2
    elif idx == FLOAT_IDX:
        y_shift = 0
    else:
        y_shift = 30 - h

    x_shift = (w_m0 - ((w + 1) // 2)) // 2

    box = [[None] * 16 for _ in range(30)]
    for y in range(h):
        out_y = y + y_shift
        if 0 <= out_y < 30:
            for xm in range(16):
                if bw > 32 and idx in SWIM_SET:
                    xdos0 = min_x + (xm * bw) // 16
                    xdos1 = min_x + ((xm * 2 + 1) * bw) // 32
                else:
                    xdos0 = (xm - x_shift) * 2
                    xdos1 = xdos0 + 1
                p0 = px[y][xdos0] if 0 <= xdos0 < w else 0
                p1 = px[y][xdos1] if 0 <= xdos1 < w else 0

                val = 0
                if p0 != 0 and p1 != 0:
                    val = p0 if p0 not in (3, 11) else p1
                elif p0 != 0:
                    val = p0
                elif p1 != 0:
                    val = p1

                pen = dos_to_cpc_pen.get(val)
                box[out_y][xm] = pen

    raw = bytearray()
    for y in range(30):
        for xb in range(8):
            p0 = box[y][xb * 2]
            p1 = box[y][xb * 2 + 1]
            inv_mask, img = encode_pair(p0, p1)
            raw.append(inv_mask)
            raw.append(img)
    return bytes(raw)

# 26 frames mirror de Jake (+50 DOS), validat slot a slot amb animframes_059d.
GAME_FRAMES_ELWOOD = [
    ('idle',  51),
    ('walk1', 52),
    ('walk2', 50),
    ('walk3', 53),
    ('jump',  57),
    ('ladder_back',  58),
    ('crouch1', 54),
    ('crouch2', 55),
    ('crouch3', 56),
    ('ladder1', 59),
    ('dance1',  86),  # 5e de animframe_022d (Jake: 33 = 5e de 0135)
    ('dance2',  88),  # cap de animframe_022d (Jake: 35 = cap de 0135)
    ('crate_walk1', 63),
    ('crate_walk2', 64),
    ('crate_walk3', 65),
    ('crate_walk4', 66),
    ('crate_idle', 60),  # DOS 60 (Jake 10 + 50): repòs amb caixa
    ('crate_lift',  62),
    ('crate_throw', 68),
    ('crate_push', 70),
    ('carry_float', 89),
    ('swim_idle',    98),
    ('swim_stroke1', 96),
    ('swim_stroke2', 97),
    ('swim_vert',    99),
    ('swim_floor',   95),
    # 26..28: Estabornit amb estrelletes girant sobre el cap (DOS 77, 78, 79 / animframe_0115 + 50)
    ('dazed1',       77),
    ('dazed2',       78),
    ('dazed3',       79),
]

# Danses completes del select (Jake A/B + Elwood A/B, llistes DOS autentiques).
DANCE_FRAMES = [
    ('jake_a1', 33), ('jake_a2', 34), ('jake_a3', 35),
    ('jake_a4', 36), ('jake_a5', 37), ('jake_a6', 38),
    ('jake_b1', 21), ('jake_b2', 22), ('jake_b3', 23),
    ('elw_a1', 51), ('elw_a2', 71), ('elw_a3', 72),
    ('elw_a4', 73), ('elw_a5', 100),
    ('elw_b1', 88), ('elw_b2', 83), ('elw_b3', 84),
    ('elw_b4', 85), ('elw_b5', 86), ('elw_b6', 87),
]

out_bin = r'assets/bbdata/ELWOOD.BIN'
all_blobs = [pack_standard_frame(idx) for _, idx in GAME_FRAMES_ELWOOD]
with open(out_bin, 'wb') as f:
    f.write(b''.join(all_blobs))
total_bytes = len(all_blobs) * 480
print(f'Generat {out_bin}: {total_bytes} bytes ({len(all_blobs)} frames x 480 B)')

out_dance = r'assets/bbdata/DANCE.BIN'
dance_blobs = [pack_standard_frame(idx) for _, idx in DANCE_FRAMES]
with open(out_dance, 'wb') as f:
    f.write(b''.join(dance_blobs))
print(f'Generat {out_dance}: {len(dance_blobs) * 480} bytes ({len(dance_blobs)} frames x 480 B)')

hdr = ['#ifndef ELWOOD_FRAMES_H', '#define ELWOOD_FRAMES_H', '',
       '#include "cpctelera.h"', '',
       '// Frames autentics d\'Elwood (DOS) - 16 px Mode 0 (8 bytes x 30 = 480 B)',
       '// Banc proposat 0xC3 (lliure), base 0x4000. REVISAR a F0.2.',
       '#define ELWOOD_FRAMES_BANK 0xC3',
       '#define ELWOOD_FRAMES_BASE 0x4000',
       '#define ELWOOD_FRAME_SIZE 480',
       f'#define ELWOOD_FRAMES_COUNT {len(GAME_FRAMES_ELWOOD)}',
       '// Dansa select (DANCE.BIN, amb FRONT):',
       f'#define DANCE_FRAMES_COUNT {len(DANCE_FRAMES)}',
       '// 0..5 Jake A (33-38), 6..8 Jake B (21-23),',
       '// 9..13 Elwood A (51,71,72,73,100), 14..19 Elwood B (88,83,84,85,86,87)']
for k, (name, _) in enumerate(GAME_FRAMES_ELWOOD):
    hdr.append('// %2d (%5d): %s' % (k, k * 480, name))
hdr.append('')
hdr.append('#endif')

with open('src/elwood_frames.h', 'w', encoding='utf-8') as f:
    f.write('\n'.join(hdr) + '\n')
print('Actualitzat src/elwood_frames.h!')
