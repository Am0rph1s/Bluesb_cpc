#!/usr/bin/env python3
"""
unsqz.py - Descompressor de la compressio SQZ de Titus Interactive (variants
.sqz/.sqv), implementat segons bb/unpack.c de cyxx/blues.
Capcalera de 6 bytes: mida (4, dos uint16 LE) + longitud diccionari (2, LE).
"""


def unsqz(data):
    uncompressed_size = (int.from_bytes(data[0:2], 'little') << 16) + int.from_bytes(data[2:4], 'little')
    dict_len = int.from_bytes(data[4:6], 'little')
    dic = data[6:6 + dict_len]
    pos = 6 + dict_len

    out = bytearray()
    bitbuf = 0
    bitcount = 0
    word = 0
    val = 0

    while len(out) < uncompressed_size:
        if bitcount == 0:
            if pos + 2 > len(data):
                break
            word = int.from_bytes(data[pos:pos + 2], 'big')
            pos += 2
            bitcount = 16
        carry = (word & 0x8000) != 0
        word = (word << 1) & 0xFFFF
        bitcount -= 1
        if carry:
            val += 2
        val = int.from_bytes(dic[val:val + 2], 'little') if val + 2 <= len(dic) else 0
        if (val & 0x8000) == 0:
            continue
        out.append(val & 0xFF)
        val = 0
    return bytes(out)
