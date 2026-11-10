import os
import re
import socket
import subprocess
import sys
import time
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
EMU = os.path.join(HERE, "ZEsarUX_windows-13.0", "zesarux.exe")
DSK = os.path.join(PROJ, "bluesb.dsk")
PORT = 10000

class Zrcp:
    KEY_ENTER, KEY_SPACE, KEY_SHIFT = 129, 128, 133

    def __init__(self, port):
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
        self.cmd(f"send-keys-event {key} 1", wait=0.02)
        time.sleep(dur)
        self.cmd(f"send-keys-event {key} 0", wait=0.02)

    def keys(self, text):
        self.cmd(f"send-keys-string 40 {text}", wait=0.15)

    def shot(self, path):
        path = os.path.abspath(path)
        if os.path.exists(path):
            os.remove(path)
        self.cmd(f"save-screen {path.replace('\\', '/')}", wait=0.5)
        return os.path.exists(path)

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass

def symbols():
    syms = {}
    p = os.path.join(PROJ, "obj", "bluesb.map")
    if not os.path.exists(p): return syms
    with open(p, "r", errors="replace") as f:
        for line in f:
            m = re.match(r"\s+([0-9A-Fa-f]{8})\s+(_\w+)", line)
            if m:
                syms[m.group(2)] = int(m.group(1), 16)
    return syms

def test_single_level(lvl_idx, key_char):
    lvl_num = lvl_idx + 1
    print(f"\n==========================================")
    print(f"=== TEST NIVELL {lvl_num} (Key '{key_char}') ===")
    print(f"==========================================")
    subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
    time.sleep(1.0)

    cmd = [
        EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
        "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)
    ]
    p = subprocess.Popen(cmd, cwd=os.path.dirname(EMU))
    time.sleep(4.0)

    z = Zrcp(PORT)

    t0 = time.time()
    ready = False
    while time.time() - t0 < 30:
        ocr = z.cmd("get-ocr", wait=0.5).lower()
        if "ready" in ocr or "basic" in ocr:
            ready = True
            break
        time.sleep(1.0)
    if not ready:
        print("ERROR: BASIC no ha respost")
        z.close()
        return False, "NO_BASIC"

    def quote():
        z.cmd(f"send-keys-event {Zrcp.KEY_SHIFT} 1", wait=0.02)
        z.press(50, 0.05)
        z.cmd(f"send-keys-event {Zrcp.KEY_SHIFT} 0", wait=0.02)

    z.keys("run")
    quote()
    z.keys("bluesb")
    quote()
    z.press(Zrcp.KEY_ENTER, 0.1)

    sym = symbols()
    a_magic = sym.get("_s_lv", 0)
    a_px8, a_py8 = sym.get("_s_px8", 0), sym.get("_s_py8", 0)
    a_lvl = sym.get("_g_map_level", 0)

    key_code = ord(key_char)
    if key_char != '1':
        z.cmd(f"send-keys-event {key_code} 1", wait=0.02)

    t0 = time.time()
    magic = px = py = lvl = 0
    loaded = False
    while time.time() - t0 < 60:
        magic = z.r8(a_magic) if a_magic else 0
        px = z.r16(a_px8) if a_px8 else 0
        py = z.r16(a_py8) if a_py8 else 0
        lvl = z.r8(a_lvl) if a_lvl else 0
        if magic == 0xB0 and px != 0 and py != 0:
            loaded = True
            break
        z.press(Zrcp.KEY_SPACE, 0.12)
        time.sleep(1.0)

    if key_char != '1':
        z.cmd(f"send-keys-event {key_code} 0", wait=0.02)
    time.sleep(0.5)

    scr_bmp = os.path.join(PROJ, f"verify_lvl{lvl_num}.bmp")
    scr_png = os.path.join(PROJ, f"verify_lvl{lvl_num}.png")
    if z.shot(scr_bmp):
        Image.open(scr_bmp).save(scr_png)

    # Monitoritzacio del bucle durant 2 segons
    time.sleep(2.0)
    regs = z.cmd("get-registers", wait=0.2)
    m = re.search(r"PC=(\w+)\s+SP=(\w+)", regs)
    pc = m.group(1) if m else "?"
    sp = m.group(2) if m else "?"

    # Lectura del tile de caixa des de CRATE_FLY_FRAME (0x7A20 a C7)
    # L'estat es comprova mirant si PC esta al bucle i no en crash
    is_frozen = (pc.lower().startswith("3f") or sp.lower() in ("0000", "0007"))
    status = "FROZEN" if is_frozen else ("OK" if loaded else "TIMEOUT")
    print(f"Nivell {lvl_num}: status={status}, lvl_var={lvl}, px8={px}, py8={py}, PC={pc}, SP={sp}")

    z.close()
    return not is_frozen and loaded, status

def main():
    levels = [
        (0, '1'),
        (1, '2'),
        (2, '3'),
        (3, '4'),
        (4, '5'),
        (5, '6')
    ]
    results = {}
    for idx, key in levels:
        ok, stat = test_single_level(idx, key)
        results[idx + 1] = stat

    print("\n================== RESUM ==================")
    for lvl, stat in results.items():
        print(f"Nivell {lvl}: {stat}")

if __name__ == "__main__":
    main()
