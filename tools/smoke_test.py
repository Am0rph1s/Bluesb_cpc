#!/usr/bin/env python3
"""smoke_test.py - Fase 0.6: verificacio obligatoria abans de qualsevol canvi.

Fa dues coses independents:

  1) DSK: llegeix cada fitxer del disc amb la seva taula de sectors (CHS) i
     comprova el CRC contra el header generat (src/disk_tables.h i
     src/starter_tables.h). Tambe comprova que el cataleg sigui llegible.
  2) BOOT: arrenca ZEsarUX, espera el prompt de BASIC, executa RUN"BLUESB",
     prem SPACE fins que el nivell es carrega i comprova:
        - s_lv.magic == 0xB0  (el paquet de parametres s'ha carregat)
        - s_px8 != 0 i s_py8 != 0 (el jugador te posicio)
     Desa una captura a scratch/smoke_level.png.

Us:
    py -3 scratch/smoke_test.py            # DSK + BOOT
    py -3 scratch/smoke_test.py --dsk-only
    py -3 scratch/smoke_test.py --boot-only
    py -3 scratch/smoke_test.py --keep      # no tanca l'emulador al final

Codi de sortida: 0 = OK, 1 = FALLADA.
"""
import os
import re
import subprocess
import sys
import time
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, "tools"))

DSK = os.path.join(PROJ, "bluesb.dsk")
MAP = os.path.join(PROJ, "obj", "bluesb.map")
EMU = os.path.join(PROJ, "tools", "ZEsarUX_windows-13.0", "zesarux.exe")
PORT = 10010
MAGIC = 0xB0
SECTOR = 512


# ---------------------------------------------------------------- utilitats
def crc16_ccitt(data, init=0xFFFF):
    """Mateix CRC que fdc_crc16() del joc (CRC-16/CCITT-FALSE)."""
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_chs(text, name):
    """Retorna la llista de parelles (track, sector_id) de g_<name>_chs[]."""
    m = re.search(r"g_%s_chs\[(\d+)\]\s*=\s*\{([^}]*)\}" % name, text, re.S)
    if not m:
        return None
    vals = [int(x, 16) for x in m.group(2).replace("\n", " ").split(",") if x.strip()]
    return list(zip(vals[0::2], vals[1::2]))


def parse_defines(text):
    return {k: int(v, 16) for k, v in
            re.findall(r"#define ((?:CRC_|GAME_)\w+) 0x([0-9A-Fa-f]+)", text)}


def parse_ondisk(text, name):
    """Mida declarada a DiskFileDesc g_file_<name> = { ondisk_bytes, n, chs }."""
    m = re.search(r"g_file_%s\s*=\s*\{\s*(\d+)\s*,\s*(\d+)" % name, text)
    return int(m.group(1)) if m else None


def symbols():
    out = {}
    for m in re.finditer(r"^\s*([0-9A-Fa-f]{8})\s+(\S+)", read_text(MAP), re.M):
        out[m.group(2)] = int(m.group(1), 16)
    return out


# --------------------------------------------------------------------- DSK
def check_dsk():
    from dskutil import DskPatcher

    print("== DSK ==", flush=True)
    ok = True
    dt = read_text(os.path.join(PROJ, "src", "disk_tables.h"))
    st = read_text(os.path.join(PROJ, "src", "starter_tables.h"))
    crcs = parse_defines(dt)
    crcs.update(parse_defines(st))

    files = [("jake", "CRC_JAKE"), ("elwood", "CRC_ELWOOD"),
             ("front", "CRC_FRONT"), ("game", "GAME_CRC")]

    dsk = DskPatcher(DSK)

    # Cataleg: noms llegibles a les entrades del directori (4 sectors).
    cat = bytes()
    for sid in (0xC1, 0xC2, 0xC3, 0xC4):
        s = dsk.read_sector(0, sid)
        if s is None:
            print("  [KO] sector de directori 0x%02X il.legible" % sid)
            return False
        cat += s
    names = []
    for i in range(64):
        e = cat[i * 32:(i + 1) * 32]
        if e[0] == 0x00:
            nm = bytes(e[1:9]).decode("latin1").strip()
            ex = bytes(e[9:12]).decode("latin1").strip()
            if nm:
                names.append(nm + "." + ex)
    print("  cataleg: %s" % ", ".join(names) if names else "  cataleg: BUIT")
    if "BLUESB.BIN" not in names or "GAME.BIN" not in names:
        print("  [KO] el cataleg no te BLUESB.BIN / GAME.BIN")
        ok = False

    # Validacio de nivells via taula LVLCHS de MUSBANK
    mb_raw = None
    for i in range(64):
        e = cat[i * 32:(i + 1) * 32]
        if e[0] == 0x00:
            nm = bytes(e[1:9]).decode("latin1").strip()
            ex = bytes(e[9:12]).decode("latin1").strip()
            if nm == "MUSBANK" and ex == "BIN":
                mb_blocs = [b for b in e[16:32] if b]
                m_data = bytearray()
                for b in mb_blocs:
                    for t, sid in dsk.bloc_to_ts(b):
                        s = dsk.read_sector(t, sid)
                        if s: m_data += s
                mb_raw = bytes(m_data[128:])
                break

    LVLCHS_MB_OFF = 0x1D00
    if mb_raw and len(mb_raw) >= LVLCHS_MB_OFF + 4 and mb_raw[LVLCHS_MB_OFF:LVLCHS_MB_OFF + 2] == b"LV":
        lv_raw = mb_raw[LVLCHS_MB_OFF:]
        n_lvl = lv_raw[3]
        for lvl in range(n_lvl):
            for typ, suffix in ((0, "WORLD"), (1, "ENEMI"), (2, "C1")):
                off = 4 + (lvl * 3 + typ) * 5
                ondisk, sec, crc = struct.unpack("<HBH", lv_raw[off:off+5])
                if sec == 0:
                    continue
                pool_off = 4 + n_lvl * 3 * 5 + lvl * (56 + 32 + 32) + (0 if typ == 0 else (56 if typ == 1 else 88))
                chs_bytes = lv_raw[pool_off:pool_off + sec * 2]
                chs = list(zip(chs_bytes[0::2], chs_bytes[1::2]))
                data = bytearray()
                for t, sid in chs:
                    s = dsk.read_sector(t, sid)
                    if s: data += s
                payload = bytes(data[128:ondisk])
                got = crc16_ccitt(payload)
                label = "l%d%s" % (lvl + 1, suffix.lower())
                if got != crc:
                    print("  [KO] %-8s CRC 0x%04X != LVLCHS 0x%04X" % (label, got, crc))
                    ok = False
                else:
                    print("  [OK] %-8s %d sectors, %d B, CRC 0x%04X (LVLCHS)" % (label, sec, ondisk - 128, got))

    for key, crc_key in files:
        src = st if key == "game" else dt
        chs = parse_chs(src, key)
        want = crcs.get(crc_key)
        size = parse_ondisk(src, key)
        if chs is None or want is None or size is None:
            print("  [KO] %-8s sense taula CHS, mida o CRC al header" % key)
            ok = False
            continue
        data = bytearray()
        for t, sid in chs:
            s = dsk.read_sector(t, sid)
            if s is None:
                print("  [KO] %-8s sector il.legible (pista %d, 0x%02X)" % (key, t, sid))
                ok = False
                break
            data += s
        else:
            # data = capcalera AMSDOS (128 B) + payload + farciment 0xE5
            payload = bytes(data[128:size])
            got = crc16_ccitt(payload)
            if len(data) < size:
                print("  [KO] %-8s nomes %d B al disc (calen %d)" % (key, len(data), size))
                ok = False
            elif got != want:
                print("  [KO] %-8s CRC 0x%04X != header 0x%04X" % (key, got, want))
                ok = False
            else:
                print("  [OK] %-8s %d sectors, %d B, CRC 0x%04X" %
                      (key, len(chs), size - 128, got))
    return ok


# -------------------------------------------------------------------- BOOT
class Zrcp:
    """Client minim del protocol remot de ZEsarUX (evita dependre de tools/)."""

    KEY_ENTER, KEY_SPACE, KEY_SHIFT = 129, 128, 133

    def __init__(self, port):
        import socket
        self.s = socket.socket()
        self.s.settimeout(10)
        self.s.connect(("127.0.0.1", port))
        time.sleep(0.2)
        try:
            self.s.recv(4096)
        except Exception:
            pass

    def cmd(self, line, wait=0.15):
        self.s.sendall(line.encode() + b"\r\n")
        time.sleep(wait)
        buf = b""
        try:
            while True:
                d = self.s.recv(65536)
                if not d:
                    break
                buf += d
                if buf.rstrip().endswith(b">"):
                    break
        except Exception:
            pass
        t = buf.decode("latin1")
        for marker in ("command@cpu-step> ", "command> "):
            if marker in t:
                t = t.split(marker)[0]
        return t.strip("\r\n ")

    def r8(self, addr):
        for tok in self.cmd("read-memory %d 1" % addr, wait=0.05).split():
            if re.fullmatch(r"[0-9A-Fa-f]{2}", tok):
                return int(tok, 16)
        return -1

    def r16(self, addr):
        v = self.r8(addr) | (self.r8(addr + 1) << 8)
        return v - 65536 if v >= 32768 else v

    def press(self, key, dur=0.12):
        self.cmd("send-keys-event %d 1" % key, wait=0.02)
        time.sleep(dur)
        self.cmd("send-keys-event %d 0" % key, wait=0.02)

    def keys(self, text):
        self.cmd("send-keys-string 40 %s" % text, wait=0.15)

    def shot(self, path):
        path = os.path.abspath(path)
        if os.path.exists(path):
            os.remove(path)
        self.cmd("save-screen %s" % path.replace("\\", "/"), wait=0.5)
        return os.path.exists(path)


def check_boot(keep=False):
    from PIL import Image

    print("== BOOT ==", flush=True)
    subprocess.run(["powershell", "-Command",
                    "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
    time.sleep(1)
    subprocess.Popen([EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
                      "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                     cwd=os.path.dirname(EMU))
    time.sleep(4)
    z = Zrcp(PORT)

    # 1. Esperar BASIC (no un sleep fix: el boot del disc pot trigar).
    t0 = time.time()
    ready = False
    while time.time() - t0 < 40:
        ocr = z.cmd("get-ocr", wait=0.5).lower()
        if "ready" in ocr or "basic" in ocr:
            ready = True
            break
        time.sleep(1.0)
    print("  BASIC prompt: %s (%.1fs)" % ("OK" if ready else "NO", time.time() - t0),
          flush=True)

    # 2. RUN"BLUESB"  ('"' = SHIFT+2, amb SHIFT premut mentre es prem el 2)
    def quote():
        z.cmd("send-keys-event %d 1" % Zrcp.KEY_SHIFT, wait=0.02)
        z.press(50, 0.05)
        z.cmd("send-keys-event %d 0" % Zrcp.KEY_SHIFT, wait=0.02)

    z.keys("run")
    quote()
    z.keys("bluesb")
    quote()
    z.press(Zrcp.KEY_ENTER, 0.1)

    # 3. Esperar que el nivell carregui (s_lv.magic i posicio del jugador).
    sym = symbols()
    a_magic = sym.get("_s_lv", 0)
    a_px8, a_py8 = sym.get("_s_px8", 0), sym.get("_s_py8", 0)
    a_bank = sym.get("_g_bank", 0)
    print("  simbols: s_lv=0x%04X s_px8=0x%04X s_py8=0x%04X" % (a_magic, a_px8, a_py8),
          flush=True)

    t0 = time.time()
    magic = px = py = 0
    while time.time() - t0 < 90:
        magic = z.r8(a_magic) if a_magic else 0
        px = z.r16(a_px8) if a_px8 else 0
        py = z.r16(a_py8) if a_py8 else 0
        if magic == MAGIC and px != 0 and py != 0:
            break
        z.press(Zrcp.KEY_SPACE, 0.12)
        time.sleep(1.2)

    shot_bmp = os.path.join(HERE, "smoke_level.bmp")
    shot_png = os.path.join(HERE, "smoke_level.png")
    if z.shot(shot_bmp):
        im = Image.open(shot_bmp).convert("RGB")
        w, h = im.size
        im.crop(((w - 768) // 2, (h - 512) // 2,
                 (w - 768) // 2 + 768, (h - 512) // 2 + 512)).save(shot_png)

    # Posicio esperada: la del paquet (s_lv.start_px/start_py, a +34/+36).
    spx = z.r16(a_magic + 34) if a_magic else 0
    spy = z.r16(a_magic + 36) if a_magic else 0
    ok = (magic == MAGIC and px != 0 and py != 0 and
          abs(px - spx * 8) <= 64 and abs(py - spy * 8) <= 1024)
    print("  magic=0x%02X px8=%d py8=%d (esperat %d,%d) bank=0x%02X  -> %s" % (
        magic & 0xFF, px, py, spx * 8, spy * 8,
        z.r8(a_bank) & 0xFF if a_bank else 0, "OK" if ok else "FALLADA"), flush=True)
    if not ok:
        regs = z.cmd("get-registers", wait=0.3)
        m = re.search(r"PC=(\w+)", regs)
        print("  PC: %s" % (m.group(1) if m else "?"), flush=True)
        print("  pila: %s" % z.cmd("get-stack-backtrace", wait=0.3), flush=True)
        print("  captura: %s" % shot_png, flush=True)

    # Segona captura 3 s despres (sense input): detecta si algu esborra el HUD.
    time.sleep(3.0)
    bmp2 = os.path.join(HERE, "smoke_level2.bmp")
    png2 = os.path.join(HERE, "smoke_level2.png")
    if z.shot(bmp2):
        im = Image.open(bmp2).convert("RGB")
        w, h = im.size
        im.crop(((w - 768) // 2, (h - 512) // 2,
                 (w - 768) // 2 + 768, (h - 512) // 2 + 512)).save(png2)

    if not keep:
        subprocess.run(["powershell", "-Command",
                        "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
    return ok

def main():
    args = sys.argv[1:]
    keep = "--keep" in args
    ok = True
    if "--boot-only" not in args:
        ok = check_dsk() and ok
    if "--dsk-only" not in args:
        ok = check_boot(keep) and ok
    print("\nRESULTAT: %s" % ("OK" if ok else "FALLADA"), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
