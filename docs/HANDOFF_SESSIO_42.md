# Handoff — Blues Brothers CPC (per obrir una sessió nova)

Ets al repo `C:\Projects\bluesb_cpc`: port **1:1 DOS→CPC** de *The Blues Brothers*
(Z80, SDCC 4.5 + sdasz80, build amb Python). Llegeix `AGENTS.md`.

**Idioma: català.** Regla de l'usuari: cap canvi estructural (render, blit,
mirror, **layout de RAM/bancs**) ni build llarg sense **proposta + aprovació**;
valida pas a pas. No inventis mecàniques: el codi DOS de referència és a
`tools/blues_dos/bb/` i `tools/blues_dos/ja/`.

## Estat ja verificat (no cal reconfirmar-ho)

- Build: `py -3 -u tools/build.py`. Verificació: `py -3 tools/build.py --check-boot`
  (~1-2 min; comprova CRC del DSK + arrencada real amb 2 captures) o
  `py -3 -u tools/smoke_test.py [--dsk-only|--boot-only]`.
- Resident (`_CODE`): **13.286 B**, marge **922 B**. `--data-loc 0x3880`.
- DSK: 7 fitxers amb CRC correcte. Arrencada OK: `magic=0xB0`, `px8=256`,
  `py8=8848`. HUD hi és a t=0 i a t+3 s, i s'actualitza (test en viu: escriure
  `g_vinyls_count` → "05").
- **HUD + GAME OVER** viuen al **MUSBANK (C1 compartit)** a `0x4C10` (dades
  `0x4F40`), amb EQUs generats a `obj/hud_ext.s`; el resident els crida amb
  `call_banked(0xC0, (void*)hud_*_o)` i els paràmetres van per `bc_a`/`bc_b`.
- **Layout del C1 (nivell 1)**: `0x5000` imatge (cançó 1.619, HUD 936,
  GAMEOVER a `0x5800`, portes 92, restore 90, **params `0x6900`**), **codi del
  nivell `0x6948` (963 B)**, frames ascensors `0x6E20`, buffers BG `0x7000`,
  dades `0x7500`, còpia FDC `0x7800`.
- **LevelParams v2 (72 B)** a `C1:0x6900`; offsets: `map_w` 52, `map_h` 53,
  `map_rows` 54, `door_count` 55, `rooms_off` 56, `doors_off` 58,
  `restore_off` 60, `map_w_px` 62, `map_w_x2` 64, `cam_max_x4` 66,
  `room_row_last` 68, `code_exc_off` 70. El build els omple (72 B).
- **C5 actual (nivell 1)**: mapa 9.216 + sales 1.000 + TRIG 2.560 + **codi del
  món 4.086 = 16.862 > 16.384** → **no hi cap**: és el que cal arreglar.

## Dades mesurades que necessitaràs

- Mapa compacte (sense files de sales): 9.216 / 9.216 / 9.216 / 7.808 / 12.160 /
  6.272 (nivells 1-6). **Sales** (200 B cadascuna): 5 / 0 / 6 / 3 / 1 / 0.
- **TRIG = 2.560 B** (les 256 entrades amb dades; tile màxim 251 → no compactar).
- Tileset = 16.384 B = 256 × 64 (C4 sempre ple). Player AKG 4.096. Enemics
  nivell 1 = 15.012 (C6).
- **Cançons**: intro 3.091 · main 1.619 (nivells 1,4) · Theme1 2.721 (2,5) ·
  **Theme2 4.670 (3,6)**.
- **Pressupost de 3.2** (C5 = mapa+sales+TRIG · RAM 1 = AKG+cançó+HUD+portes+
  restore+params+codi nivell+**codi món 4.086**+frames+BG+GAMEOVER 1.360+FDC 785):

| Nivell | C5 | lliures | RAM 1 | lliures |
|---|---|---|---|---|
| 1 magasin | 12.776 | +3.608 | 15.443 | +941 |
| 2 ent | 11.776 | +4.608 | 14.146 | +2.238 |
| **3 prison** | 12.976 | +3.408 | **16.191** | **+193** |
| 4 egou | 10.968 | +5.416 | 13.124 | +3.260 |
| 5 ville | 14.920 | +1.464 | 14.154 | +2.230 |
| 6 concert | 8.832 | +7.552 | 16.119 | +265 |

C5 sempre hi cap. A RAM 1, **prison (193 B) i concert (265 B) queden < 256 B**.

## TASCA: Fase 3.2 (canvi ATÒMIC, no es pot fer a trossos)

Les sales no poden entrar a C5 sense treure'n el codi del món (nivell 1 → 16.862 B).

1. **Dieta del codi del món** (~300 B: 4.086 → ~3.786) perquè prison quedi ≥256 B.
2. **`tools/build.py`**: C5 com a **3 seccions** (mapa, sales, TRIG) amb offsets
   al manifest; enllaçar `moving_bank` a la **RAM 1** amb base calculada (com el
   codi del nivell a `build_levelcode()`); bolcar `rooms_off`, `trig_off` (i
   `code_world_off`) a `LevelParams` i actualitzar `LVLPARM_SIZE`.
3. **`src/moving_bank.c`** (ara a C5): `b5_tile_type`, `b5_trig_ptr`, `MAP_MUT`
   → **accessors residents** (poden commutar a C5); eliminar `LEVEL_*` de
   `level_pkg.h` i `s_bank_start_x/y`, `s_bank_map_col` (posicions dels
   ascensors = objectes `op` 4 del paquet).
4. **`src/main.c` / `src/render.c`**: `get_tile_at()` llegeix les sales de **C5**
   via `s_lv.rooms_off`; fora `render_room()` i `check_room_bonus()`;
   `restore_level_tiles()` restaura les sales a C5.
5. **Verificar**: `py -3 tools/build.py --check-boot` + `scratch/verify_door_live.py`
   + `scratch/test_room_vinyls.py`; commit + `ESTAT.md` (sessió 42).

Després: 3.3 (`g_map_level` real), de-hardcodejar `src/enemy.c` (C6, encara usa
`LEVEL_W_PX`/`LEVEL_MAP_H`) i Fase 4 (extractor nivells 2-6, **música per nivell
— avui només es compila "main"**, sprites AVT sense banc assignat).

## Trampes conegudes (no repetir)

- `build.py`: no restaurar versions velles (a la sessió 37 es va perdre
  l'empaquetat de frames/GAMEOVER i el joc no arrencava).
- El commit `bb60b55` és **trencat** (HUD al bloc del nivell → solapament
  `0x7600` amb els buffers d'ascensor); queda superat per `d8ce42b`.
- Funcions bancades: **no reben paràmetres C** (usa `bc_a`/`bc_b`); **no poden
  commutar de banc**; si escriuen a VRAM han de viure a la RAM 1 i cridar-se
  amb `0xC0`.
- sdasz80: sense BOM; no `ld a,(hl+1)`; no `ld hl,de`; push/pop balancejats.
- Els errors LSP de `cpctelera.h`/tipus SDCC són soroll.
- La injecció de tecles a ZEsarUX de vegades falla: l'autoritat és
  `tools/smoke_test.py`.

## Fitxers clau

`tools/build.py` (build, paquets, seccions, asserts, `--check`) ·
`src/main.c` (`load_package`, `get_tile_at`, càmera, portes) ·
`src/level_params.h` · `src/moving_bank.c` (lògica del món, a C5) ·
`src/moving.c`/`moving.h` (wrappers + `bc_*`) · `src/level_code.c` (ascensors) ·
`src/hud_bank.c` · `src/render.c` · `engine/bank5_table.s`/`bank1_table.s` ·
`tools/pack_level.py` · `tools/smoke_test.py` · `docs/PLA_NIVELLS_UNIVERSAL.md`
(§4.4b té el pressupost) · `docs/LEVEL_PACKAGE.md` · `ESTAT.md`.

HEAD = `4cb565d`; arbre net.
