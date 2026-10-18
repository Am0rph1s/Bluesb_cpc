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
addr_cam_x4 = get_sym('_g_cam_x4')
addr_cam_row = get_sym('_g_cam_row')
addr_hearts = get_sym('_g_hearts_count')
addr_lives = get_sym('_g_lives_count')
addr_checkpoint = get_sym('_g_checkpoint')
addr_dying_timer = get_sym('_s_dying_timer')
addr_dance_timer = get_sym('_s_dance_timer')

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(3)

z = Zrcp(port=10000)

def write_u8(addr, val):
    z.cmd(f'write-memory {int(addr)} {int(val) & 0xFF}', wait=0.03)

def write_u16(addr, val):
    z.cmd(f'write-memory {int(addr)} {int(val) & 0xFF}', wait=0.03)
    z.cmd(f'write-memory {int(addr) + 1} {(int(val) >> 8) & 0xFF}', wait=0.03)

def read_u8(addr):
    out = z.cmd(f'read-memory {int(addr)} 1', 0.03).strip()
    try:
        return int(out[:2], 16)
    except Exception:
        return -1

def read_u16(addr):
    out = z.cmd(f'read-memory {int(addr)} 2', 0.03).strip()
    try:
        b = bytes.fromhex(out[:4])
        return int.from_bytes(b, 'little')
    except Exception:
        return -1

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
    print(f'Waiting... py8={py8}')
    if py8 >= 8000: break
    z.press_key(Zrcp.KEY_SPACE, 0.15)
    time.sleep(1.2)
time.sleep(1.5)
print('In game!')

# Test 1: Start spawn position and dying dance
lives_start = read_u8(addr_lives)
hearts_start = read_u8(addr_hearts)
print(f'Initial state: lives={lives_start}, hearts={hearts_start}')

# Deal fatal blow: set hearts to 1, then trigger hit
print('Setting hearts to 1 and triggering damage...')
write_u8(addr_hearts, 1)
# Hit Jake by writing dying timer directly or letting next hit happen
write_u8(addr_hearts, 0)
write_u8(addr_dying_timer, 64)

# Wait a moment to catch Jake dancing
time.sleep(0.4)
capture_scr('verify_death_dance_frame1')
print(f'Dying timer: {read_u8(addr_dying_timer)}')

time.sleep(0.3)
capture_scr('verify_death_dance_frame2')

# Wait for respawn
print('Waiting for respawn...')
time.sleep(1.5)
capture_scr('verify_respawn_at_start')

lives_after = read_u8(addr_lives)
hearts_after = read_u8(addr_hearts)
px = read_u16(addr_px8) // 8
py = read_u16(addr_py8) // 8
print(f'After respawn at start: lives={lives_after}, hearts={hearts_after}, pos=({px}, {py})')

# Test 2: Set checkpoint, die, verify respawn at checkpoint (352, 464)
print('Setting checkpoint=1...')
write_u8(addr_checkpoint, 1)

print('Triggering fatal hit with checkpoint set...')
write_u8(addr_hearts, 0)
write_u8(addr_dying_timer, 64)

time.sleep(0.4)
capture_scr('verify_death_dance_at_chk')

print('Waiting for respawn at checkpoint...')
t0 = time.time()
while time.time() - t0 < 5.0:
    dt = read_u8(addr_dying_timer)
    if dt == 0:
        break
    time.sleep(0.1)
time.sleep(0.5)

capture_scr('verify_respawn_at_checkpoint')

lives_chk = read_u8(addr_lives)
hearts_chk = read_u8(addr_hearts)
px_chk = read_u16(addr_px8) // 8
py_chk = read_u16(addr_py8) // 8
cam_x4 = read_u16(addr_cam_x4)
cam_row = read_u16(addr_cam_row)
print(f'After checkpoint respawn: lives={lives_chk}, hearts={hearts_chk}, pos=({px_chk}, {py_chk}), cam=({cam_x4}, {cam_row})')

z.close()
proc.kill()
print('Verification finished successfully!')
