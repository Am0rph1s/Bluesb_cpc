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
addr_carry_kind = get_sym('_s_carry_kind')
addr_carry_state = get_sym('_s_carry_state')
addr_carry_x = get_sym('_s_carry_x')
addr_carry_y = get_sym('_s_carry_y')

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

def read_u8(addr):
    out = z.cmd(f'read-memory {addr} 1', 0.03)
    toks = [int(x, 16) for x in out.split() if re.fullmatch(r'[0-9A-Fa-f]{2}', x)]
    return toks[0] if toks else -1

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

# Test 1: Teleport to Balloon at col=32, row=35 (px=256, py=544)
print('Teleporting near balloon at col=32, row=35...')
teleport_smooth(256, 544, iters=35)
time.sleep(0.5)
capture_scr('verify_balloon_01_idle')

# Give Jake the balloon directly or trigger grab
write_u8(addr_carry_kind, 2)
write_u8(addr_carry_state, 0)
write_u16(addr_vy, -8)

print('Ascending with balloon through black shadow tile row 28...')
# Let Jake ascend through the black shadow row (py from 544 down to 480)
for step in range(30):
    time.sleep(0.08)
    cur_py8 = read_u16(addr_py8)
    kind = read_u8(addr_carry_kind)
    print(f'Ascent step {step}: py={cur_py8 >> 3}, kind={kind}')
    if (cur_py8 >> 3) <= 495: # In or right at shadow!
        break

capture_scr('verify_balloon_02_inside_shadow')

# Let it continue until it hits the real ceiling (row 27, py around 460)
for step in range(35):
    time.sleep(0.08)
    cur_py8 = read_u16(addr_py8)
    kind = read_u8(addr_carry_kind)
    if kind == 0:
        print(f'Balloon popped on solid ceiling at step {step}: py={cur_py8 >> 3}')
        break

capture_scr('verify_balloon_03_popped_at_ceiling')

# Test 2: Balloon Free-Flight release!
print('Testing balloon free-flight release...')
# Teleport Jake back to open area (px=256, py=530)
teleport_smooth(256, 530, iters=20)
write_u8(addr_carry_kind, 2)
write_u8(addr_carry_state, 0)
time.sleep(0.4)

# Release the balloon!
write_u16(addr_carry_x, 256 * 8)
write_u16(addr_carry_y, 520 * 8)
write_u8(addr_carry_state, 1) # free flight!
write_u16(addr_vy, 0) # Jake starts falling

# Capture during free flight: balloon rising, Jake falling
time.sleep(0.25)
capture_scr('verify_balloon_04_free_flight_release')

time.sleep(0.5)
capture_scr('verify_balloon_05_balloon_rising_high')

z.close()
proc.kill()
print('All verification steps completed!')
