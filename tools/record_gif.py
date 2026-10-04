import subprocess, socket, time
from PIL import Image

EMU = r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe"
DSK = r"C:\Projects\bluesb_cpc\bluesb.dsk"

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0")
time.sleep(3)

s = socket.socket()
s.settimeout(5)
s.connect(('127.0.0.1', 10000))
time.sleep(0.5)
s.recv(4096)

def send_cmd(c, delay=0.05):
    s.sendall(c.encode('latin1') + b'\r\n')
    time.sleep(delay)
    buf = b''
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b'>'): break
    return buf.decode('latin1', errors='replace')

def press_key(key, event):
    send_cmd(f'send-keys-event {key} {event}')

# Type run"bluesb"
send_cmd('send-keys-string 60 run')
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
send_cmd('send-keys-string 60 bluesb')
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
press_key(129, 1); time.sleep(0.1); press_key(129, 0)

print('Waiting 12s for game to load...')
time.sleep(12)

# Start walking right
press_key(143, 1)

frames = []
for i in range(25):
    time.sleep(0.08)
    send_cmd(r'save-screen C:\Projects\bluesb_cpc\tools\temp_frame.bmp', 0.05)
    im = Image.open(r'C:\Projects\bluesb_cpc\tools\temp_frame.bmp')
    crop = im.crop((120, 260, 680, 480))
    frames.append(crop)

press_key(143, 0)
time.sleep(0.2)

s.close()
proc.kill()

if frames:
    frames[0].save(r'C:\Projects\bluesb_cpc\tools\continuous_scroll.gif', save_all=True, append_images=frames[1:], duration=80, loop=0)
    print(f'Saved continuous_scroll.gif with {len(frames)} frames!')
