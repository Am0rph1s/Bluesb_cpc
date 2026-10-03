#!/usr/bin/env python3
"""
d64.py - Destripa discs C64 (.d64) de 1541: llista el directori i extreu fitxers.

Us:
  py d64.py list <disc.d64>
  py d64.py extract <disc.d64> [-o outdir] [--all | noms...]
  py d64.py bam <disc.d64>            # resum de sectors lliures per pista

Format D64 estandard (174848 bytes): 35 pistes.
  pistes 1-17 : 21 sectors
  pistes 18-24: 19 sectors
  pistes 25-30: 18 sectors
  pistes 31-35: 17 sectors
Directori: pista 18 sector 1. BAM: pista 18 sector 0.
"""
import argparse
import os
import sys

SPT = [0] + [21] * 17 + [19] * 7 + [18] * 6 + [17] * 5  # index 1..35


def track_offset(track):
    """Offset de la pista (1-indexada) dins del fitxer."""
    off = 0
    for t in range(1, track):
        off += SPT[t] * 256
    return off


def sector_offset(track, sector):
    return track_offset(track) + sector * 256


def read_sector(data, track, sector):
    o = sector_offset(track, sector)
    return data[o:o + 256]


PETSCII = {
    0x00: '@', 0x0A: '\n', 0x5B: '[', 0x5C: '\\', 0x5D: ']',
    0x5E: '^', 0x5F: '<', 0x60: '`', 0x61: 'A', 0x62: 'B', 0x63: 'C',
    0x64: 'D', 0x65: 'E', 0x66: 'F', 0x67: 'G', 0x68: 'H', 0x69: 'I',
    0x6A: 'J', 0x6B: 'K', 0x6C: 'L', 0x6D: 'M', 0x6E: 'N', 0x6F: 'O',
    0x70: 'P', 0x71: 'Q', 0x72: 'R', 0x73: 'S', 0x74: 'T', 0x75: 'U',
    0x76: 'V', 0x77: 'W', 0x78: 'X', 0x79: 'Y', 0x7A: 'Z',
}


def pet2ascii(b):
    if 0x41 <= b <= 0x5A:      # lletra majuscula petscii -> minuscula cbm
        return chr(b)
    if b == 0xA0:
        return ''
    return PETSCII.get(b, chr(b) if 32 <= b < 127 else '.')


def parse_name(raw):
    return ''.join(pet2ascii(b) for b in raw).rstrip()


TYPES = {0: 'DEL', 1: 'SEQ', 2: 'PRG', 3: 'USR', 4: 'REL'}


def iter_dir(data):
    track, sector = 18, 1
    while track != 0:
        sec = read_sector(data, track, sector)
        nxt_t, nxt_s = sec[0], sec[1]
        pos = 2
        while pos + 32 <= 256 and sec[pos] != 0:
            e = sec[pos:pos + 32]
            ftype = e[0] & 0x0F
            name = parse_name(e[3:3 + 16])
            size_sec = e[28] | (e[29] << 8)
            yield {
                'type': TYPES.get(ftype, '??'),
                'locked': bool(e[0] & 0x40),
                'name': name,
                'first_track': e[1],
                'first_sector': e[2],
                'size_sec': size_sec,
                'size': size_sec * 254 - 1 if size_sec else 0,
            }
            pos += 32
        if nxt_t == 0 or nxt_t == 255:
            break
        track, sector = nxt_t, nxt_s


def read_file(data, entry):
    """Segueix la cadena de sectors i concatena les dades."""
    out = bytearray()
    track, sector = entry['first_track'], entry['first_sector']
    seen = set()
    while track != 0:
        if (track, sector) in seen:
            raise SystemExit("Cadena de sectors circular al fitxer %s" % entry['name'])
        seen.add((track, sector))
        sec = read_sector(data, track, sector)
        nxt_t, nxt_s = sec[0], sec[1]
        # ultim sector: link = (0, nbytes usats + 1)
        if nxt_t == 0:
            used = nxt_s - 1
            out += sec[2:2 + used]
        else:
            out += sec[2:256]
        track, sector = nxt_t, nxt_s
    return bytes(out)


def cmd_list(args):
    data = open(args.disk, 'rb').read()
    print("Disc %s (%d bytes)" % (os.path.basename(args.disk), len(data)))
    print("%-20s %-4s %8s  %s" % ("NOM", "TIPUS", "MIDA", "PRIMER SECTOR"))
    total = 0
    for e in iter_dir(data):
        print("%-20s %-4s %8d  %d/%d" % (
            e['name'], e['type'], e['size'], e['first_track'], e['first_sector']))
        total += 1
    print("-- %d fitxers" % total)


def cmd_bam(args):
    data = open(args.disk, 'rb').read()
    bam = read_sector(data, 18, 0)
    free = bam[0]
    print("Sectors lliures: %d" % free)
    # mapa de bits comenca al byte 4, 4 bytes per pista (pistes 1-35)
    for t in range(1, 36):
        bits = bam[4 + (t - 1) * 4:4 + t * 4]
        n = SPT[t]
        # BAM: bit a 0 = sector ocupat
        used = sum(1 for s in range(n) if not (bits[s // 8] >> (s % 8)) & 1)
        print("  pista %2d: %2d/%2d ocupats" % (t, used, n))


def cmd_extract(args):
    data = open(args.disk, 'rb').read()
    entries = list(iter_dir(data))
    if args.all:
        wanted = entries
    else:
        names = {n.lower() for n in args.names}
        wanted = [e for e in entries if e['name'].lower() in names]
        if not wanted:
            raise SystemExit("Cap fitxer coincideix amb %s" % args.names)
    os.makedirs(args.outdir, exist_ok=True)
    for i, e in enumerate(wanted):
        blob = read_file(data, e)
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in e['name'])
        fn = "%02d_%s.%s" % (i, safe.strip('_'), e['type'].lower())
        path = os.path.join(args.outdir, fn)
        with open(path, 'wb') as f:
            f.write(blob)
        print("%-24s %8d bytes -> %s" % (e['name'], len(blob), path))


def main():
    ap = argparse.ArgumentParser(description="Destripador de discs C64 .d64")
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('list')
    p.add_argument('disk')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('bam')
    p.add_argument('disk')
    p.set_defaults(func=cmd_bam)

    p = sub.add_parser('extract')
    p.add_argument('disk')
    p.add_argument('names', nargs='*')
    p.add_argument('-o', '--outdir', default='c64rip')
    p.add_argument('--all', action='store_true')
    p.set_defaults(func=cmd_extract)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
