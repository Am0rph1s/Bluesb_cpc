#!/usr/bin/env python3
"""peek_enemy.py - Teleporta el jugador a una posicio i captura la pantalla
(sense moure's) per veure un enemic concret.

Us: py -3 tools/peek_enemy.py --at 4992,2816 --shots 4 [--level 2]
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
OUT = os.path.join(PROJ, "scratch", "audit")
PORT = 10014


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main():
    level = int(arg("--level", 2))
    at = arg("--at", "4992,2816").split(",")
    px8, py8 = int(at[0]), int(at[1])
    shots = int(arg("--shots", 4))
    os.makedirs(OUT, exist_ok=True)

    dsk = os.path.join(PROJ, "scratch", "peek_test.dsk")
    shutil.copy2(DSK, dsk)
    subprocess.Popen(
        [EMU, "--vo", "null", "--ao", "null", "--machine", "CPC6128",
         "--enable-dsk", "--dsk-file", dsk,
         "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
        cwd=os.path.dirname(EMU), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = socket.socket()
    s.settimeout(5)
    for _ in range(30):
        try:
            s.connect(("127.0.0.1", PORT))
            break
        except OSError:
            time.sleep(0.5)
    time.sleep(0.5)
    try:
        s.recv(4096)
    except socket.timeout:
        pass

    def cmd(c, delay=0.15):
        s.sendall(c.encode("latin1") + b"\r\n")
        time.sleep(delay)
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

    def r8(a):
        for t in cmd("read-memory %d 1" % a, 0.05).split():
            if re.fullmatch(r"[0-9A-Fa-f]{2}", t):
                return int(t, 16)
        return 0

    def r16(a):
        return r8(a) | (r8(a + 1) << 8)

    sym = {}
    for line in open(os.path.join(PROJ, "obj", "bluesb.map"), encoding="latin1"):
        m = re.match(r"^\s*([0-9A-Fa-f]{8})\s+(\S+)", line)
        if m:
            sym[m.group(2)] = int(m.group(1), 16)

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
    key(ord(str(level + 1)), 1)
    t0 = time.time()
    while time.time() - t0 < 60:
        key(128, 1); time.sleep(0.12); key(128, 0); time.sleep(0.15)
        if r8(sym["_s_lv"]) == 0xB0 and r16(sym["_s_px8"]):
            break
    key(ord(str(level + 1)), 0)
    time.sleep(1)

    for a, v in ((sym["_s_px8"], px8), (sym["_s_py8"], py8)):
        cmd("write-memory %d %d" % (a, v & 0xFF), 0.05)
        cmd("write-memory %d %d" % (a + 1, (v >> 8) & 0xFF), 0.05)
    time.sleep(1.5)
    print("jugador a px8=%d py8=%d (x=%d y=%d)" % (
        r16(sym["_s_px8"]), r16(sym["_s_py8"]),
        r16(sym["_s_px8"]) // 8, r16(sym["_s_py8"]) // 8))
    for i in range(shots):
        shot = os.path.join(OUT, "peek%d.bmp" % i)
        cmd("save-screen %s" % shot.replace("\\", "/"), 0.4)
        print("  %s (cam_x4=%d cam_row=%d)" % (
            shot, r16(sym["_g_cam_x4"]), r16(sym["_g_cam_row"])))
        time.sleep(float(arg("--wait", "0.8")))
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
