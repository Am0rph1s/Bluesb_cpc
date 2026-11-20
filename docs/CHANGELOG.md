# Registre HistÃ²ric de Canvis â€” Blues Brothers CPC

Aquest fitxer recull el detall cronolÃ²gic de les sessions i fites del projecte. Per a l'estat actual, regles i arquitectura vigent, consulta [`docs/HANDOFF.md`](HANDOFF.md).

---

### 20/11/2026 - F1: musica 50 Hz exactes ancorada al VSYNC (port del master) + tecnica d'entrada al FRONT des de l'emu

**F1 (engine/isr.s)**: eliminat `_mus_div` (divisor lliure: derivava respecte el frame amb les
finestres DI de la carrega; mesurat 19/11: fase {1,2,3} variable a l'anchor de render) i
sincronitzat el tick de musica a `_g_irq_phase == 2`, lligada al VSYNC via el PPI (0xF5 bit 0).
+12 B de _CODE (GAME_START 0x1211 -> 0x121D); _DATA sense canvi de layout (1 B per 1 B).
**Verificat amb cpcse (L1 carregat)**: `_mus_play` a deltas EXACTES de 6 ticks (15/15 mostres)
= 50,0 Hz clavades; fase constant a l'anchor de render. El mateix `hold`/`ready` guards.

**Tecnica d'entrada al FRONT des de l'emulador (apresa a pells, per futures sessions)**:
- El feed de tecles de cpcse (`press_key` i `key <nom>=<valor>`) NO alimenta la matriu PSG
  que llegeix `f_fkey_pressed` (A=0xFF amb la tecla "premuda"); el `type_text` de l'arrencada
  va pel buffer del firmware i si que funciona. Conclusio: NO confiar en events de tecla per
  entrar al joc; conduir els gates per RAM.
- El FRONT (`front_run`) carrega ELL MATEIX el MUSBANK (`f_load(musbank, C1, 0x4000)`):
  MAI saltar-se'l amb un bypass de PC (provat: mus_init posterior -> _akg_init a C1:0x4009 =
  brossa -> reinici a BASIC). El mapa fa auto-exit (~4 s, `f_map_wait(1)`), pero el map dins
  `front_run` usa `f_map_wait(0)` (press-wait real).
- **Recepta que funciona**: al bp del `call 0x4000` (0x29D3 amb aquest layout), patchejar
  `f_fkey_pressed` (0x4006, banc C4 mapejat) amb `LD A,(0x49A0); RET; NOP` (bytes 3A A0 49
  C9 00) = retorna `f_fkres` (0x49A0) que nosaltres pokegem. Els gates son
  [release=0][press=1] en cadena: splash -> select -> map. Alternar f_fkres 0/1 (0=passa
  release, 1=passa press/break del select) amb gaps de ~45 frames fins magic 0xB0.
  Gate final vist: map press-wait (0x4627). El joc in-level no usa f_fkey (usa
  cpct_scanKeyboard, no patchejat): el patch nomes afecta el FRONT.
- Trajectoria del walker L1 (referencia per gates visuals): e[0]@456, patrulla amb gir a ~536.

**Seguent (objectius mesurats 19/11, pendents)**: dirty-flag del `sprite_restore_player`
(~4 ms), `moving_draw_conveyor_tiles` bimodal 3/10 ms, fusio de probes de
`player_physics_step` (~2 ms), early-out del hit-check (~1 ms). Total ~10-12 ms -> 25 fps.


### 19/11/2026 - Arrencada neta d'obj/, baseline de rendiment mesurada i objectius revisats (cpcse)

**Context**: sessio d'optimitzacio iniciada desde la linia `master` (port del walker_sense);
canvi de rumb a `fix-c1-l3-unlock` (la linia viva del projecte) despres de confirmar que
conte tot el contingut 1:1 DOS. La feina del master queda registrada alla (7e67267, donor).

**Arrencada del build desde obj/ buit (ou-gallina del `bank_equ`)**: `build_music` necessita
`obj/bluesb.map` (via `build_bank_equ`) pero el mapa nomes el escriu l'enllac resident,
que alhora necessita `obj/mus_ext.s` + `obj/hud_ext.s` + `obj/enemy_ext.s` (generats mes
endavant al propi flux). Amb obj/ net el build pet a `map_symbols`. Llavors:
1. Escriure `obj/mus_ext.s` a ma amb els valors REALS de l'AKG (`_akg_init=0x4009`,
   `_akg_play=0x40CE`, `_akg_stop=0x40BC`; constants fixes del asset).
2. Escriure `obj/hud_ext.s` amb placeholders als noms **_o** (`_hud_init_o` etc.; el
   generador defineix la CLAU del dict, no el valor _b!).
3. `enemy_ext.s` amb la llavor oficial del propi build.py.
4. `py -c "import build; build.compile_and_link(False)"` -> escriu `obj/bluesb.map` valid
   (els EQUs placeholder no mouen el layout: son constants de 2 B) i el build complet
   convergeix amb el seu bucle de 8 iteracions.

**Mina latent trobada: `gen_enemy4_frames.py` no reprodueix l'art comes d'ENEMI4.BIN**
(677 B de diferencia): el casament de paletes del 12/11 (`d366f74`) es va cometre directament
al .BIN sense actualitzar el generador, que encara emet els pens crus del SQV. Amb
`obj/.src_hashes.json` esborrat el build REGENERA l'asset i pisa l'art verificat.
Proteccio aplicada: `git checkout` del .BIN + `build.mark_fresh(ENEMI4.BIN, [gen4, sqv4])`.
**Pendent**: actualitzar el generador amb el remap de pens (o congelar l'asset al repo i
treure'l del flux de regeneracio).

**Deriva de taules comeses**: el build net desde les fonts comeses dona CRC_MUS/MUSBANK
`0xAF7A` (comes: 0x9EE9), CRC_L2WORLD `0xFE09` (comes: 0x905C) i CRC_L4/L5/L6ENEMI nous:
les taules comeses venen d'un build amb fonts locals no comeses (estat WIP perdut).
El build actual es autoconsistent (starter valida GAME_CRC + arrenca) i amb l'art verificat
d'ENEMI4. Taules regenerades comeses en aquest commit.

**Eines**: `tools/cpcse_dbg.py` (portat de la linia master): client de l'API de
CPCSyntaxError + exportador de simbols (`bluesb.noi` -> `bluesb.sym`). Entrada directa
al nivell: poke `_g_map_level` (0x3AB5) + Space (la drecera 1..6 llegeix un sol scan just
despres del FRONT). Teclat amb hold: `key <nom>=1/0` per l'API.

**BASELINE de rendiment (cpcse, anchors de fase amb `g_ticks` 300 Hz, L1 idle amb el
walker del carrer (e[0]@456) visible, camera assentada, invulnerable)**:
- Periode: **~59-60 ms = ~17 fps** (coincideix amb el "quiet 16,8 fps" historic del
  PERF_REPORT) - el meu build net es representatiu del seu estat.
- Descomposicio del frame: `enemy_update` **3 ms** (ja rapid: les Opcio A van funcionar),
  `enemy_check_player_hit` 3 ms, `player_physics_step` 3 ms, `sprite_restore_player`
  **4 ms** (redibuixa els tiles sota Jake cada frame encara que no es mogui),
  `moving_restore`+popup+`sync_backbuffer` 7 ms, dibuixos+HUD ~12, espera VSYNC ~25.
- La feina real (~30 ms) desborda JUST el marc de 40 ms -> el frame cau al bucket de 60.
  **Retallar ~10-12 ms de feina -> 25 fps exactes.**
- Objectius mesurats (per ordre de guany): (1) dirty-flag del `sprite_restore_player`
  quan pos+anim+pagina no canvien (~4 ms), (2) skip del `sync_backbuffer` en repòs (~3-5),
  (3) fusio de probes de tile de `player_physics_step` (~2 ms, mateixa recepta que el
  walker_sense del master pero per al jugador), (4) early-out del hit-check (~1 ms).
- **Descartat amb dades**: el port del `walker_sense` del master (l'estalvi aqui seria
  ~1-2 ms; l'update d'enemics ja es de 3 ms).
- Musica: `_mus_div` a l'anchor de render varia {1,2,3} -> la fase del tick de musica NO
  esta lligada al frame (deriva). El port F1 del master (PPI-sync, `_g_irq_phase`,
  musica a fase 2, ~+12 B de _CODE) hi aplica com a millora de qualitat.
- Trajectoria del walker capturada com a referencia per als gates visuals: 496->536
  (gira a la vora real)->444->... y8 estable, cap caiguda.


### 13/11/2026 â€” CRÃTIC: freezes/resets en carregar L2-L6 (fals `code_ready`)

1. **SÃ­mptoma**: L1 arrenca, perÃ² seleccionar qualsevol altre nivell (nÃºmero+espai
   al selector) peta just en carregar: a vegades congelat, a vegades reset a BASIC
   o barres de color.
2. **Causa**: `main.c` es saltava la cÃ rrega del codi compartit de C6 si el byte
   `C6:0x5A00` era `0xC3`:
   `u8 code_ready = (*(const u8*)0x5A00 == 0xC3);`
   Aquest byte pot ser `0xC3` per RAM inicialitzada o per dades del FRONT, i llavors
   s'executava brossa a `0x5A00` â†’ reset a BASIC. L1 no ho patia perquÃ¨ no fa la
   comprovaciÃ³.
3. **ReproducciÃ³ determinista**: escriure `0xC3` a `C6:0x5A00` (fÃ­sic `0x19A00`) i
   carregar L2 deixa exactament l'estat del crash: `magic=0x3C`, `px8=3120`,
   canari `e0606c...`, PC a la ROM (`0x1BD6`).
4. **CorrecciÃ³**: carregar SEMPRE el codi compartit (`load_level_file(0,1)`) per a
   `lvl != 0`; s'elimina l'optimitzaciÃ³ frÃ gil. Cost: una lectura redundant de
   L1ENEMI (~8 KB) en els nivells 2-6.
5. **Verificat**: amb `0xC3` forÃ§at a `0x5A00`, el joc carrega L2/L3 i corre; el
   selector nÃºmero+espai ja no reseteja.

---

### 13/11/2026 â€” Celes d'enemics de L3 corregides (el policia alternava amb la rata)
1. **DiagnÃ²stic** ([`tools/check_enemy_cells.py`](../tools/check_enemy_cells.py), eina nova):
   identifica cada celÂ·la d'`ENEMI<n>.BIN` amb el frame DOS que li correspon
   (`staticres.c` â†’ `animframes_059d`) i confronta la taula de spawns
   (`tools/gen_enemy_spawn.py`) amb el contingut real de les celÂ·les.
2. **Bug corregit a L3 (presÃ³)**: la taula de spawns apuntava a celÂ·les d'un altre
   tipus d'enemic.
   - `t4` (presidiari/policia, op3) caminava amb les celÂ·les **5 i 6**: la 5 Ã©s la
     seva propia pose de tret i la 6 Ã©s **la rata** â†’ el policia alternava el seu
     fotograma amb el de la rata. Ara camina amb les celÂ·les **3 i 4** i fa el tret
     amb la **5**.
   - `t6` (rata, op1) caminava amb les celÂ·les **13 i 14**: la 13 Ã©s la celÂ·la de
     **projectils** i la 14 Ã©s buida â†’ **la rata sortia dibuixada com tots els
     projectils**. Ara camina amb les celÂ·les **6 i 7** (el seu sprite real).
3. **Bazuka de L3 implementada (op3, 13/11/2026)**: el presidiari (tipus 4) ara fa
   servir el comportament `object_func_op3` (rang `ydist<=20`, `>-160`,
   `xdist<160`, sense exigir encarament previ) i dispara el **coet del frame 13**
   de l'SQV en diagonal (xvelocity = yvelocity = 64), amb la celÂ·la **14** (abans
   buida) afegida al PNG master i al binaire. Tipus nou `kind 26`.
4. **Auditoria dels 6 nivells**: 0 referÃ¨ncies a celÂ·les incorrectes. (L4: `t26` i
   `t34` comparteixen el mateix sprite DOS â€” no Ã©s un error.)
4. **Eines noves**: `check_enemy_cells.py` (auditoria de celÂ·les), `peek_enemy.py` i
   `check_l3_enemies.py` (captures a ZEsarUX amb teletransport).
5. **Verificat**: `smoke_test --dsk-only` OK; a ZEsarUX la rata ja es dibuixa amb el
   seu sprite i el policia amb els seus propis fotogrames.
6. **ProtecciÃ³ del master editat**: `gen_enemy3_frames.py` (28/10) descrivia un
   repartiment de celÂ·les diferent del fitxer del disc. Ara el repartiment de `CELLS`
   Ã©s el real, perÃ² **l'script no escriu per defecte** (nomÃ©s avisa de la divergÃ¨ncia;
   cal `--force`). El motiu: `assets/bbdata/ENEMI3.BIN` es va generar a partir del
   **PNG editat** (`edit/enemies_cpc.png`, commit `5181c3e`), que fa servir els pens
   `{0,1,2,3,4,5,7,10,13}` en lloc del mapatge semÃ ntic DOS
   `{0,1,4,9,10,11,12,13}`. Regenerar des del DOS destruiria l'art editat.
7. **CorrecciÃ³ del mapa de comportaments d'L3 (13/11/2026)**: la decompilaciÃ³ tÃ© els
   noms de funciÃ³ desplaÃ§ats (`switch (obj->op - 1)` â†’ `object_func_opN` implementa
   **op N+1**). La taula real Ã©s:
   | Tipus | Op | Comportament | CPC |
   |---|---|---|---|
   | t3 (escut) | op2 | patrulla | kind 18 |
   | t4 (policia) | op3 | patrulla i dispara (com L1) | kind 4 |
   | t5 (bazuka) | op4 | estÃ tic + dispara en camp de visiÃ³ | kind 26 (coet, cela 14) |
   | t6 (rata) | op1 | patrulla | kind 24 |
   | t23 (presidiari) | op11 | estÃ tic + llanÃ§a la bola en camp de visiÃ³ | kind 17 + throw_cell 10 (bola, cela 15) |
   Els sprites dels projectils sÃ³n el **frame SQV 25** (coet) i el **frame SQV 22**
   (bola amb cadena), extrets amb `tools/add_l3_projectiles.py` a les celÂ·les 14/15.
   C6 va just: `enemy.c` es compila amb `--max-allocs-per-node 40000` (SDCC genera
   ~225 B menys) i el codi acaba a `0x78B2` (78 B lliures).

### 12/11/2026 â€” Auditoria i ajust de les paletes Mode 0 (contracte de pens, colors duplicats, coherÃ¨ncia PNGâ†”binari)
1. **DiagnÃ²stic** ([`tools/palette_audit.py`](../tools/palette_audit.py)):
   - El pipeline quantitza cada pÃ­xel del PNG editat al **pen mÃ©s proper de la paleta**: un color que no hi Ã©s **es canvia en silenci**, i la paleta Ã©s la font de veritat dels colors (no el PNG).
   - `palette.json` del jugador Ã©s nomÃ©s el mapa d'importaciÃ³ RGBâ†’pen; la paleta de runtime Ã©s `LEVEL_PALETTES[nivell]` â†’ `s_lv.palette`.
   - Contracte d'identitat real: Jake `0,1,4,5,11,12` Â· Elwood `0,1,4,5,10,11,13` Â· HUD `0,1,2,4,7,11,12,13` Â· enemics `0,1,4,9,10,11,12,13`.
2. **Correccions**:
   - **L4 no tenia blau marÃ­ a la paleta**: 9.465 px d'art editat (blau marÃ­ `#000080`) es convertien en **cian**, i el **vestit de Jake/Elwood sortia cian** a les clavegueres. Afegit `pen 4 = 0x44` (com al DOS, on l'Ã­ndex 4 Ã©s blau fosc a tots els nivells).
   - **PNG d'enemics obsolets a L2 i L4**: els `edit/enemies_cpc.png` eren l'art anterior a l'extracciÃ³ DOS 1:1 del 12/11, i `import` **regressava** l'art. Nou `tools/refresh_enemy_png.py` per reexportar-los des dels binaris.
   - **Paletes reajustades** als colors reals de l'art ([`tools/palette_fit.py`](../tools/palette_fit.py)): els 6 nivells passen a **16 colors Ãºnics de 16 pens** (L4 passava de 8, L2 de 9, L6 de 11).
   - Escripta la proposta a les tres fonts (`pack_level.py`, `graphics_tool.py`, `palette.json`) i reimportat l'art.
3. **DocumentaciÃ³**: nova secciÃ³ 4.2 al handoff (eines de paletes) i informe complet a [`docs/AUDITORIA_PALETES.md`](AUDITORIA_PALETES.md).
4. **Eines noves**: `palette_audit.py` (auditoria), `palette_fit.py` (ajust + previews), `refresh_enemy_png.py` (reexportaciÃ³ d'enemics), `reimport_level.py` (import per nivell) i `verify_palettes.py` (verificaciÃ³ a ZEsarUX).
5. **VerificaciÃ³**: `smoke_test --dsk-only` i `--boot-only` verds; `palette_audit` amb 0 PNG desincronitzats i 16/16 colors Ãºnics als 6 nivells; `verify_palettes.py` confirma que la paleta a la VRAM Ã©s idÃ¨ntica a l'esperada als 6 nivells i que el contracte `0/1/4/11` es compleix a tots.

### 12/11/2026 â€” MecÃ niques 1:1 DOS a Nivell 2, Clipping Reixa L1 i Projectils
1. **Nivell 2 (FÃ brica / ENT)**:
   - **Rampes diagonals del sostre (`op 32..39`)**: implementades de manera suau al Banc 5 (`src/moving_bank.c`, `engine/tile_blit.s`), sense esglaons en lliscar i usant `g_on_ice = 2` (`src/main.c`) per a l'impuls de pendent.
   - **Gel (`g_on_ice = 1`)**: ajustada l'inÃ¨rcia, la retenciÃ³ d'inici/frenada (`acc = 1`) i l'aterratge lliscÃ³s (`s_on_ground || s_vy > 0` a `src/moving_bank.c` i `engine/bank5_table.s`).
   - **Xemeneia amb scroll fins a les banderes**: entrada ocultant en Jake (`jcol` centrat, `jrow >= 8`, `jx < 80 * 8` per evitar activaciÃ³ fora de lloc) i desplaÃ§ament amb scroll fins a la sortida correcta a la zona de banderes.
   - **Premses**: restringides a `level_idx == 1` a `tools/pack_level.py`.
2. **Reixa de Primer Pla a Magasin L1 (`engine/sprite.s`, `src/moving_bank.c`)**:
   - Afegit clipping per meitats (`_g_grate_left` / `_g_grate_right` amb `s_grate_buf`) perquÃ¨ la textura de reixa no sobresurti fora dels llindars de les portes.
3. **Enemics i Projectils 1:1 DOS (`src/enemy.c`, `assets/bbdata/ENEMI2.BIN`, `ENEMI4.BIN`)**:
   - ComprovaciÃ³ d'encarament (`facing_jake`) abans d'entrar en rang i tipificaciÃ³ 1:1 de projectils segons `throw_cell` (`12` pistola pneumÃ tica, `6` mecÃ nic, `9` obrer, `4` i plat L1).
   - Actualitzats els fulls d'enemics L2/L3/L4 a `graphics_edit/` i els scripts `tools/extract_dos_enemies.py` / `tools/gen_enemy2_frames.py`.
4. **DocumentaciÃ³ ZRCP**: afegit [`docs/ZESARUX_ZRCP.md`](ZESARUX_ZRCP.md).

### 10/11/2026 â€” HarmonitzaciÃ³ Paletes Mode 0 (L1-L3) i Eines GrÃ fiques
1. **Paletes Mode 0**:
   - **L2 (FÃ brica / ENT)**: corregit `LEVEL_PALETTES[1]` a `tools/pack_level.py` (pens 13/14 vermell `0x5C`, pen 4 blau marÃ­ `0x44`, pen 8 blau cel `0x57`).
   - **L3 (PresÃ³ / PRISON)**: auditoria creuada tileset/enemics/jugador (14 colors reals, coincidÃ¨ncia 100%).
2. **Eines GrÃ fiques i ExtracciÃ³ DOS**: creat `tools/graphics_tool.py`, scripts `extract_dos_*.py` i directori `graphics_edit/`.

### 08/11/2026 â€” Diagnosi Reixa Magasin, Paleta L5 i Policies Tiradors (`object_func_op2`)
- Analitzada l'aproximaciÃ³ de reixa de primer pla (`g_grate_enable` / `blit_grate_line`).
- Corregida la paleta de L5 (teulades) fidel als 10 colors del tileset.
- Ajustat `SHOOT_CYCLE_FRAMES = 24` a `src/enemy.c` (12 frames apuntar + 12 cooldown immÃ²bil, sense caminar entre trets).

### 06/11/2026 â€” OptimitzaciÃ³ del Build i Fixes de Gameplay
- **Build rÃ pid (de ~3 h a ~6,7 s incrementals)**: compressor `tools/zx0_native.cs`, memÃ²ria cau SHA-256 (`obj/.zx0_cache/`), `_write_if_changed` a `pack_level.py` i bucle CHS optimitzat a `build.py`.
- **Fixes**: buffer de projectil `s_proj_bg` reubicat fora de `0x7800` a C6; colors de `MAPSTICK.BIN`; restauraciÃ³ de `BC` a `_b5_world_reset_tile`; detecciÃ³ de peu esquerre `px + 5` a `src/main.c`.
- **Nivell 6 (Concert) i Disc Ãšnic**: codi compartit d'enemics `ENEMYCODE.BIN` a `C6:0x5A00` i endgame `trigger_func_op40` integrats.

### 02/11/2026 â€” Comportes L4 i LÃ­nia de FlotaciÃ³ NataciÃ³ (1:1 DOS)
- Eliminada la comprovaciÃ³ de `feet_row` a la colÂ·lisiÃ³ horitzontal de parets/comportes.
- LÃ­nia de flotaciÃ³ a la superfÃ­cie (`((cr + 1) << 4) - 8`), permetent emergir el cap sense sortir per l'aire.

### 01/11/2026 â€” Trampolins L2 (`op 24`) i Comportes AutomÃ tiques L4
- Trampolins amb rebot progressiu de 3 altures (`VY_MAX_UP = 21 * SUB`).
- Comportes automÃ tiques L4 integrades a `DOS_ANIM_SEQS`.


