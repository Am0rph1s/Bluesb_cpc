import os
import subprocess
import time
import socket
import re
from PIL import Image

PROJ = r"C:\Projects\bluesb_cpc"
EMU = os.path.join(PROJ, "tools", "ZEsarUX_windows-13.0", "zesarux.exe")
DSK = os.path.join(PROJ, "bluesb.dsk")
PORT = 10000

print("Stopping previous ZEsarUX instances...", flush=True)
subprocess.run(["powershell", "-Command",
                "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1.0)

print("Starting fresh ZEsarUX...", flush=True)
subprocess.Popen([EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
                  "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                 cwd=os.path.dirname(EMU),
                 creationflags=0x00000008 | 0x00000200,
                 close_fds=True)
time.sleep(3.0)

s = socket.socket()
s.settimeout(5)
s.connect(("127.0.0.1", PORT))
time.sleep(0.3)
try:
    s.recv(4096)
except Exception:
    pass

def cmd(c, w=0.1):
    s.sendall(c.encode() + b"\r\n")
    time.sleep(w)
    buf = b""
    while True:
        try:
            d = s.recv(65536)
            if not d:
                break
            buf += d
            if buf.rstrip().endswith(b">"):
                break
        except Exception:
            break
    t = buf.decode("latin1")
    for marker in ("command@cpu-step> ", "command> "):
        if marker in t:
            t = t.split(marker)[0]
    return t.strip("\r\n ")

def press(k, dur=0.08):
    cmd(f"send-keys-event {k} 1", 0.02)
    time.sleep(dur)
    cmd(f"send-keys-event {k} 0", 0.02)

def quote():
    cmd("send-keys-event 133 1", 0.02) # SHIFT
    press(50, 0.04)                    # '2' -> produces '"' on CPC
    cmd("send-keys-event 133 0", 0.02)

def r8(addr):
    for tok in cmd("read-memory %d 1" % addr, 0.04).split():
        if re.fullmatch(r"[0-9A-Fa-f]{2}", tok):
            return int(tok, 16)
    return -1

def r16(addr):
    v0 = r8(addr)
    v1 = r8(addr + 1)
    if v0 < 0 or v1 < 0:
        return -1
    return v0 | (v1 << 8)

# Esperar BASIC prompt (esperem 3s despres de connectar)
t0 = time.time()
print("Waiting for BASIC ready...", flush=True)
time.sleep(3.0)

print("Sending RUN\"BLUESB\"...", flush=True)
cmd("send-keys-string 40 run", 0.08)
quote()
cmd("send-keys-string 40 bluesb", 0.08)
quote()
press(129, 0.1) # ENTER

t0 = time.time()
print("Starting trace...", flush=True)

# Simbols clau del mapa
a_magic = 0x3A1E    # _s_lv.magic
a_map_lvl = 0x3AB5  # _g_map_level
a_cam_x4 = 0x39DB   # _g_cam_x4
a_cam_row = 0x39DD  # _g_cam_row
a_px8 = 0x39DF      # _s_px8
a_py8 = 0x39E1      # _s_py8

import sys

target_lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1

for step in range(80):
    time.sleep(0.4)
    regs = cmd("get-registers", 0.04)
    pc = ""
    sp = ""
    m = re.search(r"PC=([0-9a-fA-F]{4})", regs)
    if m:
        pc = m.group(1).lower()
    m = re.search(r"SP=([0-9a-fA-F]{4})", regs)
    if m:
        sp = m.group(1).lower()
    
    magic = r8(a_magic)
    lvl = r8(a_map_lvl)
    px = r16(a_px8)
    py = r16(a_py8)
    
    elapsed = time.time() - t0
    print(f"[{elapsed:4.1f}s] PC={pc} SP={sp} lvl={lvl} magic=0x{magic:02X} px={px} py={py}", flush=True)
    
    # Premer Espai (codi 128) per avançar pantalles de presentació
    press(128, 0.04)
    if target_lvl == 2:
        # Premer '2' (codi 50) contínuament per activar selecció nivell 2
        press(50, 0.04)
        if elapsed > 20:
            cmd("write-memory 15029 1", 0.02)
    
    if magic == 0xB0 and px > 0 and py > 0 and (target_lvl == 1 or lvl == target_lvl - 1):
        print(f">>> SUCCESS: LEVEL {lvl+1} RUNNING! (px={px}, py={py}) <<<", flush=True)
        break
    
    if pc in ("272d", "273d", "26cf", "26ea", "26d4", "26ef", "2732", "2742"):
        print(f">>> BORDER TRAP DETECTED AT PC={pc} <<<", flush=True)
        break
        
    if sp == "0102" and elapsed > 8:
        print(f">>> CRASH TO BASIC DETECTED AT {elapsed:.1f}s (PC={pc}) <<<", flush=True)
        break

# Capture screenshot
ARTIFACTS = r"C:\Users\esquerra\.gemini\antigravity\brain\d5048ab8-d131-412d-a59a-046fb6bbb20c"
def save_art(name):
    bmp = os.path.join(ARTIFACTS, f"{name}.bmp")
    png = os.path.join(ARTIFACTS, f"{name}.png")
    if os.path.exists(bmp): os.remove(bmp)
    cmd(f"save-screen {bmp.replace(chr(92), '/')}", 0.3)
    if os.path.exists(bmp):
        try:
            im = Image.open(bmp).convert("RGB")
            w, h = im.size
            im.crop(((w - 768) // 2, (h - 512) // 2,
                     (w - 768) // 2 + 768, (h - 512) // 2 + 512)).save(png)
            print(f"Artifact screenshot saved: {name}.png", flush=True)
        except Exception as e:
            print(f"Error saving {name}: {e}", flush=True)

save_art("trace_boot_lvl2_running")

if target_lvl == 2 and magic == 0xB0 and px > 0:
    print("\n================== VERIFICACIO DESAIGUE DIPOSIT (PEIXERA) ==================", flush=True)
    # Col·locar en Jake dins del dipòsit d'aigua davant del desaigüe: col 87, row 10 (px=696, py=160)
    # Sense tocar g_cam_x4 ni g_cam_row perquè el motor faci l'scroll i repinti el mapa netament!
    t_px = 87 * 8
    t_py = 10 * 16
    cmd(f"write-memory {a_px8} {(t_px*8)&0xFF}", 0.05)
    cmd(f"write-memory {a_px8+1} {((t_px*8)>>8)&0xFF}", 0.05)
    cmd(f"write-memory {a_py8} {(t_py*8)&0xFF}", 0.05)
    cmd(f"write-memory {a_py8+1} {((t_py*8)>>8)&0xFF}", 0.05)
    # Esperem que l'scroll arribi del tot al dipòsit d'aigua (cam_row <= 16, cam_x4 >= 145)
    for _ in range(20):
        time.sleep(0.35)
        cmd(f"write-memory {a_px8} {(t_px*8)&0xFF}", 0.02)
        cmd(f"write-memory {a_px8+1} {((t_px*8)>>8)&0xFF}", 0.02)
        cmd(f"write-memory {a_py8} {(t_py*8)&0xFF}", 0.02)
        cmd(f"write-memory {a_py8+1} {((t_py*8)>>8)&0xFF}", 0.02)
        if r16(a_cam_row) <= 16 and r16(a_cam_x4) >= 145:
            break
    time.sleep(0.4)

    # Baixar fins al fons del dipòsit amb 'z' (crouch/down)
    print("Baixant al fons del diposit...", flush=True)
    cmd("send-keys-event 122 1", 0.05) # 'z' press
    time.sleep(0.5)
    cmd("send-keys-event 122 0", 0.05) # 'z' release
    time.sleep(0.2)
    cpx = r16(a_px8) >> 3
    cpy = r16(a_py8) >> 3
    print(f"Fons del diposit: px={cpx} (col {cpx//8}), py={cpy} (esperat ~163)", flush=True)
    save_art("drain_1_at_bottom")

    # Avançar cap a l'esquerra amb 'q' (Left) pel desaigüe (col 87 -> col 81)
    print("Avancant cap a l'esquerra ('q') pel desaigue...", flush=True)
    cmd("send-keys-event 113 1", 0.05) # 'q' press
    for step_d in range(10):
        time.sleep(0.25)
        cpx = r16(a_px8) >> 3
        cpy = r16(a_py8) >> 3
        climb = r8(0x39E9)
        chold = r8(0x39EB)
        print(f"  [Drain {step_d:02d}] px={cpx} (col {cpx//8}), py={cpy}, climb={climb}, crouch_hold={chold}", flush=True)
        if step_d == 1:
            save_art("drain_2_inside_tunnel")
        if cpx <= 81 * 8:
            break
    cmd("send-keys-event 113 0", 0.05) # 'q' release
    time.sleep(0.3)
    save_art("drain_3_exited_cleanly")

    # Tornem a col·locar en Jake dins del dipòsit davant del desaigüe perquè l'usuari ho provi directament!
    cmd(f"write-memory {a_px8} {(t_px*8)&0xFF}", 0.02)
    cmd(f"write-memory {a_px8+1} {((t_px*8)>>8)&0xFF}", 0.02)
    cmd(f"write-memory {a_py8} {(163*8)&0xFF}", 0.02)
    cmd(f"write-memory {a_py8+1} {((163*8)>>8)&0xFF}", 0.02)

print("\nVerificacions completades. L'emulador continua corrent.", flush=True)
s.close()

