import subprocess, socket, time

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd_args = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd_args, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(3)

s = socket.socket()
s.settimeout(5)
s.connect(('127.0.0.1', 10000))
time.sleep(0.5)
s.recv(4096)

def cmd(c, delay=0.05):
    s.sendall(c.encode('latin1') + b'\r\n')
    time.sleep(delay)
    buf = b''
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b'>'): break
    return buf.decode('latin1', errors='replace')

cmd('send-keys-string 60 run')
time.sleep(0.1)
cmd('send-keys-event 133 1'); cmd('send-keys-event 50 1'); cmd('send-keys-event 50 0'); cmd('send-keys-event 133 0')
cmd('send-keys-string 60 bluesb')
time.sleep(0.1)
cmd('send-keys-event 133 1'); cmd('send-keys-event 50 1'); cmd('send-keys-event 50 0'); cmd('send-keys-event 133 0')
cmd('send-keys-event 129 1'); time.sleep(0.05); cmd('send-keys-event 129 0')

print('Waiting 12s for load...')
time.sleep(12)

# Pause CPU
cmd('enter-cpu-step')
print('Paused!')

# Read memory: _g_spr_y, _g_spr_x from DATA (0xA427, 0xA428)
out = cmd('read-memory 41984 64')
hexs = ''.join(c for c in out if c in '0123456789abcdefABCDEF')
spr_y = int(hexs[0x27*2 : 0x27*2 + 2], 16)
spr_x = int(hexs[0x28*2 : 0x28*2 + 2], 16)
print(f'_g_spr_y = {spr_y}, _g_spr_x = {spr_x}')

# Read table from engine/sprite.s
with open('engine/sprite.s') as f:
    text = f.read()
start = text.find('_scr_addr_table::')
lines = text[start:].splitlines()
table = []
for line in lines[1:]:
    if not line.strip().startswith('.dw'): break
    parts = line.replace('.dw', '').split(',')
    for p in parts:
        table.append(int(p.strip(), 16))

print(f'Reading VRAM for 30 scanlines starting at sl={spr_y}...')
for sl in range(spr_y, spr_y + 30):
    base = table[sl] + spr_x
    out = cmd(f'read-memory {base} 12')
    h = ''.join(c for c in out if c in '0123456789abcdefABCDEF')[:24]
    print(f'sl={sl:3d} (spr line {sl-spr_y:2d}, 0x{base:04X}): {h}')

s.close()
proc.kill()
