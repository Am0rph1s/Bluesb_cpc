#!/usr/bin/env python3
"""
build.py - Build de Blues Brothers CPC amb SDCC 4.5 (natiu Windows).
Compila, enllaça, empaqueta el DSK (afegint els fitxers de dades PRIMER per
que les seves coordenades CHS no depenguin del tamany del codi) i genera
src/disk_tables.h amb les taules CHS per al carregador FDC raw.
"""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from ihx2bin import convert_ihx          # noqa: E402
from dskutil import DskPatcher, create_empty_cpc_dsk, amsdos_header  # noqa: E402

SDCC    = r"C:\Program Files\SDCC\bin\sdcc.exe"
SDASZ80 = r"C:\Program Files\SDCC\bin\sdasz80.exe"

CFLAGS    = ["-mz80", "--opt-code-size", "--max-allocs-per-node", "200000",
             "--disable-warning", "110"]
LINKARGS  = ["-mz80", "--no-std-crt0", "-Wl-u",
             "--code-loc", "0x0100", "--data-loc", "0x36A0", "-Wl-x"]
INCLUDES  = ["-I" + os.path.join(PROJ, "engine"),
             "-I" + os.path.join(PROJ, "src")]

ASM_SOURCES = [
    "engine/cpc_hardware.s",
    "engine/assets_fdc.s",
    "engine/audio.s",
    "engine/zx0_decompress.s",
    "engine/video.s",
    "engine/isr.s",
    "engine/sprite.s",
    "engine/moving_blit.s",
    "engine/tile_blit.s",
    "engine/sprite_hflip.s",
]
C_SOURCES = [
    "engine/fdc.c",
    "src/render.c",
    "src/moving.c",
    "src/main.c",
]
C_HEADERS = {
    "engine/fdc.c": ["engine/fdc.h", "engine/cpctelera.h"],
    "src/render.c": ["engine/cpctelera.h"],
    "src/moving.c": ["engine/cpctelera.h", "engine/bank.h", "src/moving.h", "src/sprite.h"],
    "src/main.c": ["engine/cpctelera.h", "engine/fdc.h", "src/disk_tables.h",
                   "src/sprite.h", "src/moving.h", "src/player_frames.h",
                   "engine/stack_canary.h"],
}

PROGNAME = "bluesb"
DSKNAME8 = "BLUESB"

# Fitxers de dades al DSK (es carregaran per FDC raw). Ordre = ordre al disc.
DATA_FILES = [
    # TITLE: el títol encara és Mode 1 (16 KB). Quan fem el títol Mode 0 el canviarem.
    ("TITLE", "BIN", os.path.join(PROJ, "assets", "bbdata", "TITLE.BIN")),
    # Mode 0: tileset 8x16 (64 B/tile, 256 tiles = 16 KB), mapa 128x72.
    ("TILES", "BIN", os.path.join(PROJ, "assets", "bbdata", "TILESET0.BIN")),
    ("MAP",   "BIN", os.path.join(PROJ, "assets", "bbdata", "MAP0.BIN")),
    ("TRIG",  "BIN", os.path.join(PROJ, "assets", "bbdata", "TRIG0.BIN")),
    ("PFRAMES", "BIN", os.path.join(PROJ, "assets", "bbdata", "PFRAMES.BIN")),
    # ELEV: 2 frames d'ascensor Mode 0 (2x224 B) -> Banc 7 lliure 0x78E0.
    ("ELEV", "BIN", os.path.join(PROJ, "assets", "bbdata", "ELEV.BIN")),
]


def run(cmd):
    print("+ " + " ".join(cmd))
    if subprocess.run(cmd).returncode != 0:
        print("ERROR: " + " ".join(cmd))
        sys.exit(1)


def newer(target, sources):
    if not os.path.exists(target):
        return True
    t = os.path.getmtime(target)
    return any(os.path.exists(s) and os.path.getmtime(s) > t for s in sources)


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
    if stack_margin < 256:
        print("\n[FATAL] Marge de pila insuficient (%d B < 256 B)! Risc immediat de crash." %
              stack_margin)
        sys.exit(1)
    if code_margin < 32:
        print("[AVIS] _CODE esta a punt de col-lidir amb _DATA! (nomes queden %d B)" % code_margin)
    if stack_margin < 1024:
        print("[AVIS] Marge de pila ajustat (%d B). Recomanat alliberar _DATA a bancs." % stack_margin)
    print()


def compile_and_link(force):
    obj = os.path.join(PROJ, "obj")
    objs = []
    for rel_src in ASM_SOURCES:
        src = os.path.join(PROJ, rel_src)
        rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
        if force or newer(rel, [src]):
            run([SDASZ80, "-plosgff", rel, src])
        objs.append(rel)
    for rel_src in C_SOURCES:
        src = os.path.join(PROJ, rel_src)
        rel = os.path.join(obj, os.path.splitext(os.path.basename(src))[0] + ".rel")
        headers = [os.path.join(PROJ, name) for name in C_HEADERS[rel_src]]
        if force or newer(rel, [src] + headers):
            run([SDCC] + INCLUDES + CFLAGS + ["-c", src, "-o", rel])
        objs.append(rel)
    ihx = os.path.join(obj, PROGNAME + ".ihx")
    run([SDCC] + LINKARGS + objs + ["-o", ihx])
    map_path = os.path.join(obj, PROGNAME + ".map")
    bin_path = os.path.join(obj, PROGNAME + ".bin")
    convert_ihx(ihx, bin_path, start_addr=0x0100, max_length=code_length(map_path))
    report_and_assert_memory_budget(map_path)
    return bin_path, find_start(map_path), os.path.getsize(bin_path)


def package(bin_path, exec_addr, code_size):
    dsk_path = os.path.join(PROJ, PROGNAME + ".dsk")
    create_empty_cpc_dsk(dsk_path, 40)
    dsk = DskPatcher(dsk_path)
    chs_map = {}
    for name8, ext3, path in DATA_FILES:
        data = open(path, "rb").read()
        hdr = amsdos_header(name8, ext3, 0x02, 0x0000, 0x0000, len(data))
        blocs = dsk.add_file(name8, ext3, hdr + data)
        chs = []
        for b in blocs:
            for (t, sid) in dsk.bloc_to_ts(b):
                chs += [t, 0, sid]
        chs_map[name8] = (len(data) + 128, len(chs) // 3, chs)
    with open(bin_path, "rb") as f:
        data = f.read()
    hdr = amsdos_header(DSKNAME8, "BIN", 0x02, 0x0100, exec_addr, len(data))
    dsk.add_file(DSKNAME8, "BIN", hdr + data)
    dsk.save(dsk_path)
    print("DSK: %s  (RUN\"%s\", exec=0x%04X, codi=%d bytes)" % (dsk_path, DSKNAME8, exec_addr, code_size))
    return chs_map


def gen_header(chs_map):
    lines = ["#ifndef DISK_TABLES_H", "#define DISK_TABLES_H", '#include "fdc.h"', ""]
    for name, (obytes, scount, chs) in chs_map.items():
        var = name.lower()
        lines.append("static const u8 g_%s_chs[%d] = {" % (var, len(chs)))
        for i in range(0, len(chs), 12):
            lines.append("    " + ",".join("0x%02X" % b for b in chs[i:i + 12]) + ",")
        lines.append("};")
        lines.append("static const DiskFileDesc g_file_%s = { %d, %d, g_%s_chs };" % (var, obytes, scount, var))
        lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def placeholder_header():
    lines = ["#ifndef DISK_TABLES_H", "#define DISK_TABLES_H", '#include "fdc.h"', ""]
    for name8, ext3, path in DATA_FILES:
        data_len = os.path.getsize(path)
        scount = ((data_len + 128 + 1023) // 1024) * 2   # blocs AMSDOS d'1 KB -> 2 sectors
        var = name8.lower()
        lines.append("static const u8 g_%s_chs[%d] = { 0 };" % (var, scount * 3))
        lines.append("static const DiskFileDesc g_file_%s = { %d, %d, g_%s_chs };" % (var, data_len + 128, scount, var))
        lines.append("")
    lines.append("#endif")
    return "\n".join(lines) + "\n"


def main():
    force = "-f" in sys.argv or "--force" in sys.argv
    os.makedirs(os.path.join(PROJ, "obj"), exist_ok=True)
    hdr_path = os.path.join(PROJ, "src", "disk_tables.h")
    open(hdr_path, "w").write(placeholder_header())   # placeholder amb tots els DATA_FILES

    prev = None
    for it in range(2):
        # Header changes from the generated CHS table are picked up through
        # newer(); avoid recompiling every assembly and C source on pass two.
        bin_path, exec_addr, code_size = compile_and_link(force)
        chs_map = package(bin_path, exec_addr, code_size)
        text = gen_header(chs_map)
        if text == prev:
            break
        prev = text
        open(hdr_path, "w").write(text)
        print("  -> disk_tables.h actualitzat (iteracio %d)" % (it + 1))


if __name__ == "__main__":
    main()
