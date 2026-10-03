#!/usr/bin/env python3
"""
scan_ports.py - Escaneja un binari buscant accessos als ports del CPC:
  CRTC  0xBC00 (select) / 0xBD00 (write)   -> scroll (R12/R13), R3 (fine)
  Gate Array 0x7F00 / 0x7F10 / 0x7Fxx      -> mode, paleta, RAM banking
Reporta offset i context, i desassembla al voltant.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from z80 import disasm   # noqa: E402


PATTERNS = [
    ('LD BC,0xBC00', bytes.fromhex('0100bc')),
    ('LD BC,0xBD00', bytes.fromhex('0100bd')),
    ('LD BC,0x7F00', bytes.fromhex('01007f')),
    ('LD BC,0x7F10', bytes.fromhex('01107f')),
    ('OUT (n),A=BC', bytes.fromhex('d3bc')),
    ('OUT (n),A=BD', bytes.fromhex('d3bd')),
    ('OUT (n),A=7F', bytes.fromhex('d37f')),
    ('OUT (C),A ED79', bytes.fromhex('ed79')),
    ('OUT (C),C ED49', bytes.fromhex('ed49')),
    ('IN A,(n)=BC', bytes.fromhex('dbbc')),
    ('IN A,(C) ED78', bytes.fromhex('ed78')),
]


def scan(data, base, name):
    print("=== %s (%d B, base 0x%04X) ===" % (name, len(data), base))
    for label, pat in PATTERNS:
        offs = []
        i = data.find(pat)
        while i >= 0:
            offs.append(i)
            i = data.find(pat, i + 1)
        if offs:
            print("  %-16s @ %s" % (label, ', '.join('0x%04X' % (base + o) for o in offs[:16])))


def dump_around(data, base, addr, before=8, after=24):
    off = addr - base
    start = max(0, off - before)
    lines, _ = disasm(data[start:off + after], base + start)
    for a, t, r in lines:
        mark = ' <==' if a == addr else ''
        print('  %04X: %-24s%s' % (a, t, mark))


if __name__ == '__main__':
    files = sys.argv[1:]
    listing = []
    for f in files:
        d = open(f, 'rb').read()
        off = 128 if (len(d) > 128 and d[0] == 0 and d[1:4].isalpha()) else 0
        body = d[off:]
        scan(body, 0, os.path.basename(f))
