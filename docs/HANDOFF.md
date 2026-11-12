# Guia d'Arquitectura i Estat del Projecte — Blues Brothers CPC

> **Document de referència unificat** · **Branca**: `fix-c1-l3-unlock` · **Actualitzat**: 12/11/2026
> **Repo**: `https://github.com/Am0rph1s/Bluesb_cpc`
> **Target**: Amstrad CPC 6128 (128 KB RAM) — Z80 @ 4 MHz, Mode 0 (16 colors), SDCC 4.5.0 + sdasz80, build Python 3, disc únic DSK de 180 KB.
> Per al detall cronològic de sessions anteriors, consulta [`docs/CHANGELOG.md`](CHANGELOG.md).

---

## 1. Estat Actual del Projecte

El joc complet (tots 6 nivells + selector de personatge/mapa `FRONT`) cap en **un sol disc `.dsk` de 180 KB** (`bluesb.dsk`), amb compilació incremental en ~7 segons (`tools/build.py` + accelerador natiu C# `tools/zx0_native.cs` + memòria cau SHA-256).

### Estat per nivells (1:1 DOS)
| Nivell | Nom / Mapa DOS | Estat | Mecàniques i notes principals |
| :--- | :--- | :--- | :--- |
| **L1** | `magasin` (Centre comercial) | **Completat i estable** | 5 ascensors, cintes transportadores, peixeres, ocells, caixes/globus/paraigües, sales interiors, clipping de reixa de primer pla (`engine/sprite.s`). |
| **L2** | `ent` (Fàbrica / Magatzem) | **En validació fina** | Premses hidràuliques (`PRESS.BIN`), àcid, trampolins 3 altures (`op 24`), dipòsit d'aigua i desaigüe, rampes diagonals suaus (`op 32..39`), gel (`g_on_ice`), xemeneia amb scroll fins a les banderes, enemics/projectils L2. |
| **L3** | `prison` (Presó) | **Integrat i jugable** | `L3WORLD.PAK` + `L3C1.PAK` separat (`code_exc_off = 0`), reixes escalables (`type 6`), palanques/comportes, trampilles temporitzades, forats d'1 tile ajupit. Pendent: `type 4`/op3 (llançadors) i movers `type 5`/`23`. |
| **L4** | `egou` (Clavegueres) | **Integrat i verificat** | Natació 1:1 DOS (`tt == 11/12`), línia de flotació, comportes automàtiques (`b4=67/68`), 16 cel·les `ENEMI4.BIN` (peix petit decoratiu `class 0`, peix gran agressiu `class 2`, rates, aranya). |
| **L5** | `ville` (Ciutat / Teulades) | **Integrat** | `L5WORLD.PAK` + `L5C1.PAK`, bastides (`SCAFFOLD`), paleta Mode 0 ajustada. |
| **L6** | `concert` (Escenari final) | **Integrat** | 2 ascensors d'escenari (`LIFT6.BIN`), spans de focus, seqüència endgame `trigger_func_op40` (ball i retorn al menú). |

---

## 2. Regles d'Or de Disseny i Implementació

1. **Fidelitat 1:1 a DOS (Prohibit inventar mecàniques)**:
   - Tota física, col·lisió, IA d'enemics, animació i regla de nivell s'ha de contrastar sempre amb el codi font original de DOS a [`tools/blues_dos/bb/`](../tools/blues_dos/bb/) (`level.c`, `objects.c`, `tiles.c`, `game.c`, `staticres.c`) i [`tools/blues_dos/ja/`](../tools/blues_dos/ja/).
2. **Conversió matemàtica de coordenades DOS ↔ CPC** (`docs/DOS_CPC_COORDINATES.md`, `tools/dos_coord_converter.py`):
   - A DOS les coordenades són centre horitzontal i base dels peus:
     `cpc_x = (dos_x - w_dos / 2) / 2 = dos_x / 2 - w_cpc / 2`, `cpc_y = dos_y - h_dos`.
   - Mai ajustar posicions a ull.
3. **Pressupost de memòria resident (Bloc 0: `0x0000..0x3FFF`)**:
   - Estat mesurat actual: `_CODE : 0x0100..0x359A` (**13.466 B**, **102 B** de marge fins a `0x3600`), `_DATA : 0x3600..0x3B21` (**1.305 B**), pila lliure (`SP`): **1.245 B**.
   - Tota lògica específica de nivell o no trivial ha d'anar als bancs superiors (`C1`, `C5`, `C6`), **mai** inflar el resident de `main.c`.
4. **Commutació de bancs de maquinari (`0x7F00`)**:
   - Per cridar codi bancat que escriu a VRAM s'utilitza **`0xC0`**, mai `0xC1` (`0xC1` mapeja RAM 7 a `0xC000..0xFFFF` i tapa la pantalla).
   - **`0xC2` i `0xC3` prohibits** (`0xC2` penja la màquina; `0xC3` reinicia).
   - El codi bancat no pot commutar bancs directament ni rebre paràmetres C normals: fer servir `bc_a..bc_r`.
5. **MUSBANK, LVLCHS i FDC (Crític)**:
   - `MUSBANK.BIN` (`C1:0x4000..0x4C00`) allotja `player_akg.bin` (`_akg_init = 0x4009`, `_akg_play = 0x40CE`, `_akg_stop = 0x40BC`). **Mai** escriure-hi taules ni ampliar-ne els blocs AMSDOS reservats.
   - `LVLCHS` (814 B) resideix a `C1:0x5D00` i es copia a `C1:0x7C00..0x7F2D` en carregar el primer nivell (única zona lliure permanent per sobre de la còpia mestra de `FDC.BIN` a `0x7800..0x7BFF`).
6. **Límit de paquet `.PAK`**:
   - Màxim **28 sectors AMSDOS** = 14.336 B en disc (14.208 B de payload). El FDC llegeix a l'scratch `0x8320..0xBBFF` (14.560 B); passar-se desborda l'scratch.

---

## 3. Arquitectura de Memòria (Amstrad CPC 6128 — 128 KB)

```
+---------------------------------------------------------------------------------+
| BLOC 0 (Resident 0x0000..0x3FFF, sempre mapejat a RAM 0)                         |
|  - 0x0038..     : Vector ISR IM1 (300 Hz -> tick + 50 Hz _mus_play)             |
|  - 0x0100..0x359A: _CODE resident (motor genèric, física, vídeo, FDC, blit)      |
|  - 0x3600..0x3B21: _DATA resident (globals, s_lv, càmera, estat del jugador)    |
|  - Fins a 0x3FFE : Pila Z80 (canari de pila actiu)                              |
+---------------------------------------------------------------------------------+
| FINESTRA BANCADA (0x4000..0x7FFF) commutada via Gate Array 0x7F00               |
|                                                                                 |
|  Banc C1 (RAM 1): Àudio compartit + layout variable de nivell                   |
|    - 0x4000..0x4C00: Player AKG (INTOCABLE)                                     |
|    - 0x4C01..0x4FE1: HUD blitter ASM (src/hud_bank.c) + _DATA                   |
|    - 0x5000..      : Cançó + HUD + GAMEOVER + portes + restore + codi excepció  |
|    - 0x7680..0x76CC: LevelParams v3 (77 B)                                      |
|    - 0x7700..      : _DATA del codi d'excepcions (si n'hi ha)                   |
|    - 0x7800..0x7BFF: Còpia mestra de FDC.BIN (PROHIBIT trepitjar)               |
|    - 0x7C00..0x7F2D: Taula LVLCHS (sectors dels 6 nivells)                      |
|                                                                                 |
|  Banc C4 (RAM 4): Tileset compactat del nivell (o FRONT.BIN al menú)            |
|  Banc C5 (RAM 5): Món del nivell                                                |
|    - 0x4000..      : Mapa + sales (rooms_off) + TRIG compacte (5 B/entrada)     |
|    - Darrere TRIG  : Codi dinàmic de nivell (src/moving_bank.c) + _DATA         |
|    - 0x7FE8..0x7FFF: Taula de salts fixa BC_* (8 slots × 3 B = 24 B)            |
|  Banc C6 (RAM 6): Enemics                                                       |
|    - 0x4000..0x4EFF: Taula de cel·les, blocs ZX0, taula restore i s_spawn       |
|    - 0x5000..0x59FF: Cache de 4 cel·les + estat + _DATA d'enemics               |
|    - 0x5A00..0x78xx: Codi compartit d'enemics (ENEMYCODE.BIN, carregat per L1)  |
|    - 0x7900..0x7FFF: LUT de flip (256 B) + pool de fons (6 × 256 B)             |
|  Banc C7 (RAM 7): Frames de Jake/Elwood + buffers de fons de caixes/jugador     |
+---------------------------------------------------------------------------------+
| VRAM (0x8000..0xFFFF): Doble buffer hardware (pàgina 0: 0xC000 / pàgina 1: 0x8000)
+---------------------------------------------------------------------------------+
```

### 3.1 `LevelParams` v3 (77 bytes a `C1:0x7680` → `s_lv` resident)
Definit a `src/level_params.h`, generat per `tools/pack_level.py` i carregat per `level_params_load()`. Camps principals:
- `room_count` (+2), `room_rows` (+4), `room_row0` (+5)
- `start_px` (+34), `start_py` (+36), `cam0_x4` (+38), `cam0_row` (+40), `chk_px` (+42), `chk_py` (+44)
- `map_w` (+52), `map_h` (+53), `map_rows` (+54), `door_count` (+55)
- `rooms_off` (+56), `doors_off` (+58), `restore_off` (+60), `trig_off` (+69), `code_exc_off` (+71, `0` si no té codi d'excepcions), `hud_off` (+73), `gameover_off` (+75).
*(SDCC empaqueta l'struct sense alineació; qualsevol canvi requereix actualitzar `src/level_params.h`, `tools/pack_level.py` i `tools/build.py` alhora).*

---

## 4. Eines, Compilació i Depuració

```powershell
# 1. Regenerar paquets d'un nivell (tileset, mapa, sales, TRIG, restore, params)
py -3 tools/pack_level.py 0                       # L1 (magasin)
py -3 tools/pack_level.py 1 --outdir obj/lvl1     # L2 (ent)
py -3 tools/pack_level.py 2 --outdir obj/lvl2     # L3 (prison)
py -3 tools/pack_level.py 3 --outdir obj/lvl3     # L4 (egou)

# 2. Compilar el joc complet i generar bluesb.dsk
py -3 tools/build.py                              # Build incremental (~7 s)
py -3 tools/build.py -f                           # Rebuild complet (recomprimeix ZX0)

# 3. Validació automàtica
py -3 tools/smoke_test.py --dsk-only              # Catàleg + CRCs del DSK
py -3 tools/smoke_test.py --boot-only             # Arrencada real a ZEsarUX
py -3 tools/build.py --check                      # Build + validació DSK
py -3 tools/build.py --check-boot                 # Build + DSK + arrencada
```

- **Dreceres de test al menú (`src/main.c`)**: mantenir **`1`..`6`** en prémer `SPACE` al menú salta directament a `L1..L6`.
- **Depuració en viu amb ZEsarUX (ZRCP port 10000)**: consulta [`docs/ZESARUX_ZRCP.md`](ZESARUX_ZRCP.md) (mode gràfic i mode silenciós `--vo null --ao null --noconsole`, lectura de memòria en decimal `%d`, resolució de símbols amb `obj/bluesb.map`).
- **Eines gràfiques**: `tools/graphics_tool.py` i `graphics_edit/` per a tilesets, enemics i paletes Mode 0.

---

## 5. Documentació de Suport

| Document | Contingut |
| :--- | :--- |
| [`docs/CHANGELOG.md`](CHANGELOG.md) | Registre cronològic de canvis i sessions anteriors. |
| [`docs/ZESARUX_ZRCP.md`](ZESARUX_ZRCP.md) | Manual de connexió i depuració remota amb ZEsarUX (ZRCP). |
| [`docs/DOS_CPC_COORDINATES.md`](DOS_CPC_COORDINATES.md) | Fórmules oficials de conversió de coordenades DOS ↔ CPC. |
| [`docs/LEVEL_PACKAGE.md`](LEVEL_PACKAGE.md) | Format binari dels paquets `.PAK` i `.ZX0`. |
| [`docs/OPTIMITZACIO_BUILD.md`](OPTIMITZACIO_BUILD.md) | Arquitectura del build ràpid (C# ZX0, SHA-256 cache, CHS). |
| [`docs/INVENTARI_NIVELLS.md`](INVENTARI_NIVELLS.md) | Mides i recursos dels 6 nivells originals. |
| [`docs/PLA_NIVELLS_UNIVERSAL.md`](PLA_NIVELLS_UNIVERSAL.md) | Disseny de l'arquitectura multi-nivell universal. |
| [`docs/PERF_REPORT_L1L2.md`](PERF_REPORT_L1L2.md) | Mesures i anàlisi de rendiment / FPS del motor. |
| [`tools/blues_dos/`](../tools/blues_dos/) | Codi font DOS original de referència absoluta. |

*(Nota: documents antics com `ESTAT_L3_C1_C3.md` o `HANDOFF_SESSIO_42.md` són arxius històrics; la font de veritat actual és aquest document, `tools/build.py`, `obj/C1LAY<n>.BIN` i `obj/bluesb.map`).*
