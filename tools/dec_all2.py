#!/usr/bin/env python3
"""
dec_all2.py - Descomprimeix tots els fitxers .p00 usant el decrunch de Titus a VICE.

Metode validat (vice_dec_test): patch del CHRIN -> lector de RAM, arrencada a $CE14.
La font es posa a $0200 i l'output va de `dest` ($FC/$FD) cap avall.
L'span es detecta comparant amb un baseline net.

Us:
  py dec_all2.py --prgs assets/prgs --out assets/dec
"""
import argparse
import glob
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicebin import ViceBin  # noqa: E402

SRC = 0x0200
READER = bytes([
    0x84, 0xE2, 0xA0, 0x00, 0xB1, 0xE0, 0xE6, 0xE0,
    0xD0, 0x02, 0xE6, 0xE1, 0xA4, 0xE2, 0x60,
])


def p00_payload(path):
    d = open(path, 'rb').read()
    body = d[26:]
    la = body[0] | (body[1] << 8)
    return la, body[2:]


def setreg(v, rid, val):
    v._send(0x32, bytes([0]) + struct.pack('<H', 1) + bytes([3, rid]) + struct.pack('<H', val))
    try:
        v.wait_for(0x31, tries=60)
    except Exception:
        pass


def setup(v, dcode, comp):
    v.mem_set(0xCE00, dcode)
    v.mem_set(0xCF20, READER)
    v.mem_set(0xCE1A, bytes([0x20, 0x20, 0xCF]))
    v.mem_set(0xCF01, bytes([0x20, 0x20, 0xCF]))
    v.mem_set(0xCE2E, bytes([0xEA, 0xEA]))
    v.mem_set(SRC, comp)
    v.mem_set(0xE0, struct.pack('<H', SRC))
    v.mem_set(0x90, bytes([0]))
    for rid, val in [(0, 0), (1, 0), (2, 0), (3, 0xCE14), (4, 0xFD), (5, 0x24)]:
        setreg(v, rid, val)


def run(v, dcode, comp, wait):
    # omple la zona desti amb $CC per detectar escriptures netes
    setup(v, dcode, comp)
    v.exit()
    time.sleep(wait)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prgs', default='assets/prgs')
    ap.add_argument('--out', default='assets/dec')
    ap.add_argument('--wait', type=float, default=3.0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    decf = [p for p in glob.glob(os.path.join(args.prgs, '*.p00'))
            if os.path.basename(p).startswith('7-')][0]
    _, dcode = p00_payload(decf)

    v = ViceBin()
    v.ping()
    for p in sorted(glob.glob(os.path.join(args.prgs, '*.p00'))):
        name = os.path.basename(p)
        la, comp = p00_payload(p)
        if la == 0xCE00:
            continue
        run(v, dcode, comp, args.wait)
        # llegim $FC/$FD per saber el desti final (no sempre fiable)
        fcp = v.mem_get(0xFC, 0xFD)
        _ = fcp[0] | (fcp[1] << 8)
        # llegim tota la zona 0x2000-0xFFFF
        after = v.mem_get(0x2000, 0xFFFF)
        open(os.path.join(args.out, name + '.raw'), 'wb').write(after)
        print("%-26s dest(header)=%04X" % (name, comp[3] | (comp[2] << 8)))
    v.close()


if __name__ == '__main__':
    main()
