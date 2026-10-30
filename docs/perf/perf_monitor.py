import sys, re, time, collections
sys.path.insert(0, r'C:\Projects\bluesb_cpc\tools')
from zrcp import Zrcp

OUT = r'C:\Projects\bluesb_cpc\scratch\perf.log'
MAP = r'C:\Projects\bluesb_cpc\obj\bluesb.map'
WIN = 2.0  # segons per a la finestra del fps

_txt = open(MAP, encoding='utf-8', errors='replace').read()


def sym(name):
    m = re.search(r'([0-9A-Fa-f]{8})\s+' + re.escape(name) + r'\b', _txt)
    return int(m.group(1), 16) if m else 0


A = {n: sym(n) for n in ('_s_conveyor_phase', '_s_px8', '_s_py8', '_s_vx', '_s_vy',
                          '_s_on_ground', '_s_carry_kind', '_g_cam_x4', '_g_cam_row',
                          '_s_lv', '_s_climb_prev')}


def rd(z, a, n):
    o = z.cmd('read-memory %d %d' % (a, n), wait=0.02).strip()
    return bytes.fromhex(o)


def main(dur=1800):
    z = Zrcp(port=10000)
    f = open(OUT, 'w', buffering=1)
    f.write('# px8=%04X conv=%04X climb=%04X\n' % (
        A['_s_px8'], A['_s_conveyor_phase'], A['_s_climb_prev']))
    f.write('t(s) fps px py vx vy carry gnd climb camx4 camrow mov lvl\n')
    t0 = time.time()
    hist = collections.deque()
    prevcam = None
    while time.time() - t0 < dur:
        try:
            p = rd(z, A['_s_conveyor_phase'], 1)[0]
            t = time.time() - t0
            hist.append((t, p))
            while len(hist) > 2 and hist[0][0] < t - WIN:
                hist.popleft()
            fps = 0.0
            if len(hist) >= 2 and t > hist[0][0] + 0.5:
                d = (p - hist[0][1]) & 0xFF
                dt = t - hist[0][0]
                fps = d * 4.0 / dt
            s = rd(z, A['_s_px8'], 12)
            px = (s[0] | (s[1] << 8)) >> 3
            py = (s[2] | (s[3] << 8)) >> 3
            vx = s[4] | (s[5] << 8)
            vx = vx - 65536 if vx > 32767 else vx
            vy = s[6] | (s[7] << 8)
            vy = vy - 65536 if vy > 32767 else vy
            gnd = s[8]
            c = rd(z, A['_g_cam_x4'], 4)
            cam = (c[0] | (c[1] << 8), c[2] | (c[3] << 8))
            carry = rd(z, A['_s_carry_kind'], 1)[0]
            climb = rd(z, A['_s_climb_prev'], 1)[0]
            lvl = rd(z, A['_s_lv'] + 13, 1)[0]
            mov = 'S' if prevcam is not None and prevcam != cam else '-'
            prevcam = cam
            f.write('%5.1f %5.1f %4d %4d %4d %5d %d %d %d %4d %4d %s %d\n' % (
                t, fps, px, py, vx, vy, carry, gnd, climb, cam[0], cam[1], mov, lvl))
        except Exception:
            try:
                z.close()
            except Exception:
                pass
            time.sleep(1.0)
            try:
                z = Zrcp(port=10000)
            except Exception:
                pass
        time.sleep(0.25)
    f.close()
    try:
        z.close()
    except Exception:
        pass


if __name__ == '__main__':
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
    main(d)
