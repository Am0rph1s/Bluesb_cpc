#!/usr/bin/env python3
"""
inventory_levels.py - Inventari de nivells (Fase 0 de docs/PLA_NIVELLS_UNIVERSAL.md)
Nomes LLEGEIX: staticres.c del DOS i els fitxers de assets/bbdata. No modifica res.

Us:  py -3 tools/inventory_levels.py            (taula a pantalla)
     py -3 tools/inventory_levels.py --md FILE  (escriu un .md)
"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from pack_level import parse_staticres_arrays  # noqa: E402

MAX_LEVELS = 6
MAX_OBJECTS = 41
MAX_DOORS = 30
TRIG_BYTES = 2560      # X.BIN: 256 entrades x 10 B
C5_BYTES = 16384       # un banc CPC
ROOM_H = 10            # alcada del bloc d'habitacio (files)
NAMES = ["magasin", "ent", "prison", "egou", "ville", "concert"]
# Fitxers DOS per nivell (level.c: _levels[])
FILES = [
    ("mag.ck1", "mag.ck2", "mag.sql", "magasin.bin", "avtmag.sqv", "enemi1.sqv"),
    ("ent.ck1", "ent.ck2", "ent.sql", "entrepot.bin", "avtent.sqv", "enemi2.sqv"),
    ("prison.ck1", "prison.ck2", "prison.sql", "prison.bin", "avtpris.sqv", "enemi3.sqv"),
    ("egou.ck1", "egou.ck2", "egou.sql", "egou.bin", "avtegou.sqv", "enemi4.sqv"),
    ("ville.ck1", "ville.ck2", "ville.sql", "ville.bin", "avtville.sqv", "enemi5.sqv"),
    ("concert.ck1", "concert.ck2", "concert.sql", "concert.bin", "", "enemi6.sqv"),
]
MUSIC = [1, 2, 3, 1, 2, 3]  # _levels[].music
BBDATA = os.path.join(PROJ, "assets", "bbdata")
ELEVATOR_TYPE = 7


def fsize(name):
    if not name:
        return None
    p = os.path.join(BBDATA, name)
    if not os.path.exists(p):
        # cerca insensible a majuscules
        for f in os.listdir(BBDATA):
            if f.lower() == name.lower():
                p = os.path.join(BBDATA, f)
                break
        else:
            return None
    return os.path.getsize(p)


def room_row0():
    """Fila on comencen les habitacions de cada nivell (DOS level.c:1135).

    A DOS les habitacions son files DEL MATEIX tilemap (array pla de 128
    columnes, resource.c:381 `y * 128 + x`), per sobre de l'alcada visible:
    `if (obj->ypos > screen_tilemap_h)` (level.c:1141) -> camera a pos[nivell].
    """
    path = os.path.join(HERE, "blues_dos", "bb", "level.c")
    txt = open(path, encoding="latin1").read()
    m = re.search(r"uint8_t\s+pos\[\]\s*=\s*\{([^}]*)\}", txt)
    if not m:
        return []
    return [int(x.strip(), 0) for x in m.group(1).split(",") if x.strip()]


def inventory():
    a = parse_staticres_arrays(os.path.join(HERE, "blues_dos", "bb", "staticres.c"))
    dim = a["level_dim"]
    data = a["level_data"]
    doors = a["level_door"]
    rrow = room_row0()
    rows = []
    for n in range(MAX_LEVELS):
        w = dim[n * 2]
        h_px = dim[n * 2 + 1]
        h = h_px >> 4
        objs = data[n * MAX_OBJECTS:(n + 1) * MAX_OBJECTS]
        kinds = Counter(t for t in objs if t != 100)
        d = doors[n * MAX_DOORS * 8:(n + 1) * MAX_DOORS * 8]
        dl = []
        for i in range(MAX_DOORS):
            v = d[i * 8:i * 8 + 8]
            sx = v[0] | (v[1] << 8)
            sy = v[2] | (v[3] << 8)
            dx = v[4] | (v[5] << 8)
            dy = v[6] | (v[7] << 8)
            if sx or sy or dx or dy:
                dl.append((sx, sy, dx, dy))
        in_room = [x for x in dl if x[3] >= h or x[1] >= h]
        # Files reals del tilemap: si hi ha habitacions, arriba fins pos+ROOM_H.
        r0 = rrow[n] if n < len(rrow) else None
        h_real = h
        if in_room and r0 is not None:
            h_real = max(h, r0 + ROOM_H)
        fl = {}
        for k, nm in zip(("ck1", "ck2", "sql", "bin", "avt", "sqv"), FILES[n]):
            fl[k] = fsize(nm)
        rows.append(dict(n=n + 1, name=NAMES[n], w=w, h=h, h_real=h_real,
                         room0=r0 if in_room else None,
                         map=w * h_real, map_vis=w * h,
                         trig=TRIG_BYTES, map_trig=w * h_real + TRIG_BYTES,
                         objs=sum(kinds.values()), kinds=dict(sorted(kinds.items())),
                         elev=kinds.get(ELEVATOR_TYPE, 0), doors=len(dl),
                         door_room=len(in_room), music=MUSIC[n], files=fl))
    return rows


def fmt(v):
    return "-" if v is None else "{:,}".format(v).replace(",", ".")


def render_md(rows):
    L = []
    L.append("# Inventari dels 6 nivells (generat per tools/inventory_levels.py)\n")
    L.append("> Mides **reals** del tilemap: a DOS les habitacions son files del mateix")
    L.append("> array de 128 columnes (`level.c:1135 pos[]`, `resource.c:381 y*128+x`),")
    L.append("> per sobre de l'alcada visible. Per tant `Mapa = ample x max(alcada, pos+10)`.")
    L.append("> `TRIG` = 2.560 B (256 entrades x 10 B). Un banc CPC = 16.384 B.\n")
    L.append("| Nivell | Nom | Ample | Alt visible | pos sala | Files reals | Mapa (B) | +TRIG (B) | Cap a C5? | Objectes | Ascensors | Portes | Portes amb sala | Cançó (#) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        fit = "SI" if r["map_trig"] <= C5_BYTES else "NO (-%d)" % (r["map_trig"] - C5_BYTES)
        L.append("| %d | %s | %d | %d | %s | %d | %s | %s | %s | %d | %d | %d | %d | %d |" % (
            r["n"], r["name"], r["w"], r["h"],
            "-" if r["room0"] is None else r["room0"],
            r["h_real"], fmt(r["map"]), fmt(r["map_trig"]), fit,
            r["objs"], r["elev"], r["doors"], r["door_room"], r["music"]))
    L.append("\n> `Cap a C5?` compara **mapa + TRIG** amb els 16.384 B del banc, **sense**")
    L.append("> comptar-hi el codi del mon (`moving_bank`, 4.548 B avui). Amb el codi, cap")
    L.append("> nivell hi cap (nivell 1: 17.860 B).")
    L.append("\n## Fitxers DOS al disc (bytes, comprimits tal com son a assets/bbdata)\n")
    L.append("| Nivell | CK1 | CK2 | SQL (mapa) | BIN (TRIG) | AVT | SQV (enemics) | Total |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        f = r["files"]
        tot = sum(v for v in f.values() if v)
        L.append("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
            r["n"], fmt(f["ck1"]), fmt(f["ck2"]), fmt(f["sql"]), fmt(f["bin"]),
            fmt(f["avt"]), fmt(f["sqv"]), fmt(tot)))
    L.append("\n## Tipus d'objecte per nivell (tipus DOS: quantitat)\n")
    for r in rows:
        L.append("- Nivell %d (%s): %s" % (r["n"], r["name"],
                 ", ".join("%d:%d" % kv for kv in r["kinds"].items())))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    rows = inventory()
    md = render_md(rows)
    if "--md" in sys.argv:
        out = sys.argv[sys.argv.index("--md") + 1]
        open(out, "w", encoding="utf-8").write(md)
        print("Escrit", out)
    else:
        print(md)
