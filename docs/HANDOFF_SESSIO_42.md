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
- Resident (`_CODE`): **13.286 B**, marge **922 B**. `--data-loc 0x3880`.
- DSK: 7 fitxers amb CRC correcte. Arrencada OK: `magic=0xB0`, `px8=256`,
  `py8=8848`. HUD hi és a t=0 i a t+3 s i s'actualitza (test en viu).
- **HUD + GAME OVER** al **MUSBANK (C1 compartit)** a `0x4C10` (dades `0x4F40`),
  amb EQUs a `obj/hud_ext.s`; el resident els crida amb
  `call_banked(0xC0, (void*)hud_*_o)` i els paràmetres van per `bc_a`/`bc_b`.
- **Layout C1 (nivell 1)**: `0x5000` imatge (cançó 1.619, HUD 936, GAMEOVER a
  `0x5800`, portes 92, restore 90, **params `0x6900`**), **codi del nivell
  `0x6948` (963 B)**, frames `0x6E20`, buffers BG `0x7000`, dades `0x7500`,
  **còpia mestra FDC `0x7800`** (785 B; es restaura a `0x8000` abans de cada
  lectura perquè el memset posterior esborra el motor).
- **LevelParams v2 (72 B)** a `C1:0x6900`; offsets: `map_w` 52, `map_h` 53,
  `map_rows` 54, `door_count` 55, `rooms_off` 56, `doors_off` 58,
  `restore_off` 60, `map_w_px` 62, `map_w_x2` 64, `cam_max_x4` 66,
  `room_row_last` 68, `code_exc_off` 70.
- Mides a `obj/`: `BANK5.BIN` **4.548 B** (codi del món), `MUSMAIN.BIN` 6.472,
  `LEVELCODE.BIN` 963, `ENEMI.BIN` 13.988, `L1WORLD.PAK` 12.908.
- **C5 actual (nivell 1)**: mapa 9.216 + sales 1.000 + TRIG 2.560 + codi del món
  4.548 = **17.324 > 16.384**: no hi cap.

## Dades mesurades que necessitaràs

- Mapa compacte (sense files de sales): 9.216 / 9.216 / 9.216 / 7.808 / 12.160 /
  6.272 (nivells 1-6). **Sales** (200 B): 5 / 0 / 6 / 3 / 1 / 0.
- **TRIG = 2.560 B = 256 entrades × 10 B**, però `b5_check_bonus_triggers` fa
  `if (b6 >= 64) return;` → **només calen les 64 primeres = 640 B** (estalvi
  1.920 B); i encara menys per nivell segons el `b6` màxim real del mapa.
- Tileset = 16.384 B = 256 × 64 (C4 sempre ple). Player AKG 4.096.
- **Cançons**: intro 3.091 · main 1.619 (1,4) · Theme1 2.721 (2,5) ·
  **Theme2 4.670 (3,6)**.
- **Pressupost de 3.2** (C5 = mapa + sales + TRIG64 640 + codi del món 4.548):

| Nivell | C5 | lliures |
|---|---|---|
| 1 magasin | 15.404 | +980 |
| 2 ent | 14.404 | +1.980 |
| 3 prison | 15.604 | +780 |
| 4 egou | 13.596 | +2.788 |
| **5 ville** | **17.548** | **-1.164** |
| 6 concert | 11.460 | +4.924 |

- **El codi del món es QUEDA a C5**: a la RAM 1 no hi cap (nivell 1 +724 B,
  prison +2.568 B per Theme2). La còpia FDC només pot viure a `RAM1:0x7800` (cap
  càrrega hi escriu) o al resident (922 < 785): **no es mou**.

## TASCA: Fase 3.2 (números reals)

1. **Retallar el TRIG** a `tools/pack_level.py`: només calen les entrades
   `b6 < 64` (256×10 → 64×10 = 640 B); millor encara, retallar per nivell al
   `b6` màxim real. Assert al build.
2. **C5 = mapa + sales + TRIG(c) + codi del món**, en seccions separades, amb
   `rooms_off`/`trig_off` (camp nou) reals a `LevelParams` i al manifest.
3. **`src/main.c` / `src/render.c`**: llegir sales i TRIG de C5 amb aquests
   offsets; fora `render_room()` i `check_room_bonus()`.
4. **Ville** (5): decidir com hi entra (17.548 B, −1.164): dieta real del codi del
   món (~800 B) o repartiment propi (sales+TRIG a la RAM 1, que per a ville té
   ~3,2 KB lliures).
5. Verificar els 5 nivells que hi caben (`--check-boot` + portes/sales).

Després: 3.3 (`g_map_level` real), de-hardcodejar `src/enemy.c` (C6, encara usa
`LEVEL_W_PX`/`LEVEL_MAP_H`) i Fase 4 (extractor nivells 2-6, **música per nivell
— avui només es compila "main"**, sprites AVT sense banc assignat).

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

HEAD = bcf6577 (docs). Estat de codi: build verd, marge resident 922 B.
