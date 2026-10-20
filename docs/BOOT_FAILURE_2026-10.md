# Diagnòstic: el joc no arrenca després del canvi "ascensors al Banc C1" [RESOLT]

> Estat a 20/10/2026. Document de continuació: resolt i tancat.
> Relacionat: `ESTAT.md` (sessions 31-36), `AGENTS.md` (regles del projecte).

---

## 1. Objectiu de la sessió (què volia aconseguir)

1. **Arreglar el bucle de convergència del build** (`tools/build.py`): els headers
   (`disk_tables.h`, `front_tables.h`, `crt_addrs.h`, `starter_tables.h`) es
   calculaven al FINAL de la iteració, però el resident es compilava al
   PRINCIPI → el resident es quedava amb el CRC vell → el DSK no arrencava.
   **Estat: FET I VERIFICAT** (el bucle ara convergeix en 2 iteracions i els CRC
   del disc coincideixen amb els dels fitxers).
2. **Treure el codi dels ascensors del Bloc 0 resident** i deixar-lo al
   **Banc C1**, dins el mateix paquet que la música/HUD/les habitacions
   (`src/level_code.c` + `engine/bank1_table.s` + `build_levelcode()`).
   Motiu: el resident ha de contenir **només el motor comú**; el codi
   d'un nivell concret no hi ha de viure.
3. Verificar que el joc arrenca, que el nivell 1 es carrega i que els
   ascensors es dibuixen.
4. Després, continuar la llista de fidelitat DOS (velocitats de walkers,
   reixes de primer pla, plataformes/`op4`, tiles animats) i el mapatge
   "a la DOS" de les habitacions (files 74-83 del mateix tilemap).

** Estat real: el pas 1 està fet; el pas 2 està a mitges (codi escrit, no
verificat) i el pas 3 està BLOQUEJAT perquè el joc no arrenca.**

---

## 2. Estat de l'arbre de treball (NO commitejat)

```
 M tools/build.py        <- pas del build_levelcode() + constants LC1_* + C1 + bucle corregit
 M src/disk_tables.h     <- generat (CRC/CHS)
 M src/starter_tables.h  <- generat (CHS/CRC)
 M src/crt_addrs.h       <- generat
 M engine/front_tables.h <- generat
?? engine/bank1_table.s  <- NOU: taula de salts del C1 (_lc_elev_draw 0x6934 / _lc_elev_restore 0x6937)
?? src/level_code.c      <- NOU: codi dels ascensors per al Banc C1 (draw/restore, frames 0x6E20, buffers 0x7000)
```

`src/moving.c` i `src/moving.h` han estat **revertits** amb `git checkout`
(el codi dels ascensors encara viu al resident, versió "bisec 2": al C1 només hi
ha el *codi*, els frames i els buffers tornen al C0/C7).

Darrer commit pujat: `b9a8e4a` (docs sessió 35). **Tot el que hi ha al voltant
d'aquestes modificacions no està pujat.**

---

## 3. El problema concret

Amb el build actual (`py -3 -u tools/build.py`, converges en 2 iteracions):

* `scratch/test_cam_fix.py` → el joc **no arriba al nivell**:
  `inici: py=480 cam_row=0` i `FINAL: py=480 ... DESFASAMENT=+364 px`
  (en el build que funcionava era `DESFASAMENT=-2 px`).
* La pantalla és **negra** (captura `scratch/camfix_final.png`).
* El `PC` del processador és sempre a `0x1Bxx-0x1Exx` (la zona del firmware).

---

## 4. Diagnòstic fet pas a pas (amb resultats)

### 4.1 El bucle del build: CONFIRMAT que era un problema i ja està arreglat

* Symptom històric: border vermell (0x43) i el joc no arrencava.
* Diagnòstic: els CRC dels fitxers del disc **coincidien** amb els dels
  fitxers (`CRC_L1WORLD` 0x8848, `CRC_L1ENEMI` 0x0A63, `CRC_FDC` 0xE50B) i el
  `GAME_CRC` del starter (0xF2EF) és el CRC real d'`obj/GAME.BIN`.
  ⇒ el problema **no** era el CRC sinó l'ordre del bucle.
* **Fix** (`tools/build.py`): els headers s'escriuen **abans** de
  `compile_and_link()` de la iteració següent. El bucle ara:
  iteració N → compila → construeix el DSK → calcula els headers nous →
  si canvien, s'escriuen i es torna a iterar. Convergeix en 2 iteracions:
  ```
  BANC1: codi del nivell a 0x6934 (957 B de codi, 20 B de dades)
  PAK: L1WORLD 13473 B (tiles=5649 b5=4945 mus=2209 elev=664)
  DSK: ...bluesb.dsk  (RUN"BLUESB" -> starter load 0x3000/run 0xC000, game=15367 bytes)
    -> starter_tables.h actualitzat (iteracio 1)
  ```
* **El bucle ja no és el problema.** Ara el que falla és una altra cosa.

### 4.2 El DSK: el joc NO s'arriba a carregar a la memòria

* `scratch/diag_boot2.py` (arrenca el joc i fa `get-registers` cada 2,5 s):
  `PC=1bc5 SP=bfea AF=0000 BC=0400 HL=050a ... IX=e5e5` → el processador
  executa **codi del firmware ROM** (el desensamblatge dona instruccions
  8080, p. ex. `CP (HL)`, que no existeixen al Z80) ⇒ **no és codi del joc**.
* `scratch/diag_boot3.py` (memòria a l'arrencada, abans de_running el joc):
  ```
  BOOT 0x3900: 00 00 00 00 00 00 00 00 18 18 18 18 18 00 18 00
  BOOT 0x3C00: 00 00 00 00 00 00 00 00 F0 F0 F0 F0 00 00 00 00
  ```
  Això és **la font del sistema del CPC** (0x3000-0x3FFF).
* Després de prémer SPACE 10 cops, la memòria a `0x3900-0x3CFF` és **exactament
  la mateixa font** ⇒ **el `cpct_memset(CRT_DATA_START=0x3900, 0, 1021)` de
  `main()` (src/main.c) MAI S'HA EXECUTAT** ⇒ **`main()` no s'ha arribat a cridar**.
* Cerca de la imatge del joc a tota la memòria (64 KB, blocs de 4 KB,
  `read-memory`): **ni `GAME.BIN` ni `STARTER.BIN` hi són** (patró de 8 bytes,
  cap hit) ⇒ **el fitxer no s'ha carregat mai a la RAM**.
* `get-stack-backtrace`: `1CE6H 0400H 0000H 1BD9H 050AH` (adresses de ROM).
* Conclusió: **el boot del disc no carrega res i el joc no s'arriba a executar**.

### 4.3 El catàleg del disc: **és correcte**

`scratch/diag_cat.py` (escripta `cat` a BASIC + captura `scratch/cat_list.png`):

```
Amstrad 128K Microcomputer  (v3)
BASIC 1.1
Ready
cat
Drive A: user 0
BLUESB   .BIN    2K    FSPLASH .ZX0    5K
ELWOOD  .ZX0    3K    GAME     .BIN   16K
FDC      .BIN    1K    JAKE     .ZX0    4K
FMAP     .ZX0   10K    L1ENEMI  .ZX0    8K
FRONT    .BIN    3K    L1WORLD  .PAK   14K
FSELECT  .ZX0   13K    MUSBANK  .BIN    8K
91K free
Ready
```

⇒ El firmware llegeix **tots** els fitxers del catàleg ⇒ **el catàleg no és el
problema**. I la mida de cada fitxer correspon al que hi ha al DSK.

### 4.4 El sector d'arrencada del disc: **està ocupat per una entrada del catàleg**

Al DSK, pista 0 / sector 0xC1, l'àrea 0x80-0xFF (que el firmware del CPC
exECUTA com a codi d'arrencada) conté l'entrada de catàleg "FSPLASH ZX0":

```
sect 0xC1 0x00-0x3F: 00 42 4C 55 45 53 42 20 20 42 49 4E ...  (entrada BLUESB.BIN)
BOOT 0x80-0xBF      : 00 46 53 50 4C 41 53 48 20 5A 58 30 ...  (entrada FSPLASH.ZX0)
```

⇒ El codi del sector d'arrencada és basura ⇒ **el boot del disc falla** ⇒ el CPC
torna al BASIC ("Ready" ✓, ho confirma la captura) ⇒ el joc no arrenca ✓.

**IMPORTANT (encara no resolt):** `tools/dskutil.py` (que escriu el catàleg
a partir de l'offset 0x00 de la concatenació C1..C4) **no ha canviat des del
commit `6269126`**, és a dir: **aquest DSK probably mai ha tingut un sector
d'arrencada vàlid** → el joc s'hauria d'arrencar sempre des de BASIC amb
`RUN "BLUESB"` (el que fan els scripts de test), no des del boot del disc.
Cal confirmar-ho amb el test A/B del punt 6.

### 4.5 Cronologia: les tecles es poden perdre

* `scratch/test_cam_fix.py` i `diag_boot2.py` escriuen `run "bluesb"` + RETURN
  **~4 s després d'arrencar l'emulador**, és a dir, mentre el CPC encara està
  fent el boot del disc (que avisa amb "lp0 on fire ... Just kidding ;)").
  Si el boot del disc acaba en BASIC, aquestes tecles **es perden**.
* Amb el build que funcionava, el mateix script funcionava ⇒ o bé les tecles
  arribaven, o bé el joc s'arrencava pel boot del disc.

---

## 5. Hipòtesis (amb el grau de confiança)

| # | Hipòtesi | Estat |
|---|-----------|-------|
| H1 | El CRC obsolet al resident (bucle del build) | **DESCARTADA** (els CRC coincideixen i el bucle ja està corregit) |
| H2 | El catàleg del DSK està trencat | **DESCARTADA** (`cat` llegeix els 12 fitxers correctament) |
| H3 | El codi nou del C1 (`src/level_code.c`) corrompreix el Banc 1 i el joc peta en carregar el nivell | **POC PROBABLE**: el joc no arriba ni a `main()` (no hi ha memset ⇒ no s'ha carregat res des del disc); a més el codi del C1 no el crida ningú (el `moving.c` està revertit) |
| H4 | El DSK està mal construït en aquesta iteració (p. ex. la DSK que hi ha al disc és d'una iteració i el `starter_tables.h` d'una altra) | **PLAUSIBLE** — el bucle restructurat escriu el DSK i els headers en ordre diferent del d'abans; cal revisar l'ordre exacte i fer la prova A/B |
| H5 | El problema **ja existia** abans d'aquest canvi (el DSK mai no ha arrencat pel boot del disc i cal `RUN "BLUESB"` escrit a mà, i els scripts de test l'escriuen massa tard) | **PLAUSIBLE** i **imperceptible**: si el build anterior també fallava, aleshores el "boot" que fèiem era el `RUN` de BASIC i el canvi l'ha trencat per un altre motiu (temps d'espera) |
| H6 | El codi del C1 a `0x6934` **sobreposa** alguna cosa del Banc 1 (p. ex. la cua de la música, el HUD o la taula de salts) i en la càrrega es barra la memòria | **A EXAMINAR**: el Banc 1 allotja `0x5000` música, `0x6000` HUD, `0x6400` habitacions, `0x6800` portes, `0x6860` taula de restauració, `0x6900` paràmetres i `0x6934` el codi nou (957 B → acaba a `0x6D0F`). Cal mirar `obj/MUSBANK.BIN` i el bloc "mus" del PAK per veure si hi ha solapaments |

---

## 6. El pas següent (el més important): test A/B

**Objectiu:** saber si el DSK actual arrenca o no, comparant amb el DSK de l'últim
commit bo.

```powershell
# 0) Conserva l'estat actual (no ho perdis!)
Copy-Item bluesb.dsk scratch\dsk_C1.dsk
Copy-Item obj\GAME.BIN scratch\GAME_C1.BIN

# 1) Aplica només el canvi del bucle (el que sembla segur) i prova
git stash push tools/build.py src/level_code.c engine/bank1_table.s   # si falla, fes-ho a mà
py -3 -u tools\build.py
py -3 -u scratch\test_cam_fix.py
#    -> si el joc arrenca: el problema és el codi del C1 / el PAK
#    -> si NO arrenca: el problema és el bucle o ja existia

# 2) Comparació directa dels dos DSK
py -3 -c "import sys; sys.path.insert(0,'tools'); from dskutil import DskPatcher; ..."
#    compara sector 0xC1 (0x00-0xFF) i les entrades del catàleg
```

Alternativa ràpida si no vols tocar el git: **desactiva només la inserció del
codi del nivell al PAK** (a `build_level_bundles`, les 2 línies que apliquen
`levelcode_src` al bloc "mus"), recompila i prova. Si el joc arrenca, el
culpat és el codi del C1.

### Altres proves útils

* `scratch/diag_boot2.py` → PC, registres i captures periòdiques.
* `scratch/diag_boot4.py` → registres + `get-stack-backtrace` + `get-memory-pages` + `disassemble`.
* `scratch/diag_cat.py` → `cat` a BASIC + OCR (per veure si el catàleg és bo).
* `scratch/diag_boot3.py` → lectura de memòria **abans** d'arrencar el joc
  (per comparar la font del sistema amb la _DATA del resident).
* Cerca del codi del joc a la RAM:
  ```python
  # recorrega 0x0000-0xFFFF amb read-memory i busca els 8 primers bytes
  # d'obj/GAME.BIN i d'obj/STARTER.BIN
  ```
* Per veure si el **boot del disc** hauria de funcionar: el codi del sector
  d'arrencada ha d'estar a `0x80-0xFF` del sector `0xC1` de la pista 0.
  `tools/dskutil.py` no l'escriu mai (el catàleg l'ocupa) ⇒ si el boot del disc
  és el camí real, cal afegir-hi un sector d'arrencada de 128 bytes (o
  confirmar que el joc s'arrenca sempre amb `RUN "BLUESB"` des de BASIC i que
  els scripts de test han d'esperar abans d'escriure la comanda).

---

## 7. Comandes del protocol remot de ZEsarUX que han estat útils

```
read-memory <addr decimal> <len>     -> hex pla
get-registers                        -> PC/SP/AF/.../IFF
get-stack-backtrace                  -> últims 16 bits de la pila
get-memory-pages                     -> ROM0 RAM1 RAM2 RAM3
disassemble <addr decimal> [n]       -> desensamblatge (adreces DECIMALS!)
save-screen <fitxer>                -> .bmp (retallar els 768x512 centrals)
get-ocr                              -> text de la pantalla
send-keys-string <delay> <text>      -> escriu tecles
send-keys-event <key> <0|1>         -> keycode 128=SPACE, 129=ENTER, 133=SHIFT
```
Constants útils: `Zrcp.KEY_SPACE=128`, `KEY_ENTER=129`, `KEY_SHIFT=133`.
Per a "comillas" cal `SHIFT` + `50` (el '2' de ZEsarUX no mapeja el `"`).
Emulador: `tools/ZEsarUX_windows-13.0/zesarux.exe --machine CPC6128 --enable-dsk
--dsk-file bluesb.dsk --enable-remoteprotocol --remoteprotocol-port 10000`.

**AceDL** (`C:\cpc\AceDL\AceDL.exe`) serveix per llegir memòria bancada i posar
breakpoints, però **no pot injectar tecles** (l'API és TCP JSON i no té
`sendKey`; l'autotype `.txt` no funciona) ⇒ per al **input** cal ZEsarUX.

---

## 8. Layout actual del Banc 1 (C1) pel que fa el codi nou

```
0x4000  codi del reproductor AKG (obj/MUSBANK.BIN, _akg_init=0x4009)
0x5000  música (MUSMAIN.BIN)
0x6000  HUD
0x6400  habitacions (ROOMS0.BIN)
0x6800  portes
0x6860  taula de restauració de les habitacions (18 posicions, tile 208 = vinil;
        el tile 159 (instrument) NO hi és → l'item secret persisteix, 1:1 DOS)
0x6900  LEVELPARM0.BIN (52 B) → `LevelParams` (src/level_params.h)
0x6934  codi del nivell (src/level_code.c + engine/bank1_table.s)  <- NOU
0x6E20  frame de l'ascensor (ELEV.BIN)                            <- previst
0x7000  buffers de fons dels ascensors (2 pàgines x 5 x 112 B)   <- previst
0x7500  dades del codi del nivell                                 <- previst
```
El PAK (`obj/L1WORLD.PAK`) és: header de 6 B (off_bank5, off_mus, off_elev) +
TILES.ZX0 + BANK5_FULL.ZX0 + MUSMAIN.ZX0 + ELEV.ZX0. El bloc "mus" es
descomprimeix a `0x5000` del Banc 1; el codi nou s'hi encosta al final.

---

## 9. Restriccions a recordar (AGENTS.md)

* Cap canvi de layout/memòria ni build llarg **sense aprovació explícita** de
  l'usuari (l'usuari es va queixar d'això: "per què et dispares a treballar
  sense que jo hagi validat?").
* La memòria del Bloc 0 és just: `_CODE 0x0100-0x386E` (14190 B) i `_DATA
  0x3900-0x3CFD` (1021 B, amb `s_lv` a 0x3CD9); el canari de pila és a 0x3D00.
  Banc C5: 16324 de 16384 B (ple). C6: 604 B lliures de codi, 40 B de dades.
  C1: ~12 KB lliures.
* `sdasz80` peta amb `ld a,(hl+1)`, `ld hl,de`, push/pop desbalancejats i amb
  fitxers **amb BOM UTF-8** (els `.s` nous s'han d'escriure sense BOM).
* Un codi bancat **no pot commutar de banc** (el seu propi codi a
  0x4000-0x7FFF desapareix); sí que pot cridar codi resident i llegir la seva
  banca i la RAM baixa.

---

## 10. Resolució Final i Causa Arrel Identificada (20/10/2026)

### 10.1 Causa Arrel del Crash a `PC=0000H`
El problema del bloqueig no era cap trencament del catàleg del disc ni del sector de boot (ja que el CPC Data format arrenca normalment amb `RUN "BLUESB"`).
La causa arrel real i determinista que provocava el crash en entrar al Nivell 1 va ser una **col·lisió de memòria al Slot 1 (`0x4000..0x7FFF`)**:
1. A l'arquitectura Amstrad CPC 6128, les configuracions del Gate Array `0xC0` i `0xC1` comparteixen la **mateixa RAM física** en el rang `0x4000..0x7FFF` (el banc base 1 / RAM de pantalla o banc de dades segons configuració).
2. A `tools/build.py`, el codi del nivell dels ascensors (`src/level_code.c` + `engine/bank1_table.s`) es compilava a `0x6934` i ocupava fins a `0x6CF7` (963 bytes).
3. A `src/main.c`, la descompressió del sub-bloc 4 del paquet de nivell (`off_elev`) es feia directament a `0x6A00` pensant que es feia sobre "Banc C0" independent de C1:
   ```c
   prev = bank_set(0xC0);
   zx0_decompress((const void*)(pak + off_elev), (void*)0x6A00);
   bank_restore(prev);
   ```
4. Com que `0x6A00` a `0xC0` apunta exactament a la mateixa RAM que a `0xC1`, la descompressió del banner de Game Over (1.360 bytes de gràfics) **sobreescrivia 760 bytes del codi d'execució dels ascensors** (`0x6934..0x6CF7`) amb patrons de bytes `03 03 03 03 03 CF...`.
5. Quan `moving_draw` cridava `call_banked(0xC1, LC1_DRAW)` (`0x6934`), l'execució saltava al mig del patró corromput a `0x6A21`, executant `03` (`INC BC`) fins a arribar a `CF` (`RST 8`). L'opcode `RST 8` saltava al vector de firmware `0x0008` (`JP 0xB98A`), que en trobar la memòria alterada acabava saltant a `PC=0000H` (`RST 0`), provocant el reinici/crash de la màquina.

### 10.2 Solució Aplicada
1. **Reubicació de GAMEOVER a zona lliure segura (`0x7600`)**:
   - S'ha mogut `GAMEOVER_PTR` a `(void*)0x7600` tant a [`src/main.c`](file:///C:/Projects/bluesb_cpc/src/main.c) com a [`tools/build.py`](file:///C:/Projects/bluesb_cpc/tools/build.py) (`LC1_GAMEOVER_BASE = 0x7600`).
   - L'espai entre el final dels buffers d'ascensors (`s_elev_dst` a `0x7514`) i `0x7600` queda net, i `0x7600..0x7B50` (1.360 B) deixa encara ~1,2 KB lliures fins a `0x8000`.
   - Afegit assert a `tools/build.py` per garantir que el codi i dades del Banc 1 mai no puguin sobrepassar `LC1_GAMEOVER_BASE`.
2. **Neteja del sub-bloc 4 de `L1WORLD.PAK`**:
   - El paquet `e_data` comprimit conté exclusivament el banner de `GAMEOVER.BIN`, ja que els frames de l'ascensor van al bloc de nivell a `0x6E20`.
3. **Manteniment del Bloc 0 resident genèric**:
   - El Bloc 0 només conté el trampolí `call_banked(0xC1, LC1_DRAW)` i `call_banked(0xC1, LC1_RESTORE)` a [`src/moving.c`](file:///C:/Projects/bluesb_cpc/src/moving.c). Tota la implementació resident específica del Nivell 1 ha estat eliminada del Bloc 0.

### 10.3 Verificació
- Validat amb el test ZEsarUX `scratch/verify_l1_boot.py`:
  - Boot net: Splash $\to$ Selecció $\to$ Mapa $\to$ Nivell 1.
  - Breakpoint a `PC=0000H` **no es dispara mai**.
  - El bucle principal de joc s'executa correctament a 50 Hz.
  - Moviment del personatge comprovat en temps real (`nat_l1_04_gameplay.png` i `nat_l1_05_moved.png`).
- Estat: **TANCAT I RESOLT**.
