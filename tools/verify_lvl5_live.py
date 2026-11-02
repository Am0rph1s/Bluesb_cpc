import subprocess, time, os, re
from PIL import Image
import sys
sys.path.insert(0, r'C:\Projects\bluesb_cpc\tools')
from zrcp import Zrcp

EMU = r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0\zesarux.exe'
DSK = r'C:\Projects\bluesb_cpc\bluesb.dsk'
OUT = r'C:\Projects\bluesb_cpc\scratch'
ARTIFACT_DIR = r'C:\Users\esquerra\.gemini\antigravity\brain\d5048ab8-d131-412d-a59a-046fb6bbb20c'

subprocess.run(["powershell", "-Command", "Stop-Process -Name zesarux -Force -ErrorAction SilentlyContinue"])
time.sleep(1)

cmd = [EMU, '--machine', 'CPC6128', '--enable-dsk', '--dsk-file', DSK, '--enable-remoteprotocol', '--remoteprotocol-port', '10000']
proc = subprocess.Popen(cmd, cwd=r'C:\Projects\bluesb_cpc\tools\ZEsarUX_windows-13.0')
time.sleep(3)

z = Zrcp(port=10000)

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

print('Enviant comanda de boot a BASIC...')
time.sleep(2)
z.cmd('send-keys-string 60 run')
time.sleep(0.2)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.cmd('send-keys-string 60 bluesb')
time.sleep(0.2)
z.send_event(Zrcp.KEY_SHIFT, 1); time.sleep(0.05); z.send_event(50, 1); time.sleep(0.05); z.send_event(50, 0); time.sleep(0.05); z.send_event(Zrcp.KEY_SHIFT, 0)
time.sleep(0.1)
z.send_event(Zrcp.KEY_ENTER, 1); time.sleep(0.1); z.send_event(Zrcp.KEY_ENTER, 0)

# Mantingues premuda la tecla '5' (ASCII 53) durant el boot del joc
print("Prement tecla '5' per anar directe al Nivell 5...")
z.send_event(53, 1)

print('Esperant boot (38s)...')
time.sleep(38)
z.send_event(53, 0)

# Avançar pel mapa
for _ in range(5):
    z.send_event(Zrcp.KEY_SPACE, 1)
    time.sleep(0.15)
    z.send_event(Zrcp.KEY_SPACE, 0)
    time.sleep(0.5)

print('Esperant càrrega del nivell 5 (12s)...')
time.sleep(12)

capture_scr('level5_boot')

print('Saltar a la dreta per superar el desnivell i caure a la bastida...')
z.send_event(Zrcp.KEY_SPACE, 1)
z.send_event(Zrcp.KEY_RIGHT, 1)
time.sleep(0.6)
z.send_event(Zrcp.KEY_SPACE, 0)
z.send_event(Zrcp.KEY_RIGHT, 0)
time.sleep(0.5)

capture_scr('level5_jump1')

print('Moure més a la dreta...')
z.send_event(Zrcp.KEY_RIGHT, 1)
time.sleep(1.0)
z.send_event(Zrcp.KEY_RIGHT, 0)
time.sleep(0.5)

capture_scr('level5_jump2')

print('Saltar a la dreta sobre el pont...')
z.send_event(Zrcp.KEY_SPACE, 1)
z.send_event(Zrcp.KEY_RIGHT, 1)
time.sleep(0.8)
z.send_event(Zrcp.KEY_SPACE, 0)
z.send_event(Zrcp.KEY_RIGHT, 0)
time.sleep(0.5)

capture_scr('level5_bridge')

print('Test finalitzat amb èxit!')
