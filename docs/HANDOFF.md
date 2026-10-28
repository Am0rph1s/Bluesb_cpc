# Handoff Global — Blues Brothers CPC (Estat Actual i Guia de Continuació)

> **Document unificat de referència per reprendre el desenvolupament**
> **Data d'actualització**: 28 d'octubre de 2026
> **Branca**: `fix-c1-l3-unlock` — HEAD `4e53f58` + integració de L3 en l'arbre de treball (pendent de commit)
> **Repo**: `https://github.com/Am0rph1s/Bluesb_cpc`
> **Target**: Amstrad CPC 6128 (128 KB RAM) — Z80, Mode 0 (16 colors), SDCC 4.5.0 + sdasz80, build amb Python 3.

---

## 1. Regles d'Or No Negociables (Llegir abans de tocar codi)

1. **Fidelitat 1:1 a DOS (Prohibit inventar mecàniques)**:
   - Tota física, col·lisió, IA d'enemics, animació i sincronització de nivell prové directament del codi font original de DOS:
     - `tools/blues_dos/bb/` (`level.c`, `objects.c`, `tiles.c`, `game.c`, `staticres.c`)
     - `tools/blues_dos/ja/`
   - Mai ajustar valors a ull ni per intuïció. Per a coordenades, utilitzar la fórmula oficial:
     `cpc_x = dos_x / 2 - w_cpc / 2`, `cpc_y = dos_y - h_dos` (`docs/DOS_CPC_COORDINATES.md`).
2. **Pressupost de memòria resident (Bloc 0: `0x0000..0x3FFF`)**:
   - `_CODE`: `0x0100..0x3826` (**14.118 B**), amb **90 B** de marge fins a `_DATA` (`0x3880`).
   - `_DATA`: `0x3880..0x3CDE` (1.108 B, inclou `s_lv`). Pila lliure: ~800 B.
   - Qualsevol lògica nova no trivial s'ha de compilar en bancs superiors (C1, C4-C7), mai al resident.
3. **Regla de commutació de maquinari**:
   - Per cridar codi bancat que escriu a VRAM s'utilitza `0xC0`, mai `0xC1`
     (`0xC1` mostra la RAM 7 a `0xC000..0xFFFF` i tapa la pantalla; `0xC0` manté la VRAM visible a la pàgina 0).
   - `C2` i `C3` **no s'han de fer servir** (`OUT(0x7F00,0xC2)` penja la màquina; C3 reinicia).
4. **Idioma de comunicació**: Català.

---

## 2. Comandes Principals de Treball

```powershell
# 1. Regenerar paquets de dades d'un nivell (reordena tilesets, compacta TRIG, genera LevelParams)
py -3 tools/pack_level.py 0                       # Nivell 1
py -3 tools/pack_level.py 1 --outdir obj/lvl1     # Nivell 2
py -3 tools/pack_level.py 2 --outdir obj/lvl2     # Nivell 3

# 2. Compilar el joc complet i generar bluesb.dsk
py -3 tools/build.py                              # Build incremental
py -3 tools/build.py -f                           # Rebuild complet (recomprimeix tots els ZX0)

# 3. Validació automàtica en emulador
py -3 tools/smoke_test.py --dsk-only              # Només catàleg + CRCs del DSK
py -3 tools/smoke_test.py --boot-only             # Arrencada real a L1 (magic=0xB0)
py -3 tools/build.py --check                      # Build + validació DSK
py -3 tools/build.py --check-boot                 # Build + DSK + arrencada

# 4. Arrencar ZEsarUX amb connexió remota ZRCP (port 10000)
# Des de tools/ZEsarUX_windows-13.0:
.\zesarux.exe --machine CPC6128 --enable-dsk --dsk-file ..\..\bluesb.dsk --enable-remoteprotocol --remoteprotocol-port 10000
```

Dreceres de test a `src/main.c`: mantenir **`2`** en arrencar entra directament a L2; **`3`** entra a L3.
Són només per a depuració i no afecten el flux normal.

---

## 3. Arquitectura de Memòria de 128 KB

```
+---------------------------------------------------------------------------------+
| BLOC 0 (Resident 0x0000..0x3FFF, sempre mapejat a RAM 0)                         |
|  - 0x0100..0x3826: _CODE del resident (motor genèric, vídeo, ISR, blit)          |
|  - 0x3880..0x3CDE: _DATA resident (globals, s_lv, càmera, estat del jugador)     |
|  - Pila Z80 (SP=0x3FFE)                                                          |
+---------------------------------------------------------------------------------+
| FINESTRA BANCADA (0x4000..0x7FFF) commutada via 0x7F00                          |
|                                                                                 |
|  Banc C1 (0x4000..0x7FFF): Àudio compartit + imatge variable del nivell         |
|    - 0x4000..0x4C00: Player àudio AKG (MAI escriure-hi dades)                    |
|    - 0x4C10..0x4FA5: HUD blitter ASM (src/hud_bank.c)                            |
|    - 0x4FA8..0x4FE1: _DATA de HUD (src/hud_bank.c)                               |
|    - 0x5000..: cançó + HUD + GAMEOVER + portes + restore (layout variable)       |
|    - 0x7680..0x76CC: LevelParams v3 (77 B)                                       |
|    - 0x7700: _DATA del codi d'excepcions (si n'hi ha)                            |
|    - 0x7800..0x7BFF: còpia mestra de FDC.BIN (C0:0x7800) — PROHIBIT trepitjar    |
|    - 0x7C00..0x7F2D: LVLCHS copiada per load_level_file                          |
|                                                                                 |
|  Banc C4 (0x4000..0x7FFF): Tileset compactat del nivell                          |
|  Banc C5 (0x4000..0x7FFF): Món del nivell                                        |
|    - 0x4000: mapa · rooms_off: sales · trig_off: TRIG compacte (5 B/entrada)     |
|    - 0x6E00: codi del món (moving_bank.c) + _DATA enganxada                      |
|  Banc C6 (0x4000..0x7FFF): Enemics                                           |
|    - 0x4000: taula de celes + blocs ZX0                                          |
|    - 0x4B00: taula de restauració de tiles del nivell                            |
|    - 0x5000..0x57FF: cache de 4 celes (scratch)                                   |
|    - 0x5800..0x581F: estat de la cache                                           |
|    - 0x5820..0x5BFF: _DATA d'enemics                                             |
|    - 0x5C00..<0x7900: codi d'enemics (enemy.c)                                   |
|    - 0x7900..0x79FF: LUT de flip                                                |
|    - 0x7A00..0x7FFF: pool de fons (6 x 256 B)                                    |
|  Banc C7 (0x4000..0x7FFF): Frames del jugador (Jake/Elwood)                      |
+---------------------------------------------------------------------------------+
| VRAM (0x8000..0xFFFF, doble buffer de pàgines 0 i 1 a Mode 0)                    |
+---------------------------------------------------------------------------------+
```

### 3.1 Layout C1 variable per nivell

El build calcula els offsets i els desa a `obj/C1LAY<n>.BIN` y a `LevelParams`.

| Nivell | Cançó | HUD | GAMEOVER | Portes | Restore | Codi exc. | Frames | BG | Params | Mida PAK |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 0x5000 (1.619) | 0x5658 | 0x5A00 | 0x5F50 | 0x5FB0 | 0x5FE8 (1.135 B) | 0x6900 | 0x6D00 | 0x7680 | 13.427 B |
| L2 | 0x5000 (2.721) | 0x5AA8 | 0x5E50 | 0x63A0 | 0x63A0 | 0x63A8 (1.135 B) | 0x6900 (PRESS 792 B) | 0x6D00 | 0x7680 | 13.357 B |
| L3 | 0x5000 (4.670) | 0x6240 | 0x65E8 | 0x6B38 | 0x6B98 | **cap** (`code_exc_off=0`) | — | — | 0x7680 | 14.051 B |

- L3 **no porta codi d'excepcions**: no té ascensors ni premses encara. Això és el que fa que
  `L3WORLD.PAK` càpiga en 28 sectors (14.051 B; **157 B de marge** sobre el límit de 14.208 B).
- Si mai s'hi afegeix codi de mecanismes a L3, caldrà comprimir més o fer split de C1.

### 3.2 Pressupost C5 (mapa + sales + TRIG5 + codi del món)

| Nivell | Mapa | Sales | TRIG5 | Codi | Total | Lliures |
|---|---|---|---|---|---|---|
| L1 | 9.216 | 1.000 | 1.195 | 4.580 | 15.991 | **393** |
| L2 | 9.216 | 0 | 1.025 | 4.516 | 14.757 | 1.627 |
| L3 | 9.216 | 1.200 | 1.065 | 3.196 | 14.677 | 1.707 |

### 3.3 C6 (enemics)

- `ENEMY_N = 20` (no 22: el codi de C6 acaba a `0x7833` i la LUT viu a `0x7900`).
- L3 omple **18 slots**: 11 policies (`type 3` → `kind 4`, op2) i 7 gossos (`type 6` → `kind 18`, op1).
- Queden fora, documentats com a pendents:
  - `type 4` → **op3** (llançador): cal comportament 1:1 i espai a C6.
  - `type 5` → **op4** (4 movers) i `type 23` → **op11** (2 movers): no són walkers de C6.

---

## 4. Estat dels Nivells

### Nivell 1 (`magasin`) — **COMPLETAT I ESTABLE**
- 5 ascensors verticals amb restauració de fons intacta.
- Cintes transportadores amb animació i empenyiment de velocitat correcta.
- Enemics terrestres (policia, iaies, rockers, grangers, cambrera), peixos a les peixeres i ocells als núvols.
- Caixes agafables i llançables, paraigües, globus, recollida de vinils i pas per habitacions interiors.

### Nivell 2 (`ent` / fàbrica i magatzem) — **AVANÇAT**
- **Operatiu**:
  - Mapa i tileset empaquetats a `L2WORLD.PAK` i `L2ENEMI.ZX0`.
  - Àcid, cintes transportadores de fàbrica, trituradores i animacions de panells.
  - **Premses hidràuliques** sincronitzades amb `PRESS.BIN` (24×33 px) i buffers de fons.
  - **Inèrcia de gel**: `g_on_ice` resident accelera el jugador sobre `op 30` i rampes 32..35.
  - Enemics L2 per tipus 11/12/13/14/21.
- **Pendent**:
  1. Dipòsit d'aigua del sostre / desguàs: en Jake no hi passa bé (col·lisió massa estreta / postura).
  2. Trampolins elàstics: validar i connectar el salt (no hi ha implementació tancada al codi actual).
  3. Fidelitat fina d'animacions i tipus 22 com a objecte mòbil independent.

### Nivell 3 (`prison`) — **INTEGRAT I CARREGANT**
- Afegit a `LEVELS` i `DATA_FILES`: `L3WORLD.PAK` (14.051 B) i `L3ENEMI.ZX0` (6.676 B).
- `pack_level.py 2 --outdir obj/lvl2` regenera tileset/mapa/sales/TRIG/restore/params.
- Xarxa de C1 variable: Theme2 (4.670 B), HUD, GAMEOVER, 24 portes i restore de 6 sales.
- **Verificat en emulador** (drecera `3`): `magic=0xB0`, `level_id=2`, `g_map_level=2`,
  Jake apareix ja centrat al punt d'inici (`px8=1600`, `py8=1296`), moviment OK i 18 enemics visibles.
- **Entrada 1:1 DOS** (`init_level`): per als nivells 2-6 la càmera inicial es calcula centrada al jugador
  (`start_px = xpos/2 - 8`, `cam0` segons la fórmula DOS), no a `(0, max_cam_row)`. Això elimina el
  desplaçament inicial que es veia en arrencar L3.
- **Forat d'1 tile (row 23, cols 8-21)**: el jugador hi passa **ajupit**. La col·lisió horitzontal
  ara només mira la fila del cap abaixat quan `crouch` (1:1 DOS `unk2E==0` → alçada 14).
- **Reixes `type 6` (cols 35-44, rows 18-23)**: són escalables com al DOS (`do_level_fixup_object_unkA`),
  sense l'imant horitzontal del `type 7`; per tant s'hi pot pujar/baixar i entrar/sortir pels costats.
- **Pendent**:
  1. `type 4`/op3 (4 llançadors) i movers `type 5`/op4 + `type 23`/op11.
  2. Validació de portes/sales/àcid i recorregut complet del nivell.
  3. `ENEMY_N=20`: si s'hi afegeixen els 4 llançadors caldrà 22 slots o reduir el codi de C6.

---

## 5. Rendiment i Optimització del Framerate (Octubre 2026)

- **Estat del motor**: Sòlid a **25 Hz** (40 ms / 2 VSYNCs) tant en repòs com en **scroll horitzontal**.
- **Fase 1 (Completada - commit `127e306`)**:
  - `_hud_blit_col` i el bucle de redibuix del HUD s'han mogut del resident al Banc C1 (`src/hud_bank.c`) i reescrits en ASM directe (Mode 0, càlcul incremental de VRAM amb màscara wrap 2 KB).
  - Ha recuperat **388 línies de raster d'espera VSYNC** durant el scroll horitzontal.
  - Actualment `_CODE` acaba a `0x3826` (14.118 B), amb **90 B** de marge.
- **Fases 2 i 3 (Pausades / Documentades)**:
  - *Fase 2 (Render ràpid de tiles)*: reordenació del tileset a la càrrega del nivell + blit via `POP`.
  - *Fase 3 (Còpia front->back en caiguda / Split CRTC)*: descartada a curt termini per complexitat de sprites superposats i sincronització de raster.
- **Sincronització d'habitacions**:
  - Les habitacions interiors corren a **25 Hz exactes** (2 VSYNCs obligatoris a `src/main.c`).

---

## 6. Taula de Paràmetres del Nivell (`LevelParams` v3, 77 bytes)

Ubicada a `C1:0x7680` al paquet i copiada a `s_lv` a RAM resident:
- Offset 5: `room_row0` · Offset 4: `room_rows` · Offset 2: `room_count`
- Offset 34: `start_px` (i16) · Offset 36: `start_py` (i16)
- Offset 38: `cam0_x4` (i16) · Offset 40: `cam0_row` (i16)
- Offset 42: `chk_px` (i16) · Offset 44: `chk_py` (i16)
- Offset 52: `map_w` (u8) · Offset 53: `map_h` (u8) · Offset 54: `map_rows` (u8)
- Offset 55: `door_count` · Offset 56: `rooms_off` (u16)
- Offset 58: `doors_off` · Offset 60: `restore_off`
- Offset 69: `trig_off` (u16)
- Offset 71: `code_exc_off` (u16) — **0 si el nivell no té codi d'excepcions (L3)**
- Offset 73: `hud_off` (u16) · Offset 75: `gameover_off` (u16)

> **Atenció**: SDCC empaqueta l'struct sense alineació. No inserir camps al mig sense actualitzar
> `tools/pack_level.py`, `tools/build.py` i `src/level_params.h` alhora.

---

## 7. Peculiaritats conegudes (no repetir errors)

- **MUSBANK.BIN** (`C1:0x4000`): el player AKG comença a `0x4009`; **mai** escriure-hi taules.
  `LVLCHS` (814 B) viu a l'offset `0x1D00` (`C1:0x5D00`) i es copia a `C1:0x7C00..0x7F2D`
  en carregar el primer nivell. Pool: WORLD 56 B (28 sectors), ENEMI 32 B, C1 32 B per nivell.
- **Límit del paquet**: 28 sectors AMSDOS = 14.336 B en disc (14.208 B de payload).
  El FDC els llegeix sencers a l'scratch `0x8320..0xBBFF` (14.560 B); un paquet de 30
  sectors (15.360 B) desborda l'scratch i corromp la imatge. Els asserts del build ho bloquegen.
- **FDC mestre** a `C0:0x7800` (785 B). Cap imatge de C1 pot arribar-hi: el build ho asserta.
- **`0xC0`/`0xC1` comparteixen RAM** a `0x4000..0x7FFF`; només canvia què es veu a `0xC000..0xFFFF`.
- **Codi bancat**:
  - No pot commutar de banc (perdria el seu propi codi).
  - No rep paràmetres C: usar `bc_a`..`bc_r`.
  - Si escriu a VRAM, ha de viure a la RAM 1 i cridar-se amb `0xC0`.
- **sdasz80**: sense BOM; no `ld a,(hl+1)`; no `ld hl,de`; push/pop equilibrats.
- **ZRCP**: `read-memory` i `disassemble` requereixen adreces **decimals** (`%d`), no hex.
- **Build**: no restaurar versions velles de `build.py` (es va perdre l'empaquetat de frames/GAMEOVER).
- **Els docs antics poden estar desfasats**. Font de veritat: `tools/build.py`, `obj/C1LAY<n>.BIN`,
  `obj/bluesb.map` i els headers generats (`src/disk_tables.h`, `src/crt_addrs.h`, `src/starter_tables.h`).
  En particular, `HANDOFF` antic parlava de params a `0x6900` i frames a `0x6E00`: **ja no és així**.

---

## 8. Llista de Documents de Suport

- [`docs/DOS_CPC_COORDINATES.md`](file:///C:/Projects/bluesb_cpc/docs/DOS_CPC_COORDINATES.md): fórmules de conversió 1:1.
- [`docs/PLA_NIVELLS_UNIVERSAL.md`](file:///C:/Projects/bluesb_cpc/docs/PLA_NIVELLS_UNIVERSAL.md): pla d'extensió universal als 6 nivells.
- [`docs/LEVEL_PACKAGE.md`](file:///C:/Projects/bluesb_cpc/docs/LEVEL_PACKAGE.md): especificació del format de fitxers `.PAK` i `.ZX0`.
- [`docs/FIX_PREMSES_NIVELL2.md`](file:///C:/Projects/bluesb_cpc/docs/FIX_PREMSES_NIVELL2.md): anàlisi del bug de memòria de les premses.
- [`docs/INVENTARI_NIVELLS.md`](file:///C:/Projects/bluesb_cpc/docs/INVENTARI_NIVELLS.md): mides i contingut dels 6 nivells.
- [`docs/ESTAT_L3_C1_C3.md`](file:///C:/Projects/bluesb_cpc/docs/ESTAT_L3_C1_C3.md): registre històric del WIP de C1/L3 (pot contenir adreces antigues).
- [`tools/blues_dos/`](file:///C:/Projects/bluesb_cpc/tools/blues_dos/): descompilació DOS de referència absoluta.

---

## 9. Properes passes recomanades

1. **Commit** de la integració L3 (build, tools, spawns/frames i HANDOFF) un cop validada.
2. Validar L3 en joc: portes, 6 sales, àcid, mort/respawn i sortida de nivell.
3. Implementar `type 4`/op3 (llançador) amb fidelitat DOS i mirar si cal `ENEMY_N=22`.
4. Implementar movers `type 5`/op4 i `type 23`/op11 (L3) al subsistema de movers.
5. Reprendre els pendents de L2: desguàs del dipòsit d'aigua i trampolins.
