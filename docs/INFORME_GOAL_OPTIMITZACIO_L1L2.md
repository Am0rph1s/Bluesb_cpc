# Informe del goal: optimitzacio FPS L1/L2 (P1b i P3)

Data: 30/10/2026
Branca: `fix-c1-l3-unlock`
Commits: `e33a859`, `d71fd72`, `364a480`, `3a6d1ec`

---

## 1. Que es va demanar

Continuar l'execucio del pla `docs/pla_optimitzacio_fps_l1l2.md` **sense aturar-se**
fins a tenir resolts tots els passos. En concret, quan va comencar aquest goal ja
estaven fets P4.2, P2.1, P1a, P2.2 i la verificacio de P4.1, i faltaven:

* **P1b** - substituir el repintat tile a tile del conveyor per un blit de *span*
  amb una sola commutacio al banc `0xC4`.
* **P3** - permetre que dos enemics girats amb celes diferents convisquin sense
  trepitjar-se (el pla proposava un segon buffer de flip a `0x4E00`).

Requisits permanents del projecte: fidelitat 1:1 al DOS, res d'inventar
mecaniques, verificar amb ZEsarUX i mesurar amb `docs/perf/perf_monitor.py`.

---

## 2. Que s'ha fet

### 2.1 Passos que ja venien fets (commit `e33a859`)

| Pas | Canvi | Efecte mesurat (L1, inici) |
|---|---|---|
| **P4.2** | llindar de pacing VSYNC `< 2` -> `< 7` ticks (`g_ticks` va a 300 Hz) | el joc deixa de poder anar a 50 fps a les sales |
| **P2.1** | `get_tile_at` + `get_trig_byte` fusionats amb una sola commutacio a `0xC5` | menys commutacions per consulta de tile/TRIG |
| **P1a** | `s_anim_pos[16]` (posicio per sequencia) + salt del repintat si el tile no canvia | quiet 13,0 -> **16,6 fps** |
| **P2.2** | `en2_update`: `tt_pf`/`tt_pb` llegits un cop, short-circuit i `c2row != brow` | menys consultes cares per enemic i frame |
| **P4.1** | verificat: a C1 el rang `0xC000-0xFFFF` es sempre el banc 7 | **no cal canvi** |

### 2.2 P3 - flip multiple (commit `d71fd72`)

El pla proposava dos buffers de flip. S'ha implementat una solucio **millor**:

* `en2_cell(cell, flip)` desa les celes girades a la **mateixa cache ZX0** del
  banc C6 amb la clau `cela | 0x80`.
* Consequencies: una cela girada es descomprimeix i gira **un sol cop**; els
  frames seguents la troben a la cache; dos enemics girats amb celes diferents
  no es trepitgen; **desapareix** `s_flip_buffer` (512 B de `_DATA`).
* Cache de **4 slots** (`0x5000..0x57FF`), el projectil tambe la fa servir.
* S'elimina `_s_flip_lut` (256 B de `_DATA` que no tenien cap referencia).
* `ENEMY_BASE` baixa de `0x5C00` a `0x5A00`: el banc C6 passa de 16 B a
  **1.804 B lliures** de codi.

### 2.3 P1b - blit de span (commit `364a480`)

* `render_tile_span(tile, col0, col1, row, cam_x4, cam_row)`: pinta un span
  sencer (4-6 columnes) amb **una sola** commutacio al banc 4; el punter al tile
  es calcula un sol cop i el MA s'incrementa de 40 per subfila en lloc de
  multiplicar per 40 a cada caracter.
* `render_tile_world()` queda com a envolcall per als repintats puntuals
  (`main.c`, `render_room`).
* `moving_bank_conveyor` crida el span un sol cop.
* Cost: +186 B de resident -> `_DATA` de `0x38F0` a `0x39A0` i canari de pila de
  `0x3D60` a `0x3E10`.

### 2.4 Verificacio feta

* `py -3 tools/build.py` sense FATAL als 3 nivells; DSK generat.
* `py -3 tools/smoke_test.py --dsk-only` -> `RESULTAT: OK`
  (`game 32 sectors, 15632 B, CRC 0x3936`).
* ZEsarUX: arrencada, intro, SPACE fins a `s_lv` magic `0xB0`, L1 jugable,
  caminar/d salts durant 20 s sense crash, canari de pila `0x55AA` x8 intacte.
* Captura amb el monitor oficial: `docs/perf/perf_monitor.py` (340 mostres).

---

## 3. Problemes trobats

### 3.1 El bloc `0x4E00..0x4FFF` que el pla donava per lliure NO ho es

El pla afirmava que `0x4E00..0x4FFF` era 100% lliure perque `EN_RESTORE` feia
"com a molt 725 B". Al build real, **L1 te 917 B** de taula de restauracio a
`0x4B00`, o sigui que arriba a `0x4E95`. En posar-hi la LUT de flip:

* `en2_init_lut` trepitjava 150 B de la taula,
* `restore_level_tiles` llegia escombraries i les escrivia com a tiles dins el
  **codi del banc C5** (`0x6801+`),
* el joc queia a Locomotive BASIC al cap d'un parell de segons.

Solucio: la LUT de flip es queda a `0x7900..0x79FF` (lliure: el codi acaba a
`0x76F4`) i `build.py` ara avorta si `_CODE` arriba a `0x7900`.

### 3.2 `raw_len` fix a `build.py` (el bug que va costar mes temps)

La imatge del banc C6 es muntava amb `raw_len = 0x1C00` **hardcoded**, de manera
que el codi s'incrustava sempre a `0x5C00` encara que `ENEMY_BASE` fos `0x5A00`.
El resident cridava els slots a `0x5A00` i saltava dins les dades de la imatge:
`SP` acabat a `0xBFF8`, PC a la ROM i caiguda a BASIC.

Solucio: `raw_len = ENEMY_BASE - 0x4000` i les comprovacions de cache i LUT
derivades d'`ENEMY_BASE`.

**Llico**: els dos bugs es manifestaven igual (BASIC al cap d'1-2 s) i em van fer
culpar la pila i revertir P1b injustament. Calia mesurar la pila de veritat
(watermark) abans de treure conclusions.

### 3.3 La pila: fals desbordament

Amb `_DATA` a `0x39A0` la pila queda en **494 B**. El primer intent de mesurar
l'us de pila omplia `0x3E10..0x3FFD` amb `0xCC` **incloent-hi la pila viva**, i
el joc petava: la mesura era invalida i el "crash" tambe.

Metode correcte: llegir `SP`, omplir **nomes** la zona lliure (canari .. `SP-64`)
i jugar 20 s. Resultat: **us real maxim 100 B**. Els 494 B son de sobres.

### 3.4 Altres entrebancs de metode

* **ZEsarUX "penjat"**: si l'emulador queda en pausa, `get-registers` retorna
  sempre el mateix PC i sembla un bucle infinit. Cal reiniciar l'emulador despres
  de cada DSK i comprovar que el PC es mou.
* **Adreces**: qualsevol moviment de `_DATA` desplac'a tots els simbols; sempre
  s'han de resoldre des de `obj/bluesb.map` (mai constants a ma).
* **Build de 2 passades**: quan canvien adreces del resident, `build.py`
  regenera `crt_addrs.h`/`disk_tables.h`/`starter_tables.h`, detecta el canvi i
  refa tot el build. Son ~50 min per build en lloc de ~25.
* **Comptador d'fps**: `s_conveyor_phase` es de 8 bits i fa wrap; en creuar una
  zona dona pics falsos (fins a 184 fps). Per aixo s'usa la **mediana**.

---

## 4. Analisi de rendiment

### 4.1 Punt de partida (informe `PERF_REPORT_L1L2.md`, 4.320 mostres / 1.800 s)

| Metrica | Valor |
|---|---|
| FPS mitja / mediana | 12,2 / **10,5** |
| p10 / p25 / p75 / p90 | 6,3 / 8,4 / 12,6 / 14,7 |
| L1 (n=2.027) | mitjana 12,4, mediana **12,5**, p10 8,4, p90 16,5 |
| L2 (n=1.506) | mitjana 8,6, mediana **8,4**, p10 6,3, p90 12,5 |
| Quiet (n=2.177) | mediana 10,4 |
| Scroll (n=1.356) | mediana 10,5 |

Perfil de CPU per banc: **C5 42%**, C0 22% (ISR musica + HUD + espera VSYNC),
**C6 16%** (enemics), **C7 16%** (blits del Jake).
Cos de frame ~**85 ms** enfront d'un pressupost de **40 ms** per anar a 25 fps.

### 4.2 Despres dels passos

| Build | quiet | caminant | caminant2 | quiet2 |
|---|---|---|---|---|
| Baseline (abans del pla) | 13,0 | 11,0 | 11,0 | - |
| `e33a859` P4.2+P2.1+P1a+P2.2 | **16,6** | 10,5 | 11,0 | - |
| `d71fd72` + P3 | 12,4 | 10,5 | 9,3 | 16,6 |
| `364a480` + P1b | 12,5 | 10,5 | 9,3 | 16,6 |

Captura final amb el monitor oficial (`scratch/perf.log`, 130 s, 340 mostres):

| Tram | n | mediana | min | max |
|---|---|---|---|---|
| quiet (5-22 s) | 45 | **16,8 fps** | 14,7 | 18,5 |
| caminant (30-70 s) | 105 | **10,4 fps** | 8,3 | 184* |
| quiet2 (100-128 s) | 73 | **16,7 fps** | 14,6 | 16,8 |

\* pic fals pel wrap del comptador de fase.

### 4.3 Per que P3 i P1b no mouen el numero

El frame esta **lligat a VSYNC**: nomes es poden donar 50/N fps. Les xifres
observades son exactament 50/3 = **16,7** i 50/5 = **10,0**, o sigui que el joc
salta de 3 a 5 VSYNCs segons la zona. Qualsevol optimitzacio mes petita que el
salt d'un VSYNC (20 ms) **no es pot veure** al comptador.

Magnituds:
* `render_tile_fast` (blit d'un caracter CRTC de 4x8) ~2.400 T-states
  (estimacio del pla d'optimitzacio).
  Repintar una columna de tile = 2-4 caracters = ~9.600 T-states.
* P1b estalvia 4-6 commutacions de banc per span (~60 T-states cadascuna) enfront
  d'aquests ~9.600 T-states per columna: **~0,6%** del cost del span.
* P3 estalvia el re-flip de 512 B per enemic girat i frame (i les
  descompressons repetides), pero els enemics nomes son el 16% del frame.

Per tant: **P1a (que elimina repintats sencers) es l'unic pas que ha mogut la
xifra** en aquesta mesura (quiet 13,0 -> 16,6); P4.2 no apuja el sostre, sino que
evita que el joc s'acceleri a les sales quan el frame baixa de 20 ms. P2.1/P2.2/
P3/P1b redueixen treball real pero no creuen cap frontera de VSYNC.

### 4.4 Que caldria per arribar a 25 fps

Cal baixar el cos de frame de ~85 ms a **< 40 ms** (-45 ms). Amb el perfil actual:

| Banc | % | ~ms/frame | Que hi ha |
|---|---|---|---|
| C5 | 42% | ~36 | `anim_tick_c5`, `moving_bank_update`, `find_landing`, conveyor |
| C0 | 22% | ~19 | ISR musica (50 Hz), HUD, espera VSYNC |
| C6 | 16% | ~14 | IA + dibuix d'enemics |
| C7 | 16% | ~14 | blits del Jake / objectes |

Les palanques amb mes recorregut, per ordre:

1. **Cost per caracter del blit** (el que domina el repintat): el render pinta
   caracters de 4x8 px amb 8 copies de 2 bytes. Un blit de 8 bytes per caracter
   (o 16 px d'una tirada) reduiria el cost del scroll a la meitat.
2. **C5 (42%)**: treure del cami per frame el que sigui possible
   (`find_landing`, comprovacions de tiles) o cachejar-les.
3. **C0 (22%)**: el player de musica corre a 50 Hz dins la ISR; si el frame baixa
   a 25 fps es pot baixar el tick a 25 Hz (mateixa musica, meitat de cost).
4. **C6 (16%)**: dibuix d'enemics (clipping per enemic i frame).

### 4.5 Estat de memoria (despres del goal)

| Zona | Us | Lliure |
|---|---|---|
| Resident `_CODE` | `0x0100..0x3985` (14.469 B) | **27 B** |
| Resident `_DATA` | `0x39A0..0x3E10` (1.126 B) | - |
| Pila | 494 B | us real mesurat: **100 B** |
| Banc C1 | ~10.000 B | 6.400 B |
| Banc C4 | 13.696-15.296 B | 1.088-2.688 B |
| Banc C5 | 16.384 B | **0 B** (ple) |
| Banc C6 | 14.580 B | **1.804 B** |

---

## 5. Que queda obert

* **L2 i L3**: es compilen i empaqueten be (i el `smoke_test` valida tots els
  fitxers del DSK), pero **no s'han jugat** en aquest goal. L2 es el nivell lent
  (mediana 8,4) i es on P1a/P1b haurien de notar-se mes (54 spans, 12 sequencies).
* **P1b**: es mante perque fa menys treball real i no empitjora res, pero el seu
  guany no es mesurable i consumeix els ultims 27 B de resident: es el **primer
  candidat a treure** si cal espai.
* **Incidencies visuals pendents** (de reports anteriors, no tocades aqui):
  la caixa no queda tapada per la reixa quan la portes, el rectangle blau
  intermitent (2 tiles del 211 en un sol buffer) i el "rocker del passadis".
* **Propera fita de rendiment**: atacar el cost per caracter del blit i el banc
  C5 (seccio 4.4), que es l'unic que pot creuar la frontera dels 40 ms.

---

## 6. Com reproduir les mesures

```
py -3 tools/build.py
py -3 tools/smoke_test.py --dsk-only
# reiniciar ZEsarUX amb el DSK i el port ZRCP 10000
py -3 docs/perf/perf_monitor.py        # 1.800 s -> scratch/perf.log
py -3 scratch/verify_p3.py             # arrencada + fps + canari + captura
py -3 scratch/stack_wm.py              # watermark d'us de pila
```
