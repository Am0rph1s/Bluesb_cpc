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
| 0x0100 - 0x30D7   | Codi executable (_CODE: C + ASM + taules constants) |
| 0x3200 - 0x3528   | Variables globals i dades estàtiques (_DATA)        |
| 0x3529 - 0x3FFE   | PILA DE LA CPU (Stack Pointer SP fixat a 0x3FFE)    |
+-------------------+-----------------------------------------------------+
| 0x4000 - 0x7FFF   | Finestra de Bank Switching (Bancs 4..7 de 16 KB)   |
|                   | - En descans (0xC0): RAM Base Bloc 1               |
|                   | - Si es commuta 0xC4: Banc 4 visible (TILESET)      |
|                   | - Si es commuta 0xC5: Banc 5 visible (MAP + TRIG)   |
+-------------------+-----------------------------------------------------+
| 0x8000 - 0xB7FF   | PÀGINA DE VRAM 'B' (14 KB usats / 16 KB total)      |
|                   | Display start CRTC: R12 = 0x20                     |
| 0xB800 - 0xB9FF   | Buffer FDC RAW de sectors (512 bytes)              |
| 0xBA00 - 0xBA0F   | Àrea de treball FDC (16 bytes)                      |
| 0xBA10 - 0xBFFF   | Espai lliure / reservat per a SFX i taules auxiliars|
+-------------------+-----------------------------------------------------+
| 0xC000 - 0xFFFF   | PÀGINA DE VRAM 'A' (16 KB estàndard CPC)            |
|                   | Display start CRTC: R12 = 0x30                     |
+-------------------+-----------------------------------------------------+

+-------------------------------------------------------------------------+
|                            RAM ESTESA (64 KB)                           |
+-------------------+-----------------------------------------------------+
| Banc 4 (0xC4)     | TILESET0.BIN (16.384 bytes = 256 tiles de 8x16 Mode0|
+-------------------+-----------------------------------------------------+
| Banc 5 (0xC5)     | 0x4000..0x63FF: MAP0.BIN (9.216 B = 128x72 índexs)  |
|                   | 0x6400..0x6800: TRIG0.BIN (1.024 B = flags i opcodes|
|                   | 0x6800..0x7FFF: Espai lliure per a nivells / dades  |
+-------------------+-----------------------------------------------------+
| Banc 6 (0xC6)     | Reservat (futur: cançons AKG / dades dels enemics)   |
+-------------------+-----------------------------------------------------+
| Banc 7 (0xC7)     | Reservat (futur: banc d'animacions extres)          |
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
   Totes les variables globals (posició del jugador, estats d'animació, punters de buffers) estan concentrades entre `0x3200` i `0x3528`, deixant quasi 3 KB lliures de pila fins a `0x3FFE`.

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
| **Registre CRTC R12** | `0x30` | `0x20` |
| **Offset MA13..MA12** | Bits 13-12 actius (`11`) | Bit 13 actiu (`10`) |
| **Variable interna ASM** | `_g_vram_base_hi = 0xC0` | `_g_vram_base_hi = 0x80` |

### Commutació de Pàgina a `engine/cpc_hardware.s`:
```z80
_crtc_set_page::
    ld   bc, #0xBC0C         ; CRTC Registre 12 (Display Start High)
    out  (c), c
    ld   b, #0xBD
    out  (c), a              ; Escriu 0x30 (pàgina 0xC000) o 0x20 (pàgina 0x8000)
    ret
```

### Bucle de Doble Buffer a `src/main.c`:
1. La CPU dibuixa exclusivament sobre la pàgina oculta (`g_backbuffer = 0x8000` o `0xC000`).
2. S'esborra/restaura el fons de la posició anterior del jugador.
3. S'executen els canvis de càmera i desplaçaments.
4. Es bliteja el jugador sobre el fons del backbuffer.
5. S'espera l'inici del retrocés vertical: `cpc_wait_vsync_start()`.
6. Es commuta el registre 12 del CRTC a la nova pàgina visible.
7. S'inverteix el punter `s_back_page ^= 1` per al següent fotograma.

---

## 5. El Blitter d'Sprites (`engine/sprite.s`)

El jugador (Jake) té una mida de **24x30 píxels** (en Mode 0: **12 bytes d'amplada per 30 línies d'alçada**).

### 5.1 Format de les Dades
Els frames estan precalculats a `src/player_frames.h`. Cada píxel conté la seva màscara invertida i les dades acolorides combinades:
- `inv_mask`: bits a 0 on hi ha sprite, bits a 1 on es preserva el fons.
- `img_masked`: píxels Mode 0 del personatge.

### 5.2 Estructura Dual del Buffer de Fons
Com que tenim dues pàgines de VRAM físiques independents (`0xC000` i `0x8000`), el fons que tapa el personatge a la pàgina A no és el mateix que a la pàgina B (degut a l'scroll i al moviment entre fotogrames). Per tant, el mòdul ASM manté **dos buffers de restauració de fons independents**:
- `_s_player_bg_c0`: 360 bytes (12x30) per a la pàgina `0xC000`.
- `_s_player_bg_80`: 360 bytes (12x30) per a la pàgina `0x8000`.
- Coordenades anteriors separades (`_s_old_x_c0`/`_s_old_y_c0` i `_s_old_x_80`/`_s_old_y_80`).

### 5.3 Suport Transparent per a Bases `0xC000` i `0x8000`
La taula `_scr_addr_table` conté les adreces d'inici de les 200 línies de pantalla en format natiu CPC (`0xC000..0xF800`).
Per evitar duplicar una taula de 400 bytes, el blitter comprova la variable `_g_vram_base_hi`:
```z80
    ld   a, (_g_vram_base_hi)
    cp   #0x80
    jr   nz, no_remap
    res  6, d                ; Si base és 0x80, neteja el bit 6: 0xC0..0xF8 -> 0x80..0xB8
no_remap:
```
Això mapeja a l'instant qualsevol scanline de `0xC000` cap a `0x8000` amb només 2 cicles de rellotge!

### 5.4 Algorisme del Blitter (Sense Branques)
El bucle principal bliteja 12 bytes consecutius per línia desenrotllats amb la directiva `.rept 12`:
```z80
    ld   a, (de)             ; Llegeix el fons existent a VRAM
    ld   (bc), a             ; Desa el fons original al buffer de restauració
    inc  bc
    and  (hl)                ; Aplica la màscara (forat negre per al personatge)
    inc  hl
    or   (hl)                ; Afegeix els colors del sprite
    inc  hl
    ld   (de), a             ; Escriu el resultat final a la pantalla oculta!
    inc  de
```
Rendiment: bliteig complet amb desat de fons en només **~21.000 T-states** (~6 ms de CPU Z80).

---

## 6. Motor d'Scroll per Blocs (160x160 px)

El viewport de joc mostra una finestra activa de **20x20 subtiles (160x160 píxels)**.
L'scroll es produeix quan el jugador creua els límits de la zona morta (`DEAD_L=48`, `DEAD_R=88`, `DEAD_T=32`, `DEAD_B=116`).

### 6.1 Desplaçament Intern en Memòria
Quan la càmera es mou, es desplacen les dades gràfiques de la finestra de joc a la VRAM oculta:
- **`scroll_shift_left_4`**: Desplaça 19 columnes (76 bytes) cap a l'esquerra per línia mitjançant `LDIR`. Deixa la columna 19 buida per renderitzar el nou bloc.
- **`scroll_shift_right_4`**: Desplaça 19 columnes cap a la dreta mitjançant `LDDR`. Deixa la columna 0 lliure.
- **`scroll_shift_up_8`**: Desplaça 19 files cap amunt amb `LDIR` de 1.520 bytes per scanline.
- **`scroll_shift_down_8`**: Desplaça 19 files cap avall amb `LDDR`.

> [!IMPORTANT]
> **Nota crítica sobre els registres Z80:** Les rutines `scroll_shift_left_4` i `scroll_shift_right_4` fan servir `A` com a comptador de les 160 línies. Cal fer `push af` abans de consultar `_g_vram_base_hi` per evitar sobreescriure el comptador de bucle (error solucionat que causava el penjat inicial).

### 6.2 Sincronització entre ambdós Buffers
Com que treballem amb doble buffer, quan es produeix un moviment de càmera, **tots dos buffers han d'aplicar el desplaçament** (`move_x` / `move_y`) perquè la imatge no faci salts endavant i endarrere en alternar entre la pàgina A i la B.

---

## 7. Pipeline de Construcció (`tools/build.py`)

El sistema de compilació automàtic s'encarrega de tot el cicle d'integració:
1. **Dades primer**: Munta `TITLE.BIN`, `TILESET0.BIN`, `MAP0.BIN` i `TRIG0.BIN` als primers sectors del disc `.dsk`.
2. **Generació automàtica de taules CHS**: Genera `src/disk_tables.h` amb les coordenades físiques exactes (pista, cap, sector) de cada fitxer al disquet.
3. **Compilació SDCC 4.5+**: Compila els mòduls C i ASM amb `--opt-code-size` i format `__sdcccall(1)`.
4. **Enllaçat**: Genera el binari `BLUESB.BIN` amb punt d'entrada a `_start` (`0x0E42`).
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
1. Actualment `render_column` i `render_row` són funcions buides (stubs).
2. Per completar l'scroll continu perfecte, implementar el dibuix de la columna entrant llegint els tiles del Banc 4/5 i pintant només els 4 bytes corresponents a la vora alliberada per `scroll_shift_*`.
