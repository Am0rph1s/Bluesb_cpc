#!/usr/bin/env python3
"""
pack_level.py - Empaquetador de dades de nivell per a Blues Brothers CPC (Banc 5)
=================================================================================
Extreu automàticament de les dades originals de DOS (tools/blues_dos/bb/staticres.c,
MAP0.BIN, TRIG0.BIN) les particularitats del nivell (dimensions, posició d'inici,
ascensors/entitats i spans de tiles animats com cintes i superfície d'aigua)
i genera src/level_pkg.h per ser compilat dins del mòdul de nivell al Banc 5.

Ãšs:
    py -3 tools/pack_level.py [level_num]
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

LEVEL_NAMES = ["magasin", "ent", "prison", "egou", "ville", "concert"]

# Seqüències d'animació de tiles de DOS (level_tilesdata_1e8c a staticres.c)
# indexades pel byte 4 de TRIG.BIN (op_table2). LONGITUD EXACTA 1:1 DOS
# (no MCM6): el raig d'àcid fa 20 frames (10 on + 10 off = cicle 80 loops;
# a 25 fps són 3,2 s amb finestres d'1,6 s, com els 2,67 s del DOS a 30 Hz).
# Truncar a 6 donava cicles de 24 loops (0,96 s) sense finestra útil.
DOS_ANIM_SEQS = {
    19: [147, 146, 167, 146],  # level_tiledata_1cce (4 frames; 167 = buit b6=255)
    24: [134, 135, 136],  # level_tiledata_1cea (3 frames)
    25: [137, 138, 139],  # level_tiledata_1cef (3 frames)
    29: [253, 252, 251],  # level_tiledata_1d1c: corró cinta dreta
    30: [240, 241, 242],  # level_tiledata_1d21: corró cinta esquerra
    31: [248, 249, 250],  # level_tiledata_1d26: cos cinta dreta
    32: [239, 238, 237],  # level_tiledata_1d2b: cos cinta esquerra
    59: [44, 45, 45, 44, 45, 44, 45, 44, 45, 44,
         90, 90, 90, 90, 90, 90, 90, 90, 90, 90],  # level_tiledata_1dcf (20: 10 on + 10 off b6=255)
    60: [10, 46, 47, 38, 47, 38, 46, 47, 38, 46, 38,
         10, 10, 10, 10, 10, 10, 10, 10, 10],  # level_tiledata_1de5 (20: 11 on + 9 off)
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


def build_level_pkg(level_idx=0, out_dir=None):
    measure_only = "--measure" in sys.argv
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

    # PREMSES (op11): objectes amb level_objtypes[type] == 12. Al DOS
    # (objects.c object_func_op11) puja 40 passos, baixa 40 i reescriu els
    # tiles que deixa al pas: el jugador hi puja. Coordenades: X centrat
    # (DOS 320 -> CPC 160, horitzontal 2:1) i Y als peus (vertical 1:1).
    obj_types = arrays["level_objtypes"]
    presses = []
    for slot, obj_kind in enumerate(level_data):
        if obj_kind < len(obj_types) and obj_types[obj_kind] == 12:
            dos_x = xpos_arr[slot]
            dos_y = ypos_arr[slot]
            presses.append((slot, dos_x >> 1, dos_y, dos_x >> 4))
    press_x = [p[1] for p in presses]
    press_y = [p[2] for p in presses]
    press_col = [p[3] for p in presses]

    # Coordenades exactes Mode 0 dels 5 ascensors de Magasin (slots 19..23)
    if level_idx == 0:
        elev_x = [760, 808, 760, 808, 304]
        elev_y = [384, 464, 592, 736, 784]
        elev_col = [95, 101, 95, 101, 38]
        # Spawn NATURAL del nivell 1 (13/10/26): slot DOS 39 (jugador 1) =
        # xpos 64 (peus) -> 32 ; ypos 1136 (peus) - PH 30 = 1106 (cap).
        # Havia quedat (184,860) d'un debug de globus: en Jake naixia al
        # costat dels globus en comptes del carrer. (generic: xpos>>1,
        # ypos-PH).
        start_px = 32
        start_py = 1106
        cam0_x4 = 0
        cam0_row = 124
    else:
        elev_x = [(x >> 1) for _, x, _ in elevators]
        elev_y = [y for _, _, y in elevators]
        elev_col = [(x >> 4) for _, x, _ in elevators]
        start_px = xpos_arr[39] >> 1
        # DOS dona la base dels peus; el motor CPC fa servir la cantonada
        # superior (s_py8), igual que el cas hardcoded de Magasin (ypos - PH).
        start_py = ypos_arr[39] - 30
        cam0_x4 = 0
        cam0_row = max(0, (map_h * 2) - 20)

    DOS_RESTART_X = [720, 912, 336, 288, 960, 64]
    DOS_RESTART_Y = [496, 752, 816, 304, 592, 352]
    chk_px = (DOS_RESTART_X[level_idx] - 16) // 2
    chk_py = DOS_RESTART_Y[level_idx] - 32
    chk_cam_x4 = max(0, min((map_w * 2) - 40, (chk_px - 80) // 4))
    chk_cam_row = max(0, min((map_h * 2) - 20, (chk_py - 80) // 8))

    # Fitxers del nivell (permetre N nivells: MAP<n>.BIN, TRIG<n>.BIN...)
    map_path = os.path.join(PROJ, "assets", "bbdata", "MAP%d.BIN" % level_idx)
    trig_path = os.path.join(PROJ, "assets", "bbdata", "TRIG%d.BIN" % level_idx)
    rooms_path = os.path.join(PROJ, "assets", "bbdata", "ROOMS%d.BIN" % level_idx)
    tileset_path = os.path.join(PROJ, "assets", "bbdata", "TILESET%d.BIN" % level_idx)
    map_bin = open(map_path, "rb").read()
    trig_bin = open(trig_path, "rb").read()
    rooms_bin = open(rooms_path, "rb").read() if os.path.exists(rooms_path) else b""
    tileset_full = open(tileset_path, "rb").read()

    # Només les seqs realment presents al mapa (1:1 DOS: op_table2 per tile).
    # Abans s'empaquetaven totes (12) a tots els nivells i el C5 d'L2
    # desbordava (marge 0 -> FATAL 0x80A2). Ara L1=7, L2=àcid.
    present_b4 = sorted({trig_bin[t * 10 + 4] for t in set(map_bin) | set(rooms_bin)} & set(DOS_ANIM_SEQS.keys()))
    used_b4 = present_b4
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

    # Extreure les taules de triggers d'ítems/bonus/malus (byte 6 de TRIG.BIN -> level_triggersdata_2030)
    txt = open(staticres_path, "r", encoding="utf-8", errors="replace").read()
    m6 = re.search(r"level_triggersdata_2030\[\]\s*=\s*\{([^}]*)\}", txt, re.S)
    names6 = [x.strip() for x in m6.group(1).split(",") if x.strip()]
    m4b = re.search(r"level_tilesdata_1fe8\[\]\s*=\s*\{([^}]*)\}", txt, re.S)
    names4b = [x.strip() for x in m4b.group(1).split(",") if x.strip() and x.strip() != "0"]

    used_b6 = sorted(set(trig_bin[t * 10 + 6] for t in range(256) if trig_bin[t * 10 + 6] != 255))
    # L'àcid (kind=10, b6=2/3/4) es gestiona per b6 directe a moving_bank
    # (dany segueix MAP_MUT) i no cal entrada a s_level_trig3: estalvia C5.
    # I només els b6 presents al mapa+sales (p. ex. b6=27 no hi és a L2).
    b6_in_level = set(trig_bin[t * 10 + 6] for t in set(map_bin) | set(rooms_bin))
    trig_b6 = [b6 for b6 in used_b6
               if b6 in b6_in_level and list(arrays[names6[b6]])[1] in (11, 12)]
    b6_to_idx = {b6: i for i, b6 in enumerate(trig_b6)}
    b6_lut = [b6_to_idx.get(b6, 0xFF) for b6 in range(64)]

    trig_entries = []
    for b6 in trig_b6:
        p = list(arrays[names6[b6]])
        # trig_b6 ja filtra kind 11/12 (l'àcid va per b6 directe).
        p2 = p[2]
        b4 = trig_bin[p2 * 10 + 4]
        final_bg = p2
        if 128 <= b4 < 255:
            final_bg = arrays[names4b[b4 - 128]][-1]
        # (kind=p[1], bg_tile, add_vinyls=p[3], sub_vinyls=p[4], add_heart=p[5],
        #  special_anim=p[6], instrument=p[7], exit_flag=p[8], popup_or_chk=p[9], add_life=p[10], b6)
        trig_entries.append((p[1], final_bg, p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], b6))

    # L'instrument col·leccionable obligatori viu exclusivament a la sala secreta (ROOMS0.BIN).
    # Al mapa principal no hi ha d'aparèixer duplicat.
    inst_col, inst_row, inst_tile = (0, 0, 0)

    # --- Compactacio d'IDs de tile (build-time, 1:1) ---------------------
    # Es reordena el tileset amb els tiles realment usats i es remapegen
    # mapa, sales, TRIG, restore, sequencies animades i bg_tile dels triggers.
    # Els IDs compactes son els que veu el runtime (tileset + TRIG + mapa).
    used = set(map_bin) | set(rooms_bin)
    for seq in DOS_ANIM_SEQS.values():
        used |= set(seq)
    for entry in trig_entries:
        used.add(entry[1])
    used |= {208, 159, 96}          # vinil, instrument, tile buit
    tile_order = sorted(used)
    assert len(tile_order) <= 256, len(tile_order)
    remap = [0] * 256
    for i, t in enumerate(tile_order):
        remap[t] = i
    assert len(tileset_full) == 16384, len(tileset_full)
    tileset_c = b"".join(tileset_full[t * 64:(t + 1) * 64] for t in tile_order)
    map_c = bytes(remap[t] for t in map_bin)
    rooms_c = bytes(remap[t] for t in rooms_bin)
    trig_c = b"".join(bytes((trig_bin[t * 10], trig_bin[t * 10 + 1],
                            trig_bin[t * 10 + 2], trig_bin[t * 10 + 6],
                            trig_bin[t * 10 + 9])) for t in tile_order)
    trig_entries = [
        (k, remap[bg], av, sv, ah, sa, inst, ex, pop, al, b6)
        for (k, bg, av, sv, ah, sa, inst, ex, pop, al, b6) in trig_entries
    ]
    if inst_tile:
        inst_tile = remap[inst_tile]
    tile_vinyl_c = remap[208]
    tile_instr_c = remap[159]
    tile_empty_c = remap[96]
    print("  tile compaction: %d tiles usats (tileset %d B, TRIG %d B)" %
          (len(tile_order), len(tileset_c), len(trig_c)))
    if measure_only:
        return
    for name, data in (("TILESETC%d.BIN" % level_idx, tileset_c),
                       ("MAPC%d.BIN" % level_idx, map_c),
                       ("ROOMSC%d.BIN" % level_idx, rooms_c),
                       ("TRIGC%d.BIN" % level_idx, trig_c)):
        with open(os.path.join(PROJ, "assets", "bbdata", name), "wb") as f:
            f.write(data)

    elev_storage = max(1, len(elev_x))
    span_storage = max(1, len(spans))
    trig_storage = max(1, len(trig_entries))
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
        f"#define LEVEL_CHK_PX        {chk_px}",
        f"#define LEVEL_CHK_PY        {chk_py}",
        f"#define LEVEL_CHK_CAM_X4    {chk_cam_x4}",
        f"#define LEVEL_CHK_CAM_ROW   {chk_cam_row}",
        "",
        f"#define LEVEL_ELEVATOR_COUNT {len(elev_x)}",
        f"#define LEVEL_ELEVATOR_STORAGE {elev_storage}",
        f"#define LEVEL_PRESS_COUNT {len(press_x)}",
        f"#define LEVEL_PRESS_STORAGE {max(1, len(press_x))}",
        f"#define LEVEL_HAS_ACID {(1 if any((t in (2, 3, 4)) for t in set(trig_bin[x * 10 + 6] for x in set(map_bin))) else 0)}",
        f"#define LEVEL_HAS_BALLOON {(1 if any((trig_bin[x * 10] == 8) for x in set(map_bin)) else 0)}",
        f"#define LEVEL_HAS_UMBRELLA {(1 if any((trig_bin[x * 10] == 9) for x in set(map_bin)) else 0)}",
        f"#define LEVEL_INST_COL      {inst_col}",
        f"#define LEVEL_INST_ROW      {inst_row}",
        f"#define LEVEL_INST_TILE     {inst_tile}",
        "",
        "#ifndef LEVEL_PKG_DEFS_ONLY",
        "static const i16 s_bank_start_x[LEVEL_ELEVATOR_STORAGE] = { "
        + (", ".join(str(x) for x in elev_x) if elev_x else "0")
        + " };",
        "static const i16 s_bank_start_y[LEVEL_ELEVATOR_STORAGE] = { "
        + (", ".join(str(y) for y in elev_y) if elev_y else "0")
        + " };",
        "static const u8 s_bank_map_col[LEVEL_ELEVATOR_STORAGE] = { "
        + (", ".join(str(c) for c in elev_col) if elev_col else "0")
        + " };",
        "static const i16 s_bank_press_x[LEVEL_PRESS_STORAGE] = { "
        + (", ".join(str(x) for x in press_x) if press_x else "0")
        + " };",
        "static const i16 s_bank_press_y[LEVEL_PRESS_STORAGE] = { "
        + (", ".join(str(y) for y in press_y) if press_y else "0")
        + " };",
        "static const u8 s_bank_press_map_col[LEVEL_PRESS_STORAGE] = { "
        + (", ".join(str(c) for c in press_col) if press_col else "0")
        + " };",
        "",
        "// Seqüències EXACTES 1:1 DOS en pla (sense MCM6): cada b4 cicla amb",
        "// el seu propi període (2/3/4/20 frames × tick de 4 game-frames).",
        "// Índex: tile = s_anim_data[s_anim_off[seq] + s_anim_phase[seq]].",
        "// s_anim_len porta sentinella 0 (bucle sense comptador).",
        f"#define LEVEL_ANIM_SEQ_COUNT {len(used_b4)}",
        f"#define LEVEL_ANIM_DATA_LEN {sum(len(DOS_ANIM_SEQS[b4]) for b4 in used_b4)}",
    ]
    assert len(used_b4) <= 64, "massa seqs (span.seq és u8)"
    flat, offs, lens = [], [], []
    for b4 in used_b4:
        seq = [remap[t] for t in DOS_ANIM_SEQS[b4]]
        offs.append(len(flat))
        lens.append(len(seq))
        flat.extend(seq)
    assert len(flat) <= 255, "s_anim_data no cap en índex u8"
    lines.append(
        "static const u8 s_anim_data[LEVEL_ANIM_DATA_LEN] = { "
        + ", ".join(str(t) for t in flat) + " };"
    )
    lines.append(
        "static const u8 s_anim_off[LEVEL_ANIM_SEQ_COUNT] = { "
        + ", ".join(str(o) for o in offs) + " };"
    )
    lines.append(
        "static const u8 s_anim_len[LEVEL_ANIM_SEQ_COUNT + 1] = { "
        + ", ".join(str(l) for l in lens) + ", 0 };"
    )
    lines.append("")
    lines.append("// Trams animats: (row, col_ini, col_fi, seq). Tipus AnimSpan de moving.h.")
    lines.append("")
    lines.append(f"#define LEVEL_ANIM_SPAN_COUNT {len(spans)}")
    lines.append(f"#define LEVEL_ANIM_SPAN_STORAGE {span_storage}")
    lines.append("static const AnimSpan s_level_anim_spans[LEVEL_ANIM_SPAN_STORAGE] = {")
    for r, c0, c1, seq_idx, b4 in spans:
        lines.append(
            f"    {{ {r:2d}, {c0:3d}, {c1:3d}, {seq_idx} }}, // row {r}, cols {c0}..{c1} (DOS b4={b4})"
        )
    if not spans:
        lines.append("    { 0, 0, 0, 0 },")
    lines.append("};")
    lines.append("")
    lines.append("// Taula de triggers d'ítems / bonus / malus (DOS level_triggersdata_2030)")
    lines.append("typedef struct {")
    lines.append("    u8 kind;         // 11 = directe, 12 = amb popup emergent")
    lines.append("    u8 bg_tile;      // tile de fons net que substitueix l'ítem al mapa")
    lines.append("    u8 add_vinyls;   // vinils a sumar (+1, +50)")
    lines.append("    u8 sub_vinyls;   // vinils a restar (-10, -20, -30, -40, -50)")
    lines.append("    u8 add_heart;    // +1 cor d'energia (màx 5)")
    lines.append("    u8 special_anim; // 21 = ballar")
    lines.append("    u8 instrument;   // >0 = objecte col·leccionable obligatori del nivell")
    lines.append("    u8 exit_flag;    // 1 = meta final de nivell (requereix instrument)")
    lines.append("    u8 popup_or_chk; // kind==12: grab_type (16..22); kind==11: checkpoint")
    lines.append("    u8 add_life;     // +1 vida (ulleres i barret)")
    lines.append("} LevelTriggerEntry;")
    lines.append("")
    # Identificar quins sprites emergents (grab_type 16..22) s'utilitzen realment en aquest nivell
    used_popups = sorted(set(
        pop for (kind, _, _, _, _, _, _, _, pop, _, _) in trig_entries
        if kind == 12 and 16 <= pop <= 22
    ))
    popup_to_idx = {pop: i for i, pop in enumerate(used_popups)}

    lines.append(f"#define LEVEL_TRIG3_COUNT {len(trig_entries)}")
    lines.append(f"#define LEVEL_TRIG3_STORAGE {trig_storage}")
    lines.append("static const LevelTriggerEntry s_level_trig3[LEVEL_TRIG3_STORAGE] = {")
    for kind, bg, av, sv, ah, sa, inst, ex, pop, al, b6 in trig_entries:
        pop_val = popup_to_idx.get(pop, 0xFF) if kind == 12 else pop
        lines.append(
            f"    {{ {kind:2d}, {bg:3d}, {av:2d}, {sv:2d}, {ah}, {sa:2d}, {inst}, {ex}, {pop_val:3d}, {al} }}, // DOS b6={b6}"
        )
    if not trig_entries:
        lines.append("    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },")
    lines.append("};")
    lines.append("")
    lines.append("// LUT ràpida: byte 6 de TRIG.BIN (0..63) -> índex a s_level_trig3 (0xFF = cap)")
    lines.append("static const u8 s_b6_to_trig3[64] = {")
    for i in range(0, 64, 16):
        chunk = ", ".join(f"0x{v:02X}" if v == 0xFF else f"{v:4d}" for v in b6_lut[i : i + 16])
        lines.append(f"    {chunk},")
    lines.append("};")
    lines.append("")

    # Extreure només els sprites emergents de DOS usats pel nivell (SPRITE.SQV frames 128..134 -> grab_type 16..22)
    # 16x7 px DOS -> 8x7 px Mode 0 = 4 bytes/fila * 2 [inv_mask, img] * 7 files = 56 bytes/popup
    sys.path.insert(0, os.path.join(HERE, "bbdata"))
    from sprites import load_sqv_frames  # noqa: E402
    from gen_extra_frames import encode_pair, dos_to_cpc_pen  # noqa: E402

    sqv_frames = load_sqv_frames(os.path.join(PROJ, "assets", "bbdata", "SPRITE.SQV"))
    popup_labels = {16: "-10", 17: "-20", 18: "-30", 19: "-40", 20: "-50", 21: "+50", 22: "1UP"}
    popup_storage = max(1, len(used_popups))
    lines.append(f"#define LEVEL_POPUP_COUNT {len(used_popups)}")
    lines.append(f"#define LEVEL_POPUP_STORAGE {popup_storage}")
    lines.append("static const u8 s_popup_sprites[LEVEL_POPUP_STORAGE][56] = {")
    for idx_p, pop_gt in enumerate(used_popups):
        dos_f = 128 + (pop_gt - 16)
        w, h, px = sqv_frames[dos_f]
        raw = []
        for y in range(7):
            m0_pens = []
            for xm in range(8):
                p0 = px[y][xm * 2]
                p1 = px[y][xm * 2 + 1]
                val = p0 if p0 != 0 else p1
                m0_pens.append(dos_to_cpc_pen.get(val))
            for xb in range(4):
                inv_mask, img = encode_pair(m0_pens[xb * 2], m0_pens[xb * 2 + 1])
                raw.append(inv_mask)
                raw.append(img)
        hex_str = ", ".join(f"0x{b:02X}" for b in raw)
        lines.append(f"    {{ {hex_str} }}, // {idx_p}: grab_type {pop_gt} ({popup_labels[pop_gt]})")
    if not used_popups:
        lines.append("    { " + ", ".join(["0"] * 56) + " },")
    lines.append("};")
    lines.append("#endif // LEVEL_PKG_DEFS_ONLY")
    lines.append("")
    lines.append("#endif")

    hdr_dir = out_dir if out_dir else os.path.join(PROJ, "src")
    os.makedirs(hdr_dir, exist_ok=True)
    out_path = os.path.join(hdr_dir, "level_pkg.h")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(
        f"Generat {out_path}: nivell {level_idx + 1} ({lname}), "
        f"{len(elev_x)} ascensors, {len(spans)} spans animats, {len(trig_entries)} triggers bonus/malus."
    )

    # ==========================================================================
    # Taula de RESTAURACIO en reinici per mort.
    # 1:1 DOS: al morir, game.c torna a cridar load_level_data() i el mapa es
    # re-llegeix del disc -> discos, cors, ulleres i interrogants reapareixen.
    # Aqui NO recarreguem res: guardem les posicions que es poden modificar i el
    # seu TILE INICIAL (el de MAP0.BIN). Els comptadors de tile son sempre els
    # mateixos en carregar, aixi que n'hi ha prou de tornar-los a escriure.
    #  - kind 11/12 (portes/checkpoints/bonus): el tile es consumeix.
    #  - types 5/8/9 (caixa/globus/paraigua): el tile s'esborra en agafar-los.
    # L'item secret NO s'hi posa: el seu estat persisteix (DOS).
    # Format: [n u16 LE] + n * (col, row, tile)
    # ==========================================================================
    restore = []
    for r in range(map_h):
        for c in range(map_w):
            t = map_c[(r << 7) + c]
            canviable = trig_c[t * 5 + 0] in (5, 8, 9)
            if not canviable:
                b6 = trig_c[t * 5 + 3]
                if b6 < 64:
                    i = b6_lut[b6]
                    if i != 0xFF and trig_entries[i][0] in (11, 12):
                        canviable = True
            if canviable and not (c == inst_col and r == inst_row):
                restore.append((c, r, t))
    blob = struct.pack("<H", len(restore))
    blob += b"".join(bytes((c, r, t)) for c, r, t in restore)
    restore_path = os.path.join(PROJ, "assets", "bbdata", "RESTORE%d.BIN" % level_idx)
    with open(restore_path, "wb") as f:
        f.write(blob)
    print("  RESTORE%d.BIN: %d posicions restaurables (%d bytes)"
          % (level_idx, len(restore), len(blob)))

    # --- Bloc de PARAMETRES DEL NIVELL per al paquet -----------------------
    # Tot el que es del nivell (geometria del mapa, de les habitacions, tiles
    # dels items, posicio inicial, checkpoint, parametres de camera) va aqui,
    # al paquet, i el resident el llegeix en carregar: al Bloc 0 no hi ha de
    # quedar cap constant del nivell 1.
    prm = bytearray()
    prm += bytes((0xB0, 1))                  # magic, version
    room_count = len(rooms_bin) // 200
    txt_level = open(os.path.join(HERE, "blues_dos", "bb", "level.c"),
                     encoding="latin1").read()
    mpos = re.search(r"uint8_t\s+pos\[\]\s*=\s*\{([^}]*)\}", txt_level)
    room_pos = [int(x.strip(), 0) for x in mpos.group(1).split(",") if x.strip()]
    r0 = room_pos[level_idx] if level_idx < len(room_pos) else 0
    room_total_cols = 20 * room_count
    room_floor_row = r0 + 9
    room_cam_row = r0 * 2
    prm += bytes((room_count, 20, 10))        # habitacions, columnes, files
    prm += bytes((r0, room_floor_row, room_total_cols, room_cam_row))
    prm += bytes((tile_vinyl_c, tile_instr_c, tile_empty_c))  # vinil, instrument, buit (compactes)
    prm += bytes((5, level_idx))              # nombre d'ascensors, id del nivell
    # Offsets de fila dins el mapa de les habitacions (el resident no ha de
    # multiplicar: multiplicar 16 bits costa codi).
    prm += b"".join(struct.pack("<H", r * room_total_cols) for r in range(10))
    prm += struct.pack("<hhhhhhhh", start_px, start_py, cam0_x4, cam0_row,
                       chk_px, chk_py, chk_cam_x4, chk_cam_row)
    prm += struct.pack("<H", max(0, (map_h * 2) - 20))   # fila maxima de camera
    # --- v2: geometries i OFFSETS dels blocs (Fase 3, PLA_NIVELLS_UNIVERSAL) --
    # El build els reescriu si cal (build.py); aqui van els valors actuals perque
    # el fitxer sigui autosuficient.
    doors_path = os.path.join(PROJ, "assets", "bbdata", "DOORS%d.BIN" % level_idx)
    door_count = (len(open(doors_path, "rb").read()) // 4) if os.path.exists(doors_path) else 0
    prm += bytes((map_w & 0xFF, map_h & 0xFF, map_h & 0xFF, door_count))
    prm += struct.pack("<HHH", 0x6400, 0x6800, 0x6860)  # rooms (C5), doors/restore (C1)
    # Valors derivats perque el resident NO faci matematiques de 16 bits:
    prm += struct.pack("<HHH", map_w * 8, map_w * 2, max(0, map_w * 2 - 20))
    # NOTA: SDCC empaqueta LevelParams sense alineacio: room_row_last=68,
    # trig_off=69, code_exc_off=71 (sizeof=73). El blob ha de coincidir-hi.
    prm += bytes(((room_floor_row & 0xFF),))            # room_row_last
    prm += struct.pack("<H", 0x67E8)                   # trig_off (el build el reescriu)
    prm += struct.pack("<H", 0x6934)                   # code_exc_off (el build el reescriu)
    assert len(prm) == 73, len(prm)
    parm_path = os.path.join(PROJ, "assets", "bbdata", "LEVELPARM%d.BIN" % level_idx)
    with open(parm_path, "wb") as f:
        f.write(bytes(prm))
    print("  LEVELPARM%d.BIN: %d bytes (parametres del nivell per al paquet)"
          % (level_idx, len(prm)))

    build_hud_pkg(level_idx, sqv_frames, hdr_dir)


def encode_m0_byte(p0, p1):
    b0 = ((p0 & 1) << 7) | (((p0 >> 1) & 1) << 3) | (((p0 >> 2) & 1) << 5) | (((p0 >> 3) & 1) << 1)
    b1 = ((p1 & 1) << 6) | (((p1 >> 1) & 1) << 2) | (((p1 >> 2) & 1) << 4) | (((p1 >> 3) & 1) << 0)
    return b0 | b1


def grid_to_strip24(grid12x4):
    """Converteix una columna de 12 files x 4 píxels Mode 0 en 24 bytes:
    bytes 0..11 = sy=20 (ra=2..7), bytes 12..23 = sy=21 (ra=0..5)."""
    out = []
    for y in range(12):
        r = grid12x4[y]
        out.append(encode_m0_byte(r[0], r[1]))
        out.append(encode_m0_byte(r[2], r[3]))
    return out


def build_hud_pkg(level_idx, sqv_frames, out_dir=None):
    bar_pen = {11: 11, 4: 4, 3: 2, 8: 12, 15: 0, 5: 1}
    inst_uncol_pen = {11: 11, 4: 4, 3: 2, 8: 12, 15: 0}
    inst_col_pen = {11: 11, 4: 4, 3: 2, 8: 12, 7: 7, 5: 1, 15: 0}

    _, _, px124 = sqv_frames[124]
    bar_rows = [bar_pen.get(px124[y][10], 11) for y in range(12)]

    # 0: bar, 1: cap_l, 2: cap_r
    strip_bar = [[bar_rows[y]] * 4 for y in range(12)]
    strip_cap_l = [[bar_pen.get(px124[y][xm * 2], 11) for xm in range(4)] for y in range(12)]
    strip_cap_r = [[bar_pen.get(px124[y][312 + xm * 2], 11) for xm in range(4)] for y in range(12)]

    # 3, 4: Jake icon (#115, 8x12 -> 2 strips of 4x12)
    _, _, px115 = sqv_frames[115]
    jake_grid = []
    for y in range(12):
        row = []
        for xm in range(8):
            p0, p1 = px115[y][xm * 2], px115[y][xm * 2 + 1]
            if xm == 0 or xm == 7:
                pen = bar_rows[y] if (p0 in (3, 4, 11) and p1 in (3, 4, 11)) else 11
            elif 5 in (p0, p1) or 7 in (p0, p1):
                pen = 1
            elif 4 in (p0, p1):
                pen = 4
            else:
                pen = 11
            row.append(pen)
        jake_grid.append(row)

    # 5 slots col.leccionables (un per nivell): gris DOS #135+i, color DOS #140+i.
    # Cada icona 8x12 -> 2 tires de 4x12. Indices: slot i -> gris 23+4i,24+4i;
    # color 25+4i,26+4i (total tires 23..42). Es mantenen 0..22 intactes.
    inst_grids = []
    for slot in range(5):
        _, _, px_ioff = sqv_frames[135 + slot]
        _, _, px_ion = sqv_frames[140 + slot]
        ioff_grid, ion_grid = [], []
        for y in range(12):
            r_off, r_on = [], []
            for xm in range(8):
                p0, p1 = px_ioff[y][xm * 2], px_ioff[y][xm * 2 + 1]
                val = p0 if p0 != 11 else p1
                r_off.append(inst_uncol_pen.get(val, 11))

                p0, p1 = px_ion[y][xm * 2], px_ion[y][xm * 2 + 1]
                val = p0 if p0 != 11 else p1
                r_on.append(inst_col_pen.get(val, 11))
            ioff_grid.append(r_off)
            ion_grid.append(r_on)
        inst_grids.append((ioff_grid, ion_grid))

    # 9, 10: Vinyl icon (8x12 -> 2 strips)
    vinyl_ascii = [
        "........",
        "..BBBB..",
        ".B4BBBB.",
        "B4BB77BB",
        "BBB7007B",
        "BB70BB07",
        "BB70BB07",
        "BBB7007B",
        "BBBB77B4",
        ".BBBB4B.",
        "..BBBB..",
        "........",
    ]
    vinyl_grid = [
        [bar_rows[y] if ch == "." else int(ch, 16) for ch in vinyl_ascii[y]]
        for y in range(12)
    ]

    # 11, 12: Heart icon (#120, 8x12 -> 2 strips)
    _, _, px120 = sqv_frames[120]
    heart_grid = []
    for y in range(12):
        row = []
        for xm in range(8):
            p0, p1 = px120[y][xm * 2], px120[y][xm * 2 + 1]
            if y in (3, 4) and xm == 2:
                pen = 0
            elif 15 in (p0, p1) and 1 < y < 9 and 0 < xm < 6:
                pen = 7
            elif 5 in (p0, p1):
                pen = 1
            elif 7 in (p0, p1):
                pen = 13
            elif 11 in (p0, p1):
                pen = 11
            else:
                pen = bar_rows[y]
            row.append(pen)
        heart_grid.append(row)

    # 13..22: Digits 0..9 (4x12 each)
    digits_ascii = [
        ["111", "101", "101", "101", "101", "101", "111"],
        ["010", "110", "010", "010", "010", "010", "111"],
        ["111", "001", "001", "111", "100", "100", "111"],
        ["111", "001", "001", "111", "001", "001", "111"],
        ["101", "101", "101", "111", "001", "001", "001"],
        ["111", "100", "100", "111", "001", "001", "111"],
        ["111", "100", "100", "111", "101", "101", "111"],
        ["111", "001", "001", "001", "001", "001", "001"],
        ["111", "101", "101", "111", "101", "101", "111"],
        ["111", "101", "101", "111", "001", "001", "111"],
    ]
    digit_strips = []
    for d in range(10):
        g = digits_ascii[d]
        d_grid = []
        for y in range(12):
            row = []
            gy = y - 2
            for xm in range(4):
                pen = bar_rows[y]
                if 0 <= gy < 7 and xm < 3 and g[gy][xm] == "1":
                    pen = 11
                elif 0 <= gy - 1 < 7 and 0 <= xm - 1 < 3 and g[gy - 1][xm - 1] == "1":
                    pen = 4
                row.append(pen)
            d_grid.append(row)
        digit_strips.append(grid_to_strip24(d_grid))

    strips = [
        ("bar", grid_to_strip24(strip_bar)),
        ("cap_l", grid_to_strip24(strip_cap_l)),
        ("cap_r", grid_to_strip24(strip_cap_r)),
        ("jake_0", grid_to_strip24([r[:4] for r in jake_grid])),
        ("jake_1", grid_to_strip24([r[4:] for r in jake_grid])),
        ("vinyl_0", grid_to_strip24([r[:4] for r in vinyl_grid])),
        ("vinyl_1", grid_to_strip24([r[4:] for r in vinyl_grid])),
        ("heart_0", grid_to_strip24([r[:4] for r in heart_grid])),
        ("heart_1", grid_to_strip24([r[4:] for r in heart_grid])),
    ]
    for d in range(10):
        strips.append((f"digit_{d}", digit_strips[d]))
    # 23..42: slots col.leccionables (gris parell, color imparell per slot).
    for slot in range(5):
        ioff_grid, ion_grid = inst_grids[slot]
        strips.append((f"inst{slot}_off_0", grid_to_strip24([r[:4] for r in ioff_grid])))
        strips.append((f"inst{slot}_off_1", grid_to_strip24([r[4:] for r in ioff_grid])))
        strips.append((f"inst{slot}_on_0", grid_to_strip24([r[:4] for r in ion_grid])))
        strips.append((f"inst{slot}_on_1", grid_to_strip24([r[4:] for r in ion_grid])))

    h_lines = [
        "#ifndef HUD_PKG_H",
        "#define HUD_PKG_H",
        "",
        "// Generat automàticament per tools/pack_level.py. NO EDITAR MANUALMENT.",
        "// NON-static a proposit: viu al banc C2 (src/hud_strips.c) via EQU;",
        "// render.c hi accedeix amb bank_set(0xC2) (dieta Bloc 0, 10/26).",
        "// 39 tires de columna CRTC (4x12 px Mode 0 = 24 bytes cadascuna):",
        "//   0: barra, 1..2: extrems, 3..4: Jake, 5..6: vinil, 7..8: cor,",
        "//   9..18: dígits 0..9, 19..38: slots col.leccionables (slot i:",
        "//   gris 19+4i,20+4i; color 21+4i,22+4i).",
        "const u8 s_hud_strips[39][24] = {",
    ]
    for idx, (label, data) in enumerate(strips):
        hex_s = ", ".join(f"0x{b:02X}" for b in data)
        h_lines.append(f"    {{ {hex_s} }}, // {idx:2d}: {label}")
    h_lines.append("};")
    h_lines.append("")
    h_lines.append("#endif")

    hud_dir = out_dir if out_dir else os.path.join(PROJ, "src")
    os.makedirs(hud_dir, exist_ok=True)
    hud_path = os.path.join(hud_dir, "hud_pkg.h")
    with open(hud_path, "w", encoding="utf-8") as f:
        f.write("\n".join(h_lines) + "\n")
    print(f"Generat {hud_path}: 23 tires Mode 0 (552 B) per al HUD del nivell {level_idx + 1}.")


if __name__ == "__main__":
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    out_dir = None
    if "--outdir" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--outdir") + 1]
    build_level_pkg(lvl, out_dir)

