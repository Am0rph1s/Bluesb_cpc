import subprocess, socket, time, os, re
from PIL import Image

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'
OUT = r'C:\Projects\bluesb_cpc\scratch'
MAP = r'C:\Projects\bluesb_cpc\obj\bluesb.map'

os.makedirs(OUT, exist_ok=True)

# Read symbol addresses from obj/bluesb.map
map_txt = open(MAP, 'r', encoding='utf-8', errors='replace').read()
def get_sym(name):
    m = re.search(rf'([0-9A-Fa-f]{{8}})\s+{re.escape(name)}\b', map_txt)
    if not m:
        raise RuntimeError(f'Symbol {name} not found in {MAP}')
    return int(m.group(1), 16)

addr_px8 = get_sym('_s_px8')
addr_py8 = get_sym('_s_py8')
addr_on_ground = get_sym('_s_on_ground')
print(f'_s_px8 = 0x{addr_px8:04X}, _s_py8 = 0x{addr_py8:04X}, _s_on_ground = 0x{addr_on_ground:04X}')

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

def write_u16(addr, val):
    lo = val & 0xFF
    hi = (val >> 8) & 0xFF
    send_cmd(f'write-memory {addr} {lo}', 0.05)
    send_cmd(f'write-memory {addr + 1} {hi}', 0.05)

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

print('Waiting 58s for game to boot and finish loading all asset files...')
for sec in range(1, 59):
    time.sleep(1.0)
    if sec % 10 == 0:
        print(f'Elapsed: {sec}s...')

# 1. Capture start position to verify border is BLACK (not red!)
send_cmd(rf'save-screen {OUT}\water_00_start_border.bmp', 0.4)

# Teleport Jake into Peixera 1: col 51 (px = 408 -> s_px8 = 3264), row 31 (py = 496 -> s_py8 = 3968)
print('Teleporting Jake to Peixera 1 (px=408, py=496) while camera scrolls naturally...')
for _ in range(12):
    write_u16(addr_px8, 408 * 8)
    write_u16(addr_py8, 496 * 8)
    time.sleep(0.4)

# Let Jake sink to the bottom of Peixera 1 (row 32, py=514) and settle on tank floor
time.sleep(1.2)

# 2. Capture Jake on tank floor (swim_floor) + water surface phase A and B
send_cmd(rf'save-screen {OUT}\water_01_floor_phaseA.bmp', 0.22)
send_cmd(rf'save-screen {OUT}\water_02_floor_phaseB.bmp', 0.22)

# 3. Swim vertically UP (Cursor Up = 145)
print('Testing vertical swimming UP...')
press_key(145, 1)
time.sleep(0.6)
send_cmd(rf'save-screen {OUT}\water_03_swim_up.bmp', 0.25)

# 4. Swim horizontally RIGHT (Cursor Right = 143) while holding UP
print('Testing horizontal swimming RIGHT...')
press_key(143, 1)
time.sleep(0.3)
send_cmd(rf'save-screen {OUT}\water_04_swim_strokeA.bmp', 0.22)
send_cmd(rf'save-screen {OUT}\water_05_swim_strokeB.bmp', 0.22)
press_key(143, 0)
press_key(145, 0)

# 5. Let Jake sink in water (swim_idle)
time.sleep(0.35)
send_cmd(rf'save-screen {OUT}\water_06_swim_idle.bmp', 0.25)

s.close()
proc.kill()

ARTIFACT_DIR = r'C:\Users\esquerra\.gemini\antigravity\brain\1592641d-8217-48b5-aebf-30a79b1763e6'
captures = [
    'water_00_start_border',
    'water_01_floor_phaseA',
    'water_02_floor_phaseB',
    'water_03_swim_up',
    'water_04_swim_strokeA',
    'water_05_swim_strokeB',
    'water_06_swim_idle',
]
for name in captures:
    bmp_p = os.path.join(OUT, f'{name}.bmp')
    if os.path.exists(bmp_p):
        im = Image.open(bmp_p)
        png_p = os.path.join(ARTIFACT_DIR, f'{name}.png')
        im.save(png_p)
        crop = im.crop((80, 140, 560, 520))
        crop_p = os.path.join(ARTIFACT_DIR, f'{name}_crop.png')
        crop.save(crop_p)
        print(f'Saved {name}.png (top-left border pixel RGB={im.getpixel((10, 10))})')
