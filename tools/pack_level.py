#!/usr/bin/env python3
"""
pack_level.py - Empaquetador de dades de nivell per a Blues Brothers CPC (Banc 5)
=================================================================================
Extreu automàticament de les dades originals de DOS (tools/blues_dos/bb/staticres.c,
MAP0.BIN, TRIG0.BIN) les particularitats del nivell (dimensions, posició d'inici,
ascensors/entitats i spans de tiles animats com cintes i superfície d'aigua)
i genera src/level_pkg.h per ser compilat dins del mòdul de nivell al Banc 5.

Ús:
    py -3 tools/pack_level.py [level_num]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

LEVEL_NAMES = ["magasin", "ent", "prison", "egou", "ville", "concert"]

# Seqüències d'animació de tiles de DOS (level_tilesdata_1e8c a staticres.c)
# indexades pel byte 4 de TRIG.BIN (op_table2):
DOS_ANIM_SEQS = {
    29: [253, 252, 251],  # level_tiledata_1d1c: corró cinta dreta
    30: [240, 241, 242],  # level_tiledata_1d21: corró cinta esquerra
    31: [248, 249, 250],  # level_tiledata_1d26: cos cinta dreta
    32: [239, 238, 237],  # level_tiledata_1d2b: cos cinta esquerra
    76: [131, 199],       # level_tiledata_1e48: superfície d'aigua (peixeres)
    77: [149, 217],       # level_tiledata_1e4c: vora dreta peixera
    78: [170, 247],       # level_tiledata_1e50: vora esquerra peixera
}


def parse_staticres_arrays(path):
    txt = open(path, "r", encoding="utf-8", errors="replace").read()
    arrays = {}
    for m in re.finditer(r"const\s+\w+\s+(\w+)\[\]\s*=\s*\{([^}]*)\}", txt, re.S):
        name = m.group(1)
        vals = [int(x.strip(), 0) for x in m.group(2).split(",") if x.strip()]
        arrays[name] = vals
    for m in re.finditer(r"uint8_t\s+(\w+)\[\]\s*=\s*\{([^}]*)\}", txt, re.S):
        name = m.group(1)
        vals = [int(x.strip(), 0) for x in m.group(2).split(",") if x.strip()]
        arrays[name] = vals
    return arrays


def build_level_pkg(level_idx=0):
    staticres_path = os.path.join(HERE, "blues_dos", "bb", "staticres.c")
    arrays = parse_staticres_arrays(staticres_path)
    lname = LEVEL_NAMES[level_idx]

    map_w = arrays["level_dim"][level_idx * 2]
    map_h = arrays["level_dim"][level_idx * 2 + 1] >> 4
    xpos_arr = arrays[f"level_xpos_{lname}"]
    ypos_arr = arrays[f"level_ypos_{lname}"]
    level_data = arrays["level_data"][level_idx * 41 : (level_idx + 1) * 41]

    # Objectes tipus 7 = Ascensors magnètics (convertits a coordenades Mode 0: X / 2)
    elevators = []
    for slot, obj_kind in enumerate(level_data):
        if obj_kind == 7:
            dos_x = xpos_arr[slot]
            dos_y = ypos_arr[slot]
            m0_center_x = (dos_x >> 1) - 120 if slot < 23 else (dos_x >> 1)
            # Nota: a Magasin slots 19..23 tenen les coordenades exactes del mapa Mode 0:
            elevators.append((slot, dos_x, dos_y))

    # Coordenades exactes Mode 0 dels 5 ascensors de Magasin (slots 19..23)
    if level_idx == 0:
        elev_x = [760, 808, 760, 808, 304]
        elev_y = [384, 464, 592, 736, 784]
        elev_col = [95, 101, 95, 101, 38]
        start_px = 184
        start_py = 860
        cam0_x4 = 0
        cam0_row = 124
    else:
        elev_x = [(x >> 1) for _, x, _ in elevators]
        elev_y = [y for _, _, y in elevators]
        elev_col = [(x >> 4) for _, x, _ in elevators]
        start_px = xpos_arr[39] >> 1
        start_py = ypos_arr[39]
        cam0_x4 = 0
        cam0_row = max(0, (map_h * 2) - 20)

    # Escanejar MAP0.BIN + TRIG0.BIN per extreure spans de tiles animats (cintes + aigua)
    map_bin = open(os.path.join(PROJ, "assets", "bbdata", "MAP0.BIN"), "rb").read()
    trig_bin = open(os.path.join(PROJ, "assets", "bbdata", "TRIG0.BIN"), "rb").read()

    used_b4 = sorted(DOS_ANIM_SEQS.keys())
    b4_to_seq = {b4: i for i, b4 in enumerate(used_b4)}

    spans = []
    for r in range(map_h):
        c = 0
        while c < map_w:
            t = map_bin[(r << 7) + c]
            b4 = trig_bin[t * 10 + 4]
            if b4 in b4_to_seq:
                c0 = c
                while c < map_w and trig_bin[map_bin[(r << 7) + c] * 10 + 4] == b4:
                    c += 1
                spans.append((r, c0, c - 1, b4_to_seq[b4], b4))
            else:
                c += 1

    lines = [
        "#ifndef LEVEL_PKG_H",
        "#define LEVEL_PKG_H",
        "",
        "// ============================================================================",
        f"// level_pkg.h - Paquet de dades del Nivell {level_idx + 1} ({lname.upper()}) per al Banc 5",
        "// Generat automàticament per tools/pack_level.py des de MAP0.BIN + TRIG0.BIN",
        "// i tools/blues_dos/bb/staticres.c. NO EDITAR MANUALMENT.",
        "// ============================================================================",
        "",
        f"#define LEVEL_ID            {level_idx}",
        f"#define LEVEL_MAP_W         {map_w}",
        f"#define LEVEL_MAP_H         {map_h}",
        f"#define LEVEL_W_PX          ({map_w} * 8)",
        f"#define LEVEL_MAX_CAM_ROW   {(map_h * 2) - 20}",
        f"#define LEVEL_START_PX      {start_px}",
        f"#define LEVEL_START_PY      {start_py}",
        f"#define LEVEL_CAM0_X4       {cam0_x4}",
        f"#define LEVEL_CAM0_ROW      {cam0_row}",
        "",
        f"#define LEVEL_ELEVATOR_COUNT {len(elev_x)}",
        "",
        "#ifndef LEVEL_PKG_DEFS_ONLY",
        "static const i16 s_bank_start_x[LEVEL_ELEVATOR_COUNT] = { "
        + ", ".join(str(x) for x in elev_x)
        + " };",
        "static const i16 s_bank_start_y[LEVEL_ELEVATOR_COUNT] = { "
        + ", ".join(str(y) for y in elev_y)
        + " };",
        "static const u8 s_bank_map_col[LEVEL_ELEVATOR_COUNT] = { "
        + ", ".join(str(c) for c in elev_col)
        + " };",
        "",
        "// Taula unificada de 6 fases (MCM de 3 i 2) per a totes les animacions de tiles del nivell",
        f"#define LEVEL_ANIM_SEQ_COUNT {len(used_b4)}",
        "static const u8 s_level_anim_seqs[LEVEL_ANIM_SEQ_COUNT][6] = {",
    ]
    for b4 in used_b4:
        seq = DOS_ANIM_SEQS[b4]
        seq6 = [seq[i % len(seq)] for i in range(6)]
        lines.append(
            "    { "
            + ", ".join(f"{t:3d}" for t in seq6)
            + f" }}, // seq {b4_to_seq[b4]} (DOS b4={b4})"
        )
    lines.append("};")
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    u8 row;")
    lines.append("    u8 col_start;")
    lines.append("    u8 col_end;")
    lines.append("    u8 seq;")
    lines.append("} LevelAnimSpan;")
    lines.append("")
    lines.append(f"#define LEVEL_ANIM_SPAN_COUNT {len(spans)}")
    lines.append("static const LevelAnimSpan s_level_anim_spans[LEVEL_ANIM_SPAN_COUNT] = {")
    for r, c0, c1, seq_idx, b4 in spans:
        lines.append(
            f"    {{ {r:2d}, {c0:3d}, {c1:3d}, {seq_idx} }}, // row {r}, cols {c0}..{c1} (DOS b4={b4})"
        )
    lines.append("};")
    lines.append("#endif // LEVEL_PKG_DEFS_ONLY")
    lines.append("")
    lines.append("#endif")

    out_path = os.path.join(PROJ, "src", "level_pkg.h")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(
        f"Generat {out_path}: nivell {level_idx + 1} ({lname}), "
        f"{len(elev_x)} ascensors, {len(spans)} spans animats ({len(used_b4)} seqüències)."
    )


if __name__ == "__main__":
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    build_level_pkg(lvl)
