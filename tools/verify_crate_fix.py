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
addr_vx = get_sym('_s_vx')
addr_face = get_sym('_g_face')
addr_carry_kind = get_sym('_s_carry_kind')
addr_carry_state = get_sym('_s_carry_state')
addr_carry_x = get_sym('_s_carry_x')
addr_carry_y = get_sym('_s_carry_y')
addr_carry_vx = get_sym('_s_carry_vx')
addr_lives = get_sym('_g_lives_count')
addr_cam_x4 = get_sym('_g_cam_x4')
addr_cam_row = get_sym('_g_cam_row')

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
    out = z.cmd(f'read-memory {addr} 1', wait=0.03)
    for tok in out.split():
        if re.fullmatch(r'[0-9A-Fa-f]{2}', tok):
            return int(tok, 16)
    return -1

def read_u16(addr):
    lo = read_u8(addr)
    hi = read_u8(addr + 1)
    if lo < 0 or hi < 0: return -1
    return lo | (hi << 8)

def capture_scr(tag):
    bmp_path = os.path.join(OUT, f'{tag}.bmp')
    png_path = os.path.join(ARTIFACT_DIR, f'{tag}.png')
    if os.path.exists(bmp_path): os.remove(bmp_path)
    z.cmd(f'save-screen {bmp_path}', wait=0.3)
    if os.path.exists(bmp_path):
        img = Image.open(bmp_path)
        img.save(png_path)
        print(f'Screenshot saved to {png_path}', flush=True)
        return png_path
    return None

def crop_jake(tag, out_tag, box=(200, 240, 480, 480)):
    png_path = os.path.join(ARTIFACT_DIR, f'{tag}.png')
    if os.path.exists(png_path):
        im = Image.open(png_path)
        c = im.crop(box)
        crop_path = os.path.join(ARTIFACT_DIR, f'{out_tag}.png')
        c.save(crop_path)
        print(f'Cropped saved to {crop_path}', flush=True)

# Boot game
time.sleep(1)
z.send_string('run')
time.sleep(0.1)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.send_string('bluesb')
time.sleep(0.1)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.send_event(Zrcp.KEY_ENTER, 1); time.sleep(0.1); z.send_event(Zrcp.KEY_ENTER, 0)

print('Waiting for Level 1...', flush=True)
start_time = time.time()
while time.time() - start_time < 90:
    lives = read_u8(addr_lives)
    py8 = read_u16(addr_py8)
    if lives == 3 and py8 >= 8000:
        print(f'Level 1 active: lives={lives}, py8={py8} at {time.time()-start_time:.1f}s', flush=True)
        break
    z.press_key(Zrcp.KEY_SPACE, 0.3)
    time.sleep(1.0)

time.sleep(1.0)

# Move Jake to open area on the roof (away from ladder at col 15): x = 64 pixels -> s_px8 = 512
print('Moving Jake to open area (px=64)...', flush=True)
write_u16(addr_px8, 512)
write_u16(addr_vx, 0)
write_u16(addr_vy, 0)
time.sleep(0.3)

# 1. Equip crate facing right
print('Equipping crate facing right...', flush=True)
write_u8(addr_face, 0)
write_u8(addr_carry_kind, 1)
write_u8(addr_carry_state, 0)
time.sleep(0.2)
capture_scr('verify_crate_carry_right')
crop_jake('verify_crate_carry_right', 'verify_crate_crop_right', box=(200, 240, 400, 440))

# 2. Equip crate facing left
print('Equipping crate facing left...', flush=True)
write_u8(addr_face, 1)
write_u8(addr_carry_kind, 1)
write_u8(addr_carry_state, 0)
time.sleep(0.2)
capture_scr('verify_crate_carry_left')
crop_jake('verify_crate_carry_left', 'verify_crate_crop_left', box=(200, 240, 400, 440))

# 3. Throw crate to the right in open space!
print('Throwing crate to the right in open space...', flush=True)
write_u8(addr_face, 0)
write_u8(addr_carry_kind, 1)
write_u8(addr_carry_state, 0)
time.sleep(0.1)

# Press space to throw
z.press_key(Zrcp.KEY_SPACE, 0.05)
time.sleep(0.02)

# Capture flight frames
for f in range(1, 10):
    cx = read_u16(addr_carry_x)
    cy = read_u16(addr_carry_y)
    ckind = read_u8(addr_carry_kind)
    cstate = read_u8(addr_carry_state)
    print(f'Flight frame {f}: kind={ckind}, state={cstate}, x={cx}, y={cy}', flush=True)
    capture_scr(f'verify_crate_flight_{f}')
    crop_jake(f'verify_crate_flight_{f}', f'verify_crate_crop_flight_{f}', box=(200, 240, 500, 440))
    time.sleep(0.05)

z.close()
proc.kill()
print('Verification completed successfully!', flush=True)

