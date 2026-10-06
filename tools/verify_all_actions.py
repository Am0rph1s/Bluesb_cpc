import subprocess, socket, time
from PIL import Image

EMU = r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe"
DSK = r"C:\Projects\bluesb_cpc\bluesb.dsk"

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r"C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0")
time.sleep(3)

s = socket.socket()
s.settimeout(5)
s.connect(('127.0.0.1', 10000))
time.sleep(0.5)
s.recv(4096)

def send_cmd(c, delay=0.1):
    s.sendall(c.encode('latin1') + b'\r\n')
    time.sleep(delay)
    buf = b''
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b'>'): break
    return buf.decode('latin1', errors='replace')

def press_key(key, event):
    send_cmd(f'send-keys-event {key} {event}')

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

print('Waiting 16s for game to load...')
time.sleep(16)

# 1. Capture idle standing
send_cmd(r'save-screen C:\Projects\bluesb_cpc\tools\action_1_idle.bmp', 0.4)

# 2. Walk right
print('Walking right...')
press_key(143, 1) # KEY_RIGHT
time.sleep(0.4)
send_cmd(r'save-screen C:\Projects\bluesb_cpc\tools\action_2_walk_right.bmp', 0.4)
press_key(143, 0)
time.sleep(0.2)

# 3. Walk left
print('Walking left...')
press_key(142, 1) # KEY_LEFT
time.sleep(0.4)
send_cmd(r'save-screen C:\Projects\bluesb_cpc\tools\action_3_walk_left.bmp', 0.4)
press_key(142, 0)
time.sleep(0.2)

# 4. Crouch
print('Crouching...')
press_key(141, 1) # KEY_DOWN
time.sleep(0.3)
send_cmd(r'save-screen C:\Projects\bluesb_cpc\tools\action_4_crouch.bmp', 0.4)

# 5. Crawl left
print('Crawling...')
press_key(142, 1) # KEY_LEFT while crouch
time.sleep(0.4)
send_cmd(r'save-screen C:\Projects\bluesb_cpc\tools\action_5_crawl.bmp', 0.4)
press_key(142, 0)
press_key(141, 0)
time.sleep(0.2)

# 6. Jump
print('Jumping...')
press_key(128, 1) # SPACE
time.sleep(0.2)
send_cmd(r'save-screen C:\Projects\bluesb_cpc\tools\action_6_jump.bmp', 0.4)
press_key(128, 0)
time.sleep(0.3)

s.close()
proc.kill()
print('Finished all actions capture.')
