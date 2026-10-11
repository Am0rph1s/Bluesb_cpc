# Blues Brothers CPC - Arquitectura Tècnica 128 KB (Doble Buffer & Bank Switching)

Aquest document detalla l'arquitectura interna del port de **Blues Brothers** per a **Amstrad CPC 6128 (128 KB)**, dissenyat des de zero per a SDCC 4.5+ en ensamblador natiu Z80 i C. Explica la distribució de memòria, la gestió dels bancs del Gate Array, el sistema de doble memòria de vídeo per maquinari (sense flicker), el funcionament del blitter d'sprites, el motor d'scroll i la guia per continuar el desenvolupament.

---

## 1. Mapa de Memòria i Filosofia de Disseny

El joc s'executa en mode bare-metal (sense firmware AMSDOS en temps de joc) aprofitant els 128 KB de RAM de l'Amstrad CPC 6128.

### 1.1 Restricció Clau de Maquinari del CPC
- El controlador de vídeo **CRTC (HD6845)** i el **Gate Array** només tenen línies d'adreces connectades físicament a la **RAM Base de 64 KB** (Blocs 0 a 3).
- La **RAM Estesa de 64 KB** (Bancs 4 a 7) **no pot ser visualitzada pel CRTC**. Només és accessible per la CPU Z80 quan es commuta dins de la finestra de banc central (`0x4000..0x7FFF`).
- **Conseqüència directa:** Els dos buffers de pantalla (Doble Buffer) **han de residir forçosament a la RAM base**, mentre que els bancs alts (4 a 7) s'utilitzen com a emmagatzematge de dades (tilesets, mapes de col·lisió, música, taules).

### 1.2 Distribució Global dels 128 KB

```
+-------------------------------------------------------------------------+
|                              RAM BASE (64 KB)                           |
+-------------------+-----------------------------------------------------+
| 0x0000 - 0x00FF   | Vectors del sistema Z80 (ISR IM 1 a 0x0038)        |
| 0x0100 - 0x3229   | Codi resident (_CODE: motor genèric + ASM, 12.585 B)|
| 0x322A - 0x369F   | Marge lliure de codi al Bloc 0 (1.143 bytes)        |
| 0x36A0 - 0x3AC6   | Variables globals i dades estàtiques (_DATA, 1.062B)|
| 0x3B40 - 0x3B41   | Canari de pila (CANARY_ADDR = 0x3B40, valor 0xA55A) |
| 0x3B42 - 0x3FFE   | PILA CPU (SP=0x3FFE; 1.336 bytes disponibles)       |
+-------------------+-----------------------------------------------------+
| 0x4000 - 0x7FFF   | Finestra de Bank Switching (Bancs 4..7 de 16 KB)   |
|                   | - En descans (0xC0): RAM Base Bloc 1               |
|                   | - Si es commuta 0xC4: Banc 4 visible (TILESET0.BIN) |
|                   | - Si es commuta 0xC5: Banc 5 visible (MAP+TRIG+B5)  |
|                   | - Si es commuta 0xC7: Banc 7 visible (Sprites/LUT)  |
+-------------------+-----------------------------------------------------+
| 0x8000 - 0xBFFF   | PÀGINA DE VRAM 'B' (anell circular de 16 KB)        |
|                   | Base CRTC MA = 0x2000 + offset de càmera            |
|                   | Scratch FDC superposat; es reutilitza després càrrega|
| 0xB800 - 0xB9FF   | Buffer FDC RAW temporal durant la càrrega           |
| 0xBA00 - 0xBA0F   | Àrea FDC temporal; alliberada abans del joc          |
| 0xBA10 - 0xBFFF   | VRAM B; memòria de vídeo durant el joc              |
+-------------------+-----------------------------------------------------+
| 0xC000 - 0xFFFF   | PÀGINA DE VRAM 'A' (anell circular de 16 KB)        |
|                   | Base CRTC MA = 0x3000 + offset de càmera            |
+-------------------+-----------------------------------------------------+

+-------------------------------------------------------------------------+
|                            RAM ESTESA (64 KB)                           |
+-------------------+-----------------------------------------------------+
| Banc 4 (0xC4)     | 0x4000..0x7FFF: TILESET0.BIN (16.384 B = 256 tiles) |
+-------------------+-----------------------------------------------------+
| Banc 5 (0xC5)     | 0x4000..0x63FF: MAP0.BIN (9.216 B = 128x72 índexs)  |
|                   | 0x6400..0x6DFF: TRIG0.BIN (2.560 B = 256×10)        |
|                   | 0x6E00..0x7DFF: BANK5.BIN (Paquet de nivell + codi  |
|                   |                 d'entitats/spans/efectes, 4.096 B)  |
+-------------------+-----------------------------------------------------+
| Banc 6 (0xC6)     | Reservat (futur: cançons AKG / dades dels enemics)   |
+-------------------+-----------------------------------------------------+
| Banc 7 (0xC7)     | 0x4000..0x70BF: PFRAMES.BIN (12.480 B; 26 frames de |
|                   |                 Jake 16x30 px Mode 0 = 480 B/frame) |
|                   | 0x70C0..0x751F: Buffers fons 5 ascensors (1.120 B)  |
|                   | 0x7520..0x76FF: Buffers fons Jake C0/80 (2x240 B)   |
|                   | 0x7700..0x78DF: Buffer gir horitzontal H-Flip (480B)|
|                   | 0x78E0..0x7A9F: ELEV.BIN (448 B; 2 frames ascensor) |
|                   | 0x7AA0..0x7E7F: EXTRA.BIN (992 B; caixa 128B +      |
|                   |                 globus 224B + paraigües 640B)       |
|                   | 0x7F00..0x7FFF: Taula LUT H-Flip Mode 0 (256 B)     |
+-------------------+-----------------------------------------------------+
```

---

## 2. Pila i Protecció del Segment `_DATA`

Un dels problemes més habituals al CPC 6128 en fer *bank switching* és la corrupció de la pila si `SP` es troba a la zona commutada (`0x4000..0x7FFF`) o si les variables de treball de la CPU desapareixen quan s'activa un banc estès.

Per garantir estabilitat absoluta:
1. **Pila (`SP`)**: A la funció `start()` (`src/main.c`) s'inicialitza immediatament a:
   ```z80
   ld sp, #0x3FFE
   ```
   Això ubica la pila al cim del **Bloc 0** (`0x0000..0x3FFF`). Com que el Bloc 0 mai es commuta, qualsevol interrupció IM 1 o crida `CALL`/`RET` és 100% segura mentre s'accedeix a la memòria estesa.
2. **Localització de `_DATA` i Canari de Pila**: Al script `tools/build.py`, s'indica a l'enllaçador:
   ```python
   LINKARGS = ["-mz80", "--no-std-crt0", "-Wl-u", "--code-loc", "0x0100", "--data-loc", "0x36A0", "-Wl-x"]
   ```
   Les dades globals se situen a `0x36A0..0x3AC6` (1.062 B), deixant 1.143 bytes de marge per a `_CODE` (`0x0100..0x3229`) i situant el canari de pila (`CANARY_ADDR` a `engine/stack_canary.h`) a `0x3B40`, just entre el final de `_DATA` i la pila (`0x3FFE`).

---

## 3. Bank Switching (Gate Array 0x7Fxx)

La selecció de banc es realitza mitjançant el Gate Array al port I/O `0x7F00`.

### Comandes Implementades a `engine/cpc_hardware.s`:
```z80
_cpc_bank_set::
    ld   bc, #0x7F00
    out  (c), a          ; A = 0xC4 (Banc 4), 0xC5 (Banc 5), etc.
    ret

_cpc_bank_restore::
    ld   bc, #0x7F00
    ld   a, #0xC0        ; 0xC0 = RAM Base estàndard (0x4000..0x7FFF torna a ser Bloc 1)
    out  (c), a
    ret
```

### Protocol de seguretat en C:
Qualsevol lectura de la memòria estesa (mapa, flags de solidesa, gràfics) segueix el patró:
```c
cpc_bank_set(0xC5);
t = MAP_PTR[(row << 7) + col];
cpc_bank_restore();
```
Com que el codi s'executa al Bloc 0 (`< 0x4000`) i les dades estan a `0x3200`, la commutació és completament transparent i atòmica.

---

## 4. Doble Buffer per Maquinari (CRTC Page Flipping)

Per eliminar definitivament el parpelleig (*sprite flicker*) i el tall de pantalla (*tearing*), s'ha implementat doble buffer per maquinari alternant entre dues pàgines de la RAM base:

| Paràmetre | Pàgina A | Pàgina B |
| :--- | :--- | :--- |
| **Adreça CPU (RAM)** | `0xC000` | `0x8000` |
| **Base CRTC MA** | `0x3000` | `0x2000` |
| **Offset MA13..MA12** | Bits 13-12 actius (`11`) | Bit 13 actiu (`10`) |
| **Variable interna ASM** | `_g_vram_base_hi = 0xC0` | `_g_vram_base_hi = 0x80` |

### Start address de càmera

El CRTC adreça la pantalla en paraules MA de 16 bits (2 bytes). Amb `R1=40`,
un caràcter de pantalla ocupa 80 bytes i un subtile vertical de 8 píxels ocupa
40 paraules MA. L'offset circular de càmera és:

```c
ma_offset = (cam_row * 40 + cam_x4) & 0x03FF;
```

L'adreça escrita a `R12/R13` és `0x2000 + ma_offset` per a la pàgina `0x8000`,
o `0x3000 + ma_offset` per a `0xC000`. El Gate Array fa wrap de l'adreça dins
de cada bloc de trama de 2 KB. `_crtc_set_display_start` a `engine/video.s`
escriu R12 i R13 amb l'adreça MA completa durant el VSYNC.

### Bucle de doble buffer a `src/main.c`

1. Es restaura Jake al backbuffer ocult amb l'origen MA que tenia quan s'hi va dibuixar.
2. Es restauren els ascensors del backbuffer; si ha canviat la càmera, es fa abans de redibuixar les vores del ring.
3. En moure la càmera, només es renderitza la columna/fila entrant al ring; no es copia la finestra sencera.
4. Es dibuixen els ascensors i després Jake al backbuffer, perquè cada sprite desi el fons correcte.
5. S'espera VSYNC i s'escriu a R12/R13 la pàgina més l'offset circular objectiu.
6. S'alterna la pàgina. La pàgina que queda oculta es posa al dia amb les tires pendents abans de tornar-la a mostrar.

Cada pàgina té el seu propi ring de tiles i buffers de restauració per a Jake i per
a cadascun dels cinc ascensors.
`cam_x4` avança una paraula MA (4 px) per pas horitzontal; dues paraules són un
subtile complet de 8 px. Verticalment l'offset avança 40 paraules per subtile.

### 4.1 Mòdul de Nivell al Banc 5 (`src/moving_bank.c` + `src/level_pkg.h`)

Per evitar que les particularitats de cada nivell creixin dins del motor resident al Bloc 0, les dades i regles del nivell s'empaqueten automàticament amb `tools/pack_level.py` a `src/level_pkg.h` i es compilen dins del mòdul bancat `src/moving_bank.c` (`BANK5.BIN`, carregat a `0x6E00` al Banc 5 `0xC5`). Com que `MAP0.BIN` (`0x4000`) i `TRIG0.BIN` (`0x6400`) viuen al mateix Banc 5, totes les consultes s'executen sense commutació de bancs:

- **Inicialització (`moving_bank_init`)**: Carrega les coordenades d'inici del jugador (`LEVEL_START_PX`, `LEVEL_START_PY`), la càmera (`LEVEL_CAM0_X4`, `LEVEL_CAM0_ROW`) i els ascensors magnètics (`s_bank_start_x`, `s_bank_start_y`, `s_bank_map_col`).
- **Actualització d'entitats i efectes de tiles (`moving_bank_update`)**:
  - Mou els ascensors magnètics (frenant en `tile_type == 10`) i el delta de plataforma.
  - Avança les 6 fases d'animació de tots els trams animats del nivell (`s_level_anim_spans`) a `MAP_MUT`.
  - Resol els efectes dels tiles del mapa sobre en Jake: escales (`tile_type == 7`), aigua/peixeres amb natació (`tile_type == 11`), recollida d'objectes (caixes `5`, globus `8`, paraigües `9`) i arrossegament de cintes (`op == 27/28`).
- **Repintat d'spans, pop del globus i reixes de primer pla (`moving_bank_conveyor`)**:
  - Repinta al backbuffer només els trams animats visibles a càmera.
  - Comprova el sostre del globus (`tile_type > 5`) i les reixes de primer pla llegint el byte 9 de `TRIG0.BIN` (`avt_num` entre 12 i 17).
- **Render d'ascensors (`src/moving.c`)**: Les rutines `moving_restore` i `moving_draw` viuen al Bloc 0 perquè commuten al Banc 7 (`0xC7`) on resideixen `ELEV.BIN` (`0x78E0`) i els buffers de fons (`0x70C0`).

---

## 5. El Blitter d'Sprites (`engine/sprite.s` i `engine/sprite_hflip.s`)

El jugador (Jake) té una mida de **16×30 píxels Mode 0** (**8 bytes d'amplada per 30 línies d'alçada** = 240 bytes d'imatge + 240 bytes de màscara = **480 bytes/frame**).

### 5.1 Format de les Dades (`PFRAMES.BIN` i `EXTRA.BIN`)
- **`PFRAMES.BIN` (12.480 B a `0x4000` del Banc 7)**: Generat per `tools/generate_cpc_jake_dos.py` a partir de `SPRITE.SQV` (DOS), conté **26 frames** orientats a la dreta:
  - `0..3`: idle i cicle de caminar.
  - `4`: salt a l'aire; `5, 9`: escala; `6..8`: ajupit i gateig.
  - `12..16`: carregar i caminar/saltar amb caixa o paraigües (`g_crate_walk`).
  - `20`: `carry_float` (DOS frame 39, braços alçats subjectant globus o paraigües).
  - `21..25`: els **5 frames autèntics de natació de DOS** (`swim_idle` 48, `swim_stroke1/2` 46–47, `swim_vert` 49, `swim_floor` 45).
- **Gir horitzontal en temps real (`engine/sprite_hflip.s`)**: En mirar a l'esquerra (`g_face == 1`), el frame es reflecteix horitzontalment cap a `0x7700` usant la taula LUT de 256 B a `0x7F00`.
- **`EXTRA.BIN` (992 B a `0x7AA0` del Banc 7)**: Conté els sprites en Mode 0 masked de la caixa (`128 B`), el globus vermell (`224 B`, 8×14) i el paraigües obert (`640 B`, 12×16).

### 5.2 Estructura Dual del Buffer de Fons
Com que tenim dues pàgines de VRAM físiques independents (`0xC000` i `0x8000`), el mòdul ASM manté buffers independents per pàgina al Banc 7 (`_s_player_bg_c0` i `_s_player_bg_80`, de 240 bytes cadascun) i a `_DATA` per a l'objecte portat (`_s_carry_bg_c0` i `_s_carry_bg_80`, de 192 bytes cadascun, capaços d'allotjar tant el globus de 8×14 com el paraigües de 12×16).

### 5.3 Adreçament sobre el ring CRTC i Algorisme del Blitter
La taula `_scr_addr_table` conté les adreces de línia base CPC; `sprite_map_line` hi suma `_g_vram_start` i conserva els bits de pàgina/trama. El camí comú no-wrap bliteja 8 bytes per línia desenrotllats amb `.rept 8` (o `.rept 12` per al paraigües), combinant màscara i desat de fons simultàniament:
```z80
    ld   a, (de)             ; Llegeix el fons existent a VRAM
    ld   (bc), a             ; Desa el fons original al buffer de restauració
    inc  bc
    and  (hl)                ; Aplica la màscara invertida
    inc  hl
    or   (hl)                ; Afegeix els píxels del sprite
    inc  hl
    ld   (de), a             ; Escriu el resultat final al backbuffer
    inc  de
```

---

## 6. Motor d'Scroll CRTC amb VRAM circular (160x160 px)

El viewport de joc mostra una finestra activa de **20x20 subtiles (160x160 píxels)**.
L'scroll es produeix quan el jugador creua els límits de la zona morta (`DEAD_L=48`, `DEAD_R=88`, `DEAD_T=32`, `DEAD_B=116`).

### 6.1 Mapping de les coordenades

El viewport ocupa 40 caràcters CRTC d'ample i 20 files de caràcter d'alt.
Cada tile de 8 px abasta dos caràcters CRTC; les coordenades es projecten a
cada pàgina circular així:

```text
world_char_x = cam_x4 + screen_char
world_col = world_char_x >> 1
tile_half_x = world_char_x & 1
MA = (world_subrow * 40 + world_char_x) & 0x03FF
byte_offset = MA * 2
CPU address = page_base + (RA * 0x0800) + byte_offset
```

Cada subtile Mode 0 ocupa 4 bytes × 8 línies de trama. `engine/tile_blit.s`
copia les 32 bytes directament als vuit bancs RA de la pàgina. `R6=20` limita
el display actiu a les 160 línies del viewport.

### 6.2 Render incremental i doble buffer

- Scroll horitzontal: cada pas de 4 px renderitza només un caràcter CRTC
  (mitja amplada de tile) per cadascuna de les 20 files visibles.
- Scroll vertical: es renderitza només la fila entrant (20 subtiles).
- En moviment diagonal es dibuixen les dues vores entrants; la cantonada queda
  coberta pels dos renders.
- La pàgina que s'acaba de mostrar queda al dia; la que passa a oculta renderitza
  les tires pendents abans del següent flip.

### 6.3 Spans de Tiles Animats (Cintes + Peixeres) i Reixes Data-Driven

- **Sistema unificat d'animació de tiles (`src/level_pkg.h`, `src/moving_bank.c`)**:
  - `tools/pack_level.py` escaneja el byte 4 (`anim_idx`) de `TRIG0.BIN` sobre `MAP0.BIN` i genera `s_level_anim_seqs[7][6]` (6 fases, MCM de les seqüències de 3 fases de les cintes i de 2 fases de l'aigua) i `s_level_anim_spans[18]`.
  - Cada 4 fotogrames (160 ms a 25 Hz), `moving_bank_update` actualitza els 18 spans a `MAP_MUT` i `moving_bank_conveyor` repinta només els que intersecten el viewport:
    - **Peixeres (aigua i vores, fila 30)**: superfície d'aigua (`131 <-> 199`), vora dreta (`149 <-> 217`) i vora esquerra (`170 <-> 247`).
    - **Cintes transportadores (files 36, 39, 42, 45)**: dreta (`248->249->250`, corrons `253->252->251`) i esquerra (`239->238->237`, corrons `240->241->242`).
- **Efecte de reixa transparent per sobre d'en Jake (`engine/sprite.s`, `src/moving_bank.c`)**:
  - Es determina dinàmicament llegint el byte 9 (`avt_num`) de `TRIG0.BIN` a la posició d'en Jake (`avt >= 12 && avt <= 17`), activant `_grate_lut` durant el blit.

---

## 7. Pipeline de Construcció (`tools/build.py`)

El sistema de compilació automàtic s'encarrega de tot el cicle d'integració en ~30 segons:
1. **Compilació Resident i Banc 5**: Compila el motor resident (`obj/GAME.BIN`), extreu els símbols globals a `obj/bank_equ.s` i compila+enllaça el paquet de nivell del Banc 5 (`obj/BANK5.BIN` a `0x6E00`).
2. **Starter reubicable (`obj/STARTER.BIN`)**: Compila el carregador inicial que s'executa a `0xC000` per carregar `GAME.BIN` via FDC raw sense trepitjar-se a si mateix.
3. **Empaquetat DSK i Taules CHS + CRC16**: Munta `BLUESB.BIN`, `GAME.BIN`, `BANK5.BIN`, `TITLE.BIN`, `TILESET0.BIN`, `MAP0.BIN`, `TRIG0.BIN`, `PFRAMES.BIN`, `EXTRA.BIN` i `ELEV.BIN` dins `bluesb.dsk`, generant automàticament `src/disk_tables.h`, `src/starter_tables.h` i `src/crt_addrs.h` amb verificació CRC16-CCITT.

---

## 8. Guia per a Futures Ampliacions

Per a qualsevol programador que vulgui continuar desenvolupament:

### Afegir Enemics o Objectes:
1. Utilitzar el mateix patró que `_sprite_blit_player`:
   - Crear una funció per a enemics que accepti coordenades i punter a frame.
   - Si es volen restaurar fons d'enemics, reservar buffers de restauració a `_DATA` (`< 0x4000`).

### Afegir Música (WYZ / Arkos Tracker 2):
1. El reproductor AKG pot ubicar-se a `_CODE` (`< 0x4000`).
2. Les cançons i taules d'instruments poden residir al **Banc 6 (`0xC6`)**.
3. A la interrupció IM 1 (`engine/isr.s`), activar el banc 6, cridar `PLY_AKG_Play()`, restaurar el banc 0xC0 i sortir amb `RETI`.

### Render Incremental de Vores:
1. `render_column` i `render_row` ja llegeixen índexs del Banc 5 i dibuixen les
   tires entrants amb els gràfics del Banc 4.
2. Les properes optimitzacions de vídeo s'han de validar amb perfil de CPU a
   ZEsarUX, especialment durant scroll diagonal i restauració d'Sprites.
