#!/usr/bin/env python3
"""diag_sp.py - Arrenca un nivell i mostreja PC/SP cada segon durant N segons
per detectar quan es corromp la pila (SP fora de 0x3Bxx..0x3FFF).

Us: py -3 tools/diag_sp.py [nivell] [segons]
"""
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
DSK = os.path.join(PROJ, "bluesb.dsk")
LEVEL = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
PORT = 10020


def main():
    dsk = os.path.join(PROJ, "scratch", "diag_sp.dsk")
    shutil.copy2(DSK, dsk)
    subprocess.Popen([EMU, "--vo", "null", "--ao", "null", "--machine", "CPC6128",
                      "--enable-dsk", "--dsk-file", dsk,
                      "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                     cwd=os.path.dirname(EMU),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = socket.socket(); s.settimeout(5)
    for _ in range(30):
        try:
            s.connect(("127.0.0.1", PORT)); break
        except OSError:
            time.sleep(0.5)
    time.sleep(0.5)
    try:
        s.recv(4096)
    except socket.timeout:
        pass

    def cmd(c, delay=0.1):
        s.sendall(c.encode("latin1") + b"\r\n"); time.sleep(delay)
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

    def r8(a):
        for t in cmd("read-memory %d 1" % a, 0.03).split():
            if re.fullmatch(r"[0-9A-Fa-f]{2}", t):
                return int(t, 16)
        return 0

    def regs():
        r = cmd("get-registers")
        m = re.search(r"PC=([0-9A-Fa-f]{4})\s+SP=([0-9A-Fa-f]{4})", r)
        return (m.group(1), m.group(2)) if m else ("?", "?")

    t0 = time.time()
    while time.time() - t0 < 40:
        if "ready" in cmd("get-ocr", 0.5).lower():
            break
        time.sleep(1)
    cmd("send-keys-string 60 run"); time.sleep(0.2)
    for i in range(2):
        key(133, 1); time.sleep(0.03)
        key(50, 1); time.sleep(0.03)
        key(50, 0); time.sleep(0.03)
        key(133, 0); time.sleep(0.03)
        if i == 0:
            cmd("send-keys-string 60 bluesb"); time.sleep(0.2)
    key(129, 1); time.sleep(0.08); key(129, 0)
    key(ord(str(LEVEL + 1)), 1)
    t0 = time.time()
    while time.time() - t0 < 50:
        key(128, 1); time.sleep(0.1); key(128, 0); time.sleep(0.12)
        if r8(sym["_s_lv"]) == 0xB0:
            break
    key(ord(str(LEVEL + 1)), 0)
    print("nivell=%d magic=0x%02X" % (r8(sym["_g_map_level"]), r8(sym["_s_lv"])))

    # prem RIGHT perque passin coses (enemics, camera)
    key(143, 1)
    for i in range(SECS):
        time.sleep(1)
        pc, sp = regs()
        bad = not (0x3B40 <= int(sp, 16) <= 0x3FFF)
        print("  t=%2ds PC=0x%s SP=0x%s%s" % (i + 1, pc, sp, "   <-- SP FORA!" if bad else ""))
        if bad:
            cmd("save-screen %s" % os.path.join(PROJ, "scratch", "diag_sp_crash.bmp").replace("\\", "/"), 0.5)
            break
    key(143, 0)
    try:
        print("bt:", " ".join(cmd("get-stack-backtrace").split())[:160])
    except Exception:
        pass
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
