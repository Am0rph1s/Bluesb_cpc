#!/usr/bin/env python3
"""
ihx2bin.py - Convertidor natiu d'Intel HEX (.ihx) a binari brut (.bin)
Substitut de hex2bin sense dependències externes ni WSL.
"""
import sys, os

def convert_ihx(ihx_path, bin_path, start_addr=None, max_length=None, pad_byte=0x00):
    mem = {}
    min_addr = 0x10000
    max_addr = 0
    with open(ihx_path, "r", encoding="latin1") as f:
        for line in f:
            line = line.strip()
            if not line.startswith(":"):
                continue
            rec_len = int(line[1:3], 16)
            addr = int(line[3:7], 16)
            rec_type = int(line[7:9], 16)
            if rec_type == 0:  # Data record
                data = bytes.fromhex(line[9:9+rec_len*2])
                for i, b in enumerate(data):
                    a = addr + i
                    mem[a] = b
                    if a < min_addr:
                        min_addr = a
                    if a > max_addr:
                        max_addr = a
            elif rec_type == 1:  # EOF
                break

    if not mem:
        print(f"Error: cap dada trobada a {ihx_path}")
        return False

    base = start_addr if start_addr is not None else min_addr
    if max_length is not None:
        limit = base + max_length
    else:
        limit = max_addr + 1

    buf = bytearray([pad_byte] * (limit - base))
    for a, b in mem.items():
        if base <= a < limit:
            buf[a - base] = b

    with open(bin_path, "wb") as f:
        f.write(buf)

    print(f"Convertit {ihx_path} -> {bin_path} ({len(buf)} bytes, base=0x{base:04X}, limit=0x{limit:04X})")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert IHX to BIN")
    parser.add_argument("input", help="Fitxer IHX d'entrada")
    parser.add_argument("output", help="Fitxer BIN de sortida")
    parser.add_argument("-s", "--start", type=lambda x: int(x, 16), default=None, help="Adreca base hexadecimal (p.ex. 0100 o 4000)")
    parser.add_argument("-l", "--length", type=lambda x: int(x, 16), default=None, help="Longitud maxima hexadecimal (p.ex. 8000 o 3F00)")
    parser.add_argument("-p", "--pad", type=lambda x: int(x, 16), default=0, help="Byte de padding (per defecte 00)")
    args = parser.parse_args()

    success = convert_ihx(args.input, args.output, start_addr=args.start, max_length=args.length, pad_byte=args.pad)
    if not success:
        sys.exit(1)
