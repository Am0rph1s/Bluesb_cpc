#!/usr/bin/env python3
"""
verify_phase0_emu.py - Test autònom amb ZEsarUX per a la Fase 0:
1. Executa bluesb.dsk a ZEsarUX.
2. Comprova la memòria del canari de pila a 0x3C00 via ZRCP (ha de ser 0xAA55).
3. Llegeix el valor de SP (pila) i calcula el marge real en execució.
4. Captura pantalla de verificació a scratch/phase0_running.png.
"""
import subprocess, time, os, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from zrcp import Zrcp

EMU = os.path.join(HERE, "ZEsarUX_windows-13.0", "zesarux.exe")
DSK = os.path.join(PROJ, "bluesb.dsk")

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [
    EMU,
    "--machine", "CPC6128",
    "--enable-dsk",
    "--dsk-file", DSK,
    "--enable-remoteprotocol",
    "--remoteprotocol-port", "10000"
]

proc = subprocess.Popen(cmd, cwd=os.path.join(HERE, "ZEsarUX_windows-13.0"))
time.sleep(3)

z = Zrcp()

print("Esperant prompt del BASIC...")
time.sleep(3)

# Executa run"bluesb"
z.send_string("run")
time.sleep(0.2)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.send_string("bluesb")
time.sleep(0.2)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.send_event(Zrcp.KEY_ENTER, 1); time.sleep(0.1); z.send_event(Zrcp.KEY_ENTER, 0)

print("Carregant el joc des de disc (esperant 18 segons)...")
for i in range(18):
    time.sleep(1.0)
    regs = z.cmd("get-registers", wait=0.05)
    for line in regs.splitlines():
        if "PC=" in line and (i % 4 == 0 or i == 17):
            print(f"  [{i+1}s] {line.strip()}")

print("\n--- COMPROVACIÓ DEL CANARI DE PILA (CP-0.1) ---")
# El canari està a 0x3C00 (16 bytes = 8 paraules de 0xAA55 -> en little-endian: 55 AA 55 AA ...)
canary_mem = z.read_mem(0x3C00, 16)
print(f"Memòria a 0x3C00 (16 bytes): {canary_mem.hex()}")
expected = bytes.fromhex("55aa" * 8)
if canary_mem == expected:
    print("[EXIT] Canari de pila 100% INTACTE a 0x3C00 (0xAA55 repetit 8 vegades)!")
else:
    print(f"[ERROR] Canari corromput! Esperat {expected.hex()}, obtingut {canary_mem.hex()}")

# Llegir SP actual
regs = z.cmd("get-registers", wait=0.1)
sp_val = None
for part in regs.split():
    if part.startswith("SP="):
        sp_val = int(part.split("SP=")[1], 16)
        print(f"Punter de pila actual: SP = 0x{sp_val:04X}")
        margin = sp_val - 0x3C00
        print(f"Marge net de pila sobre el canari (SP - 0x3C00): {margin} bytes!")

os.makedirs(os.path.join(PROJ, "scratch"), exist_ok=True)
bmp_path = os.path.join(PROJ, "scratch", "phase0_live.bmp")
png_path = os.path.join(PROJ, "scratch", "phase0_live.png")
z.cmd(f"save-screen {bmp_path}", wait=0.5)
if os.path.exists(bmp_path):
    im = Image.open(bmp_path)
    crop = im.crop((80, 50, 720, 480))
    crop.save(png_path)
    print(f"\nCaptura desada a {png_path} ({crop.size})")

z.close()
subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
print("\nVerificació ZEsarUX finalitzada amb èxit!")
