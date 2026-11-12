#!/usr/bin/env python3
"""
palette_audit.py - Auditoria de les paletes Mode 0 (16 pens) dels 6 nivells
=============================================================================

Eina de SOL lectura: no modifica cap fitxer. Serveix per:

  1. Comprovar que les tres fonts de paleta estan sincronitzades:
       - DEFAULT_PALETTES (tools/graphics_tool.py)  [font de l'import]
       - LEVEL_PALETTES  (tools/pack_level.py)      [paleta de runtime]
       - graphics_edit/level*/palette.json          [paleta editada]
  2. Detectar quins pens fa servir cada asset (tileset, enemics, Jake, Elwood,
     HUD) descomprimint/descodificant els binaris reals.
  3. Detectar colors DUPLICATS (slots que repeteixen color) i pens MORTS
     (slots que no fa servir ningú).
  4. Auditar el CONTRACTE de pens compartits: els pens que fan servir els
     sprites compartits i el HUD haurien de tenir el mateix color a tots els
     nivells, perquè PFRAMES/ELWOOD son comunitaris i el HUD es dibuixa sempre.

Us:
    py -3 tools/palette_audit.py                 # informe per pantalla
    py -3 tools/palette_audit.py --json          # sortida JSON (per maquines)
    py -3 tools/palette_audit.py --strict        # codi de sortida != 0 si hi ha errors

Codi de sortida:
    0  cap error
    1  error de sincronia entre les tres fonts de paleta (o --strict amb
       violacions del contracte de pens)
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BBDATA = os.path.join(PROJ, "assets", "bbdata")
EXPORT_DIR = os.path.join(PROJ, "graphics_edit")
sys.path.insert(0, HERE)

from graphics_tool import (  # noqa: E402
    DEFAULT_PALETTES,
    HW_TO_COLOR,
    LEVEL_INFO,
    decode_enemy_pair,
    decode_mode0_byte,
)


# ---------------------------------------------------------------------------
# Fonts de paleta
# ---------------------------------------------------------------------------
def load_pack_level_palettes():
    """Llegeix LEVEL_PALETTES de tools/pack_level.py sense importar el modul."""
    path = os.path.join(HERE, "pack_level.py")
    txt = open(path, "r", encoding="utf-8").read()
    m = re.search(r"LEVEL_PALETTES\s*=\s*\[(.*?)\n\]", txt, re.DOTALL)
    if not m:
        raise SystemExit("No s'ha trobat LEVEL_PALETTES a pack_level.py")
    pals = []
    for row in re.findall(r"\[([^\]]*)\]", m.group(1)):
        vals = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", row)]
        if len(vals) == 16:
            pals.append(vals)
    return pals


def load_json_palettes():
    """Palette.json de cada nivell (editable per l'usuari)."""
    out = []
    for lv in LEVEL_INFO:
        p = os.path.join(EXPORT_DIR, lv["folder"], "palette.json")
        if not os.path.exists(p):
            out.append(None)
            continue
        pj = json.load(open(p, "r", encoding="utf-8"))
        vals = [0] * 16
        for item in pj:
            pen = int(item["pen"])
            if "ga_code" in item:
                vals[pen] = int(item["ga_code"], 16)
            elif "hw_code" in item:
                vals[pen] = int(item["hw_code"], 16)
            elif "rgb" in item:
                vals[pen] = closest_hw(item["rgb"])
        out.append(vals)
    return out


def closest_hw(rgb):
    from graphics_tool import closest_cpc_color
    return closest_cpc_color(*rgb)["hw"]


def nearest_pen(rgb_pal, rgb):
    """Pen de la paleta mes proper del color donat."""
    best, bd = 0, 1 << 30
    for pen, (pr, pg, pb) in enumerate(rgb_pal):
        d = (rgb[0] - pr) ** 2 + (rgb[1] - pg) ** 2 + (rgb[2] - pb) ** 2
        if d < bd:
            bd, best = d, pen
    return best


# Paletes de runtime (pack_level.LEVEL_PALETTES), carregades una sola vegada.
LEVEL_PALETTES_REF = [load_pack_level_palettes()]


# ---------------------------------------------------------------------------
# Descodificacio d'assets -> pens
# ---------------------------------------------------------------------------
def pens_tileset(lid):
    """Tileset COMPACTAT del nivell (TILESETC<n>.BIN): 1 byte = 2 pixels Mode 0."""
    p = os.path.join(BBDATA, "TILESETC%d.BIN" % lid)
    if not os.path.exists(p):
        return None
    c = Counter()
    for b in open(p, "rb").read():
        p0, p1 = decode_mode0_byte(b)
        c[p0] += 1
        c[p1] += 1
    return c


def pens_enemies(lid):
    """16 cel·les d'enemics (ENEMI<n+1>.BIN): 32 files x 16 bytes = 8 parelles."""
    p = os.path.join(BBDATA, "ENEMI%d.BIN" % (lid + 1))
    if not os.path.exists(p):
        return None
    raw = open(p, "rb").read()
    c = Counter()
    for cell in range(len(raw) // 512):
        data = raw[cell * 512:(cell + 1) * 512]
        for row in range(32):
            rb = data[row * 16:(row + 1) * 16]
            for i in range(8):
                p0, p1 = decode_enemy_pair(rb[i * 2], rb[i * 2 + 1])
                if p0 is not None:
                    c[p0] += 1
                if p1 is not None:
                    c[p1] += 1
    return c


def pens_player(fname):
    """Frames del jugador (PFRAMES/ELWOOD): 30 files x 16 bytes = 8 parelles."""
    p = os.path.join(BBDATA, fname)
    if not os.path.exists(p):
        return None
    raw = open(p, "rb").read()
    c = Counter()
    for frame in range(len(raw) // 480):
        data = raw[frame * 480:(frame + 1) * 480]
        for row in range(30):
            rb = data[row * 16:(row + 1) * 16]
            for i in range(8):
                p0, p1 = decode_enemy_pair(rb[i * 2], rb[i * 2 + 1])
                if p0 is not None:
                    c[p0] += 1
                if p1 is not None:
                    c[p1] += 1
    return c


def pens_hud():
    """Tires del HUD (obj/hud_strips.asm, 39 columnes x 24 B = 936 B)."""
    p = os.path.join(PROJ, "obj", "hud_strips.asm")
    if not os.path.exists(p):
        return None
    txt = open(p, "r", encoding="utf-8", errors="ignore").read()
    vals = [int(x, 16) for x in re.findall(r"\.db\s+#0x([0-9A-Fa-f]{2})", txt)]
    if not vals:
        return None
    c = Counter()
    for b in vals:
        p0, p1 = decode_mode0_byte(b)
        c[p0] += 1
        c[p1] += 1
    return c


# ---------------------------------------------------------------------------
# Coherencia PNG <-> binaris (el PNG es el master editable)
# ---------------------------------------------------------------------------
def coherence_tileset(lid, png_path):
    """El pixel del PNG ha de correspondre al pen del binaire.

    Es compara amb el color MES PROPER de la paleta: si el pixel del PNG es
    quantitza a un altre pen, l'art es veurà amb un color diferent del master
    (error real). Els colors simplement "propers" (p. ex. #3090D0 -> 0x57) no
    es consideren error, perquè la quantització és el comportament esperat.
    """
    from PIL import Image
    bin_path = os.path.join(BBDATA, "TILESET%d.BIN" % lid)
    if not (os.path.exists(bin_path) and os.path.exists(png_path)):
        return None
    pal = LEVEL_PALETTES_REF[0][lid] if LEVEL_PALETTES_REF else None
    if pal is None:
        return None
    rgb = [tuple(HW_TO_COLOR[h]["rgb"]) for h in pal]
    data = open(bin_path, "rb").read()
    im = Image.open(png_path).convert("RGBA")
    px = im.load()
    bad = tot = 0
    for t in range(256):
        tb = data[t * 64:(t + 1) * 64]
        tx, ty = (t % 16) * 8, (t // 16) * 16
        for r in range(16):
            rb = tb[r * 4:(r + 1) * 4]
            for i in range(4):
                p0, p1 = decode_mode0_byte(rb[i])
                for k, p in ((0, p0), (1, p1)):
                    rr, gg, bb, _ = px[tx + i * 2 + k, ty + r]
                    tot += 1
                    if nearest_pen(rgb, (rr, gg, bb)) != p:
                        bad += 1
    return bad, tot


def coherence_enemies(lid, png_path):
    from PIL import Image
    bin_path = os.path.join(BBDATA, "ENEMI%d.BIN" % (lid + 1))
    if not (os.path.exists(bin_path) and os.path.exists(png_path)):
        return None
    pal = LEVEL_PALETTES_REF[0][lid] if LEVEL_PALETTES_REF else None
    if pal is None:
        return None
    rgb = [tuple(HW_TO_COLOR[h]["rgb"]) for h in pal]
    data = open(bin_path, "rb").read()
    im = Image.open(png_path).convert("RGBA")
    px = im.load()
    bad = tot = 0
    for c in range(16):
        cx, cy = (c % 4) * 16, (c // 4) * 32
        d = data[c * 512:(c + 1) * 512]
        for row in range(32):
            rb = d[row * 16:(row + 1) * 16]
            for i in range(8):
                p0, p1 = decode_enemy_pair(rb[i * 2], rb[i * 2 + 1])
                for k, p in ((0, p0), (1, p1)):
                    if p is None:
                        continue
                    rr, gg, bb, aa = px[cx + i * 2 + k, cy + row]
                    tot += 1
                    if aa < 128 or nearest_pen(rgb, (rr, gg, bb)) != p:
                        bad += 1
    return bad, tot


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------
def name_of(hw):
    return HW_TO_COLOR[hw]["name"]


def fmt_pal(pal):
    return " ".join("%02X" % v for v in pal)


def main():
    json_out = "--json" in sys.argv
    strict = "--strict" in sys.argv

    pack = load_pack_level_palettes()
    jsons = load_json_palettes()

    # --- 1. Sincronia entre les tres fonts -------------------------------
    sync_errors = []
    for lid in range(6):
        tag = "L%d" % (lid + 1)
        if len(pack) <= lid:
            sync_errors.append("%s: LEVEL_PALETTES te només %d entrades" % (tag, len(pack)))
            continue
        if pack[lid] != DEFAULT_PALETTES[lid]:
            sync_errors.append(
                "%s: pack_level.LEVEL_PALETTES != graphics_tool.DEFAULT_PALETTES\n"
                "      pack_level : %s\n"
                "      graphics_tool: %s" % (tag, fmt_pal(pack[lid]), fmt_pal(DEFAULT_PALETTES[lid])))
        if jsons[lid] is None:
            sync_errors.append("%s: falta graphics_edit/%s/palette.json" % (tag, LEVEL_INFO[lid]["folder"]))
        elif jsons[lid] != pack[lid]:
            sync_errors.append(
                "%s: palette.json != LEVEL_PALETTES\n"
                "      palette.json: %s\n"
                "      LEVEL_PALETTES: %s" % (tag, fmt_pal(jsons[lid]), fmt_pal(pack[lid])))

    # --- 2. Pens per asset ------------------------------------------------
    assets = {}
    for lid in range(6):
        assets["L%d" % (lid + 1)] = {
            "tileset": pens_tileset(lid),
            "enemies": pens_enemies(lid),
        }
    jake = pens_player("PFRAMES.BIN")
    elwood = pens_player("ELWOOD.BIN")
    hud = pens_hud()

    shared = {}
    if jake:
        shared["Jake"] = jake
    if elwood:
        shared["Elwood"] = elwood
    if hud:
        shared["HUD"] = hud

    # --- 3. Contracte: pens compartits que han de ser constants ----------
    contract = []          # (asset, pen) amb color diferent per nivell
    shared_pens = set()
    for a, c in shared.items():
        shared_pens |= set(c.keys())
    for pen in sorted(shared_pens):
        colors = [pack[lid][pen] for lid in range(6)]
        if len(set(colors)) > 1:
            users = [a for a, c in shared.items() if pen in c]
            contract.append({
                "pen": pen,
                "assets": users,
                "colors": ["%02X" % v for v in colors],
            })

    # --- 4. Duplicats i pens morts per nivell ----------------------------
    levels = []
    for lid in range(6):
        tag = "L%d" % (lid + 1)
        pal = pack[lid]
        used = Counter()
        for key in ("tileset", "enemies"):
            c = assets[tag][key]
            if c:
                used.update(c)
        for a, c in shared.items():
            used.update(c)
        dup = {}
        for hw, n in Counter(pal).items():
            if n > 1:
                dup["%02X" % hw] = [i for i, v in enumerate(pal) if v == hw]
        dead = [i for i in range(16) if i not in used]
        levels.append({
            "level": tag,
            "palette": ["%02X" % v for v in pal],
            "unique_colors": len(set(pal)),
            "duplicates": dup,
            "dead_pens": dead,
            "used_pens": sorted(used.keys()),
        })

    result = {
        "sync_errors": sync_errors,
        "assets": {a: sorted(c.keys()) for a, c in shared.items()},
        "contract_violations": contract,
        "levels": levels,
    }

    if json_out:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if sync_errors else 0

    # ---- sortida per pantalla -------------------------------------------
    print("=" * 72)
    print(" AUDITORIA DE PALETES MODE 0 - 6 NIVELLS (16 pens)")
    print("=" * 72)

    print("\n[1] SINCRONIA DE LES TRES FONTS DE PALETA")
    if sync_errors:
        for e in sync_errors:
            print("  ERROR  " + e)
    else:
        print("  OK     DEFAULT_PALETTES == LEVEL_PALETTES == palette.json (els 6 nivells)")

    print("\n[2] PENS QUE FA SERVIR CADA ASSET COMPARTIT")
    for a, c in shared.items():
        print("  %-8s pens %s" % (a, ",".join(str(p) for p in sorted(c.keys()))))
    for lid in range(6):
        tag = "L%d" % (lid + 1)
        t = assets[tag]["tileset"]
        e = assets[tag]["enemies"]
        print("  %-8s pens %s | enemics %s" % (
            tag + " tiles",
            ",".join(str(p) for p in sorted(t.keys())) if t else "-",
            ",".join(str(p) for p in sorted(e.keys())) if e else "-"))

    print("\n[3] CONTRACTE DE PENS COMPARTITS (haurien de ser iguals a tots els nivells)")
    if not contract:
        print("  OK     tots els pens compartits son constants")
    else:
        for v in contract:
            print("  AVIS   pen %-2d usat per %-18s colors per nivell: %s" % (
                v["pen"], ", ".join(v["assets"]), " ".join(v["colors"])))

    print("\n[4] DUPLICATS I PENS MORTS PER NIVELL")
    for lv in levels:
        dup = lv["duplicates"]
        dtext = ", ".join("%s->%s" % (k, v) for k, v in sorted(dup.items())) or "cap"
        print("  %-4s %s  colors unic=%2d/16  duplicats: %s" % (
            lv["level"], " ".join(lv["palette"]), lv["unique_colors"], dtext))
        print("       pens morts (cap asset els usa): %s" % (
            ",".join(str(p) for p in lv["dead_pens"]) or "cap"))

    print()
    stale = report_coherence()

    print("\n" + "=" * 72)
    if sync_errors:
        print(" RESULTAT: ERROR de sincronia (%d).", len(sync_errors))
        return 1
    if contract or stale:
        print(" RESULTAT: sincronia OK, %d violacions del contracte, %d PNG desincronitzats." % (
            len(contract), len(stale)))
        return 1 if strict else 0
    print(" RESULTAT: OK")
    return 0


def report_coherence():
    """[5] Coherencia PNG master <-> binaris."""
    print("[5] COHERENCIA PNG (master editable) <-> BINARI")
    stale = []
    for lid in range(6):
        folder = os.path.join(EXPORT_DIR, LEVEL_INFO[lid]["folder"])
        cands = [
            ("tileset.png", os.path.join(folder, "tileset.png"), coherence_tileset),
            ("enemies.png", os.path.join(folder, "enemies.png"), coherence_enemies),
            ("edit/tileset_edit.png", os.path.join(folder, "edit", "tileset_edit.png"), coherence_tileset),
            ("edit/enemies_edit.png", os.path.join(folder, "edit", "enemies_edit.png"), coherence_enemies),
            ("edit/enemies_cpc.png", os.path.join(folder, "edit", "enemies_cpc.png"), coherence_enemies),
        ]
        for name, path, fn in cands:
            r = fn(lid, path)
            if r is None:
                continue
            bad, tot = r
            if bad:
                stale.append((lid, name, bad, tot))
                print("  AVIS   L%d %-22s %5d/%5d pixels desincronitzats" % (
                    lid + 1, name, bad, tot))
    if not stale:
        print("  OK     tots els PNG master son coherents amb els binaris")
    return stale


if __name__ == "__main__":
    sys.exit(main())
