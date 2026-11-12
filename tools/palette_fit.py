#!/usr/bin/env python3
"""
palette_fit.py - Ajusta les paletes Mode 0 als colors REALS de l'art editat
=============================================================================

Es una eina de SOL LECTURA per defecte (no toca res). Serveix per resoldre el
problema central del projecte:

    El pipeline d'import (graphics_tool.py) quantitza cada pixel del PNG editat
    al pen mes proper de la paleta del nivell. Per tant:
      - si un color que has posat a l'art NO existeix a la paleta, el tool el
        converteix al color mes proper (canvi silenciós de color!), i
      - si la paleta te dos pens amb el mateix color, un d'ells espta.

Aquesta eina:
  1. Extreu els colors reals de l'art editat (graphics_edit/level*/tileset.png
     i enemies.png) amb el recompte de pixels.
  2. Comprova quants d'aquests colors NO tenen un pen equivalent a la paleta.
  3. Proposa una paleta nova per nivell que:
       - respecta el CONTRACTE d'identitat (pen 0 blanc, 1 pell, 4 blau, 11 negre),
       - dona un pen a TOT color significatiu de l'art,
       - no repeteix colors (cada pen un color diferent).
  4. Pot generar previews (map renderitzat amb la paleta proposada) i, amb
     --apply, escriu la paleta a les tres fonts (pack_level.py, graphics_tool.py
     i graphics_edit/level*/palette.json).

Us:
    py -3 tools/palette_fit.py                # analisi + proposta per pantalla
    py -3 tools/palette_fit.py --preview      # genera previews a scratch/palette_fit/
    py -3 tools/palette_fit.py --apply        # escriu les paletes proposades
    py -3 tools/palette_fit.py --level 3      # nomes un nivell (0..5)

Requisit per aplicar: després de --apply cal tornar a importar l'art
(`py -3 tools/graphics_tool.py import`) perquè els pixels del PNG quedin
assignats als pens nous, i depois reconstruir i verificar en ZEsarUX.
"""
import json
import os
import re
import sys
from collections import Counter
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BBDATA = os.path.join(PROJ, "assets", "bbdata")
EXPORT_DIR = os.path.join(PROJ, "graphics_edit")
PREVIEW_DIR = os.path.join(PROJ, "scratch", "palette_fit")
sys.path.insert(0, HERE)

from graphics_tool import (  # noqa: E402
    CPC_27_COLORS,
    DEFAULT_PALETTES,
    HW_TO_COLOR,
    LEVEL_INFO,
    decode_mode0_byte,
)

# CONTRACTE D'IDENTITAT: pens que comparteixen el jugador (Jake/Elwood) i el HUD.
# El jugador (PFRAMES/ELWOOD) es dibuixa SEMPRE amb la paleta del nivell, aixi
# que aquests pens han de tenir el mateix color a tots els nivells.
CONTRACT = {
    0: 0x4B,   # blanc pur (camisa)
    1: 0x47,   # pell (cara, mans)
    4: 0x44,   # blau marí (vestit)
    11: 0x54,  # negre (vestit, barret, ulleres)
}
# El HUD (tiles del logotip i icones) fa servir a mes: 2, 7, 12, 13.
HUD_PENS = (2, 7, 12, 13)


def closest_hw(rgb):
    r, g, b = rgb
    best, bd = None, 1 << 30
    for c in CPC_27_COLORS:
        d = (r - c["rgb"][0]) ** 2 + (g - c["rgb"][1]) ** 2 + (b - c["rgb"][2]) ** 2
        if d < bd:
            bd, best = d, c
    return best["hw"]


def load_pack_level_palettes():
    txt = open(os.path.join(HERE, "pack_level.py"), "r", encoding="utf-8").read()
    m = re.search(r"LEVEL_PALETTES\s*=\s*\[(.*?)\n\]", txt, re.DOTALL)
    pals = []
    for row in re.findall(r"\[([^\]]*)\]", m.group(1)):
        vals = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", row)]
        if len(vals) == 16:
            pals.append(vals)
    return pals


def art_colors(lid):
    """Colors reals de l'art editat del nivell: RGB -> pixels."""
    folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
    cnt = Counter()
    for png in ("tileset.png", "enemies.png"):
        p = os.path.join(folder, png)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGBA")
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b, a = px[x, y]
                if png == "enemies.png" and a < 128:
                    continue
                cnt[(r, g, b)] += 1
    return cnt


def hw_of_art(cnt):
    """RGB -> (codi GA mes proper, pixels)"""
    per_hw = Counter()
    for rgb, n in cnt.items():
        per_hw[closest_hw(rgb)] += n
    return per_hw


def dos_reference(lid):
    """Paleta DOS/Amiga original del nivell (_colors_data a level.c) -> codi GA."""
    txt = open(os.path.join(HERE, "blues_dos", "bb", "level.c"), encoding="latin1").read()
    m = re.search(r"_colors_data\[16 \* MAX_LEVELS\] = \{(.*?)\};", txt, re.DOTALL)
    vals = [int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{3})", m.group(1))]
    out = []
    for i in range(16):
        v = vals[lid * 16 + i]
        r, g, b = (v >> 8) & 0xF, (v >> 4) & 0xF, v & 0xF
        out.append((closest_hw((r * 17, g * 17, b * 17)), (r * 17, g * 17, b * 17)))
    return out


def fit_level(lid, cur, per_hw, fixed_pens):
    """Proposa una paleta de 16 pens.

    Criteri (per conservar el aspecte actual):
      1. Els pens del contracte tenen el seu color fix.
      2. Un pen que ja te un color que l'art fa servir CONSERVA el color.
      3. Els pens que no son necessaris per l'art reben un color de l'art que
         encara no tingui pen (aqui es on hi ha el canvi real).
      4. Si sobren pens, reben colors nous inedits (cap repetit).
    Retorna (paleta nova, colors de l'art que no hi caben).
    """
    required = [hw for hw, _ in per_hw.most_common()]
    req_set = set(required)

    new = list(cur)
    for p, hw in fixed_pens.items():
        new[p] = hw

    kept = set(new[p] for p in fixed_pens)
    free = [p for p in range(16) if p not in fixed_pens]

    # (2) conservar els colors que l'art fa servir
    for p in free:
        if cur[p] in req_set and cur[p] not in kept:
            new[p] = cur[p]
            kept.add(cur[p])

    def owner_of(hw):
        for q in range(16):
            if new[q] == hw:
                return q
        return None

    # (3) colors de l'art sense pen -> assignar als pens que no el tenen
    missing = [hw for hw in required if hw not in kept]
    for p in free:
        if not missing:
            break
        hw = new[p]
        if hw in req_set and owner_of(hw) == p:
            continue              # aquest pen conserva el seu color de l'art
        new[p] = missing.pop(0)
        kept.add(new[p])

    # (4) cap color repetit. Els pens del CONTRACTE tenen la prioritat: si un
    #     altre pen porta el seu color, es reassigna l'altre.
    all_hw = [c["hw"] for c in CPC_27_COLORS]

    def owner_of(hw):
        for q in fixed_pens:
            if new[q] == hw:
                return q
        for q in range(16):
            if new[q] == hw:
                return q
        return None

    for p in free:
        if owner_of(new[p]) != p:
            cand = [h for h in all_hw if h not in new]
            if cand:
                new[p] = cand[0]
    seen = set(new[p] for p in fixed_pens)
    for p in free:
        if new[p] in seen:
            cand = [h for h in all_hw if h not in new]
            if cand:
                new[p] = cand[0]
        seen.add(new[p])

    still_missing = [hw for hw in required if hw not in new]
    return new, still_missing


def render_preview(lid, cur, new):
    """Renderitza el mapa del nivell amb la paleta actual i amb la proposta."""
    folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
    src = os.path.join(folder, "map_mode0.png")
    if not os.path.exists(src):
        return None
    im = Image.open(src).convert("RGBA")
    px = im.load()
    cur_rgb = [tuple(HW_TO_COLOR[h]["rgb"]) for h in cur]
    new_rgb = [tuple(HW_TO_COLOR[h]["rgb"]) for h in new]
    out = Image.new("RGB", (im.width * 2, im.height), (0, 0, 0))
    opx = out.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            # pixel actual -> color mes proper de la paleta nova (simula l'import)
            best, bd = None, 1 << 30
            for c in new_rgb:
                d = (r - c[0]) ** 2 + (g - c[1]) ** 2 + (b - c[2]) ** 2
                if d < bd:
                    bd, best = d, c
            opx[x, y] = best
            opx[x + im.width, y] = (r, g, b)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    path = os.path.join(PREVIEW_DIR, "L%d_preview.png" % (lid + 1))
    out.save(path)
    return path


def write_palettes(new_palettes):
    """Escriu les tres fonts: pack_level.py, graphics_tool.py i palette.json."""
    names = [
        "L1: Magatzem (magasin)",
        "L2: Fabrica (ent)",
        "L3: Preso (prison)",
        "L4: Clavegueres (egou)",
        "L5: Ciutat / Teulades (ville)",
        "L6: Concert (concert)",
    ]
    code = "LEVEL_PALETTES = [\n"
    for n, p in zip(names, new_palettes):
        code += "    # %s\n" % n
        code += "    [" + ", ".join("0x%02X" % x for x in p) + "],\n"
    code += "]"
    pl_path = os.path.join(HERE, "pack_level.py")
    txt = open(pl_path, "r", encoding="utf-8").read()
    txt = re.sub(r"LEVEL_PALETTES\s*=\s*\[\n.*?^\]", lambda m: code, txt,
                 count=1, flags=re.DOTALL | re.MULTILINE)
    open(pl_path, "w", encoding="utf-8").write(txt)

    gt_path = os.path.join(HERE, "graphics_tool.py")
    gtxt = open(gt_path, "r", encoding="utf-8").read()
    gcode = "DEFAULT_PALETTES = [\n"
    for p in new_palettes:
        gcode += "    [" + ", ".join("0x%02X" % x for x in p) + "],\n"
    gcode += "]"
    gtxt = re.sub(r"DEFAULT_PALETTES\s*=\s*\[\n.*?^\]", lambda m: gcode, gtxt,
                  count=1, flags=re.DOTALL | re.MULTILINE)
    open(gt_path, "w", encoding="utf-8").write(gtxt)

    for lid, pal in enumerate(new_palettes):
        folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
        pj_path = os.path.join(folder, "palette.json")
        if not os.path.exists(pj_path):
            continue
        pj = json.load(open(pj_path, "r", encoding="utf-8"))
        for item in pj:
            hw = pal[int(item["pen"])]
            info = HW_TO_COLOR[hw]
            item["ga_code"] = "0x%02X" % hw
            item["ink_number"] = info["ink"]
            item["rgb"] = info["rgb"]
            item["color_name"] = info["name"]
        json.dump(pj, open(pj_path, "w", encoding="utf-8"), indent=2)


def main():
    args = sys.argv[1:]
    only = None
    if "--level" in args:
        only = int(args[args.index("--level") + 1])
    apply = "--apply" in args
    preview = "--preview" in args

    cur_all = load_pack_level_palettes()
    fixed = dict(CONTRACT)

    print("=" * 78)
    print(" AJUST DE PALETES MODE 0 ALS COLORS REALS DE L'ART EDITAT")
    print("=" * 78)
    print("\n Contracte d'identitat (jugador + HUD): pens %s" %
          ", ".join("%d=%02X" % (p, h) for p, h in sorted(CONTRACT.items())))

    proposals = {}
    for lid in range(6):
        if only is not None and lid != only:
            continue
        tag = "L%d" % (lid + 1)
        cur = cur_all[lid]
        cnt = art_colors(lid)
        per_hw = hw_of_art(cnt)
        missing = []
        for rgb, n in cnt.items():
            if closest_hw(rgb) not in cur:
                missing.append((("%02X%02X%02X" % rgb), n, "%02X" % closest_hw(rgb)))
        missing.sort(key=lambda x: -x[1])

        new, need = fit_level(lid, cur, per_hw, fixed)
        proposals[lid] = new

        print("\n" + "-" * 78)
        print(" %s  paleta actual : %s" % (tag, " ".join("%02X" % v for v in cur)))
        print("      colors de l'art (RGB -> pixels, GA mes proper):")
        for rgb, n in cnt.most_common(14):
            print("        #%02X%02X%02X %6d -> %02X %s" % (
                rgb[0], rgb[1], rgb[2], n, closest_hw(rgb),
                "" if closest_hw(rgb) in cur else "  <-- NO HI HA PEN A LA PALETA"))
        print("      paleta proposada: %s" % " ".join("%02X" % v for v in new))
        diff = [(i, cur[i], new[i]) for i in range(16) if cur[i] != new[i]]
        print("      canvis: %s" % (", ".join(
            "pen%d %02X->%02X" % (i, a, b) for i, a, b in diff) or "cap"))
        dup = {}
        for hw, n in Counter(new).items():
            if n > 1:
                dup["%02X" % hw] = [i for i, v in enumerate(new) if v == hw]
        print("      colors unic=%d/16  duplicats: %s" % (
            len(set(new)), ", ".join("%s->%s" % (k, v) for k, v in sorted(dup.items())) or "cap"))
        if missing:
            print("      ATENCIO %d colors de l'art fora de la paleta: %s" % (
                len(missing), ", ".join("%s(%d)->%s" % m for m in missing[:6])))

        if preview:
            p = render_preview(lid, cur, new)
            if p:
                print("      preview: %s" % p)

    if apply:
        if only is not None:
            new_all = list(cur_all)
            new_all[only] = proposals[only]
        else:
            new_all = [proposals.get(i, cur_all[i]) for i in range(6)]
        write_palettes(new_all)
        print("\n[OK] Paletes escrites a pack_level.py, graphics_tool.py i palette.json.")
        print("     Ara cal: py -3 tools/graphics_tool.py import  (i després el build).")
    else:
        print("\n (mode lectura: res s'ha modificat; usa --apply per escriure)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
