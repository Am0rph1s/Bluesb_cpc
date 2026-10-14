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
import json
import hashlib
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from ihx2bin import convert_ihx          # noqa: E402
from dskutil import DskPatcher, create_empty_cpc_dsk, amsdos_header  # noqa: E402

SDCC    = r"C:\Program Files\SDCC\bin\sdcc.exe"
SDASZ80 = r"C:\Program Files\SDCC\bin\sdasz80.exe"

CFLAGS    = ["-mz80", "--opt-code-size", "--max-allocs-per-node", "15000",
             "--disable-warning", "110"]
LINKARGS  = ["-mz80", "--no-std-crt0", "-Wl-u",
             "--code-loc", "0x0100", "--data-loc", "0x3780", "-Wl-x"]
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
GAME_LINK_SKIP = {"engine/fdc.c", "engine/assets_fdc.s", "engine/zx0_decompress.s"}
C_HEADERS = {
    "engine/fdc.c": ["engine/fdc.h", "engine/cpctelera.h"],
    "src/render.c": ["engine/cpctelera.h", "engine/bank.h", "src/moving.h", "src/sprite.h", "src/hud_pkg.h"],
    "src/moving.c": ["engine/cpctelera.h", "engine/bank.h", "src/moving.h", "src/sprite.h", "engine/fdc.h"],
    "src/main.c": ["engine/cpctelera.h", "engine/fdc.h", "engine/front.h", "engine/mus.h", "src/disk_tables.h",
                   "src/sprite.h", "src/moving.h", "src/player_frames.h",
                   "engine/stack_canary.h", "src/crt_addrs.h", "src/level_pkg.h"],
}

PROGNAME = "bluesb"
DSKNAME8 = "BLUESB"

# --- Banc 5 (CP-2.2): lògica moving.* a 0x6E00; slots fixos 0x6E00+3k
# (han de coincidir amb engine/bank5_table.s; build_bank() ho verifica).
BANK5_BASE = 0x6E00
BANK5_MAXLEN = 0x1200   # finestra: CODE + pad zeros fins fi _DATA (0x7E07);
                        # el banc físic dona fins 0x7FFF, de sobres.
BANK_C_SOURCES = ["src/moving_bank.c"]
BANK_ASM_SOURCES = ["engine/bank5_table.s"]
BANK_C_HEADERS = {
    "src/moving_bank.c": ["engine/cpctelera.h", "engine/bank.h",
                          "src/moving.h", "src/sprite.h", "src/level_pkg.h"],
}

# FRONT banked (overlay d'arrencada C4:0x4000, descartable per TILESET).
# front.c (show/key/pal, nomes central/VRAM/PPI/GA) + front_table.s (slot JP)
# + front_ext.s (EQU externs centrals generat del mapa resident).
FRONT_BASE = 0x4000
# FRONT_DATA a 0x44C0 (era 0x4450): ballarins select F1 en C (~450 B:
# blitter+bg+anim+pols) no cabien en 1104 B de _CODE. C4:0x4300-0x4FFF
# lliure durant el FRONT (nomes hi viu FRONT.BIN; el TILESET el trepitja
# despres). Historial: 0x4200 -> 0x4300 (select L/R) -> 0x4450 -> 0x44C0.
FRONT_DATA = 0x44C0
FRONT_MAXLEN = 0x1000
FRONT_C_SOURCE = "engine/front.c"
FRONT_C_HEADERS = ["engine/cpctelera.h", "engine/fdc.h", "engine/front.h"]

# MUSICA (banc C1, AT3 AKG): player a MUS_PLAYER_BASE + canco a MUS_SONG_SLOT
# (les 4 fan 1.6-4.7 KB; player ~3.1 KB). MUSBANK.BIN = player + intro (el
# carrega l'starter); MUSMAIN.BIN = tema nivell 1 (el carrega el GAME).
MUS_BANK = 0xC1
MUS_PLAYER_BASE = 0x4000
MUS_SONG_SLOT = 0x5000
MUS_PLAYER_SRC = "tools/akg/PlayerAkg.asm"
MUS_INTRO_SRC = "assets/musica_cpc/The_Blues_Brothers_Intro_CPC.akg"
MUS_MAIN_SRC = "assets/musica_cpc/The_Blues_Brothers_CPC.akg"

# Fitxers de dades al DSK (es carregaran per FDC raw). Ordre = ordre al disc.
# (L'ordre de dades no afecta el boot; el BLUESB va primer via package().)
DATA_FILES = [
    # BANK5: codi moving.* generat per build (obj/) -> Banc 5 a 0x6E00.
    ("BANK5", "BIN", os.path.join(PROJ, "obj", "BANK5.BIN")),
    # FDC: motor FDC (fdc.c + assets_fdc.s) enllacat a 0x8000 (imatge) -> Banc 6
    # (dest C6:0x7000, dins la finestra bancable: alla hi es correcte).
    # El resident el copia a scratch central 0x8000 (VRAM pag.2, FORA de la
    # finestra 0x4000-0x7FFF: el motor pagina bancs i s'esborraria ell mateix
    # a 0x7000!) i l'executa alla (F1).
    ("FDC", "BIN", os.path.join(PROJ, "obj", "FDC.BIN")),
    # TITLE.BIN (Mode 1, 16 KB) NO va al DSK: cap codi el carrega (el FRONT
    # mostra SPLASH/SELECT/MAP). Quan fem el titol Mode 0 el re-afegirem
    # (junt amb g_file_title). Treure'l estalvia 107 B de taules al Bloc 0.
    # Mode 0: tileset 8x16 (64 B/tile, 256 tiles = 16 KB), mapa 128x72.
    ("TILES", "BIN", os.path.join(PROJ, "assets", "bbdata", "TILESET0.BIN")),
    ("MAP",   "BIN", os.path.join(PROJ, "assets", "bbdata", "MAP0.BIN")),
    ("TRIG",  "BIN", os.path.join(PROJ, "assets", "bbdata", "TRIG0.BIN")),
    ("PFRAMES", "BIN", os.path.join(PROJ, "assets", "bbdata", "PFRAMES.BIN")),
    # ELWOOD: frames d'Elwood mateix format (26x480 B) -> C7:0x4000 EN COMPTES
    # de PFRAMES si g_player_choice==1 (mateixos indexos: motor intacte).
    ("ELWOOD", "BIN", os.path.join(PROJ, "assets", "bbdata", "ELWOOD.BIN")),
    # EXTRA: DOS 39 (480 B) + BOX (128 B) + BALLOON (224 B) -> Banc 7 lliure 0x7AA0.
    ("EXTRA", "BIN", os.path.join(PROJ, "assets", "bbdata", "EXTRA.BIN")),
    # ELEV: 2 frames d'ascensor Mode 0 (2x224 B) -> Banc 7 lliure 0x78E0.
    ("ELEV", "BIN", os.path.join(PROJ, "assets", "bbdata", "ELEV.BIN")),
    # FRONT.BIN: overlay d'arrencada (front.c banked C4:0x4000) -> C4 (el
    # TILESET el sobreescriu quan acaba el FRONT). L'starter el carrega.
    ("FRONT", "BIN", os.path.join(PROJ, "obj", "FRONT.BIN")),
    # F1-FRONT: les 3 pantalles (el GAME les mostra via FRONT banked).
    ("FSPLASH", "ZX0", os.path.join(PROJ, "obj", "FSPLASH.ZX0")),
    ("FSELECT", "ZX0", os.path.join(PROJ, "obj", "FSELECT.ZX0")),
    ("FMAP", "ZX0", os.path.join(PROJ, "obj", "FMAP.ZX0")),
    # MUSICA: MUSBANK (player+intro, el FRONT el carrega a C1) + MUSMAIN
    # (el GAME el carrega a l'slot C1:0x5000). Mai des de l'starter (C1 mata
    # l'slot 3).
    ("MUSBANK", "BIN", os.path.join(PROJ, "obj", "MUSBANK.BIN")),
    ("MUSMAIN", "BIN", os.path.join(PROJ, "obj", "MUSMAIN.BIN")),
    # DANCE: NO es fitxer DSK (taules Bloc0 justes!): build_dance() l'AFEGEIX
    # a la cua de obj/FSELECT.ZX0 (el depack l'ignora: te fi explicita) i el
    # FRONT el llegeix de scratch+off (EQU front_ext, sense FDC ni mute).
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
    # DESPRÉS de compilar bé (abans, un kill a mig SDCC enverinava el
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
                for k in ("s__CODE", "l__CODE", "s__DATA", "l__DATA"):
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
    data_end = s_data + l_data
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
    if data_end > 0x3C00:
        print("\n[FATAL] _DATA ha trepitjat el canari de pila (data_end=0x%04X > 0x3C00)! Mou CANARY_ADDR." %
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
                  "_bc_push", "_bc_find", "_bc_init", "_bc_conveyor")
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


def build_bank(force):
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
    for rel_src in BANK_C_SOURCES:
        src = os.path.join(PROJ, rel_src)
        rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
        headers = [os.path.join(PROJ, name) for name in BANK_C_HEADERS[rel_src]]
        if force or is_stale(rel, [src] + headers):
            run([SDCC] + INCLUDES + CFLAGS + ["-c", src, "-o", rel])
            mark_fresh(rel, [src] + headers)
        bank_rels.append(rel)
    equ_s = os.path.join(obj, "bank_equ.s")
    equ_rel = os.path.join(obj, "bank_equ.rel")
    if force or is_stale(equ_rel, [equ_s]):
        run([SDASZ80, "-plosgff", equ_rel, equ_s])
        mark_fresh(equ_rel, [equ_s])
    bank_rels.append(equ_rel)
    ihx = os.path.join(PROJ, "bank5.ihx") if False else os.path.join(obj, "bank5.ihx")
    run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x%04X" % BANK5_BASE,
         "--data-loc", "0x7F80"] + bank_rels + ["-o", ihx])
    map_path = os.path.join(obj, "bank5.map")
    b5_code_s, b5_code_l = map_area(map_path, "CODE")
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
    bin_path = os.path.join(obj, "BANK5.BIN")
    convert_ihx(ihx, bin_path, start_addr=BANK5_BASE,
                max_length=image_length(map_path, BANK5_BASE))
    size = os.path.getsize(bin_path)
    if size > BANK5_MAXLEN:
        print("\n[FATAL] Banc 5: %d bytes > límit 0x%04X! Cal aprimar moving_bank.c." %
              (size, BANK5_MAXLEN))
        sys.exit(1)
    print("BANC5: 0x%04X (%d bytes, code=%d B, marge_code=%d B)" %
          (BANK5_BASE, size, b5_code_l, (b5_data_s or 0x7F80) - (BANK5_BASE + b5_code_l)))
    return bin_path


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
    need = {"_fdc_load_file": None, "_g_front_args": None,
            "_mus_play": None, "_mus_init": None, "_mus_stop": None,
            "_g_ticks": None, "_g_mus_hold": None,
            "_g_player_choice": None}
    for k in need:
        if k not in syms:
            print("\n[FATAL] FRONT: %s no es al mapa resident. Enllaca GAME primer?" % k)
            sys.exit(1)
        need[k] = syms[k]
    ext_s = os.path.join(obj, "front_ext.s")
    ext_txt = ("    .module front_ext\n" +
               "".join("    .globl %s\n%s = 0x%04X\n" % (k, k, v) for k, v in need.items()))
    # DANCE_OFF: offset de la cua DANCE dins FSELECT.ZX0 (= len - 1920).
    # Literal (no es simbol del mapa): el FRONT llegeix els frames de
    # scratch 0x8400+DANCE_OFF (el depack els ignora). S'exporta com a
    # ADRECA (array): `extern const u8 fselect_dance_base[]`.
    fsel_zx = os.path.join(obj, "FSELECT.ZX0")
    dance_base = 0x8400 + (os.path.getsize(fsel_zx) - DANCE_LEN) if os.path.exists(fsel_zx) else 0x8400
    ext_txt += "    .globl _fselect_dance_base\n_fselect_dance_base = 0x%04X\n" % dance_base
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
    f_code_s, f_code_l = map_area(map_path, "CODE")
    f_data_s, f_data_l = map_area(map_path, "DATA")
    if (f_code_s is not None and f_data_s is not None and
            (f_code_s + f_code_l) > f_data_s):
        print("\n[FATAL] FRONT _CODE envaeix _DATA! Mou --data-loc amunt.")
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
    for tag, src in (("intro", MUS_INTRO_SRC), ("main", MUS_MAIN_SRC)):
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
    # MUSBANK = player + pad fins slot + intro.
    mbin = os.path.join(obj, "MUSBANK.BIN")
    pdata = open(pbin, "rb").read()
    idata = open(songs["intro"][0], "rb").read()
    pad = MUS_SONG_SLOT - (MUS_PLAYER_BASE + len(pdata))
    assert pad >= 0
    open(mbin, "wb").write(pdata + bytes(pad) + idata)
    # MUSMAIN = tema sol (mateix slot).
    mainbin = os.path.join(obj, "MUSMAIN.BIN")
    mdata = open(songs["main"][0], "rb").read()
    open(mainbin, "wb").write(mdata)
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
          (len(pdata), len(idata), os.path.getsize(mbin), len(mdata),
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
    """Mini-DANCE per al select (F1): 4 frames de 480 B (parelles
    mascara/imatge, mateix format PFRAMES) = Jake dansa1/2 (PFRAMES[10,11],
    provats in-game) + Elwood dansa1/2 (ELWOOD[10,11]).
    S'AFEGEIX a la cua de obj/FSELECT.ZX0 dins zx0_pack_all (un sol
    escriptor; el depack ZX0 classic te fi explicita i els ignora). El
    FRONT els llegeix de scratch 0x8400+DANCE_OFF (EQU front_ext).
    Per que no fitxer DSK propi? Taules CHS+desc costen ~15 B de Bloc0 i
    forcen rewrite placeholder de TOTES les taules (+150 B transitori):
    a la cua son 0 B."""
    pf = os.path.join(PROJ, "assets", "bbdata", "PFRAMES.BIN")
    ew = os.path.join(PROJ, "assets", "bbdata", "ELWOOD.BIN")
    pfd = open(pf, "rb").read()
    ewd = open(ew, "rb").read()
    assert len(pfd) >= 5760 and len(ewd) >= 5760, (len(pfd), len(ewd))
    return pfd[4800:5760] + ewd[4800:5760]

DANCE_LEN = 1920


def zx0_pack_all():
    """Comprimeix les pantalles FRONT a obj/<TAG>.ZX0 (cache per mtime).
    FSELECT porta la cua DANCE (4 frames) a sobre: deps inclouen PFRAMES,
    ELWOOD i aquest fitxer."""
    from zx0pkg.zx0 import zx0_compress
    pf = os.path.join(PROJ, "assets", "bbdata", "PFRAMES.BIN")
    ew = os.path.join(PROJ, "assets", "bbdata", "ELWOOD.BIN")
    for tag, base in FRONT_SCREENS:
        src = os.path.join(PROJ, "assets", "bbdata", base + ".BIN")
        dst = os.path.join(PROJ, "obj", tag + ".ZX0")
        deps = [src] if tag != "FSELECT" else [src, pf, ew, __file__]
        if is_stale(dst, deps):
            data = open(src, "rb").read()
            out, stats = zx0_compress(bytes(data), classic=True, quick=ZX0_QUICK)
            out = bytes(out)
            if tag == "FSELECT":
                out = out + build_dance()
            open(dst, "wb").write(out)
            mark_fresh(dst, deps)
            print("ZX0: %s %d -> %d B (classic v1, %s)" %
                  (tag, len(data), len(out), "quick" if ZX0_QUICK else "optimal"))


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
    for name8, ext3, path in DATA_FILES:
        data = open(path, "rb").read()
        hdr = amsdos_header(name8, ext3, 0x02, 0x0000, 0x0000, len(data))
        blocs = dsk.add_file(name8, ext3, hdr + data)
        chs = []
        for b in blocs:
            for (t, sid) in dsk.bloc_to_ts(b):
                chs += [t, sid]  # parelles (track,sid): head sempre 0
        chs_map[name8] = (len(data) + 128, len(chs) // 2, chs, crc16_ccitt(data))
    dsk.save(dsk_path)
    print("DSK: %s  (RUN\"%s\" -> starter load 0x%04X/run 0x%04X, game=%d bytes)" %
          (dsk_path, DSKNAME8, ST_LOAD, ST_RUN, len(gdata)))
    return chs_map, gentry, len(gdata), crc16_ccitt(gdata)


def gen_header(chs_map):
    lines = ["#ifndef DISK_TABLES_H", "#define DISK_TABLES_H", '#include "fdc.h"', ""]
    for name, (obytes, scount, chs, crc) in chs_map.items():
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
    # amb placeholders invalidaria mtime+hash i forzaria recompilar-ho TOT
    # amb SDCC (~15 min) a cada build encara que res hagi canviat.
    try:
        hdr_txt = open(hdr_path).read()
    except OSError:
        hdr_txt = ""
    # Placeholder si falta qualsevol fitxer de DATA_FILES (p.ex. ELWOOD nou):
    # compilar-hi a sobre petaria amb 'Undefined identifier' a la iteracio 1
    # (vist 14/10/26). Generic: no cal afegir un marcador per fitxer nou.
    if any(("g_file_%s" % name8.lower()) not in hdr_txt for name8, _, _ in DATA_FILES):
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

    prev = None
    prev_crt = None
    prev_stab = None
    # 8 iteracions (no 4): la cadena taules->recompila->CRC nou es pot
    # propagar 3-4 cops (vist 12/10/26: ZX0 mes grans + FSELECT/FMAP nous
    # mouen GAME 2 cops; amb 4 l'starter del DSK quedava amb CRC vell =
    # vermell a l'emu). Si no convergeix, FATAL (mai un DSK incoherent).
    for it in range(8):
        # Header changes from the generated CHS table are picked up through
        # newer(); avoid recompiling every assembly and C source on pass two.
        build_music(force)  # MUSICA primer (obj/mus_ext.s pel GAME)
        game_path, game_start, game_size = compile_and_link(force)
        build_bank(force)  # Banc 5 (necessita el mapa resident per l'equ)
        build_fdcbank(force)  # Banc FDC (fdc.rel/assets_fdc.rel ja compilats)
        build_front(force)  # FRONT banked (necessita el mapa resident)
        starter_path, starter_start = build_starter(force)
        chs_map, gentry, game_len, game_crc = package(starter_path, starter_start, game_path)
        text = gen_header(chs_map)
        crt_text = crt_addrs_text(os.path.join(PROJ, "obj", PROGNAME + ".map"))
        stab_text = gen_starter_tables(gentry, game_start, game_len, game_crc, chs_map["FDC"], chs_map["FRONT"], chs_map["MUSBANK"])
        changed = False
        # Escriure NOMES si el contingut canvia (si no, el mtime nou
        # invalidaria hash/mtime i recompilaria dependents debades, i
        # amagaria la no-convergencia entre iteracions).
        for cur, old, path, label in ((text, prev, hdr_path, "disk_tables.h"),
                                      (crt_text, prev_crt, crt_path, "crt_addrs.h"),
                                      (stab_text, prev_stab, stab_path, "starter_tables.h")):
            if cur != old:
                try:
                    disk = open(path).read()
                except OSError:
                    disk = None
                if disk != cur:
                    open(path, "w").write(cur)
                    print("  -> %s actualitzat (iteracio %d)" % (label, it + 1))
                    changed = True
                if label == "disk_tables.h":
                    prev = cur
                elif label == "crt_addrs.h":
                    prev_crt = cur
                else:
                    prev_stab = cur
        if not changed:
            break
    else:
        print("\n[FATAL] 8 iteracions sense convergir: el DSK quedaria incoherent (starter ranci).")
        sys.exit(1)
    verify_starter_jump()
    print()


if __name__ == "__main__":
    main()
