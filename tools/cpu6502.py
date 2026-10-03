#!/usr/bin/env python3
"""
cpu6502.py - Emulador i desassemblador 6502 en Python.

Emulador:
    m = CPU6502()
    m.load(addr, data)
    m.hooks[0xFFD2] = lambda m: ...   # intercepta JSR a adreca
    m.pc = 0x0801
    m.run(max_instr=...)

Desassemblador:
    for addr, text in dasm(data, base, count):
        print("%04X: %s" % (addr, text))
"""

# --- taules d'opcodes (mides i noms) ---
# mode: imp, acc, imm, zp, zpx, zpy, abs, absx, absy, ind, indx, indy, rel
OPCODES = {
    0x00: ('BRK', 'imp'), 0x01: ('ORA', 'indx'), 0x05: ('ORA', 'zp'),
    0x06: ('ASL', 'zp'), 0x08: ('PHP', 'imp'), 0x09: ('ORA', 'imm'),
    0x0A: ('ASL', 'acc'), 0x0D: ('ORA', 'abs'), 0x0E: ('ASL', 'abs'),
    0x10: ('BPL', 'rel'), 0x11: ('ORA', 'indy'), 0x15: ('ORA', 'zpx'),
    0x16: ('ASL', 'zpx'), 0x18: ('CLC', 'imp'), 0x19: ('ORA', 'absy'),
    0x1D: ('ORA', 'absx'), 0x1E: ('ASL', 'absx'),
    0x20: ('JSR', 'abs'), 0x21: ('AND', 'indx'), 0x24: ('BIT', 'zp'),
    0x25: ('AND', 'zp'), 0x26: ('ROL', 'zp'), 0x28: ('PLP', 'imp'),
    0x29: ('AND', 'imm'), 0x2A: ('ROL', 'acc'), 0x2C: ('BIT', 'abs'),
    0x2D: ('AND', 'abs'), 0x2E: ('ROL', 'abs'),
    0x30: ('BMI', 'rel'), 0x31: ('AND', 'indy'), 0x35: ('AND', 'zpx'),
    0x36: ('ROL', 'zpx'), 0x38: ('SEC', 'imp'), 0x39: ('AND', 'absy'),
    0x3D: ('AND', 'absx'), 0x3E: ('ROL', 'absx'),
    0x40: ('RTI', 'imp'), 0x41: ('EOR', 'indx'), 0x45: ('EOR', 'zp'),
    0x46: ('LSR', 'zp'), 0x48: ('PHA', 'imp'), 0x49: ('EOR', 'imm'),
    0x4A: ('LSR', 'acc'), 0x4C: ('JMP', 'abs'), 0x4D: ('EOR', 'abs'),
    0x4E: ('LSR', 'abs'),
    0x50: ('BVC', 'rel'), 0x51: ('EOR', 'indy'), 0x55: ('EOR', 'zpx'),
    0x56: ('LSR', 'zpx'), 0x58: ('CLI', 'imp'), 0x59: ('EOR', 'absy'),
    0x5D: ('EOR', 'absx'), 0x5E: ('LSR', 'absx'),
    0x60: ('RTS', 'imp'), 0x61: ('ADC', 'indx'), 0x65: ('ADC', 'zp'),
    0x66: ('ROR', 'zp'), 0x68: ('PLA', 'imp'), 0x69: ('ADC', 'imm'),
    0x6A: ('ROR', 'acc'), 0x6C: ('JMP', 'ind'), 0x6D: ('ADC', 'abs'),
    0x6E: ('ROR', 'abs'),
    0x70: ('BVS', 'rel'), 0x71: ('ADC', 'indy'), 0x75: ('ADC', 'zpx'),
    0x76: ('ROR', 'zpx'), 0x78: ('SEI', 'imp'), 0x79: ('ADC', 'absy'),
    0x7D: ('ADC', 'absx'), 0x7E: ('ROR', 'absx'),
    0x81: ('STA', 'indx'), 0x84: ('STY', 'zp'), 0x85: ('STA', 'zp'),
    0x86: ('STX', 'zp'), 0x88: ('DEY', 'imp'), 0x8A: ('TXA', 'imp'),
    0x8C: ('STY', 'abs'), 0x8D: ('STA', 'abs'), 0x8E: ('STX', 'abs'),
    0x90: ('BCC', 'rel'), 0x91: ('STA', 'indy'), 0x94: ('STY', 'zpx'),
    0x95: ('STA', 'zpx'), 0x96: ('STX', 'zpy'), 0x98: ('TYA', 'imp'),
    0x99: ('STA', 'absy'), 0x9A: ('TXS', 'imp'), 0x9D: ('STA', 'absx'),
    0xA0: ('LDY', 'imm'), 0xA1: ('LDA', 'indx'), 0xA2: ('LDX', 'imm'),
    0xA4: ('LDY', 'zp'), 0xA5: ('LDA', 'zp'), 0xA6: ('LDX', 'zp'),
    0xA8: ('TAY', 'imp'), 0xA9: ('LDA', 'imm'), 0xAA: ('TAX', 'imp'),
    0xAC: ('LDY', 'abs'), 0xAD: ('LDA', 'abs'), 0xAE: ('LDX', 'abs'),
    0xB0: ('BCS', 'rel'), 0xB1: ('LDA', 'indy'), 0xB4: ('LDY', 'zpx'),
    0xB5: ('LDA', 'zpx'), 0xB6: ('LDX', 'zpy'), 0xB8: ('CLV', 'imp'),
    0xB9: ('LDA', 'absy'), 0xBA: ('TSX', 'imp'), 0xBC: ('LDY', 'absx'),
    0xBD: ('LDA', 'absx'), 0xBE: ('LDX', 'absy'),
    0xC0: ('CPY', 'imm'), 0xC1: ('CMP', 'indx'), 0xC4: ('CPY', 'zp'),
    0xC5: ('CMP', 'zp'), 0xC6: ('DEC', 'zp'), 0xC8: ('INY', 'imp'),
    0xC9: ('CMP', 'imm'), 0xCA: ('DEX', 'imp'), 0xCC: ('CPY', 'abs'),
    0xCD: ('CMP', 'abs'), 0xCE: ('DEC', 'abs'),
    0xD0: ('BNE', 'rel'), 0xD1: ('CMP', 'indy'), 0xD5: ('CMP', 'zpx'),
    0xD6: ('DEC', 'zpx'), 0xD8: ('CLD', 'imp'), 0xD9: ('CMP', 'absy'),
    0xDD: ('CMP', 'absx'), 0xDE: ('DEC', 'absx'),
    0xE0: ('CPX', 'imm'), 0xE1: ('SBC', 'indx'), 0xE4: ('CPX', 'zp'),
    0xE5: ('SBC', 'zp'), 0xE6: ('INC', 'zp'), 0xE8: ('INX', 'imp'),
    0xE9: ('SBC', 'imm'), 0xEA: ('NOP', 'imp'), 0xEC: ('CPX', 'abs'),
    0xED: ('SBC', 'abs'), 0xEE: ('INC', 'abs'),
    0xF0: ('BEQ', 'rel'), 0xF1: ('SBC', 'indy'), 0xF5: ('SBC', 'zpx'),
    0xF6: ('INC', 'zpx'), 0xF8: ('SED', 'imp'), 0xF9: ('SBC', 'absy'),
    0xFD: ('SBC', 'absx'), 0xFE: ('INC', 'absx'),
}

MODE_LEN = {'imp': 1, 'acc': 1, 'imm': 2, 'zp': 2, 'zpx': 2, 'zpy': 2,
            'abs': 3, 'absx': 3, 'absy': 3, 'ind': 3, 'indx': 2,
            'indy': 2, 'rel': 2}


def dasm_one(data, addr):
    op = data[addr]
    if op not in OPCODES:
        return '??? (%02X)' % op, 1
    name, mode = OPCODES[op]
    ln = MODE_LEN[mode]
    if mode in ('imp', 'acc'):
        return name + (' A' if mode == 'acc' else ''), 1
    if mode == 'imm':
        return '%s #$%02X' % (name, data[addr + 1]), 2
    if mode in ('zp', 'zpx', 'zpy', 'indx', 'indy'):
        b = data[addr + 1]
        suf = {'zp': '', 'zpx': ',X', 'zpy': ',Y', 'indx': ',X)', 'indy': '),Y'}[mode]
        pre = '(' if mode in ('indx', 'indy') else ''
        return '%s %s$%02X%s' % (name, pre, b, suf), 2
    if mode == 'rel':
        off = data[addr + 1]
        if off >= 128:
            off -= 256
        return '%s $%04X' % (name, (addr + 2 + off) & 0xFFFF), 2
    lo, hi = data[addr + 1], data[addr + 2]
    a = lo | (hi << 8)
    if mode == 'abs':
        return '%s $%04X' % (name, a), 3
    if mode == 'absx':
        return '%s $%04X,X' % (name, a), 3
    if mode == 'absy':
        return '%s $%04X,Y' % (name, a), 3
    if mode == 'ind':
        return '%s ($%04X)' % (name, a), 3
    return name, 1


def dasm(data, base, count=1):
    out = []
    off = 0
    for _ in range(count):
        if off >= len(data):
            break
        text, ln = dasm_one(data, off)
        out.append((base + off, text, data[off:off + ln]))
        off += ln
    return out, off


# --- Emulador ---
class CPU6502:
    def __init__(self):
        self.mem = bytearray(0x10000)
        self.a = 0
        self.x = 0
        self.y = 0
        self.sp = 0xFD
        self.pc = 0
        self.c = 0
        self.z = 0
        self.i = 0
        self.d = 0
        self.v = 0
        self.n = 0
        self.hooks = {}       # addr -> callable(m)
        self.instr_count = 0
        self.read_hook = None  # callable(m, addr) -> value or None
        self.write_hook = None  # callable(m, addr, value)
        self.halted = False

    def load(self, addr, data):
        self.mem[addr:addr + len(data)] = data

    def rd(self, addr):
        addr &= 0xFFFF
        return self.mem[addr]

    def wr(self, addr, val):
        addr &= 0xFFFF
        self.mem[addr] = val & 0xFF

    def push(self, val):
        self.wr(0x100 + self.sp, val)
        self.sp = (self.sp - 1) & 0xFF

    def pull(self):
        self.sp = (self.sp + 1) & 0xFF
        return self.rd(0x100 + self.sp)

    def set_nz(self, val):
        val &= 0xFF
        self.z = 1 if val == 0 else 0
        self.n = 1 if (val & 0x80) else 0
        return val

    def flags(self):
        return ((self.n << 7) | (self.v << 6) | 0x20 | (self.d << 3) |
                (self.i << 2) | (self.z << 1) | self.c)

    def set_flags(self, p):
        self.n = (p >> 7) & 1
        self.v = (p >> 6) & 1
        self.d = (p >> 3) & 1
        self.i = (p >> 2) & 1
        self.z = (p >> 1) & 1
        self.c = p & 1

    def addr_mode(self, mode):
        pc = self.pc
        if mode in ('imp', 'acc'):
            self.pc += 1
            return ('none', 0)
        if mode == 'imm':
            v = self.rd(pc + 1)
            self.pc += 2
            return ('imm', v)
        if mode == 'zp':
            a = self.rd(pc + 1)
            self.pc += 2
            return ('mem', a)
        if mode == 'zpx':
            a = (self.rd(pc + 1) + self.x) & 0xFF
            self.pc += 2
            return ('mem', a)
        if mode == 'zpy':
            a = (self.rd(pc + 1) + self.y) & 0xFF
            self.pc += 2
            return ('mem', a)
        if mode == 'abs':
            a = self.rd(pc + 1) | (self.rd(pc + 2) << 8)
            self.pc += 3
            return ('mem', a)
        if mode == 'absx':
            a = (self.rd(pc + 1) | (self.rd(pc + 2) << 8)) + self.x
            self.pc += 3
            return ('mem', a & 0xFFFF)
        if mode == 'absy':
            a = (self.rd(pc + 1) | (self.rd(pc + 2) << 8)) + self.y
            self.pc += 3
            return ('mem', a & 0xFFFF)
        if mode == 'indx':
            zp = (self.rd(pc + 1) + self.x) & 0xFF
            a = self.rd(zp) | (self.rd((zp + 1) & 0xFF) << 8)
            self.pc += 2
            return ('mem', a)
        if mode == 'indy':
            zp = self.rd(pc + 1)
            a = (self.rd(zp) | (self.rd((zp + 1) & 0xFF) << 8)) + self.y
            self.pc += 2
            return ('mem', a & 0xFFFF)
        return ('none', 0)

    def branch(self, cond):
        off = self.rd(self.pc + 1)
        self.pc += 2
        if cond:
            if off >= 128:
                off -= 256
            self.pc = (self.pc + off) & 0xFFFF

    def step(self):
        # hook de instruccio
        if self.pc in self.hooks:
            r = self.hooks[self.pc](self)
            if r == 'skip':
                return
            if r == 'halt':
                self.halted = True
                return
        op = self.rd(self.pc)
        pc0 = self.pc
        entry = OPCODES.get(op)
        if entry is None:
            self.halted = True
            return
        name, mode = entry
        kind, val = self.addr_mode(mode)

        def M():
            return self.rd(val) if kind == 'mem' else val

        def W(v):
            if kind == 'mem':
                self.wr(val, v)

        if name == 'LDA':
            self.a = self.set_nz(M())
        elif name == 'LDX':
            self.x = self.set_nz(M())
        elif name == 'LDY':
            self.y = self.set_nz(M())
        elif name == 'STA':
            W(self.a)
        elif name == 'STX':
            W(self.x)
        elif name == 'STY':
            W(self.y)
        elif name == 'TAX':
            self.x = self.set_nz(self.a)
        elif name == 'TAY':
            self.y = self.set_nz(self.a)
        elif name == 'TXA':
            self.a = self.set_nz(self.x)
        elif name == 'TYA':
            self.a = self.set_nz(self.y)
        elif name == 'TSX':
            self.x = self.set_nz(self.sp)
        elif name == 'TXS':
            self.sp = self.x
        elif name == 'INX':
            self.x = self.set_nz(self.x + 1)
        elif name == 'INY':
            self.y = self.set_nz(self.y + 1)
        elif name == 'DEX':
            self.x = self.set_nz(self.x - 1)
        elif name == 'DEY':
            self.y = self.set_nz(self.y - 1)
        elif name == 'INC':
            W(self.set_nz(M() + 1))
        elif name == 'DEC':
            W(self.set_nz(M() - 1))
        elif name == 'ADC':
            m = M()
            s = self.a + m + self.c
            self.v = 1 if (~(self.a ^ m) & (self.a ^ s) & 0x80) else 0
            self.c = 1 if s > 0xFF else 0
            self.a = self.set_nz(s)
        elif name == 'SBC':
            m = M() ^ 0xFF
            s = self.a + m + self.c
            self.v = 1 if (~(self.a ^ m) & (self.a ^ s) & 0x80) else 0
            self.c = 1 if s > 0xFF else 0
            self.a = self.set_nz(s)
        elif name == 'AND':
            self.a = self.set_nz(self.a & M())
        elif name == 'ORA':
            self.a = self.set_nz(self.a | M())
        elif name == 'EOR':
            self.a = self.set_nz(self.a ^ M())
        elif name == 'CMP':
            self.cmp(self.a, M())
        elif name == 'CPX':
            self.cmp(self.x, M())
        elif name == 'CPY':
            self.cmp(self.y, M())
        elif name == 'ASL':
            v = M()
            self.c = (v >> 7) & 1
            v = self.set_nz((v << 1) & 0xFF)
            if mode == 'acc':
                self.a = v
            else:
                W(v)
        elif name == 'LSR':
            v = M()
            self.c = v & 1
            v = self.set_nz(v >> 1)
            if mode == 'acc':
                self.a = v
            else:
                W(v)
        elif name == 'ROL':
            v = M()
            nc = (v >> 7) & 1
            v = self.set_nz(((v << 1) | self.c) & 0xFF)
            self.c = nc
            if mode == 'acc':
                self.a = v
            else:
                W(v)
        elif name == 'ROR':
            v = M()
            nc = v & 1
            v = self.set_nz((v >> 1) | (self.c << 7))
            self.c = nc
            if mode == 'acc':
                self.a = v
            else:
                W(v)
        elif name == 'BIT':
            m = M()
            self.z = 1 if (self.a & m) == 0 else 0
            self.n = (m >> 7) & 1
            self.v = (m >> 6) & 1
        elif name == 'JMP':
            if mode == 'abs':
                self.pc = val
            else:
                lo = self.rd(val)
                hi = self.rd((val & 0xFF00) | ((val + 1) & 0xFF))
                self.pc = lo | (hi << 8)
        elif name == 'JSR':
            ret = (self.pc - 1) & 0xFFFF
            self.push(ret >> 8)
            self.push(ret & 0xFF)
            self.pc = val
        elif name == 'RTS':
            lo = self.pull()
            hi = self.pull()
            self.pc = ((hi << 8) | lo) + 1
        elif name == 'RTI':
            self.set_flags(self.pull())
            lo = self.pull()
            hi = self.pull()
            self.pc = (hi << 8) | lo
        elif name == 'PHA':
            self.push(self.a)
        elif name == 'PLA':
            self.a = self.set_nz(self.pull())
        elif name == 'PHP':
            self.push(self.flags() | 0x10)
        elif name == 'PLP':
            self.set_flags(self.pull())
        elif name == 'CLC':
            self.c = 0
        elif name == 'SEC':
            self.c = 1
        elif name == 'CLI':
            self.i = 0
        elif name == 'SEI':
            self.i = 1
        elif name == 'CLD':
            self.d = 0
        elif name == 'SED':
            self.d = 1
        elif name == 'CLV':
            self.v = 0
        elif name == 'BPL':
            self.branch(self.n == 0)
        elif name == 'BMI':
            self.branch(self.n == 1)
        elif name == 'BVC':
            self.branch(self.v == 0)
        elif name == 'BVS':
            self.branch(self.v == 1)
        elif name == 'BCC':
            self.branch(self.c == 0)
        elif name == 'BCS':
            self.branch(self.c == 1)
        elif name == 'BNE':
            self.branch(self.z == 0)
        elif name == 'BEQ':
            self.branch(self.z == 1)
        elif name == 'NOP':
            pass
        elif name == 'BRK':
            self.halted = True
        else:
            self.halted = True
        self.instr_count += 1

    def cmp(self, reg, m):
        r = (reg - m) & 0x1FF
        self.c = 1 if reg >= m else 0
        self.set_nz((reg - m) & 0xFF)

    def run(self, max_instr=1000000):
        n = 0
        while not self.halted and n < max_instr:
            self.step()
            n += 1
        return n


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == 'dasm':
        path = sys.argv[2]
        base = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
        data = open(path, 'rb').read()
        lines, _ = dasm(data, base, 400)
        for addr, text, raw in lines:
            print('%04X: %-16s %s' % (addr, text, raw.hex(' ')))
