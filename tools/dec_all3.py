#!/usr/bin/env python3
"""
dec_all3.py - Descomprimeix tots els fitxers .p00 del disc C64 usant el decrunch
original de Titus a VICE (metode validat i robust).

Metode:
  - Patcha el decrunch perque llegeixi d'un buffer de RAM (lector a $CF20).
  - Executa el decrunch DUES vegades, amb la regio de desti inicialitzada
    amb $00 i amb $FF.
  - Els bytes que coincideixen en les dues execucions son output real
    (independents de l'estat inicial de la RAM).
  - L'span es detecta des de `dest` ($FC/$FD del header) cap avall, mentre
    els bytes son estables.

Us:
  py dec_all3.py --prgs assets/prgs --out assets/dec
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
        v._send(0x32, bytes([0]) + struct.pack('<H', 1) + bytes([3, rid]) +
                struct.pack('<H', val))
        try:
            v.wait_for(0x31, tries=60)
        except Exception:
            pass


def run(v, dcode, comp, fill, wait):
    v.mem_set(0x2000, bytes([fill]) * 0xC000)
    setup(v, dcode, comp)
    v.exit()
    time.sleep(wait)
    return v.mem_get(0x2000, 0xFFFE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prgs', default='assets/prgs')
    ap.add_argument('--out', default='assets/dec')
    ap.add_argument('--wait', type=float, default=2.5)
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
        dest = comp[3] | (comp[2] << 8)
        a = run(v, dcode, comp, 0x00, args.wait)
        b = run(v, dcode, comp, 0xFF, args.wait)
        # span: des de dest cap avall mentre els bytes son estables
        lo = dest
        while lo > 0x2000 and a[lo - 0x2000] == b[lo - 0x2000]:
            lo -= 1
        lo += 1
        payload = bytes(a[lo - 0x2000:dest - 0x2000 + 1])
        nz = sum(1 for x in payload if x)
        outname = os.path.join(args.out, name + '.dec')
        open(outname, 'wb').write(payload)
        print("%-26s dest=%04X out %04X-%04X (%d B, nz=%d)" % (
            name, dest, lo, dest, len(payload), nz))
    v.close()


if __name__ == '__main__':
    main()
