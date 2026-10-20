# Pla: sistema universal de nivells (6 nivells, zero pedaços)

> Document viu. Cada fase té **checkpoints** (`[ ]` pendent, `[x]` fet). Qui continuï ha de:
> 1. llegir §1-§3, 2. anar al primer checkpoint sense marcar, 3. fer-lo, verificar-lo, marcar-lo i fer commit.
> Idioma de treball: **català**. Regles del projecte: `AGENTS.md`. Estat general: `ESTAT.md`.

## 0. Supòsits (revisar quan l'usuari els confirmi)

- S1. Prioritat: **fidelitat 1:1 amb el DOS**; si la memòria no hi dona, es consulta l'usuari abans de recortar.
- S2. Disc: DSK estàndard de 180 KB fins que l'inventari (Fase 0) digui el contrari.
- S3. Cap canvi de layout de memòria ni build llarg sense aprovació explícita de l'usuari (`AGENTS.md`).

## 1. Context i fets comprovats

Cada nivell del DOS és el mateix conjunt de recursos (`tools/blues_dos/bb/level.c`, `staticres.c`):
tileset (`X.CK1/CK2`), mapa (`X.SQL`), TRIG (`X.BIN`, 2.560 B), enemics (`ENEMIn.SQV`),
sprites propis (`AVTX.SQV`), 41 objectes (`level_data/xpos/ypos`), portes (`level_door`),
dimensions (`level_dim`) i música.

| Nivell | 1 MAG | 2 ENT | 3 PRISON | 4 EGOU | 5 VILLE | 6 CONCERT |
|---|---|---|---|---|---|---|
| Ample (tiles) | 128 | 128 | 128 | 128 | 128 | 128 |
| Alt (files) | 72 | 72 | 72 | 61 | **95** | 49 |
| Mapa (B) | 9.216 | 9.216 | 9.216 | 7.808 | **12.160** | 6.272 |

Només el nivell 1 està convertit a CPC. Estat actual de memòria (Nivell 1):
- Banc C5 = mapa 9.216 + TRIG 2.560 + codi `moving_bank` 4.548 = 16.324/16.384 B (ple).
- C4 = tileset 16 KB (ple). C7 = frames jugador. C6 = enemics. C1 = música + HUD + habitacions + portes + params + codi ascensors.
- Bloc 0: ~836 B de marge de codi.

## 2. Per què ara són pedaços

- C5 barreja dades de nivell i codi del motor: el nivell 5 no hi cap.
- Adreces fixes a mà (`0x6400`, `0x6934`, `0x5800`...): ja hem patit **3 solapaments** (GAMEOVER vs ascensors, GAMEOVER vs còpia FDC `C0:0x7800`, i el `0xC1` que amaga la VRAM pàg. 0).
- Constants del nivell 1 a `build.py`/resident; `L1WORLD.PAK`/`L1ENEMI` hardcoded a `main.c`.
- Habitacions fora del mapa amb `if (row >= 74)` i funcions duplicades.

## 3. Principis (no negociables)

1. Bloc 0 = **només motor**. Cap constant, adreça ni codi d'un nivell concret.
2. Codi del motor ≠ dades de nivell: viuen en bancs diferents.
3. Cada nivell és un **paquet autodescrit** (manifest `(banc, adreça, mida)`); el carregador és un bucle genèric.
4. **Layout de bancs idèntic** per als 6 nivells, dimensionat pel pitjor cas, amb asserts al build.
5. El build itera una **taula de nivells**; mai `if level == 0`.
6. Habitacions = files del mateix mapa (com al DOS).
7. **Regla maquinari:** per cridar codi bancat que escriu a VRAM s'usa `0xC0` (no `0xC1`: amaga la VRAM pàg. 0). Les adreces de C0 i C1 a `0x4000-0x7FFF` són la **mateixa RAM**.
8. Tota adreça nova s'afegeix a **una sola taula d'adreces** amb assert de no-solapament.

---

## Fase 0 — Inventari (només lectura; no canvia res del joc)

Objectiu: dades reals per dimensionar el layout.

- [x] **0.1** Crear `tools/inventory_levels.py` que, per als 6 nivells i només des de `staticres.c`, mostri: mida de mapa, nombre d'objectes per tipus, ascensors, portes, habitacions (dst_row ≥ alçada), música, fitxers DOS associats.
- [ ] **0.2** Ampliar-lo amb mides dels recursos DOS al disc (`assets/bbdata`: `X.CK1/CK2/SQL/BIN`, `ENEMIn.SQV`, `AVTX.SQV`) i estimació de pes CPC (món + enemics) per nivell.
- [ ] **0.3** Determinar **tiles únics** usats per nivell (cal poder llegir el mapa de cada nivell; si no hi ha extractor, anotar-ho com a bloqueig i crear-lo a la Fase 4).
- [ ] **0.4** Escriure `docs/INVENTARI_NIVELLS.md` amb la taula resultant.
- [ ] **0.5** Calcular pressupost de disc: pes estimat dels 6 nivells vs 180 KB. Resposta explícita: *caben / no caben*.
- **CHECKPOINT F0:** inventari publicat + commit. Presentar a l'usuari i confirmar S1/S2.

## Fase 1 — Especificació (només document)

- [ ] **1.1** Redactar `docs/LEVEL_PACKAGE.md`: format del manifest (capçalera, seccions, CRC), mapa de bancs, adreces, pressupost per banc i per nivell.
- [ ] **1.2** Decidir on va el codi de `moving_bank` (4,5 KB) un cop fora de C5 (opcions: banc de codi fix, compressió del tileset, etc.), justificat amb números de F0.
- [ ] **1.3** Definir la taula única d'adreces (`src/mem_map.h` + còpia a `build.py` generada o verificada).
- [ ] **1.4** Definir el protocol de "codi propi de nivell" (taula de salts estàndard, com els ascensors).
- **CHECKPOINT F1:** `LEVEL_PACKAGE.md` **aprovat per l'usuari**. No tocar codi abans.

## Fase 2 — Build universal (sense canvi visible)

- [ ] **2.1** `build.py`: taula `LEVELS = [...]` (nom, fitxers, params) i bucle que genera `LnWORLD.PAK`/`LnENEMI` per nivell.
- [ ] **2.2** Asserts de pressupost per banc i nivell + comprovador de solapaments contra la taula d'adreces.
- [ ] **2.3** Nivell 1 generat amb el nou sistema; **el joc ha de ser idèntic** (`scratch/test_user_flow.py` + captura).
- **CHECKPOINT F2:** build net, nivell 1 verificat a ZEsarUX (Jake i Elwood), commit + push.

## Fase 3 — Resident genèric

- [ ] **3.1** `load_level_packages(level)` guiat pel manifest (cap adreça de nivell al resident).
- [ ] **3.2** Mapa de nivell amb files de habitacions integrades; eliminar `get_tile_at` especial, `render_room`, `check_room_bonus` duplicats.
- [ ] **3.3** `g_map_level` realment usat (carrega el paquet del nivell triat).
- [ ] **3.4** Revisar marge del Bloc 0 (objectiu: no empitjorar els 836 B).
- **CHECKPOINT F3:** nivell 1 idèntic, habitacions/portes/vinils verificats (`verify_door_live.py`, `test_room_vinyls.py`), commit + push.

## Fase 4 — Conversió dels nivells 2-6 (un per sessió)

Per a cada nivell N (2..6), mateixa llista:
- [ ] **N.a** Extractor: tileset + mapa + TRIG + enemics + objectes + portes a format CPC.
- [ ] **N.b** Paquet generat pel build universal; assert de pressupost verd.
- [ ] **N.c** Carrega a l'emulador i es veu correcte (captura).
- [ ] **N.d** Física/col·lisions bàsiques OK (camina, salta, escala).
- [ ] **N.e** Objectes/enemics propis del nivell; nous tipus → codi de nivell amb taula de salts.
- [ ] **N.f** Commit + `ESTAT.md`.

Ordre recomanat: 2 (ENT), 3 (PRISON), 4 (EGOU), 6 (CONCERT, el més petit), 5 (VILLE, el més gran: stress de memòria).
- **CHECKPOINT F4:** els 5 nivells verificats.

## Fase 5 — Integració final

- [ ] **5.1** Flux mapa → nivell triat → següent nivell → final de joc.
- [ ] **5.2** Disc final: els 6 paquets caben; CRCs correctes; arrenca amb `RUN"BLUESB"`.
- [ ] **5.3** Regressió completa (mort, Game Over, ascensors, habitacions, música).
- **CHECKPOINT F5:** joc complet verificat; documentació final; commit + push.

---

## 4. Protocol per a cada sessió

1. Llegir aquest document i `ESTAT.md`; `git status` net abans de començar.
2. Treballar **un checkpoint cada cop**; verificar amb l'emulador (ZEsarUX, scripts a `scratch/`).
3. En acabar: marcar el checkpoint aquí, actualitzar `ESTAT.md`, commit i push.
4. Si un checkpoint revela un bloqueig, escriure'l a la secció 5 i **preguntar a l'usuari** abans de canviar el pla.

## 5. Registre de bloqueigs i decisions

| Data | Tema | Decisió/Estat |
|---|---|---|
| 2026-10-20 | Pla creat | S1-S3 per confirmar |

## 6. Referències tècniques útils

- ZEsarUX remot: `scratch/test_user_flow.py` (Splash→Select→Map→Nivell), `read-memory`, `save-screen`, `get-registers`.
- Mapa de símbols: `obj/bluesb.map`. Diagnòstic de crashes: `docs/BOOT_FAILURE_2026-10.md`.
- Lliçons dures: `0xC0`/`0xC1` comparteixen RAM a `0x4000-0x7FFF`; `0xC1` canvia `0xC000-0xFFFF` a RAM 7; la còpia mestra del driver FDC viu a `C0:0x7800`; `sdasz80` no accepta `ld a,(hl+1)`, `ld hl,de` ni fitxers amb BOM.
