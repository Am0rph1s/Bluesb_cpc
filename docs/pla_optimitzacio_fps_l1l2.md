# Pla Definitiu d'Optimització — Fase 2 (revisat i verificat)

> Revisió feta contra `tools/build.py`, `src/hud_bank.c`, `src/enemy.c`,
> `engine/tile_blit.s` i els `.map` reals d'`obj/` (build `3a6d1ec`).

## 1. Els 3 Descobriments Crítics (verificats)

### Trampa 1 (Pas A) — El Banc C1 NO té 6,4 KB lliures per a un buffer de HUD ✅

* `hud_bank.c` viu incrustat dins `MUSBANK.BIN` a **`0x4C10..0x4FA5`** (917 B de
  920: **3 B lliures**) i el seu `_DATA` a `0x4FA8..0x4FFF` (57 B de 88: 31 B).
* Els 6.380 B "lliures" del build són de la part **de nivell** de C1 (variable; a
  L3 només queden 594 B). **No hi cap cap buffer de HUD a C1.**

**Solució (0 bytes de buffer):** les dues pàgines de VRAM (`0xC000` i `0x8000`)
són accessibles alhora. Quan només ha canviat `g_vram_start` (scroll) i els
comptadors no han canviat, es copia el HUD ja renderitzat de l'altra pàgina
(`other = page ^ 1`) amb `LDIR`.

**Correcció important de la mida:** el HUD **no** són 160 B contigus. Cada fila
de caràcters ocupa 8 scanlines de 80 B a passos de `0x800` (interleavejat CPC):
2 files × 8 scanlines = **16 scanlines × 80 B = 1.280 B**. Per tant:

| Mètode | Cost | Estalvi |
|---|---|---|
| `hud_blit_columns()` actual | 40 col × ~1.585 T = **63.400 T (15,9 ms)** | — |
| Còpia VRAM→VRAM (16 × 80 B, LDIR 21 T/B) | **26.900 T (6,7 ms)** | **9,1 ms** |

La còpia és 2,4× més barata que reconstruir (no rellegeix tiles ni recalcula
`tile*24`). Un memmove de 160 B **no és possible**: les scanlines no són
contigües.

### Trampa 2 (Pas B) — C6 `_CODE` acaba a `0x76F4`, a 12 B de `0x7700` ✅

* `obj/enemybank_0.map`: `_CODE` `0x5A00` + `0x1CF4` = **`0x76F4`**.
* Si `en2_cell()` creix, el scratch a `0x7700` sobreescriuria `en2_room_exit`.
* I si `opp_slot == s`, `en2_flip_cell(slot_s, slot_s)` corromp la meitat
  esquerra (llegeix de dreta a esquerra i escriu d'esquerra a dreta).

**Solució:** scratch fix a `0x7700..0x78FF`, `s = (s+1)&3` si `s == opp_slot`
(així es conserven les dues orientacions), factoritzar `dst`/`src` per aprimar
`en2_cell()` ~15 B i **assert al build**: `_CODE` ≤ `0x7700` → FATAL.

### Trampa 3 (Pas C) — Paritat de `cam_x4 + sx` ✅ (amb una correcció)

* Les dues columnes noves (`sx, sx+1`) són les dues meitats del mateix tile
  només si `(cam_x4 + sx)` és parell → **~50% dels frames** (cam_x4 pot ser
  senar). Correcte.
* **Correcció:** l'offset vertical per a la segona meitat del mateix tile és
  **`HL + 3`**, no `+10`. `_render_tile_fast_de` avança HL **+29** (7 blocs ×
  `+4` + `+1`) i la subfila següent és a `+32` (8 scanlines × 4 B).
* A més, `s_tile_ids[i] == s_tile_ids[i+1]` és **sempre cert** (el bucle
  `rc_map_loop$` llegeix el mateix byte de `GMAP` per a cada parella de
  subfiles): no cal comprovar-ho, l'optimització s'aplica a les 10 parelles.

---

## 2. Passos (ordre d'execució)

### Pas 0 — Mesura del frame en `quiet` (abans de tocar res)

`quiet` és a 41-44 ms (3 VSYNCs) i el llindar de 25 fps és a 40 ms. Cap dels
passos A-C hi ajuda (el HUD no corre en quiet i `en2_restore` només crida
`moving_restore_box`, sense commutacions per caràcter). Cal mesurar per seccions
amb `dbg_border`/`PROFILE_BORDER` i decidir després (candidats: repintat del
conveyor ~2 ms, dibuix d'enemics, blits del Jake).

### Pas D — Revertir P1b + retall d'spans (allibera resident)

1. Treure `render_tile_span` de `src/render.c` i tornar `render_tile_world` a la
   versió per tile (recupera **+186 B** de `_CODE`).
2. `src/moving_bank.c`: bucle per columna + retall del span contra
   `[g_cam_x4 >> 1, (g_cam_x4 + 39) >> 1]` (evita iterar spans fora de pantalla).
3. `main.c:1324`: `hud_render(s_back_page, 0)` (+14 B; el scroll ja es detecta
   per `g_vram_start != s_hud_vram_start[page]`).
4. `_DATA` torna a `0x38F0` i el canari a `0x3D60` (pila 670 B).

### Pas A — HUD: còpia VRAM→VRAM del frontbuffer

1. Rutina resident `hud_copy_strip(src, dst)` a `engine/tile_blit.s` (~55 B):
   `16 × (LDIR 80 B; src += 0x800; dst += 0x800)`. Al resident no gasta espai
   de C1 i és cridable des de C1.
2. `src/hud_bank.c` (`hud_render_b`): si `!force` i els comptadors de `page`
   coincideixen amb els globals:
   * si `s_hud_vram_start[page] == g_vram_start` → `return` (quiet = 0 ms);
   * si l'altra pàgina té el HUD vàlid (`s_hud_vram_start[other] != 0xFFFF` i
     comptadors iguals) → `hud_copy_strip(base_other + off_other,
     base_page + off_new)`; actualitzar `s_hud_vram_start[page]` i `return`;
   * si no, reconstrucció completa (com ara).
3. `s_base_hi`/offsets: `off = ((vram_start + 800) & 0x3FF) << 1`.

Cost del fast-path: ~26.900 T (6,7 ms) en lloc de 63.400 T (15,9 ms).

### Pas B — Cache d'enemics: scratch fix + reutilització de l'oposada

1. `src/enemy.c`: `ENEMY_FLIP_SCRATCH ((u8*)0x7700)`.
   * En el `for (s...)`, buscar `key` i `opp = key ^ 0x80` alhora.
   * En un miss: `s = ENEMY_CACHE_NEXT`; si `s == opp_slot`, `s = (s+1)&3`;
     `NEXT = (s+1)&3`.
   * Si `opp_slot != 0xFF` → `en2_flip_cell(slot_opp, slot_s)` (sense ZX0).
   * Si no, `zx0_decompress` a `0x7700` + `en2_flip_cell` si `flip`, o directe a
     `slot_s` si no.
   * `WHO[s] = key` sempre (cap slot queda a `0xFF`).
2. `tools/build.py`: FATAL si `_CODE` de C6 > `0x7700`.

### Pas C — `render_column`: parelles i meitat inferior

1. A `rc_draw_loop$`: quan la subfila és la meitat inferior del mateix tile
   (sempre), no cridar `calc_tile_hl`: `HL += 3` després de
   `_render_tile_fast_de` i saltar la lectura de `s_tile_ids`.
2. `_render_column_pair(cam_x4, cam_row, sx)` per a `page_dx == ±2` quan
   `((cam_x4 + sx) & 1) == 0` i `E != 0xFE`: 4 bytes contigus per scanline en
   lloc de 2 × 2 B (~95 T vs 150 T per scanline).
3. Si no es compleix la condició, cridar `render_column` per a `sx` i `sx+1`.

---

## 3. Impacte esperat (L1)

| Escenari | Ara (`3a6d1ec`) | Després de A+B+C | Guany |
|---|---|---|---|
| `caminant` | ~82 ms (5 VSYNCs = 10,4 fps) | ~63 ms → ~60 ms | **-19 a -22 ms**; a tocar del llindar de 3 VSYNCs (16,7 fps) |
| `caminant2` | ~86 ms (9,3 fps) | ~64 ms | elimina la regressió de P3 |
| `quiet` | ~41-44 ms (16,8 fps) | igual fins al Pas 0 | cal mesura prèvia |
| `_CODE` resident | 27 B | **~200 B** (P1b + main.c) | marge per al Pas A/C |

---

## 4. Estat d'execució (build `11ac841`)

| Pas | Estat | Resultat |
|---|---|---|
| **Pas D** (P1b revertit + retall d'spans) | FET | `render_tile_span` fora; +186 B de `_CODE`; retall a C5 |
| **Pas A** (HUD: còpia VRAM→VRAM) | FET | `hud_try_copy`/`hud_copy_strip` al resident; snapshot global de 4 B |
| **Pas B** (cache d'enemics) | FET | scratch `0x7700` + reutilització `key^0x80`; assert `_CODE` ≤ `0x7700` |
| **Pas C** (`render_column` parelles + `HL+3`) | PENDENT | el resident té ~97 B; cal mesurar abans |
| **Pas 0** (mesura de `quiet`) | PENDENT | `quiet` segueix a 16,7 fps (3 VSYNCs) |

### Mesura A/B del Pas A (en calent, mateix build i mateixa ruta)

El HUD es pot desactivar en calent patchejant `hud_try_copy` a `xor a; ret`
(retorna 0 = reconstrucció, el comportament anterior). Caminant alternant
direcció (per no encallar-se), 4 mostres de 8 s:

| Configuració | Mostres | Mediana |
|---|---|---|
| Amb fast-path (còpia VRAM→VRAM) | 13,9 / 14,9 / 14,9 / 14,4 | **14,7 fps** |
| Sense fast-path (reconstrucció) | 14,4 / 13,9 / 13,4 / 12,4 | **13,7 fps** |

**Guany: +1,0 fps (~9 ms/frame en scroll).** El HUD era el cost dominant de
l'scroll (15,9 ms) i ara en costa 6,7 ms, però com que el frame segueix a ~70 ms
(4 VSYNCs) el guany en fps queda limitat per la quantització de VSYNC.

> **Correcció d'una mesura anterior**: un `perf_monitor` va donar "caminant
> 16,7 fps (+60%)" però era un artefacte: el jugador es va quedar encallat a
> `px=76` i l'fps mesurava repòs. La xifra bona és l'A/B de dalt.

### Detalls d'implementació que cal recordar

* **El HUD no són 160 B contigus**: són 2 files de caràcters = **16 scanlines de
  80 B a passos de `0x800`**. `hud_copy_strip` fa 2 files × 8 scanlines.
* La còpia només és lineal si la tira **no creua el wrap de `0x800`**
  (`off <= 0x760`); si el creua, es reconstrueix (~8% dels offsets).
* El **snapshot de contingut és global** (4 B), no per pàgina: quan canvia, la
  pàgina de torn es reconstrueix i l'altra copia d'ella al frame següent.
  Amb comptadors per pàgina el codi de C1 no hi cabia (aritmètica de 16 bits ×8).
* **C1 va just**: `hud_bank` viu a `0x4C01..0x4FC6` (965 B de 967) i `_DATA` a
  `0x4FC8..0x4FFF` (53 B). `hb_base`/`hb_data` ajustats a `build.py`.
* `_DATA` resident a `0x39A0` (pila 494 B; **ús real mesurat 100 B**) i canari a
  `0x3E10`.
* `build_bank_equ` genera un placeholder per `_hud_try_copy` a la 1a iteració
  (el HUD es construeix abans del resident); la 2a ja hi posa l'adreça bona.

### Següent objectiu

Per creuar a 16,7 fps caminant calen ~10 ms més. Candidats, per ordre:
1. **Pas C** (parelles de columnes a `render_column`): ~3-4 ms.
2. **Dibuix/restauració d'enemics** (C6, ~14 ms/frame segons el perfil): el
   següent coll d'ampolla real.
3. **Pas 0**: mesurar el frame en `quiet` per seccions abans de tocar res.
