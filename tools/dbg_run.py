import sys, time
sys.path.insert(0, r"C:\Projects\bluesb_cpc\tools")
from zrcp import Zrcp

z = Zrcp()
print("machine:", z.cmd("get-current-machine").strip())
# envia RUN"BLUESB" amb el temps correcte
z.cmd('send-keys-string 100 RUN"BLUESB"', 1.5)
# comprova l'estat
for i in range(4):
    print("pc:", z.cmd("evaluate PC").strip())
    time.sleep(0.4)
# bolca una mica de VRAM
mem = z.read_mem(0xC000, 32)
print("vram[0..32]:", mem.hex())
# comprova si el nostre codi es a 0x0100
code = z.read_mem(0x0100, 16)
print("code@0x100:", code.hex())
z.close()
