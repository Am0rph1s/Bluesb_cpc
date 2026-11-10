import os, sys, time, subprocess

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

def w8(addr, val):
    z.cmd(f"write-memory {addr} {val & 0xFF}", wait=0.02)

def w16(addr, val):
    w8(addr, val & 0xFF)
    w8(addr + 1, (val >> 8) & 0xFF)

print(f"L1 CARREGAT! px={z.r16(sym['_s_px8']) >> 3} py={z.r16(sym['_s_py8']) >> 3}")

# Teleportem Jake a x=240, y=1088 (davant del policia a x=280, y=1088)
# s_px8 = 240 * 8 = 1920
# s_py8 = 1088 * 8 = 8704
# cam_x4 = 40 (x=160..320)
# cam_row = 126
w16(sym["_s_px8"], 240 * 8)
w16(sym["_s_py8"], 1088 * 8)
w16(sym["_g_cam_x4"], 40)
w8(sym["_g_cam_row"], 126)

print(f"Teleportat: px={z.r16(sym['_s_px8']) >> 3} py={z.r16(sym['_s_py8']) >> 3}")

# Observem frame a frame
for f in range(150):
    time.sleep(0.04)
    px = z.r16(sym["_s_px8"]) >> 3
    py = z.r16(sym["_s_py8"]) >> 3
    regs = z.cmd("get-registers", wait=0.01).splitlines()
    reg_str = regs[0] if regs else ""
    if f % 10 == 0:
        print(f"frame {f:03d}: px={px} py={py} | {reg_str[:45]}")
    if "SP=bf" in reg_str.lower():
        print(f"\nCRASH DETECTAT al frame {f}! Registres:\n  {reg_str}")
        break

z.shot("obj/cop_teleport_result.bmp")
z.s.close()
subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
