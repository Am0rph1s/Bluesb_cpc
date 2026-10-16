import subprocess, time, os, re, sys
sys.path.insert(0, r'C:\Projects\bluesb_cpc\tools')
from zrcp import Zrcp

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'
MAP = r'C:\Projects\bluesb_cpc\obj\bluesb.map'

map_txt = open(MAP, 'r', encoding='utf-8', errors='replace').read()
def get_sym(name):
    m = re.search(rf'([0-9A-Fa-f]{{8}})\s+{re.escape(name)}\b', map_txt)
    return int(m.group(1), 16)

addr_px8 = get_sym('_s_px8')
addr_py8 = get_sym('_s_py8')
addr_vy = get_sym('_s_vy')
addr_cam_x4 = get_sym('_g_cam_x4')
addr_cam_row = get_sym('_g_cam_row')

subprocess.run(['powershell', '-Command', 'Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue'])
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

time.sleep(1.0)
print('At Level 1!')

# Teleport Jake to x=272, py=144
for step in range(200):
    write_u16(addr_px8, 272 * 8)
    write_u16(addr_py8, 144 * 8)
    write_u16(addr_vy, 0)
    time.sleep(0.05)
    if step % 20 == 0:
        cam_x4 = read_u16(addr_cam_x4)
        cam_row = read_u16(addr_cam_row)
        print(f'Step {step}: cam_x4={cam_x4} (view_x={cam_x4*4}), cam_row={cam_row} (view_y={cam_row*8})')

subprocess.run(['powershell', '-Command', 'Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue'])
z.close()
