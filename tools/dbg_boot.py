import sys, time
sys.path.insert(0, r"C:\Projects\bluesb_cpc\tools")
from zrcp import Zrcp

BIN = r"C:\Projects\bluesb_cpc\obj\bluesb.bin"
ENTRY = 0x25CB

z = Zrcp()
print("machine:", z.cmd("get-current-machine").strip())
# para la CPU i carrega el binari a 0x0100
z.cmd("enter-cpu-step", 0.3)
print(z.cmd("load-binary %s 256 0" % BIN, 1.0).strip())
# comprova que el codi hi es (primer byte a 0x0100 = ?)
print("code@0x100:", z.read_mem(0x0100, 8).hex())
# SP i PC
z.cmd("set-register SP=BFFEH", 0.1)
z.cmd("set-register PC=%04XH" % ENTRY, 0.1)
# deixa correr
z.cmd("exit-cpu-step", 0.3)
time.sleep(5.0)
print("pc:", z.cmd("evaluate PC").strip())
mem = z.read_mem(0xC000, 64)
print("vram nonzero:", sum(1 for b in mem if b))
print("vram[0:32]:", mem[:32].hex())
z.close()
