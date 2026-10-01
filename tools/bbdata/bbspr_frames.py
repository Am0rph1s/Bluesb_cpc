#!/usr/bin/env python3
"""Genera src/player_frames.h amb els frames del Jake (sprite.sqv) per a l'animacio."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbspr  # noqa: E402

FRAMES = [0, 1, 2, 3, 7]  # 0..3 caminar/idle, 7 salt
OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "src", "player_frames.h")
SQV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "assets", "bbdata", "SPRITE.SQV")


def main():
    targets = [(0, 0, 0), (0, 0, 200), (230, 230, 0), (240, 240, 240)]
    arrs = []
    infos = []
    for f in FRAMES:
        w, h, wb, data = bbspr.convert(f, targets, SQV)
        name = "g_pf_%d" % f
        arrs.append((name, data))
        infos.append((name, wb, h))
        print("frame", f, "->", w, "x", h, "wb", wb, len(data), "bytes")

    lines = ["#ifndef PLAYER_FRAMES_H", "#define PLAYER_FRAMES_H", "", '#include "cpctelera.h"', ""]
    for name, data in arrs:
        lines.append("static const u8 %s[%d] = {" % (name, len(data)))
        for i in range(0, len(data), 12):
            lines.append("    " + ",".join("0x%02X" % b for b in data[i:i + 12]) + ",")
        lines.append("};")
        lines.append("")
    lines.append("typedef struct { const u8* data; u8 wb; u8 h; } PSprFrame;")
    lines.append("static const PSprFrame g_player_frames[%d] = {" % len(FRAMES))
    for name, wb, h in infos:
        lines.append("    { %s, %d, %d }," % (name, wb, h))
    lines.append("};")
    lines.append("")
    lines.append("// Sequencia de caminar (indexs dins g_player_frames: 0..3)")
    lines.append("static const u8 g_walk_seq[6] = { 2, 0, 1, 3, 0, 1 };")
    lines.append("")
    lines.append("#endif")
    open(OUT, "w").write("\n".join(lines) + "\n")
    print("escrit", OUT)


if __name__ == "__main__":
    main()
