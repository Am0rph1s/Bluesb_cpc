import os, sys, time, subprocess
from PIL import Image

sys.path.insert(0, r"C:\Projects\bluesb_cpc\tools")
from smoke_test import Zrcp, EMU, DSK, PORT

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

# Launch ZEsarUX
subprocess.Popen([EMU, "--machine", "CPC6128", "--enable-dsk", "--dsk-file", DSK,
                  "--enable-remoteprotocol", "--remoteprotocol-port", str(PORT)],
                 cwd=os.path.dirname(EMU), creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
time.sleep(4)

print(f"Connectant al port {PORT}...")
z = Zrcp(PORT)

# Wait BASIC
t0 = time.time()
while time.time() - t0 < 30:
    ocr = z.cmd("get-ocr", wait=0.5).lower()
    if "ready" in ocr or "basic" in ocr:
        break
    time.sleep(0.5)

print("BASIC detectat! Escrivint run\"bluesb\"...")
def quote():
    z.cmd("send-keys-event %d 1" % Zrcp.KEY_SHIFT, wait=0.02)
    z.press(50, 0.05)
    z.cmd("send-keys-event %d 0" % Zrcp.KEY_SHIFT, wait=0.02)

z.keys("run")
quote()
z.keys("bluesb")
quote()
z.press(Zrcp.KEY_ENTER, 0.1)

print("Ordre enviada! Esperant que carregui...")
time.sleep(3)

# Do NOT close zesarux; close socket connection cleanly so user can play
z.s.close()
print("ZEsarUX actiu i llest per jugar!")
