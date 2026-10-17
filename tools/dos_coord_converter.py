#!/usr/bin/env python3
"""
tools/dos_coord_converter.py - Eina de conversió de coordenades 1:1 DOS <-> CPC (Blues Brothers)

Fonament matemàtic (extret de tools/blues_dos/bb/screen.c:40):
  - A DOS: (dos_x, dos_y) és el CENTRE HORITZONTAL i la BASE DELS PEUS (terra) de l'sprite.
    draw_x_dos = dos_x - w_dos / 2
    draw_y_dos = dos_y - h_dos
  - A CPC Mode 0: la resolució horitzontal és la meitat (160 px vs 320 px de DOS, aspecte 2:1).
    w_cpc = w_dos / 2 (píxels Mode 0, cada byte = 2 px).
    h_cpc = h_dos (línies).
    cpc_x = (dos_x - w_dos / 2) / 2 = dos_x / 2 - w_cpc / 2  (vora ESQUERRA)
    cpc_y = dos_y - h_dos                                    (vora SUPERIOR)
    cpc_floor_y = dos_y                                      (línia de terra)

Rajoles (Tiles):
  - DOS: 16x16 px -> tile_col = dos_x >> 4, tile_row = dos_y >> 4
  - CPC:  8x16 px -> tile_col = cpc_x >> 3, tile_row = cpc_y >> 4
"""

import sys, re, argparse

# Taules de dimensions per tipus d'objecte a DOS (bb/staticres.c i level_obj_w / level_obj_h):
# Per defecte: personatges w_dos = 32, h_dos = 32 (a CPC: w_cpc = 16 px = 8 bytes, h_cpc = 32 línies)
SPRITE_DIMS = {
    # type: (name, w_dos, h_dos)
    0:  ('Jake',       32, 32),
    1:  ('Elwood',     32, 32),
    2:  ('Crate',      16, 16),
    4:  ('Policia',    32, 32),
    7:  ('Elevator',   48, 16),
    8:  ('Peix',       16, 16),
    10: ('Cambrera',   32, 32),
    15: ('Iaia',       32, 32),
    17: ('Cambrera',   32, 32),
    18: ('Granger',    32, 32),
    19: ('Ocell',      32, 32),
    20: ('Rocker',     32, 32),
}

def dos_to_cpc(dos_x, dos_y, w_dos=32, h_dos=32):
    """Converteix coordenades DOS (centre, peus) a CPC (top-left)."""
    w_cpc = w_dos // 2
    cpc_x = (dos_x - (w_dos // 2)) // 2
    cpc_y = dos_y - h_dos
    cpc_floor_y = dos_y
    tile_col = dos_x // 16
    tile_row = dos_y // 16
    return {
        'cpc_x': cpc_x,
        'cpc_y': cpc_y,
        'cpc_floor_y': cpc_floor_y,
        'w_cpc': w_cpc,
        'h_cpc': h_dos,
        'tile_col': tile_col,
        'tile_row': tile_row,
        'sub_px8': cpc_x * 8,
        'sub_py8': cpc_y * 8,
    }

def cpc_to_dos(cpc_x, cpc_y, w_dos=32, h_dos=32):
    """Converteix coordenades CPC (top-left) a DOS (centre, peus)."""
    dos_x = (cpc_x * 2) + (w_dos // 2)
    dos_y = cpc_y + h_dos
    return {
        'dos_x': dos_x,
        'dos_y': dos_y,
        'tile_col': dos_x // 16,
        'tile_row': dos_y // 16,
    }

def dump_level_from_staticres(level_idx=0):
    """Llegeix staticres.c i converteix automàticament tots els objectes del nivell."""
    with open('tools/blues_dos/bb/staticres.c', 'r', encoding='utf-8', errors='replace') as f:
        src = f.read()

    level_names = ['magasin', 'ent', 'prison', 'egou', 'ville', 'concert']
    lname = level_names[level_idx]

    # Troba level_xpos_{lname} i level_ypos_{lname}
    rx_x = rf'const int16_t level_xpos_{lname}\[\]\s*=\s*\{{([^}}]+)\}};'
    rx_y = rf'const int16_t level_ypos_{lname}\[\]\s*=\s*\{{([^}}]+)\}};'
    mx = re.search(rx_x, src, re.DOTALL)
    my = re.search(rx_y, src, re.DOTALL)
    if not mx or not my:
        print(f'Error: no s\'han trobat les taules per al nivell {lname}')
        return

    x_vals = [int(x.strip(), 0) for x in re.findall(r'0x[0-9A-Fa-f]+|\b\d+\b', mx.group(1))]
    y_vals = [int(y.strip(), 0) for y in re.findall(r'0x[0-9A-Fa-f]+|\b\d+\b', my.group(1))]

    # Llegeix level_data
    m_data = re.search(r'uint8_t level_data\[\]\s*=\s*\{([^}]+)\};', src, re.DOTALL)
    types_all = [int(t.strip(), 0) for t in re.findall(r'0x[0-9A-Fa-f]+|\b\d+\b', m_data.group(1))]
    types = types_all[level_idx * 41 : (level_idx + 1) * 41]

    print(f'=== OBJECTES NIVELL {level_idx}: {lname.upper()} ===')
    print(f'{"Slot":4s} | {"Tipus":10s} | {"DOS (X, Y)":14s} | {"DOS Tile":8s} | {"CPC (X, Y)":12s} | {"Floor Y":7s} | {"CPC Tile":8s}')
    print('-' * 78)
    for i in range(len(x_vals)):
        t = types[i] if i < len(types) else 100
        if t == 100: continue
        name, w, h = SPRITE_DIMS.get(t, (f'Type_{t}', 32, 32))
        dx, dy = x_vals[i], y_vals[i]
        c = dos_to_cpc(dx, dy, w, h)
        print(f'{i:4d} | {name:10s} | ({dx:4d}, {dy:4d})   | ({c["tile_col"]:2d}, {c["tile_row"]:2d})   | ({c["cpc_x"]:4d}, {c["cpc_y"]:4d}) | {c["cpc_floor_y"]:7d} | ({c["cpc_x"]//8:2d}, {c["cpc_y"]//16:2d})')

def main():
    p = argparse.ArgumentParser(description='Conversor 1:1 de coordenades DOS <-> CPC per Blues Brothers')
    p.add_argument('--dos', nargs=2, type=int, metavar=('X', 'Y'), help='Coordenades DOS (centre, peus)')
    p.add_argument('--cpc', nargs=2, type=int, metavar=('X', 'Y'), help='Coordenades CPC (top-left)')
    p.add_argument('--w', type=int, default=32, help='Amplada sprite a DOS (defecte 32)')
    p.add_argument('--h', type=int, default=32, help='Alçada sprite a DOS (defecte 32)')
    p.add_argument('--level', type=int, choices=range(6), help='Bolca tots els objectes del nivell (0=Magasin, 1=Entrepot, ...)')

    args = p.parse_args()

    if args.level is not None:
        dump_level_from_staticres(args.level)
        return

    if args.dos:
        dx, dy = args.dos
        res = dos_to_cpc(dx, dy, args.w, args.h)
        print(f'DOS: ({dx}, {dy}) [w={args.w}, h={args.h}]')
        print(f' -> CPC top-left:   X={res["cpc_x"]} px (subpixel: {res["sub_px8"]}), Y={res["cpc_y"]} línies (subpixel: {res["sub_py8"]})')
        print(f' -> CPC floor Y:    {res["cpc_floor_y"]}')
        print(f' -> Rajola (Tile):  Col={res["tile_col"]}, Row={res["tile_row"]}')
        return

    if args.cpc:
        cx, cy = args.cpc
        res = cpc_to_dos(cx, cy, args.w, args.h)
        print(f'CPC: ({cx}, {cy}) [w_dos={args.w}, h_dos={args.h}]')
        print(f' -> DOS (centre, peus): X={res["dos_x"]}, Y={res["dos_y"]}')
        print(f' -> Rajola (Tile):      Col={res["tile_col"]}, Row={res["tile_row"]}')
        return

    # Si no s'especifica res, mostra ajuda i nivell 0
    p.print_help()
    print('\nExemple per defecte: Nivell 1 (Magasin):')
    dump_level_from_staticres(0)

if __name__ == '__main__':
    main()
