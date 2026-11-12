#!/usr/bin/env python3
"""verify_palettes.py - Comprova al ZEsarUX que la paleta del nivell arriba a la
pantalla (palette_table) i que el jugador manté el contracte de colors.

Per a cada nivell 1..6:
  - arrenca un ZEsarUX nou (el hard-reset-cpu no reinicia el firmware i la
    drecera de nivell deixa de funcionar),
  - llança el joc amb la drecera del nivell,
  - llegeix els 16 bytes de palette_table (la paleta que hi ha a la VRAM),
  - compara amb LEVEL_PALETTES[nivell] (paleta esperada),
  - comprova els pens del contracte d'identitat (0=blanc, 1=pell, 4=blau marí,
    11=negre) i captura la pantalla.

Us: py -3 tools/verify_palettes.py [nivell ...]
"""
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from graphics_tool import HW_TO_COLOR  # noqa: E402
from palette_fit import load_pack_level_palettes  # noqa: E402

EMU = os.path.join(PROJ, "tools", "ZEsarUX_windows-13.0", "zesarux.exe")
DSK = os.path.join(PROJ, "bluesb.dsk")
MAP = os.path.join(PROJ, "obj", "bluesb.map")
PORT = 10010
CONTRACT = {0: 0x4B, 1: 0x47, 4: 0x44, 11: 0x54}


def symbols():
    out = {}
    for line in open(MAP, "r", encoding="latin1"):
        m = re.match(r"^\s*([0-9A-Fa-f]{8})\s+(\S+)", line)
        if m:
            out[m.group(2)] = int(m.group(1), 16)
    return out


def start_emu():
    """Engega un ZEsarUX nou i connecta el protocol ZRCP."""
    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
    time.sleep(1)
    proc = subprocess.Popen(
        [EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
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
    s.recv(4096)
    return proc, s


class Zr:
    """Client ZRCP minim."""

    def __init__(self, sock):
        self.s = sock

    def cmd(self, c, delay=0.1):
        self.s.sendall(c.encode("latin1") + b"\r\n")
        time.sleep(delay)
        buf = b""
        while True:
            try:
                d = self.s.recv(65536)
            except socket.timeout:
                break
            if not d:
                break
            buf += d
            if buf.rstrip().endswith(b">"):
                break
        return buf.decode("latin1", errors="replace")

    def key(self, k, ev):
        self.cmd("send-keys-event %d %d" % (k, ev), 0.05)

    def r8(self, addr):
        for tok in self.cmd("read-memory %d 1" % addr, 0.05).split():
            if re.fullmatch(r"[0-9A-Fa-f]{2}", tok):
                return int(tok, 16)
        return 0

    def r16(self, addr):
        return self.r8(addr) | (self.r8(addr + 1) << 8)


def main():
    levels = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(6))
    pals = load_pack_level_palettes()
    sym = symbols()
    pal_addr = sym.get("_palette_table") or sym.get("palette_table")
    a_magic = sym.get("_s_lv")
    a_px8 = sym.get("_s_px8")
    a_py8 = sym.get("_s_py8")
    print("palette_table a 0x%04X" % pal_addr)

    rc = 0
    for lid in levels:
        proc, sock = start_emu()
        z = Zr(sock)
        print("\n=== Nivell %d ===" % (lid + 1))

        # Espera el prompt de BASIC abans d'escriure la comanda
        t0 = time.time()
        ready = False
        while time.time() - t0 < 40:
            ocr = z.cmd("get-ocr", 0.5).lower()
            if "ready" in ocr or "basic" in ocr:
                ready = True
                break
            time.sleep(1.0)
        print("  prompt BASIC: %s" % ("OK" if ready else "NO"))

        z.cmd("send-keys-string 60 run"); time.sleep(0.2)
        for i in range(2):                      # les comilles: Shift + '2'
            z.key(133, 1); time.sleep(0.04)
            z.key(50, 1); time.sleep(0.04)
            z.key(50, 0); time.sleep(0.04)
            z.key(133, 0); time.sleep(0.04)
            if i == 0:
                z.cmd("send-keys-string 60 bluesb"); time.sleep(0.2)
        z.key(129, 1); time.sleep(0.1); z.key(129, 0)

        # La drecera de nivell es llegeix UN COP a la sortida del menu frontal
        # (src/main.c:972): cal mantenir la tecla premuda fins que el nivell
        # carregui (es solta quan magic==0xB0).
        z.key(ord(str(lid + 1)), 1)
        t0 = time.time()
        while time.time() - t0 < 60:
            z.key(128, 1); time.sleep(0.12); z.key(128, 0)
            time.sleep(0.15)
            if z.r8(a_magic) == 0xB0 and z.r16(a_px8) and z.r16(a_py8):
                break
        z.key(ord(str(lid + 1)), 0)
        time.sleep(1.5)

        got = [z.r8(pal_addr + i) for i in range(16)]
        exp = pals[lid]
        print("  paleta a la VRAM : %s" % " ".join("%02X" % v for v in got))
        print("  paleta esperada  : %s" % " ".join("%02X" % v for v in exp))
        print("  %s" % ("IDENTICA" if got == exp else "DIFERENT"))
        if got != exp:
            rc = 1
        for pen, hw in sorted(CONTRACT.items()):
            good = got[pen] == hw
            print("    contracte pen %-2d: %02X %-14s %s" % (
                pen, got[pen], HW_TO_COLOR[got[pen]]["name"],
                "OK" if good else "FALLA (hauria de ser %02X)" % hw))
            if not good:
                rc = 1
        shot = os.path.join(PROJ, "scratch", "palette_fit", "L%d_screen.bmp" % (lid + 1))
        z.cmd("save-screen %s" % shot.replace("\\", "/"), 0.5)
        print("  captura: %s" % shot)
        sock.close()

    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
    return rc


if __name__ == "__main__":
    sys.exit(main())
