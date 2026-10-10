import subprocess, socket, time, os
from PIL import Image

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'
OUT = r'C:\Projects\bluesb_cpc\scratch'

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(3)

s = socket.socket()
s.settimeout(5)
s.connect(('127.0.0.1', 10000))
time.sleep(0.5)
s.recv(4096)

def send_cmd(c, delay=0.1):
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

print('Waiting 52s for game to boot and finish loading all 7 asset files...')
for sec in range(1, 53):
    time.sleep(1.0)
    if sec % 10 == 0:
        print(f'Elapsed: {sec}s...')

# 1. Capture base game active
send_cmd(rf'save-screen {OUT}\live_01_idle.bmp', 0.5)

# 2. Test Balloon
print('Triggering jump into balloon...')
press_key(145, 1) # UP
time.sleep(0.3)
press_key(145, 0)
time.sleep(1.2)
send_cmd(rf'save-screen {OUT}\live_02_balloon_flight.bmp', 0.5)

# 3. Test Umbrella Standing
print('Testing umbrella standing...')
send_cmd('write-memory 14879 8', 0.1)
time.sleep(0.5)
send_cmd(rf'save-screen {OUT}\live_03_umbrella_stand.bmp', 0.5)

# 4. Test Umbrella Walking Right
print('Testing umbrella walking right...')
press_key(143, 1) # RIGHT
time.sleep(0.6)
send_cmd(rf'save-screen {OUT}\live_04_umbrella_walk.bmp', 0.5)
time.sleep(0.4)
press_key(143, 0)
time.sleep(0.5)
send_cmd(rf'save-screen {OUT}\live_04b_umbrella_trail_check.bmp', 0.5)

# 5. Test Umbrella Floating
print('Testing umbrella floating...')
press_key(145, 1) # UP
time.sleep(0.3)
press_key(145, 0)
time.sleep(0.8)
send_cmd(rf'save-screen {OUT}\live_05_umbrella_float.bmp', 0.5)

s.close()
proc.kill()

print('Converting live captures to PNG and zooms...')
ARTIFACT_DIR = r'C:\Users\esquerra\.gemini\antigravity\brain\1592641d-8217-48b5-aebf-30a79b1763e6'
captures = ['live_01_idle', 'live_02_balloon_flight', 'live_03_umbrella_stand', 'live_04_umbrella_walk', 'live_04b_umbrella_trail_check', 'live_05_umbrella_float']
for name in captures:
    bmp_p = os.path.join(OUT, f'{name}.bmp')
    if os.path.exists(bmp_p):
        im = Image.open(bmp_p)
        png_p = os.path.join(ARTIFACT_DIR, f'{name}.png')
        im.save(png_p)
        crop = im.crop((80, 150, 560, 520))
        crop_p = os.path.join(ARTIFACT_DIR, f'{name}_crop.png')
        crop.save(crop_p)
        print(f'Saved {png_p} and {crop_p}')

print('Done verification!')
