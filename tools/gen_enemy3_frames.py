#!/usr/bin/env python3
"""Genera assets/bbdata/ENEMI3.BIN per al nivell 3 (PRISON).

Mateixa cela 16x32 / 512 B que ENEMI1/ENEMI2.BIN. Les imatges surten de
ENEMI3.SQV. Els indexs de frame SON els del DOS: es treuen de
`animframes_059d` (staticres.c), on el frame del nivell = index - SPRITES_COUNT
(146). Vegeu tools/dump_level_sprites.py per veure les tires per tipus.

Celes (16) - REPARTIMENT REAL (verificat amb tools/check_enemy_cells.py):
   0,1,2   t3  (op2)  guardia amb escut       frames DOS 0,1,2
   3,4,5   t4  (op3)  presidiari amb bazuka    frames DOS 5,6,11 (11 = tret)
   6,7     t6  (op1)  rata                     frames DOS 26,27
   8,9,10  t23 (op11) presidiari de cel·les    frames DOS 14,15,21
   11,12   t5  (op4)  presidiari amb casc      frames DOS 23,24
   13      projectils (copia de la cel·la 13 d'ENEMI1.BIN: ou/bala/plat)
   14,15   lliures

El tipus 5/op4 i el 23/op11 son movers (ascensors), no walkers de C6: els
frames hi son per quan s'implementin.

IMPORTANT (13/11/2026): aquest fitxer ha estat DESACTUALITZAT des del 28/10 i
el repartiment de cel·les que hi ha al disc era diferent (el policia usava les
cel·les de la rata i la rata les de projectils). Ara el repartiment de CELLS
esta corregit, pero l'empaquetat NO es correspon byte a byte amb el binaire del
disc (aquell va fer-se amb els indexs de color DOS tal qual; aquest script fa
servir el mapatge semantic de pack_cell). Per aixè l' script **no escriu res**
per defecte: nomes informa de la divergencia i cal --force per substituir el
binaire. Despres de substituir-lo, refresca el PNG master amb
    py -3 tools/graphics_tool.py export
i torna a importar amb
    py -3 tools/graphics_tool.py import
Per verificar la taula de cel·les contra el DOS (i no contra el binaire), fes
servir tools/check_enemy_cells.py.

Regenerar:
  py -3 tools/gen_enemy3_frames.py            # escriu el binaire
  py -3 tools/gen_enemy3_frames.py --check    # nomes verifica
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))
sys.path.insert(0, HERE)

from sprites import load_sqv_frames  # noqa: E402
from gen_enemy_frames import pack_cell  # noqa: E402

SQV = os.path.join(PROJ, "assets", "bbdata", "ENEMI3.SQV")
OUT_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI3.BIN")
L1_BIN = os.path.join(PROJ, "assets", "bbdata", "ENEMI1.BIN")

# (cela, frame SQV) - repartiment real (vegeu la capçalera)
CELLS = [
    (0, 0),    # t3  guardia amb escut, walk A
    (1, 1),    # t3  walk B
    (2, 2),    # t3  pose
    (3, 5),    # t4  presidiari, walk A
    (4, 6),    # t4  walk B
    (5, 11),   # t4  pose de tret
    (6, 26),   # t6  rata, walk A
    (7, 27),   # t6  rata, walk B
    (8, 14),   # t23 presidiari de cel·les, walk A
    (9, 15),   # t23 walk B
    (10, 21),  # t23 pose
    (11, 23),  # t5  presidiari amb casc, walk A
    (12, 24),  # t5  walk B
]


def crop_content(px, w, h):
    """Retalla al bbox del contingut real i l'ajusta a 16x32 (com L2)."""
    xs = [x for y in range(h) for x in range(w) if px[y][x] != 0]
    ys = [y for y in range(h) for x in range(w) if px[y][x] != 0]
    if not xs:
        return px, w, h
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 - x0 + 1 > 32:
        x1 -= (x1 - x0 + 1) - 32
    if y1 - y0 + 1 > 32:
        y0 += (y1 - y0 + 1) - 32
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    out = [[0] * cw for _ in range(ch)]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            out[y - y0][x - x0] = px[y][x]
    return out, cw, ch


def main():
    frames = load_sqv_frames(SQV)
    print("ENEMI3.SQV: %d frames" % len(frames))

    cells = [bytes(512) for _ in range(16)]
    for cell, idx in CELLS:
        w, h, px = frames[idx]
        px, w, h = crop_content(px, w, h)
        assert w <= 32 and h <= 32, (idx, w, h)
        cells[cell] = pack_cell(px, w, h)

    # Projectils: la cela 13 d'ENEMI1.BIN te ou/bala/plat alineats.
    l1 = open(L1_BIN, "rb").read()
    assert len(l1) >= 14 * 512, len(l1)
    cells[13] = l1[13 * 512:14 * 512]

    out = b"".join(cells)
    assert len(out) == 16 * 512

    cur = open(OUT_BIN, "rb").read() if os.path.exists(OUT_BIN) else b""
    if cur == out:
        print("OK: %s coincideix amb el repartiment de cel·les actual" % OUT_BIN)
        return 0

    diff = [c for c in range(16) if cur[c * 512:(c + 1) * 512] != out[c * 512:(c + 1) * 512]]
    print("DIVERGENCIA amb %s: cel·les %s" % (OUT_BIN, diff))
    print("  (el fitxer del disc es va construir amb un altre empaquetat: el binaire")
    print("   del disc usa els indexs de color DOS tal qual, i aquest script usa el")
    print("   mapatge semantic de pack_cell. NO s'ha d'escriure a ciegas.)")

    if "--force" not in sys.argv:
        print("No s'escriu res (passa --force si de debò vols substituir el binaire,")
        print("i aleshores refresca el PNG master amb 'graphics_tool.py export').")
        return 1

    open(OUT_BIN, "wb").write(out)
    print("escrit %s: %d bytes (16 celes)" % (OUT_BIN, len(out)))
    print("ATENCIO: refresca el PNG master amb 'graphics_tool.py export' i torna a")
    print("          importar amb 'graphics_tool.py import'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
