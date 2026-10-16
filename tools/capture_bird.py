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
addr_cam_x4 = get_sym('_g_cam_x4')
addr_cam_row = get_sym('_g_cam_row')

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(3)

z = Zrcp(port=10000)

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

def teleport_smooth(px, py, max_iters=40):
    prev_cam = None
    stable = 0
    for _ in range(max_iters):
        write_u16(addr_px8, px * 8)
        write_u16(addr_py8, py * 8)
        write_u16(addr_vy, 0)
        time.sleep(0.12)
        cam = (read_u16(addr_cam_x4), read_u16(addr_cam_row))
        if cam == prev_cam:
            stable += 1
            if stable >= 2: break
        else:
            stable = 0
            prev_cam = cam
    write_u16(addr_px8, px * 8)
    write_u16(addr_py8, py * 8)
    write_u16(addr_vy, 0)

# Type run"bluesb"
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
    if py8 >= 8000:
        print(f'Level 1 reached at {time.time()-start_time:.1f}s!')
        break
    z.press_key(Zrcp.KEY_SPACE, 0.15)
    time.sleep(1.2)

time.sleep(1.5)

# Teleport Jake on top of cloud at (col=54, px=440, py=80)
print('Teleporting Jake to cloud platform at x=440, py=80...')
teleport_smooth(440, 80)
time.sleep(0.4)
capture_scr('walker_test_06_bird_clouds_f1')
time.sleep(0.6)
capture_scr('walker_test_06_bird_clouds_f2')

# Also capture Ocell 1 over cloud at col 32 (x=256, py=128)
print('Teleporting Jake to cloud platform at x=256, py=128 (Ocell 1)...')
teleport_smooth(256, 128)
time.sleep(0.4)
capture_scr('walker_test_07_bird1_clouds_f1')
time.sleep(0.6)
capture_scr('walker_test_07_bird1_clouds_f2')

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
z.close()
print('Bird test done!')
