#!/usr/bin/env python3
"""Simulador host-side dels walkers de src/enemy.c amb dades reals del nivell 1.

Per que: validar aterratge i patrulla 1:1 sense Depends de l'emulador (rebuild
de 12 min per proves). Reprodueix EXACTAMENT la llogica de src/enemy.c
(gravetat + snap d'is_floor_solid + sonda X de tiles) i el model de col.lisio
de src/main.c (is_floor_solid), i calcula on aterra cada enemic segons la
formula oficial (docs/DOS_CPC_COORDINATES.md) o segons la taula de src/enemy.c.

Us:
  py -3 tools/sim_enemies.py            # resum de tots els slots
  py -3 tools/sim_enemies.py --verbose  # + traça frame a frame d'un slot
  py -3 tools/sim_enemies.py --slot 3   # trace d'un sol slot
"""
import argparse
import os
import re

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAP_W, MAP_H = 128, 72
LEVEL_H = MAP_H * 16          # screen_tilemap_h (game.c: level_pkg.h)
ENEMY_W, ENEMY_HT = 16, 32
SUB = 8
YSHIFT = 3               # enemy.c: y8 = top << 3  (8 subpixels per pixel)
GRAV, VYMAX = 24, 120

# kind -> vx (SUB8) i tipus DOS segons l'eina oficial
KIND_VX = {4: 24, 15: 36, 17: 20, 18: 24, 20: 24}


def load_level():
    mapb = open(os.path.join(PROJ, "assets", "bbdata", "MAP0.BIN"), "rb").read()
    trig = open(os.path.join(PROJ, "assets", "bbdata", "TRIG0.BIN"), "rb").read()
    assert len(mapb) == MAP_W * MAP_H, len(mapb)
    assert len(trig) == 256 * 10, len(trig)
    return mapb, trig


MAPB, TRIG = load_level()


def rec(t):
    return TRIG[min(t, 255) * 10:][:10]


def tile_type(col, row):
    if col < 0 or col >= MAP_W or row < 0 or row >= MAP_H:
        return 1                      # fora de mapa = aire (main.c tile_type)
    return rec(MAPB[row * MAP_W + col])[0]


def tile_flags(col, row):
    if col < 0 or col >= MAP_W or row < 0 or row >= MAP_H:
        return 0
    return rec(MAPB[row * MAP_W + col])[1]


def is_floor_solid(col, row, vy=0, crouch=0):
    """src/main.c:is_floor_solid, literal."""
    if row >= MAP_H - 1:
        return vy >= 0
    if col >= MAP_W:
        return 0
    op = rec(MAPB[row * MAP_W + col])[2]
    if op in (20, 21, 27, 28):
        return 1
    if vy >= 0:
        if op in (14, 15):
            return not crouch
        if 31 <= op <= 39:
            return 1
    return 0


class Enemy:
    """Copia de l'estat d'enemy.c (fields que afecten X/Y)."""

    def __init__(self, x, y8, kind, vx):
        self.x = x              # vora esquerra (Mode 0)
        self.x0 = x             # x d'spawn (enemy.c usa sp->x per a les caixes)
        self.y8 = y8            # top en subpixels
        self.kind = kind
        self.vx = vx            # 0 = estatic
        self.dir = 1
        self.vy = 0
        self.on_ground = 0
        self.tick = 0

    @property
    def y(self):
        return self.y8 >> 3

    def step(self, trace=False):
        y = self.y
        if self.vx == 0:                       # policia estatica: no avança
            nx, dx = self.x, 0
        else:
            dx = (self.vx >> 3) if self.dir > 0 else -(self.vx >> 3)
            nx = self.x + dx
        # enemy.c l.244-257: ocells (19) i peixos (8) NO tenen gravetat:
        # volten/ neden en una caixa lliure i només patrullen en x.
        if self.kind in (8, 19):
            if self.kind == 8:
                min_x = 388 if self.x0 < 500 else 564
                max_x = min_x + 48
            else:
                min_x, max_x = self.x0 - 96, self.x0 + 96
            nx = self.x + dx
            if nx < min_x:
                self.x, self.dir = min_x, 1
            elif nx > max_x:
                self.x, self.dir = max_x, -1
            else:
                self.x = nx
            self.on_ground = 1
            self.vy = 0
            self.tick += 1
            if trace:
                print("  t%-3d x=%-5d y=%-5d [patrulla aire] dir=%-2d" %
                      (self.tick, self.x, self.y, self.dir))
            return self
        if self.vx:
            if nx < 0:
                nx, self.dir = 0, 1
            if nx > MAP_W * 8 - ENEMY_W:
                nx, self.dir = MAP_W * 8 - ENEMY_W, -1
            # enemy.c l.262-274
            frow = (y + ENEMY_HT) >> 4
            brow = (y + ENEMY_HT - 1) >> 4
            c2row = (y + ENEMY_HT - 2) >> 4
            ccol = (self.x + 8) >> 3               # centre = xpos16 (DOS)
            pcol = ccol + (2 if self.dir > 0 else -2)
            acol = (nx + (12 if self.dir > 0 else 2)) >> 3
            bit = 1 if self.dir > 0 else 2
            if (tile_type(pcol, frow) == 1 or tile_type(pcol, brow) == 1 or
                    (tile_flags(acol, brow) & bit) or
                    (tile_flags(acol, c2row) & bit)):
                self.dir = -self.dir
            else:
                self.x = nx
        # enemy.c l.275-295
        if not self.on_ground:
            prev_feet = y + ENEMY_HT
            self.vy = min(self.vy + GRAV, VYMAX)
            self.y8 += self.vy
            y = self.y
            feet = y + ENEMY_HT
            trow = feet >> 4
            if trow < MAP_H:
                cc = (self.x + 8) >> 3                # centre (DOS xpos16)
                surf = trow << 4
                if (is_floor_solid(cc, trow, 0, 0) and
                        prev_feet <= surf + 8 and feet >= surf):
                    self.y8 = (surf - ENEMY_HT) << 3
                    self.vy = 0
                    self.on_ground = 1
                else:
                    self.on_ground = 0
        elif (self.tick & 3) == 0:
            # enemy.c l.315-324: cada 4 ticks, si ja no hi ha terra sota
            # el centre, torna a caure (pasos i voreres).
            trow = (y + ENEMY_HT) >> 4
            if trow < MAP_H and not is_floor_solid((self.x + 8) >> 3, trow, 0, 0):
                self.on_ground = 0
        self.tick += 1
        if trace:
            print("  t%-3d x=%-5d y=%-5d vy=%-4d dir=%-2d g=%d" %
                  (self.tick, self.x, self.y, self.vy, self.dir, self.on_ground))
        return self


def parse_spawn_table():
    """Extreu src/enemy.c s_spawn[20] (x, y8, kind, vx, base_cell)."""
    src = open(os.path.join(PROJ, "src", "enemy.c"), encoding="utf-8", errors="replace").read()
    m = re.search(r"static const Spawn s_spawn\[ENEMY_N\] = \{(.*?)\n\};", src, re.S)
    rows = re.findall(r"\{\s*(\d+),\s*(\d+)\s*<<\s*3,\s*(\d+),\s*(\d+),\s*(\d+)\s*\},?\s*//\s*(.*)", m.group(1))
    out = []
    for r in rows:
        out.append({"x": int(r[0]), "y8": int(r[1]) << YSHIFT, "kind": int(r[2]),
                    "vx": int(r[3]), "cell": int(r[4]), "com": r[5].strip()})
    return out


def official_positions():
    """Formula oficial (docs/DOS_CPC_COORDINATES.md) via l'eina del repo.

    Retorna {slot: (dos_x, dos_y, tipus)} amb el tipus en versió CPC
    (kind) i la posicio oficial CPC ja aplicada.
    """
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
        tmp = f.name
    subprocess.run(["py", "-3", os.path.join(PROJ, "tools", "dos_coord_converter.py"),
                    "--level", "0"], stdout=open(tmp, "w"), check=True)
    kindmap = {"Policia": 4, "Cambrera": 17, "Rocker": 20, "Iaia": 15,
               "Peix": 8, "Granger": 18, "Ocell": 19}
    slots = {}
    for line in open(tmp, encoding="utf-8", errors="replace"):
        mm = re.match(r"\s*(\d+)\s*\|\s*(\w+)\s*\|\s*\(\s*(\d+),\s*(\d+)\s*\)", line)
        if mm and mm.group(2) in kindmap:
            dx, dy = int(mm.group(3)), int(mm.group(4))
            slots[int(mm.group(1))] = (dx, dy, kindmap[mm.group(2)],
                                       dx // 2 - 8, dy - 32)
    os.unlink(tmp)
    return slots


def sim(x, y8, kind, vx, steps=600):
    """Retorna (x_min, x_max, y_min, y_max, enemic_final, landed)."""
    e = Enemy(x, y8, kind, vx)
    xmin = xmax = x
    ymin = ymax = e.y
    for _ in range(steps):
        e.step()
        xmin, xmax = min(xmin, e.x), max(xmax, e.x)
        ymin, ymax = min(ymin, e.y), max(ymax, e.y)
    return xmin, xmax, ymin, ymax, e, e.on_ground == 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--slot", type=int, default=None)
    ap.add_argument("--steps", type=int, default=600)
    args = ap.parse_args()

    table = parse_spawn_table()
    off = official_positions()

    # Parell slot DOS <-> fila de la taula, verificat a ma (tipus + proximitat).
    # 4 = policia del repla: cap parell exacte al rumb (slot 0 oficial es al
    # carrer) -> None per marcar-ho com a PENDENT.
    DOS_SLOT = {0: 1, 1: 2, 2: 5, 3: 3, 4: None, 5: 7, 6: 29, 7: 18,
                8: 24, 9: 12, 10: 26, 11: 27, 12: 28, 13: 16, 14: 17,
                15: 10, 16: 6, 17: 15, 18: 9, 19: 13}

    def fmt(r):
        if r is None:
            return "?"
        e, landed = r[4], r[5]
        return "%s y=%-5d rang %d-%d" % ("terra" if landed else "CAIU", e.y, r[2], r[3])

    print("idx kind vx  taula(x,y)   oficial DOS slot(x,y)  delta    aterratge taula -> oficial")
    print("-" * 108)
    only = [args.slot] if args.slot is not None else range(len(table))
    for i in only:
        sp = table[i]
        k = DOS_SLOT.get(i)
        ox = oy = None
        if k is not None and k in off:
            ox, oy = off[k][3], off[k][4]
        simA = sim(sp["x"], sp["y8"], sp["kind"], sp["vx"], args.steps)
        simB = sim(ox, oy << YSHIFT, sp["kind"], sp["vx"], args.steps) if ox is not None else None
        if ox is not None:
            d = "%+d,%+d" % (sp["x"] - ox, (sp["y8"] >> 3) - oy)
            slotname = "%d (%s)" % (k, off[k][2])
        else:
            d = "SENSE PARELL"
            slotname = "-"
        print("%-3d %-4d %-3d (%4d,%5d) %-20s %-9s %s -> %s" %
              (i, sp["kind"], sp["vx"], sp["x"], sp["y8"] >> 3, slotname,
               d, fmt(simA), fmt(simB)))
        if args.verbose:
            print("  -- taula:")
            e = Enemy(sp["x"], sp["y8"], sp["kind"], sp["vx"])
            for _ in range(12):
                e.step(trace=True)
            if ox is not None:
                print("  -- oficial:")
                e = Enemy(ox, oy << YSHIFT, sp["kind"], sp["vx"])
                for _ in range(12):
                    e.step(trace=True)


if __name__ == "__main__":
    main()