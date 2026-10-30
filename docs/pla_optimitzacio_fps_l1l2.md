# Pla d'Optimització Definitiu (L1 i L2)

Després de revisar les teves observacions punt per punt contra els mapes d'enllaçat (`obj/enemybank_0.map`, `obj/bluesb.map`) i el maquinari CPC, aquí tens el pla corregit i definitiu.

---

## 1. Revisió dels Punts Crítics que has Detectat

### A. Correcció de P3: Mapa de Memòria Real del Banc C6 (`obj/enemybank_0.map`)
Tens tota la raó: a `obj/enemybank_0.map`, `_CODE` comença a `0x5C00` i ocupa `0x1CE5` bytes, acabant a **`0x78E5`** (a només 27 bytes de la LUT a `0x7900`). Per tant, a `0x6E00..0x77FF` **no hi ha espai**.

Mirem el mapa real complet del Banc C6 (`0x4000..0x7FFF`) als 3 nivells compilats:
* `0x4000..0x403F` (64 B): `EN_TABLE` (16 punters ZX0)
* `0x4040..0x49EF` (màx. 2.479 B a L1; 2.040 B a L2; 2.221 B a L3): `EN_BLOCKS` (cel·les ZX0)
* `0x4B00..0x4DD5` (màx. 725 B a L3; 557 B a L1; 548 B a L2): `EN_RESTORE` (`RESTORE*.BIN`)
* **`0x4E00..0x4FFF` (512 B)**: **100% LLIURE a tots els nivells** (entre el final de `EN_RESTORE` i `EN_CACHE` a `0x5000`). A més, si pugem `EN_RESTORE` a `0x4A00` (ja que `EN_BLOCKS` acaba a `0x49EF`), l'espai lliure és `0x4CE0..0x4FFF` (~800 B).
* `0x5000..0x57FF` (2.048 B): `EN_CACHE` (4 slots $\times$ 512 B)
* `0x5800..0x581F` (32 B): `ENEMY_CACHE_WHO` + `ENEMY_CACHE_NEXT`
* `0x5820..0x5BF2` (978 B): `_DATA` — **on ja viu `s_flip_buffer[512]`**!
* `0x5C00..0x78E5` (7.397 B): `_CODE`
* `0x7900..0x79FF` (256 B): LUT de H-Flip
* `0x7A00..0x7FFF` (1.536 B): `BG_BASE` (6 slots $\times$ 256 B)

#### Solució Viable per a P3 sense tocar `_CODE` ni `0x7900`:
1. **Segon buffer de flip a `0x4E00..0x4FFF` (o Cache Direccional unificada de 6 slots)**:
   - Actualment tenim 4 slots a `0x5000..0x57FF` (2 KB) + `s_flip_buffer` a `_DATA` (512 B) + `0x4E00..0x4FFF` lliure (512 B) = **6 blocs de 512 B ja disponibles sense moure cap codi ni LUT**.
   - Si utilitzem `0x4E00..0x4FFF` com a segon buffer de flip (`s_flip_buf[2][512]` amb `s_flipped_cell[2]`, o bé convertim els 6 blocs de 512 B en una **cache direccional on l'etiqueta és `cell | (flip ? 0x80 : 0)`** usant un dels slots com a scratch quan cal girar), eliminem el thrashing quan hi ha 2 enemics mirant a l'esquerra **sense gastar ni un byte extra a `_CODE` ni envair `0x7900`**.

---

### B. Correcció de P2.2: Fidelitat 1:1 a Consultes d'Enemics i Modificacions del Mapa
Tens tota la raó: si una palanca/switch (`b5_set_tile`) obre o tanca una comporta o si es destrueix/agafa una caixa (`b5_world_reset_tile`), el mapa canvia.
Per garantir **fidelitat 100% 1:1 en qualsevol situació**:
1. **Optimizacions intra-frame sense estat (100% segures davant qualsevol canvi de mapa)**:
   - **Deduplicació de `c2row == brow`**: A cada frame es calcula `brow = (y + 31) >> 4` i `c2row = (y + 30) >> 4`. Quan `c2row == brow` (que passa el **100% del temps quan l'enemic camina sobre terra pla**, ja que `y` és múltiple de 16), no es repeteixen les crides `is_floor_solid(acol, c2row, -1, 0)` ni `tile_flags(acol, c2row)` sobre la mateixa fila que ja s'acaba de comprovar amb `brow`.
   - **Variables locals `tt_pf` i `tt_pb` + Short-Circuit**: Llegir un sol cop `tt_pf = tile_type(pcol, frow)` i `tt_pb = tile_type(pcol, brow)` (evitant la doble lectura de `kind == 21` a L2) i comprovar si l'enemic ja ha de girar per precipici (`== 1`) o límit (`== 12`) **abans** d'invocar `is_floor_solid` i `tile_flags`.
2. **Cache de columna validada amb invalidació per `g_map_dirty` (opcional i blindada)**:
   - Si a més guardem l'última columna validada o bé incrementem un comptador/flag global `g_map_dirty` dins de `b5_set_tile` (que és l'únic punt per on passen les palanques/switches i les caixes a `bank5_table.s`), qualsevol modificació del mapa invalida immediatament el fast-path.
   - Ara bé, només amb P2.1 (fusió de `get_trig_byte`) + la deduplicació intra-frame (`c2row == brow` + short-circuit de `tt_pf`/`tt_pb`), les commutacions de banc per walker ja baixen de **16 a 4–6 per frame** (~70% d'estalvi) sense cap necessitat d'estat entre frames!

---

### C. Aclariment de P4.1: Què mapeja `0xC0` vs `0xC1` al Gate Array del CPC 6128?
És molt bon punt verificar-ho abans de tocar res:
* Al nostre projecte:
  - El **mapa (`MAPC`), `ROOMSC`, `TRIGC` i `moving_bank.c`** viuen al **Banc C5 (`0xC5`)**.
  - La **música (`MUSBANK`), el HUD (`hud_bank.c`) i els ascensors (`level_code.c`)** viuen al bloc de 16 KB que anomenem "C1" (`0x4000..0x7FFF`).
* Com funciona el maquinari Gate Array del CPC 6128 per a `0xC0` i `0xC1`?
  - A **`0xC0`** (configuració base de 64 KB): `0x0000..0x3FFF` = RAM 0, **`0x4000..0x7FFF` = RAM 1**, `0x8000..0xBFFF` = RAM 2 (VRAM pàg. 1), `0xC000..0xFFFF` = RAM 3 (VRAM pàg. 0).
  - A **`0xC1`**: `0x0000..0x3FFF` = RAM 0, **`0x4000..0x7FFF` = RAM 1 (la mateixa física que a `0xC0`!)**, `0x8000..0xBFFF` = RAM 2, i **`0xC000..0xFFFF` = Banc Extra 7 (on viuen els sprites d'en Jake!)**.
* Per això mateix a [`src/render.c:16-23`](file:///c:/Projects/bluesb_cpc/src/render.c#L16-L23) hi ha aquest comentari:
  > `// El HUD viu a C1:0x4C00 (dins MUSBANK, darrere player_akg). Escriu a VRAM (0x8000 i 0xC000): el banc durant l'execucio ha de ser 0xC0 (a 0xC1 el rang 0xC000..0xFFFF es el banc 7 i trepitjariem els frames del jugador!).`
  I per això `hud_render` fa `call_banked(0xC0, (void*)hud_render_o)`, i dins de [`src/level_code.c:73`](file:///c:/Projects/bluesb_cpc/src/level_code.c#L73) `lc_moving_restore` (tot i estar executant-se a `0x6500`) fa `prev = bank_set(0xC0); moving_restore_box(); bank_restore(prev);` sense penjar-se!
* Com proposes, deixem **P4.1 per al final de tot** i ho verifiquem aïlladament.

---

### D. 25 Hz vs 30 Hz (Velocitat en Temps Real respecte al DOS)
A [`tools/blues_dos/bb/level.c:2122`](file:///c:/Projects/bluesb_cpc/tools/blues_dos/bb/level.c#L2122), el DOS limita el bucle amb:
```c
const int diff = (timestamp + (1000 / 30)) - g_sys.get_timestamp();
g_sys.sleep(diff < 10 ? 10 : diff); // 33 ms/frame = 30,3 fps
```
Per què en CPC sincronitzem amb VSYNC a **25 Hz** (2 VSYNCs de 50 Hz = 40 ms) i com afecta les velocitats?
1. **Per què no es pot fer doble buffer sense VSYNC al CRTC del CPC?**
   Al CPC, el CRTC només llegeix els registres R12/R13 (`crtc_set_display_start`) a l'inici del quadre de vídeo (just després del VSYNC). Si commutéssim `s_back_page` a 30 Hz lliures sense esperar el VSYNC i comencéssim a esborrar (`restore`) l'altra pàgina abans del VSYNC, esborrariem els sprites de la pàgina que el monitor **encara està escanejant**, produint parpelleig/tall d'sprites (*tearing*).
2. **Com estan calibrades les velocitats al nostre port per compensar 25 Hz vs 30 Hz?**
   - **Moviment horitzontal d'en Jake (`SPEED_MAX`)**: Al DOS (`level.c:1770`), `xmaxvelocity = 50` subpíxels DOS ($50 / 8 = 6\text{ px DOS/frame} = 3\text{ px CPC/frame}$). A 30 fps, en Jake recorre $3 \times 30 = \mathbf{90\text{ px CPC/s}}$. Al nostre [`src/main.c:49`](file:///c:/Projects/bluesb_cpc/src/main.c#L49), vam definir `SPEED_MAX = 30` ($30 / 8 = 3{,}75\text{ px CPC/frame}$), que a **25 fps** dóna $3{,}75 \times 25 = \mathbf{93{,}75\text{ px CPC/s}}$ (ja compensat un $+25\%$ per igualar la velocitat en temps real del DOS!).
   - **Moviment horitzontal dels enemics (`ENEMY_VX`)**: Al nostre [`src/enemy.c:29`](file:///c:/Projects/bluesb_cpc/src/enemy.c#L29) ja tenim documentat:
     `#define ENEMY_VX 24 // 3 px/frame @SUB8 (DOS 40>>3=5 DOSpx/f @30fps = 150 px/s; 3*2*25 = 150)`
     És a dir, els walkers a 25 fps ja es mouen a la **mateixa velocitat exacta en píxels/segon** que al DOS a 30 fps!
   - **Gravetat i Salt (`GRAV = 16`, `JUMP_VY = -112`)**: Aquests valors determinen la **geometria de la paràbola en píxels** ($56\text{ px}$ d'alçada = $3{,}5\text{ tiles}$), per tant han de ser 1:1 per frame perquè en Jake arribi exactament a les mateixes plataformes que al DOS.

Per tant, quan el joc corre a **25 fps** (2 VSYNCs), la velocitat de desplaçament d'en Jake i dels enemics en temps real ja és ~1:1 amb el DOS a 30 fps! El motiu pel qual ara es nota lent és perquè a 12,5 fps (L1) o 8,4 fps (L2) va a la meitat o a un terç d'aquests 25 fps.

---

## 2. Ordre Definitiu d'Execució (Pas a Pas)

Seguim exactament l'ordre d'aplicació i verificació que proposes:

1. **Pas 1 — P4.2 (Pacing VSYNC `< 7` a [`src/main.c`](file:///c:/Projects/bluesb_cpc/src/main.c#L1393))**:
   - Canviar `if ((u8)(g_ticks - last_ticks) < 2)` per `< 7` (1 línia).
   - Impedeix que el joc s'acceleri a 50 fps a les habitacions i a les escenes que baixin de 20 ms gràcies a les optimitzacions següents.
2. **Pas 2 — P2.1 (Fusió de `get_tile_at` + `get_trig_byte` a [`src/main.c`](file:///c:/Projects/bluesb_cpc/src/main.c#L177-L194))**:
   - Llegir el tile i el byte de `TRIG` dins d'un sol bloc `bank_set(0xC5)` / `bank_restore(prev)`.
   - Accelera tant `player_physics_step` com totes les consultes de `en2_update`, i **allibera bytes de `_CODE` resident**.
3. **Pas 3 — P1 (Spans Animats i Blit de Span/Tile a `moving.c`, `moving_bank.c`, `tile_blit.s`)**:
   - Eliminar el bucle `while (p >= L) p -= L;` repetit pels 54 spans; avançar les seqüències (`LEVEL_ANIM_SEQ_COUNT`: 7 a L1, 12 a L2) un sol cop per tick.
   - Detectar quines seqüències han canviat realment de tile (`new_tile != old_tile`) per saltar les que repeteixen tile (com el 60% dels passos de les espurnes `seq 10` i `seq 11` a L2).
   - Substituir la crida per tile a `render_tile_world` dins de `moving_bank_conveyor` per una rutina ràpida a [`engine/tile_blit.s`](file:///c:/Projects/bluesb_cpc/engine/tile_blit.s) que commuti a `0xC4` un sol cop per span i pinti els tiles visibles seguits al ring VRAM.
4. **Pas 4 — P2.2 (Deduplicació intra-frame de consultes a [`src/enemy.c`](file:///c:/Projects/bluesb_cpc/src/enemy.c#L422-L454))**:
   - Guardar `tt_pf` i `tt_pb` en variables locals i fer short-circuit abans de consultar `is_floor_solid` i `tile_flags`.
   - Evitar consultar `c2row` quan `c2row == brow` (100% dels frames sobre terra pla).
   - Sense saltar consultes entre frames (o invalidant amb `g_map_dirty` si calgués), mantenint fidelitat 100% 1:1 amb comportes i caixes.
5. **Pas 5 — P3 (Segon Buffer de Flip / Cache Direccional a `0x4E00..0x4FFF` al Banc C6)**:
   - Usar el bloc lliure `0x4E00..0x4FFF` (512 B, verificat lliure a L1, L2 i L3 a `build_enemybank`) juntament amb `s_flip_buffer` a `_DATA` per tenir 2 buffers de flip (o cache direccional de 6 slots amb `0x5000..0x57FF`), sense tocar `_CODE` (`0x5C00..0x78E5`) ni la LUT (`0x7900`).
6. **Pas 6 — P4.1 (Commutació directa a `0xC0` a `moving_restore` / `moving_draw`)**:
   - Verificar i aplicar al final, comprovant que el marge de `level_code` i el comportament dels ascensors/premses és idèntic.
