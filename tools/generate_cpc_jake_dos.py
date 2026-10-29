# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, 'tools/bbdata')
from sprites import load_sqv_frames

frames = load_sqv_frames(r'assets/bbdata/SPRITE.SQV')

# Mapatge autèntic DOS VGA -> Pen Mode 0 Amstrad CPC
# Paleta Mode 0 configurada a engine/video.s:
# Pen 0  = BLANC PUR per a la camisa (pen en desús a les tiles del nivell) (0x4B)
# Pen 1  = Rosa / Carn (cara, mans) (0x47)
# Pen 2  = Gris canonada/metàl·lic (restaurat per al nivell) (0x40)
# Pen 3  = Gris mitjà (0x40)
# Pen 4  = Blau vestit (reflex) (0x44)
# Pen 8  = Blau cel (0x57)
# Pen 11 = Negre sòlid (vestit, barret, ulleres) (0x54)
# Pen 12 = Blau pastel (0x5F)
# Pen 13 = Vermell fosc (0x5C)
# Pen 15 = Gris clar / núvols (0x40)
dos_to_cpc_pen = {
    0:  None, # Transparent
    1:  1,    # Rosa / Carn
    2:  12,   # Blau pastel
    3:  11,   # Negre sòlid vestit (Pen 11)
    4:  4,    # Blau vestit
    5:  1,    # Rosa / Carn clara
    6:  1,    # Rosa / Carn mitja
    7:  1,    # Rosa / Carn
    8:  0,    # BLANC PUR camisa (Pen 0 exclusiu per al personatge)
    9:  9,    # Verd
    10: 10,   # Verd brillant
    11: 11,   # Negre vestit / barret / ulleres (Pen 11)
    12: 0,    # BLANC PUR camisa (Pen 0)
    13: 13,   # Vermell fosc
    14: 13,   # Vermell fosc
    15: 0     # BLANC PUR (Pen 0)
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
        img |= ((p & 1) << 6) | (((p >> 2) & 1) << 4) | (((p >> 1) & 1) << 2) | ((p >> 3) & 1)
    inv_mask = (~mask) & 0xFF
    img_masked = img & mask
    return inv_mask, img_masked

def pack_standard_frame(idx):
    w, h, px = frames[idx]
    # Ample Mode 0 complet: 16 píxels Mode 0 = 32 píxels DOS = 8 bytes
    w_m0 = 16
    
    # Comprovar bounding box per a frames més amples de 32 px (ex: natació)
    min_x, max_x = w, 0
    for y in range(h):
        for x in range(w):
            if px[y][x] != 0:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
    bw = max_x - min_x + 1 if max_x >= min_x else 0

    if idx in (45, 46, 47, 48, 49):
        y_shift = (30 - h) // 2
    elif idx == 39:
        y_shift = 0
    else:
        y_shift = 30 - h
        
    x_shift = (w_m0 - ((w + 1) // 2)) // 2
    
    box = [[None] * 16 for _ in range(30)]
    for y in range(h):
        out_y = y + y_shift
        if 0 <= out_y < 30:
            for xm in range(16):
                if bw > 32 and idx in (45, 46, 47, 48):
                    xdos0 = min_x + (xm * bw) // 16
                    xdos1 = min_x + ((xm * 2 + 1) * bw) // 32
                else:
                    xdos0 = (xm - x_shift) * 2
                    xdos1 = xdos0 + 1
                p0 = px[y][xdos0] if 0 <= xdos0 < w else 0
                p1 = px[y][xdos1] if 0 <= xdos1 < w else 0
                
                # Seleccionar color prioritari (prioritzar camisa/detalls sobre contorns)
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

# 26 frames complets de gameplay (amb natació DOS completa)
# 26 frames x 480 bytes = 12.480 bytes (caben exactament al Banc 7)
GAME_FRAMES = [
    # 0..3: Caminar i aturat
    ('idle',  1),
    ('walk1', 2),
    ('walk2', 0),
    ('walk3', 3),
    # 4..5: Salt i caiguda
    ('jump',  7), # agafant-se el barret (32 px DOS complets, sense peus tallats!)
    ('ladder_back',  8), # reservat per a escales, no usar en aire
    # 6..8: Ajupit (duck 1, crawl 2, crawl 3 - 32 px DOS complets!)
    ('crouch1', 4),
    ('crouch2', 5),
    ('crouch3', 6),
    # 9..11: Escala de mà (9) + Ball d'interrogant/meta (10..11, DOS 33 i 35 / animframe_0135)
    ('ladder1', 9),
    ('dance1',  33),
    ('dance2',  35),
    # 12..17: Caixes (portar, caminar, agafar)
    ('crate_walk1', 13),
    ('crate_walk2', 14),
    ('crate_walk3', 15),
    ('crate_walk4', 16),
    ('crate_walk5', 17),
    ('crate_lift',  12),
    # 18..19: Empènyer, llançar
    ('crate_throw', 18),
    ('crate_push',  20),
    # 20: Vol amb globus / paraigües (DOS 39)
    ('carry_float', 39),
    # 21..25: Natació a les peixeres (DOS 48, 46, 47, 49, 45)
    ('swim_idle',    48), # surant diagonal / quiet (DOS 48 / animframe_017e)
    ('swim_stroke1', 46), # braçada 1 (DOS 46 / animframe_016d)
    ('swim_stroke2', 47), # braçada 2 (DOS 47 / animframe_016d)
    ('swim_vert',    49), # nedar vertical amunt/avall (DOS 49 / animframe_0182)
    ('swim_floor',   45), # fons de la peixera (DOS 45 / animframe_0180)
    # 26..28: Estabornit amb estrelletes girant sobre el cap (DOS 27, 28, 29 / animframe_0115)
    ('dazed1',       27),
    ('dazed2',       28),
    ('dazed3',       29),
]

out_bin = r'assets/bbdata/PFRAMES.BIN'
all_blobs = []
for name, idx in GAME_FRAMES:
    all_blobs.append(pack_standard_frame(idx))

with open(out_bin, 'wb') as f:
    f.write(b''.join(all_blobs))

total_bytes = len(all_blobs) * 480
print(f'Generat {out_bin}: {total_bytes} bytes ({len(GAME_FRAMES)} frames x 480 B)')

hdr = ['#ifndef PLAYER_FRAMES_H', '#define PLAYER_FRAMES_H', '',
       '#include "cpctelera.h"', '',
       '// Frames autèntics de Jake (DOS 16 colors) al Banc 7 - 16 px Mode 0 (8 bytes x 30 = 480 B)',
       '#define PLAYER_FRAMES_BANK 0xC7',
       '#define PLAYER_FRAMES_BASE 0x4000',
       '#define PLAYER_FRAME_SIZE 480',
       f'#define PLAYER_FRAMES_COUNT {len(GAME_FRAMES)}']

for k, (name, _) in enumerate(GAME_FRAMES):
    hdr.append('// %2d (%5d): %s' % (k, k * 480, name))
hdr.append('')
hdr.append('#endif')

with open('src/player_frames.h', 'w', encoding='utf-8') as f:
    f.write('\n'.join(hdr) + '\n')
print('Actualitzat src/player_frames.h!')
