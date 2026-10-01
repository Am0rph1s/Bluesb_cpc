#!/usr/bin/env python3
"""
ilbm.py - Decodificador IFF/ILBM (el format dels gràfics de Blues Brothers DOS).
Gestiona: BMHD, CMAP, BODY (PackBits) i decodificació planar de 4 bitplanes.
Retorna la imatge com a indexs de paleta (0..15) i la paleta RGB.
"""
import struct


def _decode_packbits(body, w, h, planes):
    row_bytes = ((w + 15) // 16) * 2 * planes  # w arrodonit a 16 px, 2 bytes per 16 px per pla
    total = row_bytes * h
    out = bytearray()
    i = 0
    while len(out) < total and i < len(body):
        code = body[i]
        i += 1
        if code == 128:
            continue
        if code < 128:
            n = code + 1
            out += body[i:i + n]
            i += n
        else:
            n = 257 - code
            if i >= len(body):
                break
            out += bytes([body[i]]) * n
            i += 1
    if len(out) < total:
        out += bytes(total - len(out))
    return out[:total]


def decode_body(body, w, h, planes, compression):
    if compression == 1:
        packed = _decode_packbits(body, w, h, planes)
    else:
        packed = body
    row_bytes = ((w + 15) // 16) * 2 * planes
    plane_size = row_bytes // planes
    pixels = []
    for y in range(h):
        row = packed[y * row_bytes:(y + 1) * row_bytes]
        line = [0] * w
        for xb in range(plane_size):
            for b in range(8):
                bit = 7 - b
                x = xb * 8 + b
                if x >= w:
                    break
                c = 0
                for p in range(planes):
                    if row[p * plane_size + xb] & (1 << bit):
                        c |= 1 << p
                line[x] = c
        pixels.append(line)
    return pixels


def read_ilbm(data):
    """Retorna (w, h, planes, palette, pixels)."""
    if data[:4] != b'FORM':
        raise ValueError("No es un fitxer IFF (FORM)")
    off = 12
    w = h = planes = compression = None
    palette = None
    pixels = None
    while off + 8 <= len(data):
        tag = data[off:off + 4]
        size = struct.unpack('>I', data[off + 4:off + 8])[0]
        body = data[off + 8:off + 8 + size]
        if tag == b'BMHD':
            w = struct.unpack('>H', body[0:2])[0]
            h = struct.unpack('>H', body[2:4])[0]
            planes = body[8]
            compression = body[10]
        elif tag == b'CMAP':
            palette = [(body[i], body[i + 1], body[i + 2]) for i in range(0, len(body) - 2, 3)]
        elif tag == b'BODY':
            pixels = decode_body(body, w, h, planes, compression)
        off += 8 + size + (size & 1)
    return w, h, planes, palette, pixels
