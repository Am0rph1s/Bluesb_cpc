#!/usr/bin/env python3
"""graphics_tool.py - Eina d'exportació i importació de gràfics per a Blues Brothers CPC.

Permet extreure els tilesets i enemics de cada nivell en carpetes individuals
amb imatges PNG editables amb la seva paleta oficial Mode 0, i reimportar-los
directament al joc després de la seva modificació.

Ús:
  py -3 tools/graphics_tool.py export
  py -3 tools/graphics_tool.py import
"""
import os
import sys
import json
import struct
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BBDATA = os.path.join(PROJ, "assets", "bbdata")
EXPORT_DIR = os.path.join(PROJ, "graphics_edit")

# Taula completa oficial dels 27 colors de l'Amstrad CPC (Locomotive BASIC INK 0..26)
CPC_27_COLORS = [
    {"ink": 0,  "hw": 0x54, "rgb": [0, 0, 0],       "name": "Black"},
    {"ink": 1,  "hw": 0x44, "rgb": [0, 0, 128],     "name": "Blue"},
    {"ink": 2,  "hw": 0x55, "rgb": [0, 0, 255],     "name": "Bright Blue"},
    {"ink": 3,  "hw": 0x5C, "rgb": [128, 0, 0],     "name": "Red"},
    {"ink": 4,  "hw": 0x58, "rgb": [128, 0, 128],   "name": "Magenta"},
    {"ink": 5,  "hw": 0x5D, "rgb": [128, 0, 255],   "name": "Mauve"},
    {"ink": 6,  "hw": 0x4C, "rgb": [255, 0, 0],     "name": "Bright Red"},
    {"ink": 7,  "hw": 0x45, "rgb": [255, 0, 128],   "name": "Purple"},
    {"ink": 8,  "hw": 0x4D, "rgb": [255, 0, 255],   "name": "Bright Magenta"},
    {"ink": 9,  "hw": 0x56, "rgb": [0, 128, 0],     "name": "Green"},
    {"ink": 10, "hw": 0x46, "rgb": [0, 128, 128],   "name": "Cyan"},
    {"ink": 11, "hw": 0x57, "rgb": [0, 128, 255],   "name": "Sky Blue"},
    {"ink": 12, "hw": 0x5E, "rgb": [128, 128, 0],   "name": "Yellow"},
    {"ink": 13, "hw": 0x40, "rgb": [128, 128, 128], "name": "White / Gray"},
    {"ink": 14, "hw": 0x5F, "rgb": [128, 128, 255], "name": "Pastel Blue"},
    {"ink": 15, "hw": 0x4E, "rgb": [255, 128, 0],   "name": "Orange"},
    {"ink": 16, "hw": 0x47, "rgb": [255, 128, 128], "name": "Pink"},
    {"ink": 17, "hw": 0x4F, "rgb": [255, 128, 255], "name": "Pastel Magenta"},
    {"ink": 18, "hw": 0x52, "rgb": [0, 255, 0],     "name": "Bright Green"},
    {"ink": 19, "hw": 0x42, "rgb": [0, 255, 128],   "name": "Sea Green"},
    {"ink": 20, "hw": 0x53, "rgb": [0, 255, 255],   "name": "Bright Cyan"},
    {"ink": 21, "hw": 0x5A, "rgb": [128, 255, 0],   "name": "Lime Green"},
    {"ink": 22, "hw": 0x59, "rgb": [128, 255, 128], "name": "Pastel Green"},
    {"ink": 23, "hw": 0x5B, "rgb": [128, 255, 255], "name": "Pastel Cyan"},
    {"ink": 24, "hw": 0x4A, "rgb": [255, 255, 0],   "name": "Bright Yellow"},
    {"ink": 25, "hw": 0x43, "rgb": [255, 255, 128], "name": "Pastel Yellow"},
    {"ink": 26, "hw": 0x4B, "rgb": [255, 255, 255], "name": "Bright White"},
]

HW_TO_COLOR = {c["hw"]: c for c in CPC_27_COLORS}

def closest_cpc_color(r, g, b):
    best_c = CPC_27_COLORS[0]
    best_d = 1 << 30
    for c in CPC_27_COLORS:
        cr, cg, cb = c["rgb"]
        d = (r - cr)**2 + (g - cg)**2 + (b - cb)**2
        if d < best_d:
            best_d = d
            best_c = c
    return best_c

LEVEL_INFO = [
    {"id": 0, "folder": "level1_magasin", "name": "Nivell 1 - Magatzem (Magasin)", "tileset_bin": "TILESET0.BIN", "enemy_bin": "ENEMI1.BIN"},
    {"id": 1, "folder": "level2_factory", "name": "Nivell 2 - Fàbrica (Entrepot)",  "tileset_bin": "TILESET1.BIN", "enemy_bin": "ENEMI2.BIN"},
    {"id": 2, "folder": "level3_prison",  "name": "Nivell 3 - Presó (Prison)",     "tileset_bin": "TILESET2.BIN", "enemy_bin": "ENEMI3.BIN"},
    {"id": 3, "folder": "level4_sewers",  "name": "Nivell 4 - Clavegueres (Égout)", "tileset_bin": "TILESET3.BIN", "enemy_bin": "ENEMI4.BIN"},
    {"id": 4, "folder": "level5_city",    "name": "Nivell 5 - Ciutat (Ville)",      "tileset_bin": "TILESET4.BIN", "enemy_bin": "ENEMI5.BIN"},
    {"id": 5, "folder": "level6_concert", "name": "Nivell 6 - Concert (Concert)",  "tileset_bin": "TILESET5.BIN", "enemy_bin": "ENEMI6.BIN"},
]

SCREEN_INFO = [
    {
        "folder": "screen_splash",
        "name": "Pantalla de Títol / Splash",
        "bin": "SPLASH.BIN",
        "palhw": "SPLASH.PALHW",
        "png": "splash.png",
    },
    {
        "folder": "screen_map",
        "name": "Pantalla del Mapa (Inter-nivells)",
        "bin": "MAP.BIN",
        "palhw": "MAP.PALHW",
        "png": "map.png",
    },
]

PLAYER_INFO = [
    {
        "folder": "player_jake",
        "name": "Jake Blues (Jugador 1)",
        "bin": "PFRAMES.BIN",
        "png": "jake.png",
        "frames_count": 29,
        "cols": 6,
        "rows": 5,
        "cell_w": 16,
        "cell_h": 30,
        "default_palette": [0x4B, 0x47, 0x40, 0x40, 0x44, 0x43, 0x5B, 0x4C, 0x57, 0x56, 0x52, 0x54, 0x5F, 0x5C, 0x5C, 0x40],
    },
    {
        "folder": "player_elwood",
        "name": "Elwood Blues (Jugador 2)",
        "bin": "ELWOOD.BIN",
        "png": "elwood.png",
        "frames_count": 29,
        "cols": 6,
        "rows": 5,
        "cell_w": 16,
        "cell_h": 30,
        "default_palette": [0x4B, 0x47, 0x40, 0x40, 0x44, 0x43, 0x5B, 0x4C, 0x57, 0x56, 0x52, 0x54, 0x5F, 0x5C, 0x5C, 0x40],
    },
]

FRAME_NAMES = [
    "00_idle",
    "01_walk1",
    "02_walk2",
    "03_walk3",
    "04_jump",
    "05_ladder_back",
    "06_crouch1",
    "07_crouch2",
    "08_crouch3",
    "09_ladder1",
    "10_dance1",
    "11_dance2",
    "12_crate_walk1",
    "13_crate_walk2",
    "14_crate_walk3",
    "15_crate_walk4",
    "16_crate_walk5",
    "17_crate_lift",
    "18_crate_throw",
    "19_crate_push",
    "20_carry_float",
    "21_swim_idle",
    "22_swim_stroke1",
    "23_swim_stroke2",
    "24_swim_vert",
    "25_swim_floor",
    "26_dazed1",
    "27_dazed2",
    "28_dazed3",
]

# Paletes oficials per defecte (Mode 0)
DEFAULT_PALETTES = [
    [0x4B, 0x47, 0x40, 0x40, 0x44, 0x43, 0x5B, 0x4C, 0x57, 0x56, 0x52, 0x54, 0x5F, 0x5C, 0x5C, 0x40],
    [0x4B, 0x47, 0x40, 0x46, 0x44, 0x47, 0x5E, 0x47, 0x57, 0x5E, 0x5E, 0x54, 0x40, 0x5C, 0x5C, 0x40],
    [0x4B, 0x47, 0x40, 0x5F, 0x44, 0x43, 0x47, 0x5C, 0x57, 0x56, 0x52, 0x54, 0x5B, 0x4C, 0x5E, 0x4B],
    [0x4B, 0x47, 0x5E, 0x46, 0x46, 0x47, 0x5F, 0x40, 0x54, 0x40, 0x40, 0x54, 0x40, 0x5E, 0x46, 0x5B],
    [0x4B, 0x47, 0x5E, 0x40, 0x44, 0x5C, 0x45, 0x4F, 0x46, 0x58, 0x5B, 0x54, 0x5B, 0x54, 0x58, 0x4B],
    [0x4B, 0x47, 0x40, 0x40, 0x44, 0x43, 0x5C, 0x47, 0x46, 0x5C, 0x4E, 0x54, 0x54, 0x5C, 0x4A, 0x5F],
]

def decode_mode0_byte(b):
    p0_0 = (b >> 7) & 1
    p1_0 = (b >> 6) & 1
    p0_2 = (b >> 5) & 1
    p1_2 = (b >> 4) & 1
    p0_1 = (b >> 3) & 1
    p1_1 = (b >> 2) & 1
    p0_3 = (b >> 1) & 1
    p1_3 = b & 1
    p0 = p0_0 | (p0_1 << 1) | (p0_2 << 2) | (p0_3 << 3)
    p1 = p1_0 | (p1_1 << 1) | (p1_2 << 2) | (p1_3 << 3)
    return p0, p1

def encode_mode0_byte(p0, p1):
    p0 = int(p0) & 0x0F
    p1 = int(p1) & 0x0F
    return (
        ((p0 & 1) << 7) |
        ((p1 & 1) << 6) |
        (((p0 >> 2) & 1) << 5) |
        (((p1 >> 2) & 1) << 4) |
        (((p0 >> 1) & 1) << 3) |
        (((p1 >> 1) & 1) << 2) |
        (((p0 >> 3) & 1) << 1) |
        ((p1 >> 3) & 1)
    )

def decode_enemy_pair(inv, img):
    pen0 = None if (inv & 0xAA) else (((img >> 7) & 1) | (((img >> 3) & 1) << 1) | (((img >> 5) & 1) << 2) | (((img >> 1) & 1) << 3))
    pen1 = None if (inv & 0x55) else (((img >> 6) & 1) | (((img >> 2) & 1) << 1) | (((img >> 4) & 1) << 2) | ((img & 1) << 3))
    return pen0, pen1

def encode_enemy_pair(pen0, pen1):
    mask = 0
    img = 0
    if pen0 is not None and pen0 >= 0:
        mask |= 0xAA
        p = int(pen0) & 0x0F
        img |= ((p & 1) << 7) | (((p >> 2) & 1) << 5) | (((p >> 1) & 1) << 3) | (((p >> 3) & 1) << 1)
    if pen1 is not None and pen1 >= 0:
        mask |= 0x55
        p = int(pen1) & 0x0F
        img |= ((p & 1) << 6) | (((p >> 2) & 1) << 4) | (((p >> 1) & 1) << 2) | ((p >> 3) & 1)
    return (~mask) & 0xFF, img & mask

def export_assets():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    print("=== EXPORTANT GRÀFICS DEL JOC A 'graphics_edit/' ===")

    # Desar taula de referència de colors CPC
    ref_path = os.path.join(EXPORT_DIR, "CPC_27_COLORS_REFERENCE.json")
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(CPC_27_COLORS, f, indent=2)

    for lv in LEVEL_INFO:
        lid = lv["id"]
        out_folder = os.path.join(EXPORT_DIR, lv["folder"])
        os.makedirs(out_folder, exist_ok=True)

        hw_pal = DEFAULT_PALETTES[lid]
        rgb_pal = [HW_TO_COLOR[hw]["rgb"] for hw in hw_pal]
        pil_pal = []
        for c in rgb_pal:
            pil_pal.extend(c)
        while len(pil_pal) < 256 * 3:
            pil_pal.extend([0, 0, 0])

        # 1. Palette JSON
        pal_json = []
        for pen, hw in enumerate(hw_pal):
            c_info = HW_TO_COLOR[hw]
            pal_json.append({
                "pen": pen,
                "ink_number": c_info["ink"],
                "ga_code": "0x%02X" % hw,
                "rgb": c_info["rgb"],
                "color_name": c_info["name"]
            })
        with open(os.path.join(out_folder, "palette.json"), "w", encoding="utf-8") as f:
            json.dump(pal_json, f, indent=2)

        # 2. Export Tileset (256 tiles x 64 B = 16.384 B)
        # Graella: 16 columnes x 16 files de tiles. Cada tile és de 8 px d'ample x 16 px d'alt.
        # Imatge final: 128 x 256 píxels.
        t_path = os.path.join(BBDATA, lv["tileset_bin"])
        if os.path.exists(t_path):
            t_raw = open(t_path, "rb").read()
            assert len(t_raw) == 16384, (t_path, len(t_raw))
            img_tiles = Image.new("P", (128, 256), 0)
            img_tiles.putpalette(pil_pal)
            pixels = img_tiles.load()

            for t_idx in range(256):
                tile_bytes = t_raw[t_idx * 64 : (t_idx + 1) * 64]
                tx = (t_idx % 16) * 8
                ty = (t_idx // 16) * 16
                for row in range(16):
                    row_bytes = tile_bytes[row * 4 : (row + 1) * 4]
                    col = 0
                    for b in row_bytes:
                        p0, p1 = decode_mode0_byte(b)
                        pixels[tx + col, ty + row] = p0
                        pixels[tx + col + 1, ty + row] = p1
                        col += 2

            tiles_png_path = os.path.join(out_folder, "tileset.png")
            img_tiles.save(tiles_png_path)
            print(f"[{lv['folder']}] Tileset exportat: {tiles_png_path} (128x256 px, 256 tiles)")

        # 3. Export Enemies (16 celes x 512 B = 8.192 B)
        # Graella: 4 columnes x 4 files de celes. Cada cela és de 16 px d'ample x 32 px d'alt.
        # Imatge final: 64 x 128 píxels RGBA (amb fons transparent).
        e_path = os.path.join(BBDATA, lv["enemy_bin"])
        if os.path.exists(e_path):
            e_raw = open(e_path, "rb").read()
            assert len(e_raw) == 8192, (e_path, len(e_raw))
            img_enemies = Image.new("RGBA", (64, 128), (0, 0, 0, 0))
            epixels = img_enemies.load()

            for c_idx in range(16):
                cell_bytes = e_raw[c_idx * 512 : (c_idx + 1) * 512]
                cx = (c_idx % 4) * 16
                cy = (c_idx // 4) * 32
                for row in range(32):
                    row_bytes = cell_bytes[row * 16 : (row + 1) * 16]
                    col = 0
                    for pair_idx in range(8):
                        inv = row_bytes[pair_idx * 2]
                        img = row_bytes[pair_idx * 2 + 1]
                        pen0, pen1 = decode_enemy_pair(inv, img)
                        if pen0 is not None:
                            r, g, b = rgb_pal[pen0]
                            epixels[cx + col, cy + row] = (r, g, b, 255)
                        if pen1 is not None:
                            r, g, b = rgb_pal[pen1]
                            epixels[cx + col + 1, cy + row] = (r, g, b, 255)
                        col += 2

            enemies_png_path = os.path.join(out_folder, "enemies.png")
            img_enemies.save(enemies_png_path)
            print(f"[{lv['folder']}] Enemics exportats: {enemies_png_path} (64x128 px, 16 celes, fons transparent)")

        # 4. Export Full Level Map (muntat complet per provar paletes)
        m_path = os.path.join(BBDATA, f"MAP{lid}.BIN")
        if os.path.exists(t_path) and os.path.exists(m_path):
            t_raw = open(t_path, "rb").read()
            m_raw = open(m_path, "rb").read()
            map_w = 128
            map_h = len(m_raw) // map_w

            decoded_tiles = []
            for t_idx in range(256):
                tile_bytes = t_raw[t_idx * 64 : (t_idx + 1) * 64]
                t_rows = []
                for row in range(16):
                    r_bytes = tile_bytes[row * 4 : (row + 1) * 4]
                    r_pens = []
                    for b in r_bytes:
                        p0, p1 = decode_mode0_byte(b)
                        r_pens.extend([p0, p1])
                    t_rows.append(r_pens)
                decoded_tiles.append(t_rows)

            img_m0 = Image.new("P", (map_w * 8, map_h * 16), 0)
            img_m0.putpalette(pil_pal)
            pix_m0 = img_m0.load()

            for my in range(map_h):
                for mx in range(map_w):
                    t_idx = m_raw[my * map_w + mx]
                    t_rows = decoded_tiles[t_idx]
                    for ty in range(16):
                        for tx in range(8):
                            pix_m0[mx * 8 + tx, my * 16 + ty] = t_rows[ty][tx]

            map_m0_path = os.path.join(out_folder, "map_mode0.png")
            img_m0.save(map_m0_path)

            img_full = img_m0.resize((img_m0.width * 2, img_m0.height), Image.NEAREST)
            map_full_path = os.path.join(out_folder, "map_full.png")
            img_full.save(map_full_path)
            print(f"[{lv['folder']}] Mapa complet muntat: {map_full_path} ({img_full.width}x{img_full.height} px, Mode P 16 colors)")

    # 5. Export Screens (Splash, Map, etc.)
    for sc in SCREEN_INFO:
        out_folder = os.path.join(EXPORT_DIR, sc["folder"])
        os.makedirs(out_folder, exist_ok=True)
        palhw_path = os.path.join(BBDATA, sc["palhw"])
        if not os.path.exists(palhw_path):
            continue
        hw_pal = list(open(palhw_path, "rb").read()[:16])
        rgb_pal = [HW_TO_COLOR[hw]["rgb"] for hw in hw_pal]
        pil_pal = []
        for c in rgb_pal:
            pil_pal.extend(c)
        while len(pil_pal) < 256 * 3:
            pil_pal.extend([0, 0, 0])

        # Palette JSON
        pal_json = []
        for pen, hw in enumerate(hw_pal):
            c_info = HW_TO_COLOR[hw]
            pal_json.append({
                "pen": pen,
                "ink_number": c_info["ink"],
                "ga_code": "0x%02X" % hw,
                "rgb": c_info["rgb"],
                "color_name": c_info["name"]
            })
        with open(os.path.join(out_folder, "palette.json"), "w", encoding="utf-8") as f:
            json.dump(pal_json, f, indent=2)

        # Export Screen (16.384 B VRAM Mode 0 entrellaçada -> 160x200 PNG)
        bin_path = os.path.join(BBDATA, sc["bin"])
        if os.path.exists(bin_path):
            raw = open(bin_path, "rb").read()
            assert len(raw) == 16384, (bin_path, len(raw))
            img_sc = Image.new("P", (160, 200), 0)
            img_sc.putpalette(pil_pal)
            pixels = img_sc.load()

            for y in range(200):
                base = (y % 8) * 2048 + (y // 8) * 80
                for xb in range(80):
                    byte = raw[base + xb]
                    p0, p1 = decode_mode0_byte(byte)
                    pixels[xb * 2, y] = p0
                    pixels[xb * 2 + 1, y] = p1

            sc_png_path = os.path.join(out_folder, sc["png"])
            img_sc.save(sc_png_path)
            print(f"[{sc['folder']}] Pantalla exportada: {sc_png_path} (160x200 px, Mode 0)")

    # 5. Export Players (Jake & Elwood)
    for pl in PLAYER_INFO:
        out_folder = os.path.join(EXPORT_DIR, pl["folder"])
        os.makedirs(out_folder, exist_ok=True)
        hw_pal = pl["default_palette"]
        rgb_pal = [HW_TO_COLOR[hw]["rgb"] for hw in hw_pal]

        # Palette JSON
        pal_json = []
        for pen, hw in enumerate(hw_pal):
            c_info = HW_TO_COLOR[hw]
            pal_json.append({
                "pen": pen,
                "ink_number": c_info["ink"],
                "ga_code": "0x%02X" % hw,
                "rgb": c_info["rgb"],
                "color_name": c_info["name"]
            })
        with open(os.path.join(out_folder, "palette.json"), "w", encoding="utf-8") as f:
            json.dump(pal_json, f, indent=2)

        # Guia de frames
        guide_path = os.path.join(out_folder, "frames_guide.txt")
        with open(guide_path, "w", encoding="utf-8") as f:
            f.write(f"Guia de frames per a {pl['name']}:\n")
            f.write("Graella: 6 columnes x 5 files. Mida de cada cel·la: 16x30 píxels.\n")
            f.write("Mida total de la imatge: 96x150 píxels (canal alfa transparent per al fons).\n\n")
            for idx, fname in enumerate(FRAME_NAMES):
                col = idx % 6
                row = idx // 6
                f.write(f"Frame {idx:02d} (Columna {col}, Fila {row}): {fname}\n")

        # Export PNG (96x150 RGBA transparent)
        bin_path = os.path.join(BBDATA, pl["bin"])
        if os.path.exists(bin_path):
            raw = open(bin_path, "rb").read()
            assert len(raw) == pl["frames_count"] * 480, (bin_path, len(raw))
            img_pl = Image.new("RGBA", (pl["cols"] * pl["cell_w"], pl["rows"] * pl["cell_h"]), (0, 0, 0, 0))
            pixels = img_pl.load()

            for c_idx in range(pl["frames_count"]):
                col = c_idx % pl["cols"]
                row = c_idx // pl["cols"]
                cx = col * pl["cell_w"]
                cy = row * pl["cell_h"]
                cell_bytes = raw[c_idx * 480 : (c_idx + 1) * 480]

                for y in range(pl["cell_h"]):
                    row_bytes = cell_bytes[y * 16 : (y + 1) * 16]
                    for pair_idx in range(8):
                        inv = row_bytes[pair_idx * 2]
                        img = row_bytes[pair_idx * 2 + 1]
                        pen0, pen1 = decode_enemy_pair(inv, img)
                        if pen0 is not None:
                            r, g, b = rgb_pal[pen0]
                            pixels[cx + pair_idx * 2, cy + y] = (r, g, b, 255)
                        if pen1 is not None:
                            r, g, b = rgb_pal[pen1]
                            pixels[cx + pair_idx * 2 + 1, cy + y] = (r, g, b, 255)

            pl_png_path = os.path.join(out_folder, pl["png"])
            img_pl.save(pl_png_path)
            print(f"[{pl['folder']}] Jugador exportat: {pl_png_path} (96x150 px, 29 frames, RGBA)")

    # Crear fitxer README explicatiu
    readme_path = os.path.join(EXPORT_DIR, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("""# Edició de Gràfics i Paletes - Blues Brothers CPC

Aquesta carpeta conté tots els gràfics dels 6 nivells, pantalles fixes i personatges protagonistes (Jake i Elwood), preparats per ser editats amb qualsevol editor (Aseprite, Photoshop, GIMP, GrafX2, etc.).

## Estructura per subcarpetes

### 1. Personatges protagonistes:
- `player_jake/`: Jake Blues (`jake.png`, **96 x 150 px**, graella de 6x5 cel·les de 16x30 px, RGBA transparent). Inclou `frames_guide.txt` i `palette.json`.
- `player_elwood/`: Elwood Blues (`elwood.png`, **96 x 150 px**, graella de 6x5 cel·les de 16x30 px, RGBA transparent). Inclou `frames_guide.txt` i `palette.json`.

### 2. Nivells de joc:
- `level1_magasin/` (Magatzem)
- `level2_factory/` (Fàbrica)
- `level3_prison/` (Presó)
- `level4_sewers/` (Clavegueres)
- `level5_city/` (Ciutat i teulades)
- `level6_concert/` (Concert final)

A cada carpeta de nivell trobaràs:
- `map_full.png`: **Mapa complet del nivell muntat** (**2048 x H px**, proporció 4:3 de pantalla CPC). Format Mode 'P' (16 colors) amb la paleta del nivell. **Ideal per provar paletes** en viu!
- `map_mode0.png`: El mateix mapa complet en resolució nativa Mode 0 (**1024 x H px**, tiles de 8x16 px).
- `tileset.png`: Graella de **16x16 tiles** (total 256 tiles, cadascun de 8x16 píxels). Mida imatge: **128 x 256 px**. Mode indexat (16 colors) amb la paleta exacte del nivell.
- `enemies.png`: Graella de **4x4 cel·les** d'enemics (total 16 cel·les, cadascuna de 16x32 píxels). Mida imatge: **64 x 128 px**. Els píxels transparents són canal Alpha transparent (o fons buit).
- `palette.json`: Descripció dels 16 colors (pens 0..15) emprats pel nivell.

### 3. Pantalles fixes:
- `screen_splash/`: Pantalla de títol / logo del joc (`splash.png`, **160 x 200 px**, Mode 0 indexat 16 colors) + `palette.json`.
- `screen_map/`: Pantalla del mapa de la ciutat entre nivells (`map.png`, **160 x 200 px**, Mode 0 indexat 16 colors) + `palette.json`.

## Com modificar la paleta
- Pots canviar els colors directament a la paleta del programa d'edició (o modificant `palette.json`).
- Consulta `CPC_27_COLORS_REFERENCE.json` per conèixer els 27 colors que la màquina real CPC pot reproduir. Quan importem els gràfics, cada color RGB s'ajustarà automàticament al color CPC equivalent més proper.

## Com integrar els canvis al joc
Quan acabis d'editar i desis els PNGs, avisa'm al xat o executa:
```bash
py -3 tools/graphics_tool.py import
```
L'eina reconstruirà automàticament els fitxers binaris, empaquetarà els nivells, recomprimirà pantalles ZX0, actualitzarà Jake i Elwood al Banc 7 i generarà el disc `bluesb.dsk` amb els teus canvis integrats 100%!
""")
    print("\n[OK] Tots els gràfics i paletes han estat exportats correctament!")

def import_assets():
    print("=== REIMPORTANT GRÀFICS EDITATS DES DE 'graphics_edit/' ===")
    palettes_changed = False
    levels_changed = set()
    new_palettes = [list(p) for p in DEFAULT_PALETTES]

    for lv in LEVEL_INFO:
        lid = lv["id"]
        folder = os.path.join(EXPORT_DIR, lv["folder"])
        if not os.path.exists(folder):
            continue

        # 1. Llegir paleta (primer provar de palette.json si existeix, o del PNG)
        pal_json_path = os.path.join(folder, "palette.json")
        hw_pal = list(DEFAULT_PALETTES[lid])
        if os.path.exists(pal_json_path):
            with open(pal_json_path, "r", encoding="utf-8") as f:
                pj = json.load(f)
                for item in pj:
                    pen = item["pen"]
                    if "ga_code" in item:
                        hw_pal[pen] = int(item["ga_code"], 16)
                    elif "hw_code" in item:
                        hw_pal[pen] = int(item["hw_code"], 16)
                    elif "rgb" in item:
                        c = closest_cpc_color(*item["rgb"])
                        hw_pal[pen] = c["hw"]
        else:
            # Si el PNG té paleta indexada modificada (comprovant tileset.png o map_full.png):
            for pal_img_name in ("map_full.png", "map_mode0.png", "tileset.png"):
                img_path = os.path.join(folder, pal_img_name)
                if os.path.exists(img_path):
                    im_chk = Image.open(img_path)
                    if im_chk.mode == "P":
                        raw_pal = im_chk.getpalette()
                        if raw_pal and len(raw_pal) >= 48:
                            for pen in range(16):
                                r, g, b = raw_pal[pen*3 : pen*3+3]
                                c = closest_cpc_color(r, g, b)
                                hw_pal[pen] = c["hw"]
                            break

        tiles_png_path = os.path.join(folder, "tileset.png")
        edit_png_path = os.path.join(folder, "edit", "tileset_edit.png")
        if os.path.exists(edit_png_path):
            import shutil
            shutil.copy2(edit_png_path, tiles_png_path)
            print(f"[{lv['folder']}] Sincronitzat {edit_png_path} -> {tiles_png_path}")

        new_palettes[lid] = hw_pal
        rgb_pal = [HW_TO_COLOR[hw]["rgb"] for hw in hw_pal]

        # 2. Reimportar Tileset
        if os.path.exists(tiles_png_path):
            im_t = Image.open(tiles_png_path).convert("RGBA")
            assert im_t.size == (128, 256), f"Mida incorrecta de tileset {im_t.size}"
            pix = im_t.load()
            out_tiles = bytearray(16384)

            # Funció auxiliar per mapejar un píxel RGB al pen 0..15 del nivell
            def rgb_to_pen(r, g, b):
                best_pen = 0
                best_d = 1 << 30
                for pen, (pr, pg, pb) in enumerate(rgb_pal):
                    d = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
                    if d < best_d:
                        best_d = d
                        best_pen = pen
                return best_pen

            for t_idx in range(256):
                tx = (t_idx % 16) * 8
                ty = (t_idx // 16) * 16
                tile_bytes = bytearray()
                for row in range(16):
                    for xb in range(4):
                        r0, g0, b0, _ = pix[tx + xb * 2, ty + row]
                        r1, g1, b1, _ = pix[tx + xb * 2 + 1, ty + row]
                        p0 = rgb_to_pen(r0, g0, b0)
                        p1 = rgb_to_pen(r1, g1, b1)
                        tile_bytes.append(encode_mode0_byte(p0, p1))
                out_tiles[t_idx * 64 : (t_idx + 1) * 64] = tile_bytes

            dst_bin = os.path.join(BBDATA, lv["tileset_bin"])
            old_bin = open(dst_bin, "rb").read() if os.path.exists(dst_bin) else b""
            if bytes(out_tiles) != old_bin:
                with open(dst_bin, "wb") as f:
                    f.write(out_tiles)
                print(f"[{lv['folder']}] Tileset reimportat a {dst_bin}")
                levels_changed.add(lid)

        # 3. Reimportar Enemies
        enemies_png_path = os.path.join(folder, "enemies.png")
        for edit_cand in ("enemies_cpc.png", "enemies_edit.png"):
            edit_enemies_path = os.path.join(folder, "edit", edit_cand)
            if os.path.exists(edit_enemies_path):
                import shutil
                shutil.copy2(edit_enemies_path, enemies_png_path)
                print(f"[{lv['folder']}] Sincronitzat {edit_enemies_path} -> {enemies_png_path}")
                break
        if os.path.exists(enemies_png_path):
            im_e = Image.open(enemies_png_path).convert("RGBA")
            assert im_e.size == (64, 128), f"Mida incorrecta de enemies {im_e.size}"
            epix = im_e.load()
            out_enemies = bytearray(8192)

            for c_idx in range(16):
                cx = (c_idx % 4) * 16
                cy = (c_idx // 4) * 32
                cell_bytes = bytearray()
                for row in range(32):
                    for pair_idx in range(8):
                        x0 = cx + pair_idx * 2
                        x1 = x0 + 1
                        y = cy + row
                        r0, g0, b0, a0 = epix[x0, y]
                        r1, g1, b1, a1 = epix[x1, y]
                        p0 = None if a0 < 128 else rgb_to_pen(r0, g0, b0)
                        p1 = None if a1 < 128 else rgb_to_pen(r1, g1, b1)
                        inv, img = encode_enemy_pair(p0, p1)
                        cell_bytes.append(inv)
                        cell_bytes.append(img)
                out_enemies[c_idx * 512 : (c_idx + 1) * 512] = cell_bytes

            dst_ebin = os.path.join(BBDATA, lv["enemy_bin"])
            old_ebin = open(dst_ebin, "rb").read() if os.path.exists(dst_ebin) else b""
            if bytes(out_enemies) != old_ebin:
                with open(dst_ebin, "wb") as f:
                    f.write(out_enemies)
                print(f"[{lv['folder']}] Enemics reimportats a {dst_ebin}")
                levels_changed.add(lid)

    # Reimportar pantalles fixes (Splash, Map, etc.)
    screens_changed = False
    for sc in SCREEN_INFO:
        folder = os.path.join(EXPORT_DIR, sc["folder"])
        if not os.path.exists(folder):
            continue

        palhw_path = os.path.join(BBDATA, sc["palhw"])
        cur_palhw = list(open(palhw_path, "rb").read()[:16]) if os.path.exists(palhw_path) else [0]*16
        new_palhw = list(cur_palhw)

        # 1. Palette JSON
        pal_json_path = os.path.join(folder, "palette.json")
        if os.path.exists(pal_json_path):
            with open(pal_json_path, "r", encoding="utf-8") as f:
                pj = json.load(f)
                for item in pj:
                    pen = item["pen"]
                    if "ga_code" in item:
                        new_palhw[pen] = int(item["ga_code"], 16)
                    elif "hw_code" in item:
                        new_palhw[pen] = int(item["hw_code"], 16)
                    elif "rgb" in item:
                        c = closest_cpc_color(*item["rgb"])
                        new_palhw[pen] = c["hw"]

        png_path = os.path.join(folder, sc["png"])
        if os.path.exists(png_path):
            im_sc = Image.open(png_path)
            # Paleta del PNG si és indexat
            if im_sc.mode == "P":
                raw_pal = im_sc.getpalette()
                if raw_pal:
                    for pen in range(16):
                        r, g, b = raw_pal[pen*3 : pen*3+3]
                        c = closest_cpc_color(r, g, b)
                        new_palhw[pen] = c["hw"]

            rgb_pal = [HW_TO_COLOR[hw]["rgb"] for hw in new_palhw]

            def rgb_to_pen_sc(r, g, b):
                best_pen = 0
                best_d = 1 << 30
                for pen, (pr, pg, pb) in enumerate(rgb_pal):
                    d = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
                    if d < best_d:
                        best_d = d
                        best_pen = pen
                return best_pen

            out_vram = bytearray(16384)
            if im_sc.mode == "P":
                assert im_sc.size == (160, 200), f"Mida incorrecta de pantalla {im_sc.size}"
                pix_p = im_sc.load()
                for y in range(200):
                    base = (y % 8) * 2048 + (y // 8) * 80
                    for xb in range(80):
                        p0 = pix_p[xb * 2, y] & 0x0F
                        p1 = pix_p[xb * 2 + 1, y] & 0x0F
                        out_vram[base + xb] = encode_mode0_byte(p0, p1)
            else:
                im_rgba = im_sc.convert("RGBA")
                assert im_rgba.size == (160, 200), f"Mida incorrecta de pantalla {im_rgba.size}"
                pix_rgba = im_rgba.load()
                for y in range(200):
                    base = (y % 8) * 2048 + (y // 8) * 80
                    for xb in range(80):
                        r0, g0, b0, _ = pix_rgba[xb * 2, y]
                        r1, g1, b1, _ = pix_rgba[xb * 2 + 1, y]
                        p0 = rgb_to_pen_sc(r0, g0, b0)
                        p1 = rgb_to_pen_sc(r1, g1, b1)
                        out_vram[base + xb] = encode_mode0_byte(p0, p1)

            dst_bin = os.path.join(BBDATA, sc["bin"])
            old_bin = open(dst_bin, "rb").read() if os.path.exists(dst_bin) else b""
            if bytes(out_vram) != old_bin:
                with open(dst_bin, "wb") as f:
                    f.write(out_vram)
                print(f"[{sc['folder']}] Pantalla VRAM actualitzada a {dst_bin}")
                screens_changed = True

        if new_palhw != cur_palhw:
            with open(palhw_path, "wb") as f:
                f.write(bytes(new_palhw))
            print(f"[{sc['folder']}] Paleta HW actualitzada a {palhw_path}")
            screens_changed = True

    # Reimportar personatges (Jake i Elwood)
    players_changed = False
    for pl in PLAYER_INFO:
        folder = os.path.join(EXPORT_DIR, pl["folder"])
        if not os.path.exists(folder):
            continue

        hw_pal = list(pl["default_palette"])
        pal_json_path = os.path.join(folder, "palette.json")
        if os.path.exists(pal_json_path):
            with open(pal_json_path, "r", encoding="utf-8") as f:
                pj = json.load(f)
                for item in pj:
                    pen = item["pen"]
                    if "ga_code" in item:
                        hw_pal[pen] = int(item["ga_code"], 16)
                    elif "ga_code" in item:
                        hw_pal[pen] = int(item["ga_code"], 16)
                    elif "hw_code" in item:
                        hw_pal[pen] = int(item["hw_code"], 16)
                    elif "rgb" in item:
                        c = closest_cpc_color(*item["rgb"])
                        hw_pal[pen] = c["hw"]

        rgb_pal = [HW_TO_COLOR[hw]["rgb"] for hw in hw_pal]

        def rgb_to_pen_pl(r, g, b):
            best_pen = 0
            best_d = 1 << 30
            for pen, (pr, pg, pb) in enumerate(rgb_pal):
                d = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
                if d < best_d:
                    best_d = d
                    best_pen = pen
            return best_pen

        png_path = os.path.join(folder, pl["png"])
        if os.path.exists(png_path):
            im_pl = Image.open(png_path).convert("RGBA")
            assert im_pl.size == (pl["cols"] * pl["cell_w"], pl["rows"] * pl["cell_h"]), f"Mida incorrecta de {pl['png']}: {im_pl.size}"
            pix = im_pl.load()
            out_bin = bytearray(pl["frames_count"] * 480)

            for c_idx in range(pl["frames_count"]):
                col = c_idx % pl["cols"]
                row = c_idx // pl["cols"]
                cx = col * pl["cell_w"]
                cy = row * pl["cell_h"]
                cell_bytes = bytearray()

                for y in range(pl["cell_h"]):
                    for pair_idx in range(8):
                        x0 = cx + pair_idx * 2
                        x1 = x0 + 1
                        yp = cy + y
                        r0, g0, b0, a0 = pix[x0, yp]
                        r1, g1, b1, a1 = pix[x1, yp]
                        p0 = None if a0 < 128 else rgb_to_pen_pl(r0, g0, b0)
                        p1 = None if a1 < 128 else rgb_to_pen_pl(r1, g1, b1)
                        inv, img = encode_enemy_pair(p0, p1)
                        cell_bytes.append(inv)
                        cell_bytes.append(img)

                out_bin[c_idx * 480 : (c_idx + 1) * 480] = cell_bytes

            dst_bin = os.path.join(BBDATA, pl["bin"])
            old_bin = open(dst_bin, "rb").read() if os.path.exists(dst_bin) else b""
            if bytes(out_bin) != old_bin:
                with open(dst_bin, "wb") as f:
                    f.write(out_bin)
                print(f"[{pl['folder']}] Personatge actualitzat a {dst_bin}")
                players_changed = True

    # Comprovar si les paletes han canviat respecte a DEFAULT_PALETTES
    if new_palettes != DEFAULT_PALETTES:
        for _i in range(6): levels_changed.add(_i)
        print("[Paleta] Actualitzant paletes a pack_level.py...")
        pl_path = os.path.join(HERE, "pack_level.py")
        txt = open(pl_path, "r", encoding="utf-8").read()
        import pprint
        pal_code = "LEVEL_PALETTES = [\n"
        for p in new_palettes:
            pal_code += "    [" + ", ".join("0x%02X" % x for x in p) + "],\n"
        pal_code += "]"
        import re
        txt = re.sub(r"LEVEL_PALETTES\s*=\s*\[[^\]]+\]", pal_code, txt, flags=re.DOTALL)
        open(pl_path, "w", encoding="utf-8").write(txt)

    # Executar pack_level.py per als nivells modificats
    if levels_changed:
        print(f"\nExecutant compactació dels nivells modificats ({sorted(levels_changed)})...\n")
        import pack_level
        for lid in sorted(levels_changed):
            out_dir = os.path.join(PROJ, "src") if lid == 0 else os.path.join(PROJ, "obj", f"lvl{lid}")
            pack_level.build_level_pkg(lid, out_dir=out_dir)

    if players_changed:
        import build
        build.build_level_bundles(force=False)

    print("\nExecutant reconstrucció del projecte (build.py)...")
    import build
    build.main()
    print("\n[OK] Reimportació completada i DSK actualitzat amb èxit!")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("import", "--import"):
        import_assets()
    else:
        export_assets()
