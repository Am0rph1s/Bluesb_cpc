import subprocess, socket, time, os

EMU = r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe"
DSK = r"C:\Projects\bluesb_cpc\bluesb.dsk"

# Stop existing
subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

# Start interactive process
subprocess.Popen([
    EMU,
    "--machine", "CPC6128",
    "--enable-dsk",
    "--dsk-file", DSK,
    "--enable-remoteprotocol",
    "--remoteprotocol-port", "10000"
], cwd=r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0")

print("Esperant 4s per inicialitzar ZEsarUX...")
time.sleep(4)

s = socket.socket()
s.settimeout(5)
s.connect(("127.0.0.1", 10000))
time.sleep(0.5)
banner = s.recv(4096).decode("latin1", errors="replace")
print("Connectat al port ZRCP 10000 amb èxit!")

def send_cmd(c, delay=0.05):
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

# Wait for BASIC prompt
t0 = time.time()
while time.time() - t0 < 15:
    ocr = send_cmd("get-ocr", delay=0.2).lower()
    if "ready" in ocr or "basic" in ocr:
        break
    time.sleep(0.5)

# Type run"bluesb"
print("Escrivint run\"bluesb\"...")
send_cmd("send-keys-string 60 run")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
send_cmd("send-keys-string 60 bluesb")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
press_key(129, 1); time.sleep(0.1); press_key(129, 0)

s.close()
print("ZEsarUX obert interactiu i joc arrencat!")
