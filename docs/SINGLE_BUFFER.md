# Arquitectura Single Buffer (`single-buffer-split`) — Blues Brothers CPC

> **Branca**: `single-buffer-split` · **Data**: 17/11/2026
> **Estat**: Compilat i verificat a ZEsarUX (`smoke_test --dsk-only`, `verify_sb_l1_iaia.py`, `verify_vscroll.py`, `hud_check.py`).

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
| **RAM 0 (`0x0000..0x3FFF`)** | `_CODE` `0x0100..0x359A`, `_DATA` `0x3600`, canari `0x3Bxx` | **`_CODE` `0x0100..0x37B3` (`14.003 B`, marge `77 B`)**, **`_DATA` `0x3800..0x3BE7` (`989 B`)**, **`CANARY_ADDR = 0x3C40`**, pila lliure `1.047 B` |
| **RAM 2 (`0x8000..0xBFFF`)** | Pàgina VRAM 1 (`0x8000`) durant el joc; scratch FDC en càrrega | **Alliberada en joc**: cel·les d'enemics + cache H-flip (`0x8000..0xB5FF`), buffer fix del HUD (`0x8760`/`0x87B0` × 8 scanlines), `ENEMY_BBOX_ADDR` (`0xB700`), **codi resident ràpid `ram2_code.s` (`0xB800..0xBBFF`, `1.024 B`)**. En càrrega de nivells segueix fent de scratch FDC (`0x8000..0xBBFF`, `FDC.BIN` a `0x8000..0x8FFF`, càrrega `.PAK` a `0x8320`). |
| **RAM 3 (`0xC000..0xFFFF`)** | Pàgina VRAM 0 (`0xC000`) | **Única pàgina VRAM (`0xC000`)** en anell circular (`0x3000..0x33FF`) |
| **Banc `C1` (RAM 1)** | Player AKG + `hud_bank` + cançó + `LVLCHS` + `FDC.BIN` mestre | Mateix esquema, i a **`C1:0x6030`** s'hi emmagatzema la imatge de `RAM2.BIN` (`engine/ram2_code.s`), que es copia a `0xB800` al carregar el primer nivell |
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
- **`0xBC00..0xBDFF` (`512 B`)**: `ASSETS_FDC_BUF` (buffer de sector FDC).

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
Com que l'àrea de joc i el HUD comparteixen l'anell `0xC000`, en desplaçar `R12/R13` el HUD antic queda desplaçat `dx` columnes / `dy` files fins que es reescriu:
- **Scroll horitzontal o amunt (`dy <= 0`)**:
  1. Si `dy < 0`, [`render_rows_edge(..., 0)`](../src/main.c#L1014-L1015) pinta primer les files superiors (`0 .. -dy-1`) abans de `VCC = 0` perquè no quedin restes del HUD antic a dalt.
  2. Restores a coordenades antigues (`restore_fg_sprites`, `enemy_restore`, `moving_restore`).
  3. **`hud_render((u8)(s_mn_page_dy != 0), 1)` abans de `sync_backbuffer()`**: el HUD queda copiat a `new_ma + 800..879` molt abans que el feix arribi a la fila `20` (`~17 ms`).
  4. `sync_backbuffer()` (columnes `0`/`39` si `dx != 0`) i `early_jake`.
- **Scroll vertical cap avall (`dy > 0`)**:
  - Quan `dy = +2`, el HUD antic cau sobre les files `18..19` noves (que el feix escombra a `~16 ms`, **abans** que el HUD a `~17 ms`), i no hi solapament amb el playfield antic (`old_ma` acaba com a màxim a la fila `18` nova).
  - Ordre: **`hud_render(1, 1)` → `early_jake` → [`render_rows_edge((u8)s_mn_page_dy, 1)`](../src/main.c#L1016-L1026)** (`rows 19..18`) → restores d'enemics/movers → `sync_backbuffer()` (columnes si `dx != 0`).

---

## 4. Verificació Realitzada

- `py -3 tools/build.py` i `py -3 tools/smoke_test.py --dsk-only`:
  - `GAME.BIN`: `15.079 B` (`30` sectors, `CRC 0xE5B4`), `_CODE` `14.003 B` (`77 B` de marge fins a `_DATA` a `0x3800`), `RESULTAT: OK`.
- **Nivell 1 (scroll horitzontal + col·lisió)**: `verify_sb_l1_iaia.py` (`Loaded=True`, `hit_seen: True`), captures netes als marges, Jake i HUD.
- **Nivell 3 (scroll vertical cap avall)**: `hud_check.py` (`0` píxels de diferència al HUD durant el descens `r12 -> r52`) i `verify_vscroll.py` sense rastre del HUD antic sobre l'àrea de joc.
