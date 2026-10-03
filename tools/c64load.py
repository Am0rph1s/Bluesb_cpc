#!/usr/bin/env python3
"""
c64load.py - Arrenca el joc a VICE, supera el cracktro i captura la RAM.

Pla:
  1. Connecta al binary monitor.
  2. Espera que el loader arribi a l'espera de foc ($1704-$170C) i injecta foc.
  3. Repeteix fins que el PC deixa d'estar en zones de loader conegudes.
  4. Quan el joc corre, dumpeja RAM completa + estat VIC.

Us:
  py c64load.py --dump out_prefix   # arrenca i captura
  py c64load.py --attach --dump ...  # nomes connecta a un VICE ja corrent
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicebin import ViceBin  # noqa: E402


# adreces d'espera del loader (bucle de joystick fire)
LOADER_WAIT = set(range(0x1704, 0x1719))


def press_fire(v, down=True):
    v._send(0xa2, struct.pack('<HH', 1, 0x0000 if down else 0xFFFF))
    try:
        v.wait_for(0xa2, tries=50)
    except Exception:
        pass


def vic_state(v):
    d018 = v.mem_get(0xd018, 0xd018)[0]
    d011 = v.mem_get(0xd011, 0xd011)[0]
    return d018, d011


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default=None, help='prefix de sortida')
    ap.add_argument('--attach', action='store_true')
    ap.add_argument('--max-seconds', type=int, default=180)
    ap.add_argument('--patched', action='store_true',
                    help='assumeix que ja esta patxejat (no injecta foc)')
    args = ap.parse_args()

    v = ViceBin()
    v.ping()
    start = time.time()
    seen = []
    captures = 0
    while time.time() - start < args.max_seconds:
        r = v.regs()
        pc = r.get(3, 0)
        if not seen or seen[-1] != pc:
            seen.append(pc)
            if len(seen) > 40:
                seen.pop(0)
        if pc in LOADER_WAIT:
            press_fire(v)
            press_fire(v, False)
            v.exit()
            time.sleep(0.3)
        else:
            v.exit()
            time.sleep(0.3)
        # cada ~5 s comprova estat VIC i captura si sembla joc
        captures += 1
        if captures % 10 == 0:
            d018, d011 = vic_state(v)
            print("PC=%04X D018=%02X D011=%02X" % (pc, d018, d011), flush=True)
    v.close()


if __name__ == '__main__':
    main()
