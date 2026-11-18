# Registre Històric de Canvis — Blues Brothers CPC

Aquest fitxer recull el detall cronològic de les sessions i fites del projecte. Per a l'estat actual, regles i arquitectura vigent, consulta [`docs/HANDOFF.md`](HANDOFF.md).

---

### 18/11/2026 - Dibuix: cache de columna estable (single buffer)

- **Cache lookahead de columna** a `0xBC00`/`0xBD00` (buffer FDC lliure en joc, 160 B per a 10 files) i estat a `0x9E58..0x9E5D`. El pre-render omple la columna del frame seguent i el sync la copia a VRAM.
- **Copia byte a byte estable** a `ccb_tile$`. La variant `LDI` (2 `ldi` + 2 `dec e`) era mes rapida pero va provocar un salt salvatge/reset a `px8=1732`; queda descartada fins a validar-la de nou.
- **Ordre horitzontal**: sync (225) -> restore Jake (277) -> draw (16) -> HUD (88..168) -> restores d'enemics diferits (169) -> enemy draw (234..265) -> pre-render. Primera columna correcta i HUD net.
- **FPS**: 25,0 fps amb scroll (`g_ticks` delta 12), enfront de ~15-17 fps del doble buffer `master`.
- **Verificacio**: `smoke_test` OK (`magic=0xB0`, `px8=192`), `check_c6_flag` OK, DSK 30 sectors/14.899 B CRC `0xA561`, caminada real de 25 s sense crash (px8 192..5.952), diff d'enemics old/clean = 0 pixels, salt natural `dsy=58` i captures de scroll/vertical netes.
- **Caixa/carry**: `s_carry_kind=1` a `px8=1462`; captura `carry_hud` neta (Jake amb caixa, HUD net).
- **Verificacio funcional addicional**: globus/paraigua amb estat injectat (captures netes), ascensor 0 (camera `cam_row 28->30`, captura neta), sala L1 entrada/sortida (`in_room 1->0`, captura neta; sala blanca identica al baseline), 5 frames d'enemics en moviment sense crash, i L2 carregat per `check_c6_flag`.
- **Enemic en moviment**: `s_enemies[2]` x 600->632 i `s_enemies[7]` 688->664 (estat C6), amb camera seguint l'enemic; el diff stationary segueix sent 0. El retall aillat del sprite en moviment no es concloent (teleport/fons animats de L1 dominen el diff); el retall per slots C6 a `en2_draw` tampoc va donar valors valids. El lag d'un camp del restore diferit queda com a risc residual, no observat.
- **Transicio completa L1->L2**: `g_level_complete=1` a L1, 50 frames de celebracio, front/mapa i carrega del paquet L2 (`room_count=0`, `row0=255`) al cap de ~34,5 s; captura `l2_settled` de la fabrica L2, sense crash. Pickup natural de globus/paraigua encara pendent: sales 1-4 provades amb popups `b3=19/20` (posicions 77..83, 82..98), pero `s_carry_kind` va quedar 0.

---

### 17/11/2026 — Memòria: Fase 0+1 (límit de pak i dades fredes a RAM 2)
- **Crític**: `PAK_SCRATCH_MAX` passa de 14.208 a **13.536 B** (`0xB800 - 0x8320`). El codi resident RAM2 viu a `0xB800`; l'antic límit permetia que un pak gran el trepitgés i pengés el joc al primer scroll. El build avisa si queden menys de 512 B.
- **C0**: `_DATA` baixa de 989 a **297 B** i `--data-loc` passa a `0x3A00`; `_CODE` queda a **13.960 B** amb **632 B** de marge (abans 77 B). Pila útil ~958 B.
- Dades fredes reubicades als gaps de RAM 2: `s_carry_bg_c0` (320 B a `0x8600`), `s_lv` (93 B a `0x8E80`), `g_mag_elevators` (80 B a `0x9600`), estat `s_mn_*`/`s_cd_*`/`s_rep_*` (`0x9E00`) i dades de càrrega (`0xBE10`, fora del pak). S'han afegit els resets post-load necessaris (`s_rep_n = 0`) i s'ha mogut `level_params_load()` **després dels paks ENEMI**, que trepitjaven `s_lv`.
- Eliminats `s_rep_pages[4]` (single buffer) i el seed `hud_try_copy`; `bank5_table.s` ja no escriu la pàgina. També s'han eliminat `g_split_en`, `g_play_ma`, `g_vram_base_hi`, `en2_slot_get` i el fast-path duplicat del HUD; `_CODE` final 13.960 B (632 B de marge) i `_DATA` 297 B.
- **C5 és el nou coll amagat**: el codi del món deixa L1 amb **236 B** lliures i L5 amb **300 B** (abans es documentava 3,9 KB/1,6 KB). No s'hi pot afegir codi; cal optimitzar o moure'l a C6/C1.
- Verificació: `smoke_test --dsk-only` OK; `smoke_test --boot-only` OK (`magic=0xB0`, `px8=192`); `check_c6_flag.py` OK (`magic=0xB0`, canari intacte); `check_dsk_banks.py` OK.
- Documentació: nou [`docs/MEMORY_MAP.md`](MEMORY_MAP.md); `HANDOFF.md`, `SINGLE_BUFFER.md` i `LEVEL_PACKAGE.md` actualitzats al límit de 13.536 B i al mapa de RAM 2.
- Pendent (Fase 2/3): moure codi de C0 a C6/C1 (C5 no té espai), replantejar la reubicació de HUD strips/GAMEOVER (C4 L1 només té 1.536 B i C5 L5 300 B), i el codi específic de L3 que no arriba al DSK.

---


- Documentació completa de l'arquitectura i del nou mapeig de RAM 2/RAM 0/C6 a [`docs/SINGLE_BUFFER.md`](SINGLE_BUFFER.md).
- Eliminat el desdoblament/parpelleig de Jake (inclòs amb caixa/globus/paraigua) movent `crtc_set_display_start` a l'inici de `render_frame()` (`g_irq_phase == 5`), unificant `draw_fg_sprites` i ampliant la comprovació vertical `g_jake_en_near`.
- Eliminat el tremolor del HUD en scroll horitzontal (`hud_render` abans de `sync_backbuffer`) i en scroll vertical (`dy > 0`: `hud_render` + `early_jake` + `render_rows_edge(19..18)` abans dels restores; `dy < 0`: `render_rows_edge(0..-dy-1)` primer).
- Reubicat `_DATA` a `0x3800` i `CANARY_ADDR` a `0x3C40` (`_CODE` `14.003 B`, `77 B` de marge).

---

### 14/11/2026 — Batch de proves d'usuari: bazuka, bola, rata, guardià, respawn i items de sala

1. **Bazuka (L3)**: el tret passa a **horitzontal** (`s_proj.vy = 0`; el DOS
   ho fa a `unk42 == 2`) i la caixa puja a `peus-28..peus-18` (tipus 2, 10 px):
   Jake dret el rep, ajupit passa per sota.
2. **Bola del presidiari**: cela **13** (la 15 era buida), base a `peus-3`,
   visible i arran de terra.
3. **Rata boja**: eliminat el teletransport `bc_a±80` de `en2_room_exit` que la
   deixava dins una paret.
4. **Guardià L3 slot 27**: `ENEMY_N` 26→27 amb slots de fons empaquetats
   (`slot_bits`); el t3 de (800,864) ja apareix a (392,832).
5. **Respawn de checkpoint**: es desa la posició/camera reals en tocar-lo i es
   restaura al respawn (el `restart_*` estàtic quedava dins el mur).
6. **Items de sala**: `check_room_bonus` prova les dues columnes de Jake i la
   fila dels peus; `pack_level.py` detecta el tile real de cada sala (L1 208,
   L3 0xB5/+1, L4 233, L5 24/65) i el `bg_tile` de substitució. El **+50**
   de L3 (tile 0x90, popup) queda pendent (camp únic i resident suma 1).
7. **Capa base del bazuka**: identificat que el tile dels peus és foreground
   (`0x9A = 0x80|0x1A`); pedaç parcial que pinta la base CK1 sota l'enemic als
   slots 7/14/22. El blit emmascarat de la barana CK2 queda pendent.
8. **Build/regressió**: `build.py` passa `-DLEVEL_ID` al mòdul d'enemics;
   `smoke_test --dsk-only`, `check_dsk_banks` i `check_c6_flag` OK; L3 carrega
   i corre 25 s amb el canari intacte.

---

### 13/11/2026 — CRÍTIC: freezes/resets en carregar L2-L6 (fals `code_ready`)

1. **Símptoma**: L1 arrenca, però seleccionar qualsevol altre nivell (número+espai
   al selector) peta just en carregar: a vegades congelat, a vegades reset a BASIC
   o barres de color.
2. **Causa**: `main.c` es saltava la càrrega del codi compartit de C6 si el byte
   `C6:0x5A00` era `0xC3`:
   `u8 code_ready = (*(const u8*)0x5A00 == 0xC3);`
   Aquest byte pot ser `0xC3` per RAM inicialitzada o per dades del FRONT, i llavors
   s'executava brossa a `0x5A00` → reset a BASIC. L1 no ho patia perquè no fa la
   comprovació.
3. **Reproducció determinista**: escriure `0xC3` a `C6:0x5A00` (físic `0x19A00`) i
   carregar L2 deixa exactament l'estat del crash: `magic=0x3C`, `px8=3120`,
   canari `e0606c...`, PC a la ROM (`0x1BD6`).
4. **Correcció**: carregar SEMPRE el codi compartit (`load_level_file(0,1)`) per a
   `lvl != 0`; s'elimina l'optimització fràgil. Cost: una lectura redundant de
   L1ENEMI (~8 KB) en els nivells 2-6.
5. **Verificat**: amb `0xC3` forçat a `0x5A00`, el joc carrega L2/L3 i corre; el
   selector número+espai ja no reseteja.

---

### 13/11/2026 — Celes d'enemics de L3 corregides (el policia alternava amb la rata)
1. **Diagnòstic** ([`tools/check_enemy_cells.py`](../tools/check_enemy_cells.py), eina nova):
   identifica cada cel·la d'`ENEMI<n>.BIN` amb el frame DOS que li correspon
   (`staticres.c` → `animframes_059d`) i confronta la taula de spawns
   (`tools/gen_enemy_spawn.py`) amb el contingut real de les cel·les.
2. **Bug corregit a L3 (presó)**: la taula de spawns apuntava a cel·les d'un altre
   tipus d'enemic.
   - `t4` (presidiari/policia, op3) caminava amb les cel·les **5 i 6**: la 5 és la
     seva propia pose de tret i la 6 és **la rata** → el policia alternava el seu
     fotograma amb el de la rata. Ara camina amb les cel·les **3 i 4** i fa el tret
     amb la **5**.
   - `t6` (rata, op1) caminava amb les cel·les **13 i 14**: la 13 és la cel·la de
     **projectils** i la 14 és buida → **la rata sortia dibuixada com tots els
     projectils**. Ara camina amb les cel·les **6 i 7** (el seu sprite real).
3. **Bazuka de L3 implementada (op3, 13/11/2026)**: el presidiari (tipus 4) ara fa
   servir el comportament `object_func_op3` (rang `ydist<=20`, `>-160`,
   `xdist<160`, sense exigir encarament previ) i dispara el **coet del frame 13**
   de l'SQV en diagonal (xvelocity = yvelocity = 64), amb la cel·la **14** (abans
   buida) afegida al PNG master i al binaire. Tipus nou `kind 26`.
4. **Auditoria dels 6 nivells**: 0 referències a cel·les incorrectes. (L4: `t26` i
   `t34` comparteixen el mateix sprite DOS — no és un error.)
4. **Eines noves**: `check_enemy_cells.py` (auditoria de cel·les), `peek_enemy.py` i
   `check_l3_enemies.py` (captures a ZEsarUX amb teletransport).
5. **Verificat**: `smoke_test --dsk-only` OK; a ZEsarUX la rata ja es dibuixa amb el
   seu sprite i el policia amb els seus propis fotogrames.
6. **Protecció del master editat**: `gen_enemy3_frames.py` (28/10) descrivia un
   repartiment de cel·les diferent del fitxer del disc. Ara el repartiment de `CELLS`
   és el real, però **l'script no escriu per defecte** (només avisa de la divergència;
   cal `--force`). El motiu: `assets/bbdata/ENEMI3.BIN` es va generar a partir del
   **PNG editat** (`edit/enemies_cpc.png`, commit `5181c3e`), que fa servir els pens
   `{0,1,2,3,4,5,7,10,13}` en lloc del mapatge semàntic DOS
   `{0,1,4,9,10,11,12,13}`. Regenerar des del DOS destruiria l'art editat.
7. **Correcció del mapa de comportaments d'L3 (13/11/2026)**: la decompilació té els
   noms de funció desplaçats (`switch (obj->op - 1)` → `object_func_opN` implementa
   **op N+1**). La taula real és:
   | Tipus | Op | Comportament | CPC |
   |---|---|---|---|
   | t3 (escut) | op2 | patrulla | kind 18 |
   | t4 (policia) | op3 | patrulla i dispara (com L1) | kind 4 |
   | t5 (bazuka) | op4 | estàtic + dispara en camp de visió | kind 26 (coet, cela 14) |
   | t6 (rata) | op1 | patrulla | kind 24 |
   | t23 (presidiari) | op11 | estàtic + llança la bola en camp de visió | kind 17 + throw_cell 10 (bola, cela 15) |
   Els sprites dels projectils són el **frame SQV 25** (coet) i el **frame SQV 22**
   (bola amb cadena), extrets amb `tools/add_l3_projectiles.py` a les cel·les 14/15.
   C6 va just: `enemy.c` es compila amb `--max-allocs-per-node 40000` (SDCC genera
   ~225 B menys) i el codi acaba a `0x78B2` (78 B lliures).

### 12/11/2026 — Auditoria i ajust de les paletes Mode 0 (contracte de pens, colors duplicats, coherència PNG↔binari)
1. **Diagnòstic** ([`tools/palette_audit.py`](../tools/palette_audit.py)):
   - El pipeline quantitza cada píxel del PNG editat al **pen més proper de la paleta**: un color que no hi és **es canvia en silenci**, i la paleta és la font de veritat dels colors (no el PNG).
   - `palette.json` del jugador és només el mapa d'importació RGB→pen; la paleta de runtime és `LEVEL_PALETTES[nivell]` → `s_lv.palette`.
   - Contracte d'identitat real: Jake `0,1,4,5,11,12` · Elwood `0,1,4,5,10,11,13` · HUD `0,1,2,4,7,11,12,13` · enemics `0,1,4,9,10,11,12,13`.
2. **Correccions**:
   - **L4 no tenia blau marí a la paleta**: 9.465 px d'art editat (blau marí `#000080`) es convertien en **cian**, i el **vestit de Jake/Elwood sortia cian** a les clavegueres. Afegit `pen 4 = 0x44` (com al DOS, on l'índex 4 és blau fosc a tots els nivells).
   - **PNG d'enemics obsolets a L2 i L4**: els `edit/enemies_cpc.png` eren l'art anterior a l'extracció DOS 1:1 del 12/11, i `import` **regressava** l'art. Nou `tools/refresh_enemy_png.py` per reexportar-los des dels binaris.
   - **Paletes reajustades** als colors reals de l'art ([`tools/palette_fit.py`](../tools/palette_fit.py)): els 6 nivells passen a **16 colors únics de 16 pens** (L4 passava de 8, L2 de 9, L6 de 11).
   - Escripta la proposta a les tres fonts (`pack_level.py`, `graphics_tool.py`, `palette.json`) i reimportat l'art.
3. **Documentació**: nova secció 4.2 al handoff (eines de paletes) i informe complet a [`docs/AUDITORIA_PALETES.md`](AUDITORIA_PALETES.md).
4. **Eines noves**: `palette_audit.py` (auditoria), `palette_fit.py` (ajust + previews), `refresh_enemy_png.py` (reexportació d'enemics), `reimport_level.py` (import per nivell) i `verify_palettes.py` (verificació a ZEsarUX).
5. **Verificació**: `smoke_test --dsk-only` i `--boot-only` verds; `palette_audit` amb 0 PNG desincronitzats i 16/16 colors únics als 6 nivells; `verify_palettes.py` confirma que la paleta a la VRAM és idèntica a l'esperada als 6 nivells i que el contracte `0/1/4/11` es compleix a tots.

### 12/11/2026 — Mecàniques 1:1 DOS a Nivell 2, Clipping Reixa L1 i Projectils
1. **Nivell 2 (Fàbrica / ENT)**:
   - **Rampes diagonals del sostre (`op 32..39`)**: implementades de manera suau al Banc 5 (`src/moving_bank.c`, `engine/tile_blit.s`), sense esglaons en lliscar i usant `g_on_ice = 2` (`src/main.c`) per a l'impuls de pendent.
   - **Gel (`g_on_ice = 1`)**: ajustada l'inèrcia, la retenció d'inici/frenada (`acc = 1`) i l'aterratge lliscós (`s_on_ground || s_vy > 0` a `src/moving_bank.c` i `engine/bank5_table.s`).
   - **Xemeneia amb scroll fins a les banderes**: entrada ocultant en Jake (`jcol` centrat, `jrow >= 8`, `jx < 80 * 8` per evitar activació fora de lloc) i desplaçament amb scroll fins a la sortida correcta a la zona de banderes.
   - **Premses**: restringides a `level_idx == 1` a `tools/pack_level.py`.
2. **Reixa de Primer Pla a Magasin L1 (`engine/sprite.s`, `src/moving_bank.c`)**:
   - Afegit clipping per meitats (`_g_grate_left` / `_g_grate_right` amb `s_grate_buf`) perquè la textura de reixa no sobresurti fora dels llindars de les portes.
3. **Enemics i Projectils 1:1 DOS (`src/enemy.c`, `assets/bbdata/ENEMI2.BIN`, `ENEMI4.BIN`)**:
   - Comprovació d'encarament (`facing_jake`) abans d'entrar en rang i tipificació 1:1 de projectils segons `throw_cell` (`12` pistola pneumàtica, `6` mecànic, `9` obrer, `4` i plat L1).
   - Actualitzats els fulls d'enemics L2/L3/L4 a `graphics_edit/` i els scripts `tools/extract_dos_enemies.py` / `tools/gen_enemy2_frames.py`.
4. **Documentació ZRCP**: afegit [`docs/ZESARUX_ZRCP.md`](ZESARUX_ZRCP.md).

### 10/11/2026 — Harmonització Paletes Mode 0 (L1-L3) i Eines Gràfiques
1. **Paletes Mode 0**:
   - **L2 (Fàbrica / ENT)**: corregit `LEVEL_PALETTES[1]` a `tools/pack_level.py` (pens 13/14 vermell `0x5C`, pen 4 blau marí `0x44`, pen 8 blau cel `0x57`).
   - **L3 (Presó / PRISON)**: auditoria creuada tileset/enemics/jugador (14 colors reals, coincidència 100%).
2. **Eines Gràfiques i Extracció DOS**: creat `tools/graphics_tool.py`, scripts `extract_dos_*.py` i directori `graphics_edit/`.

### 08/11/2026 — Diagnosi Reixa Magasin, Paleta L5 i Policies Tiradors (`object_func_op2`)
- Analitzada l'aproximació de reixa de primer pla (`g_grate_enable` / `blit_grate_line`).
- Corregida la paleta de L5 (teulades) fidel als 10 colors del tileset.
- Ajustat `SHOOT_CYCLE_FRAMES = 24` a `src/enemy.c` (12 frames apuntar + 12 cooldown immòbil, sense caminar entre trets).

### 06/11/2026 — Optimització del Build i Fixes de Gameplay
- **Build ràpid (de ~3 h a ~6,7 s incrementals)**: compressor `tools/zx0_native.cs`, memòria cau SHA-256 (`obj/.zx0_cache/`), `_write_if_changed` a `pack_level.py` i bucle CHS optimitzat a `build.py`.
- **Fixes**: buffer de projectil `s_proj_bg` reubicat fora de `0x7800` a C6; colors de `MAPSTICK.BIN`; restauració de `BC` a `_b5_world_reset_tile`; detecció de peu esquerre `px + 5` a `src/main.c`.
- **Nivell 6 (Concert) i Disc Únic**: codi compartit d'enemics `ENEMYCODE.BIN` a `C6:0x5A00` i endgame `trigger_func_op40` integrats.

### 02/11/2026 — Comportes L4 i Línia de Flotació Natació (1:1 DOS)
- Eliminada la comprovació de `feet_row` a la col·lisió horitzontal de parets/comportes.
- Línia de flotació a la superfície (`((cr + 1) << 4) - 8`), permetent emergir el cap sense sortir per l'aire.

### 01/11/2026 — Trampolins L2 (`op 24`) i Comportes Automàtiques L4
- Trampolins amb rebot progressiu de 3 altures (`VY_MAX_UP = 21 * SUB`).
- Comportes automàtiques L4 integrades a `DOS_ANIM_SEQS`.
