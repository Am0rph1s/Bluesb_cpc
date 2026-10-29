# LEVEL_PACKAGE — format del paquet de nivell (Fase 1.1)

> Estat: **ESBORRANY per aprovar** (2026-10-20). No s'ha d'implementar res
> d'aquí fins que l'usuari aprovi el document (CHECKPOINT F1).
> Complementa `docs/PLA_NIVELLS_UNIVERSAL.md` (mides mesurades i decisions
> D1/D2) i `docs/INVENTARI_NIVELLS.md` (dades dels 6 nivells).

---

## 1. Objectiu

Un sol build ha de generar **6 paquets de nivell** amb la mateixa estructura, i
el **resident no ha de tenir cap dada, adreça ni codi exclusiu de cap nivell**:
tot el que és del nivell viatja al paquet i el carregador és un **bucle genèric**
guiat per un manifest.

Canvis respecte del format actual (`L1WORLD.PAK`):

| Actual | Nou |
|---|---|
| Header de 6 B amb 3 offsets fixos (`b5`, `mus`, `elev`) | **Manifest** amb N seccions `(banc, destí, compressió, offset)` |
| Adreces de destí **hardcoded** a `main.c` | Les dóna el manifest |
| Bloc únic de C1 amb offsets fixos (HUD a `0x6000`, portes a `0x6800`...) | **Seccions independents** amb adreça calculada pel build |
| Sales a `C1:0x6400` (fora del mapa) | Sales **compactes al paquet**, dins **C5** (D1) |
| Portes escrites a mà a `build_music()` (llista Python) | Portes llegides de `staticres.c` (`level_door`) |
| Codi del món dins C5 (`BANK5.BIN` amb mapa+TRIG+codi) | Codi del món **a C1** (D2), mapa i TRIG a C5 |
| Un sol nivell | Taula `LEVELS[]` al build |

---

## 2. Fitxers per nivell

Dos fitxers per nivell (cap dels dos no arriba a l'scratch de `0x8320-0xBBFF`
= **14.560 B**, límit dur del carregador FDC actual):

| Fitxer | Contingut | Mida actual (nivell 1) |
|---|---|---|
| `LnWORLD.PAK` | tileset, mapa, sales, TRIG, cançó, HUD, portes, paràmetres, codi del món, (codi d'excepcions), (gràfics d'ascensor), GAMEOVER | 13.483 B |
| `LnENEMI.ZX0` | frames dels enemics → `C6:0x4000` | 7.233 B |

> Si en algun nivell `LnWORLD.PAK` s'acostés al límit, la sortida és **càrrega
> en 2 passades** per sectors (el FDC llegeix per sectors i tenim la taula CHS).
> L'assert del build ha de vigilar-ho.

Noms 8.3: `L1WORLD.PAK` … `L6WORLD.PAK`; `L1ENEMI.ZX0` … `L6ENEMI.ZX0`.

---

## 3. Format del manifest

### 3.1 Capçalera (16 bytes, little-endian)

| Offset | Mida | Camp | Valor |
|---|---|---|---|
| 0 | u8 | `magic` | `0x42` ('B') |
| 1 | u8 | `version` | `1` |
| 2 | u8 | `level_id` | 0..5 |
| 3 | u8 | `flags` | bit0: te codi d'excepcions · bit1: te gràfics d'ascensor · bit2: te sales · bit3: te cançó pròpia |
| 4 | u16 | `total_len` | mida total del fitxer |
| 6 | u16 | `n_sections` | nombre de seccions |
| 8 | u16 | `disc_id` | 0 = disc 1, 1 = disc 2 (reserva S2) |
| 10 | u16 | `hdr_crc` | CRC-16/CCITT dels 10 bytes anteriors |
| 12 | u32 | `reserved` | 0 |

### 3.2 Descriptor de secció (8 bytes, little-endian)

| Offset | Mida | Camp | Notes |
|---|---|---|---|
| 0 | u8 | `bank` | valor a escriure a `0x7F00`: `0xC1` (RAM 1), `0xC4`, `0xC5`, `0xC6`, `0xC7` |
| 1 | u8 | `flags` | bit0: **1 = ZX0**, 0 = cru |
| 2 | u16 | `dest` | adreça dins la finestra (p. ex. `0x4000`, `0x5000`…) |
| 4 | u16 | `src_off` | offset dins el fitxer |
| 6 | u16 | `src_len` | bytes al fitxer (comprimits si ZX0) |

Les seccions comencen a `16 + 8 × n_sections`, **sense alineació obligatòria**
(el build pot alinear a 2 B per comoditat).

### 3.3 Verificació

- CRC-16/CCITT del **fitxer sencer** (com ara: `fdc_crc16`), comparat amb el
  header generat (`src/disk_tables.h`). Es manté el comportament actual
  (3 reintents de càrrega i border de color si falla).
- El `dest` de cada secció ha de caure **dins** la finestra `0x4000-0x7FFF` i no
  solapar-se amb cap altra secció del mateix banc (assert del build).

---

## 4. Seccions del paquet de món (`LnWORLD.PAK`)

| # | Secció | Banc | Destí | Mida (mesurada/calculada) | Compressió |
|---|---|---|---|---|---|
| 1 | Tileset | `0xC4` | `0x4000` | **16.384** (256 × 64 B) | ZX0 |
| 2 | Mapa | `0xC5` | `0x4000` | `128 × files_reals` (10.752 / 9.216 / 11.136 / 9.728 / **12.160** / 6.272) | ZX0 |
| 3 | Sales | `0xC5` | `0x4000 + map_len` | `200 × room_count` (1.000 / 0 / 1.200 / 600 / 200 / 0) | cru |
| 4 | TRIG | `0xC5` | `després de les sales` | **1.280** (256 × 5 B) | cru |
| 5 | Cançó | `0xC1` | `0x5000` | **1.619 / 2.721 / 1.619 / 1.619 / 2.721 / 4.670** | ZX0 |
| 6 | HUD | `0xC1` | després de la cançó | 936 | cru |
| 7 | Portes | `0xC1` | després del HUD | `4 × n_portes` (92 màx.) | cru |
| 8 | Paràmetres | `0xC1` | després de portes | 52 (v2, vegeu §6) | cru |
| 9 | Codi del món | `0xC1` | després de paràmetres | **4.548** (avui) | cru (vegeu §10) |
| 10 | Codi d'excepcions | `0xC1` | després | 957 (nivell 1) · **0 als altres** | ZX0 |
| 11 | Gràfics d'ascensor | `0xC1` | després | 224 frame + (1.120 de buffers **no es carreguen**) | cru |
| 12 | GAMEOVER | `0xC1` | després | 1.360 (o 619 comprimit) | ZX0 |

Notes:

- Els **buffers de fons dels ascensors** (`0x7000` avui) són RAM de treball: no
  són cap secció, només cal reservar-hi espai (només als nivells amb ascensors).
- La **còpia mestra del FDC** surt de la RAM 1 (D2): es carrega amb el motor FDC
  a un forat lliure de C5 o C6, o bé es manté a `0x7800` **només** si el
  pressupost del nivell ho permet (l'assert ho decideix).
- L'ordre de les seccions dins el fitxer és lliure; el build les emet en l'ordre
  que li convingui (les ZX0 grans primer, per si mai cal streaming).
- **Sessió 42 — compactació d'IDs**: el build reordena el tileset amb els tiles
  usats i remapeja mapa, sales, TRIG, restore, animacions i `bg_tile`. El
  tileset passa a `N×64` (L1: 232 = 14.848 B) i el TRIG a `N×5` (L1: 1.160 B);
  les mides d'aquesta taula són les màximes amb 256 tiles.

---

## 5. Layout per nivell (el calcula el build)

El build **calcula** les adreces i les escriu al manifest i als paràmetres. No
hi ha cap adreça de C1 hardcoded al resident.

```
C4:  0x4000  tileset (16.384)                                        [ple]
C5:  0x4000  mapa (128 * files_reals)
     +        sales (200 * room_count)          <- rooms_off
     +        TRIG compacte (5 B per tile usat) <- trig_off
     +        codi del món (moving_bank.c) + _DATA contigua
     ...      (forat lliure unificat)
     0x7FE8   taula de salts fixa BC_* (8 slots x 3 B = 24 B)
C1:  0x4000  player AKG (4.096, slot fix)          [no és secció: MUSBANK]
     0x5000  cançó (S)
     +       HUD (936)
     +       portes
     +       paràmetres (52)
     +       codi del món (4.548)
     +       [codi d'excepcions]  (només si flags bit0)
     +       [frame ascensor]     (només si flags bit1)
     +       GAMEOVER
     +       [buffers d'ascensor: RAM, 1.120, només si flags bit1]
C6:  0x4000  frames d'enemics + codi d'enemics (LnENEMI)
C7:  0x4000  frames del jugador (Jake/Elwood, fixes)
```

**Pressupost mesurat (pitjor cas per nivell; C1 inclou player AKG 4.096, HUD 936,
portes `4×n`, paràmetres 84, codi del món 4.548, GAMEOVER 1.360 i, només al
nivell 1, codi d'excepcions 957 + frame 224; **sense** la còpia FDC):**

| Nivell | C5 (mapa+sales+TRIG) | C5 lliures | C1 | C1 lliures |
|---|---|---|---|---|
| 1 magasin | 12.776 | +3.608 | 13.916 | **+2.468** |
| 2 ent | 11.776 | +4.608 | 13.745 | +2.639 |
| 3 prison | 12.976 | +3.408 | **15.790** | **+594** |
| 4 egou | 10.968 | +5.416 | 12.723 | +3.661 |
| 5 ville | **14.920** | **+1.464** | 13.753 | +2.631 |
| 6 concert | 8.832 | +7.552 | 15.718 | +666 |

(el pitjor de C1 és el 3 perquè té 24 portes; el 6 té la mateixa cançó i 6 portes)


Asserts obligatoris al build: `≤ 16.384` **i** `≥ 256 B` de marge a cada banc.

---

## 6. Paràmetres del nivell (`LevelParams` v2)

El resident **només** llegeix aquests camps. Cap constant de nivell al codi.

| Camp | Tipus | Origen |
|---|---|---|
| `magic`, `version` | u8, u8 | `0xB0`, `2` |
| `level_id` | u8 | índex 0..5 |
| `map_w`, `map_h` | u8, u8 | `level_dim` (columnes / files visibles) |
| `map_rows` | u8 | files reals (amb el bloc de sales) |
| `rooms_off`, `trig_off` | u16, u16 | offsets **dins C5** (`trig_off` = 69 al struct) |
| `room_count`, `room_cols`, `room_row0` | u8 ×3 | `room_cols = 20`, `room_row0 = pos[nivell]` |
| `hud_off`, `doors_off`, `params_off` | u16 ×3 | offsets **dins C1** |
| `code_world_off`, `code_exc_off` | u16 ×2 | 0 si no n'hi ha |
| `frames_off`, `bg_off` | u16 ×2 | 0 si no n'hi ha (ascensors) |
| `gameover_off` | u16 | dins C1 |
| `tile_vinyl`, `tile_instr`, `tile_empty` | u8 ×3 | tiles d'ítems |
| `elev_count` | u8 | nombre d'ascensors |
| `song_id` | u8 | 1..3 |
| `start_x`, `start_y` | u16 ×2 | posició inicial (px8) |
| `cam0_x4`, `cam0_row` | u16 ×2 | càmera inicial |
| `restart_x`, `restart_y` | u16 ×2 | respawn |
| `max_cam_row` | u16 | `map_h*2 - 20` |

> **Atenció (sessió 42):** SDCC **empaqueta** l'struct sense alineació. La v2
> actual fa **73 B**: `rooms_off`=56, `doors_off`=58, `restore_off`=60,
> `map_w_px`=62, `map_w_x2`=64, `cam_max_x4`=66, `room_row_last`=68,
> `trig_off`=69, `code_exc_off`=71. El build ha de fer servir aquests offsets
> (abans es patchava `code_exc_off` a 70 i el runtime llegia 0x4800).

---

## 7. Carregador genèric (resident)

```c
static u8 load_package(const DiskFileDesc* f, u16 crc) {
    u8 t, ok = 0;
    for (t = 0; t < 3 && !ok; t++) {
        if (!fdc_load_file(0xC0, f, 0xC0, (void*)PAK_SCRATCH)) continue;
        if (fdc_crc16((const u8*)PAK_SCRATCH, (u16)(f->ondisk_bytes - 128)) == crc) ok = 1;
    }
    if (!ok) return 0;
    const u8* pak = (const u8*)PAK_SCRATCH;
    u8 n = pak[6], i;
    for (i = 0; i < n; i++) {
        const u8* d = pak + 16 + i * 8;
        u8 bank = d[0], flags = d[1];
        u16 dst = (u16)(d[2] | (d[3] << 8));
        u16 off = (u16)(d[4] | (d[5] << 8));
        u8 prev = bank_set(bank);
        if (flags & 1) zx0_decompress(pak + off, (void*)dst);
        else cpct_memcpy((void*)dst, pak + off, (u16)(d[6] | (d[7] << 8)));
        bank_restore(prev);
    }
    return 1;
}
```

Després: `level_params_load()` (llegeix `params_off` del manifest → `s_lv`).

Substitueix els 4 blocs de descompressió actuals de `load_level_packages()`.
Cost estimat de codi: ~40-60 B més que la versió desenrotllada → cap al
pressupost de 836 B del Bloc 0 (caldrà mesurar-ho).

---

## 8. Asserts del build (bloquejants)

1. Cap secció no surt de la finestra `0x4000-0x7FFF`.
2. Dins de cada banc, les seccions **no se solapen** (ordenades per `dest`).
3. Cada banc té **≥ 256 B** de marge.
4. `LnWORLD.PAK` **≤ 14.560 B** (límit de l'scratch) o, si no, el build ha
   d'activar el mode de càrrega en 2 passades.
5. `magic`/`version`/`hdr_crc` correctes i `n_sections` coherent amb el fitxer.
6. `hud_off`, `rooms_off`, `trig_off`… dins dels límits dels blocs respectius.
7. El **codi del món** (`moving_bank`) no pot excedir el forat assignat.

---

## 9. Migració (per fases, sense trencar el joc)

1. **Fase 2.3a**: el build genera `L1WORLD.PAK` **amb el nou manifest**, però
   el resident encara el carrega com ara (s'ignoren les seccions). Sirveix per
   validar mides i asserts sense tocar el joc.
2. **Fase 2.3b**: el resident passa a `load_package()` genèric. El joc ha de
   quedar **idèntic** (smoke test + `test_user_flow.py`).
3. **Fase 3**: treure del resident les adreces (`0x6400`, `0x6860`, `0x6934`,
   `0x5800`, `0x7200`) i usar els offsets de `s_lv`; accessor únic de tiles
   (mapa + sales); `get_tile` amb `room_row0`.
4. **Fase 4**: repetir per als nivells 2-6 (extractor + paquet + asserts).

---

## 10. Decisions obertes (per a l'aprovació)

1. **Codi del món comprimit (ZX0) o cru?** Comprimit estalvia al disc
   (~4.548 → ~2.8 KB) però obliga a un destí temporal gran a l'scratch abans de
   copiar-lo a C1 (l'scratch té 14.560 B i el paquet ja hi és) → **cru** és més
   simple; el disc té marge suficient (Fase 0.5). *Recomanació: cru.*
2. **GAMEOVER dins cada paquet** (1.360 B × 6 ≈ 8 KB de disc) o **fitxer comú**
   (`GAMEOVER.BIN`, 1.360 B una sola vegada). *Recomanació: fitxer comú carregat
   amb el paquet del nivell (una secció més al manifest).*
3. **TRIG dins C5** (decidit, D2) — confirmar que el codi del món l'ha de llegir
   per accessor (cost per frame a mesurar a Fase 3).
4. **Nom dels fitxers**: `L1WORLD.PAK`/`L1ENEMI.ZX0` (mantenir) vs
   `L1.PAK`/`L1.ENE`. *Recomanació: mantenir els actuals.*
5. **Segon disc (S2)**: camp `disc_id` reservat; cap lògica fins que calgui.
