#!/usr/bin/env python3
"""Convert the Magasin lift (ENEMI1.SQV frame 0) to CPC Mode 0.

NOTA (criteri Amiga): el DOS anima l'ascensor alternant dos frames
(l'ENEMI1.SQV 0 i 1: son la mateixa peça amb diferent fase de la banda
del motor, pen 11/pen 4). A la versio Amiga el grafic es identic pero
SENSE cap animacio. Aqui exportem NOMES el frame 0 (estalvia 224 B al
banc C0 i treu l'swap per frame de moving_bank.c). Es una desviacio
deliberada respecte al DOS, documentada a ESTAT.md.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_extra_frames import encode_pair, dos_to_cpc_pen  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.SQV")
OUT = os.path.join(PROJ, "src", "elevator_frames.h")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ELEV.BIN")


def convert_frame(frame):
    width, height, pixels = frame
    if width != 32 or height != 14:
        raise ValueError("Unexpected lift frame size: %dx%d" % (width, height))

    data = bytearray()
    for y in range(height):
        # Original 320-pixel art is halved horizontally for CPC Mode 0.
        row = pixels[y][0::2]
        for bx in range(8):
            left = row[bx * 2]
            right = row[bx * 2 + 1]
            # Només el pen 0 és transparent (com fa l'exportador d'enemics
            # per al mateix fitxer). El pen 11 és un color VISIBLE en aquest
            # sprite: marcar-lo transparent esborrava mitja banda del motor.
            pen_l = None if left == 0 else dos_to_cpc_pen.get(left, 0)
            pen_r = None if right == 0 else dos_to_cpc_pen.get(right, 0)
            inv_mask, image = encode_pair(pen_l, pen_r)
            data.extend((inv_mask, image))
    return bytes(data)


def main():
    frames = load_sqv_frames(SQV, reverse=False)
    converted = [convert_frame(frames[0])]          # criteri Amiga: 1 sol frame
    lines = [
        "#ifndef ELEVATOR_FRAMES_H",
        "#define ELEVATOR_FRAMES_H",
        "",
        '#include "cpctelera.h"',
        "",
        "#define ELEVATOR_SPR_W_BYTES 8",
        "#define ELEVATOR_SPR_H 14",
        "",
    ]
    for frame_no, data in enumerate(converted):
        lines.append("static const u8 g_elevator_frame_%d[%d] = {" %
                     (frame_no, len(data)))
        for i in range(0, len(data), 12):
            lines.append("    " + ",".join("0x%02X" % b
                                           for b in data[i:i + 12]) + ",")
        lines.extend(("};", ""))
    lines.extend(("#endif", ""))
    with open(OUT, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines))
    print("Generated %s" % OUT)

    raw_bin = converted[0]
    assert len(raw_bin) == 224
    with open(OUT_BIN, "wb") as f:
        f.write(raw_bin)
    print("Generated %s (%d bytes)" % (OUT_BIN, len(raw_bin)))


if __name__ == "__main__":
    main()
