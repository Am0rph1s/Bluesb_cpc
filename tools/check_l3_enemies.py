#!/usr/bin/env python3
"""check_l3_enemies.py - Verifica a ZEsarUX els sprites d'enemics de L3.

Arrenca un ZEsarUX *propi* (port configurable, no toca l'altre que puguis
tenir obert), entra a la preso i captura pantalles per veure els enemics.

Us: py -3 tools/check_l3_enemies.py [--port 10012] [--level 2] [--steps 8]
"""
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
EMU = os.path.join(PROJ, "tools", "ZEsarUX_windows-13.0", "zesarux.exe")
DSK = os.path.join(PROJ, "bluesb.dsk")
OUT = os.path.join(PROJ, "scratch", "audit")


def arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def main():
    port = int(arg("--port", 10012))
    level = int(arg("--level", 2))
    steps = int(arg("--steps", 8))
    os.makedirs(OUT, exist_ok=True)

    # NO matem l'emulador que l'usuari tingui obert: engegem una instancia
    # nova amb una COPIA del disc (el fitxer original el te obert l'usuari).
    import shutil
    dsk_copy = os.path.join(PROJ, "scratch", "l3_test.dsk")
    shutil.copy2(DSK, dsk_copy)
    subprocess.Popen(
        [EMU, "--vo", "null", "--ao", "null",
         "--machine", "CPC6128", "--enable-dsk", "--dsk-file", dsk_copy,
         "--enable-remoteprotocol", "--remoteprotocol-port", str(port)],
        cwd=os.path.dirname(EMU), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = socket.socket()
    s.settimeout(5)
    for _ in range(30):
        try:
            s.connect(("127.0.0.1", port))
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
        if "ready" in cmd("get-ocr", 0.5).lower() or "basic" in cmd("get-ocr", 0.5).lower():
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
    print("Nivell carregat: g_map_level=%d px8=%d py8=%d" % (
        r8(sym["_g_map_level"]), r16(sym["_s_px8"]), r16(sym["_s_py8"])))

    for i in range(steps):
        if i == 0 and "--teleport" in sys.argv:
            x = int(arg("--teleport", "4846").split(",")[0])
            y = int(arg("--teleport", "4846").split(",")[1]) if "," in arg("--teleport", "") else 2960
            a = sym["_s_px8"]
            cmd("write-memory %d %d" % (a, x & 0xFF), 0.05)
            cmd("write-memory %d %d" % (a + 1, (x >> 8) & 0xFF), 0.05)
            b = sym["_s_py8"]
            cmd("write-memory %d %d" % (b, y & 0xFF), 0.05)
            cmd("write-memory %d %d" % (b + 1, (y >> 8) & 0xFF), 0.05)
            print("  teletransport a px8=%d py8=%d" % (x, y))
            time.sleep(1.0)
        key(143, 1); time.sleep(1.1); key(143, 0)
        time.sleep(0.4)
        shot = os.path.join(OUT, "l3_walk%d.bmp" % i)
        cmd("save-screen %s" % shot.replace("\\", "/"), 0.4)
        print("  pas %d: px8=%d py8=%d cam_x4=%d -> %s" % (
            i, r16(sym["_s_px8"]), r16(sym["_s_py8"]), r16(sym["_g_cam_x4"]), shot))

    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
