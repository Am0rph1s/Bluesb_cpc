# Guia d'Arquitectura i Estat del Projecte — Blues Brothers CPC

> **Document de referència unificat** · **Branca**: `fix-c1-l3-unlock` · **Actualitzat**: 12/11/2026
> **Repo**: `https://github.com/Am0rph1s/Bluesb_cpc`
>
> **Nota d'estat (18/11/2026)**: branca `draw-opt-enemy-late` (`3d51ca0`): single buffer estable a **25 fps**, cache de columna a `0xBC00`/`0xBD00`, HUD a **168**, Jake alt `dsy=58` net. `_CODE 0x0100..0x38F9`, `_DATA 0x3A00..0x3B29`. Vegeu [`SINGLE_BUFFER.md`](SINGLE_BUFFER.md) seccions 3.3/4 i [`MEMORY_MAP.md`](MEMORY_MAP.md).
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
| **L3** | `prison` (Presó) | **Integrat i jugable** | `L3WORLD.PAK` + `L3C1.PAK` separat (`code_exc_off = 0`), reixes escalables (`type 6`), palanques/comportes, trampilles temporitzades, forats d'1 tile ajupit. Celes d'enemics corregides el 13/11 (el policia ja no alterna amb la rata) i **bazuka op3 implementada** (el presidiari dispara el coet del frame 13 en diagonal, cela 14). Pendent: els movers `type 5`/`23` (op4/op11 = ascensors). |
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
   - Estat mesurat (17/11/2026, single buffer): `_CODE : 0x0100..0x38F9` (**14.585 B**, **632 B** de marge fins a `_DATA` a `0x3A00`), `_DATA : 0x3A00..0x3B29` (**297 B**), pila útil (`SP` fins al canari `0x3C40`): **958 B**.
   - Les dades fredes (`s_lv`, `g_mag_elevators`, `s_carry_bg_c0`, estat de frame i dades de càrrega) viuen als gaps de RAM 2; vegeu [`docs/MEMORY_MAP.md`](MEMORY_MAP.md).
   - Tota lògica específica de nivell o no trivial ha d'anar als bancs superiors (`C1`, `C6`), **mai** inflar el resident de `main.c`. **C5 (L1/L5) i L2WORLD no tenen marge** (236/300 B i 313 B).
4. **Commutació de bancs de maquinari (`0x7F00`)**:
   - Per cridar codi bancat que escriu a VRAM s'utilitza **`0xC0`**, mai `0xC1` (`0xC1` mapeja RAM 7 a `0xC000..0xFFFF` i tapa la pantalla).
   - **`0xC2` i `0xC3` prohibits** (`0xC2` penja la màquina; `0xC3` reinicia).
   - El codi bancat no pot commutar bancs directament ni rebre paràmetres C normals: fer servir `bc_a..bc_r`.
5. **MUSBANK, LVLCHS i FDC (Crític)**:
   - `MUSBANK.BIN` (`C1:0x4000..0x4C00`) allotja `player_akg.bin` (`_akg_init = 0x4009`, `_akg_play = 0x40CE`, `_akg_stop = 0x40BC`). **Mai** escriure-hi taules ni ampliar-ne els blocs AMSDOS reservats.
   - `LVLCHS` (814 B) resideix a `C1:0x5D00` i es copia a `C1:0x7C00..0x7F2D` en carregar el primer nivell (única zona lliure permanent per sobre de la còpia mestra de `FDC.BIN` a `0x7800..0x7BFF`).
6. **Límit de paquet `.PAK`**:
   - Màxim **13.536 B de payload** (`0x8320..0xB800`): el pak es carrega a `0x8320` i el codi resident de RAM 2 comença a `0xB800`. Els 28 sectors AMSDOS (14.336 B) són només l'allocació de disc; el payload que s'escriu a memòria no pot passar de 13.536 B. El build (`PAK_SCRATCH_MAX`) ho valida i avisa si queden menys de 512 B.

---

## 3. Arquitectura de Memòria (Amstrad CPC 6128 — 128 KB)

```
+---------------------------------------------------------------------------------+
| BLOC 0 (Resident 0x0000..0x3FFF, sempre mapejat a RAM 0)                         |
|  - 0x0038..     : Vector ISR IM1 (300 Hz -> tick + 50 Hz _mus_play)             |
|  - 0x0100..0x38F9: _CODE resident (motor genèric, física, vídeo, FDC, blit)      |
|  - 0x3A00..0x3B29: _DATA resident (globals, càmera, estat del jugador)          |
|  - Canari 0x3C40; fins a 0x3FFE: pila Z80 (~958 B útils)                        |
+---------------------------------------------------------------------------------+
| FINESTRA BANCADA (0x4000..0x7FFF) commutada via Gate Array 0x7F00               |
|                                                                                 |
|  Banc C1 (RAM 1): Àudio compartit + layout variable de nivell                   |
|    - 0x4000..0x4C00: Player AKG (INTOCABLE)                                     |
|    - 0x4C01..0x4E7E: HUD blitter ASM (src/hud_bank.c); lliure 0x4E7F..0x4FC0    |
|    - 0x4FC0..0x5000: _DATA del HUD                                              |
|    - 0x5000..      : Cançó + HUD + GAMEOVER + portes + restore + codi excepció  |
|    - 0x7680..0x76DD: LevelParams v3 + paleta (93 B)                             |
|    - 0x7700..      : _DATA del codi d'excepcions (si n'hi ha)                   |
|    - 0x7800..0x7BFF: Còpia mestra de FDC.BIN (PROHIBIT trepitjar)               |
|    - 0x7C00..0x7F2D: Taula LVLCHS (sectors dels 6 nivells)                      |
|                                                                                 |
|  Banc C4 (RAM 4): Tileset compactat del nivell (o FRONT.BIN al menú)            |
|  Banc C5 (RAM 5): Món del nivell                                                |
|    - 0x4000..      : Mapa + sales (rooms_off) + TRIG compacte (5 B/entrada)     |
|    - Darrere TRIG  : Codi dinàmic de nivell (src/moving_bank.c) + _DATA         |
|    - 0x7FE8..0x7FFF: Taula de salts fixa BC_* (8 slots × 3 B = 24 B)            |
|    - Lliure real: L1 236 B, L5 300 B (coll; no hi afegir codi)                  |
|  Banc C6 (RAM 6): Enemics                                                       |
|    - 0x4000..0x4B1F: Taula de cel·les + blocs ZX0                              |
|    - 0x4B20..0x4C1F: Taula de spawn                                            |
|    - 0x4C20..0x4FFF: Taula de restauració de tiles                             |
|    - 0x5000..0x51FF: _DATA d'enemics                                            |
|    - 0x5200..0x78FF: Codi compartit d'enemics (ENEMYCODE.BIN, carregat per L1)  |
|    - 0x7900..0x7FFF: LUT de flip (256 B) + pool de fons (6 × 256 B)             |
|  Banc C7 (RAM 7): Frames de Jake/Elwood + buffers de fons de caixes/jugador     |
+---------------------------------------------------------------------------------+
| VRAM 0xC000..0xFFFF: single buffer (ring 0x3000..0x33FF)                        |
| RAM 2 0x8000..0xBFFF: utilitat (cel·les, HUD, codi RAM2, FDC); vegeu MEMORY_MAP  |
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
- **Depuració avançada amb CPCSyntaxError (API port 6128 / `cpcse-ctl`)**: [`tools/cpcse_dbg.py`](../tools/cpcse_dbg.py) exporta automàticament `obj/bluesb.sym` (des de `obj/bluesb.noi` + `obj/main.rst`), arrenca `cpcse.exe --api=6128 --symbols obj/bluesb.sym` i ofereix `boot_level(n)`, lectura/escriptura per nom de símbol, *breakpoints* condicionals, *watchpoints* de lectura/escriptura, `disasm`, avanç per `frames(n)` i captures `.png`. També es pot fer servir l'API interactiva amb `cpcse-ctl.exe` o el servidor MCP (`--mcp`, port `6129`).

- **Auditoria de cel·les d'enemics** (`py -3 tools/check_enemy_cells.py`): identifica cada cel·la d'`ENEMI<n>.BIN` amb el frame DOS que li correspon (`staticres.c` → `animframes_059d`) i comprova que la taula de spawns (`tools/gen_enemy_spawn.py`) apunta a les cel·les correctes. **Executa'l després de tocar `gen_enemy_spawn.py` o `gen_enemy*_frames.py`**: ha detectat el bug de L3 (13/11/2026) en què el policia alternava el seu fotograma amb el de la rata i la rata sortia dibuixada com un projectil.

### 4.1 Gràfics Editats i Unificació de Paletes (Mode 0, 16 Pens)
- **Flux d'edició i reintegració** ([`graphics_edit/README.md`](../graphics_edit/README.md)):
  - Edita els PNGs i `palette.json` dins `graphics_edit/` (`level*/tileset.png`, `enemies.png`, `player_jake/jake.png`, `player_elwood/elwood.png`, `screen_splash/`, `screen_map/`).
  - Per sincronitzar des del joc cap a `graphics_edit/`: `py -3 tools/graphics_tool.py export`
  - Per reimportar els teus canvis als binaris (`TILESET*.BIN`, `ENEMI*.BIN`, `PFRAMES.BIN`, etc.) i generar el disc: `py -3 tools/graphics_tool.py import` (i `py -3 tools/build.py --check` per validar el `.dsk`).
- **Unificació de paletes per no malgastar pens**:
  - En Mode 0 els **16 pens (0..15)** són compartits simultàniament per **jugador + HUD + tileset + enemics**.
  - **Slots reservats per Jake/Elwood i HUD**: Pen `0` (`0x4B` blanc), Pen `1` (`0x47` pell), Pen `4` (`0x44` blau marí), Pen `11` (`0x54` negre). Són els **contracte d'identitat**: el jugador i el HUD es dibuixen amb la paleta del nivell, així que aquests 4 pens han de tenir el mateix color als 6 nivells.
  - **Pens reals que fa servir cada asset** (mesurat 12/11/2026, `tools/palette_audit.py`): Jake `0,1,4,5,11,12` · Elwood `0,1,4,5,10,11,13` · HUD `0,1,2,4,7,11,12,13` · enemics `0,1,4,9,10,11,12,13`.
  - **Com funciona `import` amb les paletes** (`tools/graphics_tool.py:504-826`): parteix de `DEFAULT_PALETTES` (còpia a `graphics_tool.py:153`), hi superposa `palette.json` de cada nivell (`ga_code`/`hw_code`/`rgb` més proper) i, si el resultat difereix, reescriu `LEVEL_PALETTES` a `tools/pack_level.py` i repacka els 6 nivells. **`palette.json` mana sobre `pack_level.py`**.
  - **Com funciona la quantització (el punt clau)**: `import` converteix cada píxel del PNG al **pen més proper de la paleta**. Per tant (a) un color que no existeix a la paleta **es canvia de color en silenci**, i (b) la **paleta és la font de veritat dels colors**, no el PNG. Abans d'editar un PNG amb un color nou, cal afegir un pen nou a la paleta.
  - **`palette.json` del jugador NO és la paleta de runtime**: `player_jake/palette.json` i `player_elwood/palette.json` són només el mapa d'importació RGB→pen. La paleta que es veu al joc és `LEVEL_PALETTES[nivell]` → `s_lv.palette` → `palette_table` (`src/main.c:836`).
  - **Particularitats / perills coneguts**:
    1. Cal mantenir sincronitzats `DEFAULT_PALETTES`, `LEVEL_PALETTES` i els `palette.json` (estat verificat 12/11: tots tres coincideixen). `import` **no llegeix** `LEVEL_PALETTES`: compara `palette.json` amb `DEFAULT_PALETTES` i només reescriu si difereixen.
    2. ~~Bug del `re.sub` que corrompia `pack_level.py`~~ **Corregit 12/11/2026**: ara el bloc `LEVEL_PALETTES` es reescriu fins a la línia `]` i es conserven els comentaris `# L1..L6` (simulat sobre el fitxer real: sintaxi vàlida, mateix nombre de línies).
    3. Mides obligatòries: `tileset.png` 128×256, `enemies.png` 64×128, pantalles 160×200, jugadors 96×150 (si no, `assert`).
    4. Si existeix `edit/tileset_edit.png` o `edit/enemies_cpc.png`/`enemies_edit.png`, **sobreescriu** `tileset.png`/`enemies.png` abans d'importar. **Aquestes sobrescriptures són el master real**: `edit/tileset_edit.png` de L4/L6 és l'art editat que encara no era als binaris (12/11/2026).
    5. Enemics i jugadors usen alfa (`<128` = transparent, màscara); tileset i pantalles no.
    6. Un canvi de paleta força repacking dels 6 nivells; un canvi de personatge crida `build_level_bundles`; sempre acaba amb `build.main()`.
  - **Regla d'auditoria creuada**: no crear pens nous sense revisar els ja existents entre tileset i enemics; s'unifiquen colors equivalents i s'eliminen duplicats o slots morts per aprofitar tots els 16 pens (taula `LEVEL_PALETTES[0..5]` a `tools/pack_level.py` sincronitzada amb `graphics_edit/level*/palette.json`).

### 4.2 Eines de paletes (auditoria i ajust)

```powershell
py -3 tools/palette_audit.py            # sincronia, pens per asset, duplicats, coherencia PNG<->binari
py -3 tools/palette_fit.py --preview    # paleta proposada ajustada als colors reals de l'art + previews
py -3 tools/palette_fit.py --apply      # escriu pack_level.py + graphics_tool.py + palette.json
py -3 tools/refresh_enemy_png.py 1 3 --edit   # reexporta els PNG d'enemics des dels binaris vigents
py -3 tools/reimport_level.py 3         # reimporta UN nivell (mateixa logica que graphics_tool import) i reconstrueix
py -3 tools/verify_palettes.py          # ZEsarUX: paleta a la VRAM + contracte de pens dels 6 nivells
```

- **`palette_audit.py`**: detecta errors de sincronia entre les tres fonts de paleta, quins pens fa servir cada asset, colors duplicats, pens morts, **violacions del contracte de pens** i **PNG master desincronitzats amb el binaire**.
- **`palette_fit.py`**: construeix una paleta que (1) fixa el contracte `0,1,4,11`, (2) conserva el color de tot pen que l'art fa servir, (3) dona pen a tot color de l'art que abans no en tenia i (4) deixa els 16 pens amb colors **inhibits**.
- **`refresh_enemy_png.py`**: reexporta `enemies.png` des del binaire (i l'override `edit/`), perquè `import` no regressi l'art DOS 1:1.
- **`reimport_level.py`**: reimporta i repacka només els nivells indicats (iteracions ràpides sense reimportar els 6).
- **`verify_palettes.py`**: arrenca un ZEsarUX per nivell, llegeix `palette_table` de la VRAM i comprova que és idèntica a `LEVEL_PALETTES` i que els pens del contracte es compleixen.
- Detall complet del diagnòstic i de les correccions: [`docs/AUDITORIA_PALETES.md`](AUDITORIA_PALETES.md).

---

## 5. Documentació de Suport

| Document | Contingut |
| :--- | :--- |
| [`docs/MEMORY_MAP.md`](MEMORY_MAP.md) | Mapa canònic de bancs, RAM 2, paks i colls d'ampolla (single buffer). |
| [`docs/CHANGELOG.md`](CHANGELOG.md) | Registre cronològic de canvis i sessions anteriors. |
| [`docs/AUDITORIA_PALETES.md`](AUDITORIA_PALETES.md) | Diagnòstic i ajust de les paletes Mode 0 dels 6 nivells (contracte de pens, colors duplicats, coherència PNG↔binari). |
| [`docs/ZESARUX_ZRCP.md`](ZESARUX_ZRCP.md) | Manual de connexió i depuració remota amb ZEsarUX (ZRCP). |
| [`docs/DOS_CPC_COORDINATES.md`](DOS_CPC_COORDINATES.md) | Fórmules oficials de conversió de coordenades DOS ↔ CPC. |
| [`docs/LEVEL_PACKAGE.md`](LEVEL_PACKAGE.md) | Format binari dels paquets `.PAK` i `.ZX0`. |
| [`docs/OPTIMITZACIO_BUILD.md`](OPTIMITZACIO_BUILD.md) | Arquitectura del build ràpid (C# ZX0, SHA-256 cache, CHS). |
| [`docs/INVENTARI_NIVELLS.md`](INVENTARI_NIVELLS.md) | Mides i recursos dels 6 nivells originals. |
| [`docs/AUDITORIA_PALETES.md`](AUDITORIA_PALETES.md) | Diagnòstic i ajust de les paletes Mode 0 (contracte de pens, colors duplicats, coherència PNG↔binari). |
| [`docs/PLA_NIVELLS_UNIVERSAL.md`](PLA_NIVELLS_UNIVERSAL.md) | Disseny de l'arquitectura multi-nivell universal. |
| [`docs/PERF_REPORT_L1L2.md`](PERF_REPORT_L1L2.md) | Mesures i anàlisi de rendiment / FPS del motor. |
| [`tools/blues_dos/`](../tools/blues_dos/) | Codi font DOS original de referència absoluta. |

*(Nota: documents antics com `ESTAT_L3_C1_C3.md` o `HANDOFF_SESSIO_42.md` són arxius històrics; la font de veritat actual és aquest document, `tools/build.py`, `obj/C1LAY<n>.BIN` i `obj/bluesb.map`).*
