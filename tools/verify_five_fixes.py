import subprocess, time, os, re
from PIL import Image
import sys
sys.path.insert(0, r'C:\Projects\bluesb_cpc\tools')
from zrcp import Zrcp

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'
OUT = r'C:\Projects\bluesb_cpc\scratch'
MAP = r'C:\Projects\bluesb_cpc\obj\bluesb.map'
ARTIFACT_DIR = r'C:\Users\esquerra\.gemini\antigravity\brain\1592641d-8217-48b5-aebf-30a79b1763e6'

map_txt = open(MAP, 'r', encoding='utf-8', errors='replace').read()
def get_sym(name):
    m = re.search(rf'([0-9A-Fa-f]{{8}})\s+{re.escape(name)}\b', map_txt)
    return int(m.group(1), 16)

addr_px8 = get_sym('_s_px8')
addr_py8 = get_sym('_s_py8')
addr_vy = get_sym('_s_vy')
addr_carry = get_sym('_s_carry_kind')
addr_ground = get_sym('_s_on_ground')
addr_knock = get_sym('_s_knock_timer')

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(3)

z = Zrcp(port=10000)

def write_u8(addr, val):
    z.cmd(f'write-memory {addr} {val & 0xFF}', wait=0.03)

def write_u16(addr, val):
    z.cmd(f'write-memory {addr} {val & 0xFF}', wait=0.03)
    z.cmd(f'write-memory {addr + 1} {(val >> 8) & 0xFF}', wait=0.03)

def read_u16(addr):
    out = z.cmd(f'read-memory {addr} 2', 0.03)
    toks = [int(x, 16) for x in out.split() if re.fullmatch(r'[0-9A-Fa-f]{2}', x)]
    return toks[0] | (toks[1] << 8) if len(toks) >= 2 else -1

def capture_scr(tag):
    bmp_path = os.path.join(OUT, f'{tag}.bmp')
    png_path = os.path.join(ARTIFACT_DIR, f'{tag}.png')
    if os.path.exists(bmp_path): os.remove(bmp_path)
    z.cmd(f'save-screen {bmp_path}', wait=0.4)
    if os.path.exists(bmp_path):
        img = Image.open(bmp_path)
        img.save(png_path)
        print(f'Screenshot saved to {png_path}')
        return png_path
    return None

def teleport_smooth(px, py, iters=30):
    for _ in range(iters):
        write_u16(addr_px8, px * 8)
        write_u16(addr_py8, py * 8)
        write_u16(addr_vy, 0)
        time.sleep(0.08)

# Boot game
z.send_string('run')
time.sleep(0.1)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.send_string('bluesb')
time.sleep(0.1)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.send_event(Zrcp.KEY_ENTER, 1); time.sleep(0.1); z.send_event(Zrcp.KEY_ENTER, 0)

print('Waiting for Level 1...')
start_time = time.time()
while time.time() - start_time < 90:
    py8 = read_u16(addr_py8)
    if py8 >= 8000: break
    z.press_key(Zrcp.KEY_SPACE, 0.15)
    time.sleep(1.2)
time.sleep(1.5)
print('In game! Jake py8 =', read_u16(addr_py8))

# Test 1: Police 2 at elevator recess (x=816, y=784)
print('Testing Police 2 at recess...')
teleport_smooth(780, 770, iters=35)
time.sleep(0.5)
capture_scr('verify_01_police_recess')

# Test 2: Low ceiling knockdown (under low ceiling at ground floor or first floor)
print('Testing ceiling knockdown...')
# Teleport Jake under a low solid ceiling corridor, e.g. x=260, y=1106
teleport_smooth(260, 1106, iters=20)
# Trigger knock timer directly or simulate jump
write_u8(addr_knock, 36)
time.sleep(0.2)
capture_scr('verify_02_ceiling_knockdown')

# Test 3: Umbrella standing on cloud (feet on ground)
print('Testing umbrella standing on cloud...')
# Teleport to cloud at top: x=240, y=96
teleport_smooth(240, 96, iters=25)
write_u8(addr_carry, 8) # umbrella
write_u8(addr_ground, 1)
time.sleep(0.4)
capture_scr('verify_03_umbrella_cloud_standing')

# Test 4: Umbrella gliding in air
print('Testing umbrella gliding in air...')
write_u8(addr_ground, 0)
write_u16(addr_vy, 8)
time.sleep(0.2)
capture_scr('verify_04_umbrella_gliding')

# Test 5: Blue ladder in fish tank (Col 47 -> x=376, y=510)
print('Testing blue ladder in fish tank...')
teleport_smooth(372, 510, iters=25)
capture_scr('verify_05_blue_ladder')

proc.terminate()
print('All test screenshots captured!')
