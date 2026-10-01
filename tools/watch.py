import sys, time, struct
sys.path.insert(0, r"C:\Projects\bluesb_cpc\tools")
from zrcp import Zrcp

z = Zrcp()
def u16(a):
    d = z.read_mem(a, 2); return d[0] | (d[1] << 8)
print("monitor g_save_cnt @AFB0 (max logic 248). Ctrl-C per parar.")
try:
    for _ in range(200):
        sc = u16(0xAFB0)
        oc = u16(0xAFB2)
        pc = z.cmd("evaluate PC").strip()
        if sc > 260 or oc > 260:
            print("ALERTA sc=%d oc=%d pc=%s" % (sc, oc, pc))
            break
        time.sleep(0.05)
    else:
        print("cap alerta en el periode mostrejat (sc=%d oc=%d)" % (sc, oc))
except KeyboardInterrupt:
    pass
z.close()
