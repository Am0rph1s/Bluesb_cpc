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

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(5)

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

def teleport_smooth(px, py, iters=30):
    for _ in range(iters):
        write_u16(addr_px8, px * 8)
        write_u16(addr_py8, py * 8)
        write_u16(addr_vy, 0)
        time.sleep(0.08)

# Boot game
time.sleep(1)
z.send_string('run')
time.sleep(0.3)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.1); z.send_event(50, 1); time.sleep(0.1); z.send_event(50, 0); time.sleep(0.1); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.3)
z.send_string('bluesb')
time.sleep(0.3)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.1); z.send_event(50, 1); time.sleep(0.1); z.send_event(50, 0); time.sleep(0.1); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.3)
z.send_event(Zrcp.KEY_ENTER, 1); time.sleep(0.15); z.send_event(Zrcp.KEY_ENTER, 0)

print('Waiting for Level 1...')
start_time = time.time()
while time.time() - start_time < 90:
    py8 = read_u16(addr_py8)
    if py8 >= 8000: break
    z.press_key(Zrcp.KEY_SPACE, 0.15)
    time.sleep(1.2)
time.sleep(1.5)

# Teleport to the exact platform from the user's screenshot (x=272, y=432)
print('Teleporting to user platform at escalator top...')
teleport_smooth(272, 432, iters=35)
time.sleep(0.5)
capture_scr('verify_platform_01_standing')

# Jump on platform
print('Pressing jump on platform...')
z.press_key(Zrcp.KEY_UP, 0.25)
time.sleep(0.2)
capture_scr('verify_platform_02_jumping')

time.sleep(0.4)
capture_scr('verify_platform_03_landed')

z.close()
proc.kill()
print('Verification completed!')
