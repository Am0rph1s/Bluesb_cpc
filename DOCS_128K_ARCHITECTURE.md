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
| 0x0100 - 0x29D4   | Codi executable (_CODE: C + ASM + taules constants) |
| 0x3200 - 0x39FC   | Variables globals i dades estàtiques (_DATA)        |
| 0x39FD - 0x3FFE   | PILA CPU (SP=0x3FFE; ~1,5 KB disponibles)            |
+-------------------+-----------------------------------------------------+
| 0x4000 - 0x7FFF   | Finestra de Bank Switching (Bancs 4..7 de 16 KB)   |
|                   | - En descans (0xC0): RAM Base Bloc 1               |
|                   | - Si es commuta 0xC4: Banc 4 visible (TILESET)      |
|                   | - Si es commuta 0xC5: Banc 5 visible (MAP + TRIG)   |
|                   | - Si es commuta 0xC7: Banc 7 visible (frames Jake)   |
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
| Banc 4 (0xC4)     | TILESET0.BIN (16.384 bytes = 256 tiles de 8x16 Mode0|
+-------------------+-----------------------------------------------------+
| Banc 5 (0xC5)     | 0x4000..0x63FF: MAP0.BIN (9.216 B = 128x72 índexs)  |
|                   | 0x6400..0x6DFF: TRIG0.BIN (2.560 B = 256×10)        |
|                   | 0x6E00..0x7FFF: Espai lliure per a nivells / dades  |
+-------------------+-----------------------------------------------------+
| Banc 6 (0xC6)     | Reservat (futur: cançons AKG / dades dels enemics)   |
+-------------------+-----------------------------------------------------+
| Banc 7 (0xC7)     | PFRAMES.BIN (5.760 B; frames masked de Jake)         |
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
2. **Localització de `_DATA`**: Al script `tools/build.py`, s'indica a l'enllaçador:
   ```python
   LINKARGS = ["-mz80", "--no-std-crt0", "-Wl-u", "--code-loc", "0x0100", "--data-loc", "0x3200", "-Wl-x"]
   ```
   Les dades globals se situen a partir de `0x3200`; al build actual `_CODE`
   acaba a `0x29D5` i `_DATA` a `0x39F9`, sense codi executable dins la finestra
   commutable de `0x4000..0x7FFF`.

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

### 4.1 Ascensors i cintes transportadores (`src/moving.c`)

`moving.c` implementa els cinc ascensors dels slots 19–23 de les dades de
*Magasin*. Les posicions d'origen es converteixen a píxels Mode 0 halvant X
(320 px originals a 160 px CPC) i mantenint Y. Cada ascensor espera 40
fotogrames als extrems, es mou 2 px per fotograma i canvia de direcció quan
troba el `tile_type == 10` de parada: `ypos16 - 4` en pujar i `ypos16 + 1`
en baixar. Les dues pàgines desen/restauren el fons independentment.

Jake pot aterrar-hi i queda transportat pel delta vertical de la plataforma;
les cintes es detecten pels `op_func` 27 (dreta) i 28 (esquerra), i hi afegeixen
2 px/fotograma a la velocitat horitzontal mentre és a terra. Els sprites dels
ascensors provenen dels frames 0 i 1 de `ENEMI1.SQV`, convertits amb
`tools/gen_elevator_frames.py` a Mode 0 masked (`src/elevator_frames.h`).

---

## 5. El Blitter d'Sprites (`engine/sprite.s`)

El jugador (Jake) té una mida de **24x30 píxels** (en Mode 0: **12 bytes d'amplada per 30 línies d'alçada**).

### 5.1 Format de les Dades
Els frames es generen amb `tools/gen_player.py` a `assets/bbdata/PFRAMES.BIN` i es carreguen al banc 7 a `0x4000`. `src/player_frames.h` conté només els offsets i les dimensions; abans del blit, el codi mapeja el banc 7. Cada píxel té la màscara invertida i les dades acolorides combinades:
- `inv_mask`: bits a 0 on hi ha sprite, bits a 1 on es preserva el fons.
- `img_masked`: píxels Mode 0 del personatge.

### 5.2 Estructura Dual del Buffer de Fons
Com que tenim dues pàgines de VRAM físiques independents (`0xC000` i `0x8000`), el fons que tapa el personatge a la pàgina A no és el mateix que a la pàgina B (degut a l'scroll i al moviment entre fotogrames). Per tant, el mòdul ASM manté **dos buffers de restauració de fons independents**:
- `_s_player_bg_c0`: 360 bytes (12x30) per a la pàgina `0xC000`.
- `_s_player_bg_80`: 360 bytes (12x30) per a la pàgina `0x8000`.
- Coordenades anteriors separades (`_s_old_x_c0`/`_s_old_y_c0` i `_s_old_x_80`/`_s_old_y_80`).

### 5.3 Adreçament sobre el ring CRTC

La taula `_scr_addr_table` conté les adreces de línia de base CPC. `sprite_map_line`
hi suma `_g_vram_start` i conserva els bits de pàgina/trama. El blitter resol el
wrap de 2 KB quan la línia de Jake creua el límit físic del ring; el camí comú
no-wrap es manté desenrotllat per reduir el cost per fotograma.

### 5.4 Algorisme del Blitter
El camí habitual bliteja 12 bytes per línia desenrotllats amb `.rept 12`, combinant
la màscara i desant el fons alhora:
```z80
    ld   a, (de)             ; Llegeix el fons existent a VRAM
    ld   (bc), a             ; Desa el fons original al buffer de restauració
    inc  bc
    and  (hl)                ; Aplica la màscara (forat negre per al personatge)
    inc  hl
    or   (hl)                ; Afegeix els colors del sprite
    inc  hl
    ld   (de), a             ; Escriu el resultat final a la pantalla oculta!
    inc  de                  ; el camí de wrap es tracta separadament
```
El camí ràpid evita comprovacions de wrap per byte; només les línies que
travessen el límit de 2 KB fan servir el camí de còpia byte a byte.

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

El CRTC mou la finestra actualitzant R12/R13 al VSYNC. No es copia la finestra
de 12 KB per pàgina: el cost de cada pas de càmera queda reduït a renderitzar la
tira entrant.

---

## 7. Pipeline de Construcció (`tools/build.py`)

El sistema de compilació automàtic s'encarrega de tot el cicle d'integració:
1. **Dades primer**: Munta `TITLE.BIN`, `TILESET0.BIN`, `MAP0.BIN` i `TRIG0.BIN` als primers sectors del disc `.dsk`.
2. **Generació automàtica de taules CHS**: Genera `src/disk_tables.h` amb les coordenades físiques exactes (pista, cap, sector) de cada fitxer al disquet.
3. **Compilació SDCC 4.5+**: Compila els mòduls C i ASM amb `--opt-code-size` i format `__sdcccall(1)`.
4. **Enllaçat**: Genera el binari `BLUESB.BIN` i n'obté automàticament el punt
   d'entrada `_start` del map file de l'enllaçador.
5. **Generació del fitxer DSK**: Insereix el binari i actualitza la capçalera AMSDOS per permetre l'arrencada amb `RUN"BLUESB"`.

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
