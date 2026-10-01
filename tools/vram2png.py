"""Converteix la VRAM del CPC (16 KB, Mode 1) a PNG per inspeccio visual.
Us: vram2png.py vram.bin out.png [palette]
Paleta per defecte (Mode 1, color idx 0..3) = negre, blau, vermell, blanc.
"""
import sys, struct, zlib

W, H = 320, 200

def cpc_mode1_addr(x, y):
    # mode 1: 2 bits/pixel, 4 px/byte, 80 bytes per linia
    block = (y & 7) << 11
    ma = (y >> 3) * 80 + (x >> 2)   # en bytes
    return 0xC000 + (block | (ma & 0x7FF)) - 0xC000  # offset dins vram

def decode(vram, palette):
    img = bytearray()
    for y in range(H):
        row = bytearray()
        for x in range(W):
            block = (y & 7) << 11
            # ma en "paraules" com al CRTC; aqui treballem en bytes de vram
            ma_row = (y >> 3) * 80
            ma = ma_row + (x >> 2)
            addr = (block | (ma & 0x7FF))
            byte = vram[addr & 0x3FFF]
            shift = (3 - (x & 3)) * 2
            c = (byte >> shift) & 3
            row += palette[c]
        img += row
    return img

def write_png(path, rows, w, h):
    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c
    raw = b"".join(b"\x00" + r for r in rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)

if __name__ == "__main__":
    vram = open(sys.argv[1], "rb").read()
    out = sys.argv[2]
    # negre, blau, vermell, blanc
    pal = bytes([0, 0, 0,  0, 0, 200,  220, 40, 40,  255, 255, 255])
    rows = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            block = (y & 7) << 11
            ma = (y >> 3) * 80 + (x >> 2)
            addr = (block | (ma & 0x7FF)) & 0x3FFF
            byte = vram[addr]
            c = (byte >> ((3 - (x & 3)) * 2)) & 3
            row += pal[c*3:c*3+3]
        rows.append(row)
    write_png(out, rows, W, H)
    print("escrit", out)
