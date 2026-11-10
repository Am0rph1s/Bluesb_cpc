import os, sys, time, re, subprocess
from PIL import Image

sys.path.insert(0, r"C:\Projects\bluesb_cpc\tools")
from smoke_test import Zrcp, EMU, DSK, MAP, PORT, symbols

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

subprocess.Popen([EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
                  "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                 cwd=os.path.dirname(EMU))
time.sleep(4)

z = Zrcp(PORT)

# 1. Esperar BASIC
t0 = time.time()
while time.time() - t0 < 30:
    ocr = z.cmd("get-ocr", wait=0.5).lower()
    if "ready" in ocr or "basic" in ocr:
        break
    time.sleep(0.5)

# 2. RUN"BLUESB"
def quote():
    z.cmd("send-keys-event %d 1" % Zrcp.KEY_SHIFT, wait=0.02)
    z.press(50, 0.05)
    z.cmd("send-keys-event %d 0" % Zrcp.KEY_SHIFT, wait=0.02)

z.keys("run")
quote()
z.keys("bluesb")
quote()
z.press(Zrcp.KEY_ENTER, 0.1)

# 3. Esperar que el joc entri al Nivell 1
sym = symbols()
a_magic = sym.get("_s_lv", 0)
a_px8 = sym.get("_s_px8", 0)
a_py8 = sym.get("_s_py8", 0)

print("Esperant càrrega del nivell 1...")
t0 = time.time()
while time.time() - t0 < 35:
    magic = z.r8(a_magic)
    px = z.r16(a_px8)
    py = z.r16(a_py8)
    if magic == 0xB0 and px > 0 and py > 0:
        print(f"Joc carregat! px={px>>3}, py={py>>3}")
        break
    z.press(32, 0.12)
    time.sleep(1.0)

time.sleep(1.5)

def grab(name):
    bmp = os.path.abspath(f"tools/{name}.bmp")
    png = os.path.abspath(f"tools/{name}.png")
    z.shot(bmp)
    im = Image.open(bmp).convert("RGB")
    w, h = im.size
    crop = im.crop(((w - 768) // 2, (h - 512) // 2, (w - 768) // 2 + 768, (h - 512) // 2 + 512))
    crop.save(png)
    return crop

# Frame 1: Standing at start (Street / storefront)
print("Capturant frame 1: Standing...")
grab("live_01_standing")

# Walk right
print("Caminant a la dreta...")
z.cmd("send-keys-event 143 1") # Right down
time.sleep(0.3)
grab("live_02_walk1")
time.sleep(0.3)
grab("live_03_walk2")
z.cmd("send-keys-event 143 0") # Right up
time.sleep(0.3)

# Jump
print("Saltant...")
z.cmd("send-keys-event 140 1") # Up down
time.sleep(0.25)
grab("live_04_jump")
time.sleep(0.3)
z.cmd("send-keys-event 140 0") # Up up
time.sleep(0.6)

# Teleport to store to see Granny
print("Teletransportant a la botiga per capturar la Iaia (Granny)...")
target_px = 450
target_py = 1106
z.cmd(f"write-memory {a_px8} {target_px*8 % 256}")
z.cmd(f"write-memory {a_px8+1} {target_px*8 // 256}")
z.cmd(f"write-memory {a_py8} {target_py*8 % 256}")
z.cmd(f"write-memory {a_py8+1} {target_py*8 // 256}")
time.sleep(0.6)
grab("live_05_granny1")
time.sleep(0.6)
grab("live_06_granny2")

z.close()
subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
print("Captures finalitzades!")
