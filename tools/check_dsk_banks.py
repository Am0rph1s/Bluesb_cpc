#!/usr/bin/env python3
"""Audita els bancs de les seccions dels paquets de nivell DINS del DSK.

Si una seccio te bank 0xC2/0xC3, `load_package` fa OUT(0x7F00) amb aquest
valor i la maquina penja o rebota a BASIC (vegeu src/moving.c:92).

Us: py -3 tools/check_dsk_banks.py [bluesb.dsk]
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from dskutil import DskPatcher  # noqa: E402

DSK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, "bluesb.dsk")
LVLCHS_MB_OFF = 0x1D00

dsk = DskPatcher(DSK)
cat = b"".join(dsk.read_sector(0, sid) for sid in (0xC1, 0xC2, 0xC3, 0xC4))

entries = []
for i in range(64):
    e = cat[i * 32:(i + 1) * 32]
    if e[0] == 0x00:
        nm = bytes(e[1:9]).decode("latin1").strip()
        ex = bytes(e[9:12]).decode("latin1").strip()
        if nm:
            entries.append((nm, ex, [b for b in e[16:32] if b]))

print("cataleg:", ", ".join("%s.%s" % (n, x) for n, x, _ in entries))

# MUSBANK -> LVLCHS
mb = next((blocks for n, x, blocks in entries if n == "MUSBANK" and x == "BIN"), None)
if not mb:
    raise SystemExit("no MUSBANK")
m = bytearray()
for b in mb:
    for t, sid in dsk.bloc_to_ts(b):
        s = dsk.read_sector(t, sid)
        if s:
            m += s
mb_raw = bytes(m[128:])
assert mb_raw[LVLCHS_MB_OFF:LVLCHS_MB_OFF + 2] == b"LV", mb_raw[LVLCHS_MB_OFF:LVLCHS_MB_OFF + 2]
lv = mb_raw[LVLCHS_MB_OFF:]
n_lvl = lv[3]
bad = 0
for lvl in range(n_lvl):
    for typ, suffix in ((0, "WORLD"), (1, "ENEMI"), (2, "C1")):
        off = 4 + (lvl * 3 + typ) * 5
        ondisk, sec, crc = struct.unpack("<HBH", lv[off:off + 5])
        if sec == 0:
            continue
        pool = 4 + n_lvl * 3 * 5 + lvl * (56 + 32 + 32) + (0 if typ == 0 else (56 if typ == 1 else 88))
        chs = list(zip(lv[pool:pool + sec * 2][0::2], lv[pool:pool + sec * 2][1::2]))
        data = bytearray()
        for t, sid in chs:
            s = dsk.read_sector(t, sid)
            if s:
                data += s
        payload = bytes(data[128:ondisk])
        name = "L%d%s" % (lvl + 1, suffix)
        if payload[:2] != b"B\x01":
            print("  %-8s magic invalid: %s" % (name, payload[:4].hex()))
            bad += 1
            continue
        ns = payload[6]
        secs = []
        for i in range(ns):
            o = 16 + i * 8
            bank, fl = payload[o], payload[o + 1]
            dst, soff, slen = struct.unpack_from("<HHH", payload, o + 2)
            secs.append((bank, dst, slen))
            if bank in (0xC2, 0xC3) or not (0xC0 <= bank <= 0xC7):
                bad += 1
                print("  *** %-8s sec%d BANK=0x%02X (PERILLOS!) dst=0x%04X len=%d" % (
                    name, i, bank, dst, slen))
        print("  %-8s %d B  seccions: %s" % (
            name, len(payload), ", ".join("0x%02X@0x%04X(%d)" % s for s in secs)))
print("RESULTAT:", "OK" if bad == 0 else "%d PROBLEMES" % bad)
