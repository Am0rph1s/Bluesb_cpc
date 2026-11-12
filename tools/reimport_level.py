#!/usr/bin/env python3
"""
reimport_level.py - Reimporta l'art editat d'UN O MES NIVELLS i reconstrueix
=============================================================================

Es una versió focalitzada de `graphics_tool.py import` per a iterar ràpid:
en lloc de reimportar els 6 nivells i reconstruir tot (20 min), reimporta
només els nivells indicats, repacka el seu paquet i reconstrueix.

Fet exactament amb la mateixa lògica de quantització que `graphics_tool.py`
(el pixel es converteix al pen mes proper de la paleta del nivell), incloses
les sobrescriptures `edit/tileset_edit.png` i `edit/enemies_cpc.png`.

Us:
    py -3 tools/reimport_level.py 3            # reimporta L4 i reconstrueix
    py -3 tools/reimport_level.py 1 3 --no-build   # sense reconstruir el disc
    py -3 tools/reimport_level.py 3 --tileset     # només el tileset
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
    encode_mode0_byte,
    encode_enemy_pair,
)
from palette_fit import load_pack_level_palettes  # noqa: E402


def reimport_tileset(lid, pal):
    from PIL import Image
    folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
    png = os.path.join(folder, "tileset.png")
    edit = os.path.join(folder, "edit", "tileset_edit.png")
    if os.path.exists(edit):
        shutil.copy2(edit, png)
        print("[L%d] edit/tileset_edit.png -> tileset.png" % (lid + 1))
    if not os.path.exists(png):
        return False
    rgb = [tuple(HW_TO_COLOR[h]["rgb"]) for h in pal]

    def to_pen(r, g, b):
        best, bd = 0, 1 << 30
        for pen, (pr, pg, pb) in enumerate(rgb):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < bd:
                bd, best = d, pen
        return best

    im = Image.open(png).convert("RGBA")
    assert im.size == (128, 256), im.size
    px = im.load()
    out = bytearray(16384)
    for t in range(256):
        tx, ty = (t % 16) * 8, (t // 16) * 16
        data = bytearray()
        for row in range(16):
            for xb in range(4):
                r0, g0, b0, _ = px[tx + xb * 2, ty + row]
                r1, g1, b1, _ = px[tx + xb * 2 + 1, ty + row]
                data.append(encode_mode0_byte(to_pen(r0, g0, b0), to_pen(r1, g1, b1)))
        out[t * 64:(t + 1) * 64] = data
    dst = os.path.join(BBDATA, LEVEL_INFO[lid]["tileset_bin"])
    old = open(dst, "rb").read() if os.path.exists(dst) else b""
    if bytes(out) != old:
        open(dst, "wb").write(bytes(out))
        print("[L%d] Tileset reimportat: %s" % (lid + 1, dst))
        return True
    print("[L%d] Tileset sense canvis" % (lid + 1))
    return False


def reimport_enemies(lid, pal):
    from PIL import Image
    folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
    png = os.path.join(folder, "enemies.png")
    for cand in ("enemies_cpc.png", "enemies_edit.png"):
        edit = os.path.join(folder, "edit", cand)
        if os.path.exists(edit):
            shutil.copy2(edit, png)
            print("[L%d] edit/%s -> enemies.png" % (lid + 1, cand))
            break
    if not os.path.exists(png):
        return False
    rgb = [tuple(HW_TO_COLOR[h]["rgb"]) for h in pal]

    def to_pen(r, g, b):
        best, bd = 0, 1 << 30
        for pen, (pr, pg, pb) in enumerate(rgb):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < bd:
                bd, best = d, pen
        return best

    im = Image.open(png).convert("RGBA")
    px = im.load()
    out = bytearray()
    for c in range(16):
        cx, cy = (c % 4) * 16, (c // 4) * 32
        for row in range(32):
            for pair in range(8):
                a0 = px[cx + pair * 2, cy + row]
                a1 = px[cx + pair * 2 + 1, cy + row]
                p0 = None if a0[3] < 128 else to_pen(a0[0], a0[1], a0[2])
                p1 = None if a1[3] < 128 else to_pen(a1[0], a1[1], a1[2])
                inv, img = encode_enemy_pair(p0, p1)
                out.append(inv)
                out.append(img)
    dst = os.path.join(BBDATA, LEVEL_INFO[lid]["enemy_bin"])
    old = open(dst, "rb").read() if os.path.exists(dst) else b""
    if bytes(out) != old:
        open(dst, "wb").write(bytes(out))
        print("[L%d] Enemics reimportats: %s" % (lid + 1, dst))
        return True
    print("[L%d] Enemics sense canvis" % (lid + 1))
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lids = [int(a) for a in args]
    if not lids:
        print(__doc__)
        return 1
    do_build = "--no-build" not in sys.argv
    only_tiles = "--tileset" in sys.argv
    only_enemies = "--enemies" in sys.argv
    pals = load_pack_level_palettes()

    changed = []
    for lid in lids:
        if not only_enemies:
            if reimport_tileset(lid, pals[lid]):
                changed.append(lid)
        if not only_tiles:
            if reimport_enemies(lid, pals[lid]):
                changed.append(lid)

    if changed:
        import pack_level
        for lid in sorted(set(changed)):
            out_dir = os.path.join(PROJ, "src") if lid == 0 else os.path.join(PROJ, "obj", "lvl%d" % lid)
            print("Repackant nivell %d..." % (lid + 1))
            pack_level.build_level_pkg(lid, out_dir=out_dir)

    if do_build:
        import build
        build.main()
    print("[OK] Reimportació dels nivells %s completada." % lids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
