#!/usr/bin/env python3
"""diag_input.py - Arrenca un nivell, prem RIGHT i mira si el jugador es mou.
Tambe llegeix el comptador de frames (si avanca, el bucle principal corre).

Us: py -3 tools/diag_input.py [nivell]
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
PORT = 10018


def main():
    dsk = os.path.join(PROJ, "scratch", "diag.dsk")
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

    def cmd(c, delay=0.12):
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
        cmd("send-keys-event %d %d" % (k, ev), 0.05)

    sym = {}
    for line in open(os.path.join(PROJ, "obj", "bluesb.map"), encoding="latin1"):
        m = re.match(r"^\s*([0-9A-Fa-f]{8})\s+(\S+)", line)
        if m:
            sym[m.group(2)] = int(m.group(1), 16)

    def r8(a):
        for t in cmd("read-memory %d 1" % a, 0.05).split():
            if re.fullmatch(r"[0-9A-Fa-f]{2}", t):
                return int(t, 16)
        return 0

    def r16(n):
        a = sym[n]
        return r8(a) | (r8(a + 1) << 8)

    t0 = time.time()
    while time.time() - t0 < 40:
        if "ready" in cmd("get-ocr", 0.5).lower():
            break
        time.sleep(1)
    cmd("send-keys-string 60 run"); time.sleep(0.2)
    for i in range(2):
        key(133, 1); time.sleep(0.04)
        key(50, 1); time.sleep(0.04)
        key(50, 0); time.sleep(0.04)
        key(133, 0); time.sleep(0.04)
        if i == 0:
            cmd("send-keys-string 60 bluesb"); time.sleep(0.2)
    key(129, 1); time.sleep(0.1); key(129, 0)
    key(ord(str(LEVEL + 1)), 1)
    t0 = time.time()
    while time.time() - t0 < 50:
        key(128, 1); time.sleep(0.12); key(128, 0); time.sleep(0.15)
        if r8(sym["_s_lv"]) == 0xB0 and r16("_s_px8"):
            break
    key(ord(str(LEVEL + 1)), 0)
    time.sleep(1)
    print("nivell=%d px8=%d py8=%d cam_x4=%d cam_row=%d" % (
        r8(sym["_g_map_level"]), r16("_s_px8"), r16("_s_py8"),
        r16("_g_cam_x4"), r16("_g_cam_row")))
    k1 = r8(sym["_s_conveyor_phase"]) if "_s_conveyor_phase" in sym else -1
    print("conveyor_phase=%d" % k1)
    key(143, 1)  # RIGHT
    for i in range(5):
        time.sleep(1)
        print("  t=%ds px8=%d cam_x4=%d conveyor=%d" % (
            i + 1, r16("_s_px8"), r16("_g_cam_x4"),
            r8(sym["_s_conveyor_phase"]) if "_s_conveyor_phase" in sym else -1))
    key(143, 0)
    cmd("save-screen %s" % os.path.join(PROJ, "scratch", "diag_input.bmp").replace("\\", "/"), 0.5)
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
