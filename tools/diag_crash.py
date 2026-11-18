#!/usr/bin/env python3
"""
diag_crash.py - Reprodueix la corrupcio de _DATA/canari amb watchpoints.

Arrenca un DSK, tria un nivell, espera que carregui i posa breakpoints
d'escriptura a:
  0x3A1E  s_lv.magic
  0x39DF  s_px8
  0x3B40  canari de pila (16 bytes)

Despres juga automaticament (RIGHT + salts) i, quan salta un watchpoint,
desa PC/SP/backtrace i el punt exacte.

Us:
  py -3 tools/diag_crash.py --level 2 --secs 90
  py -3 tools/diag_crash.py --level 3 --secs 90
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

CANARY = 0x3B40
MAGIC = 0x3A1E
PX8 = 0x39DF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsk", default=os.path.join(PROJ, "bluesb.dsk"))
    ap.add_argument("--level", type=int, default=2)
    ap.add_argument("--secs", type=int, default=90)
    ap.add_argument("--port", type=int, default=10040)
    ap.add_argument("--tag", default="crash")
    ap.add_argument("--wp", action="store_true", help="posa watchpoints (atura la CPU)")
    ap.add_argument("--jump", action="store_true", default=True, help="salta periodicament")
    ap.add_argument("--no-jump", dest="jump", action="store_false")
    ap.add_argument("--window", action="store_true",
                    help="video/audio SDL real (com l'usuari), no --vo/--ao null")
    args = ap.parse_args()

    tmp = os.path.join(PROJ, "scratch", "diag_%s.dsk" % args.tag)
    shutil.copy2(args.dsk, tmp)
    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
    time.sleep(1)
    emu_cmd = [EMU]
    if not args.window:
        emu_cmd += ["--vo", "null", "--ao", "null"]
    emu_cmd += ["--machine", "CPC6128", "--enable-dsk", "--dsk-file", tmp,
                "--enable-remoteprotocol", "--remoteprotocol-port", str(args.port)]
    subprocess.Popen(emu_cmd,
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

    def mem(addr, n):
        out = cmd("read-memory %d %d" % (addr, n), 0.08)
        h = "".join(c for c in out if c in "0123456789abcdefABCDEF")
        return bytes.fromhex(h[:n * 2])

    def r8(a):
        return mem(a, 1)[0]

    def regs():
        r = cmd("get-registers")
        m = re.search(r"PC=([0-9A-Fa-f]{4})\s+SP=([0-9A-Fa-f]{4})", r)
        return (m.group(1), m.group(2)) if m else ("?", "?")

    # BASIC + RUN"bluesb"
    t0 = time.time()
    while time.time() - t0 < 45:
        if "ready" in cmd("get-ocr", 0.5).lower():
            break
        time.sleep(1)
    # Deixa estabilitzar el prompt: si s'escriu RUN massa aviat, el BASIC
    # rep el text a mitges i dona "Syntax error" (boot perdut).
    time.sleep(2.0)
    cmd("send-keys-string 60 run", 0.15)
    for i in range(2):
        key(133, 1); key(50, 1); key(50, 0); key(133, 0)
        if i == 0:
            cmd("send-keys-string 60 bluesb", 0.2)
    key(129, 1); time.sleep(0.1); key(129, 0)
    # Deixa arrencar el front-end abans de mantenir la tecla de nivell:
    # si es prem massa aviat, l'event es perd i el joc carrega L1.
    time.sleep(2.0)

    # tria nivell
    key(ord(str(args.level)), 1)
    t0 = time.time()
    while time.time() - t0 < 50:
        key(128, 1); key(128, 0); time.sleep(0.12)
        if r8(MAGIC) == 0xB0:
            break
    key(ord(str(args.level)), 0)
    time.sleep(2.0)

    print("carregat: magic=0x%02X px8=%d conv=%d" % (
        r8(MAGIC), mem(PX8, 2)[0] | (mem(PX8 + 1, 1)[0] << 8),
        r8(sym["_s_conveyor_phase"])))
    print("canari inicial:", mem(CANARY, 16).hex())

    if args.wp:
        cmd("clear-membreakpoints", 0.2)
        cmd("set-membreakpoint %d 2 16" % CANARY, 0.2)
        cmd("set-membreakpoint %d 2 1" % MAGIC, 0.2)
        print("watchpoints posats (escriptura 0x3A1E i 0x3B40..0x3B4F)")
    else:
        cmd("clear-membreakpoints", 0.2)

    key(143, 1)  # RIGHT
    t0 = time.time()
    shot = 0
    last_conv = None
    stuck = 0
    stop = ""
    while time.time() - t0 < args.secs:
        if args.jump:
            key(145, 1); time.sleep(0.12); key(145, 0)
        time.sleep(0.5)
        pc, sp = regs()
        can = mem(CANARY, 16)
        conv = r8(sym["_s_conveyor_phase"])
        magic = r8(MAGIC)
        px = mem(PX8, 2)
        pxv = px[0] | (px[1] << 8)
        print("  t=%4.1fs PC=0x%s SP=0x%s magic=0x%02X conv=%d px8=%d canari=%s" % (
            time.time() - t0, pc, sp, magic, conv, pxv, can.hex()))
        if can != b"\x55\xaa" * 8:
            stop = "CANARI CORROMPUT"
            break
        if magic != 0xB0:
            stop = "MAGIC CORROMPUT"
            break
        if conv == last_conv:
            stuck += 1
            if stuck >= 4:
                stop = "FREEZE (conv aturat)"
                break
        else:
            stuck = 0
        last_conv = conv
        if time.time() - t0 > shot * 10:
            cmd("save-screen %s" % os.path.join(PROJ, "scratch", "crash_%s_%02d.bmp" % (
                args.tag, shot)).replace("\\", "/"), 0.5)
            shot += 1

    key(143, 0)
    if stop:
        print("  *** %s ***" % stop)
        pc, sp = regs()
        print("  PC=0x%s SP=0x%s" % (pc, sp))
        print("  canari:", mem(CANARY, 16).hex())
        print("  magic=0x%02X px8=%d py8=%d conv=%d" % (
            r8(MAGIC), mem(PX8, 2)[0] | (mem(PX8 + 1, 1)[0] << 8),
            mem(PX8 + 2, 2)[0] | (mem(PX8 + 3, 1)[0] << 8),
            r8(sym["_s_conveyor_phase"])))
        print("  bt:", " ".join(cmd("get-stack-backtrace").split())[:200])
        try:
            print("  disasm PC:")
            print(cmd("disassemble %d" % int(pc, 16), 0.5)[:900])
        except Exception as e:
            print("  disasm ERR", e)
        cmd("save-screen %s" % os.path.join(PROJ, "scratch", "crash_%s_final.bmp" % args.tag).replace("\\", "/"), 0.6)
    print("estat final: regs=%s" % (regs(),))
    print("canari final:", mem(CANARY, 16).hex())
    print("bt:", " ".join(cmd("get-stack-backtrace").split())[:220])
    try:
        print("disasm:", " | ".join(cmd("disassemble %d" % int(regs()[0], 16), 0.4).splitlines()[:8]))
    except Exception as e:
        print("disasm ERR", e)
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
