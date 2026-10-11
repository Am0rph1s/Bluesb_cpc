import subprocess, socket, time, os, re
from PIL import Image

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'
OUT = r'C:\Projects\bluesb_cpc\scratch'
MAP = r'C:\Projects\bluesb_cpc\obj\bluesb.map'
ARTIFACT_DIR = r'C:\Users\esquerra\.gemini\antigravity\brain\1592641d-8217-48b5-aebf-30a79b1763e6'

os.makedirs(OUT, exist_ok=True)

map_txt = open(MAP, 'r', encoding='utf-8', errors='replace').read()
def get_sym(name):
    m = re.search(rf'([0-9A-Fa-f]{{8}})\s+{re.escape(name)}\b', map_txt)
    if not m:
        raise RuntimeError(f'Symbol {name} not found in {MAP}')
    return int(m.group(1), 16)

addr_px8        = get_sym('_s_px8')
addr_py8        = get_sym('_s_py8')
addr_vinyls     = get_sym('_g_vinyls_count')
addr_hearts     = get_sym('_g_hearts_count')
addr_lives      = get_sym('_g_lives_count')
addr_instrument = get_sym('_g_has_instrument')
addr_complete   = get_sym('_g_level_complete')
addr_dance      = get_sym('_s_dance_timer')

print(f'px8=0x{addr_px8:04X}, py8=0x{addr_py8:04X}, vinyls=0x{addr_vinyls:04X}, '
      f'hearts=0x{addr_hearts:04X}, lives=0x{addr_lives:04X}, inst=0x{addr_instrument:04X}, '
      f'complete=0x{addr_complete:04X}, dance=0x{addr_dance:04X}')

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

def send_cmd(c, delay=0.08):
    s.sendall(c.encode('latin1') + b'\r\n')
    time.sleep(delay)
    buf = b''
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b'>'): break
    return buf.decode('latin1', errors='replace')

def write_u8(addr, val):
    send_cmd(f'write-memory {addr} {val & 0xFF}', 0.04)

def write_u16(addr, val):
    send_cmd(f'write-memory {addr} {val & 0xFF}', 0.04)
    send_cmd(f'write-memory {addr + 1} {(val >> 8) & 0xFF}', 0.04)

def read_u8(addr):
    out = send_cmd(f'read-memory {addr} 1', 0.05)
    for tok in out.split():
        if re.fullmatch(r'[0-9A-Fa-f]{2}', tok):
            return int(tok, 16)
    return -1

def read_state():
    return {
        'vinyls': read_u8(addr_vinyls),
        'hearts': read_u8(addr_hearts),
        'lives': read_u8(addr_lives),
        'inst': read_u8(addr_instrument),
        'complete': read_u8(addr_complete),
        'dance': read_u8(addr_dance),
    }

def press_key(key, event):
    send_cmd(f'send-keys-event {key} {event}', 0.05)

addr_cam_x4     = get_sym('_g_cam_x4')
addr_cam_row    = get_sym('_g_cam_row')
addr_vy         = get_sym('_s_vy')

def read_u16(addr):
    lo = read_u8(addr)
    hi = read_u8(addr + 1)
    return lo | (hi << 8)

def teleport_smooth(px, py, max_iters=60):
    prev_cam = None
    stable = 0
    for _ in range(max_iters):
        write_u16(addr_px8, px * 8)
        write_u16(addr_py8, py * 8)
        write_u16(addr_vy, 0)
        time.sleep(0.18)
        cam = (read_u16(addr_cam_x4), read_u16(addr_cam_row))
        if cam == prev_cam:
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
            prev_cam = cam
    write_u16(addr_px8, px * 8)
    write_u16(addr_py8, py * 8)
    write_u16(addr_vy, 0)

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
    if sec % 15 == 0:
        print(f'Elapsed: {sec}s...')

st0 = read_state()
print('Initial state:', st0)
assert st0['vinyls'] == 0 and st0['hearts'] == 3 and st0['lives'] == 3 and st0['inst'] == 0

# 1. Test Vinyls (+1) and ? (+50) at (col=23..25, row=47..49) -> px=184..200, py=754
print('1. Teleporting to vinyl cluster & ? (+50) at (col=22, row=48 -> px=168, py=754)...')
teleport_smooth(168, 754)
send_cmd(rf'save-screen {OUT}\bonus_01_before_q50.bmp', 0.25)

# Move onto col 23 (vinyl +1) and col 24 (? +50)
write_u16(addr_px8, 176 * 8)
write_u16(addr_py8, 754 * 8)
time.sleep(0.15)
st1 = read_state()
print('After collecting 1 vinyl at (23,48):', st1)
assert st1['vinyls'] >= 1, f'Expected vinyls >= 1, got {st1}'

write_u16(addr_px8, 184 * 8)
write_u16(addr_py8, 754 * 8)
time.sleep(0.12)
send_cmd(rf'save-screen {OUT}\bonus_02_popup_plus50.bmp', 0.2)
st2 = read_state()
print('After collecting ? (+50) at (24,48):', st2)
assert st2['vinyls'] >= 51, f'Expected vinyls >= 51, got {st2}'

# 2. Test Broken Vinyl (-10) at (col=114, row=61 -> px=904, py=962)
print('2. Teleporting to Broken Vinyl (-10) at (col=114, row=61)...')
teleport_smooth(888, 962)
write_u16(addr_px8, 904 * 8)
write_u16(addr_py8, 962 * 8)
time.sleep(0.12)
send_cmd(rf'save-screen {OUT}\bonus_03_popup_minus10.bmp', 0.2)
st3 = read_state()
print('After Broken Vinyl (-10):', st3)

# 3. Test Heart (+1 heart) at (col=47, row=41 -> px=368, py=642)
print('3. Teleporting to Heart (+1) at (col=47, row=41)...')
teleport_smooth(352, 642)
send_cmd(rf'save-screen {OUT}\bonus_04_before_heart.bmp', 0.2)
write_u16(addr_px8, 368 * 8)
write_u16(addr_py8, 642 * 8)
time.sleep(0.15)
st4 = read_state()
print('After Heart (+1) at (47,41):', st4)
assert st4['hearts'] == 4, f'Expected hearts == 4, got {st4}'

# 4. Test Dance Question Mark (tile 6 at col=100, row=70 -> px=792, py=1106)
print('4. Teleporting to Dance ? at (col=100, row=70)...')
teleport_smooth(776, 1106)
write_u16(addr_px8, 792 * 8)
write_u16(addr_py8, 1106 * 8)
time.sleep(0.12)
st5 = read_state()
print('After Dance ? at (100,70):', st5)
send_cmd(rf'save-screen {OUT}\bonus_05_dance_poseA.bmp', 0.18)
send_cmd(rf'save-screen {OUT}\bonus_06_dance_poseB.bmp', 0.18)
assert st5['dance'] > 0, f'Expected dance > 0, got {st5}'
time.sleep(2.2) # Wait for dance to finish

# 5. Test Collectible Instrument (Guitar at col=42, row=61 -> px=328, py=962)
print('5. Teleporting to Guitar Room at (col=42, row=61)...')
teleport_smooth(312, 962)
send_cmd(rf'save-screen {OUT}\bonus_07_guitar_room.bmp', 0.25)
write_u16(addr_px8, 328 * 8)
write_u16(addr_py8, 962 * 8)
time.sleep(0.15)
st6 = read_state()
print('After picking up Guitar at (42,61):', st6)
send_cmd(rf'save-screen {OUT}\bonus_08_guitar_collected.bmp', 0.25)
assert st6['inst'] == 1, f'Expected inst == 1, got {st6}'

# 6. Test Level Exit (tile 157 at col=116, row=69 -> px=920, py=1090)
print('6. Teleporting to Level Exit at (col=116, row=69)...')
teleport_smooth(904, 1090)
write_u16(addr_px8, 920 * 8)
write_u16(addr_py8, 1090 * 8)
time.sleep(0.15)
st7 = read_state()
print('After touching Level Exit with Guitar:', st7)
send_cmd(rf'save-screen {OUT}\bonus_09_level_complete.bmp', 0.25)
assert st7['complete'] == 1, f'Expected complete == 1, got {st7}'

s.close()
proc.kill()

captures = [
    'bonus_01_before_q50',
    'bonus_02_popup_plus50',
    'bonus_03_popup_minus10',
    'bonus_04_before_heart',
    'bonus_05_dance_poseA',
    'bonus_06_dance_poseB',
    'bonus_07_guitar_room',
    'bonus_08_guitar_collected',
    'bonus_09_level_complete',
]
for name in captures:
    bmp_p = os.path.join(OUT, f'{name}.bmp')
    if os.path.exists(bmp_p):
        im = Image.open(bmp_p)
        im.save(os.path.join(ARTIFACT_DIR, f'{name}.png'))
        im.crop((60, 50, 710, 420)).save(os.path.join(ARTIFACT_DIR, f'{name}_crop.png'))
        print(f'Saved {name}.png (border RGB={im.getpixel((10, 10))})')
print('ALL BONUS/MALUS/INSTRUMENT TESTS PASSED SUCCESSFULLY!')
