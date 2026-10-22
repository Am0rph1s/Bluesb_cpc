#!/usr/bin/env python3
"""Extreu en PNG els sprites de cada tipus d'objecte d'un nivell, segons el
codi DOS (staticres.c).

- Llegeix `level_data` / `level_xpos_<nivell>` / `level_ypos_<nivell>` per saber
  quins tipus hi ha al nivell i on són.
- Llegeix `animframes_059d` (taula d'animacions per tipus) i
  `level_objtypes` (tipus -> op) del mateix staticres.c.
- Els indexs de `animframes_059d` son absoluts dins el buffer de sprites: el
  SQV del nivell es carrega a l'offset SPRITES_COUNT (146), aixi que el frame
  dins l'SQV del nivell = index - 146.
- Descodifica el SQV del nivell (unsqz + planar 4 bitplanes) i en deixa un PNG
  per tipus: la tira son els frames del tipus, retallats al bbox, amb el
  frame dibuixat a la seva posicio original (l'amplada de tela es conserva).

Us:
  py -3 tools/dump_level_sprites.py --level 1 --outdir scratch/sprites_l2
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "bbdata"))

from sprites import load_sqv_frames  # noqa: E402

SPRITES_COUNT = 146  # bb/resource.h
LEVEL_NAMES = ["magasin", "ent", "prison", "egou", "ville", "concert"]
SQV_FILES = ["ENEMI1.SQV", "ENEMI2.SQV", "ENEMI3.SQV",
             "ENEMI4.SQV", "ENEMI5.SQV", "ENEMI6.SQV"]
MAX_OBJECTS = 41


def _arrays(src):
    a = re.search(r"animframes_059d\[\]\s*=\s*\{(.*?)\};", src, re.S).group(1)
    ptrs = [x.strip() for x in a.split(",") if x.strip()]
    cache = {}

    def arr(name):
        if name not in cache:
            m = re.search(re.escape(name) + r"\[\]\s*=\s*\{([^}]*)\}", src)
            cache[name] = ([int(x.strip(), 0) for x in m.group(1).split(",")
                            if x.strip()] if m else [])
        return cache[name]

    return ptrs, arr


def type_frames(src, obj_type):
    """Frames SQV del nivell usats per un tipus d'objecte."""
    ptrs, arr = _arrays(src)
    idx = obj_type * 29
    used = set()
    for k in range(29):
        if idx + k >= len(ptrs):
            break
        for v in arr(ptrs[idx + k])[1:]:
            f = v - SPRITES_COUNT
            if f >= 0:
                used.add(f)
    return sorted(used)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--level", type=int, required=True, choices=range(6))
    p.add_argument("--outdir", default=os.path.join(PROJ, "scratch", "sprites"))
    a = p.parse_args()

    from PIL import Image, ImageDraw

    src = open(os.path.join(PROJ, "tools", "blues_dos", "bb", "staticres.c"),
               encoding="latin1").read()
    lname = LEVEL_NAMES[a.level]
    mx = re.search(r"const int16_t level_xpos_%s\[\]\s*=\s*\{([^}]+)\};" % lname,
                   src, re.S)
    my = re.search(r"const int16_t level_ypos_%s\[\]\s*=\s*\{([^}]+)\};" % lname,
                   src, re.S)
    xs = [int(x.strip(), 0) for x in mx.group(1).split(",") if x.strip()]
    ys = [int(v.strip(), 0) for v in my.group(1).split(",") if v.strip()]
    md = re.search(r"uint8_t level_data\[\]\s*=\s*\{([^}]+)\};", src, re.S)
    types = [int(t.strip(), 0) for t in
             re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", md.group(1))]
    types = types[a.level * MAX_OBJECTS:(a.level + 1) * MAX_OBJECTS]
    mo = re.search(r"const uint8_t level_objtypes\[\]\s*=\s*\{([^}]+)\};", src, re.S)
    ops = [int(x.strip(), 0) for x in mo.group(1).split(",") if x.strip()]

    sqv = os.path.join(PROJ, "assets", "bbdata", SQV_FILES[a.level])
    frames = load_sqv_frames(sqv)
    os.makedirs(a.outdir, exist_ok=True)

    used_types = sorted(set(t for t in types if t != 100))
    for t in used_types:
        fl = type_frames(src, t)
        fl = [f for f in fl if f < len(frames)]
        if not fl:
            continue
        # Tira: cada frame al seu ample original (es conserva l'amplada de tela)
        widths = [frames[f][0] for f in fl]
        total = sum(widths) + 4 * (len(fl) - 1)
        hmax = max(frames[f][1] for f in fl)
        strip = Image.new("RGB", (total, hmax), (0, 0, 0))
        d = ImageDraw.Draw(strip)
        x = 0
        for f in fl:
            w, h, px = frames[f]
            for y in range(h):
                for xx in range(w):
                    v = px[y][xx]
                    if v:
                        strip.putpixel((x + xx, y), (v * 17 % 256, v * 31 % 256,
                                                    v * 47 % 256))
            d.text((x + 1, 1), str(f), fill=(255, 255, 0))
            x += w + 4
        out = os.path.join(a.outdir, "type%02d_%s.png" % (t, lname))
        strip.save(out)
        strip.resize((strip.width * 4, strip.height * 4), Image.NEAREST).save(
            out.replace(".png", "_x4.png"))
        print("type %d (op %d) frames %s -> %s" % (t, ops[t], fl, out))

    # Llista de posicions dels objectes del tipus
    for t in used_types:
        fl = type_frames(src, t)
        slots = [(i, xs[i], ys[i]) for i, tt in enumerate(types) if tt == t]
        print("  type %d: %d objectes %s" % (t, len(slots), slots))


if __name__ == "__main__":
    main()
