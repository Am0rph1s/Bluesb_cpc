#!/usr/bin/env python3
"""
c64scan.py - Escaneja un fitxer buscant regions de dades "grafiques".

Calcula, per cada bloc de 256 bytes, l'entropia i la proporcio de bytes unics,
i marca el bloc com a grafics si es poc divers (repeticions, valors alts).
Tambe intenta detectar bitmaps C64 valids buscant un screen de 1000 bytes
(40x25, pocs valors repetits) seguits de 8000 bytes de bitmap.
"""
import argparse
import math
import os
import sys
from collections import Counter


def entropy(b):
    if not b:
        return 0.0
    c = Counter(b)
    n = len(b)
    e = 0.0
    for v in c.values():
        p = v / n
        e -= p * math.log2(p)
    return e


def scan_entropy(data, block=256):
    print("%-8s %-8s %-7s %s" % ("OFF", "OFFSET", "ENTROP", "NOTES"))
    for off in range(0, len(data) - block + 1, block):
        b = data[off:off + block]
        e = entropy(b)
        note = ""
        if e < 5.5:
            note = "BAIXA (posibles grafics)"
        print("%-8d 0x%06X %-7.3f %s" % (off, off, e, note))


def find_bitmaps(data):
    """Cerca screen+bitmap plausibles. El screen ha de tenir valors amb
    nibbles <= 0x0F i repeticions verticals."""
    print("\n--- Candidats bitmap (screen 1000B + bitmap 8000B) ---")
    n = len(data)
    for off in range(0, n - 9000, 2):
        screen = data[off:off + 1000]
        # tots els nibbles valids
        hi_ok = all((x >> 4) <= 0x0F for x in screen)
        picks = sum(1 for x in screen if x not in (0,))
        # estructura: poc canvi entre cellules verticals (indexs repetits)
        uniq = len(set(screen))
        if picks > 900 and uniq < 200:
            bmp = data[off + 1000:off + 9000]
            be = entropy(bmp)
            se = entropy(screen)
            print("off=0x%06X screen_e=%.2f bmp_e=%.2f uniq=%d" % (off, se, be, uniq))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--entropy', action='store_true')
    ap.add_argument('--bitmaps', action='store_true')
    ap.add_argument('--block', type=int, default=256)
    args = ap.parse_args()
    data = open(args.file, 'rb').read()
    print("Fitxer %s (%d bytes)" % (os.path.basename(args.file), len(data)))
    if args.entropy or (not args.bitmaps):
        scan_entropy(data, args.block)
    if args.bitmaps:
        find_bitmaps(data)


if __name__ == '__main__':
    main()
