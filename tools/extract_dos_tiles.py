#!/usr/bin/env python3
"""extract_dos_tiles.py - Extreu els tiles originals de DOS per als 6 nivells del joc
per comparar-los directament amb la versió CPC.

Genera a cada carpeta graphics_edit/levelX_.../:
1. tileset_dos.png : Graella 16x16 tiles (256x256 px) amb la paleta original VGA de DOS.
2. tileset_cpc_aspect.png : El tileset CPC (256x256 px) escalat 2x per superposar 1:1 amb DOS.
3. dos_tiles/ : Carpeta amb els 256 tiles individuals (tile_000.png .. tile_255.png a 16x16 px).
4. comparison_cpc_vs_dos.png : Full comparatiu visual amb CPC i DOS costat a costat per a cada tile.
"""
import os
import sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from unsqz import unsqz
from ilbm import read_ilbm
from graphics_tool import decode_mode0_byte, DEFAULT_PALETTES, HW_TO_COLOR

LEVELS = [
    {"lid": 0, "folder": "level1_magasin", "name": "Nivell 1 - Magatzem", "prefix": "MAG", "tileset_bin": "TILESET0.BIN"},
    {"lid": 1, "folder": "level2_factory", "name": "Nivell 2 - Fàbrica", "prefix": "ENT", "tileset_bin": "TILESET1.BIN"},
    {"lid": 2, "folder": "level3_prison", "name": "Nivell 3 - Presó", "prefix": "PRISON", "tileset_bin": "TILESET2.BIN"},
    {"lid": 3, "folder": "level4_sewers", "name": "Nivell 4 - Clavegueres", "prefix": "EGOU", "tileset_bin": "TILESET3.BIN"},
    {"lid": 4, "folder": "level5_city", "name": "Nivell 5 - Ciutat", "prefix": "VILLE", "tileset_bin": "TILESET4.BIN"},
    {"lid": 5, "folder": "level6_concert", "name": "Nivell 6 - Concert", "prefix": "CONCERT", "tileset_bin": "TILESET5.BIN"},
]

def process_level(lv):
    lid = lv["lid"]
    out_dir = os.path.join(PROJ, "graphics_edit", lv["folder"])
    indiv_dir = os.path.join(out_dir, "dos_tiles")
    os.makedirs(indiv_dir, exist_ok=True)
    bb = os.path.join(PROJ, "assets", "bbdata")

    # 1. Carregar .CK1 i .CK2 de DOS
    p1 = os.path.join(bb, f"{lv['prefix']}.CK1")
    p2 = os.path.join(bb, f"{lv['prefix']}.CK2")
    d1 = unsqz(open(p1, "rb").read())
    w1, h1, pl1, pal1, px1 = read_ilbm(d1)
    d2 = unsqz(open(p2, "rb").read())
    w2, h2, pl2, pal2, px2 = read_ilbm(d2)

    dos_pal_rgb = pal1[:16]
    pil_dos_pal = []
    for r, g, b in dos_pal_rgb:
        pil_dos_pal.extend([r, g, b])
    while len(pil_dos_pal) < 256 * 3:
        pil_dos_pal.extend([0, 0, 0])

    # Extreure 256 tiles DOS de 16x16
    ck = [px1, px2]
    tiles_dos = []
    for h in range(2):
        px = ck[h]
        for num in range(128):
            tr, tc = num // 20, num % 20
            tile = []
            for y in range(16):
                row = []
                for x in range(16):
                    row.append(px[tr * 16 + y][tc * 16 + x])
                tile.append(row)
            tiles_dos.append(tile)

    # 2. Generar tileset_dos.png (256x256 px)
    img_dos = Image.new("P", (256, 256), 0)
    img_dos.putpalette(pil_dos_pal)
    pix_dos = img_dos.load()

    for t_idx, tile in enumerate(tiles_dos):
        col = t_idx % 16
        row = t_idx // 16
        tx = col * 16
        ty = row * 16
        for y in range(16):
            for x in range(16):
                pix_dos[tx + x, ty + y] = tile[y][x]

    dos_path = os.path.join(out_dir, "tileset_dos.png")
    img_dos.save(dos_path)

    # 3. Generar tiles individuals a dos_tiles/
    for t_idx, tile in enumerate(tiles_dos):
        t_img = Image.new("P", (16, 16), 0)
        t_img.putpalette(pil_dos_pal)
        t_pix = t_img.load()
        for y in range(16):
            for x in range(16):
                t_pix[x, y] = tile[y][x]
        t_img.save(os.path.join(indiv_dir, f"tile_{t_idx:03d}.png"))

    # 4. Generar tileset_cpc_aspect.png (256x256 px) escalat 2x en horitzontal
    cpc_tileset_path = os.path.join(out_dir, "tileset.png")
    if os.path.exists(cpc_tileset_path):
        cpc_im = Image.open(cpc_tileset_path)
        cpc_256 = Image.new("P", (256, 256), 0)
        cpc_256.putpalette(cpc_im.getpalette())
        pix_cpc = cpc_im.load()
        pix_256 = cpc_256.load()
        for row in range(16):
            for col in range(16):
                for y in range(16):
                    for x in range(8):
                        val = pix_cpc[col * 8 + x, row * 16 + y]
                        pix_256[col * 16 + x * 2, row * 16 + y] = val
                        pix_256[col * 16 + x * 2 + 1, row * 16 + y] = val
        cpc_aspect_path = os.path.join(out_dir, "tileset_cpc_aspect.png")
        cpc_256.save(cpc_aspect_path)

    # 5. Generar full comparatiu visual: comparison_cpc_vs_dos.png
    comp_w = 16 * 40
    comp_h = 16 * 36
    comp_img = Image.new("RGB", (comp_w, comp_h), (25, 25, 30))
    draw = ImageDraw.Draw(comp_img)

    cpc_rgb_pal = [HW_TO_COLOR[hw]["rgb"] for hw in DEFAULT_PALETTES[lid]]
    t_raw = open(os.path.join(bb, lv["tileset_bin"]), "rb").read()
    cpc_tiles = []
    for t in range(256):
        tb = t_raw[t * 64 : (t + 1) * 64]
        t_rows = []
        for r in range(16):
            rb = tb[r * 4 : (r + 1) * 4]
            rp = []
            for b in rb:
                p0, p1 = decode_mode0_byte(b)
                rp.extend([p0, p1])
            t_rows.append(rp)
        cpc_tiles.append(t_rows)

    for t_idx in range(256):
        col = t_idx % 16
        row = t_idx // 16
        bx = col * 40 + 2
        by = row * 36 + 2

        draw.rectangle([bx, by, bx + 36, by + 32], outline=(60, 60, 75))

        # Dibuixar CPC a l'esquerra (16x16 escalat)
        c_tile = cpc_tiles[t_idx]
        for y in range(16):
            for x in range(8):
                rgb = tuple(cpc_rgb_pal[c_tile[y][x]])
                draw.point((bx + 2 + x * 2, by + 2 + y), fill=rgb)
                draw.point((bx + 2 + x * 2 + 1, by + 2 + y), fill=rgb)

        # Dibuixar DOS a la dreta (16x16)
        d_tile = tiles_dos[t_idx]
        for y in range(16):
            for x in range(16):
                rgb = tuple(dos_pal_rgb[d_tile[y][x]])
                draw.point((bx + 19 + x, by + 2 + y), fill=rgb)

        draw.text((bx + 2, by + 19), f"{t_idx:03d}", fill=(180, 180, 190))

    comp_path = os.path.join(out_dir, "comparison_cpc_vs_dos.png")
    comp_img.save(comp_path)
    print(f"[{lv['folder']}] Tiles DOS extrets i comparativa generada a {out_dir}")

def main():
    print("=== EXTRAIENT TILES DOS I COMPARATIVES PER ALS 6 NIVELLS ===")
    for lv in LEVELS:
        process_level(lv)
    print("\n[OK] Tots els nivells processats correctament!")

if __name__ == "__main__":
    main()
