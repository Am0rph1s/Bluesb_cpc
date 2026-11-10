import os, time, socket, subprocess, re, shutil
from PIL import Image

PORT = 10019
EMU = os.path.abspath(r"tools\ZEsarUX_windows-13.0\zesarux.exe")
DSK = os.path.abspath(r"bluesb.dsk")
MAP = os.path.abspath(r"obj\bluesb.map")

def get_sym(name):
    with open(MAP) as f:
        for l in f:
            m = re.match(r"\s+([0-9A-Fa-f]{8})\s+(_" + name + r")\b", l)
            if m: return int(m.group(1), 16)
    return None

sym_magic = get_sym("s_lv")
sym_px = get_sym("s_px8")
sym_decomp = get_sym("g_enemy_decomp_cnt")

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(0.5)

p = subprocess.Popen([EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
                     "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                    cwd=os.path.dirname(EMU))
time.sleep(3.0)

s = socket.socket()
s.settimeout(10)
s.connect(("127.0.0.1", PORT))
time.sleep(0.2)
s.recv(4096)

def c(line):
    s.sendall(line.encode("latin1") + b"\r\n")
    time.sleep(0.04)
    buf = b""
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b">"): break
    return buf.decode("latin1", errors="replace")

def r8(addr):
    out = c("read-memory %d 1" % addr)
    for tok in out.split():
        if re.fullmatch(r"[0-9A-Fa-f]{2}", tok): return int(tok, 16)
    return -1

def r16(addr):
    v = r8(addr) | (r8(addr + 1) << 8)
    return v - 65536 if v >= 32768 else v

# Esperar BASIC ready
t0 = time.time()
while time.time() - t0 < 15:
    if "ready" in c("get-ocr").lower(): break
    time.sleep(0.5)

# run"bluesb"
c("send-keys-string 60 run")
s.sendall(b"send-keys-event 133 1\r\nsend-keys-event 50 1\r\nsend-keys-event 50 0\r\nsend-keys-event 133 0\r\n")
time.sleep(0.05)
c("send-keys-string 60 bluesb")
s.sendall(b"send-keys-event 133 1\r\nsend-keys-event 50 1\r\nsend-keys-event 50 0\r\nsend-keys-event 133 0\r\nsend-keys-event 129 1\r\nsend-keys-event 129 0\r\n")

# Premem espai fins carregar Nivell 1
t0 = time.time()
loaded = False
while time.time() - t0 < 60:
    magic = r8(sym_magic) if sym_magic else 0
    px = r16(sym_px) if sym_px else 0
    if magic == 0xB0 and px != 0:
        loaded = True
        break
    s.sendall(b"send-keys-event 128 1\r\n")
    time.sleep(0.08)
    s.sendall(b"send-keys-event 128 0\r\n")
    time.sleep(1.0)

time.sleep(1.5)
out_bmp = os.path.abspath("obj/live_l1.bmp").replace("\\", "/")
out_png = os.path.abspath("obj/live_l1.png")
c("save-screen " + out_bmp)
if os.path.exists("obj/live_l1.bmp"):
    Image.open("obj/live_l1.bmp").save(out_png)
    shutil.copyfile(out_png, "C:/Users/esquerra/.gemini/antigravity/brain/d5048ab8-d131-412d-a59a-046fb6bbb20c/live_l1.png")

decomp = r8(sym_decomp) if sym_decomp else -1
print(f"L1 loaded: {loaded}, px={r16(sym_px)}, py={r16(sym_px+2)}, enemy_decomp_cnt={decomp}")
s.close()
subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
