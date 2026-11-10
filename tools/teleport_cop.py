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

print(f"L1 CARREGAT! px={z.r16(sym['_s_px8'])} py={z.r16(sym['_s_py8'])}")

# Teleportem Jake a x=240, y=1088 (davant del policia a x=280)
# s_px8 = 240 * 8 = 1920 (0x0780)
# s_py8 = 1088 * 8 = 8704 (0x2200)
# cam_x4 = (240 - 80) // 4 = 40
# cam_row = (1088 - 80) // 8 = 126
z.cmd(f"write-memory {sym['_s_px8']} 2 0x80 0x07")
z.cmd(f"write-memory {sym['_s_py8']} 2 0x00 0x22")
z.cmd(f"write-memory {sym['_g_cam_x4']} 2 40 0")
z.cmd(f"write-memory {sym['_g_cam_row']} 1 126")

print("Jake teleportat a x=240 davant del policia!")

# Ara observem durant 100 frames què passa (shoot timer, bala, crash)
for f in range(120):
    time.sleep(0.04)
    px = z.r16(sym["_s_px8"]) >> 3
    py = z.r16(sym["_s_py8"]) >> 3
    regs = z.cmd("get-registers", wait=0.01).splitlines()
    reg_str = regs[0] if regs else ""
    if f % 5 == 0:
        print(f"frame {f:03d}: px={px} py={py} | {reg_str[:50]}")
    if "SP=bf" in reg_str.lower():
        print(f"\nCRASH DETECTAT al frame {f}! Registres: {reg_str}")
        for l in regs: print("  ", l)
        break

z.shot("obj/cop_shoot_result.bmp")
z.s.close()
subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
