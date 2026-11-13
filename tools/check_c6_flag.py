#!/usr/bin/env python3
"""
check_c6_flag.py - Regressio del fals `code_ready` en carregar nivells.

El carregador antic es saltava la carrega del codi compartit de C6
(L1ENEMI) si `C6:0x5A00 == 0xC3`. Aquest byte pot valer 0xC3 per RAM
inicialitzada o per dades del FRONT; llavors s'executava brossa i el joc
acabava a BASIC en carregar L2-L6.

Aquest test FORCA 0xC3 a C6:0x5A00 (fisic 0x18000 + 0x1A00) abans de
carregar el nivell. Amb la correccio, el joc ha de carregar i correr.

Us: py -3 tools/check_c6_flag.py [--level 2] [--dsk bluesb.dsk] [--port 10060]
"""
import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
EMU = os.path.join(PROJ, "tools", "ZEsarUX_windows-13.0", "zesarux.exe")

# C6 = pagina 6 (64K extra); 0x5A00 cau a l'offset 0x1A00 del banc a 0x4000.
C6_5A00_PHYS = 0x18000 + 0x1A00


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsk", default=os.path.join(PROJ, "bluesb.dsk"))
    ap.add_argument("--level", type=int, default=2, help="2=L2, 3=L3")
    ap.add_argument("--port", type=int, default=10060)
    args = ap.parse_args()

    tmp = os.path.join(PROJ, "scratch", "test_c6_flag.dsk")
    shutil.copy2(args.dsk, tmp)
    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
    time.sleep(1)
    subprocess.Popen([EMU, "--vo", "null", "--ao", "null", "--machine", "CPC6128",
                      "--enable-dsk", "--dsk-file", tmp,
                      "--enable-remoteprotocol", "--remoteprotocol-port", str(args.port)],
                     cwd=os.path.dirname(EMU),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = socket.socket()
    s.settimeout(5)
    for _ in range(40):
        try:
            s.connect(("127.0.0.1", args.port))
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise SystemExit("no connect")

    def cmd(c, wait=0.1):
        s.sendall(c.encode("latin1") + b"\r\n")
        time.sleep(wait)
        buf = b""
        while True:
            try:
                d = s.recv(65536)
            except socket.timeout:
                break
            if not d:
                break
            buf += d
            if buf.rstrip().endswith(b">"):
                break
        return buf.decode("latin1", errors="replace")

    def key(k, ev):
        cmd("send-keys-event %d %d" % (k, ev), 0.03)

    sym = {}
    for line in open(os.path.join(PROJ, "obj", "bluesb.map"), encoding="latin1"):
        m = re.match(r"^\s*([0-9A-Fa-f]{8})\s+(\S+)", line)
        if m:
            sym[m.group(2)] = int(m.group(1), 16)

    def mem(addr, n):
        out = cmd("read-memory %d %d" % (addr, n), 0.1)
        h = "".join(c for c in out if c in "0123456789abcdefABCDEF")
        return bytes.fromhex(h[:n * 2])

    t0 = time.time()
    while time.time() - t0 < 45:
        if "ready" in cmd("get-ocr", 0.5).lower():
            break
        time.sleep(1)
    time.sleep(1.5)

    # Força el fals positiu
    cmd("set-memory-zone 0", 0.3)
    before = mem(C6_5A00_PHYS, 1)[0]
    cmd("write-memory %d 195" % C6_5A00_PHYS, 0.3)  # 195 = 0xC3
    after = mem(C6_5A00_PHYS, 1)[0]
    cmd("set-memory-zone -1", 0.3)
    print("C6:0x5A00 abans=0x%02X, forçat=0x%02X" % (before, after))
    if after != 0xC3:
        print("FAIL: no s'ha pogut escriure 0xC3 a C6:0x5A00")
        return 1

    cmd("send-keys-string 70 run", 0.15)
    for i in range(2):
        key(133, 1); time.sleep(0.05); key(50, 1); time.sleep(0.05)
        key(50, 0); time.sleep(0.05); key(133, 0); time.sleep(0.05)
        if i == 0:
            cmd("send-keys-string 70 bluesb", 0.25)
    key(129, 1); time.sleep(0.12); key(129, 0)
    time.sleep(6)

    key(ord(str(args.level)), 1)
    t0 = time.time()
    while time.time() - t0 < 50:
        key(128, 1); key(128, 0); time.sleep(0.12)
        if mem(sym["_s_lv"], 1)[0] == 0xB0:
            break
    key(ord(str(args.level)), 0)

    # El magic=0xB0 es posa ABANS del repaint/moving_init; el jugador
    # (px8) apareix uns quants segons despres. Espera'l.
    pxv = 0
    t0 = time.time()
    while time.time() - t0 < 12:
        px = mem(sym["_s_px8"], 2)
        pxv = px[0] | (px[1] << 8)
        if pxv:
            break
        time.sleep(0.5)

    conv1 = mem(sym["_s_conveyor_phase"], 1)[0]
    # El crash del fals code_ready apareix quan corre el codi C6 (enemic);
    # deixa temps suficient perque es vegi.
    time.sleep(10.0)
    conv2 = mem(sym["_s_conveyor_phase"], 1)[0]
    magic = mem(sym["_s_lv"], 1)[0]
    canary = mem(0x3B40, 16)
    pc = re.search(r"PC=([0-9A-Fa-f]{4})", cmd("get-registers")).group(1)
    ok = (magic == 0xB0 and pxv != 0 and conv2 != conv1 and
          canary == b"\x55\xaa" * 8)
    print("level=%d magic=0x%02X px8=%d conv=%d->%d canari=%s PC=0x%s -> %s" % (
        args.level, magic, pxv, conv1, conv2, canary.hex(), pc,
        "OK" if ok else "FALLADA"))
    s.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
