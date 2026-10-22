#!/usr/bin/env python3
"""Genera la taula de spawns d'enemics del nivell 2 (ENT) a partir de
tools/blues_dos/bb/staticres.c.

Nomes es converteixen els tipus que el motor C6 pot tractar:
  type 12 -> policia (kind 4), walk 5/6, aim 1
  type 13 -> walker  (kind 18), walk 7/8
  type 14 -> cambrera(kind 17), walk 9/10, throw 2
  type 21 -> cambrera(kind 17), walk 11/12, throw 15
Els tipus 11 (sprite de 48 px) i 22 (objecte) queden fora de la taula.

Us:
  py -3 tools/gen_enemy_spawn.py --level 1 --out obj/lvl1/enemy_spawn.h
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from pack_level import parse_staticres_arrays  # noqa: E402

LEVEL_NAMES = ["magasin", "ent", "prison", "egou", "ville", "concert"]
MAX_OBJECTS = 41

# type DOS -> (kind CPC, vx, base_cell, aim_cell, throw_cell)
SPAWN_TYPES = {
    12: (4, 24, 5, 1, 15),    # policia (home del paquet)
    13: (18, 24, 7, 14, 15),  # walker (dona cistella)
    14: (17, 24, 9, 14, 2),   # cambrera (llenca)
    21: (17, 24, 11, 14, 15), # cambrera (uniforme)
}


def generate(level_idx, out_path):
    arrays = parse_staticres_arrays(
        os.path.join(PROJ, "tools", "blues_dos", "bb", "staticres.c"))
    lname = LEVEL_NAMES[level_idx]
    xs = arrays["level_xpos_" + lname]
    ys = arrays["level_ypos_" + lname]
    data = arrays["level_data"]
    types = data[level_idx * MAX_OBJECTS:(level_idx + 1) * MAX_OBJECTS]

    rows = []
    n = 0
    for slot in range(MAX_OBJECTS):
        t = types[slot]
        if t not in SPAWN_TYPES:
            continue
        kind, vx, base, aim, throw = SPAWN_TYPES[t]
        # DOS: centre X i base dels peus. CPC: top-left, PH=32.
        x = (xs[slot] >> 1) - 8
        y = ys[slot] - 32
        rows.append((slot, t, x, y, kind, vx, base, aim, throw))
        n += 1

    lines = [
        "#ifndef ENEMY_SPAWN_H",
        "#define ENEMY_SPAWN_H",
        "// Generat per tools/gen_enemy_spawn.py: nivell %d (%s)." % (
            level_idx + 1, lname.upper()),
        "// { x, y8, kind, vx, base_cell, aim_cell, throw_cell }",
        "static const Spawn s_spawn[ENEMY_N] = {",
    ]
    for slot, t, x, y, kind, vx, base, aim, throw in rows:
        lines.append("    { %d, %d << 3, %d, %d, %d, %d, %d }, "
                     "// slot %d type 0x%02X" %
                     (x, y, kind, vx, base, aim, throw, slot, t))
    # ENEMY_N es 20; la resta queden fora de pantalla i no es dibuixen.
    for i in range(n, 20):
        lines.append("    { -1000, 0, 19, 0, 5, 14, 15 }, // inactiu")
    lines.append("};")
    lines.append("#endif")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").write("\n".join(lines) + "\n")
    print("%s: %d walkers actius" % (out_path, n))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--level", type=int, required=True, choices=range(1, 6))
    p.add_argument("--out", required=True)
    a = p.parse_args()
    generate(a.level, a.out)
