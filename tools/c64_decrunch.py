#!/usr/bin/env python3
"""
c64_decrunch.py - Captura el resultat del decrunch de Blues Brothers (C64).

Fa servir breakpoints de VICE sobre la rutina de decrunch per capturar la RAM
just en el moment de descomprimir.

Us:
  py c64_decrunch.py --disc <disc.d64> --lo 0xCE00 --hi 0xCED0 --dump prefix
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicebin import ViceBin  # noqa: E402


def dump_ram(v):
    full = bytearray()
    for start in range(0, 0x10000, 0x1000):
        full += v.mem_get(start, start + 0xfff)
    return bytes(full)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default='c64_dec')
    ap.add_argument('--disc', default=None)
    ap.add_argument('--lo', type=lambda s: int(s, 0), default=0xCE00)
    ap.add_argument('--hi', type=lambda s: int(s, 0), default=0xCED0)
    ap.add_argument('--end', type=lambda s: int(s, 0), default=0xCEC2,
                    help='adreca de fi del decrunch (RTS)')
    ap.add_argument('--seconds', type=int, default=120)
    args = ap.parse_args()

    v = ViceBin()
    v.ping()
    # breakpoint a l'entrada i al final
    cp_lo = v.checkpoint_set(args.lo, args.lo, stop=True, op=0x04)
    cp_end = v.checkpoint_set(args.end, args.end, stop=True, op=0x04)
    print("checkpoints: lo=%d end=%d" % (cp_lo, cp_end), flush=True)
    if args.disc:
        # treu breakpoints temporalment per autostart? els deixem
        v.autostart(args.disc, run=True, index=0)
    hits = 0
    start = time.time()
    while time.time() - start < args.seconds:
        try:
            t, err, rid, body = v.recv_response()
        except Exception:
            time.sleep(0.05)
            continue
        if t == 0x11:
            # checkpoint info: CN(4) CH(1) SA(2) EA(2)...
            import struct
            cn = struct.unpack('<I', body[0:4])[0]
            ch = body[4]
            sa = struct.unpack('<H', body[5:7])[0]
            print("event checkpoint %d @%04X hit=%d" % (cn, sa, ch), flush=True)
            if ch:
                hits += 1
                pc = v.regs().get(3, 0)
                ram = dump_ram(v)
                fn = "%s_%02d_%04X.bin" % (args.dump, hits, pc)
                open(fn, 'wb').write(ram)
                print("  desat", fn, "PC=%04X" % pc, flush=True)
                if hits > 40:
                    break
    v.close()


if __name__ == '__main__':
    main()
