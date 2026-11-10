import os, sys, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
EMU = os.path.join(HERE, "ZEsarUX_windows-13.0", "zesarux.exe")
DSK = os.path.join(PROJ, "bluesb.dsk")
PORT = 10000

sys.path.insert(0, HERE)
from test_l3_boot import Zrcp, symbols

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

# Launch ZEsarUX
subprocess.Popen([EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
                  "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                 cwd=os.path.dirname(EMU), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
time.sleep(4)

z = Zrcp(PORT)

# Wait BASIC
t0 = time.time()
while time.time() - t0 < 30:
    ocr = z.cmd("get-ocr", wait=0.5).lower()
    if "ready" in ocr or "basic" in ocr:
        break
    time.sleep(0.5)

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
a_px8 = sym.get("_s_px8", 0)
a_py8 = sym.get("_s_py8", 0)

key_code = ord('3')
z.cmd(f"send-keys-event {key_code} 1", wait=0.02)

t0 = time.time()
while time.time() - t0 < 90:
    magic = z.r8(a_magic) if a_magic else 0
    px = z.r16(a_px8) if a_px8 else 0
    py = z.r16(a_py8) if a_py8 else 0
    if magic == 0xB0 and px != 0 and py != 0:
        print(f"Nivell 3 carregat amb exit! px8={px}, py8={py}")
        break
    z.press(Zrcp.KEY_SPACE, 0.12)
    time.sleep(1.2)

z.cmd(f"send-keys-event {key_code} 0", wait=0.02)
time.sleep(1.0)

z.close()
print("ZEsarUX obert i en execucio al Nivell 3 (Preso)!")
