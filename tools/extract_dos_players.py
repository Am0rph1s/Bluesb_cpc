#!/usr/bin/env python3
"""extract_dos_players.py - Extreu la selecció exacta dels frames de Jake i Elwood
en versió original de DOS (32x30 px per cel·la, graella de 6x5 cel·les = 192x150 px)
per comparar-los directament amb la versió CPC.

Genera a graphics_edit/player_jake/ i graphics_edit/player_elwood/:
1. jake_dos.png / elwood_dos.png : Graella 6x5 de cel·les de 32x30 px (192x150 px RGBA)
   amb els colors VGA originals de DOS.
2. jake_cpc_aspect.png / elwood_cpc_aspect.png : El sprite de CPC escalat 2x en horitzontal
   (192x150 px) per superposar en capes 1:1 directament.
3. jake_comparison.png / elwood_comparison.png : Full comparatiu visual amb CPC i DOS
   costat a costat per a cadascun dels 29 frames etiquetats.
4. dos_frames/ : Carpeta amb els 29 frames individuals (frame_00_idle.png .. frame_28_dazed3.png).
"""
import os
import sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from sprites import load_sqv_frames
from generate_cpc_jake_dos import GAME_FRAMES as JAKE_FRAMES
from generate_cpc_elwood_dos import GAME_FRAMES_ELWOOD as ELWOOD_FRAMES

# Paleta VGA original de DOS per als personatges
raw_pal = [
    0x000, 0xc77, 0x989, 0x669, 0x147, 0xfda, 0xdb9, 0xf87,
    0x4af, 0x050, 0x091, 0x111, 0xbcf, 0xa20, 0x630, 0xfff
]
vga_pal = [
    (((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17)
    for v in raw_pal
]

PLAYERS = [
    {
        "id": "jake",
        "folder": "player_jake",
        "name": "Jake Blues",
        "frames": JAKE_FRAMES,
        "png_name": "jake.png",
        "dos_png": "jake_dos.png",
        "cpc_aspect_png": "jake_cpc_aspect.png",
        "comp_png": "jake_comparison.png",
    },
    {
        "id": "elwood",
        "folder": "player_elwood",
        "name": "Elwood Blues",
        "frames": ELWOOD_FRAMES,
        "png_name": "elwood.png",
        "dos_png": "elwood_dos.png",
        "cpc_aspect_png": "elwood_cpc_aspect.png",
        "comp_png": "elwood_comparison.png",
    },
]

SWIM_SET = {45, 46, 47, 48, 49, 95, 96, 97, 98, 99}
FLOAT_SET = {39, 89}

def make_dos_player_cell(sqv_frame, idx):
    w, h, px = sqv_frame
    cell_w, cell_h = 32, 30
    box = [[0] * cell_w for _ in range(cell_h)]

    min_x, max_x = w, 0
    for y in range(h):
        for x in range(w):
            if px[y][x] != 0:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
    bw = max_x - min_x + 1 if max_x >= min_x else w

    if idx in SWIM_SET:
        y_shift = (cell_h - min(h, cell_h)) // 2
    elif idx in FLOAT_SET:
        y_shift = 0
    else:
        y_shift = cell_h - min(h, cell_h)

    x_shift = (cell_w - min(w, cell_w)) // 2

    for y in range(min(h, cell_h)):
        oy = y + y_shift
        if 0 <= oy < cell_h:
            for xd in range(cell_w):
                if bw > 32 and idx in SWIM_SET:
                    xdos = min_x + (xd * bw) // cell_w
                else:
                    xdos = xd - x_shift
                if 0 <= xdos < w:
                    val = px[y][xdos]
                    if val != 0:
                        box[oy][xd] = val
    return box

def process_player(pl, all_sqv_frames):
    out_dir = os.path.join(PROJ, "graphics_edit", pl["folder"])
    frames_dir = os.path.join(out_dir, "dos_frames")
    os.makedirs(frames_dir, exist_ok=True)

    cols = 6
    rows = 5
    cell_w = 32
    cell_h = 30

    # 1. Generar jake_dos.png / elwood_dos.png (192x150 px RGBA)
    img_dos = Image.new("RGBA", (cols * cell_w, rows * cell_h), (0, 0, 0, 0))
    pix_dos = img_dos.load()

    dos_cells = []
    for f_idx, (f_name, sqv_idx) in enumerate(pl["frames"]):
        cell_box = make_dos_player_cell(all_sqv_frames[sqv_idx], sqv_idx)
        dos_cells.append((f_name, cell_box))

        col = f_idx % cols
        row = f_idx // cols
        cx = col * cell_w
        cy = row * cell_h

        # Dibuixar a la graella completa
        for y in range(cell_h):
            for x in range(cell_w):
                val = cell_box[y][x]
                if val != 0:
                    r, g, b = vga_pal[val]
                    pix_dos[cx + x, cy + y] = (r, g, b, 255)

        # Dibuixar frame individual a dos_frames/
        f_img = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
        f_pix = f_img.load()
        for y in range(cell_h):
            for x in range(cell_w):
                val = cell_box[y][x]
                if val != 0:
                    r, g, b = vga_pal[val]
                    f_pix[x, y] = (r, g, b, 255)
        f_img.save(os.path.join(frames_dir, f"frame_{f_idx:02d}_{f_name}.png"))

    dos_out_path = os.path.join(out_dir, pl["dos_png"])
    img_dos.save(dos_out_path)
    print(f"[{pl['folder']}] Generat {dos_out_path} (192x150 px, cel·les de 32x30 px)")

    # 2. Generar jake_cpc_aspect.png / elwood_cpc_aspect.png (192x150 px)
    # Agafa jake.png (96x150 px, cel·les de 16x30) i l'escala 2x en horitzontal
    cpc_png_path = os.path.join(out_dir, pl["png_name"])
    if os.path.exists(cpc_png_path):
        im_cpc = Image.open(cpc_png_path).convert("RGBA")
        im_cpc_aspect = Image.new("RGBA", (cols * cell_w, rows * cell_h), (0, 0, 0, 0))
        pix_src = im_cpc.load()
        pix_dst = im_cpc_aspect.load()

        for c_idx in range(len(pl["frames"])):
            col = c_idx % cols
            row = c_idx // cols
            cx_src = col * 16
            cy_src = row * 30
            cx_dst = col * 32
            cy_dst = row * 30

            for y in range(30):
                for x in range(16):
                    rgba = pix_src[cx_src + x, cy_src + y]
                    pix_dst[cx_dst + x * 2, cy_dst + y] = rgba
                    pix_dst[cx_dst + x * 2 + 1, cy_dst + y] = rgba

        cpc_aspect_path = os.path.join(out_dir, pl["cpc_aspect_png"])
        im_cpc_aspect.save(cpc_aspect_path)
        print(f"[{pl['folder']}] Generat {cpc_aspect_path} (192x150 px, superposició 1:1)")

    # 3. Generar full comparatiu visual: comparison.png
    # 6 columnes x 5 files de blocs. Cada bloc fa 76x48 px
    comp_w = cols * 76
    comp_h = rows * 50
    comp_img = Image.new("RGB", (comp_w, comp_h), (25, 25, 30))
    draw = ImageDraw.Draw(comp_img)

    cpc_aspect_img = Image.open(os.path.join(out_dir, pl["cpc_aspect_png"]))

    for f_idx, (f_name, _) in enumerate(pl["frames"]):
        col = f_idx % cols
        row = f_idx // cols
        bx = col * 76 + 2
        by = row * 50 + 2

        # Marc
        draw.rectangle([bx, by, bx + 72, by + 46], outline=(60, 60, 75))

        # Crop CPC (32x30)
        cpc_crop = cpc_aspect_img.crop((col * 32, row * 30, (col + 1) * 32, (row + 1) * 30))
        comp_img.paste(cpc_crop, (bx + 2, by + 2), cpc_crop)

        # Crop DOS (32x30)
        dos_crop = img_dos.crop((col * 32, row * 30, (col + 1) * 32, (row + 1) * 30))
        comp_img.paste(dos_crop, (bx + 38, by + 2), dos_crop)

        # Etiqueta
        draw.text((bx + 2, by + 34), f"{f_idx:02d} {f_name[:7]}", fill=(180, 180, 190))

    comp_path = os.path.join(out_dir, pl["comp_png"])
    comp_img.save(comp_path)
    print(f"[{pl['folder']}] Generat {comp_path} (full comparatiu visual etiquetat)")

def main():
    print("=== EXTRAIENT FRAMES DOS I COMPARATIVES PER A JAKE I ELWOOD ===")
    sqv_path = os.path.join(PROJ, "assets", "bbdata", "SPRITE.SQV")
    all_sqv_frames = load_sqv_frames(sqv_path)
    print(f"Carregats {len(all_sqv_frames)} frames de SPRITE.SQV")

    for pl in PLAYERS:
        process_player(pl, all_sqv_frames)

    print("\n[OK] Jake i Elwood processats correctament!")

if __name__ == "__main__":
    main()
