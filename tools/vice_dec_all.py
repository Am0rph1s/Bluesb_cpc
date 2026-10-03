#!/usr/bin/env python3
"""
vice_dec_all.py - Descomprimeix tots els fitxers .p00 del disc C64 usant el
decrunch original de Titus executat a VICE.

Metode:
  - Carrega el codi del decrunch a $CE00.
  - Patcha les crides CHRIN ($EE13) per un lector de RAM a $CF20 (punter $E0/$E1).
  - Patcha el bucle de banks i la sortida perque acabi net.
  - Posa breakpoint a la sortida ($CE30) i arrenca a $CE14.
  - Quan atura, captura la regio descomprimida.

Us:
  py vice_dec_all.py --prgs assets/prgs --out assets/dec [--port 6502]
"""
import argparse
import glob
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicebin import ViceBin  # noqa: E402

# Lector de RAM a $CF20. Llegeix ($E0),Y amb Y=0, incrementa $E0/$E1, i si el
# punter arriba al final ($E4/$E5) salta a $CFFF (bucle de fi detectable).
#   CF20: STY $E2 / LDY #0 / LDA ($E0),Y / INC $E0 / BNE / INC $E1
#         LDA $E0 / CMP $E4 / BNE cont / LDA $E1 / CMP $E5 / BNE cont
#         LDY $E2 / JMP $CFFF / cont: LDY $E2 / RTS
READER = bytes([
    0x84, 0xE2,              # STY $E2
    0xA0, 0x00,              # LDY #0
    0xB1, 0xE0,              # LDA ($E0),Y
    0xE6, 0xE0,              # INC $E0
    0xD0, 0x02,              # BNE +2
    0xE6, 0xE1,              # INC $E1
    0xA5, 0xE0,              # LDA $E0
    0xC5, 0xE4,              # CMP $E4
    0xD0, 0x0A,              # BNE cont (+10)
    0xA5, 0xE1,              # LDA $E1
    0xC5, 0xE5,              # CMP $E5
    0xD0, 0x04,              # BNE cont (+4)
    0xA4, 0xE2,              # LDY $E2
    0x4C, 0xFF, 0xCF,        # JMP $CFFF
    0xA4, 0xE2,              # cont: LDY $E2
    0x60,                    # RTS
])


def p00_payload(path):
    """Retorna (load_addr, dades) d'un .p00."""
    d = open(path, 'rb').read()
    body = d[26:]
    la = body[0] | (body[1] << 8)
    return la, body[2:]


def setup(v, dec_code, comp, src):
    v.mem_set(0xCE00, dec_code)
    v.mem_set(0xCF20, READER)
    v.mem_set(0xCE1A, bytes([0x20, 0x20, 0xCF]))
    v.mem_set(0xCF01, bytes([0x20, 0x20, 0xCF]))
    v.mem_set(0xCE2E, bytes([0xEA, 0xEA]))
    v.mem_set(0xCE30, bytes([0x4C, 0x30, 0xCE]))
    v.mem_set(src, comp)
    v.mem_set(0xE0, struct.pack('<H', src))
    # $E4/$E5 = punter de final de stream (src + len)
    v.mem_set(0xE4, struct.pack('<H', src + len(comp)))
    # bucle de fi a $CFFF
    v.mem_set(0xCFFF, bytes([0x4C, 0xFF, 0xCF]))
    v.mem_set(0x90, bytes([0]))
    # PC=$CE14, A=0 X=0 Y=0 SP=$FD
    for rid, val in [(0, 0), (1, 0), (2, 0), (3, 0xCE14), (4, 0xFD)]:
        body = bytes([0]) + struct.pack('<H', 1) + bytes([3, rid]) + struct.pack('<H', val)
        v._send(0x32, body)
        try:
            v.wait_for(0x31, tries=100)
        except Exception:
            pass


def run_once(dec_code, comp, src=0x0400, out_len=0xE000, timeout=8.0):
    v = ViceBin()
    v.ping()
    dest_lo, dest_hi = comp[3], comp[2]   # header: file[3]->$FC, file[2]->$FD
    dest = dest_lo | (dest_hi << 8)
    lo = 0
    base = v.mem_get(lo, 0xFFFE)
    setup(v, dec_code, comp, src)
    v.exit()
    # espera que el lector arribi al bucle de fi ($CFFF)
    hits = 0
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if v.regs().get(3, 0) == 0xCFFF:
                hits = 1
                break
        except Exception:
            pass
        time.sleep(0.02)
    # llegeix $FC/$FD (desti final = dest - out_len)
    fcp = v.mem_get(0xFC, 0xFD)
    final_dest = fcp[0] | (fcp[1] << 8)
    after = v.mem_get(lo, 0xFFFE)
    v.close()
    return dest, final_dest, bytes(base), bytes(after), hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prgs', default='assets/prgs')
    ap.add_argument('--out', default='assets/dec')
    ap.add_argument('--src', type=lambda s: int(s, 0), default=0x8000)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    decf = [p for p in glob.glob(os.path.join(args.prgs, '*.p00'))
            if os.path.basename(p).startswith('7-')][0]
    dec_la, dec_code = p00_payload(decf)
    print("decrunch: %s @ %04X (%d B)" % (os.path.basename(decf), dec_la, len(dec_code)))

    for p in sorted(glob.glob(os.path.join(args.prgs, '*.p00'))):
        name = os.path.basename(p)
        la, comp = p00_payload(p)
        if la == dec_la:
            continue
        try:
            dest, final_dest, base, after, hits = run_once(dec_code, comp, args.src)
        except Exception as ex:
            print("%-26s ERROR %s" % (name, ex))
            continue
        if hits and final_dest < dest:
            lo_out = final_dest + 1
            out_len = dest - lo_out + 1
            payload = bytes(after[lo_out:dest + 1])
            outname = os.path.join(args.out, name + '.dec')
            open(outname, 'wb').write(payload)
            nz = sum(1 for b in payload if b)
            print("%-26s dest=%04X out %04X-%04X (%d B, nz=%d) -> %s" % (
                name, dest, lo_out, dest, out_len, nz, os.path.basename(outname)))
        else:
            print("%-26s dest=%04X hits=%d final=%04X no acabat" % (
                name, dest, hits, final_dest))


if __name__ == '__main__':
    main()
