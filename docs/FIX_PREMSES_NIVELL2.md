# Documentació Tècnica: Correcció del Penjat a les Premses Hidràuliques (Nivell 2)

**Data**: 2026-10-25  
**Branques / Commits**: `master` (`697a2c3`)  
**Components afectats**: `tools/build.py`, `tools/pack_level.py`, `src/level_code.c`, `assets/bbdata/LEVELPARM*.BIN`.

---

## 1. Descripció del Problema

Quan en Jake arribava a la zona de les cintes transportadores sota les premses hidràuliques al Nivell 2 (`ENT`), el joc es penjava completament amb un so o xiulet continu en bucle (el xip AY encallat executant el darrer to programat).

---

## 2. Causa Arrel

El problema tenia un doble origen en la distribució de la memòria dinàmica del **Banc 1 (C1)** i el salt al codi bancat:

### A. Desbordament i Trepitjada de Buffers al Banc 1 (`0x4000..0x7FFF`)
Al Nivell 1 (`magasin`), el codi bancat gestionava 5 ascensors petits (224 bytes de frame de sprite `ELEV.BIN` i 1.120 bytes de buffer de fons). El layout inicial assignat a `build.py` era:
- `LC1_FRAMES_BASE = 0x6E20`
- `LC1_BG_BASE = 0x7000`
- `LC1_DATA_BASE = 0x7500`

Al Nivell 2 (`ent`), les premses hidràuliques utilitzen un sprite molt més gran (`PRESS.BIN`, 24×33 px Mode 0 = 12 B × 33 línies = **792 bytes**) i un buffer de restauració de fons molt més extens (**396 bytes per premsa i pàgina**, és a dir, $3 \times 2 \times 396 = \mathbf{2.376\text{ bytes}}$).

Amb el layout anterior es produïen dues col·lisions destructives:
1. `PRESS.BIN` s'escrivia a partir de `0x6E20` i ocupava fins a `0x6E20 + 792 = 0x7138`, **trepitjant 312 bytes de l'inici de `LC1_BG_BASE` (`0x7000`)**.
2. Els buffers de fons de les premses necessitaven des de `0x7000` fins a `0x7000 + 2376 = 0x7948`. Com que les variables de control (`s_mover_dst` a `_DATA`) eren a `0x7500`, el buffer **les sobreescrivia completament a cada frame**. En cridar la rutina de restauració (`moving_restore_box()`), l'adreça de destinació VRAM llegida era brossa o adreces aleatòries, corrompent la pila i bloquejant la CPU.

### B. Desalineament del Punter de Salt (`code_exc_off`)
A `tools/pack_level.py`, l'offset per defecte del punt d'entrada al codi d'excepcions (`code_exc_off`) s'havia quedat fixat a `0x6934`, mentre que la imatge real del codi compilat (`level_code`) se situava a `0x6950` (alineada amb el final de la cançó del nivell). Cridar a `0x6934` provocava executar 28 bytes de memòria no inicialitzada/zeros abans d'arribar al codi.

---

## 3. Solució Implementada

### Nou Mapa de Memòria del Banc 1 (C1: `0x5000..0x7FFF`)
S'ha reestructurat completament l'espai post-música/HUD per garantir que tot capiga sense solapaments i amb marge de seguretat:

| Offset Banc 1 | Contingut | Mida | Estat |
|---|---|---|---|
| `0x5000..0x5FFF` | Música (cançó) + GAMEOVER (`0x5800`) | ~1.619 B / 1.360 B | OK |
| `0x6000..0x63FF` | Tires Mode 0 del HUD | 552 B | OK |
| `0x6400..0x67FF` | Forat lliure / Portes / Taula Restore | ~1.000 B | OK |
| `0x6900..0x6948` | `LevelParams` (struct de paràmetres v2) | 73 B | OK |
| **`0x6950..0x6DBF`** | Codi d'excepcions del nivell (`level_code.c`) | 1.135 B | OK |
| **`0x6DC0..0x6DD4`** | `_DATA` (`s_mover_dst` de 20 bytes) | 20 B | **Mogut just darrere de `_CODE`** |
| **`0x6E00..0x7118`** | Frames de sprite (`PRESS.BIN` 792 B / `ELEV.BIN` 224 B) | 792 B / 224 B | Sense col·lisió |
| **`0x7200..0x7B48`** | Buffers de fons (3 premses × 2 pàgines × 396 B) | 2.376 B | **Marge ampli fins a `0x8000`** |

### Fitxers Modificats
- `tools/build.py`:
  - Actualitzades les constants:
    - `LC1_CODE_BASE = 0x6950`
    - `LC1_DATA_BASE = 0x6DC0`
    - `LC1_FRAMES_BASE = 0x6E00`
    - `LC1_BG_BASE = 0x7200`
- `src/level_code.c`:
  - Actualitzades les macros `#define LC_FRAMES_BASE ((const u8*)0x6E00)` i `#define LC_BG_BASE ((u8*)0x7200)`.
- `tools/pack_level.py`:
  - Actualitzat el valor contractual per defecte de `code_exc_off` a `0x6950`.
- `assets/bbdata/LEVELPARM0.BIN` i `assets/bbdata/LEVELPARM1.BIN`:
  - Regenerats amb el camp `code_exc_off = 0x6950`.

### Verificació
- El resident de Bloc 0 es manté estrictament en **14.206 B** (`0x0100..0x387E`), conservant els **2 B de marge** requerits fins a `_DATA`.
- `smoke_test.py` valida la integritat del DSK i l'arrencada neta a ZEsarUX (`magic=0xB0`, `px8=256`, `py8=8848`).
