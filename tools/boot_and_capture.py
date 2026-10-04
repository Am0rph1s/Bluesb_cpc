import subprocess, socket, time, os
from PIL import Image

EMU = r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe"
DSK = r"C:\Projects\bluesb_cpc\bluesb.dsk"

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

proc = subprocess.Popen(cmd, cwd=r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0")
time.sleep(3)

s = socket.socket()
s.settimeout(5)
s.connect(("127.0.0.1", 10000))
time.sleep(0.5)
s.recv(4096)

def send_cmd(c, delay=0.1):
    s.sendall(c.encode("latin1") + b"\r\n")
    time.sleep(delay)
    buf = b""
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b">"): break
    return buf.decode("latin1", errors="replace")

def press_key(key, event):
    send_cmd(f"send-keys-event {key} {event}")

# First, let CPC boot to BASIC
print("Waiting for BASIC prompt...")
time.sleep(3)

# Type 'run"bluesb"'
send_cmd("send-keys-string 60 run")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
send_cmd("send-keys-string 60 bluesb")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
press_key(129, 1); time.sleep(0.1); press_key(129, 0)

# Wait 12s for disk loading to finish at normal 100% speed
print("Waiting 12s for game to load from disk...")
for i in range(12):
    time.sleep(1.0)
    regs = send_cmd("get-registers", 0.05)
    for line in regs.splitlines():
        if "PC=" in line:
            pc_str = line.split("PC=")[1].split()[0]
            print(f"[{i}s] PC={pc_str}")

# Save screen
out_bmp = r"C:\Projects\bluesb_cpc\tools\jake_game.bmp"
send_cmd(f"save-screen {out_bmp}", 0.5)
print("Screen saved to:", out_bmp)

# Let's convert to PNG
if os.path.exists(out_bmp):
    im = Image.open(out_bmp)
    im.save(r"C:\Projects\bluesb_cpc\tools\jake_game.png")
    print("Saved jake_game.png, size:", im.size)

s.close()
proc.kill()
