# Registre Històric de Canvis — Blues Brothers CPC

Aquest fitxer recull el detall cronològic de les sessions i fites del projecte. Per a l'estat actual, regles i arquitectura vigent, consulta [`docs/HANDOFF.md`](HANDOFF.md).

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
3. **Auditoria dels 6 nivells**: 0 referències a cel·les incorrectes. (L4: `t26` i
   `t34` comparteixen el mateix sprite DOS — no és un error.)
4. **Eines noves**: `check_enemy_cells.py` (auditoria de cel·les), `peek_enemy.py` i
   `check_l3_enemies.py` (captures a ZEsarUX amb teletransport).
5. **Verificat**: `smoke_test --dsk-only` OK; a ZEsarUX la rata ja es dibuixa amb el
   seu sprite i el policia amb els seus propis fotogrames.

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
