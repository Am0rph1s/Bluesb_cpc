# Arquitectura Single Buffer (`single-buffer-split`) — Blues Brothers CPC

> **Branca**: `draw-opt-enemy-late` · **Data**: 18/11/2026
> **Estat**: Build estable i verificat a ZEsarUX: **25,0 fps** amb scroll, HUD acabat a la línia **168**, Jake alt (`dsy=58`) sòlid, caminada de 25 s sense crash, `smoke_test` i `check_c6_flag` OK.

---

## 1. Objectiu i Canvi d'Arquitectura

Anteriorment el motor utilitzava **doble buffer per maquinari** (`0xC000` / `0x8000`) commutant `CRTC R12` entre `0x3000` i `0x2000`. Això consumia **tota la RAM 2 (`0x8000..0xBFFF`, 16 KB)** com a segona pantalla i obligava a mantenir dues còpies sincronitzades de totes les restauracions, HUD i scroll.

La branca `single-buffer-split` passa a **Single Buffer a `0xC000..0xFFFF`** (anell circular CRTC de `1024` paraules = `25,6` files de `40` caràcters, `MA = 0x3000..0x33FF`), alliberant **16 KB complets a RAM 2 (`0x8000..0xBFFF`)** per a codi resident ràpid, buffer fix del HUD i cel·les d'enemics.

*(Nota sobre el nom de la branca: es va avaluar un split per maquinari amb `CRTC R4/R6/R7` per fixar el HUD, però es va descartar perquè la doble `VSYNC` per frame desincronitzava el CRTC a ZEsarUX; en lloc d'això, el HUD es copia cada frame d'scroll a `new_ma + 800..879` des d'un buffer pre-renderitzat a RAM 2).*

---

## 2. Canvis al Mapeig de Memòria i Bancs (CPC 6128 — 128 KB)

### 2.1 Resum de diferències respecte a l'arquitectura anterior

| Zona | Abans (Doble Buffer) | Ara (`single-buffer-split`) |
| :--- | :--- | :--- |
| **RAM 0 (`0x0000..0x3FFF`)** | `_CODE` `0x0100..0x359A`, `_DATA` `0x3600`, canari `0x3Bxx` | **`_CODE` `0x0100..0x38F9` (marge `263 B` fins a `_DATA`)**, **`_DATA` `0x3A00..0x3B29` (`297 B`)**, **`CANARY_ADDR = 0x3C40`**, pila útil ~`1.237 B` |
| **RAM 2 (`0x8000..0xBFFF`)** | Pàgina VRAM 1 (`0x8000`) durant el joc; scratch FDC en càrrega | **Alliberada en joc**: cel·les d'enemics + cache H-flip (`0x8000..0xB5FF`), buffer fix del HUD (`0x8760`/`0x87B0` × 8 scanlines), `ENEMY_BBOX_ADDR` (`0xB700`), **codi resident ràpid `ram2_code.s` (`0xB800..0xBBDB`, `988 B`)** i **dades fredes als gaps** (§2.3). En càrrega de nivells segueix fent de scratch FDC (`FDC.BIN` a `0x8000..0x8311`, càrrega `.PAK` a `0x8320..0xB7FF`). |
| **RAM 3 (`0xC000..0xFFFF`)** | Pàgina VRAM 0 (`0xC000`) | **Única pàgina VRAM (`0xC000`)** en anell circular (`0x3000..0x33FF`) |
| **Banc `C1` (RAM 1)** | Player AKG + `hud_bank` + cançó + `LVLCHS` + `FDC.BIN` mestre | Mateix esquema, i a **`C1:0x6030`** s'hi emmagatzema la imatge de `RAM2.BIN` (`engine/ram2_code.s`), que es copia a `0xB800` al carregar el primer nivell. **Atenció: el primer pak de nivell sobreescriu `C1:0x6030`; la còpia no es pot repetir des de C1.** |
| **Banc `C6` (RAM 6)** | Cel·les comprimides + cache H-flip limitada dins `C6` | Les **16 cel·les descomprimides i els 5 slots H-flip** passen a RAM 2 (`0x8000..0xB5FF`), alliberant pressió dins `C6` |
| **Bancs `C4`, `C5`, `C7`** | Tileset/FRONT (`C4`), món+TRIG+`moving_bank` (`C5`), frames jugador + buffers `0x7E00` (`C7`) | Sense canvis estructurals de banc (`C4`, `C5`, `C7` mantenen el seu mapa) |

### 2.2 Detall d'adreces a RAM 2 (`0x8000..0xBFFF`) durant el joc

La distribució a RAM 2 aprofita l'entrellaçat de 8 blocs de `2 KB` del CPC (`+0x0000, +0x0800, ..., +0x3800`) perquè les cel·les d'enemics (`512 B` cadascuna) no trepitgin les columnes del HUD ni el codi resident:

- **`0x8000..0xB5FF` (blocs de 2 KB, primers `1.536 B` de cada bloc)**:
  - **16 cel·les d'enemics** (`512 B` cadascuna = `8 KB`), adreçades per `s_cell_hi[16]` a [`src/enemy.c`](../src/enemy.c):
    `0x80, 0x82, 0x84, 0x88, 0x8A, 0x8C, 0x90, 0x92, 0x94, 0x98, 0x9A, 0x9C, 0xA0, 0xA2, 0xA4, 0xA8`.
  - **5 slots de memòria cau H-flip** (`512 B` cadascun = `2,5 KB`), adreçats per `s_cache_hi[5]`:
    `0xAA, 0xAC, 0xB0, 0xB2, 0xB4`.
- **`0x8760..0x87FF` (+ `+0x0800..+0x3800`)**:
  - **Buffer fix del HUD** (`0x8760` fila 20, `0x87B0` fila 21, `160 B × 8 línies = 1.280 B`), renderitzat per [`src/hud_bank.c`](../src/hud_bank.c) i copiat a VRAM pel codi resident `_ram2_hud_copy`.
- **`0xB700`**: `ENEMY_BBOX_ADDR` (`src/enemy.c`).
- **`0xB800..0xBBFF` (`1.024 B`)**: **Codi resident permanent** ([`engine/ram2_code.s`](../engine/ram2_code.s)), sempre visible en qualsevol configuració de bancs (`C0/C4/C5/C6/C7`). Exporta:
  - `_ring_address`
  - `_moving_blit_box` / `_moving_restore_box`
  - `_ram2_hud_copy`
  - `_ram2_en2_clip`
- **`0xBC00..0xBDFF` (`512 B`)**: `ASSETS_FDC_BUF` (buffer de sector FDC). **Durant el joc és lliure** i s'hi allotja la caché de columna:
  - `0xBC00..0xBC9F` (160 B): files 0..9 de la columna (10 tiles × 16 B).
  - `0xBD00..0xBD9F` (160 B): files 10..19.
  - El FDC el sobreescriu durant les càrregues; la caché s'invalida a `repaint_screen()` i després de cada càrrega de nivell/sala.
- **`0xBE00..0xBE0F`**: work FDC; **`0xBE10..0xBE61`**: dades fredes de càrrega.

### 2.3 Dades fredes reubicades als gaps de RAM 2 (18/11/2026)

Els gaps `0xX600..0xX75F` (352 B per bloc) allotgen estat fred que abans era a
`_DATA` resident. Com que el pak de nivell (`0x8320..0xB7FF`) els trepitja, tot
això s'ha de reinicialitzar **després** de la càrrega:

| Adreça | Dada | Mida | Reinicialització |
|---|---|---:|---|
| `0x8600` | `s_carry_bg_c0` | 320 B | scratch; s'escriu abans de cada blit |
| `0x8E80` | `s_lv` | 93 B | `level_params_load()` |
| `0x9600` | `g_mag_elevators` | 80 B | `moving_init()` (ldir 128 B) |
| `0x9E00` | `s_mn_*` | 19 B | `main()` |
| `0x9E20` | `s_cd_*` | 21 B | `carry_draw()` |
| `0x9E40` | `s_rep_*` | 13 B | `s_rep_n = 0` post-load |
| `0x9E50` | `s_carry_drawn` + span/rows/dst | 8 B | post-load / carry |
| `0x9E58` | caché de columna: valid/x4/row/col | 6 B | invalidada a cada càrrega/repaint |
| `0xBE10` | `s_chs_buf` | 56 B | durant la càrrega (fora del pak) |
| `0xBE48` | `s_lvl_desc` | 8 B | durant la càrrega |
| `0xBE50` | `s_lp_*` | 17 B | `load_package()` |

### 2.4 Límit dels `.PAK`

El payload que el FDC escriu a memòria va de `0x8320` fins a `0xB800`:
**13.536 B**. L'antic límit de 14.208 B (o 14.560 B d'scratch) trepitjava
`_ring_address`/`_moving_blit_box` a `0xB800`. Vegeu `docs/MEMORY_MAP.md` §4.

---

## 3. Implementació del Motor Single Buffer i Estabilitat Visual

### 3.1 Sincronització amb el feix CRTC (`VBLANK`)
- **Inici del frame a `g_irq_phase == 5`** ([`src/main.c`](../src/main.c#L1443-L1446)): després d'esperar el ritme de `10` ticks (`300 Hz / 10 = 30 Hz` màxim, o `25 Hz` efectiu per frame de joc), el bucle principal espera `g_irq_phase < 5` (línia `~206`, al marge inferior, `~6,8 ms` abans de `VCC = 0` a la línia `312`).
- **`crtc_set_display_start` a la primera línia de `render_frame()`** ([`src/main.c`](../src/main.c#L969-L971)): el CRTC 6845 fa *latch* de `R12/R13` a `VCC = 0` (línia `312`). Escriure `R12/R13` a l'inici del `VBLANK` garanteix que tot el frame mostri la nova posició de càmera sense desdoblaments entre camp 1 i camp 2.
- **`DEAD_R = 89`**: ajust de la zona morta dreta per evitar passos horitzontals de 2 bytes (`4 px`) en càmera.

### 3.2 Dibuix atòmic de sprites i casos especials
- **Jake i objectes portats unificats** (`restore_fg_sprites` / `draw_fg_sprites` a [`src/main.c`](../src/main.c)):
  - Caixes (`carry_draw` / `carry_restore`), globus (`sprite_blit_balloon`) i paraigües (`sprite_blit_umbrella`) s'han unificat dins la mateixa passada atòmica que Jake (`keep_jake` / `early_jake` / `mid_jake` / `late_jake`).
  - `no_ov` comprova `!s_carry_state` (en lloc de `!s_carry_kind`) i `keep_jake` fa seguiment de `s_prev_jcarry`, evitant parpelleig quan Jake porta una caixa o un globus.
- **Enemics atòmics i proximitat vertical** ([`src/enemy.c`](../src/enemy.c)):
  - `en2_update_vis()` amplia el càlcul de proximitat `g_jake_en_near` en vertical (`(u16)(g_en_y - g_en_jake_y + 58) < 104`) i `en2_update()` hi afegeix la comprovació vertical de projectils (`(u16)((s_proj.y8 >> 3) - g_en_jake_y + 32) < 76`).
  - Quan no hi ha solapament amb Jake, cada enemic fa el seu esborrat/dibuix de forma atòmica per reduir el parpelleig a pantalla única.
- **Reixa i cintes transportadores** ([`src/main.c`](../src/main.c), [`src/moving_bank.c`](../src/moving_bank.c)):
  - `g_grate_enable = 1` s'activa a `moving_bank_update()` per a les reixes de nivell 0 (files `39..41` i `45..47`), i `moving_draw_conveyor_tiles()` s'executa també amb globus (`s_carry_kind == 2`) o reixa activa.

### 3.3 Ordre de renderitzat dins `render_frame()` per eliminar tremolors al HUD

Com que l'àrea de joc i el HUD comparteixen l'anell `0xC000`, en desplaçar
`R12/R13` el HUD antic queda desplaçat `dx` columnes / `dy` files fins que es
reescriu. L'ordre final és:

- **Scroll horitzontal pur (`dx != 0`, `dy == 0`)**:
  1. S'ometen els restores inicials d'enemics/movers (`defer_enemy = 1`).
  2. `sync_backbuffer()`: copia la columna 39 (o 0) des de la caché; comença a
     la línia `225`, abans del camp nou (`VCC=0` a `312`).
  3. `restore_fg_sprites()` (Jake, línia `277`) i `draw_fg_sprites()` (línia
     `16` del camp nou).
  4. `hud_render(0, 1)` a la línia `88`; acaba a la línia **`168`**, abans que
     el feix arribi a la fila 20 (`160`) / 21 (`168`).
  5. `restore_world_scroll(wmode)` diferit a la línia `169`:
     `enemy_restore(2)` + `moving_restore()` + `moving_popup_restore()`.
  6. `moving_draw()` i `enemy_restore(0)` + `enemy_draw(0)` (`234..265`).
  7. `pre_render_next_column()`: pre-renderitza a RAM 2 la columna del frame
     següent (fora del camp visible).
- **Scroll vertical (`dy != 0`)**: es manté l'ordre original (HUD abans de
  `sync`/`early_jake`, `render_rows_edge` per `dy < 0`) perquè el HUD no es
  retrasi a la part baixa. La caché de columna s'invalida quan `dy != 0`.

### 3.4 Caché de columna: byte copy estable, LDI descartat

La caché viu a `0xBC00`/`0xBD00` (buffer FDC lliure en joc) i el tag a
`0x9E58..0x9E5D`. La còpia a VRAM es fa **byte a byte** (`ccb_tile$` a
[`engine/tile_blit.s`](../engine/tile_blit.s)).

La variant amb `LDI` (2 `ldi` + 2 `dec e` per línia, 40 T/línia) és més ràpida
(46 línies de sync en comptes de 50), però a ZEsarUX va provocar un salt
salvatge/reset a `px8≈1732` durant una caminada llarga. La còpia byte a byte
(48 T/línia) és la versió **estable**; no reintroduir `LDI` sense repetir la
prova de caminada de 25 s.

---

## 4. Verificació Realitzada (18/11/2026)

- `py -3 tools/build.py`:
  - `_CODE : 0x0100..0x38F9` (**263 B** de marge fins a `_DATA` a `0x3A00`).
  - `_DATA : 0x3A00..0x3B29` (**297 B**); pila útil ~`1.237 B`.
  - `GAME.BIN` **14.899 B**; DSK generat amb `STARTER-JUMP-OK`.
- `py -3 tools/smoke_test.py --dsk-only`: **RESULTAT: OK**; `game 30 sectors, 14899 B, CRC 0xA561`.
- `py -3 tools/smoke_test.py`: **RESULTAT: OK**; `magic=0xB0`, `px8=192`, `py8=8848` (adreces `s_px8=0x3AE2`, `s_py8=0x3AE4`).
- `py -3 tools/check_c6_flag.py` (L3, amb `0xC3` forçat a `C6:0x5A00`):
  `magic=0xB0`, `canari=55aa55aa55aa55aa55aa55aa55aa55aa` → **OK**.
- **Timeline ZEsarUX** (L1, `dx=1`, `dy=0`, Jake `dsy=114`):

  | Fase | Línia inicial | Línia final |
  |---|---:|---:|
  | `sync_backbuffer` | 225 | — |
  | `copy_column_from_buf` | 227 | 277 |
  | `restore_fg_sprites` | 277 | 16 (camp nou) |
  | `draw_fg_sprites` | 16 | 88 |
  | `hud_render` | 88 | **168** |
  | `restore_world_scroll` (diferit) | 169 | 218 |
  | `enemy_draw` | 234 | 265 |
  | `pre_render_next_column` | 265 | fora del camp visible |

- **FPS amb scroll**: `g_ticks` delta `12` a 300 Hz → **25,0 fps** (constant).
- **Jake alt natural**: salt amb `UP` (sense teleport), àpex `py8=8400`,
  `dsy=58`; captura `jump_06` neta (Jake sencer, HUD net, sense cisalla).
- **Scroll horitzontal**: captura `scroll_clean` neta; primera columna correcta.
- **Vertical amunt segur** (teleport de validació): `cam_row 122→120`,
  `dy=-2`, `dsy=36`; `render_row` a SL `224` i `62` (~150 línies/fila), frame
  estable a 25 fps; captura neta (l'estat artificial no mostra Jake, però no
  hi ha cisalla ni corrupció).
- **Jake alt amb càmera horitzontal** (teleport `py8=8472`): `dsy=67`, captura
  `highy` neta.
- **Enemics**: diff de pantalla `old_enemies` (camp de transició) vs
  `clean_field` (camp net) = **0 píxels** a tot el playfield i al HUD en el
  frame mesurat; `new_enemies` vs `clean_field` també 0. Risc residual: el
  restore diferit pot mostrar l'enemic un camp tard si es mou, no observat.
- **Caixa (carry)**: `s_carry_kind=1` detectat a `px8=1462`; captura
  `carry_hud` neta (Jake amb caixa, HUD net).
- **Globus/paraigua (pickup natural)**: el TRIG compacte té **5 B per
  tile** (`type, flags|data5<<2, op, b6, avt`), no 4. Amb aquesta mida, L1 té
  paraigües (tipus 9, tile 153) a `(row,col) = (8,10), (14,12), (19,17)` i
  globus (tipus 8, tile 155) a `(35,32)` i `(55,23..25)`. Col·locant el
  jugador sobre el tile (`col=(col*8-4)*8`, `py8=(row*16-30)*8`, `on_ground=1`),
  el pickup és automàtic: `s_carry_kind` passa a **8** a `(8,10)` i a **2**
  a `(35,32)`; captures `natural_umbrella_08_10` i `natural_balloon_35_32`.
  Les proves anteriors fallaven perquè escanejaven el TRIG amb stride 4.
- **Ascensor**: teleport a l'ascensor 0 (`center_x=760`, `y=384`); el jugador
  hi puja i la càmera segueix `cam_row 28→30` mentre l'ascensor baixa
  (`y 384→400`); captura `elevator_ride` neta. La banda lila és art del nivell
  (cinta), no una cisalla.
- **Escala type 7**: provada a `(15,101)`; el jugador puja/baixa però L1 no té
  una escala llarga (el tile 7 és un pas curt). El recorregut vertical natural
  de L1 és l'ascensor; el codi de climb no s'ha modificat.
- **Sala L1**: porta `(36,70)→(19,82)`; `in_room=1`, càmera `0,148`; sortida
  `(19,82)→(36,70)`; `in_room=0`, càmera `52,124`; captura `room_exit` neta.
  La sala blanca és idèntica al baseline `single-buffer-split`: és art del
  nivell, no una regressió de la caché.
- **Enemics en moviment**: `s_enemies[2]` (C6:`0x5018`) passa de `x=600` a
  `632` i `s_enemies[7]` (`0x5054`) de `688` a `664`. La instrumentació
  correcta és `g_en_clip_x0/x1/y0/y1` (resident, `0x3AA3..0x3AA9`) llegida al
  breakpoint de `moving_blit_box` (`0xB835`, RAM 2 sempre mapejada): dóna el
  bbox exacte de cada sprite. Als frames mesurats el desplaçament de pantalla
  va ser de **0..3 px**; dins del rectangle del sprite el diff
  transició→final és **0** quan la posició de pantalla no canvia. El
  `defer_enemy` deixa el sprite del frame anterior fins a la línia 169, o sigui
  que un enemic mòbil per sobre d'aquesta línia pot mostrar un contorn de
  **1..3 px** durant un frame. És el **risc residual** màxim; no s'ha
  observat cap parpelleig ni corrupció, i no afecta el HUD ni el camp.
- **L2**: `check_c6_flag.py` carrega el nivell 2 (`magic=0xB0`, canari OK).
- **Transició completa L1→L2**: forçant `g_level_complete=1` a L1, la
  celebració de 50 frames i el front/mapa carreguen el paquet de L2
  (`s_lv.room_count=0`, `row0=255`) al cap de ~34,5 s; `l2_settled` mostra la
  fàbrica de L2, sense crash. Cal mantenir premut `2` i prémer SPACE per
  passar el front/mapa.
- **Estabilitat**: caminada real de 25 s (px8 de 192 a ~5.952) sense reset ni
  salt a VRAM; la variant `LDI` fallava a `px8≈1732` (vegeu §3.4).
- **Doble buffer `master`** (mesura de comparació): ~15-17 fps amb scroll
  (delta `g_ticks` 17-20); estable, però més lent que el single buffer.

Pendent: res funcional. Risc residual documentat: el restore diferit
d'enemics pot mostrar un contorn d'1..3 px en un enemic mòbil per sobre de la
línia 169 durant un sol frame. La resta de verificacions (pickup natural de
globus/paraigua, caixa, ascensor, sala L1, transició completa L1→L2,
estabilitat de 25 s i 25 fps) estan cobertes.
