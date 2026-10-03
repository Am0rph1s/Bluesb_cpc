#!/usr/bin/env python3
"""
dsk.py - Llista i extreu fitxers d'un DSK CPC (format MV-CPCEMU).

Us:
  py dsk.py list <disc.dsk>
  py dsk.py extract <disc.dsk> [-o outdir]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dskutil import DskPatcher, LOGICAL_IDS   # noqa: E402


def dir_entries(dsk):
    data = dsk.read_dir_sectors()
    out = []
    for i in range(64):
        e = data[i * 32:(i + 1) * 32]
        if len(e) < 32:
            break
        user = e[0]
        if user == 0xE5:
            continue
        name = bytes(e[1:9]).decode('latin1').rstrip(' ')
        ext = bytes(e[9:12]).decode('latin1').rstrip(' ')
        ext_lo = e[12]
        ext_hi = e[14]
        nrec = e[15]
        blocks = list(e[16:32])
        out.append({'user': user, 'name': name, 'ext': ext,
                    'extent': ext_lo | (ext_hi << 5), 'nrec': nrec,
                    'blocks': blocks})
    return out


def read_block(dsk, blk):
    abs_sec = blk * 2
    secs = []
    for i in range(2):
        s = abs_sec + i
        tr = s // 9
        sid = LOGICAL_IDS[s % 9]
        sec = dsk.read_sector(tr, sid)
        secs.append(bytes(sec) if sec else b'')
    return b''.join(secs)


def extract_file(dsk, entries):
    """entries: llistes d'entrades del mateix fitxer ordenades per extent."""
    blob = bytearray()
    for e in entries:
        for b in e['blocks']:
            if b == 0:
                continue
            blob += read_block(dsk, b)
    # mida real: de la capcalera AMSDOS (0x18/0x19) + 128
    if len(blob) >= 128 and blob[0] == 0:
        size = blob[0x18] | (blob[0x19] << 8)
        load = blob[0x15] | (blob[0x16] << 8)
        exec_ = blob[0x1A] | (blob[0x1B] << 8)
        return bytes(blob[:128 + size]), load, exec_
    return bytes(blob), None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['list', 'extract'])
    ap.add_argument('disk')
    ap.add_argument('-o', '--outdir', default='dsk_out')
    args = ap.parse_args()

    dsk = DskPatcher(args.disk)
    print("%s: %d pistes, %d cara(es), track_size=%d" % (
        os.path.basename(args.disk), dsk.num_tracks, dsk.num_sides, dsk.track_size))
    entries = dir_entries(dsk)
    # agrupa per (nom,ext)
    groups = {}
    for e in entries:
        groups.setdefault((e['name'], e['ext']), []).append(e)
    if args.cmd == 'list':
        print("%-9s %-4s %-6s %s" % ("NOM", "EXT", "EXTENT", "BLOCS"))
        for (nm, ext), es in sorted(groups.items()):
            es.sort(key=lambda x: x['extent'])
            blocks = [b for e in es for b in e['blocks'] if b]
            print("%-9s %-4s %-6d %s" % (nm, ext, len(es), blocks[:20]))
        print("-- %d fitxers" % len(groups))
    else:
        os.makedirs(args.outdir, exist_ok=True)
        for (nm, ext), es in sorted(groups.items()):
            es.sort(key=lambda x: x['extent'])
            blob, load, exec_ = extract_file(dsk, es)
            fn = "%s.%s" % (nm.strip(), ext.strip())
            path = os.path.join(args.outdir, fn)
            with open(path, 'wb') as f:
                f.write(blob)
            print("%-14s %7d B  load=%s exec=%s" % (
                fn, len(blob),
                ('0x%04X' % load) if load is not None else '?',
                ('0x%04X' % exec_) if exec_ is not None else '?'))


if __name__ == '__main__':
    main()
