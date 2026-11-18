#!/usr/bin/env python3
"""
diag_level.py - Arrenca un DSK, tria un nivell i mostreja PC/SP/estat.

Sirveix per reproduir "congelacions" amb un DSK concret (actual o antic).

Us:
  py -3 tools/diag_level.py --dsk bluesb.dsk --level 2 --secs 45
  py -3 tools/diag_level.py --dsk scratch/l3_test.dsk --level 2 --secs 30 --fixed-wait 20
  py -3 tools/diag_level.py --dsk bluesb.dsk --level 2 --secs 60 --right

--level es 1..6 (tecla 1..6 al selector).
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


def connect(port, tries=40):
    s = socket.socket()
    s.settimeout(5)
    for _ in range(tries):
        try:
            s.connect(("127.0.0.1", port))
            return s
        except OSError:
            time.sleep(0.5)
    raise SystemExit("no puc connectar al port %d" % port)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsk", default=os.path.join(PROJ, "bluesb.dsk"))
    ap.add_argument("--level", type=int, default=2, help="1..6")
    ap.add_argument("--secs", type=int, default=40)
    ap.add_argument("--right", action="store_true", help="manté RIGHT durant el mostreig")
    ap.add_argument("--port", type=int, default=10030)
    ap.add_argument("--tag", default="diag")
    ap.add_argument("--snap", type=float, default=5.0, help="segons entre captures (0=cap)")
    ap.add_argument("--fixed-wait", type=float, default=0, help="no esperis magic=0xB0; espera fixa")
    ap.add_argument("--keep", action="store_true", help="deixa l'emulador engegat")
    args = ap.parse_args()

    tag = args.tag
    tmp = os.path.join(PROJ, "scratch", "diag_%s.dsk" % tag)
    shutil.copy2(args.dsk, tmp)
    print("DSK: %s -> %s" % (args.dsk, tmp))

    subprocess.Popen([EMU, "--vo", "null", "--ao", "null", "--machine", "CPC6128",
                      "--enable-dsk", "--dsk-file", tmp,
                      "--enable-remoteprotocol", "--remoteprotocol-port", str(args.port)],
                     cwd=os.path.dirname(EMU),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = connect(args.port)
    try:
        s.recv(4096)
    except Exception:
        pass

    def cmd(c, wait=0.12):
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

    def r8(a):
        for t in cmd("read-memory %d 1" % a, 0.04).split():
            if re.fullmatch(r"[0-9A-Fa-f]{2}", t):
                return int(t, 16)
        return -1

    def r16(name):
        a = sym[name]
        return r8(a) | (r8(a + 1) << 8)

    def regs():
        r = cmd("get-registers")
        m = re.search(r"PC=([0-9A-Fa-f]{4})\s+SP=([0-9A-Fa-f]{4})", r)
        return (m.group(1), m.group(2)) if m else ("?", "?")

    # Espera el prompt de BASIC
    t0 = time.time()
    while time.time() - t0 < 45:
        if "ready" in cmd("get-ocr", 0.5).lower():
            break
        time.sleep(1)

    # RUN"bluesb"
    cmd("send-keys-string 60 run", 0.15)
    for i in range(2):
        key(133, 1); key(50, 1); key(50, 0); key(133, 0)
        if i == 0:
            cmd("send-keys-string 60 bluesb", 0.2)
    key(129, 1); time.sleep(0.1); key(129, 0)
    time.sleep(2.0)
    if args.snap:
        cmd("save-screen %s" % os.path.join(PROJ, "scratch", "dl_%s_00_title.bmp" % tag).replace("\\", "/"), 0.6)

    # Compara el resident carregat amb el GAME.BIN actual: si no coincideix,
    # el DSK que s'esta executant es d'una altra compilacio.
    cur = open(os.path.join(PROJ, "obj", "GAME.BIN"), "rb").read()[:32]

    def membytes(addr, n):
        out = cmd("read-memory %d %d" % (addr, n), 0.25)
        h = "".join(c for c in out if c in "0123456789abcdefABCDEF")
        return bytes.fromhex(h[:n * 2])

    # Nivell: mantenim la tecla i premem SPACE fins que el joc arrenqui
    key(ord(str(args.level)), 1)
    if args.fixed_wait:
        for _ in range(int(args.fixed_wait / 0.25)):
            key(128, 1); key(128, 0); time.sleep(0.2)
        loaded = -1
    else:
        t0 = time.time()
        loaded = 0
        while time.time() - t0 < 50:
            key(128, 1); key(128, 0); time.sleep(0.12)
            m = r8(sym["_s_lv"]) if "_s_lv" in sym else -1
            if m == 0xB0:
                loaded = 1
                break
    key(ord(str(args.level)), 0)
    if args.snap:
        cmd("save-screen %s" % os.path.join(PROJ, "scratch", "dl_%s_01_loaded.bmp" % tag).replace("\\", "/"), 0.6)

    # Ara que el joc ja ha carregat, compara el resident amb el GAME.BIN actual.
    if loaded == 1:
        try:
            got = membytes(0x0100, 32)
            print("resident 0x0100 match GAME.BIN actual: %s" % ("SI" if got == cur else "NO"))
            if got != cur:
                print("  resident:", got.hex())
                print("  GAME.BIN:", cur.hex())
        except Exception as e:
            print("resident: no llegible", e)

    print("nivell=%d magic=0x%02X px8=%d py8=%d cam_x4=%d cam_row=%d" % (
        r8(sym["_g_map_level"]), r8(sym["_s_lv"]) & 0xFF, r16("_s_px8"), r16("_s_py8"),
        r16("_g_cam_x4"), r16("_g_cam_row")))

    if args.right:
        key(143, 1)

    next_snap = args.snap
    t0 = time.time()
    bad = 0
    for i in range(args.secs):
        time.sleep(1.0)
        pc, sp = regs()
        magic = r8(sym["_s_lv"]) & 0xFF
        conv = r8(sym["_s_conveyor_phase"]) if "_s_conveyor_phase" in sym else -1
        spi = int(sp, 16) if re.fullmatch(r"[0-9A-Fa-f]{4}", sp) else -1
        ok_sp = 0x3B40 <= spi <= 0x3FFF
        print("  t=%2ds PC=0x%s SP=0x%s magic=0x%02X conv=%3d px8=%d%s" % (
            i + 1, pc, sp, magic, conv, r16("_s_px8"),
            "   <-- SP FORA!" if not ok_sp else ""))
        if not ok_sp:
            bad += 1
        if args.snap and (time.time() - t0) >= next_snap:
            next_snap += args.snap
            cmd("save-screen %s" % os.path.join(PROJ, "scratch", "dl_%s_t%02d.bmp" % (tag, i + 1)).replace("\\", "/"), 0.4)
        if bad >= 3:
            break

    if args.right:
        key(143, 0)
    try:
        print("canari:", membytes(0x3B40, 16).hex())
    except Exception as e:
        print("canari ERR", e)
    try:
        print("bt:", " ".join(cmd("get-stack-backtrace").split())[:160])
    except Exception:
        pass

    if args.keep:
        print("emulador deixat al port %d (PID a matar manualment)" % args.port)
    else:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
