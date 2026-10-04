import subprocess, socket, time, os

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

send_cmd("send-keys-string 60 run")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
send_cmd("send-keys-string 60 bluesb")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
press_key(129, 1); time.sleep(0.1); press_key(129, 0)

print("Waiting 12s for game to load...")
time.sleep(12)

# Pause CPU
send_cmd("enter-cpu-step")
print("Paused CPU!")

# Read variables in _DATA:
# _g_spr_y is at 0xA427, _g_spr_x is at 0xA428, _s_old_y is at 0xA42A, _s_old_x is at 0xA42B
# Let's read memory 0xA420..0xA440
mem_data = send_cmd("read-memory 41984 64") # 0xA400 is 41984
print("DATA 0xA400..0xA440:", mem_data)

# Let's read VRAM at scanlines 115..128
# dsx is at _g_spr_x
for sl in range(98, 128):
    row = sl // 8
    line = sl % 8
    addr = 0xC000 | ((line << 11) + row * 80)
    out = send_cmd(f"read-memory {addr + 31} 12")
    hexs = "".join(c for c in out if c in "0123456789abcdefABCDEF")
    print(f"sl={sl:03d} (0x{addr+31:04X}): {hexs}")

s.close()
proc.kill()
