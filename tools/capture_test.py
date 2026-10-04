import subprocess, socket, time, os

EMU = r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe"
DSK = r"C:\Projects\bluesb_cpc\bluesb.dsk"

# Kill any existing instance
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

print("Booted, waiting 7s...")
time.sleep(7)

# Save screen
out_bmp = r"C:\Projects\bluesb_cpc\tools\current_jake.bmp"
send_cmd(f"save-screen {out_bmp}", 0.5)
print("Screen saved to:", out_bmp)

# Also let's press right cursor for 1 sec and save another shot
press_key(143, 1) # KEY_RIGHT
time.sleep(1.0)
press_key(143, 0)
time.sleep(0.5)
out_bmp_walk = r"C:\Projects\bluesb_cpc\tools\current_jake_walk.bmp"
send_cmd(f"save-screen {out_bmp_walk}", 0.5)
print("Walk screen saved to:", out_bmp_walk)

s.close()
