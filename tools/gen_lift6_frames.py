#!/usr/bin/env python3
"""Convert the Concert stage lift (ENEMI6.SQV frame 14) to CPC Mode 0.

ENEMI6.SQV frame 14 is 32x14 DOS px -> 16x14 Mode 0 px (112 B).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_extra_frames import encode_pair, dos_to_cpc_pen  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI6.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "LIFT6.BIN")


def convert_frame(frame):
    width, height, pixels = frame
    if width != 32 or height != 14:
        raise ValueError("Unexpected lift frame size: %dx%d" % (width, height))

    data = bytearray()
    for y in range(height):
        row = pixels[y][0::2]
        for bx in range(8):
            left = row[bx * 2]
            right = row[bx * 2 + 1]
            pen_l = None if left == 0 else dos_to_cpc_pen.get(left, 0)
            pen_r = None if right == 0 else dos_to_cpc_pen.get(right, 0)
            inv_mask, image = encode_pair(pen_l, pen_r)
            data.extend((inv_mask, image))
    return bytes(data)


def main():
    frames = load_sqv_frames(SQV, reverse=False)
    # Frame 14 is the stage elevator
    bin_data = convert_frame(frames[14])
    assert len(bin_data) == 224, len(bin_data)
    with open(OUT_BIN, "wb") as f:
        f.write(bin_data)
    print("Exported %s (%d bytes)" % (OUT_BIN, len(bin_data)))


if __name__ == "__main__":
    main()
