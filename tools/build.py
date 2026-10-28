#!/usr/bin/env python3
"""
build.py - Build de Blues Brothers CPC amb SDCC 4.5 (natiu Windows).
Compila, enllaça, empaqueta el DSK (afegint els fitxers de dades PRIMER per
que les seves coordenades CHS no depenguin del tamany del codi) i genera
src/disk_tables.h amb les taules CHS per al carregador FDC raw.
"""
import os
import sys
import re
import shutil
import json
import hashlib
import subprocess
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from ihx2bin import convert_ihx          # noqa: E402
from dskutil import DskPatcher, create_empty_cpc_dsk, amsdos_header  # noqa: E402

SDCC    = r"C:\Program Files\SDCC\bin\sdcc.exe"
SDASZ80 = r"C:\Program Files\SDCC\bin\sdasz80.exe"

CFLAGS    = ["-mz80", "--opt-code-size", "--max-allocs-per-node", "15000",
             "--disable-warning", "110"]
# El _DATA comença a 0x3880. El Bloc 0 esta ple; amb el codi dels ascensors
# fora del resident (Banc 1) el marge de codi es de 836 B.
# La PILA no canvia: el canari (0x3D00) i el limit de la pila (SP=0x3FFE) son
# els mateixos; el _DATA acaba per sota del canari.
LINKARGS  = ["-mz80", "--no-std-crt0", "-Wl-u",
             "--code-loc", "0x0100", "--data-loc", "0x3880", "-Wl-x"]
INCLUDES  = ["-I" + os.path.join(PROJ, "engine"),
             "-I" + os.path.join(PROJ, "src")]

ASM_SOURCES = [
    "engine/cpc_hardware.s",
    "engine/assets_fdc.s",
    # F1-FRONT: decoder ZX0 (el linka l'starter per desempacar pantalles;
    # el GAME no el necessita -> GAME_LINK_SKIP).
    "engine/zx0_decompress.s",
    # TEMPORALMENT EXCLOSOS (pes mort ~2KB linkat sense cridar;
    # el Bloc 0 no dona per features + reserva):
    # - engine/audio.s -> retornar a CP-5 (cablejar audio_init/update+sfx)
    "engine/video.s",
    "engine/isr.s",
    "engine/sprite.s",
    "engine/moving_blit.s",
    "engine/tile_blit.s",
    "engine/sprite_hflip.s",
    "engine/mus.s",  # stubs AKG (Init/Play via EQU obj/mus_ext.s)
]
C_SOURCES = [
    "engine/fdc.c",
    "src/render.c",
    "src/moving.c",
    "src/main.c",
]
# F1: el GAME ja no enllaca el FDC (viu al Banc 6, scratch central).
# Es continuen compilant (l'starter enllaca obj/fdc.rel + obj/assets_fdc.rel).
# F1-MUSICA: el GAME tampoc enllaca el decoder ZX0 (viu al FRONT.BIN C4;
# nomes el FRONT el crida). Guany ~94 B de Bloc 0 (overflow 53 B, 12/10/26).
GAME_LINK_SKIP = {"engine/fdc.c", "engine/assets_fdc.s"}
C_HEADERS = {
    "engine/fdc.c": ["engine/fdc.h", "engine/cpctelera.h"],
    "src/render.c": ["engine/cpctelera.h", "engine/bank.h", "src/moving.h", "src/sprite.h", "src/hud_pkg.h"],
    "src/moving.c": ["engine/cpctelera.h", "engine/bank.h", "src/moving.h", "src/sprite.h", "engine/fdc.h", "src/level_pkg.h"],
    "src/main.c": ["engine/cpctelera.h", "engine/fdc.h", "engine/front.h", "engine/mus.h", "src/disk_tables.h",
                   "src/sprite.h", "src/moving.h", "src/player_frames.h",
                   "engine/stack_canary.h", "src/crt_addrs.h", "src/level_pkg.h", "src/level_params.h"],
}

PROGNAME = "bluesb"
DSKNAME8 = "BLUESB"

# --- Banc C3 (walkers L1): frames + codi + dades (CP-2.2, com el Banc 5)
# (C3 i no C2: OUT(0x7F00,0xC2) penja la maquina, vist 10/26.)
# Frames ENEMI1.BIN (14x512 B) a 0x4000; taula de salts fixa a 0x5C00
# (engine/enemy_table.s, slots init/update/restore/draw); codi+dades
# fins 0x8000 (pool de fons inclos). ENEMI.BIN = frames + imatge codi.
ENEMY_BASE = 0x5C00
ENEMY_DATA = 0x5820  # dins l'area alliberada pels frames comprimits (cache 0x5000..0x57FF, estat 0x5800..0x581F)
ENEMY_FRAMES = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.BIN")
# L2-L6: ENEMI2.BIN..ENEMI6.BIN (mateix format de 16 celes); build_enemybank
# els tria per level_idx.
ENEMY_C_SOURCES = ["src/enemy.c"]
ENEMY_ASM_SOURCES = ["engine/enemy_table.s"]
ENEMY_C_HEADERS = {
    "src/enemy.c": ["engine/cpctelera.h", "engine/bank.h",
                    "src/moving.h", "src/sprite.h", "src/enemy.h", "src/level_pkg.h"],
}

# --- Banc 5 (CP-2.2): lògica moving.* a 0x6E00; slots fixos 0x6E00+3k
# (han de coincidir amb engine/bank5_table.s; build_bank() ho verifica).
BANK5_BASE = 0x6E00
# Layout C1 VARIABLE per nivell (blindat per sota de 0x7800 per no tocar FDC.BIN a C0:0x7800):
# canco + HUD + GAMEOVER + portes + restore + codi + frames + buffers BG.
# Parametres a C1:0x7680 (77 B), dades BSS a 0x7700 (20 B). Tot < 0x7780.
LC1_FRAMES_BASE  = 0x6900
LC1_BG_BASE      = 0x6D00
LC1_PARAMS_BASE  = 0x7680
LC1_DATA_BASE    = 0x7700
LC1_ELEV_BG_SIZE = 1120   # 2 pagines x 5 ascensors x 112 B
BANK5_MAXLEN = 0x1200   # finestra: CODE + pad zeros fins fi _DATA (0x7E07);
                        # el banc físic dona fins 0x7FFF, de sobres.
BANK_C_SOURCES = ["src/moving_bank.c"]
BANK_ASM_SOURCES = ["engine/bank5_table.s"]
BANK_C_HEADERS = {
    "src/moving_bank.c": ["engine/cpctelera.h", "engine/bank.h",
                          "src/moving.h", "src/sprite.h", "src/level_pkg.h",
                          "src/level_params.h"],
}

# FRONT banked (overlay d'arrencada C4:0x4000, descartable per TILESET).
# front.c (show/key/pal, nomes central/VRAM/PPI/GA) + front_table.s (slot JP)
# + front_ext.s (EQU externs centrals generat del mapa resident).
FRONT_BASE = 0x4000
# FRONT_DATA a 0x4900 (era 0x4800): helper f_load (3 carregues al splash,
# musica intacta) no cabia en 2048 B de _CODE.
# C4:0x4300-0x4FFF lliure durant el FRONT (nomes hi viu FRONT.BIN; el
# TILESET el trepitja despres). Historial: 0x4200 -> 0x4300 (select L/R)
# -> 0x4450 -> 0x44C0 (mini-DANCE 4f) -> 0x4640 (DANCE20) -> 0x4700
# -> 0x4800 (map sticker) -> 0x4900 (tot carregat al splash).
FRONT_DATA = 0x4900
FRONT_MAXLEN = 0x1000
FRONT_C_SOURCE = "engine/front.c"
FRONT_C_HEADERS = ["engine/cpctelera.h", "engine/fdc.h", "engine/front.h", "engine/front_tables.h"]

# MUSICA (banc C1, AT3 AKG): player a MUS_PLAYER_BASE + canco a MUS_SONG_SLOT
# (les 4 fan 1.6-4.7 KB; player ~3.1 KB). MUSBANK.BIN = player + intro (el
# carrega l'starter); MUSMAIN.BIN = tema nivell 1 (el carrega el GAME).
MUS_BANK = 0xC1
MUS_PLAYER_BASE = 0x4000
MUS_SONG_SLOT = 0x5000
MUS_PLAYER_SRC = "tools/akg/PlayerAkg.asm"
MUS_INTRO_SRC = "assets/musica_cpc/The_Blues_Brothers_Intro_CPC.akg"
MUS_MAIN_SRC = "assets/musica_cpc/The_Blues_Brothers_CPC.akg"
MUS_THEME1_SRC = "assets/musica_cpc/The_Blues_Brothers_Theme1_CPC.akg"
MUS_THEME2_SRC = "assets/musica_cpc/The_Blues_Brothers_Theme2_CPC.akg"

# Taules Bloc 0 justes: el GAME nomes referencia els fitxers del gameplay del nivell
GAME_TABLE_SKIP = {"FDC", "FSPLASH", "FSELECT", "FMAP", "MUSBANK",
                   "L1WORLD", "L1ENEMI", "L2WORLD", "L2ENEMI",
                   "L3WORLD", "L3ENEMI", "L4WORLD", "L4ENEMI",
                   "L5WORLD", "L5ENEMI", "L6WORLD", "L6ENEMI",
                   "L1C1", "L2C1", "L3C1", "L4C1", "L5C1", "L6C1"}

# Fitxers de dades al DSK (es carregaran per FDC raw). Ordre = ordre al disc.
# (L'ordre de dades no afecta el boot; el BLUESB va primer via package().)
DATA_FILES = [
    # 1. Boot / Starter
    ("FDC",     "BIN", os.path.join(PROJ, "obj", "FDC.BIN")),
    ("FRONT",   "BIN", os.path.join(PROJ, "obj", "FRONT.BIN")),
    # 2. Menú / Prejoc
    ("FSPLASH", "ZX0", os.path.join(PROJ, "obj", "FSPLASH.ZX0")),
    ("MUSBANK", "BIN", os.path.join(PROJ, "obj", "MUSBANK.BIN")),
    ("FSELECT", "ZX0", os.path.join(PROJ, "obj", "FSELECT.ZX0")),
    ("FMAP",    "ZX0", os.path.join(PROJ, "obj", "FMAP.ZX0")),
    # 3. Personatges (permanents al Banc C7)
    ("JAKE",    "ZX0", os.path.join(PROJ, "obj", "JAKE.ZX0")),
    ("ELWOOD",  "ZX0", os.path.join(PROJ, "obj", "ELWOOD.ZX0")),
    # 4. Paquets Nivell 1 + GAMEOVER comu
    ("L1WORLD", "PAK", os.path.join(PROJ, "obj", "L1WORLD.PAK")),
    ("L1ENEMI", "ZX0", os.path.join(PROJ, "obj", "L1ENEMI.ZX0")),
    ("L2WORLD", "PAK", os.path.join(PROJ, "obj", "L2WORLD.PAK")),
    ("L2ENEMI", "ZX0", os.path.join(PROJ, "obj", "L2ENEMI.ZX0")),
    ("L3WORLD", "PAK", os.path.join(PROJ, "obj", "L3WORLD.PAK")),
    ("L3ENEMI", "ZX0", os.path.join(PROJ, "obj", "L3ENEMI.ZX0")),
    ("L3C1",    "PAK", os.path.join(PROJ, "obj", "L3C1.PAK")),
]


def run(cmd):
    print("+ " + " ".join(cmd))
    if subprocess.run(cmd).returncode != 0:
        print("ERROR: " + " ".join(cmd))
        sys.exit(1)


def is_stale(target, sources):
    # Frescor per mtime O per hash de contingut (l'mtime sol no és fiable:
    # algunes eines preserven mtime en editar i el build incremental
    # enllaçaria .rel rancis amb taules noves = DSK incoherent).
    # PURA consulta (sense efectes): el marcatge es fa amb mark_fresh()
    # DESPRÃ‰S de compilar bé (abans, un kill a mig SDCC enverinava el
    # hash i el següent build saltava la recompilació = binari ranci).
    if not os.path.exists(target):
        return True
    t = os.path.getmtime(target)
    if any(os.path.exists(s) and os.path.getmtime(s) > t for s in sources):
        return True
    h = _src_hash(sources)
    old = _load_hashes().get(target)
    return h != old


def mark_fresh(target, sources):
    _store_hash(target, _src_hash(sources))


def _hashes_path():
    return os.path.join(PROJ, "obj", ".src_hashes.json")


def _load_hashes():
    try:
        with open(_hashes_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _store_hash(target, h):
    try:
        hashes = _load_hashes()
        hashes[target] = h
        with open(_hashes_path(), "w", encoding="utf-8") as f:
            json.dump(hashes, f)
    except OSError:
        pass


def _src_hash(sources):
    h = hashlib.sha1()
    for s in sorted(set(sources)):
        try:
            with open(s, "rb") as f:
                h.update(f.read())
        except OSError:
            h.update(("missing:" + s).encode())
    return h.hexdigest()


def find_start(map_path, default=0x0100):
    if not os.path.exists(map_path):
        return default
    with open(map_path, "r", encoding="latin1") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[1] in ("_start", "_main"):
                try:
                    val = int(parts[0], 16)
                    if val < 0x8000:
                        return val
                except ValueError:
                    pass
    return default


def code_length(map_path, default=0x8000):
    if not os.path.exists(map_path):
        return default
    with open(map_path, "r", encoding="latin1") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "l__CODE":
                try:
                    return int(parts[0], 16)
                except ValueError:
                    pass
    return default


def image_length(map_path, base, default=0x8000):
    """Span de la imatge a carregar: des de `base` fins al final de l'última
    àrea útil (CODE/DATA/INITIALIZED/INITIALIZER). El gap s'omple amb zeros
    (BSS) i el template INITIALIZER ve de l'ihx. Sense això, _DATA/_INITIALIZED
    queden fora del .bin (mai carregats) i el CRT manual llegeix brossa."""
    if not os.path.exists(map_path):
        return default
    syms = {}
    with open(map_path, "r", encoding="latin1") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[1] in (
                    "s__CODE", "l__CODE", "s__DATA", "l__DATA",
                    "s__INITIALIZED", "l__INITIALIZED",
                    "s__INITIALIZER", "l__INITIALIZER"):
                try:
                    syms[parts[1]] = int(parts[0], 16)
                except ValueError:
                    pass
    end = base
    for area in ("CODE", "DATA", "INITIALIZED", "INITIALIZER"):
        s = syms.get("s__" + area)
        ln = syms.get("l__" + area, 0)
        if s is not None:
            end = max(end, s + ln)
    return end - base if end > base else default


def crt_addrs_text(map_path):
    """Genera src/crt_addrs.h amb les adreces del CRT manual, llegides del
    mapa (mai hardcoded: deriven amb cada build)."""
    syms = {}
    if os.path.exists(map_path):
        with open(map_path, "r", encoding="latin1") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] in (
                        "s__DATA", "l__DATA", "s__INITIALIZED",
                        "s__INITIALIZER", "l__INITIALIZED", "_g_mus_hold"):
                    try:
                        syms[parts[1]] = int(parts[0], 16)
                    except ValueError:
                        pass
    data_start = syms.get("s__DATA", 0x36A0)
    data_len = syms.get("l__DATA", 0x18E)
    idata_dst = syms.get("s__INITIALIZED", 0x382E)
    idata_src = syms.get("s__INITIALIZER", 0x3850)
    idata_len = syms.get("l__INITIALIZED", 0x1E)
    mus_hold = syms.get("_g_mus_hold", 0x0000)
    return ("#ifndef CRT_ADDRS_H\n#define CRT_ADDRS_H\n"
            "// Generat per tools/build.py des de obj/bluesb.map. NO EDITAR.\n"
            "#define CRT_DATA_START 0x%04X\n#define CRT_DATA_LEN %d\n"
            "#define CRT_IDATA_DST 0x%04X\n#define CRT_IDATA_SRC 0x%04X\n"
            "#define CRT_IDATA_LEN %d\n"
            "// Adreca de _g_mus_hold (HOLD musica ISR): la neteja el GAME\n"
            "// post-memset(0x8000) (era VRAM: 0xBA10 = drone, vist 13/10/26).\n"
            "#define MUS_HOLD_ADDR 0x%04X\n#endif\n"
            % (data_start, data_len, idata_dst, idata_src, idata_len, mus_hold))


def map_area(map_path, area):
    """Retorna (start, length) d'una àrea del mapa (s__X/l__X)."""
    s = ln = None
    if os.path.exists(map_path):
        with open(map_path, "r", encoding="latin1") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    if parts[1] == "s__" + area:
                        try:
                            s = int(parts[0], 16)
                        except ValueError:
                            pass
                    elif parts[1] == "l__" + area:
                        try:
                            ln = int(parts[0], 16)
                        except ValueError:
                            pass
    return s, ln or 0


def emit_dat_bin(ihx_path, map_path, bin_path):
    """Extreu la plantilla _INITIALIZER de l'ihx -> DAT.BIN (30 B).
    El .bin resident va truncat (firmware el carrega de pistes baixes) i la
    plantilla no hi cap; el joc la carrega amb DAT.BIN via el carregador FDC."""
    src, ln = map_area(map_path, "INITIALIZER")
    if not src or not ln:
        print("[AVIS] sense _INITIALIZER al mapa; DAT.BIN buit")
        open(bin_path, "wb").write(b"")
        return
    mem = {}
    with open(ihx_path, "r", encoding="latin1") as f:
        for line in f:
            line = line.strip()
            if not line.startswith(":"):
                continue
            rec_len = int(line[1:3], 16)
            addr = int(line[3:7], 16)
            if int(line[7:9], 16) != 0:
                continue
            data = bytes.fromhex(line[9:9 + rec_len * 2])
            for i, b in enumerate(data):
                mem[addr + i] = b
    buf = bytes(mem.get(src + i, 0) for i in range(ln))
    with open(bin_path, "wb") as f:
        f.write(buf)
    print("DAT.BIN: %d bytes (plantilla 0x%04X)" % (ln, src))


def report_and_assert_memory_budget(map_path):
    if not os.path.exists(map_path):
        return
    syms = {}
    with open(map_path, "r", encoding="latin1") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                for k in ("s__CODE", "l__CODE", "s__DATA", "l__DATA", "s__INITIALIZER", "l__INITIALIZER"):
                    if parts[1] == k:
                        try:
                            syms[k] = int(parts[0], 16)
                        except ValueError:
                            pass
    s_code = syms.get("s__CODE", 0x0100)
    l_code = syms.get("l__CODE", 0)
    s_data = syms.get("s__DATA", 0x3300)
    l_data = syms.get("l__DATA", 0)

    code_end = s_code + l_code
    s_init = syms.get("s__INITIALIZER", s_data + l_data)
    l_init = syms.get("l__INITIALIZER", 0)
    data_end = max(s_data + l_data, s_init + l_init)
    code_margin = s_data - code_end
    stack_top = 0x3FFE
    stack_margin = stack_top - data_end

    print("\n" + "=" * 68)
    print(" PRESSUPOST DE MEMORIA (BLOC 0: 0x0000..0x3FFF)")
    print("=" * 68)
    print(" _CODE : 0x%04X..0x%04X (%5d B) | Marge fins _DATA : %4d B" %
          (s_code, code_end, l_code, code_margin))
    print(" _DATA : 0x%04X..0x%04X (%5d B) | Pila lliure (SP) : %4d B" %
          (s_data, data_end, l_data, stack_margin))
    print("=" * 68)

    if code_margin < 0:
        print("\n[FATAL] _CODE ha envait _DATA per %d bytes! (code_end=0x%04X > data_start=0x%04X)" %
              (-code_margin, code_end, s_data))
        sys.exit(1)
    if data_end > 0x3D00:
        print("\n[FATAL] _DATA ha trepitjat el canari de pila (data_end=0x%04X > 0x3D00)! Mou CANARY_ADDR." %
              data_end)
        sys.exit(1)
    if stack_margin < 256:
        print("\n[FATAL] Marge de pila insuficient (%d B < 256 B)! Risc immediat de crash." %
              stack_margin)
        sys.exit(1)
    if code_margin < 32:
        print("[AVIS] _CODE esta a punt de col-lidir amb _DATA! (nomes queden %d B)" % code_margin)
    if stack_margin < 1024:
        print("[AVIS] Marge de pila ajustat (%d B). Recomanat alliberar _DATA a bancs." % stack_margin)
    print()


def map_symbols(map_path):
    """Llegeix símbols globals {nom: addr} d'un .map d'sdasz80."""
    syms = {}
    with open(map_path, "r", encoding="latin1") as f:
        for line in f:
            m = re.match(r"\s*([0-9A-Fa-f]{8})\s+(_[A-Za-z]\w*)(\s+\S+)?\s*$", line)
            if m:
                syms[m.group(2)] = int(m.group(1), 16)
    return syms


def build_bank_equ(resident_map):
    """Genera obj/bank_equ.s amb .equ de tots els globals residents
    (perquè el link separat del banc resolgui les seves refs externes)."""
    obj = os.path.join(PROJ, "obj")
    syms = map_symbols(resident_map)
    lines = [".module bank_equ"]
    bank_local = ("moving_bank_", "_bc_update", "_bc_restore", "_bc_draw",
                  "_bc_push", "_bc_find", "_bc_init", "_bc_conveyor",
                  "_en2_", "_en_", "_s_hud_strips", "_s_enemies", "_s_bg_")
    for name in sorted(syms):
        if name.startswith(("s__", "l__")):
            continue
        if name.startswith(bank_local):
            continue
        lines.append(".globl %s" % name)
        lines.append("%s = 0x%04X" % (name, syms[name]))
    lines.append(".area _CODE")
    text = "\n".join(lines) + "\n"
    path = os.path.join(obj, "bank_equ.s")
    old = open(path).read() if os.path.exists(path) else None
    if old != text:
        open(path, "w").write(text)
    return path


def build_bank(force, level_idx=None):
    """Compila+enllaça el Banc 5 (moving_bank) a 0x6E00. Retorna BANK5.BIN."""
    obj = os.path.join(PROJ, "obj")
    resident_map = os.path.join(obj, "bluesb.map")
    build_bank_equ(resident_map)
    bank_rels = []
    for rel_src in BANK_ASM_SOURCES:
        src = os.path.join(PROJ, rel_src)
        rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
        if force or is_stale(rel, [src]):
            run([SDASZ80, "-plosgff", rel, src])
            mark_fresh(rel, [src])
        bank_rels.append(rel)
    if level_idx is None:
        for rel_src in BANK_C_SOURCES:
            src = os.path.join(PROJ, rel_src)
            rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
            headers = [os.path.join(PROJ, name) for name in BANK_C_HEADERS[rel_src]]
            if force or is_stale(rel, [src] + headers):
                run([SDCC] + INCLUDES + CFLAGS + ["-c", src, "-o", rel])
                mark_fresh(rel, [src] + headers)
            bank_rels.append(rel)
    else:
        # Compilacio per nivell: header i codi a obj/lvl<n> perque SDCC
        # trobi el level_pkg.h del nivell (include local).
        vdir = os.path.join(obj, "lvl%d" % level_idx)
        os.makedirs(vdir, exist_ok=True)
        src_c = os.path.join(vdir, "moving_bank.c")
        hdr = os.path.join(vdir, "level_pkg.h")
        def _sync(a, b):
            data = open(a, "rb").read()
            if not os.path.exists(b) or open(b, "rb").read() != data:
                open(b, "wb").write(data)
        _sync(os.path.join(PROJ, "src", "moving_bank.c"), src_c)
        if level_idx == 0:
            hdr_src = os.path.join(PROJ, "src", "level_pkg.h")
        else:
            hdr_src = os.path.join(vdir, "level_pkg.h")
            if not os.path.exists(hdr_src):
                print("\n[FATAL] Falta %s; genera'l amb pack_level.py %d --outdir %s" %
                      (hdr_src, level_idx, vdir))
                sys.exit(1)
        _sync(hdr_src, hdr)
        rel = os.path.join(vdir, "moving_bank.rel")
        headers = [hdr] + [os.path.join(PROJ, name) for name in BANK_C_HEADERS["src/moving_bank.c"]]
        if force or is_stale(rel, [src_c] + headers):
            run([SDCC, "-I" + vdir] + INCLUDES + CFLAGS + ["-c", src_c, "-o", rel])
            mark_fresh(rel, [src_c] + headers)
        bank_rels.append(rel)
    equ_s = os.path.join(obj, "bank_equ.s")
    equ_rel = os.path.join(obj, "bank_equ.rel")
    if force or is_stale(equ_rel, [equ_s]):
        run([SDASZ80, "-plosgff", equ_rel, equ_s])
        mark_fresh(equ_rel, [equ_s])
    bank_rels.append(equ_rel)
    suffix = "" if level_idx is None else "_%d" % level_idx
    ihx = os.path.join(obj, "bank5%s.ihx" % suffix)
    map_path = os.path.join(obj, "bank5%s.map" % suffix)

    def link_b5(data_loc):
        run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % BANK5_BASE,
             "--data-loc", "0x%04X" % data_loc] + bank_rels + ["-o", ihx])
        return map_area(map_path, "CODE")

    # 1a passada amb _DATA a dalt de tot; 2a passada enganxant _DATA just
    # despres del codi: elimina el forat de ~392 B dins la imatge C5.
    b5_code_s, b5_code_l = link_b5(0x7F80)
    if b5_code_s is not None:
        dloc = (b5_code_s + b5_code_l + 7) & 0xFFF8
        if dloc < 0x8000:
            b5_code_s, b5_code_l = link_b5(dloc)
    b5_data_s, b5_data_l = map_area(map_path, "DATA")
    if b5_code_s is not None and b5_data_s is not None and (b5_code_s + b5_code_l) > b5_data_s:
        print("\n[FATAL] Banc 5 _CODE (0x%04X..0x%04X) envaeix _DATA (0x%04X)!" %
              (b5_code_s, b5_code_s + b5_code_l, b5_data_s))
        sys.exit(1)
    # Asserts d'integritat del banc (FATAL si fallen: adreces o mides malament
    # penjarien el Z80 en el primer call_banked).
    syms = map_symbols(map_path)
    slot_names = {"_bc_update": 0, "_bc_restore": 1, "_bc_draw": 2, "_bc_push": 3,
                  "_bc_find": 4, "_bc_init": 5, "_bc_conveyor": 6}
    for name, slot in slot_names.items():
        want = BANK5_BASE + slot * 3
        got = syms.get(name, -1)
        if got != want:
            print("\n[FATAL] Slot %s: esperat 0x%04X, mapa diu %s. Revisa bank5_table.s!" %
                  (name, want, ("0x%04X" % got) if got >= 0 else "absent"))
            sys.exit(1)
    bin_path = os.path.join(obj, "BANK5%s.BIN" % suffix)
    convert_ihx(ihx, bin_path, start_addr=BANK5_BASE,
                max_length=image_length(map_path, BANK5_BASE))
    size = os.path.getsize(bin_path)
    if size > BANK5_MAXLEN:
        print("\n[FATAL] Banc 5: %d bytes > límit 0x%04X! Cal aprimar moving_bank.c." %
              (size, BANK5_MAXLEN))
        sys.exit(1)
    print("BANC5%s: 0x%04X (%d bytes, code=%d B, marge_code=%d B)" %
          (suffix, BANK5_BASE, size, b5_code_l,
           (b5_data_s or 0x7F80) - (BANK5_BASE + b5_code_l)))
    if level_idx == 0:
        shutil.copyfile(bin_path, os.path.join(obj, "BANK5.BIN"))
    return bin_path


def build_levelcode(force, level_idx=None):
    """Compila el codi del NIVELL (ascensors) per al Banc 1 (C1).

    El codi del nivell no ha de viure al Bloc 0 resident (que ha de ser el
    motor generic). Aquest modul s'enlla?a dins el Banc 1, al mateix paquet
    que la musica, el HUD i les habitacions, i on hi viuen tambe els frames
    de l'ascensor i els seus buffers de fons.
    Retorna obj/LEVELCODE.BIN (el codi + les dades)."""
    obj = os.path.join(PROJ, "obj")
    resident_map = os.path.join(obj, "bluesb.map")
    equ_s = build_bank_equ(resident_map)
    equ_rel = os.path.join(obj, "bank_equ.rel")
    if force or is_stale(equ_rel, [equ_s]):
        run([SDASZ80, "-plosgff", equ_rel, equ_s])
        mark_fresh(equ_rel, [equ_s])
    rels = []
    asm_src = os.path.join(PROJ, "engine", "bank1_table.s")
    asm_rel = os.path.join(obj, "bank1_table.rel")
    if force or is_stale(asm_rel, [asm_src]):
        run([SDASZ80, "-plosgff", asm_rel, asm_src])
        mark_fresh(asm_rel, [asm_src])
    rels.append(asm_rel)
    c_src = os.path.join(PROJ, "src", "level_code.c")
    c_rel = os.path.join(obj, "level_code.rel")
    headers = [os.path.join(PROJ, n) for n in
               ("engine/cpctelera.h", "engine/bank.h", "src/moving.h", "src/sprite.h",
                "src/level_params.h")]
    if force or is_stale(c_rel, [c_src] + headers):
        run([SDCC] + INCLUDES + CFLAGS + ["-c", c_src, "-o", c_rel])
        mark_fresh(c_rel, [c_src] + headers)
    rels.append(c_rel)
    rels.append(equ_rel)
    # Base del codi: just despres de la imatge C1 (MUSMAIN.BIN), alineada a 8.
    # Ja no es una constant: creix si la imatge creix (p. ex. parametres v2).
    mus_name = "MUSMAIN.BIN" if level_idx in (None, 0) else "MUSMAIN_%d.BIN" % level_idx
    base = (0x5000 + os.path.getsize(os.path.join(obj, mus_name)) + 7) & 0xFFF8
    suffix = "" if level_idx is None else "_%d" % level_idx
    ihx = os.path.join(obj, "levelcode%s.ihx" % suffix)
    run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % base,
         "--data-loc", "0x%04X" % LC1_DATA_BASE] + rels + ["-o", ihx])
    map_path = os.path.join(obj, "levelcode%s.map" % suffix)
    code_s, code_l = map_area(map_path, "CODE")
    data_s, data_l = map_area(map_path, "DATA")
    # Limit del codi: si el nivell te frames de mecanismes (ascensors/premses)
    # no pot arribar a LC1_FRAMES_BASE; si no en te (L3), pot arribar fins als
    # parametres de C1:0x7680.
    lv_cfg = next((x for x in LEVELS if x["id"] == (0 if level_idx is None else level_idx)), None)
    code_limit = LC1_FRAMES_BASE if (lv_cfg is None or lv_cfg["has_elev"]) else LC1_PARAMS_BASE
    if code_s is not None and (code_s + code_l) > code_limit:
        print("\n[FATAL] El codi del nivell (Banc 1) arriba al limit 0x%04X!" % code_limit)
        sys.exit(1)
    if data_s is not None and (data_s + data_l) > 0x7780:
        print("\n[FATAL] Les dades del codi del nivell (Banc 1) no hi caben!")
        sys.exit(1)
    # El codi i les dades van en dos fitxers perqu? al paquet el codi va
    # abans dels frames i dels buffers de fons (que son dades, no codi).
    code_path = os.path.join(obj, "LEVELCODE%s.BIN" % suffix)
    convert_ihx(ihx, code_path, start_addr=base, max_length=code_l)
    data_path = os.path.join(obj, "LEVELDATA%s.BIN" % suffix)
    convert_ihx(ihx, data_path, start_addr=LC1_DATA_BASE, max_length=data_l)
    print("BANC1%s: codi del nivell a 0x%04X (%d B de codi, %d B de dades)"
          % (suffix, base, code_l, data_l))
    if level_idx == 0:
        shutil.copyfile(code_path, os.path.join(obj, "LEVELCODE.BIN"))
        shutil.copyfile(data_path, os.path.join(obj, "LEVELDATA.BIN"))
    return code_path


def build_enemybank(force, level_idx=None):
    """Imatge C6 (walkers L1): frames ENEMI1.BIN a 0x4000 + codi linkat a
    ENEMY_BASE (taula engine/enemy_table.s primera: slots fixos 0x5200+3k)
    + dades a ENEMY_DATA. Retorna obj/ENEMI.BIN (concatenat, llest pel DSK).
    Requereix bank_equ.s fresc (el genera build_bank: cridar despres)."""
    obj = os.path.join(PROJ, "obj")
    en_rels = []
    for rel_src in ENEMY_ASM_SOURCES:
        src = os.path.join(PROJ, rel_src)
        rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
        if force or is_stale(rel, [src]):
            run([SDASZ80, "-plosgff", rel, src])
            mark_fresh(rel, [src])
        en_rels.append(rel)
    if level_idx is None:
        for rel_src in ENEMY_C_SOURCES:
            src = os.path.join(PROJ, rel_src)
            rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
            headers = [os.path.join(PROJ, name) for name in ENEMY_C_HEADERS[rel_src]]
            if force or is_stale(rel, [src] + headers):
                run([SDCC] + INCLUDES + CFLAGS + ["-c", src, "-o", rel])
                mark_fresh(rel, [src] + headers)
            en_rels.append(rel)
    else:
        vdir = os.path.join(obj, "lvl%d" % level_idx)
        os.makedirs(vdir, exist_ok=True)
        src_c = os.path.join(vdir, "enemy.c")
        hdr = os.path.join(vdir, "level_pkg.h")
        def _sync(a, b):
            data = open(a, "rb").read()
            if not os.path.exists(b) or open(b, "rb").read() != data:
                open(b, "wb").write(data)
        _sync(os.path.join(PROJ, "src", "enemy.c"), src_c)
        if level_idx == 0:
            hdr_src = os.path.join(PROJ, "src", "level_pkg.h")
        else:
            hdr_src = os.path.join(vdir, "level_pkg.h")
            if not os.path.exists(hdr_src):
                print("\n[FATAL] Falta %s; genera'l amb pack_level.py %d --outdir %s" %
                      (hdr_src, level_idx, vdir))
                sys.exit(1)
        _sync(hdr_src, hdr)
        spawn_h = os.path.join(vdir, "enemy_spawn.h")
        spawn_src = os.path.join(PROJ, "tools", "blues_dos", "bb", "staticres.c")
        spawn_gen = os.path.join(HERE, "gen_enemy_spawn.py")
        if os.path.basename(vdir) != "lvl0":
            if force or is_stale(spawn_h, [spawn_src, spawn_gen]):
                run([sys.executable, spawn_gen,
                     "--level", str(level_idx), "--out", spawn_h])
                mark_fresh(spawn_h, [spawn_src, spawn_gen])
        rel = os.path.join(vdir, "enemy.rel")
        headers = [hdr] + [os.path.join(PROJ, name) for name in ENEMY_C_HEADERS["src/enemy.c"]]
        if os.path.basename(vdir) != "lvl0":
            headers.append(spawn_h)
        if force or is_stale(rel, [src_c] + headers):
            run([SDCC, "-I" + vdir] + INCLUDES + CFLAGS + ["-c", src_c, "-o", rel])
            mark_fresh(rel, [src_c] + headers)
        en_rels.append(rel)
    en_rels.append(os.path.join(obj, "bank_equ.rel"))
    suffix = "" if level_idx is None else "_%d" % level_idx
    ihx = os.path.join(obj, "enemybank%s.ihx" % suffix)
    run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % ENEMY_BASE,
         "--data-loc", "0x%04X" % ENEMY_DATA] + en_rels + ["-o", ihx])
    map_path = os.path.join(obj, "enemybank%s.map" % suffix)
    en_code_s, en_code_l = map_area(map_path, "CODE")
    en_data_s, en_data_l = map_area(map_path, "DATA")
    # Layout C6 nou: frames comprimits 0x4000, cache 0x5000, estat 0x5800,
    # dades 0x5820..<0x5C00, codi 0x5C00..<0x7900 (LUT).
    if en_code_s is not None and (en_code_s + en_code_l) > 0x7900:
        print("\n[FATAL] Banc C6 _CODE (0x%04X..0x%04X) envaeix la LUT (0x7900)!" %
              (en_code_s, en_code_s + en_code_l))
        sys.exit(1)
    if en_data_s is not None and (en_data_s + en_data_l) > ENEMY_BASE:
        print("\n[FATAL] Banc C6 _DATA (0x%04X..0x%04X) envaeix el codi (0x%04X)!" %
              (en_data_s, en_data_s + en_data_l, ENEMY_BASE))
        sys.exit(1)
    syms = map_symbols(map_path)
    slot_names = {"_en_update": 0, "_en_restore": 1, "_en_draw": 2, "_en_init": 3,
                  "_en_check_player_hit": 4, "_en_check_crate_hit": 5}
    for name, slot in slot_names.items():
        want = ENEMY_BASE + slot * 3
        got = syms.get(name, -1)
        if got != want:
            print("\n[FATAL] Slot %s: esperat 0x%04X, mapa diu %s. Revisa enemy_table.s!" %
                  (name, want, ("0x%04X" % got) if got >= 0 else "absent"))
            sys.exit(1)
    code_path = os.path.join(obj, "ENEMYCODE%s.BIN" % suffix)
    convert_ihx(ihx, code_path, start_addr=ENEMY_BASE,
                max_length=en_code_l)
    frames_path = ENEMY_FRAMES if level_idx in (None, 0) else \
        os.path.join(PROJ, "assets", "bbdata", "ENEMI%d.BIN" % (level_idx + 1))
    if level_idx == 1:
        gen2 = os.path.join(PROJ, "tools", "gen_enemy2_frames.py")
        sqv2 = os.path.join(PROJ, "assets", "bbdata", "ENEMI2.SQV")
        if force or is_stale(frames_path, [gen2, sqv2]):
            run([sys.executable, gen2])
            mark_fresh(frames_path, [gen2, sqv2])
    if level_idx == 2:
        gen3 = os.path.join(PROJ, "tools", "gen_enemy3_frames.py")
        sqv3 = os.path.join(PROJ, "assets", "bbdata", "ENEMI3.SQV")
        if force or is_stale(frames_path, [gen3, sqv3]):
            run([sys.executable, gen3])
            mark_fresh(frames_path, [gen3, sqv3])
    frames = open(frames_path, "rb").read()
    code = open(code_path, "rb").read()
    assert len(frames) % 512 == 0 and len(frames) // 512 >= 14, len(frames)

    # --- Frames comprimits PER CELA (ZX0) + cache de 4 slots (veure enemy.c) ---
    # Layout dins C6 (imatge que es descomprimeix a 0x4000):
    #   0x4000..0x403F  taula de 16 punters absoluts (2 B/cela; 14 usades)
    #   0x4040..        blocs ZX0 per cela (1 flux independent per cela)
    #   0x5000..0x57FF  cache de 4 slots de 512 B (scratch: no cal carregar-hi res)
    #   0x5800..0x581F  estat de la cache (cela per slot + next + comptador)
    #   0x5C00..        codi (ENEMYCODE.BIN)
    from zx0pkg.zx0 import zx0_compress
    EN_TABLE = 0x4000
    EN_BLOCKS = 0x4040
    EN_CACHE = 0x5000
    EN_CACHE_SLOTS = 4
    ncell = len(frames) // 512
    table = bytearray()
    blocks = bytearray()
    for i in range(ncell):
        out, _ = zx0_compress(bytes(frames[i * 512:(i + 1) * 512]),
                              classic=True, quick=True)
        table += struct.pack("<H", EN_BLOCKS + len(blocks))
        blocks += bytes(out)
    while len(table) < 32:
        table += b"\x00\x00"
    blocks_end = EN_BLOCKS + len(blocks)
    if blocks_end > EN_CACHE:
        print("\n[FATAL] Blocs ZX0 d'enemics (fins 0x%04X) envaeixen la cache 0x%04X!",
              blocks_end, EN_CACHE)
        sys.exit(1)
    if EN_CACHE + EN_CACHE_SLOTS * 512 > 0x4000 + 0x1C00:
        print("\n[FATAL] Cache d'enemics passa del final de frames (0x5C00)!")
        sys.exit(1)
    raw_len = 0x1C00                       # 0x4000..0x5BFF
    im = bytearray(raw_len)
    im[0:len(table)] = table
    im[EN_BLOCKS - 0x4000:EN_BLOCKS - 0x4000 + len(blocks)] = blocks
    # Taula de restauracio de tiles (pack_level.py): [n u16][n x (col,row,tile)]
    # 1:1 DOS: cada nivell restaura els SEUS consumibles en morir (game.c:344
    # rellegeix el paquet del nivell). Abans sempre s'incrustava RESTORE0 (L1)
    # i morir a L2+ corrompia el mapa amb tiles d'L1. Ara es per nivell.
    rt_lvl = 0 if level_idx is None else level_idx
    rt_path = os.path.join(PROJ, "assets", "bbdata", "RESTORE%d.BIN" % rt_lvl)
    rt = open(rt_path, "rb").read()
    EN_RESTORE = 0x4B00
    if EN_BLOCKS + len(blocks) > EN_RESTORE:
        print("\n[FATAL] Blocs ZX0 d'enemics (fins 0x%04X) xoquen amb la taula de restauracio (0x%04X)!"
              % (EN_BLOCKS + len(blocks), EN_RESTORE))
        sys.exit(1)
    if EN_RESTORE + len(rt) > EN_CACHE:
        print("\n[FATAL] Taula de restauracio (%d B a 0x%04X) envaeix la cache (0x%04X)!"
              % (len(rt), EN_RESTORE, EN_CACHE))
        sys.exit(1)
    im[EN_RESTORE - 0x4000:EN_RESTORE - 0x4000 + len(rt)] = rt
    im = bytes(im) + code
    total = len(im)
    print("ENEMY cells: %d B ZX0 (de %d B en cru) en %d blocs; cache %d x 512 B a 0x%04X"
          % (len(blocks), len(frames), ncell, EN_CACHE_SLOTS, EN_CACHE))
    print("ENEMY restore: %d B a 0x%04X (%d posicions)"
          % (len(rt), EN_RESTORE, rt[0] | (rt[1] << 8)))
    out_path = os.path.join(obj, "ENEMI%s.BIN" % suffix)
    if not os.path.exists(out_path) or open(out_path, "rb").read() != im:
        open(out_path, "wb").write(im)
    print("ENEMYB%s: blocs %d B + codi %d B = %d B (0x4000..0x%04X)"
          % (suffix, len(blocks), len(code), total, 0x4000 + total))
    # EQU pel GAME (render.c llegeix s_hud_strips a 0x6000 paginant Banc C1 / C0).
    ext_s = os.path.join(obj, "enemy_ext.s")
    ext_txt = ("    .module enemy_ext\n"
               "    .globl _s_hud_strips\n_s_hud_strips = 0x6000\n")
    if not os.path.exists(ext_s) or open(ext_s).read() != ext_txt:
        open(ext_s, "w").write(ext_txt)
    if level_idx == 0:
        shutil.copyfile(out_path, os.path.join(obj, "ENEMI.BIN"))
    return out_path


# --- Banc FDC (F1): motor de disc resident tota la sessio ---
# fdc.c + assets_fdc.s, TAL QUAL (mateixes fonts que l'starter), imatge
# enllacada a FDC_BANK_BASE (execucio central NO paginable!). La imatge viu
# al Banc 6 (dest C6:0x7000, dins la finestra: correcte alla). El resident
# NO executa el banc (el motor commuta la finestra on s'executaria a 0x7000):
# copia la imatge a scratch central 0x8000 (VRAM pag.2, invisible, fora de
# 0x4000-0x7FFF) i l'executa alla, amb el comportament bit-identic al
# resident d'abans. _fdc_load_file ha de caure a FDC_BANK_BASE (fdc.rel
# enllacat primer); l'stub hi crida directe.
FDC_BANK = 0xC6
FDC_BANK_BASE = 0x8000
FDC_BANK_DATA = 0x8300
FDC_BANK_WINLEN = 0x1000  # scratch 0x8000..0x8FFF (VRAM pag.2; el GAME
                          # l'esborra amb memset post-carregues)

def build_fdc_hold(force):
    """Genera+assembla obj/fdc_hold.s (MUS_HOLD + GBANK_ADDR del GAME).
    El motor (assets_fdc.s, 3 links: starter/scratch) hi escriu l'HOLD i
    mante _g_bank (invariant bank_set: _g_bank PRIMER, despres OUT) perque
    la ISR hi pugui niuar segura durant lectures (musica continua).
    Patro front_ext (mai hardcoded). FATAL si falten simbols al mapa."""
    obj = os.path.join(PROJ, "obj")
    syms = map_symbols(os.path.join(obj, PROGNAME + ".map"))
    addr = syms.get("_g_mus_hold", -1)
    gbank = syms.get("_g_bank", -1)
    if addr < 0 or gbank < 0:
        print("\n[FATAL] HOLD: _g_mus_hold/_g_bank no son al mapa resident. Enllaca GAME primer?")
        sys.exit(1)
    hold_s = os.path.join(obj, "fdc_hold.s")
    hold_txt = ("    .module fdc_hold\n"
                "    .globl MUS_HOLD\n"
                "    .globl GBANK_ADDR\n"
                "MUS_HOLD = 0x%04X\n"
                "GBANK_ADDR = 0x%04X\n" % (addr, gbank))
    if not os.path.exists(hold_s) or open(hold_s).read() != hold_txt:
        open(hold_s, "w").write(hold_txt)
    hold_rel = os.path.join(obj, "fdc_hold.rel")
    if force or is_stale(hold_rel, [hold_s]):
        run([SDASZ80, "-plosgff", hold_rel, hold_s])
        mark_fresh(hold_rel, [hold_s])
    print("FDCHOLD: MUS_HOLD=0x%04X GBANK_ADDR=0x%04X" % (addr, gbank))
    return hold_rel


def build_fdcbank(force):
    """Enllaça FDC.BIN (motor FDC sencer) a 0x8000. Retorna FDC.BIN."""
    obj = os.path.join(PROJ, "obj")
    hold_rel = build_fdc_hold(force)
    bank_rels = [os.path.join(obj, "fdc.rel"), os.path.join(obj, "assets_fdc.rel"),
                 hold_rel]
    ihx = os.path.join(obj, "fdcbank.ihx")
    run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % FDC_BANK_BASE,
         "--data-loc", "0x%04X" % FDC_BANK_DATA] + bank_rels + ["-o", ihx])
    map_path = os.path.join(obj, "fdcbank.map")
    syms = map_symbols(map_path)
    entry = syms.get("_fdc_load_file", -1)
    if entry != FDC_BANK_BASE:
        print("\n[FATAL] FDC bank: _fdc_load_file=0x%04X (esperat 0x%04X). L'stub hi crida directe!" %
              (entry, FDC_BANK_BASE))
        sys.exit(1)
    code_s, code_l = map_area(map_path, "CODE")
    data_s, data_l = map_area(map_path, "DATA")
    if code_s is not None and data_s is not None and (code_s + code_l) > data_s:
        print("\n[FATAL] FDC bank _CODE envaeix _DATA! Mou --data-loc amunt.")
        sys.exit(1)
    bin_path = os.path.join(obj, "FDC.BIN")
    convert_ihx(ihx, bin_path, start_addr=FDC_BANK_BASE,
                max_length=image_length(map_path, FDC_BANK_BASE))
    size = os.path.getsize(bin_path)
    if size > FDC_BANK_WINLEN:
        print("\n[FATAL] FDC bank: %d bytes > scratch 0x%04X! Aprimar motor." %
              (size, FDC_BANK_WINLEN))
        sys.exit(1)
    # L'stub (moving.c) verifica CRC_FDC sobre g_len_fdc bytes: si la mida
    # de FDC.BIN canvia sense actualitzar main.c -> white-hang silencios.
    # Falla AQUI (sorollos) en comptes d'engegar malament.
    import re as _re
    m = _re.search(r"g_len_fdc\s*=\s*(\d+)",
                   open(os.path.join(PROJ, "src", "main.c")).read())
    if not m or int(m.group(1)) != size:
        print("\n[FATAL] FDC.BIN fa %d B pero g_len_fdc=%s a src/main.c. "
              "Actualitza'l (white-hang segur)!" % (size, m.group(1) if m else "?"))
        sys.exit(1)
    print("FDCBANK: 0x%04X (%d bytes, entry=0x%04X)" % (FDC_BANK_BASE, size, entry))
    return bin_path


def build_front(force):
    """Enllaca FRONT.BIN (front.c banked C4:0x4000 + slot + EQU centrals).
    Necessita el mapa resident (bluesb.map) per resoldre stub/depack/args.
    Retorna FRONT.BIN."""
    obj = os.path.join(PROJ, "obj")
    # EQU externs centrals des del mapa resident (falla sorollos si falten).
    resident_map = os.path.join(obj, PROGNAME + ".map")
    syms = map_symbols(resident_map)
    need = {"_fdc_load_file": None, "_fdc_motor_off": None,
            "_mus_play": None, "_mus_init": None, "_mus_stop": None,
            "_g_ticks": None, "_g_mus_hold": None,
            "_g_player_choice": None, "_g_map_level": None}
    for k in need:
        if k not in syms:
            print("\n[FATAL] FRONT: %s no es al mapa resident. Enllaca GAME primer?" % k)
            sys.exit(1)
        need[k] = syms[k]
    ext_s = os.path.join(obj, "front_ext.s")
    ext_txt = ("    .module front_ext\n" +
               "".join("    .globl %s\n%s = 0x%04X\n" % (k, k, v) for k, v in need.items()))
    # Layout pantalles (tot carregat al SPLASH en silenci, pre-musica; el
    # depack es des de RAM = select/mapa sense FDC, musica intacta):
    # - splash.ZX0 -> fixa 0x8400 (lliure al prejoc);
    # - select.ZX0 -> banc C4 0x4A00 (propi banc del FRONT: _DATA a 0x4900;
    #   FATAL post-link si _DATA hi arriba);
    # - map.ZX0 -> fixa 0x8400+len(splash) (darrere l'splash).
    # Fixes que creixen amb els assets: FATAL si select+bg passa 0x8000 o
    # el mapa passa 0xC000 (VRAM). Mides reals dels .ZX0.
    splash_zx = 0x8400
    sel_zx = 0x4A00
    sizes = {}
    for t, _ in FRONT_SCREENS:
        p = os.path.join(obj, t + ".ZX0")
        sizes[t] = os.path.getsize(p) if os.path.exists(p) else 0
    map_zx = splash_zx + sizes["FSPLASH"]
    bg0 = sel_zx + sizes["FSELECT"]
    bg1 = bg0 + 240
    if bg1 + 240 > 0x8000:
        print("\n[FATAL] FRONT: select+bg passa 0x8000 (sel=0x%04X len=%d). Aprimar." % (sel_zx, sizes["FSELECT"]))
        sys.exit(1)
    if map_zx + sizes["FMAP"] > 0xC000:
        print("\n[FATAL] FRONT: mapa passa 0xC000 (map=0x%04X len=%d). Aprimar." % (map_zx, sizes["FMAP"]))
        sys.exit(1)
    dance_base = sel_zx + (sizes["FSELECT"] - DANCE_LEN)
    stick_base = map_zx + (sizes["FMAP"] - STICK_LEN)
    ext_txt += ("    .globl _fsplash_zx\n_fsplash_zx = 0x%04X\n"
                "    .globl _fsel_zx\n_fsel_zx = 0x%04X\n"
                "    .globl _fmap_zx\n_fmap_zx = 0x%04X\n"
                "    .globl _f_bg0\n_f_bg0 = 0x%04X\n"
                "    .globl _f_bg1\n_f_bg1 = 0x%04X\n"
                % (splash_zx, sel_zx, map_zx, bg0, bg1))
    ext_txt += "    .globl _fselect_dance_base\n_fselect_dance_base = 0x%04X\n" % dance_base
    ext_txt += "    .globl _fmap_stick_base\n_fmap_stick_base = 0x%04X\n" % stick_base
    if not os.path.exists(ext_s) or open(ext_s).read() != ext_txt:
        open(ext_s, "w").write(ext_txt)
    # Compila front.c (cache mtime+hash com la resta).
    src = os.path.join(PROJ, FRONT_C_SOURCE)
    rel = os.path.join(obj, "front.rel")
    headers = [os.path.join(PROJ, name) for name in FRONT_C_HEADERS]
    if force or is_stale(rel, [src] + headers):
        run([SDCC] + INCLUDES + CFLAGS + ["-c", src, "-o", rel])
        mark_fresh(rel, [src] + headers)
    tab_s = os.path.join(PROJ, "engine", "front_table.s")
    tab_rel = os.path.join(obj, "front_table.rel")
    if force or is_stale(tab_rel, [tab_s]):
        run([SDASZ80, "-plosgff", tab_rel, tab_s])
        mark_fresh(tab_rel, [tab_s])
    # Decoder ZX0 al FRONT (era resident; ~94 B de Bloc 0). El GAME ja no
    # l'enllaca (GAME_LINK_SKIP); el FRONT el crida en banc C4 (nomes toca
    # scratch 0x8400 + VRAM + AF', com en central: mateixa seguretat).
    dec_s = os.path.join(PROJ, "engine", "zx0_decompress.s")
    dec_rel = os.path.join(obj, "zx0_decompress.rel")
    if force or is_stale(dec_rel, [dec_s]):
        run([SDASZ80, "-plosgff", dec_rel, dec_s])
        mark_fresh(dec_rel, [dec_s])
    ext_rel = os.path.join(obj, "front_ext.rel")
    if force or is_stale(ext_rel, [ext_s]):
        run([SDASZ80, "-plosgff", ext_rel, ext_s])
        mark_fresh(ext_rel, [ext_s])
    ihx = os.path.join(obj, "front.ihx")
    run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % FRONT_BASE,
         "--data-loc", "0x%04X" % FRONT_DATA,
         tab_rel, rel, dec_rel, ext_rel, "-o", ihx])
    map_path = os.path.join(obj, "front.map")
    syms_f = map_symbols(map_path)
    if syms_f.get("_front_entry", -1) != FRONT_BASE:
        print("\n[FATAL] FRONT: entry=0x%04X (esperat 0x%04X). Ordre _CODE trencat!" %
              (syms_f.get("_front_entry", -1), FRONT_BASE))
        sys.exit(1)
    if syms_f.get("_front_map_entry", -1) != FRONT_BASE + 3:
        print("\n[FATAL] FRONT: map entry=0x%04X (esperat 0x%04X)." %
              (syms_f.get("_front_map_entry", -1), FRONT_BASE + 3))
        sys.exit(1)
    f_code_s, f_code_l = map_area(map_path, "CODE")
    f_data_s, f_data_l = map_area(map_path, "DATA")
    if (f_code_s is not None and f_data_s is not None and
            (f_code_s + f_code_l) > f_data_s):
        print("\n[FATAL] FRONT _CODE envaeix _DATA! Mou --data-loc amunt.")
        sys.exit(1)
    if (f_data_s is not None and (f_data_s + f_data_l) > sel_zx):
        print("\n[FATAL] FRONT _DATA (fi 0x%04X) envaeix select.ZX0 (0x%04X)! Puja sel_zx." %
              (f_data_s + f_data_l, sel_zx))
        sys.exit(1)
    bin_path = os.path.join(obj, "FRONT.BIN")
    convert_ihx(ihx, bin_path, start_addr=FRONT_BASE,
                max_length=image_length(map_path, FRONT_BASE))
    size = os.path.getsize(bin_path)
    if size > FRONT_MAXLEN:
        print("\n[FATAL] FRONT: %d bytes > 0x%04X! Aprimar (o pujar data-loc)." %
              (size, FRONT_MAXLEN))
        sys.exit(1)
    print("FRONTBANK: 0x%04X (%d bytes, entry=0x%04X)" % (FRONT_BASE, size, FRONT_BASE))
    return bin_path


def akg_convert(src_path, mod, force):
    """Converteix .akg/RASM a .s sdas (cache per hash) via tools/akg_rasm2sdas.
    Retorna el .s generat a obj/."""
    obj = os.path.join(PROJ, "obj")
    dst = os.path.join(obj, mod + ".s")
    sys.path.insert(0, os.path.join(PROJ, "tools"))
    import akg_rasm2sdas
    text = open(os.path.join(PROJ, src_path), "rb").read().decode("latin1")
    out, asserts, decisions = akg_rasm2sdas.convert(text, module=mod)
    old = None
    try:
        old = open(dst).read()
    except OSError:
        pass
    if old != out or force:
        open(dst, "w").write(out)
    return dst


def link_bin(rel_path, map_name, base, data_loc, bin_path, extra_labels=()):
    """Enllaca un .rel a base + el converteix a BIN (tallat a fi de CODE:
    el _DATA buit no s'hi inclou). Retorna (size, labels)."""
    obj = os.path.join(PROJ, "obj")
    ihx = os.path.join(obj, map_name + ".ihx")
    args = [SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % base]
    if data_loc is not None:
        args += ["--data-loc", "0x%04X" % data_loc]
    run(args + [rel_path, "-o", ihx])
    map_path = os.path.join(obj, map_name + ".map")
    code_s, code_l = map_area(map_path, "CODE")
    labels = {}
    if extra_labels:
        lst_path = os.path.splitext(rel_path)[0] + ".lst"
        want = set(extra_labels)
        with open(lst_path, "r", encoding="latin1") as f:
            for line in f:
                m = re.match(r"^\s*([0-9A-Fa-f]{4,8})\s+\d+\s+(\w+):\s*$", line)
                if m and m.group(2) in want:
                    labels[m.group(2)] = base + int(m.group(1), 16)
    convert_ihx(ihx, bin_path, start_addr=base,
                max_length=(code_s + code_l) - base if code_s is not None else image_length(map_path, base))
    return os.path.getsize(bin_path), labels



def _hud_strips_raw():
    hud_h = os.path.join(PROJ, "src", "hud_pkg.h")
    hud_src = open(hud_h, "r").read()
    m_hud = re.search(r"const u8 s_hud_strips\[39\]\[24\] = \{(.*?)\};",
                      hud_src, re.DOTALL)
    hud_raw = bytearray()
    for hl in m_hud.group(1).strip().split("\n"):
        hl_clean = re.sub(r"//.*", "", hl).strip()
        m_r = re.search(r"\{(.*?)\}", hl_clean)
        if m_r:
            nums = [int(x.strip(), 16) for x in m_r.group(1).split(",") if x.strip()]
            assert len(nums) == 24
            hud_raw.extend(nums)
    assert len(hud_raw) == 39 * 24
    return bytes(hud_raw)


def _align8(v):
    return (v + 7) & 0xFFF8


def build_c1_pre(level_idx, song_bin):
    """Imatge C1 d'un nivell ABANS del codi/frames.

    Layout variable (Fase 3): canco + HUD + GAMEOVER + portes + restore.
    Els parametres NO hi son: el build els posa sempre a C1:0x7680 (blindat < 0x7800).
    El codi i els frames els afegeix build_level_packages() a partir d'aquesta imatge.
    Escriu obj/MUSMAIN_<n>.BIN i obj/C1LAY<n>.BIN (manifest d'offsets).
    """
    obj = os.path.join(PROJ, "obj")
    mdata = open(song_bin, "rb").read()
    hud_raw = _hud_strips_raw()
    go_src = os.path.join(PROJ, "assets", "bbdata", "GAMEOVER.BIN")
    if not os.path.exists(go_src):
        import gen_gameover
        gen_gameover.generate_gameover()
    go_raw = open(go_src, "rb").read()
    assert len(go_raw) == 1360, len(go_raw)
    rooms_data = open(os.path.join(PROJ, "assets", "bbdata",
                                   "ROOMSC%d.BIN" % level_idx), "rb").read()
    parm_data = open(os.path.join(PROJ, "assets", "bbdata",
                                  "LEVELPARM%d.BIN" % level_idx), "rb").read()
    assert len(parm_data) == LVLPARM_SIZE, len(parm_data)
    tile_vinyl = parm_data[9]
    room_restore = [(off, t) for off, t in enumerate(rooms_data) if t == tile_vinyl]
    rr_data = struct.pack("<H", len(room_restore)) + b"".join(
        struct.pack("<HB", o, t) for o, t in room_restore)
    doors_data = open(os.path.join(PROJ, "assets", "bbdata",
                                   "DOORS%d.BIN" % level_idx), "rb").read()

    hud_off = _align8(0x5000 + len(mdata))
    go_off = _align8(hud_off + len(hud_raw))
    doors_off = _align8(go_off + len(go_raw))
    restore_off = _align8(doors_off + len(doors_data))
    content_end = restore_off + len(rr_data)
    code_base = _align8(content_end)

    data = (mdata + bytes(hud_off - (0x5000 + len(mdata))) + hud_raw +
            bytes(go_off - (hud_off + len(hud_raw))) + go_raw +
            bytes(doors_off - (go_off + len(go_raw))) + doors_data +
            bytes(restore_off - (doors_off + len(doors_data))) + rr_data)
    assert len(data) == content_end - 0x5000, (len(data), content_end)
    out = os.path.join(obj, "MUSMAIN_%d.BIN" % level_idx)
    if not os.path.exists(out) or open(out, "rb").read() != data:
        open(out, "wb").write(data)
    if level_idx == 0:
        shutil.copyfile(out, os.path.join(obj, "MUSMAIN.BIN"))
    lay = struct.pack("<HHHHHHH", len(mdata), hud_off, go_off, doors_off,
                      restore_off, code_base, len(data))
    lay_path = os.path.join(obj, "C1LAY%d.BIN" % level_idx)
    if not os.path.exists(lay_path) or open(lay_path, "rb").read() != lay:
        open(lay_path, "wb").write(lay)
    print("MUSMAIN_%d: %d B (canco %d, HUD 0x%04X, GAMEOVER 0x%04X, "
          "portes 0x%04X, restore 0x%04X, codi 0x%04X)" %
          (level_idx, len(data), len(mdata), hud_off, go_off, doors_off,
           restore_off, code_base))
    return out


def read_c1_layout(level_idx):
    p = os.path.join(PROJ, "obj", "C1LAY%d.BIN" % level_idx)
    vals = struct.unpack("<HHHHHHH", open(p, "rb").read())
    return dict(song_len=vals[0], hud_off=vals[1], gameover_off=vals[2],
                doors_off=vals[3], restore_off=vals[4], code_base=vals[5],
                content_len=vals[6])


def build_music(force):
    """MUSBANK.BIN (player@0x4000 + intro@slot) + MUSMAIN.BIN (tema@slot).
    Genera obj/mus_ext.s (EQU _akg_init/_akg_play pel GAME)."""
    obj = os.path.join(PROJ, "obj")
    # Player (cache mtime+hash; el .rel depen del .s GENERAT + conversor).
    conv = os.path.join(PROJ, "tools", "akg_rasm2sdas.py")
    ps = akg_convert(MUS_PLAYER_SRC, "player_akg", force)
    prel = os.path.join(obj, "player_akg.rel")
    if force or is_stale(prel, [ps, os.path.join(PROJ, MUS_PLAYER_SRC), conv]):
        run([SDASZ80, "-plosgff", prel, ps])
        mark_fresh(prel, [ps, os.path.join(PROJ, MUS_PLAYER_SRC), conv])
    pbin = os.path.join(obj, "player_akg.bin")
    psize, plabels = link_bin(prel, "musplayer", MUS_PLAYER_BASE, None, pbin,
                              extra_labels=("PLY_AKG_Init", "PLY_AKG_Play", "PLY_AKG_Stop"))
    if psize > (MUS_SONG_SLOT - MUS_PLAYER_BASE):
        print("\n[FATAL] Player AKG: %d B envaeix l'slot 0x%04X!" % (psize, MUS_SONG_SLOT))
        sys.exit(1)
    # Cancons (mateix conversor; cadascuna al seu .rel).
    songs = {}
    for tag, src in (("intro", MUS_INTRO_SRC), ("main", MUS_MAIN_SRC),
                     ("theme1", MUS_THEME1_SRC), ("theme2", MUS_THEME2_SRC)):
        ss = akg_convert(src, "song_" + tag, force)
        srel = os.path.join(obj, "song_" + tag + ".rel")
        if force or is_stale(srel, [ss, os.path.join(PROJ, src), conv]):
            run([SDASZ80, "-plosgff", srel, ss])
            mark_fresh(srel, [ss, os.path.join(PROJ, src), conv])
        sbin = os.path.join(obj, "song_" + tag + ".bin")
        ssize, _ = link_bin(srel, "mussong_" + tag, MUS_SONG_SLOT, None, sbin)
        if MUS_SONG_SLOT + ssize > 0x8000:
            print("\n[FATAL] Canco %s: 0x%04X+%d surt de la finestra!" % (tag, MUS_SONG_SLOT, ssize))
            sys.exit(1)
        songs[tag] = (sbin, ssize)
    # --- HUD + GAME OVER: codi COMU al C1 compartit (MUSBANK) ---------------
    # Escriuen a VRAM => han de viure a la RAM 1 i cridar-se amb 0xC0. Com que
    # son comuns a tots els nivells, van a MUSBANK (0x4C10, despres del player)
    # i no al bloc de codi del nivell.
    hb_base, hb_data = 0x4C10, 0x4FA8
    hb_src = os.path.join(PROJ, "src", "hud_bank.c")
    hb_rel = os.path.join(obj, "hud_bank.rel")
    hb_headers = [os.path.join(PROJ, n) for n in
                  ("engine/cpctelera.h", "src/moving.h", "src/level_params.h")]
    if force or is_stale(hb_rel, [hb_src] + hb_headers):
        run([SDCC] + INCLUDES + CFLAGS + ["-c", hb_src, "-o", hb_rel])
        mark_fresh(hb_rel, [hb_src] + hb_headers)
    equ_s = build_bank_equ(os.path.join(obj, "bluesb.map"))
    equ_rel = os.path.join(obj, "bank_equ.rel")
    if force or is_stale(equ_rel, [equ_s]):
        run([SDASZ80, "-plosgff", equ_rel, equ_s])
        mark_fresh(equ_rel, [equ_s])
    hb_ihx = os.path.join(obj, "hudbank.ihx")
    run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % hb_base,
         "--data-loc", "0x%04X" % hb_data] +
        [hb_rel, equ_rel, os.path.join(obj, "enemy_ext.rel")] + ["-o", hb_ihx])
    hb_map = os.path.join(obj, "hudbank.map")
    code_s, code_l = map_area(hb_map, "CODE")
    if code_s is not None and (code_s + code_l) > hb_data:
        print("\n[FATAL] HUD (MUSBANK): el codi arriba a les dades (0x%04X)!" % hb_data)
        sys.exit(1)
    hb_bin = os.path.join(obj, "hud_bank.bin")
    convert_ihx(hb_ihx, hb_bin, start_addr=hb_base, max_length=code_l)
    hb_syms = {}
    for line in open(hb_rel, encoding="latin1"):
        m = re.match(r"S (\S+) Def([0-9A-Fa-f]+)", line.strip())
        if m:
            hb_syms[m.group(1)] = hb_base + int(m.group(2), 16)
    need_hud = {"_hud_init_o": "_hud_init_b", "_hud_render_o": "_hud_render_b",
                "_gameover_o": "_gameover_banner_b",
                "_acid_hurt_o": "_acid_hurt_b"}
    if any(k not in hb_syms for k in need_hud.values()):
        print("\n[FATAL] HUD: simbols no trobats (%s)" % sorted(hb_syms))
        sys.exit(1)
    ext_hud = os.path.join(obj, "hud_ext.s")
    ext_hud_txt = ("    .module hud_ext\n" + "".join(
        "    .globl %s\n%s = 0x%04X\n" % (o, o, hb_syms[n])
        for o, n in need_hud.items()))
    if not os.path.exists(ext_hud) or open(ext_hud).read() != ext_hud_txt:
        open(ext_hud, "w").write(ext_hud_txt)

    # MUSBANK = player + HUD/GAMEOVER + pad fins slot + intro + pad fins 0x1D00 + LVLCHS (814 B).
    LVLCHS_MB_OFF = 0x1D00
    LVLCHS_LEN = 814
    mbin = os.path.join(obj, "MUSBANK.BIN")
    pdata = open(pbin, "rb").read()
    idata = open(songs["intro"][0], "rb").read()
    hdata = open(hb_bin, "rb").read()
    pad1 = hb_base - (MUS_PLAYER_BASE + len(pdata))
    pad2 = MUS_SONG_SLOT - (hb_base + len(hdata))
    assert pad1 >= 0 and pad2 >= 0, (pad1, pad2)
    mb_prefix = pdata + bytes(pad1) + hdata + bytes(pad2) + idata
    assert len(mb_prefix) <= LVLCHS_MB_OFF, (len(mb_prefix), LVLCHS_MB_OFF)
    mb_prefix += bytes(LVLCHS_MB_OFF - len(mb_prefix))
    old_tail = bytes(LVLCHS_LEN)
    if os.path.exists(mbin):
        old_mb = open(mbin, "rb").read()
        if len(old_mb) == LVLCHS_MB_OFF + LVLCHS_LEN:
            old_tail = old_mb[LVLCHS_MB_OFF:]
    open(mbin, "wb").write(mb_prefix + old_tail)
    # MUSMAIN = imatge C1 variable de cada nivell (canco + HUD + GAMEOVER +
    # portes + restore). El codi i els frames els afegeix build_level_packages.
    mainbin = build_c1_pre(0, songs["main"][0])
    build_c1_pre(1, songs["theme1"][0])
    build_c1_pre(2, songs["theme2"][0])
    # EQU pel GAME (mus.s crida _akg_init/_akg_play en finestra C1).
    ext_s = os.path.join(obj, "mus_ext.s")
    need = {"_akg_init": plabels.get("PLY_AKG_Init"), "_akg_play": plabels.get("PLY_AKG_Play"),
            "_akg_stop": plabels.get("PLY_AKG_Stop")}
    if None in need.values():
        print("\n[FATAL] MUSICA: PLY_AKG_Init/Play no trobats al .lst (%s)" % sorted(plabels))
        sys.exit(1)
    ext_txt = ("    .module mus_ext\n" +
               "".join("    .globl %s\n%s = 0x%04X\n" % (k, k, v) for k, v in need.items()))
    if not os.path.exists(ext_s) or open(ext_s).read() != ext_txt:
        open(ext_s, "w").write(ext_txt)
    print("MUSBANK: player %d B + intro %d B = %d B; MUSMAIN %d B; init=0x%04X play=0x%04X" %
          (len(pdata), len(idata), os.path.getsize(mbin), os.path.getsize(mainbin),
           need["_akg_init"], need["_akg_play"]))
    return mbin, mainbin


def compile_and_link(force):
    obj = os.path.join(PROJ, "obj")
    objs = []
    for rel_src in ASM_SOURCES:
        src = os.path.join(PROJ, rel_src)
        rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
        if force or is_stale(rel, [src]):
            run([SDASZ80, "-plosgff", rel, src])
            mark_fresh(rel, [src])
        if rel_src not in GAME_LINK_SKIP:
            objs.append(rel)
    for rel_src in C_SOURCES:
        src = os.path.join(PROJ, rel_src)
        rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
        headers = [os.path.join(PROJ, name) for name in C_HEADERS[rel_src]]
        if force or is_stale(rel, [src] + headers):
            run([SDCC] + INCLUDES + CFLAGS + ["-c", src, "-o", rel])
            mark_fresh(rel, [src] + headers)
        if rel_src not in GAME_LINK_SKIP:
            objs.append(rel)
    # EQU de musica (obj/mus_ext.s, generat per build_music() ABANS d'aqui):
    # _akg_init/_akg_play en finestra C1 (els crida engine/mus.s).
    mus_ext_s = os.path.join(obj, "mus_ext.s")
    mus_ext_rel = os.path.join(obj, "mus_ext.rel")
    if not os.path.exists(mus_ext_s):
        print("\n[FATAL] obj/mus_ext.s no existeix: build_music() ha de correr abans de compile_and_link!")
        sys.exit(1)
    if force or is_stale(mus_ext_rel, [mus_ext_s]):
        run([SDASZ80, "-plosgff", mus_ext_rel, mus_ext_s])
        mark_fresh(mus_ext_rel, [mus_ext_s])
    objs.append(mus_ext_rel)
    # EQU del HUD/GAME OVER (obj/hud_ext.s, generat per build_music): adreces
    # del codi comu al C1 compartit (MUSBANK).
    hud_ext_s = os.path.join(obj, "hud_ext.s")
    hud_ext_rel = os.path.join(obj, "hud_ext.rel")
    if not os.path.exists(hud_ext_s):
        print("\n[FATAL] obj/hud_ext.s no existeix: build_music() ha de correr abans!")
        sys.exit(1)
    if force or is_stale(hud_ext_rel, [hud_ext_s]):
        run([SDASZ80, "-plosgff", hud_ext_rel, hud_ext_s])
        mark_fresh(hud_ext_rel, [hud_ext_s])
    objs.append(hud_ext_rel)
    # EQU d'enemics/HUD (obj/enemy_ext.s: _s_hud_strips a C2; llavor al
    # main(), real des de build_enemybank). render.c hi accedeix banked.
    en_ext_s = os.path.join(obj, "enemy_ext.s")
    en_ext_rel = os.path.join(obj, "enemy_ext.rel")
    if not os.path.exists(en_ext_s):
        print("\n[FATAL] obj/enemy_ext.s no existeix: el main() n'ha de posar llavor!")
        sys.exit(1)
    if force or is_stale(en_ext_rel, [en_ext_s]):
        run([SDASZ80, "-plosgff", en_ext_rel, en_ext_s])
        mark_fresh(en_ext_rel, [en_ext_s])
    objs.append(en_ext_rel)
    ihx = os.path.join(obj, PROGNAME + ".ihx")
    run([SDCC] + LINKARGS + objs + ["-o", ihx])
    map_path = os.path.join(obj, PROGNAME + ".map")
    game_path = os.path.join(obj, "GAME.BIN")
    convert_ihx(ihx, game_path, start_addr=0x0100, max_length=image_length(map_path, 0x0100))
    report_and_assert_memory_budget(map_path)
    return game_path, find_start(map_path), os.path.getsize(game_path)


def crc16_ccitt(data, init=0xFFFF):
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def verify_starter_jump():
    """Anti-ranci 12/10/26: el starter crida GAME_START en dur. Si el .rel
    no s'ha recompilat amb les taules finals, el salt apunta a brossa
    (sautar LD SP = pila podrida = reboot a BASIC). Compara el CALL real
    del BIN (patro CALL xxxx; JR $) amb src/starter_tables.h. FATAL si no
    coincideixen (refer amb -f, mai un DSK incoherent)."""
    import re as _re
    sbin = open(os.path.join(PROJ, "obj", "STARTER.BIN"), "rb").read()
    jumps = [m.group(1)[0] | (m.group(1)[1] << 8)
             for m in _re.finditer(b"\xCD(..)\x18\xFE", sbin, _re.S)
             if (m.group(1)[0] | (m.group(1)[1] << 8)) < 0x8000]
    if len(jumps) != 1:
        print("\n[FATAL] Starter: no trobo el salt unic a GAME (trobat=%s)." % jumps)
        sys.exit(1)
    want = _re.search(r"#define GAME_START (0x[0-9A-Fa-f]+)",
                      open(os.path.join(PROJ, "src", "starter_tables.h")).read()).group(1)
    if jumps[0] != int(want, 16):
        print("\n[FATAL] Starter ranci: salta a 0x%04X pero GAME_START=%s. Refer amb -f." %
              (jumps[0], want))
        sys.exit(1)
    print("STARTER-JUMP-OK: CALL 0x%04X == GAME_START" % jumps[0])


def gen_starter_tables(game_entry, game_start, game_len, game_crc, fdc_entry, front_entry, mus_entry):
    """Genera src/starter_tables.h (GAME + FDC + FRONT + MUSBANK + CRCs)."""
    obytes, scount, chs = game_entry
    fbytes, fcount, fchs, fcrc = fdc_entry
    rbytes, rcount, rchs, rcrc = front_entry
    mbytes, mcount, mchs, mcrc = mus_entry
    hold = map_symbols(os.path.join(PROJ, "obj", PROGNAME + ".map")).get("_g_mus_hold", -1)
    if hold < 0:
        print("\n[FATAL] HOLD: _g_mus_hold no es al mapa resident (starter_tables).")
        sys.exit(1)
    lines = ["#ifndef STARTER_TABLES_H", "#define STARTER_TABLES_H",
             '#include "fdc.h"', "",
             "// Generat per tools/build.py. NO EDITAR.",
             "#define GAME_START 0x%04X" % game_start,
             "#define GAME_LEN %d" % game_len,
             "#define GAME_CRC 0x%04X" % game_crc,
             "#define FDC_LEN %d" % fbytes,
             "#define CRC_FDC 0x%04X" % fcrc,
             "#define FRONT_LEN %d" % rbytes,
             "#define CRC_FRONT 0x%04X" % rcrc,
             "#define MUS_LEN %d" % mbytes,
             "#define CRC_MUS 0x%04X" % mcrc,
             "// HOLD musica ISR (_g_mus_hold del GAME): el starter el neteja a",
             "// s_start (reboot calent podria dur brossa = ISR muda per sempre).",
             "#define MUS_HOLD_ADDR 0x%04X" % hold, "",
             "static const u8 g_game_chs[%d] = {" % len(chs)]
    for i in range(0, len(chs), 12):
        lines.append("    " + ",".join("0x%02X" % b for b in chs[i:i + 12]) + ",")
    lines.append("};")
    lines.append("static const DiskFileDesc g_file_game = { %d, %d, g_game_chs };" % (obytes, scount))
    lines.append("static const u8 g_fdc_chs[%d] = {" % len(fchs))
    for i in range(0, len(fchs), 12):
        lines.append("    " + ",".join("0x%02X" % b for b in fchs[i:i + 12]) + ",")
    lines.append("};")
    lines.append("static const DiskFileDesc g_file_fdc = { %d, %d, g_fdc_chs };" % (fbytes, fcount))
    lines.append("static const u8 g_front_chs[%d] = {" % len(rchs))
    for i in range(0, len(rchs), 12):
        lines.append("    " + ",".join("0x%02X" % b for b in rchs[i:i + 12]) + ",")
    lines.append("};")
    lines.append("static const DiskFileDesc g_file_front = { %d, %d, g_front_chs };" % (rbytes, rcount))
    lines.append("static const u8 g_mus_chs[%d] = {" % len(mchs))
    for i in range(0, len(mchs), 12):
        lines.append("    " + ",".join("0x%02X" % b for b in mchs[i:i + 12]) + ",")
    lines.append("};")
    lines.append("static const DiskFileDesc g_file_mus = { %d, %d, g_mus_chs };" % (mbytes, mcount))
    lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def placeholder_starter_tables():
    chs = [0] * (28 * 3)
    fchs = [0] * (4 * 3)
    rchs = [0] * (2 * 3)
    mchs = [0] * (16 * 3)
    lines = ["#ifndef STARTER_TABLES_H", "#define STARTER_TABLES_H",
             '#include "fdc.h"', "",
             "#define GAME_START 0x13BA",
             "#define GAME_LEN 14185",
             "#define GAME_CRC 0x0000",
              "#define FDC_LEN 1400",
              "#define CRC_FDC 0x0000",
              "#define FRONT_LEN 512",
              "#define CRC_FRONT 0x0000",
              "#define MUS_LEN 8192",
              "#define CRC_MUS 0x0000",
              "#define MUS_HOLD_ADDR 0x0000", "",
             "static const u8 g_game_chs[%d] = { 0 };" % len(chs),
             "static const DiskFileDesc g_file_game = { 14318, 28, g_game_chs };",
             "static const u8 g_fdc_chs[%d] = { 0 };" % len(fchs),
             "static const DiskFileDesc g_file_fdc = { 1400, 4, g_fdc_chs };",
             "static const u8 g_front_chs[%d] = { 0 };" % len(rchs),
             "static const DiskFileDesc g_file_front = { 512, 2, g_front_chs };",
             "static const u8 g_mus_chs[%d] = { 0 };" % len(mchs),
             "static const DiskFileDesc g_file_mus = { 8192, 16, g_mus_chs };",
             "",
             "#endif"]
    return "\n".join(lines) + "\n"


# Starter: el firmware el carrega a ST_LOAD (0x3000) però s'hi executa
# reubicat a ST_RUN (0xC000, VRAM): la imatge GAME (0x0100..0x3869) trepitja
# 0x3000 mentre carrega i corrompria el CALL final (símptoma: cau a BASIC).
# s_start és 100% PIC (només LD imm + LDIR + JP absolut a _s_main): pot
# executar-se a 0x3000 tot i enllaçar a 0xC000, copiar la finestra sencera
# a VRAM i saltar-hi. L'exec del firmware ha de ser 0x3000 (load addr).
ST_LOAD = 0x3000
ST_RUN = 0xC000   # VRAM; s_start desconnecta ROMs (RMR) abans de copiar-hi
ST_DATA = 0xC700
ST_WIN = 0x0800


def build_starter(force):
    """Compila+enllaça el starter (load 0x3000, run 0xC000). Retorna (bin, s_start)."""
    obj = os.path.join(PROJ, "obj")
    src = os.path.join(PROJ, "engine", "starter.c")
    rel = os.path.join(obj, "starter.rel")
    headers = [os.path.join(PROJ, "src", "starter_tables.h"),
               os.path.join(PROJ, "engine", "fdc.h")]
    if force or is_stale(rel, [src] + headers):
        run([SDCC] + INCLUDES + CFLAGS + ["-c", src, "-o", rel])
        mark_fresh(rel, [src] + headers)
    fdc_rel = os.path.join(obj, "fdc.rel")
    assets_rel = os.path.join(obj, "assets_fdc.rel")
    hold_rel = os.path.join(obj, "fdc_hold.rel")
    ihx = os.path.join(obj, "starter.ihx")
    run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % ST_RUN,
         "--data-loc", "0x%04X" % ST_DATA, fdc_rel, assets_rel, hold_rel, rel, "-o", ihx])
    map_path = os.path.join(obj, "starter.map")
    bin_path = os.path.join(obj, "STARTER.BIN")
    convert_ihx(ihx, bin_path, start_addr=ST_RUN,
                max_length=image_length(map_path, ST_RUN))
    size = os.path.getsize(bin_path)
    if size > ST_WIN:
        print("\n[FATAL] Starter: %d bytes > finestra 0x%04X..0x%04X! Aprimar." %
              (size, ST_LOAD, ST_LOAD + ST_WIN - 1))
        sys.exit(1)
    syms = map_symbols(map_path)
    start = syms.get("_s_start", -1)
    if not (ST_RUN <= start < ST_RUN + ST_WIN):
        print("\n[FATAL] Starter: _s_start=0x%04X fora de [0x%04X..0x%04X)!" %
              (start, ST_RUN, ST_RUN + ST_WIN))
        sys.exit(1)
    print("STARTER: load=0x%04X run=0x%04X (%d bytes, s_start(link)=0x%04X)" %
          (ST_LOAD, ST_RUN, size, start))
    return bin_path, start


# F1-FRONT: pantalles fixes (SPLASH/SELECT/MAP) en ZX0 classic (v1 = el
# decoder resident zx0_decompress.s). Compressor optimal Orlof/Einar BSD-3
# vendoritzat a tools/zx0pkg/. QUICK mode (mateix format, quasi-optim):
# optimal es lent en Python (~minuts/fitxer) i nomes caldria per retallar
# 2-4 sectors de carrega; canviar ZX0_QUICK a False (drop-in).
ZX0_QUICK = True
# Tags DSK (unics!) -> fitxer base a assets/bbdata (.BIN entrada, .PALHW).
FRONT_SCREENS = [("FSPLASH", "SPLASH"), ("FSELECT", "SELECT"), ("FMAP", "MAP")]
FRONT_TAGS = [t for t, b in FRONT_SCREENS]
FRONT_FILES = {t: b for t, b in FRONT_SCREENS}


def build_dance():
    """DANCE20 pel select (F1): 20 frames reals DOS de 480 B (parelles
    mascara/imatge mode0) = assets/bbdata/DANCE20.BIN (tools/gen_select_dance.py
    des de SPRITE.SQV: Jake dansa 0-5 + idle 6-8 + Elwood dansa-A 9-13 +
    dansa-B 14-19).
    S'AFEGEIX a la cua de obj/FSELECT.ZX0 dins zx0_pack_all (un sol
    escriptor; el depack ZX0 classic te fi explicita i els ignora). El
    FRONT els llegeix de scratch 0x8400+DANCE_OFF (EQU front_ext).
    Per que no fitxer DSK propi? Taules CHS+desc costen ~15 B de Bloc0 i
    forcen rewrite placeholder de TOTES les taules (+150 B transitori):
    a la cua son 0 B."""
    d20 = os.path.join(PROJ, "assets", "bbdata", "DANCE20.BIN")
    data = open(d20, "rb").read()
    assert len(data) == 9600, len(data)
    return data

DANCE_LEN = 9600


def build_mapstick():
    """MAPSTICK pel mapa (F2): sticker nota musical 24x34 (1088 B) + dash
    de ruta 8x6 (96 B), SQV 126/125 a pens del MAPA (tools/gen_map_sticker.py).
    S'AFEGEIX a la cua de obj/FMAP.ZX0 dins zx0_pack_all (mateix patro
    DANCE20: el depack els ignora; el FRONT els llegeix de scratch
    0x8400+STICK_OFF via EQU _fmap_stick_base)."""
    mst = os.path.join(PROJ, "assets", "bbdata", "MAPSTICK.BIN")
    data = open(mst, "rb").read()
    assert len(data) == STICK_LEN, len(data)
    return data


STICK_LEN = 1184


def remap_select(data):
    """Retocs minims de SELECT.BIN (gen_screens, MEDIANCUT determinista de
    CHOIX.SQZ; la resta del quadre es INTACTA):
    - pen 7 (cons) partit esq/dret (x<72 -> 13 / x>=72 -> 14) pel focus
      groc/blau per tinta;
    - pen 6 (ovals a files 147-157) partit esq (x < 72 -> 6) / dret
      (x >= 72 -> 15) pel terra iluminat (groc palid) vs no (blau cel);
      la resta del 6 (linies + confeti blau) -> 7 (blau fix).
    Ha de coincidir amb SELECT.PALHW (fitxer versionat): ballarins a 9-12,
    cons a 13/14, ovals a 6/15, blau fix a 7."""

    def d0(b):
        return ((b >> 7) & 1) | (((b >> 3) & 1) << 1) | \
               (((b >> 5) & 1) << 2) | (((b >> 1) & 1) << 3)

    def d1(b):
        return ((b >> 6) & 1) | (((b >> 2) & 1) << 1) | \
               (((b >> 4) & 1) << 2) | (((b >> 0) & 1) << 3)

    def pack(a, b):
        return ((a & 1) << 7) | (((a >> 1) & 1) << 3) | (((a >> 2) & 1) << 5) | \
               (((a >> 3) & 1) << 1) | ((b & 1) << 6) | (((b >> 1) & 1) << 2) | \
               (((b >> 2) & 1) << 4) | (((b >> 3) & 1) << 0)

    assert len(data) == 16384, len(data)
    lin = bytearray(16000)
    for row in range(200):
        base = (row % 8) * 2048 + (row // 8) * 80
        for xb in range(80):
            byte = data[base + xb]
            out = []
            for k, v in ((0, d0(byte)), (1, d1(byte))):
                x = xb * 2 + k
                if v == 7:
                    v = 13 if x < 72 else 14
                elif v == 6 and 146 <= row <= 158:
                    if x < 72:
                        v = 6
                    elif x >= 72:
                        v = 15
                    else:
                        v = 7
                out.append(v)
            lin[row * 80 + xb] = pack(out[0], out[1])
    inter = bytearray(16384)
    for row in range(200):
        base = (row % 8) * 2048 + (row // 8) * 80
        inter[base:base + 80] = lin[row * 80:(row + 1) * 80]
    return bytes(inter)


def zx0_pack_all():
    """Comprimeix les pantalles FRONT a obj/<TAG>.ZX0 (cache per mtime).
    FSELECT porta la cua DANCE20 (20 frames) a sobre: deps inclouen el
    generador i el .BIN."""
    from zx0pkg.zx0 import zx0_compress
    d20 = os.path.join(PROJ, "assets", "bbdata", "DANCE20.BIN")
    gen20 = os.path.join(PROJ, "tools", "gen_select_dance.py")
    mst = os.path.join(PROJ, "assets", "bbdata", "MAPSTICK.BIN")
    genmst = os.path.join(PROJ, "tools", "gen_map_sticker.py")
    for tag, base in FRONT_SCREENS:
        src = os.path.join(PROJ, "assets", "bbdata", base + ".BIN")
        dst = os.path.join(PROJ, "obj", tag + ".ZX0")
        deps = [src] if tag != "FSELECT" else [src, d20, gen20, __file__]
        if tag == "FMAP":
            deps = [src, mst, genmst, __file__]
        if is_stale(dst, deps):
            data = open(src, "rb").read()
            if tag == "FSELECT":
                data = remap_select(data)
            out, stats = zx0_compress(bytes(data), classic=True, quick=ZX0_QUICK)
            out = bytes(out)
            if tag == "FSELECT":
                out = out + build_dance()
            if tag == "FMAP":
                out = out + build_mapstick()
            open(dst, "wb").write(out)
            mark_fresh(dst, deps)
            print("ZX0: %s %d -> %d B (classic v1, %s)" %
                  (tag, len(data), len(out), "quick" if ZX0_QUICK else "optimal"))


def build_level_bundles(force=False):
    """Genera les dades del jugador (permanents al Banc C7):
    - obj/JAKE.ZX0   : PFRAMES.BIN + 960 B zeros + EXTRA.BIN
    - obj/ELWOOD.ZX0 : ELWOOD.BIN  + 960 B zeros + EXTRA.BIN
    Els paquets de nivell els genera build_level_packages().
    """
    obj = os.path.join(PROJ, "obj")
    from zx0pkg.zx0 import zx0_compress

    # 1. JAKE.ZX0
    jake_dst = os.path.join(obj, "JAKE.ZX0")
    pf_src = os.path.join(PROJ, "assets", "bbdata", "PFRAMES.BIN")
    ex_src = os.path.join(PROJ, "assets", "bbdata", "EXTRA.BIN")
    if force or is_stale(jake_dst, [pf_src, ex_src]):
        pf_data = open(pf_src, "rb").read()
        ex_data = open(ex_src, "rb").read()
        raw = pf_data + bytes(960) + ex_data
        assert len(raw) == 15872, len(raw)
        out, _ = zx0_compress(bytes(raw), classic=True, quick=ZX0_QUICK)
        open(jake_dst, "wb").write(bytes(out))
        mark_fresh(jake_dst, [pf_src, ex_src])
        print("ZX0: JAKE %d -> %d B" % (len(raw), len(out)))

    # 2. ELWOOD.ZX0
    elwood_dst = os.path.join(obj, "ELWOOD.ZX0")
    el_src = os.path.join(PROJ, "assets", "bbdata", "ELWOOD.BIN")
    if force or is_stale(elwood_dst, [el_src, ex_src]):
        el_data = open(el_src, "rb").read()
        ex_data = open(ex_src, "rb").read()
        raw = el_data + bytes(960) + ex_data
        assert len(raw) == 15872, len(raw)
        out, _ = zx0_compress(bytes(raw), classic=True, quick=ZX0_QUICK)
        open(elwood_dst, "wb").write(bytes(out))
        mark_fresh(elwood_dst, [el_src, ex_src])
        print("ZX0: ELWOOD %d -> %d B" % (len(raw), len(out)))


# ---------------------------------------------------------------------------
# Paquets de nivell — format definit a docs/LEVEL_PACKAGE.md (aprovat 20/10/26)
#   capcalera 16 B: magic,version,level_id,flags,total_len,n_sections,disc_id,
#                   hdr_crc, reserved
#   descriptor 8 B: bank, flags(bit0=ZX0), dest, src_off, src_len
# ---------------------------------------------------------------------------
PAK_MAGIC       = 0x42
PAK_VERSION     = 1
PAK_HDR         = 16
PAK_DESC        = 8
PAK_SCRATCH_MAX = (28 * 512) - 128    # 14.208 B: 28 sectors; el FDC en llegeix 14.336 B dins l'scratch de 14.560 B
# ATENCIO: SDCC empaqueta LevelParams sense alineacio (room_row_last=68,
# trig_off=69, code_exc_off=71; sizeof=73). Els offsets ho han de reflectir.
LVLPARM_SIZE    = 77                   # mida de LEVELPARMn.BIN (LevelParams v3)
LVLPARM_ROOMS   = 56                   # offset del camp rooms_off dins el bloc
LVLPARM_DOORS   = 58                   # offset del camp doors_off dins el bloc
LVLPARM_RESTORE = 60                   # offset del camp restore_off dins el bloc
LVLPARM_TRIG    = 69                   # offset del camp trig_off dins el bloc
LVLPARM_CODE_EXC = 71                  # offset del camp code_exc_off dins el bloc
LVLPARM_HUD     = 73                   # offset del camp hud_off dins el bloc
LVLPARM_GAMEOVER = 75                  # offset del camp gameover_off dins el bloc

# Fase 2.1: nomes el nivell 1. Els altres 5 s'hi afegeixen a la Fase 4.
LEVELS = [
    dict(id=0, tag="L1", song="main", doors=23, has_code=True, has_elev=True,
         has_rooms=True),
    dict(id=1, tag="L2", song="theme1", doors=0, has_code=True, has_elev=True,
         has_rooms=False),
    # L3 prison: Theme2 (4.670 B) obliga a layout C1 variable; no te ascensors
    # ni premses (has_elev=False) ni mecanismes propis encara (has_code=False),
    # pero si 6 sales i 24 portes. Aixi el paquet cap a l'scratch de 14.560 B.
    dict(id=2, tag="L3", song="theme2", doors=24, has_code=False, has_elev=False,
         has_rooms=True),
]


def write_package(path, level_id, flags, sections):
    """Escriu un paquet amb manifest.

    sections = [(bank, zx0, dest, payload, dest_len)] on `dest_len` és la mida
    DESCOMPRIMIDA (la que ocupa al banc). Comprova solapaments, límits de
    finestra i que el fitxer càpiga a l'scratch del carregador (0x8320-0xBBFF).
    """
    n = len(sections)
    off = PAK_HDR + PAK_DESC * n
    desc = b""
    for bank, zx0, dest, payload, dest_len in sections:
        desc += struct.pack("<BBHHH", bank, 1 if zx0 else 0, dest, off, len(payload))
        off += len(payload)
    total = off

    # Per banc: dins la finestra 0x4000-0x7FFF i sense solapaments.
    by_bank = {}
    for bank, zx0, dest, payload, dest_len in sections:
        assert 0x4000 <= dest and dest + dest_len <= 0x8000, \
            "secció fora de la finestra (banc 0x%02X, 0x%04X+%d)" % (bank, dest, dest_len)
        by_bank.setdefault(bank, []).append((dest, dest + dest_len))
    for bank, rngs in by_bank.items():
        rngs.sort()
        for a, b in zip(rngs, rngs[1:]):
            assert a[1] <= b[0], "solapament al banc 0x%02X: 0x%04X..0x%04X i 0x%04X" % (
                bank, a[0], a[1], b[0])
    assert total <= PAK_SCRATCH_MAX, \
        "paquet de %d B > scratch %d B (cal carrega en 2 passades)" % (total, PAK_SCRATCH_MAX)

    head = struct.pack("<BBBBHHH", PAK_MAGIC, PAK_VERSION, level_id, flags,
                       total & 0xFFFF, n, 0)
    assert len(head) == 10
    hdr = head + struct.pack("<H", crc16_ccitt(head)) + b"\x00\x00\x00\x00"
    assert len(hdr) == PAK_HDR
    open(path, "wb").write(hdr + desc + b"".join(s[3] for s in sections))

    # Informe de pressupost per banc (asserts fatals a partir de la Fase 3,
    # quan el layout ja no és el llegat: ara C5 va ple per disseny).
    for bank in sorted(by_bank):
        used = sum(b - a for a, b in by_bank[bank])
        print("    banc 0x%02X: %5d B usats, %5d lliures%s" % (
            bank, used, 16384 - used, "" if 16384 - used >= 256 else "  [JUST]"))


def build_level_packages(force=False):
    """Genera LnWORLD.PAK + LnENEMI.ZX0 (manifest) i GAMEOVER.ZX0 (comu).

    Fase 2.1: els destins son els MATEIXOS que al format antic, perque el joc
    quedi identic; la Fase 3 els reorganitza (sales a C5, HUD despres de la
    canco...)."""
    obj = os.path.join(PROJ, "obj")
    from zx0pkg.zx0 import zx0_compress



    for lv in LEVELS:
        tag = lv["tag"]
        lid = lv["id"]
        tiles_src = os.path.join(PROJ, "assets", "bbdata", "TILESETC%d.BIN" % lid)
        map_src = os.path.join(PROJ, "assets", "bbdata", "MAPC%d.BIN" % lid)
        trig_src = os.path.join(PROJ, "assets", "bbdata", "TRIGC%d.BIN" % lid)
        rooms_src = os.path.join(PROJ, "assets", "bbdata", "ROOMSC%d.BIN" % lid)
        bank5_src = os.path.join(obj, "BANK5_%d.BIN" % lid)
        mus_src = os.path.join(obj, "MUSMAIN.BIN" if lid == 0 else "MUSMAIN_%d.BIN" % lid)
        lay_src = os.path.join(obj, "C1LAY%d.BIN" % lid)
        code_src = os.path.join(obj, "LEVELCODE_%d.BIN" % lid)
        code_data_src = os.path.join(obj, "LEVELDATA_%d.BIN" % lid)
        elev_src = os.path.join(PROJ, "assets", "bbdata", "PRESS.BIN" if lid == 1 else "ELEV.BIN")
        en_src = os.path.join(obj, "ENEMI_%d.BIN" % lid)
        parm_src = os.path.join(PROJ, "assets", "bbdata", "LEVELPARM%d.BIN" % lid)

        world_dst = os.path.join(obj, tag + "WORLD.PAK")
        en_dst = os.path.join(obj, tag + "ENEMI.ZX0")
        c1_dst = os.path.join(obj, tag + "C1.PAK")
        srcs = [tiles_src, map_src, trig_src, rooms_src, bank5_src, mus_src,
                lay_src, en_src, parm_src]
        if lv["has_code"]:
            srcs += [code_src, code_data_src]
        if lv["has_elev"]:
            srcs.append(elev_src)

        if force or is_stale(world_dst, srcs) or (lv["id"] == 2 and not os.path.exists(c1_dst)):
            t_raw = open(tiles_src, "rb").read()
            # L3: els tiles comprimeixen 321 B mes amb quick=False; cal per
            # cabre en 28 sectors (el FDC nomes pot llegir 14.336 B a l'scratch).
            t_zx, _ = zx0_compress(bytes(t_raw), classic=True,
                                   quick=ZX0_QUICK if lv["id"] != 2 else False)

            # C5 (Fase 3.2): [mapa][sales][TRIG compacte] ... [codi del mon].
            # Tres seccions independents: el codi queda a BANK5_BASE (0x6E00)
            # fix (slots BC_* del resident) i els offsets reals de les sales i
            # el TRIG van al manifest i a LevelParams. El forat entre TRIG i
            # codi no es compta com a usat (no cal omplir-lo de zeros).
            map_raw = open(map_src, "rb").read()
            rooms_raw = open(rooms_src, "rb").read()
            trigc_raw = open(trig_src, "rb").read()
            code_raw = open(bank5_src, "rb").read()
            assert len(trigc_raw) % 5 == 0 and len(trigc_raw) > 0, len(trigc_raw)
            rooms_off = 0x4000 + len(map_raw)
            trig_off = rooms_off + len(rooms_raw)
            assert trig_off + len(trigc_raw) <= BANK5_BASE, \
                "C5: sales+TRIG (fins 0x%04X) trepitgen el codi (0x%04X)" % (
                    trig_off + len(trigc_raw), BANK5_BASE)
            assert BANK5_BASE + len(code_raw) <= 0x8000, (BANK5_BASE, len(code_raw))
            rooms_trig_raw = rooms_raw + trigc_raw
            map_zx, _ = zx0_compress(bytes(map_raw), classic=True,
                                     quick=ZX0_QUICK if lv["id"] != 2 else False)
            rt_zx, _ = zx0_compress(bytes(rooms_trig_raw), classic=True, quick=ZX0_QUICK)
            code_zx, _ = zx0_compress(bytes(code_raw), classic=True, quick=ZX0_QUICK)
            c5_used = len(map_raw) + len(rooms_trig_raw) + len(code_raw)
            assert 16384 - c5_used >= 256, \
                "C5 del nivell %s: nomes %d B lliures (minim 256)" % (
                    tag, 16384 - c5_used)
            print("    C5: mapa 0x4000 (%d), sales 0x%04X (%d), TRIG 0x%04X (%d), "
                  "codi 0x%04X (%d) -> %d B, %d lliures" %
                  (len(map_raw), rooms_off, len(rooms_raw), trig_off,
                   len(trigc_raw), BANK5_BASE, len(code_raw), c5_used,
                   16384 - c5_used))

            # C1: imatge MUSMAIN (canco+HUD+GAMEOVER+portes+restore) + codi + frames + params + data
            lay = read_c1_layout(lid)
            mus_raw = open(mus_src, "rb").read()
            assert len(mus_raw) == lay["content_len"], (len(mus_raw), lay)
            code_base = lay["code_base"]
            assert code_base == _align8(0x5000 + len(mus_raw)), (code_base, len(mus_raw))
            m_data = bytearray(mus_raw)
            if lv["has_code"]:
                m_data += bytes(code_base - 0x5000 - len(m_data))
                m_data += open(code_src, "rb").read()
                if lv["has_elev"]:
                    assert len(m_data) <= (LC1_FRAMES_BASE - 0x5000), len(m_data)
                    m_data += bytes(LC1_FRAMES_BASE - 0x5000 - len(m_data))
                    m_data += open(elev_src, "rb").read()
                else:
                    # Sense frames de mecanismes: el codi pot arribar fins als
                    # parametres (p. ex. L3, Theme2 + codi a 0x6BA0).
                    assert len(m_data) <= (LC1_PARAMS_BASE - 0x5000), len(m_data)
            # Parametres sempre a C1:0x7680 (blindat < 0x7800 per no tocar FDC mestre a C0:0x7800)
            m_data += bytes(LC1_PARAMS_BASE - 0x5000 - len(m_data))
            parm = bytearray(open(parm_src, "rb").read())
            assert len(parm) == LVLPARM_SIZE, len(parm)
            for fld, val in ((LVLPARM_ROOMS, rooms_off), (LVLPARM_TRIG, trig_off),
                             (LVLPARM_CODE_EXC, code_base if lv["has_code"] else 0),
                             (LVLPARM_HUD, lay["hud_off"]),
                             (LVLPARM_GAMEOVER, lay["gameover_off"]),
                             (LVLPARM_DOORS, lay["doors_off"]),
                             (LVLPARM_RESTORE, lay["restore_off"])):
                parm[fld] = val & 0xFF
                parm[fld + 1] = (val >> 8) & 0xFF
            m_data += parm
            # Dades BSS del codi del nivell (--data-loc 0x7700)
            m_data += bytes(LC1_DATA_BASE - 0x5000 - len(m_data))
            if lv["has_code"]:
                m_data += open(code_data_src, "rb").read()
            m_data = bytes(m_data)
            # Assegurar que MAI toca 0x7800!
            assert len(m_data) <= (0x7800 - 0x5000), "C1 (len=%d, limit=0x%04X) trepitja C0:0x7800 FDC!" % (len(m_data), 0x5000 + len(m_data))
            m_zx, _ = zx0_compress(m_data, classic=True, quick=ZX0_QUICK)

            flags = ((1 if lv["has_code"] else 0) | (2 if lv["has_elev"] else 0) |
                     (4 if lv["has_rooms"] else 0) | 8)
            world_secs = [
                (0xC4, True, 0x4000, bytes(t_zx), len(t_raw)),
                (0xC5, True, 0x4000, bytes(map_zx), len(map_raw)),
                (0xC5, True, rooms_off, bytes(rt_zx), len(rooms_trig_raw)),
                (0xC5, True, BANK5_BASE, bytes(code_zx), len(code_raw)),
            ]
            # L3: C1 separat (L3C1.PAK) per alliberar L3WORLD i poder afegir
            # animacions/triggers de sala sense passar de 28 sectors.
            if lv["id"] != 2:
                world_secs.append((0xC1, True, 0x5000, bytes(m_zx), len(m_data)))
            write_package(world_dst, lv["id"], flags, world_secs)
            mark_fresh(world_dst, srcs)
            if lv["id"] == 2:
                write_package(c1_dst, lv["id"], flags,
                              [(0xC1, True, 0x5000, bytes(m_zx), len(m_data))])
                print("PAK: %sC1 %d B" % (tag, os.path.getsize(c1_dst)))
            print("PAK: %sWORLD %d B (tiles=%d c5=%d+%d+%d c1=%d)" %
                  (tag, os.path.getsize(world_dst), len(t_zx), len(map_zx),
                   len(rt_zx), len(code_zx), len(m_zx)))

        if force or is_stale(en_dst, [en_src]):
            en_raw = open(en_src, "rb").read()
            e_zx, _ = zx0_compress(bytes(en_raw), classic=True, quick=ZX0_QUICK)
            write_package(en_dst, lv["id"], 0, [(0xC6, True, 0x4000, bytes(e_zx), len(en_raw))])
            mark_fresh(en_dst, [en_src])
            print("PAK: %sENEMI %d B" % (tag, os.path.getsize(en_dst)))



def package(starter_path, starter_start, game_path):
    dsk_path = os.path.join(PROJ, PROGNAME + ".dsk")
    create_empty_cpc_dsk(dsk_path, 40)
    dsk = DskPatcher(dsk_path)
    chs_map = {}

    def add_file(name8, ext3, payload, load_addr, exec_addr, make_table=True):
        hdr = amsdos_header(name8, ext3, 0x02, load_addr, exec_addr, len(payload))
        blocs = dsk.add_file(name8, ext3, hdr + payload)
        if make_table:
            chs = []
            for b in blocs:
                for (t, sid) in dsk.bloc_to_ts(b):
                    chs += [t, sid]  # parelles (track,sid): head sempre 0
            return (len(payload) + 128, len(chs) // 2, chs)
        return None

    # BLUESB primer (starter, pistes 0-1): l'únic que carrega el firmware.
    # load=0x3000; exec=s_start en adresses de càrrega (0x3000 + desplaçament
    # dins la imatge). s_start és PIC: copia la finestra a 0xC000 i hi salta.
    s_exec = ST_LOAD + (starter_start - ST_RUN)
    sdata = open(starter_path, "rb").read()
    add_file(DSKNAME8, "BIN", sdata, ST_LOAD, s_exec, make_table=False)
    # GAME.BIN (imatge resident completa): el carrega el starter amb reintents.
    gdata = open(game_path, "rb").read()
    gentry = add_file("GAME", "BIN", gdata, 0x0100, 0x0100, make_table=True)
    mb_blocs = None
    for name8, ext3, path in DATA_FILES:
        data = open(path, "rb").read()
        hdr = amsdos_header(name8, ext3, 0x02, 0x0000, 0x0000, len(data))
        blocs = dsk.add_file(name8, ext3, hdr + data)
        chs = []
        for b in blocs:
            for (t, sid) in dsk.bloc_to_ts(b):
                chs += [t, sid]  # parelles (track,sid): head sempre 0
        chs_map[name8] = (len(data) + 128, len(chs) // 2, chs, crc16_ccitt(data))
        if name8 == "MUSBANK":
            mb_blocs = blocs

    # Taula de disc dels nivells (C1:0x4000 de MUSBANK). 6 nivells x (WORLD, ENEMI, C1).
    # Format: "LV", 1, 6 + 18 x <u16 ondisk, u8 sectors, u16 crc> (94 B)
    # + pool [6 nivells][WORLD 56 B (28 sec)][ENEMI 32 B (16 sec)][C1 32 B (16 sec)] = 720 B
    # Total = 814 B incrustats a C1:0x4000 dins MUSBANK.BIN abans de la canco intro (0x5000).
    lvl_payload = bytearray(b"LV\x01\x06")
    lvl_pool = bytearray(6 * (56 + 32 + 32))
    for lvl in range(6):
        for typ, suffix, max_sec, stride in ((0, "WORLD", 28, 56), (1, "ENEMI", 16, 32), (2, "C1", 16, 32)):
            name = "L%d%s" % (lvl + 1, suffix)
            if name in chs_map:
                obytes, scount, chs, lcrc = chs_map[name]
                assert scount <= max_sec, (name, scount, max_sec)
                lvl_payload += struct.pack("<HBH", obytes, scount, lcrc)
                off = lvl * (56 + 32 + 32) + (0 if typ == 0 else (56 if typ == 1 else 88))
                lvl_pool[off:off + len(chs)] = bytes(chs)
            else:
                lvl_payload += struct.pack("<HBH", 0, 0, 0)
    lvl_payload += lvl_pool
    assert len(lvl_payload) == 814, len(lvl_payload)

    # Incrustar LVLCHS a MUSBANK.BIN a offset 0x1D00 (C1:0x5D00, despres de song_intro)
    # sense trepitjar player_akg (0x4000..0x4C00), hud_bank (0x4C10..0x4FA0) ni song_intro (0x5000..0x5C12).
    # En arrencar el primer nivell, load_level_file el copia a C1:0x7C00..0x7F2D (zona permanent lliure).
    LVLCHS_MB_OFF = 0x1D00
    obj_dir = os.path.join(PROJ, "obj")
    mbin_path = os.path.join(obj_dir, "MUSBANK.BIN")
    mbin_data = bytearray(open(mbin_path, "rb").read())
    assert len(mbin_data) == LVLCHS_MB_OFF + len(lvl_payload), (len(mbin_data), LVLCHS_MB_OFF + len(lvl_payload))
    mbin_data[LVLCHS_MB_OFF:LVLCHS_MB_OFF + len(lvl_payload)] = lvl_payload
    open(mbin_path, "wb").write(bytes(mbin_data))

    # Actualitzar les dades de MUSBANK dins la imatge del DSK
    dsk_path = os.path.join(PROJ, PROGNAME + ".dsk")
    m_raw = bytes(mbin_data)
    m_hdr = amsdos_header("MUSBANK", "BIN", 0x02, 0x4000, 0x4000, len(m_raw))
    if mb_blocs is not None and len(mb_blocs) > 0:
        dsk.write_file_data(mb_blocs[0], m_hdr + m_raw)
        chs_map["MUSBANK"] = (len(m_raw) + 128, len(chs_map["MUSBANK"][2]) // 2, chs_map["MUSBANK"][2], crc16_ccitt(m_raw))

    dsk.save(dsk_path)
    print("DSK: %s  (RUN\"%s\" -> starter load 0x%04X/run 0x%04X, game=%d bytes)" %
          (dsk_path, DSKNAME8, ST_LOAD, ST_RUN, len(gdata)))
    return chs_map, gentry, len(gdata), crc16_ccitt(gdata)


def gen_header(chs_map):
    lines = ["#ifndef DISK_TABLES_H", "#define DISK_TABLES_H", '#include "fdc.h"', ""]
    for name, (obytes, scount, chs, crc) in chs_map.items():
        if name in GAME_TABLE_SKIP:
            lines.append("#define CRC_%s 0x%04X" % (name, crc))
            lines.append("")
            continue
        var = name.lower()
        lines.append("static const u8 g_%s_chs[%d] = {" % (var, len(chs)))
        for i in range(0, len(chs), 12):
            lines.append("    " + ",".join("0x%02X" % b for b in chs[i:i + 12]) + ",")
        lines.append("};")
        lines.append("static const DiskFileDesc g_file_%s = { %d, %d, g_%s_chs };" % (var, obytes, scount, var))
        lines.append("#define CRC_%s 0x%04X" % (name, crc))
        if name in FRONT_TAGS:
            pal = open(os.path.join(PROJ, "assets", "bbdata", FRONT_FILES[name] + ".PALHW"), "rb").read()
            assert len(pal) == 16, name
            lines.append("static const u8 g_pal_%s[16] = {%s};" % (var, ",".join("0x%02X" % b for b in pal)))
        lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def gen_front_tables(chs_map):
    lines = ["#ifndef FRONT_TABLES_H", "#define FRONT_TABLES_H", '#include "fdc.h"', ""]
    for name in ("MUSBANK", "FSPLASH", "FSELECT", "FMAP"):
        if name not in chs_map:
            continue
        obytes, scount, chs, crc = chs_map[name]
        var = name.lower()
        lines.append("static const u8 g_%s_chs[%d] = {" % (var, len(chs)))
        for i in range(0, len(chs), 12):
            lines.append("    " + ",".join("0x%02X" % b for b in chs[i:i + 12]) + ",")
        lines.append("};")
        lines.append("static const DiskFileDesc g_file_%s = { %d, %d, g_%s_chs };" % (var, obytes, scount, var))
        lines.append("#define CRC_%s 0x%04X" % (name, crc))
        if name in FRONT_TAGS:
            pal = open(os.path.join(PROJ, "assets", "bbdata", FRONT_FILES[name] + ".PALHW"), "rb").read()
            assert len(pal) == 16, name
            lines.append("static const u8 g_pal_%s[16] = {%s};" % (var, ",".join("0x%02X" % b for b in pal)))
        lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def placeholder_header():
    lines = ["#ifndef DISK_TABLES_H", "#define DISK_TABLES_H", '#include "fdc.h"', ""]
    for name8, ext3, path in DATA_FILES:
        if name8 in GAME_TABLE_SKIP:
            lines.append("#define CRC_%s 0x0000" % name8)
            lines.append("")
            continue
        try:
            data_len = os.path.getsize(path)
        except OSError:
            data_len = 4096  # generat (BANK5.BIN): estimació, el real ve després
        scount = ((data_len + 128 + 1023) // 1024) * 2   # blocs AMSDOS d'1 KB -> 2 sectors
        var = name8.lower()
        lines.append("static const u8 g_%s_chs[%d] = { 0 };" % (var, scount * 3))
        lines.append("static const DiskFileDesc g_file_%s = { %d, %d, g_%s_chs };" % (var, data_len + 128, scount, var))
        lines.append("#define CRC_%s 0x0000" % name8)
        if name8 in FRONT_TAGS:
            lines.append("static const u8 g_pal_%s[16] = { 0 };" % var)
        lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def main():
    force = "-f" in sys.argv or "--force" in sys.argv
    os.makedirs(os.path.join(PROJ, "obj"), exist_ok=True)
    zx0_pack_all()  # F1-FRONT: pantalles .ZX0 a obj/ (FSELECT amb cua DANCE)
    hdr_path = os.path.join(PROJ, "src", "disk_tables.h")
    crt_path = os.path.join(PROJ, "src", "crt_addrs.h")
    stab_path = os.path.join(PROJ, "src", "starter_tables.h")
    fhdr_path = os.path.join(PROJ, "engine", "front_tables.h")
    # amb placeholders invalidaria mtime+hash i forzaria recompilar-ho TOT
    # amb SDCC (~15 min) a cada build encara que res hagi canviat.
    try:
        hdr_txt = open(hdr_path).read()
    except OSError:
        hdr_txt = ""
    # Placeholder si falta qualsevol fitxer de DATA_FILES (p.ex. ELWOOD nou):
    # compilar-hi a sobre petaria amb 'Undefined identifier' a la iteracio 1
    # (vist 14/10/26). Generic: no cal afegir un marcador per fitxer nou.
    if any((("g_file_%s" % name8.lower()) not in hdr_txt for name8, _, _ in DATA_FILES if name8 not in GAME_TABLE_SKIP)):
        open(hdr_path, "w").write(placeholder_header())
    if not os.path.exists(crt_path):
        open(crt_path, "w").write(crt_addrs_text(os.path.join(PROJ, "obj", PROGNAME + ".map")))
    # Llavor si falta o és d'una generació antiga (sense GAME_LEN/GAME_CRC/g_file_fdc):
    # compilar-hi a sobre petaria amb 'Undefined identifier'.
    try:
        stab_txt = open(stab_path).read()
    except OSError:
        stab_txt = ""
    if "GAME_CRC" not in stab_txt or "g_file_fdc" not in stab_txt or "g_file_front" not in stab_txt or "g_file_mus" not in stab_txt or "MUS_HOLD_ADDR" not in stab_txt:
        open(stab_path, "w").write(placeholder_starter_tables())
    # Llavor enemy_ext.s (EQU _s_hud_strips pel GAME): el real el genera
    # build_enemybank DESPRES del primer link; sense llavor l'enllac 1
    # petaria (mateix patro que placeholder_header). Adreca qualsevol a C2.
    ext_seed = os.path.join(PROJ, "obj", "enemy_ext.s")
    if not os.path.exists(ext_seed):
        open(ext_seed, "w").write("    .module enemy_ext\n"
                                  "    .globl _s_hud_strips\n_s_hud_strips = 0x6000\n")

    prev = None
    prev_crt = None
    prev_stab = None
    prev_fhdr = None
    # 8 iteracions (no 4): la cadena taules->recompila->CRC nou es pot
    # propagar 3-4 cops (vist 12/10/26: ZX0 mes grans + FSELECT/FMAP nous
    # mouen GAME 2 cops; amb 4 l'starter del DSK quedava amb CRC vell =
    # vermell a l'emu). Si no convergeix, FATAL (mai un DSK incoherent).
    for it in range(8):
        # Header changes from the generated CHS table are picked up through
        # newer(); avoid recompiling every assembly and C source on pass two.
        build_music(force)  # MUSICA primer (obj/mus_ext.s pel GAME)
        game_path, game_start, game_size = compile_and_link(force)
        build_bank(force, 0)  # Banc 5 per nivell
        build_bank(force, 1)
        build_bank(force, 2)
        build_levelcode(force, 0)  # Banc 1: codi del nivell (ascensors)
        build_levelcode(force, 1)  # Banc 1: codi del nivell (premses)
        # L3 no porta codi d'excepcions (has_code=False): estalvia ~1,1 KB al
        # paquet, que es l'únic que no hi cabia a l'scratch de 14.560 B.
        build_enemybank(force, 0)  # Banc C3 (walkers; reutilitza bank_equ.rel)
        build_enemybank(force, 1)
        build_enemybank(force, 2)
        build_level_bundles(force)  # JAKE / ELWOOD (Banc C7)
        build_level_packages(force)  # LnWORLD.PAK / LnENEMI + GAMEOVER (manifest)
        build_fdcbank(force)  # Banc FDC (fdc.rel/assets_fdc.rel ja compilats)
        build_front(force)  # FRONT banked (necessita el mapa resident)
        starter_path, starter_start = build_starter(force)
        chs_map, gentry, game_len, game_crc = package(starter_path, starter_start, game_path)
        text = gen_header(chs_map)
        fhdr_text = gen_front_tables(chs_map)
        crt_text = crt_addrs_text(os.path.join(PROJ, "obj", PROGNAME + ".map"))
        stab_text = gen_starter_tables(gentry, game_start, game_len, game_crc, chs_map["FDC"], chs_map["FRONT"], chs_map["MUSBANK"])
        changed = False
        # Els headers nous (CHS, CRC, adreces) es calculen ARA, pero no
        # s'escriuen encara: s'escriuen a l'inici de la iteracio
        # seguent, ABANS de compilar el resident. Si s'escriuen aqui, el
        # resident es queda amb el CRC vell i el DSK no arrenca (border
        # vermell): el CRC del PAK depen del layout del DSK, que depen de la
        # mida del resident, que depen del CRC... es circular, i perixo el
        # bucle: primer s'escriuen els headers, despres es compila el
        # resident, despres es construeix el DSK i es calcula el CRC nou.
        pending = ((text, hdr_path, "disk_tables.h", "prev"),
                   (fhdr_text, fhdr_path, "front_tables.h", "prev_fhdr"),
                   (crt_text, crt_path, "crt_addrs.h", "prev_crt"),
                   (stab_text, stab_path, "starter_tables.h", "prev_stab"))
        for cur, path, label, which in pending:
            disk = open(path).read() if os.path.exists(path) else None
            if disk != cur:
                open(path, "w").write(cur)
                print("  -> %s actualitzat (iteracio %d)" % (label, it + 1))
                changed = True
        if not changed:
            break
    else:
        print("\n[FATAL] 8 iteracions sense convergir: el DSK quedaria incoherent (starter ranci).")
        sys.exit(1)
    verify_starter_jump()
    # Fase 0.6 (PLA_NIVELLS_UNIVERSAL): verificacio del DSK. `--check` fa la
    # comprovacio rapida (catàleg + CRC de tots els fitxers, ~2 s);
    # `--check-boot` afegeix l'arrencada real a ZEsarUX (~1-2 min).
    if "--check" in sys.argv or "--check-boot" in sys.argv:
        smoke = os.path.join(HERE, "smoke_test.py")
        args = [sys.executable, smoke]
        if "--check-boot" not in sys.argv:
            args.append("--dsk-only")
        print("\n[CHECK] %s" % " ".join(args[1:]))
        if subprocess.call(args) != 0:
            print("\n[FATAL] El DSK no passa la verificacio (%s)." % smoke)
            sys.exit(1)
    print()


if __name__ == "__main__":
    main()