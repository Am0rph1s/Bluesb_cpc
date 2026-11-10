#!/usr/bin/env python3
"""extract_dos_enemies.py - Extreu la selecció exacta dels sprites d'enemics
en versió original de DOS (32x32 px per cel·la) amb el mateix ordre de cel·les (4x4)
per als 6 nivells del joc.

Genera a cada carpeta graphics_edit/levelX_.../:
1. enemies_dos.png : Graella 4x4 de cel·les de 32x32 px (128x128 px RGBA transparent)
   amb els colors VGA originals de DOS.
2. enemies_cpc_aspect.png : El enemies.png de CPC escalat 2x en horitzontal (128x128 px)
   per superposar en capes 1:1 directament.
3. enemies_comparison.png : Full comparatiu visual amb CPC i DOS costat a costat
   per a cadascuna de les 16 cel·les etiquetades.
"""
import os
import sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from sprites import load_sqv_frames
from unsqz import unsqz
from ilbm import read_ilbm

import gen_enemy_frames as ge1
import gen_enemy2_frames as ge2
import gen_enemy3_frames as ge3
import gen_enemy4_frames as ge4
import gen_enemy5_frames as ge5
import gen_enemy6_frames as ge6

LEVELS_CONFIG = [
    {
        "id": 1,
        "folder": "level1_magasin",
        "name": "Nivell 1 - Magatzem",
        "ck": "MAG.CK1",
        "sqv": "ENEMI1.SQV",
        "module": ge1,
    },
    {
        "id": 2,
        "folder": "level2_factory",
        "name": "Nivell 2 - Fàbrica",
        "ck": "ENT.CK1",
        "sqv": "ENEMI2.SQV",
        "module": ge2,
    },
    {
        "id": 3,
        "folder": "level3_prison",
        "name": "Nivell 3 - Presó",
        "ck": "PRISON.CK1",
        "sqv": "ENEMI3.SQV",
        "module": ge3,
    },
    {
        "id": 4,
        "folder": "level4_sewers",
        "name": "Nivell 4 - Clavegueres",
        "ck": "EGOU.CK1",
        "sqv": "ENEMI4.SQV",
        "module": ge4,
    },
    {
        "id": 5,
        "folder": "level5_city",
        "name": "Nivell 5 - Ciutat",
        "ck": "VILLE.CK1",
        "sqv": "ENEMI5.SQV",
        "module": ge5,
    },
    {
        "id": 6,
        "folder": "level6_concert",
        "name": "Nivell 6 - Concert",
        "ck": "CONCERT.CK1",
        "sqv": "ENEMI6.SQV",
        "module": ge6,
    },
]

def make_cell(w, h, px):
    box = [[0]*32 for _ in range(32)]
    xs = (32 - w) // 2
    ys = 32 - h
    for y in range(h):
        oy = y + ys
        if 0 <= oy < 32:
            for x in range(w):
                ox = x + xs
                if 0 <= ox < 32:
                    box[oy][ox] = px[y][x]
    return box

def get_l1_projectiles(sqv_frames):
    projs = [(20, 0), (12, 13), (40, 19)]
    pbox = [[0]*32 for _ in range(32)]
    for sqv_idx, row_start in projs:
        w, h, px = sqv_frames[sqv_idx]
        xs = (32 - w) // 2
        for y in range(h):
            oy = row_start + y
            if 0 <= oy < 32:
                for x in range(w):
                    ox = x + xs
                    if 0 <= ox < 32:
                        val = px[y][x]
                        if val != 0:
                            pbox[oy][ox] = val
    return pbox

def get_l5_projectiles(sqv_frames):
    projs = [(4, 0), (32, 13), (12, 19)]
    pbox = [[0]*32 for _ in range(32)]
    for sqv_idx, row_start in projs:
        w, h, px = sqv_frames[sqv_idx]
        xs = (32 - w) // 2
        for y in range(h):
            oy = row_start + y
            if 0 <= oy < 32:
                for x in range(w):
                    ox = x + xs
                    if 0 <= ox < 32:
                        val = px[y][x]
                        if val != 0:
                            pbox[oy][ox] = val
    return pbox

def main():
    bb = os.path.join(PROJ, "assets", "bbdata")
    l1_sqv_frames = load_sqv_frames(os.path.join(bb, "ENEMI1.SQV"))
    l1_proj_cell = get_l1_projectiles(l1_sqv_frames)

    for cfg in LEVELS_CONFIG:
        lid = cfg["id"]
        out_dir = os.path.join(PROJ, "graphics_edit", cfg["folder"])
        os.makedirs(out_dir, exist_ok=True)

        # 1. Carregar paleta DOS del nivell des de .CK1
        ck_path = os.path.join(bb, cfg["ck"])
        d = unsqz(open(ck_path, "rb").read())
        _, _, _, pal_raw, _ = read_ilbm(d)
        dos_pal = pal_raw[:16]

        # 2. Carregar frames SQV del nivell
        sqv_path = os.path.join(bb, cfg["sqv"])
        sqv_frames = load_sqv_frames(sqv_path)
        mod = cfg["module"]

        cells = [[[0]*32 for _ in range(32)] for _ in range(16)]

        if lid == 1:
            for i, (kind, idx) in enumerate(mod.CELLS):
                w, h, px = sqv_frames[idx]
                cells[i] = make_cell(w, h, px)
            cells[13] = l1_proj_cell
            for i, (kind, idx) in enumerate(mod.POSE_CELLS):
                w, h, px = sqv_frames[idx]
                cells[14 + i] = make_cell(w, h, px)
        else:
            for cell_idx, idx in mod.CELLS:
                w, h, px = sqv_frames[idx]
                if hasattr(mod, "crop_content"):
                    px, w, h = mod.crop_content(px, w, h)
                cells[cell_idx] = make_cell(w, h, px)

            if lid == 5:
                cells[13] = get_l5_projectiles(sqv_frames)
            elif lid == 3:
                cells[12] = l1_proj_cell
            else:
                cells[13] = l1_proj_cell

        # 3. Generar enemies_dos.png (128x128 px RGBA transparent)
        img_dos = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        pix_dos = img_dos.load()

        for c_idx in range(16):
            col = c_idx % 4
            row = c_idx // 4
            cx = col * 32
            cy = row * 32
            c_data = cells[c_idx]
            for y in range(32):
                for x in range(32):
                    val = c_data[y][x]
                    if val != 0:
                        r, g, b = dos_pal[val]
                        pix_dos[cx + x, cy + y] = (r, g, b, 255)

        dos_png_path = os.path.join(out_dir, "enemies_dos.png")
        img_dos.save(dos_png_path)
        print(f"[{cfg['folder']}] Generat {dos_png_path} (128x128 px, cel·les de 32x32 px)")

        # 4. Generar enemies_cpc_aspect.png (128x128 px)
        # Agafa enemies.png (64x128 px, cel·les de 16x32) i l'escala 2x en horitzontal
        cpc_enemies_path = os.path.join(out_dir, "enemies.png")
        if os.path.exists(cpc_enemies_path):
            im_cpc = Image.open(cpc_enemies_path).convert("RGBA")
            im_cpc_aspect = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            pix_src = im_cpc.load()
            pix_dst = im_cpc_aspect.load()
            for row in range(4):
                for col in range(4):
                    cx_src = col * 16
                    cy_src = row * 32
                    cx_dst = col * 32
                    cy_dst = row * 32
                    for y in range(32):
                        for x in range(16):
                            rgba = pix_src[cx_src + x, cy_src + y]
                            pix_dst[cx_dst + x * 2, cy_dst + y] = rgba
                            pix_dst[cx_dst + x * 2 + 1, cy_dst + y] = rgba
            cpc_aspect_path = os.path.join(out_dir, "enemies_cpc_aspect.png")
            im_cpc_aspect.save(cpc_aspect_path)

        # 5. Generar enemies_comparison.png (Full comparatiu 4x4 blocs de [CPC 32x32] [DOS 32x32])
        # Cada bloc fa 72x48 px (inclou marc, CPC 32x32, DOS 32x32 i etiqueta)
        comp_w = 4 * 76
        comp_h = 4 * 52
        comp_img = Image.new("RGB", (comp_w, comp_h), (25, 25, 30))
        draw = ImageDraw.Draw(comp_img)

        cpc_aspect_img = Image.open(os.path.join(out_dir, "enemies_cpc_aspect.png"))

        for c_idx in range(16):
            col = c_idx % 4
            row = c_idx // 4
            bx = col * 76 + 2
            by = row * 52 + 2

            # Marc
            draw.rectangle([bx, by, bx + 72, by + 48], outline=(60, 60, 75))

            # Crop cel·la CPC (32x32) i pegar
            cpc_crop = cpc_aspect_img.crop((col * 32, row * 32, (col + 1) * 32, (row + 1) * 32))
            comp_img.paste(cpc_crop, (bx + 2, by + 2), cpc_crop)

            # Crop cel·la DOS (32x32) i pegar
            dos_crop = img_dos.crop((col * 32, row * 32, (col + 1) * 32, (row + 1) * 32))
            comp_img.paste(dos_crop, (bx + 38, by + 2), dos_crop)

            # Etiqueta
            draw.text((bx + 2, by + 36), f"C{c_idx:02d} CPC", fill=(140, 180, 220))
            draw.text((bx + 40, by + 36), f"DOS", fill=(220, 160, 140))

        comp_path = os.path.join(out_dir, "enemies_comparison.png")
        comp_img.save(comp_path)
        print(f"[{cfg['folder']}] Generat {comp_path} (full comparatiu CPC vs DOS)")

    print("\n[OK] Tots els sprites enemics de DOS s'han extret i comparat correctament!")

if __name__ == "__main__":
    main()
