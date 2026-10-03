#!/usr/bin/env python3
"""
z80.py - Desassemblador Z80 en Python (base + CB + ED + DD/FD + DDCB/FDCB).

Us:
  py z80.py <fitxer.bin> <adreca_base> [count]
"""

R8 = ['B', 'C', 'D', 'E', 'H', 'L', '(HL)', 'A']
RP = ['BC', 'DE', 'HL', 'SP']
RP2 = ['BC', 'DE', 'HL', 'AF']
CC = ['NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M']
ALU = ['ADD A,', 'ADC A,', 'SUB ', 'SBC A,', 'AND ', 'XOR ', 'OR ', 'CP ']
ROT = ['RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SLL', 'SRL']


def s8(b):
    return b - 256 if b >= 128 else b


def s16(b):
    return b - 65536 if b >= 32768 else b


def reg8(i, ix=None):
    if i == 6 and ix:
        d = ix[0]
        n = ix[1]
        return "(%s%s%d)" % (n, '+' if d >= 0 else '-', abs(d))
    return R8[i]


def dis(data, addr):
    """Retorna (text, longitud)."""
    op = data[0]

    def imm8(o):
        return data[o + 1]

    def imm16(o):
        return data[o + 1] | (data[o + 2] << 8)

    def rel(o):
        return (addr + o + 2 + s8(data[o + 1])) & 0xFFFF

    # prefixes
    if op in (0xDD, 0xFD):
        n = 'IX' if op == 0xDD else 'IY'
        if len(data) > 1 and data[1] == 0xCB:
            off = s8(data[2])
            sub = data[3]
            r = (sub >> 3) & 7
            l = sub & 7
            kind = ['RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SLL', 'SRL'][(sub >> 3) & 7] if sub < 0x40 else None
            if sub < 0x40:
                return "%s (%s%s%d)" % (kind, n, '+' if off >= 0 else '-', abs(off)), 4
            elif sub < 0x80:
                return "BIT %d, (%s%s%d)" % (r, n, '+' if off >= 0 else '-', abs(off)), 4
            elif sub < 0xC0:
                return "RES %d, (%s%s%d)" % (r, n, '+' if off >= 0 else '-', abs(off)), 4
            else:
                return "SET %d, (%s%s%d)" % (r, n, '+' if off >= 0 else '-', abs(off)), 4
        # normal prefix: substitute HL->IX/IY, (HL)->(IX+d)
        t, ln = dis(data[1:], addr + 1)
        if ln >= 1 and t:
            t = t.replace('(HL)', '(%s)' % n).replace('HL', n).replace('H,', '%sh,' % n).replace(',H', ',%sh' % n).replace('L,', '%sl,' % n).replace(',L', ',%sl' % n)
        return t, ln + 1

    if op == 0xCB:
        sub = data[1]
        z = sub & 7
        y = (sub >> 3) & 7
        if sub < 0x40:
            return "%s %s" % (ROT[y], R8[z]), 2
        if sub < 0x80:
            return "BIT %d, %s" % (y, R8[z]), 2
        if sub < 0xC0:
            return "RES %d, %s" % (y, R8[z]), 2
        return "SET %d, %s" % (y, R8[z]), 2

    if op == 0xED:
        sub = data[1]
        pairs = {
            0x40: 'IN B,(C)', 0x41: 'OUT (C),B', 0x42: 'SBC HL,BC', 0x43: 'LD (nn),BC',
            0x44: 'NEG', 0x46: 'IM 0', 0x47: 'LD I,A', 0x48: 'IN C,(C)', 0x49: 'OUT (C),C',
            0x4A: 'ADC HL,BC', 0x4B: 'LD BC,(nn)', 0x4D: 'RETI', 0x4F: 'LD R,A',
            0x50: 'IN D,(C)', 0x51: 'OUT (C),D', 0x52: 'SBC HL,DE', 0x53: 'LD (nn),DE',
            0x56: 'IM 1', 0x57: 'LD A,I', 0x58: 'IN E,(C)', 0x59: 'OUT (C),E',
            0x5A: 'ADC HL,DE', 0x5B: 'LD DE,(nn)', 0x5E: 'IM 2', 0x5F: 'LD A,R',
            0x60: 'IN H,(C)', 0x61: 'OUT (C),H', 0x62: 'SBC HL,HL', 0x63: 'LD (nn),HL',
            0x67: 'RRD', 0x68: 'IN L,(C)', 0x69: 'OUT (C),L', 0x6A: 'ADC HL,HL',
            0x6B: 'LD HL,(nn)', 0x6F: 'RLD',
            0x70: 'IN (C)', 0x71: 'OUT (C),0', 0x72: 'SBC HL,SP', 0x73: 'LD (nn),SP',
            0x78: 'IN A,(C)', 0x79: 'OUT (C),A', 0x7A: 'ADC HL,SP', 0x7B: 'LD SP,(nn)',
            0xA0: 'LDI', 0xA1: 'CPI', 0xA2: 'INI', 0xA3: 'OUTI',
            0xA8: 'LDD', 0xA9: 'CPD', 0xAA: 'IND', 0xAB: 'OUTD',
            0xB0: 'LDIR', 0xB1: 'CPIR', 0xB2: 'INIR', 0xB3: 'OTIR',
            0xB8: 'LDDR', 0xB9: 'CPDR', 0xBA: 'INDR', 0xBB: 'OTDR',
        }
        if sub in pairs:
            t = pairs[sub]
            if '(nn)' in t:
                nn = data[2] | (data[3] << 8)
                t = t.replace('nn', '0x%04X' % nn)
                return t, 4
            return t, 2
        return "ED %02X" % sub, 2

    # base
    if op == 0x76:
        return 'HALT', 1
    if 0x40 <= op <= 0x7F:
        return "LD %s, %s" % (R8[(op >> 3) & 7], R8[op & 7]), 1
    if 0x80 <= op <= 0xBF:
        return "%s%s" % (ALU[(op >> 3) & 7], R8[op & 7]), 1

    if 0x04 <= op <= 0x3C and (op & 7) == 4:
        return "INC %s" % R8[(op >> 3) & 7], 1
    if 0x05 <= op <= 0x3D and (op & 7) == 5:
        return "DEC %s" % R8[(op >> 3) & 7], 1
    if 0x06 <= op <= 0x3E and (op & 7) == 6:
        return "LD %s, 0x%02X" % (R8[(op >> 3) & 7], imm8(0)), 2

    simple = {
        0x00: ('NOP', 1), 0x07: ('RLCA', 1), 0x08: ("EX AF, AF'", 1), 0x0F: ('RRCA', 1),
        0x17: ('RLA', 1), 0x1F: ('RRA', 1), 0x27: ('DAA', 1), 0x2F: ('CPL', 1),
        0x37: ('SCF', 1), 0x3F: ('CCF', 1), 0xD9: ('EXX', 1), 0xE3: ('EX (SP), HL', 1),
        0xE9: ('JP (HL)', 1), 0xEB: ('EX DE, HL', 1), 0xF3: ('DI', 1), 0xF9: ('LD SP, HL', 1),
        0xFB: ('EI', 1), 0xC9: ('RET', 1),
    }
    if op in simple:
        return simple[op]

    if op in (0x01, 0x11, 0x21, 0x31):
        return "LD %s, 0x%04X" % (RP[(op >> 4) & 3], imm16(0)), 3
    if op in (0x02, 0x12):
        return "LD (%s), A" % ('BC' if op == 0x02 else 'DE'), 1
    if op in (0x0A, 0x1A):
        return "LD A, (%s)" % ('BC' if op == 0x0A else 'DE'), 1
    if op in (0x03, 0x13, 0x23, 0x33):
        return "INC %s" % RP[(op >> 4) & 3], 1
    if op in (0x0B, 0x1B, 0x2B, 0x3B):
        return "DEC %s" % RP[(op >> 4) & 3], 1
    if op in (0x09, 0x19, 0x29, 0x39):
        return "ADD HL, %s" % RP[(op >> 4) & 3], 1
    if op == 0x10:
        return "DJNZ 0x%04X" % rel(0), 2
    if op == 0x18:
        return "JR 0x%04X" % rel(0), 2
    if op in (0x20, 0x28, 0x30, 0x38):
        return "JR %s, 0x%04X" % (CC[(op >> 3) & 3], rel(0)), 2
    if op == 0x22:
        return "LD (0x%04X), HL" % imm16(0), 3
    if op == 0x2A:
        return "LD HL, (0x%04X)" % imm16(0), 3
    if op == 0x32:
        return "LD (0x%04X), A" % imm16(0), 3
    if op == 0x3A:
        return "LD A, (0x%04X)" % imm16(0), 3

    if op in (0xC1, 0xD1, 0xE1, 0xF1):
        return "POP %s" % RP2[(op >> 4) & 3], 1
    if op in (0xC5, 0xD5, 0xE5, 0xF5):
        return "PUSH %s" % RP2[(op >> 4) & 3], 1
    if op in (0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8):
        return "RET %s" % CC[(op >> 3) & 7], 1
    if op == 0xC3:
        return "JP 0x%04X" % imm16(0), 3
    if op in (0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA):
        return "JP %s, 0x%04X" % (CC[(op >> 3) & 7], imm16(0)), 3
    if op == 0xCD:
        return "CALL 0x%04X" % imm16(0), 3
    if op in (0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC):
        return "CALL %s, 0x%04X" % (CC[(op >> 3) & 7], imm16(0)), 3
    if op in (0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE):
        return "%s0x%02X" % (ALU[(op >> 3) & 7], imm8(0)), 2
    if op in (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF):
        return "RST 0x%02X" % (op & 0x38), 1
    if op == 0xD3:
        return "OUT (0x%02X), A" % imm8(0), 2
    if op == 0xDB:
        return "IN A, (0x%02X)" % imm8(0), 2
    return "DB 0x%02X" % op, 1


def disasm(data, base, count=None, start=0):
    out = []
    off = start
    n = 0
    while off < len(data) and (count is None or n < count):
        text, ln = dis(data[off:], base + off)
        out.append((base + off, text, data[off:off + ln]))
        off += ln
        n += 1
    return out, off


if __name__ == '__main__':
    import sys
    path = sys.argv[1]
    base = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    count = int(sys.argv[3]) if len(sys.argv) > 3 else None
    data = open(path, 'rb').read()
    lines, _ = disasm(data, base, count)
    for a, t, raw in lines:
        print('%04X: %-22s %s' % (a, t, raw.hex(' ')))
