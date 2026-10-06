# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, 'tools/bbdata')
from sprites import load_sqv_frames
from PIL import Image, ImageDraw

frames = load_sqv_frames(r'assets/bbdata/SPRITE.SQV')

raw_pal = [
    0x000, 0xc77, 0x989, 0x669, 0x147, 0xfda, 0xdb9, 0xf87,
    0x4af, 0x050, 0x091, 0x111, 0xbcf, 0xa20, 0x630, 0xfff
]
vga_pal = [
    (((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17)
    for v in raw_pal
]

# Jake original son els frames 0..49
# Creem una fulla dedicada exclusivament a Jake (0..49)
COLS = 10
ROWS = 5
CELL_W = 52
CELL_H = 56

im = Image.new('RGB', (COLS * CELL_W * 2, ROWS * CELL_H * 2), (24, 24, 28))
dr = ImageDraw.Draw(im)

for idx in range(50):
    w, h, px = frames[idx]
    c = idx % COLS
    r = idx // COLS
    ox = c * CELL_W * 2 + 6
    oy = r * CELL_H * 2 + 6
    
    # Text groc amb l'ID i dimensions exactes
    dr.text((ox + 2, oy), f'#{idx:02d} ({w}x{h})', fill=(255, 255, 0))
    
    # Grid de fons tènue per veure l'àrea transparent
    for gy in range(h):
        for gx in range(w):
            bg_col = (30, 30, 35) if (gx + gy) % 2 == 0 else (26, 26, 30)
            im.putpixel((ox + gx * 2, oy + 16 + gy * 2), bg_col)
            im.putpixel((ox + gx * 2 + 1, oy + 16 + gy * 2), bg_col)
            im.putpixel((ox + gx * 2, oy + 16 + gy * 2 + 1), bg_col)
            im.putpixel((ox + gx * 2 + 1, oy + 16 + gy * 2 + 1), bg_col)

    # Dibuix pixel 1:1 original
    for y in range(h):
        for x in range(w):
            val = px[y][x]
            if val != 0:
                rgb = vga_pal[val & 0x0F]
                im.putpixel((ox + x * 2, oy + 16 + y * 2), rgb)
                im.putpixel((ox + x * 2 + 1, oy + 16 + y * 2), rgb)
                im.putpixel((ox + x * 2, oy + 16 + y * 2 + 1), rgb)
                im.putpixel((ox + x * 2 + 1, oy + 16 + y * 2 + 1), rgb)

im.save('tools/jake_dos_vga_raw.png')
print('Desat tools/jake_dos_vga_raw.png!')
