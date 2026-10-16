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
    return int(m.group(1), 16) if m else None

addr_px8 = get_sym('_s_px8')
addr_py8 = get_sym('_s_py8')
addr_vy = get_sym('_s_vy')

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(4)

z = Zrcp(port=10000)

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
    z.cmd(f'save-screen {bmp_path}', wait=0.4)
    if os.path.exists(bmp_path):
        img = Image.open(bmp_path)
        img.save(png_path)
        print(f'Screenshot saved to {png_path}')
        return png_path
    return None

def move_jake_smooth(px, py, num_steps=50):
    for _ in range(num_steps):
        write_u16(addr_px8, px * 8)
        write_u16(addr_py8, py * 8)
        write_u16(addr_vy, 0)
        time.sleep(0.06)

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

print('Waiting for Level 1...')
start_time = time.time()
while time.time() - start_time < 95:
    py8 = read_u16(addr_py8)
    if py8 >= 8000:
        print(f'Level 1 entered at {time.time()-start_time:.1f}s! py8={py8}')
        break
    z.press_key(Zrcp.KEY_SPACE, 0.15)
    time.sleep(1.2)

time.sleep(2.0)

# 1. PB Store: Iaia 1 (patrol x=360..560, Jake at x=400)
print('1. PB Store (x=400, y=1104)...')
move_jake_smooth(400, 1104, 30)
time.sleep(0.4)
capture_scr('zone1_pb_iaia_store_f1')
time.sleep(0.5)
capture_scr('zone1_pb_iaia_store_f2')

# 2. PB Bar: Iaia 2 (x=632, y=1104, Jake at x=620)
print('2. PB Bar Iaia 2 (x=620, y=1104)...')
move_jake_smooth(620, 1104, 35)
time.sleep(0.4)
capture_scr('zone2_pb_iaia_bar_f1')
time.sleep(0.5)
capture_scr('zone2_pb_iaia_bar_f2')

# 3. 1r pis botiga: Policia sota escala (x=280), Rocker (x=440), Iaia (x=600) a y=976
print('3. 1r pis Policia + Rocker (x=300, y=976)...')
move_jake_smooth(300, 976, 45)
time.sleep(0.4)
capture_scr('zone3_1r_pis_police_rocker_f1')
time.sleep(0.5)
capture_scr('zone3_1r_pis_police_rocker_f2')

# 4. Escala vinils: Grangers (x=360, y=320)
print('4. Escala vinils Grangers (x=380, y=320)...')
move_jake_smooth(380, 320, 65)
time.sleep(0.4)
capture_scr('zone4_grangers_vinils_f1')
time.sleep(0.5)
capture_scr('zone4_grangers_vinils_f2')

# 5. Núvols: Ocell + ou (x=240 a y=140)
print('5. Núvols Ocell (x=240, y=140)...')
move_jake_smooth(240, 140, 65)
time.sleep(0.4)
capture_scr('zone5_ocell_nuvols_f1')
time.sleep(0.5)
capture_scr('zone5_ocell_nuvols_f2')

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
z.close()
print('All zones successfully captured!')
