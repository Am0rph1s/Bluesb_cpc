#!/usr/bin/env python3
"""build_c6.py - Compila NOMES el banc C6 (enemics) i diu on acaba el codi.
Cicle rapid per ajustar la mida del codi sense fer el build sencer.

Us: py -3 tools/build_c6.py [nivell]   (nivell 0..5, per defecte 2 = L3)
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
SDCC = r"C:\Program Files\SDCC\bin\sdcc.exe"
SDAS = r"C:\Program Files\SDCC\bin\sdasz80.exe"
LEVEL = int(sys.argv[1]) if len(sys.argv) > 1 else 2
vdir = os.path.join(PROJ, "obj", "lvl%d" % LEVEL)
obj = os.path.join(PROJ, "obj")

# sincronitza src/enemy.c
src = open(os.path.join(PROJ, "src", "enemy.c"), "rb").read()
dst = os.path.join(vdir, "enemy.c")
if not os.path.exists(dst) or open(dst, "rb").read() != src:
    open(dst, "wb").write(src)

rel = os.path.join(vdir, "enemy.rel")
cmd = [SDCC, "-I" + vdir, "-I" + os.path.join(PROJ, "engine"),
       "-I" + os.path.join(PROJ, "src"), "-mz80", "--opt-code-size",
       "--max-allocs-per-node", "40000", "--disable-warning", "110",
       "-c", dst, "-o", rel]
r = subprocess.run(cmd)
if r.returncode:
    sys.exit(r.returncode)

ihx = os.path.join(obj, "enemybank_%d.ihx" % LEVEL)
r = subprocess.run([SDCC, "-mz80", "--no-std-crt0", "--code-loc", "0x5A00",
                    "--data-loc", "0x5800", os.path.join(obj, "enemy_table.rel"),
                    rel, os.path.join(obj, "bank_equ.rel"), "-o", ihx])
if r.returncode:
    sys.exit(r.returncode)

mp = os.path.join(obj, "enemybank_%d.map" % LEVEL)
lim = 0x7900
total = 0
for line in open(mp, encoding="latin1"):
    m = re.match(r"^_CODE\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})", line)
    if m:
        total = int(m.group(2), 16)
end = 0x5A00 + total
print("C6 _CODE: %d B   fi=0x%04X   limit=0x%04X   %s" % (
    total, end, lim, "OK (%d B lliures)" % (lim - end) if end <= lim else "EXCEDEIX %d B" % (end - lim)))
