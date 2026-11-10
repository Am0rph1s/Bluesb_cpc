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
# L2 ENT (vegeu tools/gen_enemy2_frames.py per a les celes)
SPAWN_TYPES_L2 = {
    11: (18, 24, 0, 2, 2),    # científic walker (op1 / 1:1 DOS object_func_op1): walk 0/1
    12: (18, 24, 2, 4, 4),    # treballador walker (op1): walk 2/3
    13: (21, 32, 4, 6, 6),    # llançador (op7): walk 4/5, llançament 6
    14: (17, 20, 7, 9, 9),    # treballador llançador (op10): walk 7/8, llançament 9
    21: (17, 20, 10, 12, 12), # llançador (op10): walk 10/11, llançament 12
}

# L3 PRISON (vegeu tools/gen_enemy3_frames.py per a les celes)
SPAWN_TYPES_L3 = {
    3: (18, 24, 0, 2, 2),     # guardia amb escut: patrulla walk 0/1 (op2)
    4: (4, 24, 5, 11, 11),    # policia amb pistola: walk 5/6, aim 11
    6: (24, 24, 13, 15, 15),  # gos/rata L3 op1: walk 13/14, hitbox h=10
}

# L4 EGOU (vegeu tools/gen_enemy4_frames.py per a les celes)
SPAWN_TYPES_L4 = {
    25: (18, 24, 0, 2, 2),    # policia L4 (op2: patrulla walk 0/1)
    26: (9,  24, 4, 6, 6),    # peix gran / monstre marí L4 (op6: neda 4/5, fa mal, class 2)
    27: (18, 32, 6, 8, 8),    # rata gran L4 (op13: walker rapid walk 6/7)
    28: (18, 24, 2, 4, 4),    # patruller L4 (op1: walk 2/3)
    29: (24, 32, 8, 10, 10),  # rata petita L4 (op13: walker rapid walk 8/9, hitbox h=10/16)
    30: (22, 0,  13, 13, 13), # estatic L4 (op14: cela 13)
    31: (18, 32, 10, 12, 12), # walker mitja L4 (op13: walker rapid walk 10/11)
    32: (22, 0,  12, 12, 12), # aranya L4 (op15: aranya de sostre)
    33: (8,  24, 14, 16, 16), # peix petit decoratiu d'aigua L4 (op16, swim 14/15, class 0, no fa mal)
    34: (9,  24, 4, 6, 6),    # peix gran d'aigua L4 (op16, swim 4/5, class 2, fa mal)
}

# L5 VILLE (vegeu tools/gen_enemy5_frames.py)
SPAWN_TYPES_L5 = {
    4:  (4,  24, 0, 2, 2),     # policia (op2: patrulla walk 0/1 + tret frame 2)
    21: (17, 20, 3, 5, 5),     # cambrera llançadora (op10: walk 3/4 + throw 5)
    36: (17, 20, 6, 8, 8),     # home llançador (op10: walk 6/7 + throw 8)
    37: (18, 24, 9, 11, 11),   # patruller (op0: walk 9/10)
    38: (25, 24, 14, 16, 16),  # gos saltador (op18: walk 14/15)
    39: (18, 24, 11, 13, 13),  # walker (op1: walk 11/12)
}

# L6 CONCERT (vegeu tools/gen_enemy6_frames.py)
SPAWN_TYPES_L6 = {
    3: (18, 24, 0, 2, 2),      # guarda walker (op1 / walk 0/1)
    4: (4,  24, 5, 11, 11),    # policia (op2 / patrulla walk 5/6, tret frame 11)
}

SPAWN_TYPES_DEFAULT = SPAWN_TYPES_L3


def generate(level_idx, out_path):
    if level_idx == 0:
        # Nivell 1: spawns oficials preservats
        l1_spawns = [
            (456, 1088, 15, 36, 1, 14, 15),
            (624, 1088, 15, 36, 1, 14, 15),
            (592, 960, 15, 36, 1, 14, 15),
            (744, 1088, 4, 24, 3, 14, 15),
            (280, 1088, 4, 24, 3, 14, 15),
            (272, 960, 4, 24, 3, 14, 15),
            (768, 496, 4, 0, 3, 14, 15),
            (688, 320, 4, 24, 3, 14, 15),
            (428, 480, 8, 16, 0, 0, 0),
            (548, 496, 8, 16, 0, 0, 0),
            (232, 64, 19, 24, 5, 14, 15),
            (512, 48, 19, 24, 5, 14, 15),
            (808, 64, 19, 24, 5, 14, 15),
            (352, 320, 18, 24, 7, 14, 15),
            (496, 320, 18, 24, 7, 14, 15),
            (72, 592, 17, 20, 9, 14, 15),
            (432, 960, 20, 24, 11, 14, 15),
            (624, 768, 20, 24, 11, 14, 15),
            (72, 464, 20, 24, 11, 14, 15),
            (584, 720, 20, 24, 11, 14, 15),
            (816, 768, 23, 0, 9, 15, 15),
        ]
        lines = [
            "#ifndef ENEMY_SPAWN_H",
            "#define ENEMY_SPAWN_H",
            "// Spawns L1 MAGASIN",
            "static const Spawn s_spawn[ENEMY_N] = {",
        ]
        for s in l1_spawns:
            lines.append(f"    {{ {s[0]}, {s[1]} << 3, {s[2]}, {s[3]}, {s[4]}, {s[5]}, {s[6]} }},")
        for _ in range(len(l1_spawns), 26):
            lines.append("    { -1000, 0, 19, 0, 5, 14, 15 }, // inactiu")
        lines.append("};")
        lines.append("#endif")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        open(out_path, "w").write("\n".join(lines) + "\n")
        print(f"{out_path}: {len(l1_spawns)} walkers actius")
        return

    arrays = parse_staticres_arrays(
        os.path.join(PROJ, "tools", "blues_dos", "bb", "staticres.c"))
    lname = LEVEL_NAMES[level_idx]
    xs = arrays["level_xpos_" + lname]
    ys = arrays["level_ypos_" + lname]
    data = arrays["level_data"]
    types = data[level_idx * MAX_OBJECTS:(level_idx + 1) * MAX_OBJECTS]

    spawn_map = {
        1: SPAWN_TYPES_L2,
        2: SPAWN_TYPES_L3,
        3: SPAWN_TYPES_L4,
        4: SPAWN_TYPES_L5,
        5: SPAWN_TYPES_L6,
    }
    spawn_types = spawn_map.get(level_idx, SPAWN_TYPES_DEFAULT)

    rows = []
    n = 0
    for slot in range(MAX_OBJECTS):
        t = types[slot]
        if t not in spawn_types:
            continue
        kind, vx, base, aim, throw = spawn_types[t]
        # DOS: centre X i base dels peus. CPC: top-left, PH=32.
        x = (xs[slot] >> 1) - 8
        y = ys[slot] - 32
        rows.append((slot, t, x, y, kind, vx, base, aim, throw))
        n += 1

    max_enemies = 26
    if len(rows) > max_enemies:
        rows = rows[:max_enemies]
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
    # ENEMY_N es 26; la resta queden fora de pantalla i no es dibuixen.
    for i in range(n, max_enemies):
        lines.append("    { -1000, 0, 19, 0, 5, 14, 15 }, // inactiu")
    lines.append("};")
    lines.append("#endif")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").write("\n".join(lines) + "\n")
    print("%s: %d walkers actius" % (out_path, n))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--level", type=int, required=True, choices=range(0, 6))
    p.add_argument("--out", required=True)
    a = p.parse_args()
    generate(a.level, a.out)
