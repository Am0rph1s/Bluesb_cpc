# Handoff — Blues Brothers CPC (per obrir una sessió nova)

Ets al repo `C:\Projects\bluesb_cpc`: port **1:1 DOS→CPC** de *The Blues Brothers*
(Z80, SDCC 4.5 + sdasz80, build amb Python). Llegeix `AGENTS.md`.

**Idioma: català.** Regla de l'usuari: cap canvi estructural (render, blit,
mirror, **layout de RAM/bancs**) ni build llarg sense **proposta + aprovació**;
valida pas a pas. No inventis mecàniques: el codi DOS de referència és a
`tools/blues_dos/bb/` i `tools/blues_dos/ja/`.

## Estat ja verificat (no cal reconfirmar-ho)

- Build: `py -3 -u tools/build.py`. Verificació: `py -3 tools/build.py --check-boot`
  (~1-2 min; CRC del DSK + arrencada real amb 2 captures) o
  `py -3 -u tools/smoke_test.py [--dsk-only|--boot-only]`.
- Resident (`_CODE`): **13.407 B**, marge **801 B**. `--data-loc 0x3880`.
- DSK: 15 fitxers amb CRC correcte (L1 i L2). Arrencada L1 OK: `magic=0xB0`,
  `px8=256`, `py8=8848`. HUD hi és a t=0 i a t+3 s i s'actualitza (test en viu).
- **HUD + GAME OVER** al **MUSBANK (C1 compartit)** a `0x4C10` (dades `0x4F40`),
  amb EQUs a `obj/hud_ext.s`; el resident els crida amb
  `call_banked(0xC0, (void*)hud_*_o)` i els paràmetres van per `bc_a`/`bc_b`.
- **Layout C1 (nivell 1)**: `0x5000` imatge (cançó 1.619, HUD 936, GAMEOVER a
  `0x5800`, portes 92, restore 90, **params `0x6900`**), **codi del nivell
  `0x6950` (963 B)**, frames `0x6E20`, buffers BG `0x7000`, dades `0x7500`,
  **còpia mestra FDC `0x7800`** (785 B; es restaura a `0x8000` abans de cada
  lectura perquè el memset posterior esborra el motor).
- **LevelParams v2 (73 B)** a `C1:0x6900`; offsets: `map_w` 52, `map_h` 53,
  `map_rows` 54, `door_count` 55, `rooms_off` 56, `doors_off` 58,
  `restore_off` 60, `map_w_px` 62, `map_w_x2` 64, `cam_max_x4` 66,
  `room_row_last` 68, `trig_off` 69, `code_exc_off` 71.
- Mides a `obj/`: `BANK5.BIN` **4.156 B** (codi del món), `MUSMAIN.BIN` 6.472,
  `LEVELCODE.BIN` 963, `ENEMI.BIN` 13.988, `L1WORLD.PAK` **12.235**.
- **C5 actual (nivell 1)**: mapa 9.216 + sales 1.000 + TRIG5 **1.160** + codi del
  món 4.156 = **15.532**, **852 B lliures** (`_DATA` enganxada + tiles compactes).
  C4: `TILESETC0.BIN` **14.848 B** (232 tiles), **1.536 B lliures**.

## Dades mesurades que necessitaràs

- Mapa compacte (sense files de sales): 9.216 / 9.216 / 9.216 / 7.808 / 12.160 /
  6.272 (nivells 1-6). **Sales** (200 B): 5 / 0 / 6 / 3 / 1 / 0.
- **TRIG = 256 entrades × 10 B**, però el runtime només llegeix els bytes
  **0, 1, 2, 6 i 9** → es desa **compacte a 5 B** (`TRIGC<n>.BIN`; L1 1.160 B).
  (El retall a 64 entrades era incorrecte: s'indexa pel tile id, no per `b6`.)
- **Tiles compactes**: `pack_level.py` reordena el tileset amb els IDs usats i
  remapeja mapa/sales/TRIG/restore/anims. L1: 232 tiles (14.848 B); C4 ja no
  va sempre ple. Player AKG 4.096.
- **Assets dels 6 nivells**: `tools/extract_level_assets.py` genera
  `TILESET/MAP/TRIG/ROOMS/DOORS<n>.BIN` (L1 idèntic; portes 23/0/24/20/2/6).
  `build_music` ja llegeix `DOORS0.BIN` en lloc de la llista hardcoded.
- **Cançons**: intro 3.091 · main 1.619 (1,4) · Theme1 2.721 (2,5) ·
  **Theme2 4.670 (3,6)**.
- **Pressupost de 3.2** (C5 = mapa + sales + TRIG5 + codi 4.156; TRIG/tiles
  compactes depenen del `N` de cada nivell):

| Nivell | N tiles | TRIG5 | C4 (lliures) | codi | C5 | lliures |
|---|---|---|---|---|---|---|
| 1 magasin | 232 | 1.160 | 14.848 (1.536) | 4.156 | 15.532 | **+852** |
| 2 ent | 186 | 930 | 11.904 (4.480) | 2.964 | 13.110 | +3.274 |
| 3 prison | 209 | 1.045 | 13.376 (3.008) | 3.060 | 14.521 | +1.863 |
| 4 egou | 210 | 1.050 | 13.440 (2.944) | 2.996 | 12.454 | +3.930 |
| **5 ville** | 204 | 1.020 | 13.056 (3.328) | 2.964 | 16.344 | **+40** |
| 6 concert | 164 | 820 | 10.496 (5.888) | 2.660 | 9.752 | +6.632 |

(Els codis de L1 són amb 5 ascensors; L2-L6 amb 0 ascensors/span. Falta
afegir-hi els movers genèrics/animacions de cada nivell. Totes les dades
de mapa/sales/TRIG/tiles ja estan extretes amb `tools/extract_level_assets.py`.)

- **El codi del món es QUEDA a C5**: a la RAM 1 no hi cap (nivell 1 +724 B,
  prison +2.568 B per Theme2). La còpia FDC només pot viure a `RAM1:0x7800` (cap
  càrrega hi escriu) o al resident (801 < 785): **no es mou**.

## Fase 3.2 — FET (sessió 42)

1. [x] `tools/pack_level.py`: genera `TRIGC<n>.BIN` de 5 B/entrada i compacta
   els IDs de tile (`TILESETC/MAPC/ROOMSC`); `LevelParams` de 73 B amb `trig_off`.
2. [x] `tools/build.py`: C5 = **mapa (0x4000) + sales (0x6400) + TRIG5 (0x67E8)
   + codi (0x6E00)**, en 3 seccions del manifest; sales fora de la imatge C1;
   assert de mides i offsets. C5 = 15.532 B, **852 lliures** (`_DATA` enganxada
   al codi -392 B + tiles compactes).
3. [x] Resident: sales/TRIG llegits de C5 amb `rooms_off`/`trig_off`; stride 5 a
   `get_trig_byte` i `engine/bank5_table.s` (`tp[3]`=b6, `tp[4]`=avt);
   restauració de sales C1->C5; `render_room`/`enter_door` sense 20/40/74/148.
4. [ ] **Ville**: ~-1.147 B (N~203). Traient sales+TRIG de C5 queda a **+68 B**;
   cal encara ~188 B (mover ASM genèric/op-mask) per tenir el marge de 256 B.
5. [~] Verificat el nivell 1 (l'únic que existeix): `--check-boot`, sales/discs,
   bonus/malus, cor, ball, sortida, mort/respawn i instrument de sala. Prison
   (+532 B) ja passa el marge de 256 B amb `_DATA` empaquetada.

Prototip ASM del mover genèric (Fase 4, NO linkat): `engine/mover_gen.s` +
`src/mover_def.h` + `tools/measure_mover_sizes.py`; **646 B** vs 1.062 B C.

Verificació en viu feta amb scripts temporals (ZEsarUX): `test_room_vinyls.py`,
trigger live (Zrcp) i arrencada `tools/smoke_test.py --boot-only`.

Després: de-hardcodejar `src/enemy.c` (C6, encara usa
`LEVEL_W_PX`/`LEVEL_MAP_H`) i Fase 4 (extractor nivells 2-6, **música per nivell
— avui només es compila "main"**, sprites AVT sense banc assignat).

## Fase 3.3: L1 -> mapa -> L2 (verificat en emu)

- `src/main.c`: taules de world/enemy per als nivells 1-2 (`g_l2world`,
  `g_l2enemi`, CRCs de `disk_tables.h`; clamp temporal `lvl > 1 -> 1`).
  `g_map_level` es conserva entre nivells (s'inicialitza abans del bucle
  exterior; game over el torna a 0).
- En completar el nivell, 50 frames de celebració i salt al FRONT. **Cal
  recarregar `FRONT.BIN` a C4 abans de cridar `FRONT_RUN`**: el tileset del
  nivell sobreescriu C4, i sense recarregar-lo el salt anava a dades de tiles
  (pantalla de brossa). Helper `load_front_bank()` compartit amb el game over.
- `tools/pack_level.py`: el spawn genèric de nivells 2-6 ara fa
  `start_py = ypos_arr[39] - 30` (DOS dona peus; `s_py8` és la cantonada
  superior, com el cas hardcoded de Magasin). Sense això, L2 naixia 30 px
  sota el terra i queia fora del mapa.
- `tools/smoke_test.py`: el check del DSK inclou L2WORLD/L2ENEMI.
- VERIFICAT (2026-10-22, build sense debug): `--check` verd; transició
  L1 completada -> mapa -> L2: `s_lv.level_id==1`, `g_map_level==1`, start
  px8=256/py8=8848, 3 vides; estable 3 s i caminant fins px8=976. Captures:
  `scratch/l2_map_transition.png` (mapa) i `scratch/l2_final2b.png` (L2).
- Post-nivell = **NOMES mapa** (`FRONT_MAP`, C4:0x4003 -> `front_map()`), com
  `do_inter_screen` del DOS: no splash/select, espera ~4 s o SPACE i deixa el
  mapa a VRAM mentre `load_level_packages()` fa les lectures FDC. El FRONT
  sencer (`FRONT_RUN`) queda per a l'arrencada i el game over. El mapa usa
  `g_map_level` ja incrementat.
- Les imatges del FRONT són **160x200**, però el joc fa servir R6=22 (176
  línies, HUD a sota). `f_crtc_200()` posa R6=25 a `front_run()`/`front_map()`
  per mostrar les 200 línies; `video_init()` torna a R6=22 en carregar el
  nivell. Això omple les ~24 línies que faltaven a la part baixa del mapa.
- L2 ja té frames/spawns propis (vegeu Fase 3.4); queden tipus 11/22 i la
  fidelitat fina de les animacions. Sense commit.

## Fase 3.4: enemics L2 (primer pas, verificat visualment)

- `tools/gen_enemy2_frames.py`: genera `assets/bbdata/ENEMI2.BIN` (16 celes
  de 512 B) des de `ENEMI2.SQV` (35 frames). Celes: 1 tret tipus 12, 2
  llançament tipus 14, 5/6 walk tipus 12, 7/8 walk tipus 13, 9/10 walk tipus
  14, 11/12 walk tipus 21, 13 projectils L1, 15 llançament tipus 21.
- `tools/gen_enemy_spawn.py`: genera `obj/lvl1/enemy_spawn.h` des de
  `staticres.c` (`level_data`/`level_xpos_ent`/`level_ypos_ent`), amb la
  conversió DOS peus -> CPC top (`x/2-8`, `y-32`).
- `src/enemy.c`: `Spawn` té `aim_cell`/`throw_cell`; la taula L1 queda
  intacta sota `#if LEVEL_ID == 0` i L2 inclou el header generat. `build.py`
  tria `ENEMI<n>.BIN` i regenera el header de spawn per nivell.
- Mapatge actual L2: tipus 12 -> kind 4 (policia), 13 -> kind 18 (walker),
  14/21 -> kind 17 (cambrera). 15 walkers actius.
- VERIFICAT: build/DSK verd, L1 boot OK, transició mapa -> L2 i enemic visible
  a la zona de `x=248` (`scratch/l2_enemy.png`). L1 conserva els seus spawns i
  frames.
- PENDENT: tipus 11 (sprite de 48 px) i tipus 22 (objecte) no entren a
  l'atlas de 16 px; tipus 13/21 són aproximacions de comportament i cal
  contrastar les seqüències exactes d'animació DOS. Sense commit.

## Trampes conegudes (no repetir)

- `build.py`: no restaurar versions velles (a la sessió 37 es va perdre
  l'empaquetat de frames/GAMEOVER i el joc no arrencava).
- El commit `bb60b55` és **trencat** (HUD al bloc del nivell → solapament
  `0x7600` amb els buffers d'ascensor); superat per `d8ce42b`.
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
`src/hud_bank.c` · `src/render.c` · `engine/bank5_table.s` / `bank1_table.s` ·
`tools/pack_level.py` · `tools/smoke_test.py` ·
`docs/PLA_NIVELLS_UNIVERSAL.md` (§4.4b) · `docs/LEVEL_PACKAGE.md` · `ESTAT.md`.

HEAD = ba4bacc (docs) + Fase 3.2/3.3. Build verd (`--check`), marge resident 801 B, C5 L1 852 B lliures; transició L1->L2 verificada en emu.
