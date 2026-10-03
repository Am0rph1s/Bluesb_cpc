#!/usr/bin/env python3
"""
run_dec.py - Executa el decrunch de Titus (07_7) sobre un fitxer del disc
i captura el resultat descomprimit.

El decrunch es carregat a $CE00. Normalment llegeix d'un canal de disc obert
via CHRIN ($EE13). Aqui interceptem les crides KERNAL i subministrem els bytes
del fitxer comprimit.

Us:
  py run_dec.py <fitxer_comprimit> [-o out.bin]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpu6502 import CPU6502  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEC = os.path.join(HERE, '..', 'assets', 'c64rip', '07_7.prg')


# vectors/rutines KERNAL que se substitueixen per no-ops o serveis
NOOP = {0xFFBA, 0xF3D5, 0xED09, 0xEDC7, 0xF32F}


class Harness:
    def __init__(self, comp):
        self.comp = comp
        self.pos = 0
        self.out_log = []
        m = CPU6502()
        self.m = m
        code = open(DEC, 'rb').read()[2:]   # treu load addr
        m.load(0xCE00, code)
        # stack inicial
        m.sp = 0xFD
        # hooks
        for a in NOOP:
            m.hooks[a] = self._ret
        m.hooks[0xEE13] = self._chrin
        m.hooks[0xF642] = self._halt
        # sortida del bucle de blocs: despres del primer decrunch
        m.hooks[0xCE2C] = self._halt
        # registres inicials com el loader original: A=8,X=8,Y=8 abans de SETLFS
        m.a = 8
        m.x = 8
        m.y = 8
        m.pc = 0xCE00
        # level de "JSK" - simulem que $CE04 es cridat; millor comencar al CE00
        self.wrote_lo = None
        self.wrote_hi = None

    def _ret(self, m=None):
        # simula RTS: treu return addr de la pila i salta
        m = self.m
        lo = m.pull(); hi = m.pull()
        m.pc = ((hi << 8) | lo) + 1
        return 'skip'

    def _halt(self, m=None):
        self.m.halted = True
        return 'halt'

    def _chrin(self, m=None):
        m = self.m
        if self.pos < len(self.comp):
            v = self.comp[self.pos]; self.pos += 1
        else:
            v = 0
        m.a = v
        m.set_nz(v)
        # simula RTS
        lo = m.pull(); hi = m.pull()
        m.pc = ((hi << 8) | lo) + 1
        return 'skip'

    def run(self, max_instr=5000000):
        # per comencar correctament, simulem una crida JSR $CE00:
        # posem a la pila l'adreca de retorn ficticia
        self.m.push(0xFF)  # hi
        self.m.push(0xFF)  # lo -> retorna a $0100
        self.m.pc = 0xCE00
        n = 0
        while not self.m.halted and n < max_instr:
            self.m.step()
            n += 1
            if self.m.pc == 0x0100:
                break
        return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('-o', '--output', default='dec_out.bin')
    ap.add_argument('--skip', type=int, default=2,
                    help='bytes a saltar del fitxer (load addr)')
    args = ap.parse_args()
    comp = open(args.input, 'rb').read()[args.skip:]
    h = Harness(comp)
    n = h.run()
    m = h.m
    print("instruccions:", n, "PC=%04X halt=%s" % (m.pc, m.halted))
    print("bytes llegits del fitxer:", h.pos, "de", len(comp))
    # el desti es troba a l'stack/fc
    print("A=%02X X=%02X Y=%02X SP=%02X" % (m.a, m.x, m.y, m.sp))
    # desa tota la RAM per inspeccio
    open(args.output, 'wb').write(bytes(m.mem))
    print("RAM desada a", args.output)


if __name__ == '__main__':
    main()
