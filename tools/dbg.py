"""Panell de control de depuracio per ZRCP.
Us:
  python tools/dbg.py screen            # bolca VRAM -> tools/screen.png
  python tools/dbg.py regs              # mostra registres
  python tools/dbg.py mem <addr> <len>  # hexdump
  python tools/dbg.py eval <expr>       # avalua (ex: PC, HL, (0x1234))
  python tools/dbg.py step <n>          # cpu-step n cops
  python tools/dbg.py run               # run
  python tools/dbg.py bp <addr>         # breakpoint
  python tools/dbg.py con               # comandes interactives des de stdin
  python tools/dbg.py raw "<cmd>"       # envia una comanda ZRCP crua
"""
import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zrcp import Zrcp

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen.png")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    z = Zrcp()
    cmd = sys.argv[1]
    if cmd == "screen":
        mem = z.read_mem(0xC000, 0x4000)
        open(os.path.join(os.path.dirname(OUT), "vram.bin"), "wb").write(mem)
        import subprocess
        subprocess.run([sys.executable, os.path.join(os.path.dirname(OUT), "vram2png.py"),
                        os.path.join(os.path.dirname(OUT), "vram.bin"), OUT])
    elif cmd == "regs":
        print(z.regs())
    elif cmd == "mem":
        addr = int(sys.argv[2], 0); length = int(sys.argv[3], 0)
        print(z.read_mem(addr, length).hex())
    elif cmd == "eval":
        print(z.cmd("evaluate " + sys.argv[2]))
    elif cmd == "step":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        z.cmd("enter-cpu-step", 0.2)
        for _ in range(n):
            print(z.cmd("cpu-step", 0.05))
        z.cmd("exit-cpu-step", 0.2)
    elif cmd == "run":
        print(z.cmd("run", 0.5))
    elif cmd == "bp":
        print(z.cmd("set-breakpoint 1 %s" % sys.argv[2]))
    elif cmd == "raw":
        print(z.cmd(sys.argv[2], 0.4))
    elif cmd == "con":
        print("ZRCP interactiu. Escriu comandes (buit per sortir):")
        while True:
            try:
                line = input("zrcp> ")
            except EOFError:
                break
            if not line:
                break
            print(z.cmd(line, 0.4))
    z.close()

if __name__ == "__main__":
    main()
