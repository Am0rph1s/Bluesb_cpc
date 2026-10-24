#!/usr/bin/env python3
"""Convert the Entrepôt hydraulic press (ENEMI2.SQV frame 33) to CPC Mode 0.

DOS frame 33 is 48x33 pixels.
Halved horizontally for Mode 0: 24 pixels wide (12 bytes) x 33 lines = 792 bytes (mask + data pairs = 24 bytes/row * 33 = 792 bytes).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_extra_frames import encode_pair, dos_to_cpc_pen  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI2.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "PRESS.BIN")


def convert_frame(frame):
    width, height, pixels = frame
    if width != 48 or height != 33:
        raise ValueError("Unexpected press frame size: %dx%d" % (width, height))

    data = bytearray()
    for y in range(height):
        # Original 320-pixel art is halved horizontally for CPC Mode 0.
        row = pixels[y][0::2]
        for bx in range(12):
            left = row[bx * 2]
            right = row[bx * 2 + 1]
            pen_l = None if left == 0 else dos_to_cpc_pen.get(left, 0)
            pen_r = None if right == 0 else dos_to_cpc_pen.get(right, 0)
            inv_mask, image = encode_pair(pen_l, pen_r)
            data.extend((inv_mask, image))
    return bytes(data)


def main():
    frames = load_sqv_frames(SQV, reverse=False)
    converted = convert_frame(frames[33])
    assert len(converted) == 792, len(converted)
    with open(OUT_BIN, "wb") as f:
        f.write(converted)
    print("Generated %s (%d bytes)" % (OUT_BIN, len(converted)))


if __name__ == "__main__":
    main()
