#!/usr/bin/env python3
"""Genera la taula de spawns d'enemics d'un nivell (2..6) a partir de
tools/blues_dos/bb/staticres.c.

Nomes es converteixen els tipus que el motor C6 pot tractar:
  L2:
    type 11 -> static  (kind 22): op7 no hi ha case al switch DOS -> no es mou
    type 12 -> walker  (kind 18, op1): walk 1/2, atac 3
    type 13 -> llançador (kind 21, op7): walk 4/5, llançament 6
    type 14 -> walker  (kind 17, op10): walk 7/8, llançament 9
    type 21 -> walker  (kind 17, op10): walk 10/11, llançament 12
    El tipus 22 (premsa hidràulica, op11) queda fora: és un objecte mòbil
    vertical de 37 px i va en un subsistema propi.
  L3:
    type 3  -> guardia amb escut (kind 18, op2 sense tret): patrulla contínua,
               walk 0/1 (no dispara ni s'atura)
    type 4  -> policia amb pistola (kind 4): mateix comportament que a L1
               (patrulla + tret); walk 5/6, pose de tret 11
    type 6  -> gos     (kind 18, op1): walk 13/14 (celes de gen_enemy3_frames)
    Els tipus 5/23 (op4/op11) son movers, no walkers de C6.

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
    11: (22, 0, 0, 0, 0),    # estatic (op7 sense case al DOS)
    12: (18, 24, 1, 3, 3),   # walker op1 (xmaxvelocity 40)
    13: (21, 32, 4, 6, 6),   # llançador op7 (xmaxvelocity 32)
    14: (17, 20, 7, 9, 9),   # op10
    21: (17, 20, 10, 12, 12),  # op10
    # L3 (vegeu tools/gen_enemy3_frames.py per a les celes)
    3: (18, 24, 0, 0, 0),    # guardia amb escut: patrulla sense tret (op2)
    4: (4, 24, 5, 11, 11),   # policia amb pistola: com L1 (patrulla + tret)
    6: (24, 24, 13, 13, 13),  # rata/gos L3 op1: walker amb hitbox h=10 (level_obj_h[6])
    # L4 EGOU (vegeu tools/gen_enemy4_frames.py per a les celes)
    # Celes: 0,1: policia; 2,3: patruller; 4,5: peix gran/monstre; 6,7: rata gran;
    #        8: rata petita; 9: estatic; 10,11: walker mitja; 12: aranya;
    #        14,15: peix petit decoratiu (class 0, kind 8)
    25: (18, 24, 0, 1, 1),    # policia L4 (op2: patrulla)
    26: (9,  24, 4, 5, 5),    # peix gran / monstre marí L4 (op6: neda i fa mal, class 2)
    27: (18, 32, 6, 7, 7),    # rata gran L4 (op13: walker rapid)
    28: (18, 24, 2, 3, 3),    # patruller L4 (op1)
    29: (24, 32, 8, 8, 8),    # rata petita L4 (op13: walker rapid hitbox h=10/16)
    30: (22, 0,  9, 9, 9),    # estatic L4 (op14)
    31: (18, 32, 10, 11, 11), # walker mitja L4 (op13: walker rapid)
    32: (22, 0,  12, 12, 12), # aranya L4 (op15: aranya de sostre)
    33: (8,  24, 14, 15, 15), # peix petit decoratiu d'aigua L4 (op16, class 0, no fa mal)
    34: (9,  24, 4, 5, 5),    # peix gran d'aigua L4 (op16, class 2, fa mal)
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

    if len(rows) > 22:
        rows = rows[:22]
    n = len(rows)

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
    # ENEMY_N es 22; la resta queden fora de pantalla i no es dibuixen.
    for i in range(n, 22):
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
