# Registre Històric de Canvis — Blues Brothers CPC

Aquest fitxer recull el detall cronològic de les sessions i fites del projecte. Per a l'estat actual, regles i arquitectura vigent, consulta [`docs/HANDOFF.md`](HANDOFF.md).

---

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
