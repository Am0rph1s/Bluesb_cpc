#!/usr/bin/env python3
"""
check_enemy_cells.py - Auditoria de les cel·les d'enemics de cada nivell
=============================================================================

Comprova que la taula de spawns (`tools/gen_enemy_spawn.py`, base_cell/aim_cell/
throw_cell) apunti a les cel·les CORRECTES del fitxer ENEMI<n>.BIN.

Metode (tot amb la referencia DOS):
  1. De `staticres.c` es treuen els frames que cada tipus d'objecte fa servir
     al nivell (mateix algoritme que tools/dump_level_sprites.py).
  2. Es decodifica cada cel·la de ENEMI<n>.BIN i es identifica amb el frame DOS
     que hi correspon (prova les dues formes d'empaquetat: make_cell centrat i
     crop_content).
  3. Es confronta amb la taula de spawns del nivell:
       - walk  = base_cell, base_cell+1
       - pose  = aim_cell (tret) / throw_cell (llançament)
     Si alguna d'aquestes cel·les NO és del tipus esperat, hi ha un error.

També informa dels tipus DOS del nivell que NO son a la taula de spawns
(movers/ascensors, per exemple, que no son walkers de C6).

Us:
    py -3 tools/check_enemy_cells.py            # tots els nivells
    py -3 tools/check_enemy_cells.py --level 2  # nomes la preso
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BB = os.path.join(PROJ, "assets", "bbdata")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from sprites import load_sqv_frames          # noqa: E402
from gen_enemy_frames import pack_cell       # noqa: E402
import gen_enemy_spawn as gs                 # noqa: E402

SPRITES_COUNT = 146
LEVEL_NAMES = ["magasin", "ent", "prison", "egou", "ville", "concert"]
SQV_FILES = ["ENEMI1.SQV", "ENEMI2.SQV", "ENEMI3.SQV",
             "ENEMI4.SQV", "ENEMI5.SQV", "ENEMI6.SQV"]
MAX_OBJECTS = 41
STATICRES = os.path.join(HERE, "blues_dos", "bb", "staticres.c")


def staticres_arrays():
    src = open(STATICRES, encoding="latin1").read()
    a = re.search(r"animframes_059d\[\]\s*=\s*\{(.*?)\};", src, re.S).group(1)
    ptrs = [x.strip() for x in a.split(",") if x.strip()]
    cache = {}

    def arr(name):
        if name not in cache:
            m = re.search(re.escape(name) + r"\[\]\s*=\s*\{([^}]*)\}", src)
            cache[name] = ([int(x.strip(), 0) for x in m.group(1).split(",")
                            if x.strip()] if m else [])
        return cache[name]

    md = re.search(r"uint8_t level_data\[\]\s*=\s*\{([^}]+)\};", src, re.S)
    types = [int(t.strip(), 0) for t in
             re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", md.group(1))]
    mo = re.search(r"const uint8_t level_objtypes\[\]\s*=\s*\{([^}]+)\};", src, re.S)
    ops = [int(x.strip(), 0) for x in mo.group(1).split(",") if x.strip()]
    return ptrs, arr, types, ops


def type_frames(ptrs, arr, obj_type):
    idx = obj_type * 29
    used = set()
    for k in range(29):
        if idx + k >= len(ptrs):
            break
        for v in arr(ptrs[idx + k])[1:]:
            f = v - SPRITES_COUNT
            if f >= 0:
                used.add(f)
    return sorted(used)


def make_cell(w, h, px):
    box = [[0] * 32 for _ in range(32)]
    xs = (32 - w) // 2
    ys = 32 - h
    for y in range(h):
        oy = y + ys
        for x in range(w):
            ox = x + xs
            if 0 <= oy < 32 and 0 <= ox < 32:
                box[oy][ox] = px[y][x]
    return box


def crop_content(px, w, h):
    xs = [x for y in range(h) for x in range(w) if px[y][x] != 0]
    ys = [y for y in range(h) for x in range(w) if px[y][x] != 0]
    if not xs:
        return px, w, h
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 - x0 + 1 > 32:
        x1 -= (x1 - x0 + 1) - 32
    if y1 - y0 + 1 > 32:
        y0 += (y1 - y0 + 1) - 32
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    out = [[0] * cw for _ in range(ch)]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            out[y - y0][x - x0] = px[y][x]
    return out, cw, ch


def identify_cells(lid, types, ops, ptrs, arr):
    """Retorna (cel·la -> (frame, tipus)) i el llistat de frames per tipus."""
    frames = load_sqv_frames(os.path.join(BB, SQV_FILES[lid]))
    tframes = {}
    for t in sorted(set(types)):
        if t == 100:
            continue
        fl = [f for f in type_frames(ptrs, arr, t) if f < len(frames)]
        if fl:
            tframes[t] = fl

    refs = {}
    for t, fl in tframes.items():
        for f in fl:
            w, h, px = frames[f]
            refs[f] = pack_cell(make_cell(w, h, px), 32, 32)
            p2, w2, h2 = crop_content(px, w, h)
            refs[f] = pack_cell(p2, w2, h2)     # la variant "retallada" substitueix

    path = os.path.join(BB, "ENEMI%d.BIN" % (lid + 1))
    if not os.path.exists(path):
        return {}, tframes
    raw = open(path, "rb").read()
    out = {}
    for c in range(16):
        cell = raw[c * 512:(c + 1) * 512]
        if not any(cell):
            out[c] = (None, None)
            continue
        best = (0, None)
        for f, r in refs.items():
            same = sum(1 for a, b in zip(cell, r) if a == b)
            if same > best[0]:
                best = (same, f)
        owner = None
        for t, fl in tframes.items():
            if best[1] in fl:
                owner = t
        out[c] = (best[1], owner)
    return out, tframes


def spawn_types_for(lid):
    table = {0: None, 1: gs.SPAWN_TYPES_L2, 2: gs.SPAWN_TYPES_L3,
             3: gs.SPAWN_TYPES_L4, 4: gs.SPAWN_TYPES_L5, 5: gs.SPAWN_TYPES_L6}
    if lid == 0:
        return None
    return table[lid]


def main():
    args = sys.argv[1:]
    levels = [int(a) for a in args if a.isdigit()] or list(range(6))
    ptrs, arr, types, ops = staticres_arrays()
    bad = 0

    for lid in levels:
        lname = LEVEL_NAMES[lid]
        ltypes = types[lid * MAX_OBJECTS:(lid + 1) * MAX_OBJECTS]
        cells, tframes = identify_cells(lid, ltypes, ops, ptrs, arr)

        print("\n" + "=" * 76)
        print(" NIVELL %d (%s)  -  cel·les de ENEMI%d.BIN" % (lid + 1, lname, lid + 1))
        print("=" * 76)
        print("  tipus DOS del nivell: %s" % ", ".join(
            "t%d(op%d)x%d" % (t, ops[t], ltypes.count(t))
            for t in sorted(set(ltypes)) if t != 100))
        print("  cel·la -> frame DOS -> tipus DOS:")
        for c in range(16):
            f, t = cells.get(c, (None, None))
            if f is None:
                print("    cell %2d : (buida)" % c)
            else:
                print("    cell %2d : frame %2d  tipus %s" % (
                    c, f, ("t%d (op%d)" % (t, ops[t])) if t is not None else "?"))

        st = spawn_types_for(lid)
        if not st:
            print("  (taula de spawns hardcodeada de L1: no s'audita)")
            continue
        print("  taula de spawns:")
        for t, (kind, vx, base, aim, throw) in sorted(st.items()):
            if t not in ltypes:
                continue
            own = set(tframes.get(t, []))
            owners = []

            def check(cell, label, strict=True):
                """Una cel·la es valida si el seu frame DOS pertany al tipus.
                Dos tipus poden compartir el mateix sprite (p. ex. L4: t26 i
                t34 son el mateix peix) i en aquest cas la cel·la es valida
                per tots dos."""
                f, _owner = cells.get(cell, (None, None))
                ok = (f in own) if f is not None else False
                owners.append("%s=cell%d[frame %s%s]" % (
                    label, cell, f if f is not None else "-",
                    "" if ok else " <-- HAURI DE SER FRAME DE t%d" % t))
                return ok

            bad += 0 if check(base, "walk A") else 1
            if vx != 0:      # els estatics (vx=0) sempre juguen la mateixa cela
                bad += 0 if check(base + 1, "walk B") else 1
            pose_cell = aim if kind == 4 else (throw if kind in (17, 21, 23) else None)
            if pose_cell is not None:
                bad += 0 if check(pose_cell, "pose") else 1
            print("    t%-2d kind %-2d  %s" % (t, kind, "  ".join(owners)))

        missing = [t for t in sorted(set(ltypes)) if t != 100 and t not in st]
        if missing:
            print("  TIPUS DELS QUE NO HI SON A LA TAULA DE SPAWNS (no implementats): %s" % (
                ", ".join("t%d(op%d)x%d" % (t, ops[t], ltypes.count(t)) for t in missing)))

    print("\n" + "=" * 76)
    print(" RESULTAT: %d referències a cel·les incorrectes." % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
