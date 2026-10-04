import subprocess, socket, time
from PIL import Image

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd_args = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd_args, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(3)

s = socket.socket()
s.settimeout(5)
s.connect(('127.0.0.1', 10000))
time.sleep(0.5)
s.recv(4096)

def cmd(c, delay=0.05):
    s.sendall(c.encode('latin1') + b'\r\n')
    time.sleep(delay)
    buf = b''
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b'>'): break
    return buf.decode('latin1', errors='replace')

def press_key(key, event):
    cmd(f'send-keys-event {key} {event}')

cmd('send-keys-string 60 run')
time.sleep(0.1)
cmd('send-keys-event 133 1'); cmd('send-keys-event 50 1'); cmd('send-keys-event 50 0'); cmd('send-keys-event 133 0')
cmd('send-keys-string 60 bluesb')
time.sleep(0.1)
cmd('send-keys-event 133 1'); cmd('send-keys-event 50 1'); cmd('send-keys-event 50 0'); cmd('send-keys-event 133 0')
cmd('send-keys-event 129 1'); time.sleep(0.05); cmd('send-keys-event 129 0')

print('Waiting 12s for load...')
time.sleep(12)

# Save idle/stand
cmd(r'save-screen C:\Projects\bluesb_cpc\tools\shot_idle.bmp', 0.5)

# Tap RIGHT for 0.15s (walk a little bit to the right)
press_key(143, 1)
time.sleep(0.15)
cmd(r'save-screen C:\Projects\bluesb_cpc\tools\shot_walk_r.bmp', 0.5)
press_key(143, 0)
time.sleep(0.1)

# Tap SPACE (jump)
press_key(128, 1)
time.sleep(0.1)
cmd(r'save-screen C:\Projects\bluesb_cpc\tools\shot_jump.bmp', 0.5)
press_key(128, 0)
time.sleep(0.2)

# Tap LEFT for 0.15s (walk to the left, testing facing left!)
press_key(142, 1)
time.sleep(0.15)
cmd(r'save-screen C:\Projects\bluesb_cpc\tools\shot_walk_l.bmp', 0.5)
press_key(142, 0)

s.close()
proc.kill()

for name in ['shot_idle', 'shot_walk_r', 'shot_jump', 'shot_walk_l']:
    bmp_path = f'tools/{name}.bmp'
    png_path = f'tools/{name}.png'
    Image.open(bmp_path).save(png_path)
    print(f'Converted {png_path}')
