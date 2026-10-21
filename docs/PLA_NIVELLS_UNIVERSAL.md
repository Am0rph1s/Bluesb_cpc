# Pla: sistema universal de nivells (6 nivells, zero pedaços)

> Document viu. Cada fase té **checkpoints** (`[ ]` pendent, `[x]` fet).
> Qui continuï ha de: 1) llegir §1-§4, 2) anar al primer checkpoint sense marcar,
> 3) fer-lo, verificar-lo, marcar-lo i fer commit.
> Idioma de treball: **català**. Regles del projecte: `AGENTS.md`.
> Estat general: `ESTAT.md`. Diagnòstic del boot: `docs/BOOT_FAILURE_2026-10.md`.
> Dades dels 6 nivells: `docs/INVENTARI_NIVELLS.md` (generat per
> `tools/inventory_levels.py`).

---

## 0. Decisions de l'usuari

- **S1 (2026-10-20).** **Fidelitat 1:1 amb el DOS** és la prioritat. Si la memòria
  no hi dona, s'adapta el sistema (bancs, compressió, discos), no el contingut.
- **S2 (2026-10-20).** **Dos discos permesos:** si els 6 nivells no caben en un DSK
  de 180 KB, els nivells que calgui poden anar a un **segon disc**. Cal dissenyar
  el canvi de disc (missatge, ids de disc al manifest).
- **S3.** Cap canvi de layout de memòria ni build llarg sense **aprovació
  explícita** de l'usuari (`AGENTS.md`).
- **S4 (2026-10-20).** **Fase 0 aprovada:** es pot executar sense més confirmació.
- **S5 (2026-10-20, alineació).** El sistema universal vol dir:
  - **Bloc 0 = només motor.** Cap constant, adreça, mida ni codi d'un nivell
    concret hi pot viure.
  - **Tot el que és exclusiu d'un nivell viu al paquet del nivell.**
  - **Un sol layout de bancs** per als 6 nivells, dimensionat pel pitjor cas.
  - **Una sola eina de build** genera els 6 paquets; **mai** `if level == 0`.
- **S6 (2026-10-20, correcció).** El "pitjor nivell" és el **5 (ville)** pel
  **mapa**, no per la música: hi ha **4 cançons en total** i **cada nivell només
  en fa sonar una** (`level.c:90-93`; `_levels[].music` = 1,2,3,1,2,3).

---

## 1. Fets comprovats (no suposicions)

### 1.1 Les habitacions són files del MATEIX tilemap (DOS)

- `tools/blues_dos/bb/level.c:1135`:
  `static const uint8_t pos[] = { 74, 74, 77, 66, 102 };` → fila on comencen les
  habitacions de cada nivell (0..4; el nivell 6 no en té).
- `level.c:1141-1143`: `if (obj->ypos > g_vars.screen_tilemap_h)` (més enllà de
  l'alçada visible = ets a una habitació) → la càmera salta a `pos[nivell]`.
- `resource.c:381`: `return g_res.sql + y * 128 + x;` → el tilemap és **un sol
  array pla de 128 columnes**.
- `resource.c:21`: `static const int SQL_SIZE = 640 * 25;` = **16.000 B**
  reservats (cobreix totes les habitacions de tots els nivells).
- La geometria de cada sala és **20 × 10 tiles** i l'origen X és el bloc de 20
  columnes (`level.c:1144-1145`), que coincideix amb el `room_idx * 20` que fa
  servir el port CPC (`src/render.c:159`).

**Conseqüència:** la mida del mapa **no** és `ample × alçada_visible`, sinó
`128 × max(alçada_visible, pos + 10)`.

### 1.2 Mides REALS del mapa

Mesurat amb `tools/inventory_levels.py` (sales comptades pels blocs de 20
columnes que fan servir les portes amb `dst_y`/`src_y` fora de l'alçada):

| Nivell | Nom | Ample | Alt visible | `pos` sala | Sales | **Mapa** | **Mapa+sales (compacte)** | **+TRIG** | DOS (files de 128) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | magasin | 128 | 72 | 74 | 5 | 9.216 | **10.216** | 12.776 | 10.752 |
| 2 | ent | 128 | 72 | — | 0 | 9.216 | **9.216** | 11.776 | 9.216 |
| 3 | prison | 128 | 72 | 77 | 6 | 9.216 | **10.416** | 12.976 | 11.136 |
| 4 | egou | 128 | 61 | 66 | 3 | 7.808 | **8.408** | 10.968 | 9.728 |
| 5 | ville | 128 | 95 | 102 | 1 | **12.160** | **12.360** | **14.920 ✓** | 14.336 |
| 6 | concert | 128 | 49 | — | 0 | 6.272 | **6.272** | 8.832 | 6.272 |

- `TRIG` = 2.560 B (256 entrades × 10 B, `X.BIN`). Un banc CPC = **16.384 B**.
- **"Compacte"** = 200 B per sala (20×10), que és exactament el que cada nivell
  fa servir. La columna **DOS (128)** és com ho guarda el DOS: files de 128
  columnes + el forat entre l'alçada i `pos` (a ville: 7 files buides). És
  **farciment**, no contingut.
- **El mapa gros (ville) no és cap problema:** 12.160 B de mapa real caben a C5
  amb 4.224 B de sobres. El que no hi cabia era el farciment del DOS (14.336).

> Aquesta taula substitueix la de la versió anterior del pla, que feia servir
> l'alçada visible i després la mida DOS de 128 columnes.

### 1.3 Capacitat de C5 (mapa + sales + TRIG + codi del món)

Codi actual del món (`src/moving_bank.c` → `BANK5.BIN`) = **4.548 B**.

| Nivell | mapa+sales | + TRIG | + codi | Total | Veredicte |
|---|---|---|---|---|---|
| 1 magasin | 10.216 | 12.776 | 17.324 | **✗ −940** |
| 2 ent | 9.216 | 11.776 | 16.324 | **✓ +60** |
| 3 prison | 10.416 | 12.976 | 17.524 | **✗ −1.140** |
| 4 egou | 8.408 | 10.968 | 15.516 | **✓ +868** |
| 5 ville | 12.360 | 14.920 | 19.468 | **✗ −3.084** |
| 6 concert | 6.272 | 8.832 | 13.380 | **✓ +3.004** |

**Fets que se'n deriven:**
1. **Sense el codi, els 6 nivells hi caben** (pitjor: ville 14.920 → 1.464 B
   lliures). El contingut no s'ha de retallar.
2. **Amb el codi del món dins C5, només 3 de 6 hi caben.**
3. ⇒ El codi del món **no pot viure a C5**; va a la RAM 1 (§4.3).

### 1.3b El límit real és GLOBAL: només hi ha 5 bancs de 16 KB

Bancs utilitzables de manera segura al 6128 en aquest projecte (vegeu
`ESTAT.md`, sessió 36 i l'addendum CP-2.2): **RAM 1** (selectors `0xC0`/`0xC1`),
**C4**, **C5**, **C6**, **C7** → **5 × 16.384 = 81.920 B**.
(`C2`/`C3` no són segurs: `OUT(0x7F00,0xC2)` penja la màquina i `C3` reinicia.)

| Banc | Contingut | Pitjor cas conegut |
|---|---|---|
| C4 | tileset del nivell | 16.384 **per construcció** (256 tiles × 64 B) |
| C5 | mapa + sales compactes + TRIG | 14.920 (ville) ✓ 1.464 lliures |
| C6 | enemics (frames + codi) | 15.012 (nivell 1) |
| C7 | frames del jugador | 15.872 |
| RAM 1 | player AKG + música + HUD + portes + params + GAMEOVER + codi d'excepcions + gràfics d'ascensor + codi del món | 15.881 B amb la cançó actual ✓ 503 lliures (§4.3) |

**Conclusió:** el repartiment és viable, però **RAM 1 va molt justa** i depèn de
la mida de les cançons 1-3 (§1.7).



### 1.4 El comportament és per TIPUS, no per nivell

- `tools/blues_dos/bb/objects.c:448-450`: `level_call_object_func()` fa
  `switch (obj->op - 1)` → el comportament depèn **només de l'op** de l'objecte.
- `staticres.c:168-172`: `level_objtypes[]` dona, **per nivell**, l'`op` de
  cadascun dels 41 objectes.
- `staticres.c:173+`: `level_data[]` dona el paràmetre de cada objecte.
- `staticres.c:3-61`: `level_xpos_*` / `level_ypos_*` per nivell (41 valors).

**Conseqüència:** **no cal codi propi de nivell** per als 6 nivells. N'hi ha prou
amb dades. La "taula de salts de nivell" queda reservada a **excepcions
documentades** (si mai n'hi ha cap).

### 1.5 Què té avui el resident que és de nivell (violacions de S5)

| Fitxer:línia | Què és |
|---|---|
| `src/moving.c:50-51` | `LC1_DRAW/LC1_RESTORE = 0x6934/0x6937` (adreces de nivell) |
| `src/moving.h:30-31` | `ELEVATOR_BG_BASE 0x7200` + `elevator_bg_ptr()` |
| `src/moving.h:6` | `MAG_ELEVATOR_COUNT 5` (constant de nivell; `s_lv.elev_count` ja existeix) |
| `src/main.c:715` | `GAMEOVER_PTR ((const u8*)0x5800)` |
| `src/main.c:782` | `zx0_decompress(..., (void*)0x5800)` |
| `src/main.c:844-849` | taula de restauració de les habitacions a `0x6860` |
| `src/main.c:751` | `g_file_l1world` (nivell 1 clavat al resident) |
| `src/main.c:149`, `183` | `if (row >= 74)`, `s_row100[]` (habitacions fora del mapa) |
| `src/main.c:311-318` | `check_room_bonus()` (lògica duplicada de les sales) |
| `src/render.c:157-167` | `render_room()` + `((const u8*)0x6400)` + `74 + r` |
| `src/moving_bank.c` (sencer) | codi del món compilat una sola vegada, dins C5 |

Això és la **llista de treball** de la Fase 3.

### 1.6 Marge real del Bloc 0

- Amb el codi dels ascensors **dins** el resident: `_CODE` acabava a `0x386E`
  → 14.190 B i quedaven **48 B** fins a `_DATA` (`0x3900` en aquell moment).
- Amb el codi **fora** (sessió 36): marge **836 B** (`_CODE` 13.372 B).
- **Després del carregador genèric (Fase 2.1):** `_CODE` **13.742 B** →
  **marge 466 B**. El carregador genèric ha costat **+370 B** respecte dels 4
  blocs de descompressió desenrotllats.
- ⇒ El pressupost per a la Fase 3 (treure hardcodes, accessor de tiles) és de
  **466 B**, i la Fase 3 ha de **recuperar** espai eliminant `s_row100[]`,
  `render_room()` i `check_room_bonus()`.


### 1.7 Mides mesurades i el que encara falta

**Mesurat (2026-10-20)** amb el conversor del build (`akg_convert` + `link_bin`
a `MUS_SONG_SLOT = 0x5000`):

| Cançó | Fitxer font | Compilada | Fi (des de 0x5000) | Nivells |
|---|---|---|---|---|
| intro | `..._Intro_CPC.akg` | 3.091 B | 0x5C13 | (títol) |
| main | `The_Blues_Brothers_CPC.akg` | 1.619 B | 0x5653 | 1, 4 |
| Theme1 | `..._Theme1_CPC.akg` | 2.721 B | 0x5AA1 | 2, 5 |
| **Theme2** | `..._Theme2_CPC.akg` | **4.670 B** | **0x623E** | 3, 6 |

**Conseqüència dura:** amb Theme2 la cançó arriba a `0x623E`, **per sobre del HUD
actual (`0x6000`)** → el HUD no pot viure a `0x6000` en el sistema universal.

**També mesurat (2026-10-20):**

- **TRIG (nivell 1):** `TRIG0.BIN` = 2.560 B, **les 256 entrades tenen dades**,
  tile màxim usat = **251** (196 tiles diferents). ⇒ Truncar a `max_tile+1`
  només estalvia **40 B** → **no val la pena compactar**. (Un remapatge de tiles
  al build —reordenar tileset + mapa + TRIG— estalviaria ~600 B, però no cal.)
- **Tilesets (C4):** `TILESET0.BIN` = **16.384 B = 256 tiles × 64 B** → C4 és
  **sempre un banc sencer**, per construcció; no hi ha risc de desbordament.

**Encara pendent:**
1. **Mida real dels PAK dels nivells 2-6.** Només es pot saber convertint-los.
   Límit dur ja conegut: l'scratch `0x8320-0xBBFF` = **14.560 B**; `L1WORLD` ja
   en fa 13.483 → **cal un assert i, probablement, càrrega en 2 passades**.
2. **Nombre d'objectes `op` 4 (ascensors) per nivell.** L'inventari diu
   5,0,0,0,0,0 → 5 és el màxim; si un altre nivell en tingués més, caldria
   revisar `MAG_ELEVATOR_COUNT`.
3. **Nombre de sales i portes dels nivells 2-6** (l'inventari ja el dona:
   sales 0/6/3/1/0) i la seva col·locació exacta (`pos` per nivell).



---

## 2. Per què ara són pedaços

- **C5 barreja** dades de nivell (mapa, TRIG) i codi del motor (`moving_bank`):
  amb les mides reals, el nivell 5 no hi cap ni sense codi.
- **Adreces fixes a mà** (`0x6400`, `0x6934`, `0x5800`, `0x7200`...): ja hem
  patit **3 solapaments** (GAMEOVER vs ascensors, GAMEOVER vs còpia FDC a
  `0xC0:0x7800`, i `0xC1` que amaga la VRAM pàgina 0).
- **Constants del nivell 1 al resident** (`build.py`/`main.c`/`moving.*`).
- **Habitacions fora del mapa** amb `if (row >= 74)` i funcions duplicades
  (`render_room`, `check_room_bonus`), quan al DOS són **files del mateix mapa**.

---

## 3. Principis (no negociables)

1. **Bloc 0 = només motor.** Cap constant, adreça ni codi d'un nivell concret.
2. **Codi del motor ≠ dades de nivell:** viuen en bancs diferents.
3. Cada nivell és un **paquet autodescrit** (manifest `(banc, adreça, mida)`);
   el carregador és un **bucle genèric**.
4. **Mateixa *estructura* de bancs** per als 6 nivells; les **mides i offsets**
   de cada bloc surten del manifest i el build els valida amb asserts de
   no-solapament i de marge (≥ 256 B). (Revisat 2026-10-20: les cançons fan
   1.619-4.670 B i els ascensors només existeixen al nivell 1, així que un
   layout fix no hi cap; vegeu §4.3.)
5. El build itera una **taula de nivells**; mai `if level == 0`.
6. **Habitacions = files del mateix mapa** (com al DOS). Preu ja conegut:
   el mapa del nivell 1 passa de 9.216 a 10.752 B (+1.536) i les sales surten
   de la RAM 1 (−1.000 B).
7. **Regla de maquinari:** per cridar codi bancat que escriu a VRAM s'usa
   `0xC0`, **no** `0xC1`. Al 6128, `0xC0` i `0xC1` mostren **la mateixa RAM** a
   `0x4000-0x7FFF`; només canvien què apareix a `0xC000-0xFFFF`:
   `0xC0` → VRAM pàgina 0; `0xC1` → RAM 7 (amaga la VRAM). Vegeu `ESTAT.md`
   (sessió 36).
8. Tota adreça nova s'afegeix a **una sola taula d'adreces** (`src/mem_map.h`,
   generada o verificada pel build) amb **assert de no-solapament**.
9. **Un codi bancat no pot commutar de banc** (perdria el seu propi codi). Per
   tant: o les dades que toca viuen al seu banc, o hi accedeix mitjançant
   **accessors residents**.

---

## 4. Layout universal: pressupost i restriccions dures

> Aquesta secció és el **marc** de la Fase 1. Les adreces finals es fixen allà,
> amb les mides mesurades i els asserts del punt 1.7.

### 4.1 Bloc 0 (resident)

- `_CODE` `0x0100..` (avui 14.190 B amb el codi d'ascensors; ~13.230 B sense).
- `_DATA` `0x3900` (1.021 B, inclou `s_lv`), canari de pila `0x3D00`.
- **Pressupost per al motor genèric: ~962 B** (§1.6). No s'hi pot afegir res
  sense treure'n una altra cosa.

### 4.2 Repartiment dels 5 bancs

Vegeu la taula de §1.3b. Resum de la proposta:
`C4` tileset · `C5` mapa (sales compactes) + TRIG · `C6` enemics ·
`C7` frames del jugador · `RAM 1` player AKG + cançó + HUD + portes + params +
GAMEOVER + codi del món + codi d'excepcions + gràfics d'ascensor
(+ còpia FDC si hi cap).

### 4.3 RAM 1: pressupost REAL (cançons mesurades)

| Bloc | Mida | Nivells on cal |
|---|---|---|
| Player AKG | 4.096 | tots (`0x4000`, slot fix) |
| Cançó del nivell | **1.619 / 2.721 / 4.670** | tots (segons el nivell) |
| HUD | 1.024 | tots (**no pot ser a `0x6000`**: Theme2 arriba a `0x623E`) |
| Portes | 96 | tots |
| Codi del món (`moving_bank`) | 4.548 | tots |
| GAMEOVER | 1.360 | tots |
| Codi d'excepcions (ascensors) | 957 | només nivells amb ascensors |
| Frame d'ascensor | 224 | només nivells amb ascensors |
| Buffers de fons d'ascensor | 1.120 | només nivells amb ascensors |
| Còpia mestra FDC | 785 | tots |

**Paràmetres (52 B) NO compten:** `level_params_load()` els copia a `s_lv` del
resident.

**Sumes reals** (base comuna = player 4.096 + HUD 1.024 + portes 96 +
codi del món 4.548 + GAMEOVER 1.360 = **11.124 B**; ascensors = 957+224+1.120):

| Cas | Suma | Veredicte |
|---|---|---|
| Nivell 1/4 (main 1.619 + ascensors) | 15.044 | **✓ 1.340 lliures** |
| Nivell 2/5 (Theme1 2.721, sense ascensors) | 13.845 | **✓ 2.539 lliures** |
| **Nivell 3/6 (Theme2 4.670, sense ascensors)** | **15.794** | **✓ 590 lliures** |
| Nivell 3/6 + còpia FDC | 16.579 | ✗ −195 |
| Tots els blocs alhora (teòric: Theme2 + ascensors + FDC) | 18.880 | ✗ −2.496 |

**Conclusió (decisió D2):** el layout **ha de ser per nivell**, amb els offsets al
manifest (principi 3), no un únic layout fix:

- Blocs comuns: player AKG, cançó (mida variable!), HUD, portes, codi del món,
  GAMEOVER.
- Blocs opcionals: codi d'excepcions + frame + buffers d'ascensor (només si
  `elev_count > 0`).
- **La còpia mestra FDC surt de la RAM 1** (el loader és resident i pot
  commutar) → a un forat lliure de C5 o C6.
- El pitjor cas realista (nivell 3/6) queda amb **590 B de marge** ✓. Per tenir
  coixí, comprimir el GAMEOVER al paquet (1.360 → 619 B, descomprimit a VRAM
  quan calgui) dona **+741 B**.
- El HUD s'ha de col·locar **després de la cançó** (offset variable), no a
  `0x6000`; la referència `_s_hud_strips` ja és un EQU generat pel build.
- **GAMEOVER** tampoc no pot ser a `0x5800` fix: va després del HUD.
- L'assert del build ha d'exigir **≥ 256 B de marge** a cada banc i nivell.



### 4.4 Sales i TRIG: al paquet del nivell, dins C5

**Decisió (D1, aprovada 2026-10-20):** les sales **no** s'integren al mapa
principal. Es guarden **compactes** (200 B per sala) **al paquet del nivell**,
dins **C5**, just després del mapa:

```
C5:  [ mapa ]  [ sales (200 B x room_count) ]  [ TRIG 2.560 ]
     0x4000     0x4000 + map_bytes                ...        (<= 16.384)
```

Mides per nivell (mesurades):

| Nivell | mapa | sales | TRIG | **Total C5** | Lliures |
|---|---|---|---|---|---|
| 1 magasin | 9.216 | 5 × 200 = 1.000 | 2.560 | **12.776** | 3.608 |
| 2 ent | 9.216 | 0 | 2.560 | **11.776** | 4.608 |
| 3 prison | 9.216 | 6 × 200 = 1.200 | 2.560 | **12.976** | 3.408 |
| 4 egou | 7.808 | 3 × 200 = 600 | 2.560 | **10.968** | 5.416 |
| 5 ville | 12.160 | 1 × 200 = 200 | 2.560 | **14.920** | **1.464** |
| 6 concert | 6.272 | 0 | 2.560 | **8.832** | 7.552 |

**Res hardcoded al resident:** el paquet porta les dades i els paràmetres
(`room_count`, `room_row0`, `room_cols = 20`, i els offsets de cada bloc dins
C5). L'accés passa per **un sol accessor**:

```
get_tile(col, row):
    si row < alt_visible        -> mapa[row * ample + col]
    si row >= room_row0         -> sales[sala * 200 + (row - room_row0)*20 + col % 20]
                                   amb sala = col / 20
    (les files entre alt_visible i room_row0 no existeixen)
```

Això substitueix `render_room()`, `check_room_bonus()`, `s_row100[]` i tots els
`if (row >= 74)` de `main.c`/`render.c` (§1.5).

**Efecte secundari imprescindible:** les sales surten de la RAM 1 i alliberen el
bloc de `0x6400` (1.024 B). Sense això, el codi del món no hi cap (§4.3).



### 4.5 C4, C6, C7

- **C4** = tileset del nivell (nivell 1: **16.384**, ple). **Cal mesurar els
  tilesets dels 5 altres**: si algun supera 16.384, caldrà compressió o retall.
- **C6** = enemics del nivell (nivell 1: 8.192 frames + 6.820 codi = **15.012**).
- **C7** = frames del jugador (**15.872**, gairebé ple).


---

## Fase 0 — Inventari (només lectura)

- [x] **0.1** `tools/inventory_levels.py` (mides, objectes per tipus, ascensors,
      portes, sales, música).
- [x] **0.2** Mides dels recursos DOS al disc.
- [x] **0.3** Tiles únics per nivell: pendent com a tal, però l'inventari ja dona
      `CK1`/`CK2` per nivell (caldrà l'extractor a Fase 4).
- [x] **0.4** `docs/INVENTARI_NIVELLS.md` generat.
- [x] **0.5** Pressupost de disc: **els nivells 2-6 sumen ≈ 90 KB i queden ≈ 91 KB
      lliures** → **caben en un disc, amb 2-3 KB de marge** (comptes sense
      capçaleres ni codi nou). Guany fàcil: **GAMEOVER compartit** (ara va dins
      del bloc de cada nivell) ≈ +2,5 KB. **Decisió:** disc únic si l'assert hi
      cap; **disc 2 = pla B** (S2).
- **CHECKPOINT F0:** inventari publicat + commit. ✅ (pendent d'incorporar la
  correcció de mides d'aquest document)

---

## Fase 0.6 — Smoke test (BLOQUEJANT, abans de tocar res més)

Objectiu: que cap regressió torni a passar desapercebuda hores.

- [x] **0.6.1** `tools/smoke_test.py`: arrenca ZEsarUX, **espera el prompt de
      BASIC** (`get-ocr`, no un `sleep` fix), fa `RUN "BLUESB"`, espera
      `s_lv.magic == 0xB0` i `s_px8`/`s_py8` ≠ 0, fa captura i retorna codi ≠ 0
      si falla.
- [x] **0.6.2** Verificador del DSK: catàleg + CRC de cada fitxer llegit amb la
      seva taula CHS i la mida declarada (atenció: l'últim sector porta
      farciment `0xE5`; cal truncar amb `ondisk_bytes`).
- [x] **0.6.3** `tools/build.py --check` (DSK, ~2 s) i `--check-boot`
      (+ arrencada real). El build **falla** si no passa.
- [x] **CHECKPOINT F0.6:** smoke test verd amb el joc actual.
      **Fet 2026-10-20**: DSK OK (6 fitxers, CRCs correctes) i arrencada OK
      (`magic=0xB0`, `px8=256`, `py8=8848`, `bank=0xC0`).

---

## Fase 1 — Especificació (només document)

- [x] **1.1** `docs/LEVEL_PACKAGE.md` redactat (**esborrany**, pendent
      d'aprovació): manifest (capçalera 16 B + descriptors de 8 B), seccions per
      paquet, layout per nivell calculat pel build, `LevelParams` v2, carregador
      genèric i asserts.
- [ ] **1.2** **Decisió (revisada 2026-10-20 amb les cançons mesurades):**
      - `C5 = mapa + sales compactes + TRIG` (ville: 14.920 ✓).
      - `codi del món (4.548 B)` a la **RAM 1**, amb **layout per nivell**
        (offsets al manifest): blocs comuns + ascensors només si n'hi ha.
      - pitjor cas realista (nivell 3/6, Theme2): **15.794 B de 16.384** → 590 B.
      - **fora de la RAM 1**: paràmetres (ja són a `s_lv`) i **còpia mestra FDC**.
      - el **HUD** i el **GAMEOVER** van després de la cançó (offset variable).
      - accés al mapa des del codi del món mitjançant **accessors residents**.
      Justificació: §1.3, §1.7, §4.3 i §4.4.
      *Pendent: comptar triggers vius i mesurar els tilesets.*
- [ ] **1.3** Taula única d'adreces (`src/mem_map.h`) + còpia verificada pel
      build + assert de no-solapament.
- [ ] **1.4a** Manifest amb **id de disc** per paquet.
- [ ] **1.4** "Codi propi de nivell": **només excepcions documentades** (el
      comportament ja és per `op`, §1.4). Taula de salts estàndard si cal.
- [ ] **1.5** Mesurar §1.7: convertir `Theme1`/`Theme2`, comptar triggers vius,
      i fixar el layout de la RAM 1 amb els números reals.
- **CHECKPOINT F1:** `LEVEL_PACKAGE.md` **aprovat per l'usuari** + layout amb
  asserts. No tocar codi abans.

---

## Fase 2 — Build universal (sense canvi visible)

- [x] **2.1** `build.py`: taula `LEVELS = [...]` i `build_level_packages()` que
      genera `LnWORLD.PAK` / `LnENEMI.ZX0` amb **manifest** (16 B + descriptors
      de 8 B). `GAMEOVER.ZX0` comú (decisió 2). Nivell 1 emès; els altres 5
      s'afegeixen a la Fase 4.
- [x] **2.2** `write_package()` valida: dins la finestra `0x4000-0x7FFF`,
      **no-solapament per banc** (amb la mida descomprimida) i **≤ 14.560 B**
      (scratch). Informe de pressupost per banc a cada build. L'assert fatal de
      **≥ 256 B** s'activa a la Fase 3 (ara C5 va ple per disseny: 60 B).
- [x] **2.3** Nivell 1 amb el nou sistema i **joc idèntic**: smoke test verd
      (DSK: 7 fitxers amb CRC correcte; arrencada: `magic=0xB0`, `px8=256`,
      `py8=8848`) i captura idèntica.
- [x] **CHECKPOINT F2:** build net + smoke test verd.
      **Cost:** el carregador genèric al resident = **+370 B**
      (`_CODE` 13.742, marge **466 B**).


---

## Fase 3 — Resident genèric

- [x] **3.1** `load_level_packages()` guiat pel manifest: 4 blocs de
      descompressió → **`load_package()` genèric** (Fase 2) + **fora constants i
      adreces de nivell** del resident (sessió 39): `LevelParams` v2 amb offsets
      (`rooms_off`, `doors_off`, `restore_off`, `code_exc_off`) i valors derivats
      (`map_w_px`, `map_w_x2`, `cam_max_x4`, `room_row_last`).
- [ ] **3.2** Sales al paquet del nivell, dins C5 (mapa · sales compactes · TRIG),
      amb un **sol accessor** `get_tile()`. Eliminar `render_room()`,
      `check_room_bonus()` i `s_row100[]` (aquest ja fora). *Pendent: cal
      reorganitzar C5 (el codi del món ha de sortir de C5).*
- [ ] **3.3** `g_map_level` realment usat (carrega el paquet del nivell triat).
- [x] **3.4** Treure de `moving.*`/`main.c` les constants de nivell (§1.5):
      fet (sessió 39), inclòs `LC1_DRAW/RESTORE` i `GAMEOVER_PTR`.
- [x] **3.5** Marge del Bloc 0 recuperat: **903 B** (sessió 40, movent el HUD i
      el GAME OVER al bloc de codi del C1).
- **CHECKPOINT F3:** pendent (3.2 i 3.3), amb verificació
  (`tools/smoke_test.py` + `verify_door_live.py` + `test_room_vinyls.py`).


---

## Fase 4 — Conversió dels nivells 2-6 (un per sessió)

Per a cada nivell N (2..6), mateixa llista:

- [ ] **N.a** Extractor: tileset + mapa + TRIG + enemics + objectes + portes a
      format CPC (amb les **files d'habitacions** incloses).
- [ ] **N.b** Paquet generat pel build universal; assert de pressupost verd.
- [ ] **N.c** Carrega a l'emulador i es veu correcte (captura).
- [ ] **N.d** Física/col·lisions bàsiques OK (camina, salta, escala).
- [ ] **N.e** Objectes/enemics propis del nivell (per `op`); si cal un tipus nou,
      va al motor (no al resident com a excepció de nivell).
- [ ] **N.f** Commit + `ESTAT.md`.

Ordre recomanat: **2 (ent)**, **3 (prison)** (les dues més semblants al 1),
**4 (egou)**, **6 (concert, el més petit)**, **5 (ville, el més gran: stress de
memòria)**.

- **CHECKPOINT F4:** els 5 nivells verificats.

---

## Fase 5 — Integració final

- [ ] **5.1** Flux mapa → nivell triat → següent nivell → final de joc.
- [ ] **5.2** Disc final: els 6 paquets caben; CRCs correctes; arrenca amb
      `RUN"BLUESB"` (i, si cal, canvi de disc 2).
- [ ] **5.3** Regressió completa (mort, Game Over, ascensors, habitacions,
      música).
- **CHECKPOINT F5:** joc complet verificat; documentació final; commit + push.

---

## 5. Protocol per a cada sessió

1. Llegir aquest document i `ESTAT.md`; `git status` net abans de començar.
2. Treballar **un checkpoint cada cop**; verificar amb l'emulador
   (`tools/smoke_test.py` **sempre** primer).
3. En acabar: marcar el checkpoint aquí, actualitzar `ESTAT.md`, commit i push.
4. Si un checkpoint revela un bloqueig, escriure'l a §6 i **preguntar a
   l'usuari** abans de canviar el pla.

---

## 6. Registre de bloqueigs i decisions

| Data | Tema | Decisió / estat |
|---|---|---|
| 2026-10-20 | Pla creat | — |
| 2026-10-20 | Decisions de l'usuari | S1 fidelitat 1:1; S2 segon disc permès; S4 Fase 0 aprovada |
| 2026-10-20 | Revisió amb dades reals | S5 alineació; S6 el pitjor nivell és ville pel mapa |
| 2026-10-20 | Mides del mapa | **Corregides**: inclouen les files d'habitacions (§1.1-1.2) |
| 2026-10-20 | C5 | **Decidit**: mapa (sales compactes) + TRIG a C5; codi del món a la RAM 1 (§1.3, §4) |
| 2026-10-20 | Correcció de càlcul | El pressupost de RAM 1 anterior (13.525 B) **oblidava el player AKG i els gràfics d'ascensor**; el real és 15.881 B amb la cançó actual (§4.3) |
| 2026-10-20 | Sales | **Decidit (D1)**: fora del mapa principal, compactes (200 B), **al paquet del nivell dins C5**, amb accessor únic. Allibera 1.024 B de la RAM 1 (§4.4) |
| 2026-10-20 | Codi de nivell | **Rebaixat a excepcions** (el comportament és per `op`) |
| 2026-10-20 | Fase 0.5 | 1 disc possible amb 2-3 KB de marge; disc 2 = pla B |
| 2026-10-20 | Fase 0.6 | **Feta**: `tools/smoke_test.py` + `build.py --check/--check-boot`; DSK i arrencada verds |
| 2026-10-20 | Cançons | **Mesurades**: main 1.619 · Theme1 2.721 · **Theme2 4.670** (arriba a 0x623E: el HUD no pot ser a 0x6000) |
| 2026-10-20 | RAM 1 | **Decidit (D2)**: layout per nivell amb offsets al manifest; FDC i paràmetres fora; pitjor cas 15.794 B (590 lliures) |
| 2026-10-20 | Pendent | Triggers per nivell, tilesets dels 6, mida dels PAK 2-6 |

---

## 7. Referències tècniques útils

- ZEsarUX remot: `scratch/test_user_flow.py` (Splash→Select→Map→Nivell),
  `read-memory`, `save-screen`, `get-registers`, `get-stack-backtrace`,
  `disassemble` (**adreces en decimal**).
- Mapa de símbols: `obj/bluesb.map`.
- Diagnòstic de crashes: `docs/BOOT_FAILURE_2026-10.md`.
- Lliçons dures:
  - `0xC0`/`0xC1` **comparteixen RAM** a `0x4000-0x7FFF`; `0xC1` canvia
    `0xC000-0xFFFF` a RAM 7 (amaga la VRAM pàgina 0).
  - La còpia mestra del driver FDC viu a `C0:0x7800`.
  - `sdasz80` no accepta `ld a,(hl+1)`, `ld hl,de` ni fitxers amb BOM.
