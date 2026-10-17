import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dskutil import DskPatcher

dsk = DskPatcher('bluesb.dsk')
raw_dir = dsk.read_dir_sectors()
print("Files in bluesb.dsk (AMSDOS directory):")
seen = set()
for i in range(64):
    entry = raw_dir[i*32:(i+1)*32]
    user = entry[0]
    if user != 0xE5 and user < 16:
        name = bytes(entry[1:9]).decode('latin1', errors='replace').rstrip()
        ext = bytes(entry[9:12]).decode('latin1', errors='replace').rstrip()
        full = f"{name}.{ext}"
        extent = entry[12]
        records = entry[15]
        blocks = [b for b in entry[16:32] if b != 0]
        first_b = blocks[0] if blocks else -1
        last_b = blocks[-1] if blocks else -1
        t_start, s_start = dsk.bloc_to_ts(first_b)[0] if blocks else (-1, -1)
        t_end, s_end = dsk.bloc_to_ts(last_b)[-1] if blocks else (-1, -1)
        print(f"  {full:12s} ext={extent} recs={records:3d} (~{records*128:5d} B) blocks={len(blocks):2d} [{first_b:2d}..{last_b:2d}] tracks=[T{t_start:02d}..T{t_end:02d}]")

