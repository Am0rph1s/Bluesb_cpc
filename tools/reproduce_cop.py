import os, sys, time, subprocess
from PIL import Image

sys.path.insert(0, r"C:\Projects\bluesb_cpc\tools")
from smoke_test import Zrcp, EMU, DSK, PORT, symbols, MAGIC

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

emu_proc = subprocess.Popen([EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
                            "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                           cwd=os.path.dirname(EMU))
time.sleep(3)

z = Zrcp(PORT)

# Wait BASIC
t0 = time.time()
while time.time() - t0 < 30:
    ocr = z.cmd("get-ocr", wait=0.5).lower()
    if "ready" in ocr or "basic" in ocr:
        break
    time.sleep(0.5)

def quote():
    z.cmd("send-keys-event %d 1" % Zrcp.KEY_SHIFT, wait=0.02)
    z.press(50, 0.05)
    z.cmd("send-keys-event %d 0" % Zrcp.KEY_SHIFT, wait=0.02)

z.keys("run")
quote()
z.keys("bluesb")
quote()
z.press(Zrcp.KEY_ENTER, 0.1)

sym = symbols()
t0 = time.time()
while time.time() - t0 < 45:
    magic = z.r8(sym["_s_lv"])
    px = z.r16(sym["_s_px8"])
    if magic == MAGIC and px != 0:
        break
    z.press(Zrcp.KEY_SPACE, 0.08)
    time.sleep(0.6)

print(f"L1 CARREGAT! px={z.r16(sym['_s_px8'])} py={z.r16(sym['_s_py8'])}")

# Ara fem que en Jake camini a la dreta (tecla Cursor Right = 131)
# cap al policia (que està a x=280)
print("Caminant cap a la dreta...")
z.cmd("send-keys-event 131 1", wait=0.02)

for f in range(250):
    time.sleep(0.04)
    px = z.r16(sym["_s_px8"]) >> 3
    py = z.r16(sym["_s_py8"]) >> 3
    regs = z.cmd("get-registers", wait=0.01).splitlines()
    reg_str = regs[0] if regs else ""
    if f % 10 == 0:
        print(f"frame {f:03d}: px={px} py={py} | {reg_str[:40]}")
    if "SP=bf" in reg_str.lower():
        print(f"\nCRASH DETECTAT al frame {f}! Registres: {reg_str}")
        for l in regs: print("  ", l)
        break

z.cmd("send-keys-event 131 0", wait=0.02)
z.shot("obj/cop_test.bmp")
z.s.close()
subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
