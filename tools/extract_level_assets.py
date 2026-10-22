#!/usr/bin/env python3
"""Extractor d'assets de nivell (Fase 4, base per als 6 nivells).

Genera, a assets/bbdata/: TILESET<n>.BIN (256x64), MAP<n>.BIN (ample x files
visibles), TRIG<n>.BIN (256x10) i ROOMS<n>.BIN (10 files x 20*room_count,
compacte). Tambe imprimeix el nombre de sales.

Nomes llegeix dades del DOS (assets/bbdata/*.CK1/CK2/SQL i el .BIN de TRIG)
i staticres.c/level.c. No toca el build ni el joc.

Us: py -3 tools/extract_level_assets.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
BB = os.path.join(PROJ, "assets", "bbdata")
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)
from unsqz import unsqz          # noqa: E402
from ilbm import read_ilbm       # noqa: E402
from mode0 import encode_mode0_byte  # noqa: E402
from pack_level import parse_staticres_arrays  # noqa: E402

# prefix, SQL, TRIG, nom
LEVELS = [
    ("MAG", "MAG.SQL", "MAGASIN.BIN", "magasin"),
    ("ENT", "ENT.SQL", "ENTREPOT.BIN", "ent"),
    ("PRISON", "PRISON.SQL", "PRISON.BIN", "prison"),
    ("EGOU", "EGOU.SQL", "EGOU.BIN", "egou"),
    ("VILLE", "VILLE.SQL", "VILLE.BIN", "ville"),
    ("CONCERT", "CONCERT.SQL", "CONCERT.BIN", "concert"),
]


def load_ck(prefix, n):
    path = os.path.join(BB, "%s.CK%d" % (prefix, n))
    d = unsqz(open(path, "rb").read())
    w, h, pl, pal, px = read_ilbm(d)
    assert w == 320 and h == 200, (path, w, h)
    return [row[0::2] for row in px]   # 320 -> 160 (Mode 0)


def tile_bytes(px, tc, tr):
    out = bytearray()
    for j in range(16):
        y = tr * 16 + j
        for xb in range(4):
            left = px[y][tc * 8 + xb * 2] & 0x0F
            right = px[y][tc * 8 + xb * 2 + 1] & 0x0F
            out.append(encode_mode0_byte(left, right))
    return out


def pos_rows():
    txt = open(os.path.join(HERE, "blues_dos", "bb", "level.c"),
               encoding="latin1").read()
    m = re.search(r"uint8_t\s+pos\[\]\s*=\s*\{([^}]*)\}", txt)
    return [int(x.strip(), 0) for x in m.group(1).split(",") if x.strip()]


def main():
    a = parse_staticres_arrays(os.path.join(HERE, "blues_dos", "bb", "staticres.c"))
    dim = a["level_dim"]
    doors = a["level_door"]
    pos = pos_rows()
    for n, (prefix, sql_name, trig_name, lname) in enumerate(LEVELS):
        ck = [load_ck(prefix, 1), load_ck(prefix, 2)]
        tileset = bytearray()
        for h in range(2):
            px = ck[h]
            for num in range(128):
                tr, tc = num // 20, num % 20
                tileset += tile_bytes(px, tc, tr)
        assert len(tileset) == 16384

        sql = unsqz(open(os.path.join(BB, sql_name), "rb").read())
        map_h = dim[n * 2 + 1] >> 4
        w = dim[n * 2]
        assert w == 128, (lname, w)
        need = map_h * w
        if len(sql) < need:
            sql = sql + bytes(need - len(sql))
        map_data = sql[:need]
        assert len(map_data) == need

        trig = open(os.path.join(BB, trig_name), "rb").read()
        assert len(trig) == 2560

        # Nombre de sales: index maxim de columna destí de les portes que
        # van a la zona de sales (dy o sy >= alcada visible o >= pos).
        room_count = 0
        door_bytes = bytearray()
        p0 = pos[n] if n < len(pos) else 0
        for i in range(30):
            v = doors[n * 30 * 8 + i * 8:n * 30 * 8 + i * 8 + 8]
            sx = v[0] | (v[1] << 8)
            sy = v[2] | (v[3] << 8)
            dx = v[4] | (v[5] << 8)
            dy = v[6] | (v[7] << 8)
            if not (sx or sy or dx or dy):
                continue
            door_bytes += bytes((sx, sy, dx, dy))
            in_dst = dy >= map_h or (p0 and dy >= p0)
            in_src = sy >= map_h or (p0 and sy >= p0)
            if in_dst:
                rx = dx
            elif in_src:
                rx = sx
            else:
                continue
            room_count = max(room_count, rx // 20 + 1)

        rooms = b""
        if room_count:
            # El SQL descomprimit pot acabar abans de l'ultima fila de sales
            # (el buffer DOS fa 16000 B i la resta queda a zero).
            need = (p0 + 10) * 128
            if len(sql) < need:
                sql = sql + bytes(need - len(sql))
            cols = 20 * room_count
            for r in range(10):
                off = (p0 + r) * 128
                rooms += sql[off:off + cols]
            assert len(rooms) == 10 * cols

        open(os.path.join(BB, "TILESET%d.BIN" % n), "wb").write(tileset)
        open(os.path.join(BB, "MAP%d.BIN" % n), "wb").write(map_data)
        open(os.path.join(BB, "TRIG%d.BIN" % n), "wb").write(trig)
        open(os.path.join(BB, "ROOMS%d.BIN" % n), "wb").write(rooms)
        open(os.path.join(BB, "DOORS%d.BIN" % n), "wb").write(door_bytes)
        print("Nivell %d (%s): TILESET=%d MAP=%d (%dx%d) TRIG=%d ROOMS=%d (%d sales) DOORS=%d" %
              (n + 1, lname, len(tileset), len(map_data), w, map_h,
               len(trig), len(rooms), room_count, len(door_bytes) // 4))


if __name__ == "__main__":
    main()
