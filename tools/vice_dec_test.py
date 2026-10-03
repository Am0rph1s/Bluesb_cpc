#!/usr/bin/env python3
"""
vice_dec_test.py - Executa el decrunch de Titus a VICE amb un lector de RAM propi.

Patcha el decrunch perque en lloc de CHRIN($EE13) llegeixi d'un buffer a RAM amb
un punter que avanca. Aixi podem alimentar el fitxer comprimit i capturar la
sortida real que genera el codi original.

Us:
  py vice_dec_test.py <decrunch.bin> <compressed.bin> --out prefix
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicebin import ViceBin  # noqa: E402


# lector de RAM a $CF20:  LDA ($E0),Y amb Y=0, incrementa $E0/$E1, preserva Y
READER = bytes([
    0x84, 0xE2,        # STY $E2
    0xA0, 0x00,        # LDY #0
    0xB1, 0xE0,        # LDA ($E0),Y
    0xE6, 0xE0,        # INC $E0
    0xD0, 0x02,        # BNE +2
    0xE6, 0xE1,        # INC $E1
    0xA4, 0xE2,        # LDY $E2
    0x60,              # RTS
])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('decrunch')
    ap.add_argument('compressed')
    ap.add_argument('--out', default='vice_dec_out.bin')
    ap.add_argument('--src', type=lambda s: int(s, 0), default=0x0200)
    args = ap.parse_args()

    dec = open(args.decrunch, 'rb').read()
    comp = open(args.compressed, 'rb').read()

    v = ViceBin()
    v.ping()
    # carrega el decrunch a $CE00
    v.mem_set(0xCE00, dec)
    # lector a $CF20
    v.mem_set(0xCF20, READER)
    # patxeja les dues crides CHRIN ($CE1A i $CF01) -> JSR $CF20
    v.mem_set(0xCE1A, bytes([0x20, 0x20, 0xCF]))
    v.mem_set(0xCF01, bytes([0x20, 0x20, 0xCF]))
    # patxeja el bucle extern: $CE2E BNE $CE18 -> NOP NOP
    v.mem_set(0xCE2E, bytes([0xEA, 0xEA]))
    # patxeja la sortida $CE30 (JSR $F32F) -> JMP $CE30 (bucle fi, atura'ns)
    v.mem_set(0xCE30, bytes([0x4C, 0x30, 0xCE]))
    # fitxer comprimit a l'adreca font
    v.mem_set(args.src, comp)
    # zp: $E0/$E1 = punter font
    v.mem_set(0xE0, struct.pack('<H', args.src))
    # $90 = 0 (perque no salti el decrunch)
    v.mem_set(0x90, bytes([0]))
    # registres: arrenca a $CE14 (LDY #0; STY $90; ...)  amb Y=0
    # set registers: A=0 X=0 Y=0 SP=$FD, PC=$CE14
    # Registers set (0x32): MS | RC(2) | [IS RI RV]...
    def setreg(rid, val):
        # MS | RC(2) | IS RI RV(2)
        body = bytes([0]) + struct.pack('<H', 1) + bytes([3, rid]) + struct.pack('<H', val)
        v._send(0x32, body)
        try:
            v.wait_for(0x31, tries=100)
        except Exception:
            pass
    setreg(0, 0)      # A
    setreg(1, 0)      # X
    setreg(2, 0)      # Y
    setreg(3, 0xCE14)  # PC
    setreg(4, 0xFD)   # SP
    print("setup fet, executant...")
    # deixa correr 3 segons
    v.exit()
    time.sleep(3.0)
    # captura: mira que $CE14 existeix i finalitza? Capturem RAM
    full = bytearray()
    for s in range(0, 0x10000, 0x1000):
        full += v.mem_get(s, s + 0xfff)
    open(args.out, 'wb').write(bytes(full))
    print("RAM desada a", args.out)
    pc = v.regs().get(3, 0)
    print("PC final=%04X" % pc)
    # mira si $FC/$FD i quant ha avançat el punter
    fc = struct.unpack('<H', full[0xFC:0xFE])[0]
    srcp = struct.unpack('<H', full[0xE0:0xE2])[0]
    print("dest(FC/FD)=%04X  src llegeix fins=%04X (inici %04X, %d bytes)" % (
        fc, srcp, args.src, srcp - args.src))
    v.close()


if __name__ == '__main__':
    main()
