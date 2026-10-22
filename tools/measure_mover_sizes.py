#!/usr/bin/env python3
"""Mesura el tamany del prototip ASM del mover generic (Fase 4).

No toca el build del joc: assemblea engine/mover_gen.s i l'enllaca sol
a 0x6E00, amb els stubs de tile_type/tile_set que porta el mateix modul.

Us: py -3 tools/measure_mover_sizes.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build  # noqa: E402

obj = os.path.join(PROJ, "obj")
os.makedirs(obj, exist_ok=True)
rel = os.path.join(obj, "mover_gen_measure.rel")
ihx = os.path.join(obj, "mover_gen_measure.ihx")
mp = os.path.join(obj, "mover_gen_measure.map")
src = os.path.join(PROJ, "engine", "mover_gen.s")

subprocess.check_call([build.SDASZ80, "-plosgff", rel, src])
subprocess.check_call([build.SDCC, "-mz80", "--no-std-crt0",
                       "--code-loc", "0x6E00", "--data-loc", "0x7F80",
                       rel, "-o", ihx])
cs, cl = build.map_area(mp, "CODE")
ds, dl = build.map_area(mp, "DATA")
print("mover_gen: CODE=%d B  DATA=%d B  total=%d B" % (cl, dl, cl + dl))
for line in open(mp, encoding="latin1"):
    p = line.split()
    if len(p) >= 2 and p[1].startswith("_mover_gen"):
        print("  %s %s" % (p[0], p[1]))
