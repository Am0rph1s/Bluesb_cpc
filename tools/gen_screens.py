#!/usr/bin/env python3
"""gen_screens.py - Pantalles fixes DOS VGA -> Mode 0 CPC (avaluacio F0.3).
SPLASH = PRES.SQZ meitat superior (logo), SELECT = CHOIX.SQZ, MAP = INTER.SQZ.
Sortida: .BIN (160x200 indices 0..15 empaquetats 2px/byte, 16000 B) + .PAL (RGB)
+ preview PNG. La paleta HW (INKR) s'assigna al cablejat (F2).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'bbdata'))
from unsqz import unsqz
from ilbm import read_ilbm
from PIL import Image

OUT = os.path.join('/Users', 'esquerra', 'AppData', 'Local', 'Temp', 'opencode')


def convert_direct(name, png):
    """Empaqueta una pantalla 160x200 P ja retocada per l'usuari (16 colors
    HW exactes) SENSE tocar resolucio ni colors: nomes reindexa duplicats
    exactes (mateix RGB) i residuals (pocs px -> color proper mes proper).
    .BIN entrellacat HW + .PAL + .PALHW (match EXACTE, assert) + porta WYSIWYG."""
    HW = {0x54:(0,0,0),0x44:(0,0,128),0x55:(0,0,255),0x5C:(128,0,0),
          0x58:(128,0,128),0x5D:(128,0,255),0x4C:(255,0,0),0x45:(255,0,128),
          0x4D:(255,0,255),0x56:(0,128,0),0x46:(0,128,128),0x57:(0,128,255),
          0x5E:(128,128,0),0x40:(128,128,128),0x5F:(128,128,255),
          0x4E:(255,128,0),0x47:(255,128,128),0x4F:(255,128,255),
          0x52:(0,255,0),0x42:(0,255,128),0x53:(0,255,255),0x5A:(128,255,0),
          0x59:(128,255,128),0x5B:(128,255,255),0x4A:(255,255,0),
          0x43:(255,255,128),0x4B:(255,255,255)}
    RGB2HW = {v: k for k, v in HW.items()}
    im = Image.open(png)
    assert im.size == (160, 200) and im.mode == 'P', (im.size, im.mode)
    pal = im.getpalette()
    rgb = [tuple(pal[i * 3:i * 3 + 3]) for i in range(256)]
    qi = list(im.getdata())
    assert len(qi) == 32000
    # Indexs usats -> RGB unics (preservant ordre de primera aparicio).
    seen = {}
    for idx in qi:
        if idx not in seen:
            seen[idx] = rgb[idx]
    uniq = list(seen.values())
    # Fusiona duplicats exactes (mateix RGB, p.ex. negre x2).
    mains = []
    for c in uniq:
        if c not in mains:
            mains.append(c)
    # Si n'hi ha mes de 16 (residuals d'antialiasing): queda't els 16 amb
    # mes pixels i envia la resta al proper (invisible: desenes de px).
    from collections import Counter
    cnt = Counter()
    for idx in qi:
        cnt[seen[idx]] += 1
    if len(mains) > 16:
        mains = [c for c, _ in cnt.most_common(16)]
        assert len(mains) == 16
    # Residuals (indexs fora dels 16): al main proper (amb informe).
    remap = {}
    mainset = mains[:16]
    for idx, c in seen.items():
        if c in mainset:
            remap[idx] = mainset.index(c)
        else:
            best = min(range(len(mainset)),
                       key=lambda m: sum((a - b) ** 2 for a, b in zip(mainset[m], c)))
            remap[idx] = best
            print(f'  residu idx {idx} {c} ({qi.count(idx)} px) -> main {best} {mainset[best]}')
    sub = [remap[i] for i in qi]
    pal16 = mainset + [(0, 0, 0)] * (16 - len(mainset))
    # .PALHW: match EXACTE (l'usuari ja dona colors HW; res de nearest).
    palhw = bytearray()
    for c in pal16:
        assert c in RGB2HW, ('color no-HW', c)
        palhw.append(RGB2HW[c])
    out = bytearray()
    for y in range(200):
        for xb in range(80):
            a = sub[y * 160 + xb * 2]
            b = sub[y * 160 + xb * 2 + 1]
            out.append(((a & 1) << 7) | (((a >> 1) & 1) << 3) | (((a >> 2) & 1) << 5) |
                       (((a >> 3) & 1) << 1) | ((b & 1) << 6) | (((b >> 1) & 1) << 2) |
                       (((b >> 2) & 1) << 4) | (((b >> 3) & 1) << 0))
    assert len(out) == 16000
    inter = bytearray(16384)
    for L in range(200):
        base = (L % 8) * 2048 + (L // 8) * 80
        inter[base:base + 80] = out[L * 80:(L + 1) * 80]
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.BIN'), 'wb') as f:
        f.write(bytes(inter))
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.PAL'), 'wb') as f:
        for c in pal16:
            f.write(bytes(c))
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.PALHW'), 'wb') as f:
        f.write(bytes(palhw))
    # Previews + porta WYSIWYG (identics obligats: mateixes dades).
    prev = Image.new('RGB', (160, 200))
    pd = prev.load()
    for y in range(200):
        for x in range(160):
            pd[x, y] = pal16[sub[y * 160 + x]]
    prev.resize((480, 600), Image.NEAREST).save(os.path.join(OUT, name + '_m0.png'))
    raw = bytes(inter)
    hw = Image.new('RGB', (160, 200))
    hd = hw.load()
    for L in range(200):
        base = (L % 8) * 2048 + (L // 8) * 80
        for xb in range(80):
            byte = raw[base + xb]
            b0 = ((byte >> 7) & 1) | (((byte >> 3) & 1) << 1) | \
                 (((byte >> 5) & 1) << 2) | (((byte >> 1) & 1) << 3)
            b1 = ((byte >> 6) & 1) | (((byte >> 2) & 1) << 1) | \
                 (((byte >> 4) & 1) << 2) | (((byte >> 0) & 1) << 3)
            hd[xb * 2, L] = pal16[b0]
            hd[xb * 2 + 1, L] = pal16[b1]
    hw.resize((480, 600), Image.NEAREST).save(os.path.join(OUT, name + '_hw.png'))
    nd = sum(1 for y in range(200) for x in range(160)
             if hd[x, y] != pd[x, y])
    assert nd == 0, (name, nd)
    print(f'{name}: directe {png} -> {len(inter)} B + paleta HW exacta, WYSIWYG ok')


def convert(name, src, y0, y1):
    w, h, pl, pal, px = read_ilbm(unsqz(open(src, 'rb').read()))
    rows = [row[0::2] for row in px[y0:y1]]  # 320 -> 160 (pixel esquerre)
    assert len(rows) == 200 and len(rows[0]) == 160, (len(rows), len(rows[0]))
    im = Image.new('RGB', (320, 200))
    d = im.load()
    for y in range(200):
        for x in range(320):
            d[x, y] = pal[px[y0 + y][x]]
    q = im.quantize(colors=16, method=Image.MEDIANCUT)
    qp = q.getpalette()[:48]
    pal16 = [tuple(qp[i * 3:i * 3 + 3]) for i in range(16)]
    qi = list(q.getdata())
    # Submostreig 320 -> 160 (mateix que el preview _m0: pixel esquerre de
    # cada parella, fila SENCERA). OJO 12/10/26: xb*2 amb xb 0..79 nomes
    # cobreix els pixels 0..159 (meitat esquerra 1:1); cal x*2 amb x 0..159.
    sub = [qi[y * 320 + x * 2] & 0x0F for y in range(200) for x in range(160)]
    out = bytearray()
    for y in range(200):
        for xb in range(80):
            a = sub[y * 160 + xb * 2]
            b = sub[y * 160 + xb * 2 + 1]
            # Byte Mode 0: pixel esq bits 7,5,3,1; dret 6,4,2,0.
            out.append(((a & 1) << 7) | (((a >> 1) & 1) << 3) | (((a >> 2) & 1) << 5) |
                       (((a >> 3) & 1) << 1) | ((b & 1) << 6) | (((b >> 1) & 1) << 2) |
                       (((b >> 2) & 1) << 4) | (((b >> 3) & 1) << 0))
    assert len(out) == 16000
    # ENTRELLACAT HW: el depack escriu cru a 0xC000 i el 6845 llegeix la
    # fila L a ((L%8)*2048)+((L//8)*80)+xb. Un .BIN lineal es veuria
    # "ratllat" (vist 12/10/26). Guardem ja entrellacat (16384 B).
    inter = bytearray(16384)
    for L in range(200):
        base = (L % 8) * 2048 + (L // 8) * 80
        inter[base:base + 80] = out[L * 80:(L + 1) * 80]
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.BIN'), 'wb') as f:
        f.write(bytes(inter))
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.PAL'), 'wb') as f:
        for c in pal16:
            f.write(bytes(c))
    # .PALHW: 16 INKR (Gate Array) pel FRONT (nearest-match 27 colors HW).
    HW = {0x54:(0,0,0),0x44:(0,0,128),0x55:(0,0,255),0x5C:(128,0,0),
          0x58:(128,0,128),0x5D:(128,0,255),0x4C:(255,0,0),0x45:(255,0,128),
          0x4D:(255,0,255),0x56:(0,128,0),0x46:(0,128,128),0x57:(0,128,255),
          0x5E:(128,128,0),0x40:(128,128,128),0x5F:(128,128,255),
          0x4E:(255,128,0),0x47:(255,128,128),0x4F:(255,128,255),
          0x52:(0,255,0),0x42:(0,255,128),0x53:(0,255,255),0x5A:(128,255,0),
          0x59:(128,255,128),0x5B:(128,255,255),0x4A:(255,255,0),
          0x43:(255,255,128),0x4B:(255,255,255)}
    palhw = bytearray()
    for c in pal16:
        best = min(HW.items(), key=lambda kv: sum((a-b)**2 for a,b in zip(kv[1],c)))[0]
        palhw.append(best)
    with open(os.path.join(PROJ, 'assets', 'bbdata', name + '.PALHW'), 'wb') as f:
        f.write(bytes(palhw))
    prev = Image.new('RGB', (160, 200))
    pd = prev.load()
    for y in range(200):
        for x in range(160):
            pd[x, y] = pal16[qi[y * 320 + x * 2]]
    prev.resize((480, 600), Image.NEAREST).save(os.path.join(OUT, name + '_m0.png'))
    # WYSIWYG: rellegeix el .BIN i renderitza'l COM EL HW (entrellacat).
    # Si aquest preview no es identic a _m0.png, el .BIN no es mostrara be.
    raw = open(os.path.join(PROJ, 'assets', 'bbdata', name + '.BIN'), 'rb').read()
    assert len(raw) == 16384, len(raw)
    hw = Image.new('RGB', (160, 200))
    hd = hw.load()
    for L in range(200):
        base = (L % 8) * 2048 + (L // 8) * 80
        for xb in range(80):
            byte = raw[base + xb]
            # desempaqueta Mode 0 (invers de la codificacio de dalt)
            b0 = ((byte >> 7) & 1) | (((byte >> 3) & 1) << 1) | \
                 (((byte >> 5) & 1) << 2) | (((byte >> 1) & 1) << 3)
            b1 = ((byte >> 6) & 1) | (((byte >> 2) & 1) << 1) | \
                 (((byte >> 4) & 1) << 2) | (((byte >> 0) & 1) << 3)
            hd[xb * 2, L] = pal16[b0]
            hd[xb * 2 + 1, L] = pal16[b1]
    hw.resize((480, 600), Image.NEAREST).save(os.path.join(OUT, name + '_hw.png'))
    # PORTA: _hw (render HW del .BIN) ha de ser IDENTIC a _m0 (mateix qi,
    # mateix run). Si difereix, el pack no representa el preview (vist
    # 12/10/26: pack meitat-esquerra vs preview fila-sencera).
    nd = sum(1 for y in range(200) for x in range(160)
             if hd[x, y] != pd[x, y])
    assert nd == 0, (name, nd)
    print(f'{name}: {len(inter)} B + paleta, preview {name}_m0.png + {name}_hw.png (WYSIWYG ok)')


if __name__ == '__main__':
    bb = os.path.join(PROJ, 'assets', 'bbdata')
    convert('SPLASH', os.path.join(bb, 'PRES.SQZ'), 0, 200)
    convert('SELECT', os.path.join(bb, 'CHOIX.SQZ'), 0, 200)
    # MAP: retoc manual de l'usuari (160x200, 16 HW exactes): via directa,
    # sense quantitzar ni reescalar (INTER.SQZ nomes per regenerar el VGA).
    convert_direct('MAP', os.path.join(bb, 'MAP_mode0.png'))
