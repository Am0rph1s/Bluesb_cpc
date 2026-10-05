#!/usr/bin/env python3
"""Convert the Magasin lift animation (ENEMI1.SQV frames 0/1) to CPC Mode 0."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from mode0 import encode_mode0_byte  # noqa: E402
from sprites import load_sqv_frames  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.SQV")
OUT = os.path.join(PROJ, "src", "elevator_frames.h")


def convert_frame(frame):
    width, height, pixels = frame
    if width != 32 or height != 14:
        raise ValueError("Unexpected lift frame size: %dx%d" % (width, height))

    data = []
    for y in range(height):
        # Original 320-pixel art is halved horizontally for CPC Mode 0.
        row = pixels[y][0::2]
        for bx in range(8):
            left, right = row[bx * 2:bx * 2 + 2]
            inv_mask = encode_mode0_byte(15 if left == 0 else 0,
                                         15 if right == 0 else 0)
            image = encode_mode0_byte(left if left else 0,
                                      right if right else 0)
            data.extend((inv_mask, image & (~inv_mask & 0xFF)))
    return data


def main():
    frames = load_sqv_frames(SQV, reverse=False)
    converted = [convert_frame(frames[i]) for i in (0, 1)]
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


if __name__ == "__main__":
    main()
