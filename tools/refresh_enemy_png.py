#!/usr/bin/env python3
"""
refresh_enemy_png.py - Reexporta els PNG d'enemics des dels BINARIS del joc
=============================================================================

Per que:
    Els enemics de L2 i L4 es van extreure 1:1 de DOS el 12/11/2026
    (extract_dos_enemies.py / gen_enemy2_frames.py), pero els PNG de
    graphics_edit/level2_factory/edit/enemies_cpc.png i
    graphics_edit/level4_sewers/edit/enemies_cpc.png eren els ANTICS.
    Amb 'graphics_tool.py import' el fitxer edit/ sobreescriu el PNG principal
    i l'art DOS 1:1 es REGRESIONAVA (ENEMI2/ENEMI4.BIN canviats).

Aquesta eina reexporta el PNG d'enemics d'un nivell a partir del binaire
actual (amb la paleta vigent), de manera que el master editable torna a
coincidir amb el que hi ha al joc.

Us:
    py -3 tools/refresh_enemy_png.py 1 3      # nivells L2 i L4 (index 0..5)
    py -3 tools/refresh_enemy_png.py --all
    py -3 tools/refresh_enemy_png.py 3 --edit  # actualitza tambe edit/enemies_cpc.png
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BBDATA = os.path.join(PROJ, "assets", "bbdata")
EXPORT_DIR = os.path.join(PROJ, "graphics_edit")
sys.path.insert(0, HERE)

from graphics_tool import (  # noqa: E402
    HW_TO_COLOR,
    LEVEL_INFO,
    decode_enemy_pair,
)
from palette_fit import load_pack_level_palettes  # noqa: E402


def export_enemies(lid, pal):
    """Renderitza ENEMI<lid+1>.BIN a graphics_edit/<folder>/enemies.png."""
    folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
    os.makedirs(folder, exist_ok=True)
    rgb = [tuple(HW_TO_COLOR[h]["rgb"]) for h in pal]
    e_path = os.path.join(BBDATA, LEVEL_INFO[lid]["enemy_bin"])
    raw = open(e_path, "rb").read()
    assert len(raw) == 8192, (e_path, len(raw))

    from PIL import Image
    img = Image.new("RGBA", (64, 128), (0, 0, 0, 0))
    px = img.load()
    for c in range(16):
        cx, cy = (c % 4) * 16, (c // 4) * 32
        cell = raw[c * 512:(c + 1) * 512]
        for row in range(32):
            rb = cell[row * 16:(row + 1) * 16]
            for i in range(8):
                p0, p1 = decode_enemy_pair(rb[i * 2], rb[i * 2 + 1])
                if p0 is not None:
                    px[cx + i * 2, cy + row] = rgb[p0] + (255,)
                if p1 is not None:
                    px[cx + i * 2 + 1, cy + row] = rgb[p1] + (255,)
    out = os.path.join(folder, "enemies.png")
    img.save(out)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    also_edit = "--edit" in sys.argv
    pals = load_pack_level_palettes()
    if "--all" in sys.argv:
        lids = list(range(6))
    else:
        lids = [int(a) for a in args]
    for lid in lids:
        folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
        out = export_enemies(lid, pals[lid])
        print("[L%d] enemies.png exportat: %s" % (lid + 1, out))
        if also_edit:
            edit_dir = os.path.join(folder, "edit")
            os.makedirs(edit_dir, exist_ok=True)
            for cand in ("enemies_cpc.png", "enemies_edit.png"):
                dst = os.path.join(edit_dir, cand)
                if os.path.exists(dst) or cand == "enemies_cpc.png":
                    shutil.copy2(out, dst)
                    print("      -> %s actualitzat" % os.path.relpath(dst, PROJ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
