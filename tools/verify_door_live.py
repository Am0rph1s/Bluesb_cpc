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
addr_lives = get_sym('_g_lives_count')
addr_cam_x4 = get_sym('_g_cam_x4')
addr_cam_row = get_sym('_g_cam_row')
addr_in_room = get_sym('_s_in_room')
addr_scrolling_locked = get_sym('_s_scrolling_locked')

print(f"Symbols: px8=0x{addr_px8:X}, py8=0x{addr_py8:X}, in_room=0x{addr_in_room:X}, cam_x4=0x{addr_cam_x4:X}, cam_row=0x{addr_cam_row:X}", flush=True)

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
    z.send_event(Zrcp.KEY_SPACE, 1)
    time.sleep(0.15)
    z.send_event(Zrcp.KEY_SPACE, 0)
    time.sleep(1.0)

time.sleep(2.0)

# Teleport Jake to door at column 36, row 70
# Center column: (px + 8) >> 3 == 36 -> px = 284
# s_px8 = 284 * 8 = 2272 (signed i16)
# s_py8 = 1106 * 8 = 8848
# cam_col = 36 - 10 = 26 -> cam_x4 = 52
# cam_row = (70 - 6) * 2 = 128
print('Teleporting Jake to PB Store entrance at col 36, row 70...', flush=True)
write_u16(addr_px8, 2272)
write_u16(addr_py8, 8848)
write_u16(addr_vx, 0)
write_u16(addr_vy, 0)
write_u16(addr_cam_x4, 52)
write_u16(addr_cam_row, 128)

time.sleep(0.5)
capture_scr('verify_door_outside_before')

# Press SPACE + UP to trigger door entry
print('Pressing SPACE + UP to enter door...', flush=True)
z.send_event(Zrcp.KEY_SPACE, 1)
z.send_event(Zrcp.KEY_UP, 1)
time.sleep(0.4)
z.send_event(Zrcp.KEY_SPACE, 0)
z.send_event(Zrcp.KEY_UP, 0)

time.sleep(1.5)

# Check state inside room
in_room = read_u8(addr_in_room)
px8 = read_u16(addr_px8)
py8 = read_u16(addr_py8)
cam_x4 = read_u16(addr_cam_x4)
cam_row = read_u16(addr_cam_row)
print(f"Inside check: in_room={in_room}, px8={px8} (px={px8>>3}, col={(px8>>3)+8>>3}), py8={py8} (py={py8>>3}), cam_x4={cam_x4}, cam_row={cam_row}", flush=True)

capture_scr('verify_door_room_inside')

# Walk left into the room
print('Walking left into room...', flush=True)
z.send_event(Zrcp.KEY_LEFT, 1)
time.sleep(1.5)
z.send_event(Zrcp.KEY_LEFT, 0)
time.sleep(0.5)

px8 = read_u16(addr_px8)
print(f"Mid-room: px8={px8} (px={px8>>3}, col={(px8>>3)+8>>3})", flush=True)
capture_scr('verify_door_room_walking')

# Walk back right to the door at column 18..19
print('Walking right back to door in room...', flush=True)
z.send_event(Zrcp.KEY_RIGHT, 1)
time.sleep(1.7)
z.send_event(Zrcp.KEY_RIGHT, 0)
time.sleep(0.5)

# Fine tune Jake to door column 18/19: (px + 8) >> 3 == 18 or 19 -> px ~ 140..148
# Let's write directly or ensure Jake is at (19, 82): px8 = 19 << 6 = 1216 (px=152), py8 = ((83 << 7) - 240) = 10384
write_u16(addr_px8, 1216)
write_u16(addr_py8, 10384)
write_u16(addr_vx, 0)
write_u16(addr_vy, 0)
time.sleep(0.5)

px8 = read_u16(addr_px8)
py8 = read_u16(addr_py8)
col = ((px8 >> 3) + 8) >> 3
row = ((py8 >> 3) + 29) >> 4
print(f"At exit door inside room: col={col}, row={row}, px8={px8}, py8={py8}", flush=True)
capture_scr('verify_door_room_at_exit')

# Press SPACE + UP to exit room back to street
print('Pressing SPACE + UP to exit room back to street...', flush=True)
z.send_event(Zrcp.KEY_SPACE, 1)
z.send_event(Zrcp.KEY_UP, 1)
time.sleep(0.4)
z.send_event(Zrcp.KEY_SPACE, 0)
z.send_event(Zrcp.KEY_UP, 0)

time.sleep(1.5)

in_room = read_u8(addr_in_room)
px8 = read_u16(addr_px8)
py8 = read_u16(addr_py8)
cam_x4 = read_u16(addr_cam_x4)
cam_row = read_u16(addr_cam_row)
col = ((px8 >> 3) + 8) >> 3
row = ((py8 >> 3) + 29) >> 4
print(f"Outside after exit check: in_room={in_room}, col={col}, row={row}, px8={px8} (px={px8>>3}), py8={py8}, cam_x4={cam_x4}, cam_row={cam_row}", flush=True)

capture_scr('verify_door_outside_after')

proc.terminate()
print('DONE!')
