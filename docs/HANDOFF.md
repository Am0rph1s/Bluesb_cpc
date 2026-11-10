# Handoff Global — Blues Brothers CPC (Estat Actual i Guia de Continuació)

> **Document unificat de referència per reprendre el desenvolupament**
> **Data d'actualització**: 10 de novembre de 2026
> **Branca**: `fix-c1-l3-unlock` — estat 10/11/2026 (Harmonització de paletes Mode 0 L1/L2/L3, eines gràfiques graphics_tool, extracció DOS i correcció bugs 1:1 DOS)
> **Repo**: `https://github.com/Am0rph1s/Bluesb_cpc`
> **Target**: Amstrad CPC 6128 (128 KB RAM) — Z80, Mode 0 (16 colors), SDCC 4.5.0 + sdasz80, build amb Python 3.

### Actualització 10/11/2026: Harmonització Paletes Mode 0 (L1-L3) i Eines Gràfiques
1. **Harmonització de Paletes de Mode 0 (16 colors CPC Gate Array)**:
   - **Nivell 2 (Fàbrica / ENT)**:
     - S'ha corregit `LEVEL_PALETTES[1]` a `tools/pack_level.py`: pens 13 i 14 assignats a vermell (`0x5C`), pen 4 a blau marí (`0x44`) i pen 8 a blau cel (`0x57`).
     - Això resol definitivament el problema visual on l'obrer/enemic de la planta baixa es camuflava i emborronava amb les parets i canonades verdes de la fàbrica.
   - **Nivell 3 (Presó / PRISON)**:
     - S'ha realitzat l'auditoria cromàtica creuada entre el tileset de la presó, els enemics (policies amb escut, policies armats, rates) i en Jake/Elwood.
     - Es van unificar els slots repetits o buits (eliminant el cian inutilitzat a pen 4 i duplicats innecessaris) per donar cabuda als 14 colors reals de l'escena: pen 4 blau marí (`0x44`), pen 7 vermell (`0x5C`), pen 3 blau pastel (`0x5F`). Coincidència cromàtica del 100%.
2. **Eines Gràfiques i Extracció DOS 1:1**:
   - Creat [`tools/graphics_tool.py`](../tools/graphics_tool.py) per a la importació i exportació automàtica de gràfics en Mode 0, sincronitzant paletes JSON, tilesets i enemics.
   - Creats scripts d'extracció i comparació de recursos VGA DOS originals a `tools/` (`extract_dos_enemies.py`, `extract_dos_tiles.py`, `extract_dos_players.py`).
   - Creat directori centralitzat [`graphics_edit/`](../graphics_edit/) per contenir les edicions mestres de tilesets, enemics i paletes.
3. **Verificació Funcional**:
   - Passat `tools/smoke_test.py` amb èxit complet (CRCs CCITT dels 24 fitxers de disc i verificació d'arrencada).


---

## 1. Regles d'Or No Negociables (Llegir abans de tocar codi)

1. **Fidelitat 1:1 a DOS (Prohibit inventar mecàniques)**:
   - Tota física, col·lisió, IA d'enemics, animació i sincronització de nivell prové directament del codi font original de DOS:
     - `tools/blues_dos/bb/` (`level.c`, `objects.c`, `tiles.c`, `game.c`, `staticres.c`)
     - `tools/blues_dos/ja/`
   - Mai ajustar valors a ull ni per intuïció. Per a coordenades, utilitzar la fórmula oficial:
     `cpc_x = dos_x / 2 - w_cpc / 2`, `cpc_y = dos_y - h_dos` (`docs/DOS_CPC_COORDINATES.md`).
2. **Pressupost de memòria resident (Bloc 0: `0x0000..0x3FFF`)**:
   - `_CODE`: `0x0100..0x34AC` (**13.228 B**), amb marge lliure net fins a `_DATA` (`0x3600`).
   - `_DATA`: `0x3600..0x3B15` (1.301 B, inclou `s_lv` i variables estàtiques compartides). Pila lliure: **1.257 B** (canari a `0x3B40`, intacte `0x55AA`).
   - `check_room_bonus`: restaurada amb variables estàtiques compartides (`s_crb_*`) sense cap despesa de frame de pila (0 B IX frame). Permet agafar vinils i instrument a les sales amb neteja i refresc de pantalla net (`s_rep_*`).
   - Qualsevol lògica nova no trivial s'ha de compilar en bancs superiors (C1, C4-C7), mai al resident.
3. **Regla de commutació de maquinari**:
   - Per cridar codi bancat que escriu a VRAM s'utilitza `0xC0`, mai `0xC1`
     (`0xC1` mostra la RAM 7 a `0xC000..0xFFFF` i tapa la pantalla; `0xC0` manté la VRAM visible a la pàgina 0).
   - `C2` i `C3` **no s'han de fer servir** (`OUT(0x7F00,0xC2)` penja la màquina; C3 reinicia).
4. **Idioma de comunicació**: Català.

---

## 2. Comandes Principals de Treball

```powershell
# 1. Regenerar paquets de dades d'un nivell (reordena tilesets, compacta TRIG, genera LevelParams)
py -3 tools/pack_level.py 0                       # Nivell 1
py -3 tools/pack_level.py 1 --outdir obj/lvl1     # Nivell 2
py -3 tools/pack_level.py 2 --outdir obj/lvl2     # Nivell 3
py -3 tools/pack_level.py 3 --outdir obj/lvl3     # Nivell 4

# 2. Compilar el joc complet i generar bluesb.dsk
py -3 tools/build.py                              # Build incremental
py -3 tools/build.py -f                           # Rebuild complet (recomprimeix tots els ZX0)

# 3. Validació automàtica en emulador
py -3 tools/smoke_test.py --dsk-only              # Només catàleg + CRCs del DSK
py -3 tools/smoke_test.py --boot-only             # Arrencada real a L1 (magic=0xB0)
py -3 tools/build.py --check                      # Build + validació DSK
py -3 tools/build.py --check-boot                 # Build + DSK + arrencada

# 4. Arrencar ZEsarUX amb connexió remota ZRCP (port 10000)
# Des de tools/ZEsarUX_windows-13.0:
.\zesarux.exe --machine CPC6128 --enable-dsk --dsk-file ..\..\bluesb.dsk --enable-remoteprotocol --remoteprotocol-port 10000
```

Dreceres de test a `src/main.c`: mantenir **`2`** en arrencar entra directament a L2; **`3`** entra a L3; **`4`** entra a L4; **`5`** entra a L5; **`6`** entra a L6.
Són només per a depuració i no afecten el flux normal.

### Actualització 08/11/2026: Diagnosi Reixa Magasin (CPC vs DOS) i Paleta L5
1. **Reixa de Primer Pla a Magasin L1 (Limitació de Disseny vs Bug)**:
   - *Comportament a DOS*: El DOS original fa servir una capa de primer pla real (*avant-plan*, `AVTMAG.SQV`), dibuixada a coordenades fixes de pantalla a sobre dels sprites. Això tapa automàticament qualsevol entitat (Jake, caixes agafades, enemics) i retalla de manera natural a les vores dels tiles.
   - *Aproximació a CPC (optimització de cicles)*: Donada la restricció de 25 FPS amb el Z80 a 4 MHz i memòria VRAM/RAM molt ajustada, no hi ha marge per a un segon passatge de render de primer pla amb buffers de restauració. La reixa es va implementar com una textura inline dins el propi blitter de Jake (`engine/sprite.s:blit_grate_line` amb `_grate_lut`) activada pel booleà `g_grate_enable` a `moving_bank.c:635` segons el centre de Jake.
   - *Causes de les dues anomalies observades*:
     - **Efecte estrany a les entrades/portes**: `g_grate_enable` és un booleà global per a tot el rectangle de 16 píxels d'en Jake. En entrar per la porta, tan bon punt el centre del personatge creua el límit del trigger, la reixa cobreix tot l'sprite (incloent la meitat del cos que encara sobresurt fora de la porta sobre l'aire lliure).
     - **La caixa no queda tapada**: La caixa portada es renderitza com una entitat independent a `carry_draw()` -> `moving_blit_box()`, el qual és un blitter genèric que no aplica la màscara `_grate_lut`.
   - *Millores proposades per a futures fases*:
     - Estendre `g_grate_enable` a `carry_draw()` per aplicar la màscara també a la caixa portada.
     - Implementar clipping per columnes a `blit_grate_line` basat en la distància al marge del tile per evitar que la textura sobresurti fora del llindar de les portes.
2. **Correcció de la Paleta de L5 (Ciutat / Teulades)**:
   - S'ha assignat la paleta de maquinari fidel als 10 colors del tileset editat (`tileset_edit.png`), substituint el magenta (0x58) per blau (0x44) i cian (0x46).
3. **Comportament 1:1 de Policies i Enemics Tiradors (`object_func_op2`)**:
   - *Problema previ*: Els policies patrullaven caminant cap a en Jake entre trets perquè només s'aturaven durant `AIM_FRAMES` (12 frames) i requerien estar ja encarant en Jake prèviament. Quan el projectil encara estava en vol o en cooldown, el policia avançava caminant cap al jugador, fent el joc molt més difícil i trencat respecte a DOS.
   - *Comportament original DOS*: A `tools/blues_dos/bb/objects.c` (`object_func_op2`), en entrar en Jake a la zona de tret (`player_ydist <= 20 && abs(player_xdist) < 80`), el policia gira immediatament de cara a en Jake (`facing_left = player_xdist < 0`), entra en cicle de tret (`special_anim = 2`) de 24 bucles i posteriorment en espera/recarrega (`special_anim = 3`) de 24 bucles. Mentre `special_anim != 0`, `direction_lr = 0` (immòbil absolut). En acabar el cooldown, si en Jake encara és a la zona, encadena immediatament el següent tret sense avançar mai.
   - *Solució a CPC (`src/enemy.c`)*:
     - `SHOOT_CYCLE_FRAMES = 24` (48 bucles DOS @ 50 Hz = 24 frames CPC @ 25 Hz), dividit en 12 frames d'apuntar/disparar (`AIM_FRAMES`) i 12 frames de cooldown/espera immòbil.
     - Quan en Jake és en rang (`in_range`), el tirador s'encara a en Jake (`e->dir = (dx_jake >= 0) ? 1 : -1`) i manté `dx = 0; nx = e->x;`.
     - En `en2_draw()`, només s'aplica `aim_cell`/`throw_cell` durant la fase d'apuntar (`shoot_timer > 12`); durant el cooldown es dibuixa la pose de peu estàtica (`base_cell`, `step = 0`).
     - Només quan en Jake surt del rang i el timer arriba a 0 el policia reprèn la seva patrulla habitual.

### Actualització 06/11/2026: Optimització Radical del Procés de Compilació i Correcció de Bugs de Gameplay

#### 1. Optimització del Temps de Compilació (de ~3 hores a 6 segons)
- **Diagnòstic del coll d'ampolla original**:
  - `pack_level.py` es cridava incondicionalment dins del bucle de convergència CHS/CRC de `build.py` (8 iteracions), escrivint fitxers amb `open("wb")` i alterant els timestamps (`mtime`), invalidant la memòria cau i forçant a recompilar amb SDCC i recomprimir en ZX0 els 6 nivells múltiples vegades seguides.
  - El compressor ZX0 oficial en Python pur (`tools/zx0pkg/optimize.py`) executava programació dinàmica en Python interpretat creant milions d'objectes: per als fitxers sense compressió ràpida (`quick=False`) executava **~86 milions d'iteracions en Python per fitxer**, trigant hores.
- **Solució implementada**:
  1. **Accelerador ZX0 natiu C# (`tools/zx0_native.cs`)**:
     - Implementació nactiva 1:1 de l'algorisme ZX0 oficial d'Einar Saukas amb arrays plans i compilació en memòria/optimitzada (`csc.exe /optimize+`).
     - Comprimeix blocs de 16 KB en **30–80 ms** (>1.000x més ràpid que Python interpretat) generant un flux binari 100% idèntic.
  2. **Memòria cau persistent SHA-256 (`obj/.zx0_cache/`)**:
     - Qualsevol bloc binari que ja hagi estat comprimit anteriorment es recupera del disc en **< 1 ms**, fins i tot en recompilacions forçades (`build.py -f`).
  3. **Preservació de timestamps (`_write_if_changed`)**:
     - `tools/pack_level.py` ara comprova si el contingut generat difereix del disc abans d'escriure (`TILESETC`, `MAPC`, `ROOMSC`, `TRIGC`, `RESTORE`, `level_pkg.h`, `hud_pkg.h`).
  4. **Bucle de convergència de `tools/build.py` optimitzat**:
     - La generació de paquets de nivell s'executa **abans** del bucle de convergència CHS, ja que no depèn del disc.
     - Les iteracions $it \ge 1$ desactiven `force` (`cur_force = force if it == 0 else False`), recompilant només els mòduls les taules dels quals hagin canviat realment (`main.c` / `starter.c`).
- **Resultats mesurats**:
  - Reconstrucció completa des de zero (`py -3 tools/build.py -f --check`): **5 minuts i 58 segons** (abans > 3 hores).
  - Compilació incremental habitual (`py -3 tools/build.py --check`): **6,7 segons**.
  - Catàleg i CRC de tots els fitxers del DSK verificats amb èxit (`tools/smoke_test.py --dsk-only`).

#### 2. Correcció del Bug de Congelació del Policia en Disparar (Bug 8)
- **Causa arrel trobada**: A `src/enemy.c`, el buffer de restauració del fons del projectil de bala `PROJ_BG_ADDR(p)` estava adreçat rígidament a `0x7800 + (p << 6)`. Tanmateix, el codi compilat d'enemics al banc C6 (`_CODE`) arriba fins a `0x7871`. En disparar el policia, el blitter desava el fons a `0x7800`, **sobreescrivint directament el codi executable d'enemics**.
- **Solució 1:1 DOS**: Buffer reubicat a `static u8 s_proj_bg[2][56]` i `s_cache_who` dins del segment `_DATA` de C6 (que finalitza netament abans d'`ENEMY_BASE = 0x5A00`), i `s_spawn` mogut a `0x4B20`.
- **Verificació**: Test automàtic `tools/verify_cop_shooting.py` a ZEsarUX amb Jake davant del policia (`px=240, py=1088`): el policia dispara, la bala col·lisiona amb en Jake, Jake perd cors, fa respawn i el motor continua funcionant a 50 Hz sense cap bloqueig.

#### 3. Correcció de la Nota Musical i Creus de Nivell al Menú (Bug 4)
- A `tools/gen_map_sticker.py`:
  - `VMAP_NOTE`: actualitzat a color negre (pen 5 `0x54`), fidel al disseny original de DOS (abans erròniament vermell).
  - `VMAP_DASH` (creus de nivell superat): actualitzades a vermell (pen 1 `0x5C` i pen 11 `0x4C`) en comptes de grisos.
  - Generat `assets/bbdata/MAPSTICK.BIN` (1.184 B) i integrat al DSK.

#### 4. Correcció del Tile Estrany en Agafar Caixes (Bug 5)
- **Causa arrel trobada**: A [`engine/bank5_table.s`](file:///c:/Projects/bluesb_cpc/engine/bank5_table.s), la rutina `_b5_world_reset_tile` trobava correctament el tile de fons veí (tile 20) i el desava a `C`. Immediatament després, executava `pop bc` per restaurar la fila `B = row`. Com que el `pop` recupera tant `B` com `C`, **esborrava el tile calculat a `C`** i hi posava les escombraries de la pila (la fila `70`), pintant un tile estrany de fàbrica.
- **Solució**: S'emmagatzema el tile trobat a `A` (`ld a, (hl)`), es buida la pila netament (`pop hl; pop bc; pop de`) i es transfereix `ld c, a`, restaurant netament l'asfalt/fons (`tile 20`).

#### 5. Correcció de la Plataforma Fantasma en Arrambar-se a la Paret (Bug 7)
- **Causa arrel trobada**: A [`src/main.c:642`](file:///c:/Projects/bluesb_cpc/src/main.c#L642), el mostreig del peu esquerre per a la detecció de sòl utilitzava `c_mid1 = (u16)((px + 3) >> 3)`. Com que la física 1:1 DOS atura el cos d'en Jake horitzontalment a `px + 4`, `px + 3` sobresortia 1 píxel per l'esquerra entrant dins de la columna de la paret vertical (tile 17, `op = 20`). Com que `is_floor_solid` tracta `op = 20` com a plataforma, en Jake detectava la paret com si fos un terra a la fila 80 i s'hi asseia en l'aire.
- **Solució**: Ajustat `c_mid1 = (u16)((px + 5) >> 3)` (el peu esquerre real, dins del cos `px+4..px+11`). Ara, en arrambar-se a qualsevol paret, mai mostreja la columna exterior i cau de manera fluida fins al terra real.
1. **Disc Únic DSK (6 Nivells en 180 KB amb 26 KB de Marge Lliure)**:
   - Desacoblament de codi i dades a `ENEMI`: `ENEMYCODE.BIN` (7.505 B) es comparteix resident a `C6:0x5A00..0x782F` carregat per L1.
   - Les taules `s_spawn` es generen binàries (234 B per nivell) a `C6:0x4E00..0x4EE9`.
   - `L2ENEMI..L6ENEMI` només empaqueten dades (`0x4000..0x4FFF`, 4.096 B crus -> 2..3 KB ZX0 = 6 sectors).
   - Estalvi total al disc: ~16-20 KB alliberats. Resultat del DSK: **152 / 178 blocs usats (26 KB lliures)**!
2. **Nivell 6 (Concert, `level_idx = 5`) 1:1 DOS**:
   - Mapa 128x49 (6.272 B raw), 184 tiles compactats, 6 portes, 6 spans d'animació de focus d'escenari (seqüències 74 i 75).
   - 2 ascensors d'escenari (`object_func_op19`, 16x14 Mode 0 a `assets/bbdata/LIFT6.BIN`) a `center_x=528` (`map_col=66`), `y=448` i `688`.
   - 9 enemics (6 guàrdies tipus 3 i 3 policies tipus 4 de `ENEMI6.SQV` convertits a Mode 0).
   - Cançó `theme2` (4.670 B) a `C1:0x5000` i layout C1 adaptat (`frames_base = 0x7000`, `code = 0x6B58..0x6F0E`).
3. **Seqüència Endgame 1:1 DOS (`trigger_func_op40`)**:
   - Al terra de l'escenari (fila 24, cols 95..104, tile 76, `op == 40`), actua com a terra sòlid (`is_floor_solid` retorna 1).
   - En tocar el terra, `s_dance_timer = 2` manté en Jake ballant el ball dels Blues Brothers contínuament (`s_vx = 0`).
   - Comptador de concert `s_concert_counter` arriba a 400 frames (~8 segons a 50 Hz), fixa `g_level_complete = 1`.
   - El cicle de finalització fa wrap `g_map_level = 0`, `g_front_map_only = 0` i torna netament a la pantalla de menú/títol.
4. **Verificació a ZEsarUX**:
   - Arrencada verificada amb drecera `Key_6` (`level6_boot.png`).
   - Moviment per la teulada nevada de l'edifici (`level6_gameplay.png`, `level6_jump.png`).
   - Teleport a l'escenari amb el ball dels Blues Brothers i els focus sobre la cortina (`level6_stage_dance1.png`, `level6_stage_dance2.png`).
   - `smoke_test.py` passa el 100% de les comprovacions DSK + BOOT.

### Actualització 02/11/2026: Fix Col·lisió Comportes L4 i Línia de Flotació Natació (1:1 DOS)
1. **Fix Col·lisió i Bug de Retrocés a les Comportes de L4**:
   - *Causa arrel detectada*: La comprovació de paret a `src/main.c` incloïa indegudament `feet_row` (`tile_flags(c, feet_row)`). Quan Jake nedava pel canal (files 11-12), els peus tocaven la fila 13 (fons de canal, sòlid `flags=3`). A cada pas endavant, el codi creia trobar una paret frontal a la fila 13 i executava un snap destructiu `s_px8 = (((c_right << 3) - 11) * SUB)` que catapultava en Jake 8-11 px cap enrere a cada columna de terra de manera indefinida.
   - *Solució 1:1 DOS* (`level.c:1763-1840`):
     - Eliminada la comprovació de `feet_row` a la col·lisió horitzontal (com ja indicava el comentari resident: en CPC els peus no es miren amb `tile_flags`).
     - Al xocar amb una paret o comporta tancada (`fl & 1` o `fl & 2`), s'aplica el model fidel de DOS (`_si = 0`): `s_vx = 0` sense reubicar ni catapultar `s_px8` enrere.
     - Jake s'atura netament davant de la comporta tancada i la travessa suaument quan s'obre sense cap bug ni retrocés.
2. **Línia de Flotació a la Superfície de l'Aigua (Entremig 1:1 DOS)**:
   - Contrastat amb DOS `level.c:622` (`tile0_num = triggers_get_tile_type(..., ypos16 - 2)`).
   - Abans es clampava rígidament a `surf_py = (head_r + 1) << 4`, deixant en Jake 100% submergit sota la línia de flotació.
   - Ara es permet que el pit estigui a la línia de flotació i el cap emergeixi 8 píxels (mig tile) per sobre de l'aigua (`py = ((cr + 1) << 4) - 8`). Jake neda mostrant el cap i les ulleres de sol fora de l'aigua respirant a la superfície com a DOS, sense sortir de l'aigua per l'aire.
3. **Pressupost de Memòria i Optimitacions**:
   - Bloc 0 Resident: `_CODE : 0x0100..0x382A (14122 B)` -> **374 B de marge lliure** fins a `_DATA` (`0x39A0`). Guanyats +141 B lliures al resident!
   - Banc C5 (`moving_bank.c`): Unificada la lògica d'escales/reixes (`tt == 6 || tt == 7`) i unificat `tp = b5_trig_ptr(col, row)`, assegurant que `_CODE` i `_DATA` càpiguen amb seguretat per sota de la taula de salts `0x7FE8`.
   - DSK i paquets de disc generats i verificats al 100%.

### Actualització 01/11/2026: Trampolins L2 (3 Altures 1:1 DOS) i Comportes L4 Automàtiques
1. **Trampolins de L2 (op 24, 3 altures 1:1 DOS)**:
   - Contrastat amb `tiles.c:391` (`trigger_func_op24`) i `level.c:1516-1533` (`yfriction = (yvelocity & 255) + 6`).
   - Implementació a `src/main.c`: `is_floor_solid` retorna 2 per `op == 24`; detecció unificada d'aterratge aplica `s_vy = -(s_vy + 48)` (clamped a `VY_MAX_UP = 21 * SUB = 168`), `s_on_ground = 0`.
   - Eliminat el clampeig restrictiu cap amunt `if (s_vy < -VY_MAX) s_vy = -VY_MAX` (abans tallava salts a 120 subpíxels).
   - Verificat a ZEsarUX (`tools/test_l2_trampoline.py`): Rebot 1 (62 px), Rebot 2 (99 px), Rebot 3 (impuls màxim -168 / -21 px/f). Captures `l2_trampoline_bounce1.png` i `l2_trampoline_bounce2.png`.
2. **Comportes Automàtiques de L4 (egou / clavegueres)**:
   - Identificat a DOS `level_tilesdata_1e8c`: seqüències `b4=67` (comporta superior, len=44) i `b4=68` (comporta inferior, len=44).
   - Integrades a `DOS_ANIM_SEQS` a `tools/pack_level.py`. Generats 8 spans animats de comporta (4 comportes de 2 tiles: cols 60 i 88 al mapa, cols 85 i 117 a les sales secretes).
   - Els tiles compactats s'alternen cíclicament entre sòlids (100, 101, 102, 112, `flags=3`) i oberts (49, 99, `flags=0`).
   - Verificat a ZEsarUX (`tools/test_l4_gates.py`): monitoratge de la fase de 44 frames, captures `level4_gate_closed.png`, `level4_gate_open.png`, i travessament verificat de Jake d'un costat a l'altre (`level4_gate_passed.png`, x=460 -> x=550).
3. **Pressupost de memòria**:
   - Resident Bloc 0: `_CODE : 0x0100..0x38B7 (14263 B)` amb **233 B de marge** fins a `_DATA` (`0x39A0`).
   - Paquet de dades: `L4WORLD.PAK: 13883 B` (dins del límit de 14208 B, 325 B lliures).

---

## 3. Arquitectura de Memòria de 128 KB

```
+---------------------------------------------------------------------------------+
| BLOC 0 (Resident 0x0000..0x3FFF, sempre mapejat a RAM 0)                         |
|  - 0x0100..0x38CB: _CODE del resident (motor genèric, vídeo, ISR, blit)          |
|  - 0x39A0..0x3E10: _DATA resident (globals, s_lv, càmera, estat del jugador)     |
|  - Marge lliure _CODE fins _DATA: 213 B                                          |
|  - Pila Z80 (SP=0x3FFE, ~494 B lliures)                                          |
+---------------------------------------------------------------------------------+
| FINESTRA BANCADA (0x4000..0x7FFF) commutada via 0x7F00                          |
|                                                                                 |
|  Banc C1 (0x4000..0x7FFF): Àudio compartit + imatge variable del nivell         |
|    - 0x4000..0x4C00: Player àudio AKG (MAI escriure-hi dades)                    |
|    - 0x4C01..0x4F96: HUD blitter ASM (src/hud_bank.c, 917 B)                     |
|    - 0x4FA8..0x4FE1: _DATA de HUD (src/hud_bank.c)                               |
|    - 0x5000..: cançó + HUD + GAMEOVER + portes + restore (layout variable)       |
|    - 0x7680..0x76CC: LevelParams v3 (77 B)                                       |
|    - 0x7700: _DATA del codi d'excepcions (si n'hi ha)                            |
|    - 0x7800..0x7BFF: còpia mestra de FDC.BIN (C0:0x7800) — PROHIBIT trepitjar    |
|    - 0x7C00..0x7F2D: LVLCHS copiada per load_level_file                          |
|                                                                                 |
|  Banc C4 (0x4000..0x7FFF): Tileset compactat del nivell                          |
|  Banc C5 (0x4000..0x7FFF): Món del nivell                                        |
|    - 0x4000: mapa · rooms_off: sales · trig_off: TRIG compacte (5 B/entrada)     |
|    - darrere TRIG: codi del món (moving_bank.c) + _DATA contigua                 |
|    - 0x7FE8..0x7FFF: taula de salts fixa BC_* (8 slots x 3 B = 24 B)             |
|  Banc C6 (0x4000..0x7FFF): Enemics                                           |
|    - 0x4000: taula de celes + blocs ZX0                                          |
|    - 0x4B00: taula de restauració de tiles del nivell                            |
|    - 0x5000..0x57FF: cache de 4 celes (scratch a slot lliure t, zero buffer fix) |
|    - 0x5800..0x581F: estat de la cache                                           |
|    - 0x5820..0x59FF: _DATA d'enemics                                             |
|    - 0x5A00..0x77A3: codi d'enemics (src/enemy.c) — 349 B lliures fins a LUT     |
|    - 0x7900..0x79FF: LUT de flip (256 B)                                         |
|    - 0x7A00..0x7FFF: pool de fons (6 x 256 B)                                    |
|  Banc C7 (0x4000..0x7FFF): Frames del jugador (Jake/Elwood)                      |
+---------------------------------------------------------------------------------+
| VRAM (0x8000..0xFFFF, doble buffer de pàgines 0 i 1 a Mode 0)                    |
+---------------------------------------------------------------------------------+
```

### 3.1 Layout C1 variable per nivell

El build calcula els offsets i els desa a `obj/C1LAY<n>.BIN` y a `LevelParams`.

| Nivell | Cançó | HUD | GAMEOVER | Portes | Restore | Codi exc. | Frames | BG | Params | Mida PAK |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 0x5000 (1.619) | 0x5658 | 0x5A00 | 0x5F50 | 0x5FB0 | 0x5FE8 (1.135 B) | 0x6900 | 0x6D00 | 0x7680 | 13.401 B |
| L2 | 0x5000 (2.721) | 0x5AA8 | 0x5E50 | 0x63A0 | 0x63A0 | 0x63A8 (1.135 B) | 0x6900 (PRESS 792 B) | 0x6D00 | 0x7680 | 13.284 B |
| L3 | 0x5000 (4.670) | 0x6240 | 0x65E8 | 0x6B38 | 0x6B98 | **cap** (`code_exc_off=0`) | — | — | 0x7680 | 11.369 + 3.520 B |
| L4 | 0x5000 (1.619) | 0x5658 | 0x5A00 | 0x5F50 | 0x5FA0 | **cap** (`code_exc_off=0`) | — | — | 0x7680 | 13.361 B |
| L5 | 0x5000 (2.721) | 0x5AA8 | 0x5E50 | 0x63A0 | 0x63A8 | 0x63F0 (1.706 B) | 0x6B00 (SCAFFOLD 528 B) | 0x6D20 | 0x7680 | 11.580 + 3.599 B |

- L3 **no porta codi d'excepcions**: no té ascensors ni premses encara. Això és el que fa que
  `L3WORLD.PAK` = 11.369 B (23 sectors) i `L3C1.PAK` = 3.520 B (8 sectors); C1 va separat amb `load_level_file(lvl,2)`.
- Si mai s'hi afegeix codi de mecanismes a L3, caldrà comprimir més o fer split de C1.

### 3.2 Layout i Pressupost C5 (mapa + sales + TRIG5 + codi del món dinàmic + taula 0x7FE8)

El codi de món (src/moving_bank.c) s'enllaça just darrere les dades del nivell (0x4000 + mapa + sales + TRIG) i la taula de salts fixa viu a 0x7FE8..0x7FFF (slots fixos BC_*). L'espai lliure queda unificat abans de la taula:

| Nivell | Mapa | Sales | TRIG5 | Base Codi | Codi+DATA | Lliures fins a 0x7FE8 |
|---|---|---|---|---|---|---|
| L1 | 9.216 | 1.000 | 1.195 | 0x6C93 | 4.601 B | **348 B** |
| L2 | 9.216 | 0 | 1.025 | 0x6801 | 4.644 B | **1.468 B** |
| L3 | 9.216 | 1.200 | 1.070 | 0x6CDE | 4.494 B | **379 B** |
| L4 | 7.808 | 600 | 1.105 | 0x6529 | 4.494 B | **2.245 B** |
| L5 | 12.160 | 200 | 1.070 | 0x7476 | 2.822 B | **108 B** |

### 3.3 C6 (enemics)

- `ENEMY_N = 20` (no 22: el codi de C6 acaba a `0x7833` i la LUT viu a `0x7900`).
- L3 omple **18 slots**: 11 policies (`type 3` → `kind 4`, op2) i 7 gossos (`type 6` → `kind 18`, op1).
- Queden fora, documentats com a pendents:
  - `type 4` → **op3** (llançador): cal comportament 1:1 i espai a C6.
  - `type 5` → **op4** (4 movers) i `type 23` → **op11** (2 movers): no són walkers de C6.

---

## 4. Estat dels Nivells

### Nivell 1 (`magasin`) — **COMPLETAT I ESTABLE**
- 5 ascensors verticals amb restauració de fons intacta.
- Cintes transportadores amb animació i empenyiment de velocitat correcta.
- Enemics terrestres (policia, iaies, rockers, grangers, cambrera), peixos a les peixeres i ocells als núvols.
- Caixes agafables i llançables, paraigües, globus, recollida de vinils i pas per habitacions interiors.

### Nivell 2 (`ent` / fàbrica i magatzem) — **AVANÇAT**
- **Operatiu**:
  - Mapa i tileset empaquetats a `L2WORLD.PAK` i `L2ENEMI.ZX0`.
  - Àcid, cintes transportadores de fàbrica, trituradores i animacions de panells.
  - **Premses hidràuliques** sincronitzades amb `PRESS.BIN` (24×33 px) i buffers de fons.
  - **Inèrcia de gel**: `g_on_ice` resident accelera el jugador sobre `op 30` i rampes 32..35.
  - Enemics L2 per tipus 11/12/13/14/21.
- **Pendent**:
  1. Dipòsit d'aigua del sostre / desguàs: en Jake no hi passa bé (col·lisió massa estreta / postura).
  2. Trampolins elàstics: validar i connectar el salt (no hi ha implementació tancada al codi actual).
  3. Fidelitat fina d'animacions i tipus 22 com a objecte mòbil independent.

### Nivell 3 (`prison`) — **INTEGRAT I CARREGANT**
- Afegit a `LEVELS` i `DATA_FILES`: `L3WORLD.PAK` (11.296 B), `L3C1.PAK` (3.520 B) i `L3ENEMI.ZX0` (6.676 B).
- `pack_level.py 2 --outdir obj/lvl2` regenera tileset/mapa/sales/TRIG/restore/params.
- Xarxa de C1 variable: Theme2 (4.670 B), HUD, GAMEOVER, 24 portes i restore de 6 sales.
- **Verificat en emulador** (drecera `3`): `magic=0xB0`, `level_id=2`, `g_map_level=2`,
  Jake apareix ja centrat al punt d'inici (`px8=1600`, `py8=1296`), moviment OK i 18 enemics visibles.
- **Entrada 1:1 DOS** (`init_level`): per als nivells 2-6 la càmera inicial es calcula centrada al jugador
  (`start_px = xpos/2 - 8`, `cam0` segons la fórmula DOS), no a `(0, max_cam_row)`. Això elimina el
  desplaçament inicial que es veia en arrencar L3.
- **Forat d'1 tile (row 23, cols 8-21)**: el jugador hi passa **ajupit**. La col·lisió horitzontal
  ara només mira la fila del cap abaixat quan `crouch` (1:1 DOS `unk2E==0` → alçada 14).
- **Reixes `type 6` (cols 35-44, rows 18-23)**: són escalables com al DOS (`do_level_fixup_object_unkA`),
  sense l'imant horitzontal del `type 7`; per tant s'hi pot pujar/baixar i entrar/sortir pels costats.
- **Palanques/comportes (`b6 < 10`)**: implementades a C5 amb una taula compacta per als dos
  switches de L3 (`b6=0` a (23,29) i `b6=53` a (78,28)). En tocar la palanca (peus o fila de sobre)
  s'obren les comportes (29,26)/(29,27) i (76,30)/(76,31). Com que els grafics DOS de comporta
  oberta (175/178) no caben al paquet de 28 sectors, s'obre amb el tile buit 15; pendent recuperar
  el grafic exacte si es guanya espai.
- **Trampilles L3**: afegides les seqüències DOS b4 4/5/7/8 (obertes/tancades
  temporitzades) a DOS_ANIM_SEQS; el motor ja les anima amb anim_tick_c5.
- **Ítems de les habitacions**: moving_bank.c ara llegeix els triggers b6 de
  ROOMSC (no només vinils/instrument) i actualitza el tile de la sala.
- **Hitbox de la rata**: el check vertical genèric passa de 50 a 38 px; la rata
  (level_obj_h[6]=10) ja no toca Jake una fila més amunt.
- **Pendent**:
  1. `type 4`/op3 (4 llançadors) i movers `type 5`/op4 + `type 23`/op11.
  2. Validació de portes/sales/àcid i recorregut complet del nivell.
  3. `ENEMY_N=20`: si s'hi afegeixen els 4 llançadors caldrà 22 slots o reduir el codi de C6.

### Nivell 4 (`egou` / clavegueres) — **INTEGRAT I ENEMICS 1:1 DOS VERIFICATS**
- Afegit a `LEVELS` i `DATA_FILES`: `L4WORLD.PAK` (13.361 B, 28 sectors) i `L4ENEMI.ZX0` (7.105 B, 16 sectors).
- `pack_level.py 3 --outdir obj/lvl3` genera tileset (14.144 B), mapa (7.808 B), sales (600 B, 3 sales), TRIG (1.105 B), restore (356 B) i params (77 B).
- Format C1: Cançó principal Peter Gunn (`main`, 1.619 B), HUD, GAMEOVER, 20 portes i restore de 3 sales. Càpiga directament dins de `L4WORLD.PAK` sense necessitar C1 separat.
- **Natació 1:1 DOS**:
  - Tiles d'aigua unificades (`tt == 11` fons, `tt == 12` línia de flotació/superfície).
  - Cap submergit puja a velocitat DOS `s_vy = -16`; la línia de flotació s'atura a `s_vy = 0` sense saltar a l'aire ni xocar amb sostres exteriors.
  - Supressió total d'estrelletes/dazed a l'aigua (1:1 DOS `level.c:1652, 1664`).
- **Enemics 1:1 DOS (C6, 16 cel·les d'ENEMI4.SQV a `assets/bbdata/ENEMI4.BIN`)**:
  - D'acord amb `tools/blues_dos/bb/staticres.c` (`level_data`, `level_objtypes`, `level_obj_type`, `level_obj_h`) i `objects.c`:
    - **Tipus 25** (Policia de claveguera, op 2): patrulla sense tret, celes 0/1 (`kind 18`, `vx=24`).
    - **Tipus 28** (Patruller estàndard, op 1): walk celes 2/3 (`kind 18`, `vx=24`).
    - **Tipus 26 i 34** (Peix gran / monstre aquàtic de claveguera, op 6/16): swim celes 4/5 (`kind 9`, `vx=24`). Neda a l'aigua i **fa mal** (`class 2` 1:1 DOS `level_obj_type[34] == 2`).
    - **Tipus 27** (Rata gran ràpida, op 13): walk ràpid celes 6/7 (`kind 18`, `vx=32`).
    - **Tipus 29** (Rata petita ràpida, op 13): walk ràpid cela 8 (`kind 24`, `vx=32`, hitbox reduïda).
    - **Tipus 30** (Enemic estàtic, op 14): pose cela 9 (`kind 22`, `vx=0`).
    - **Tipus 31** (Walker mitjà, op 13): walk celes 10/11 (`kind 18`, `vx=32`).
    - **Tipus 32** (Aranya vertical de sostre, op 15): cela 12 (`kind 22`, `vx=0`).
    - **Tipus 33** (**Peix petit d'aigua**, op 16): swim celes 14/15 (`kind 8`, `vx=24`). **DECORACIÓ PURA, NO FA MAL** (`class 0` 1:1 DOS `level_obj_type[33] == 0`), no interactua amb caixes ni fereix Jake.
    - **Cela 13**: Projectils compartits (ou/bala/plat d'ENEMI1.BIN).
- **Verificat en emulador**:
  - Drecera de boot tecla `4` arrenca directament a Nivell 4 (`magic=0xB0`, `g_map_level=3`).
  - Verificació a l'aquari superior: Jake toca el peix petit i els cors no baixen (`h_before=1, h_after=1`, dany 0).
  - Verificació a la claveguera inferior: Peix gran visible amb sprite 32x32 autèntic de DOS nedant a l'aigua. Captures generades a `level4_small_fish.png` i `level4_big_fish.png`.

### 4.4 Mecànica universal: Llançament de caixes (1:1 DOS)
- **Llançament des d'escales, reixes i aigua**: d'acord amb level.c:1940-1942 i do_level_throw_crate (level.c:845-871), si el jugador porta una caixa sobre el cap (s_carry_kind == 1), prémer el botó d'acció (grab) la llança immediatament amb velocitat +/-128, tant a terra com enfilat a una escala (tt == 7), a una reixa (tt == 6, L3) o submergit a l'aigua (tt == 11).
- **Restriccions mantingudes**: agafar caixes del terra continua exigint terra ferm (s_on_ground == 1), de manera que no es pot agafar una caixa des de l'escala. Els globus (tt == 8) i paraigües (tt == 9) continuen caient automàticament en entrar a l'escala (carry_abort()).

---

## 5. Rendiment i Optimització del Framerate (Octubre 2026)

- **Estat del motor**:
  - **QUIET (Jake immòbil)**: **22,6 – 22,7 fps** (2 VSYNCs / ~44 ms per frame, +81% vs 12,5 fps original).
  - **CAMINANT (Contra paret)**: **12,4 – 18,1 fps** (+72% vs 10,5 fps).
  - **CAMINANT (Scroll actiu)**: **9,1 – 13,6 fps** (4-5 VSYNCs, +31% vs 8,4–10,4 fps).
- **Fase 1 (Completada - commit `127e306` + `8030c9d` + optimització HUD)**:
  - `_hud_blit_col` i el bucle de redibuix del HUD s'han mogut del resident al Banc C1 (`src/hud_bank.c`) i reescrits en ASM directe (Mode 0, càlcul incremental de VRAM amb màscara wrap 2 KB).
  - **Optimització ASM de `hud_blit_columns()` (Banc C1)**:
    - Pre-incorporació de `_s_base_hi` directament a `_s_cur_off20` i `_s_cur_off21` abans del bucle (estalvia 2.720 T i 10 B dins el bucle de 40 columnes).
    - Unroll de 2 línies per iteració a `hb_blit6$` (`c=3` en lloc de `c=6`) utilitzant `set 3, d` a la línia A (estalvia 5.520 T).
    - Agrupació de la doble crida `hb_blit_ff$` amb `hb_blit_ff2$` a la fila 20 (estalvia 1.080 T).
    - Estalvi total: **~9.300 T per frame d'scroll** (~2,3 ms recuperats).
    - Codi de HUD: 922 B (`0x4C01..0x4F9B`), deixant 13 B de marge abans de `_DATA` (`0x4FA8`).
  - **Opció A d'Enemics (commit `8030c9d`)**:
    - `en2_draw()`: Descart ràpid horitzontal `(u16)(e->x - view_x + 15) >= 175` que estalvia clipping i reserves de slot d'enemics fora de pantalla.
    - `en2_update()`: Caixa d'activació 1:1 DOS precalculada en 2 comprovacions unsigned de 16 bits.
    - `en2_check_player_hit()`: Pre-filtrat `(u16)(e->x - (px - 9)) >= 19` que descarta 21 de cada 22 enemics a la primera instrucció abans d'avaluar tipus o altures.
  - Actualment resident `_CODE` acaba a `0x38CB` (14.283 B), amb **213 B** de marge fins a `_DATA` (`0x39A0`).
- **Fases 2 i 3 (Pausades / Documentades)**:
  - *Fase 2 (Render ràpid de tiles)*: reordenació del tileset a la càrrega del nivell + blit via `POP`.
  - *Fase 3 (Còpia front->back en caiguda / Split CRTC)*: descartada a curt termini per complexitat de sprites superposats i sincronització de raster.
- **Sincronització d'habitacions**:
  - Les habitacions interiors corren a **25 Hz exactes** (2 VSYNCs obligatoris a `src/main.c`).

---

## 6. Taula de Paràmetres del Nivell (`LevelParams` v3, 77 bytes)

Ubicada a `C1:0x7680` al paquet i copiada a `s_lv` a RAM resident:
- Offset 5: `room_row0` · Offset 4: `room_rows` · Offset 2: `room_count`
- Offset 34: `start_px` (i16) · Offset 36: `start_py` (i16)
- Offset 38: `cam0_x4` (i16) · Offset 40: `cam0_row` (i16)
- Offset 42: `chk_px` (i16) · Offset 44: `chk_py` (i16)
- Offset 52: `map_w` (u8) · Offset 53: `map_h` (u8) · Offset 54: `map_rows` (u8)
- Offset 55: `door_count` · Offset 56: `rooms_off` (u16)
- Offset 58: `doors_off` · Offset 60: `restore_off`
- Offset 69: `trig_off` (u16)
- Offset 71: `code_exc_off` (u16) — **0 si el nivell no té codi d'excepcions (L3)**
- Offset 73: `hud_off` (u16) · Offset 75: `gameover_off` (u16)

> **Atenció**: SDCC empaqueta l'struct sense alineació. No inserir camps al mig sense actualitzar
> `tools/pack_level.py`, `tools/build.py` i `src/level_params.h` alhora.

---

## 7. Peculiaritats conegudes (no repetir errors)

- **MUSBANK.BIN** (`C1:0x4000`): el player AKG comença a `0x4009`; **mai** escriure-hi taules.
  `LVLCHS` (814 B) viu a l'offset `0x1D00` (`C1:0x5D00`) i es copia a `C1:0x7C00..0x7F2D`
  en carregar el primer nivell. Pool: WORLD 56 B (28 sectors), ENEMI 32 B, C1 32 B per nivell.
- **Límit del paquet**: 28 sectors AMSDOS = 14.336 B en disc (14.208 B de payload).
  El FDC els llegeix sencers a l'scratch `0x8320..0xBBFF` (14.560 B); un paquet de 30
  sectors (15.360 B) desborda l'scratch i corromp la imatge. Els asserts del build ho bloquegen.
- **FDC mestre** a `C0:0x7800` (785 B). Cap imatge de C1 pot arribar-hi: el build ho asserta.
- **`0xC0`/`0xC1` comparteixen RAM** a `0x4000..0x7FFF`; només canvia què es veu a `0xC000..0xFFFF`.
- **Codi bancat**:
  - No pot commutar de banc (perdria el seu propi codi).
  - No rep paràmetres C: usar `bc_a`..`bc_r`.
  - Si escriu a VRAM, ha de viure a la RAM 1 i cridar-se amb `0xC0`.
- **sdasz80**: sense BOM; no `ld a,(hl+1)`; no `ld hl,de`; push/pop equilibrats.
- **ZRCP**: `read-memory` i `disassemble` requereixen adreces **decimals** (`%d`), no hex.
- **Build**: no restaurar versions velles de `build.py` (es va perdre l'empaquetat de frames/GAMEOVER).
- **Els docs antics poden estar desfasats**. Font de veritat: `tools/build.py`, `obj/C1LAY<n>.BIN`,
  `obj/bluesb.map` i els headers generats (`src/disk_tables.h`, `src/crt_addrs.h`, `src/starter_tables.h`).
  En particular, `HANDOFF` antic parlava de params a `0x6900` i frames a `0x6E00`: **ja no és així**.

- **Natació a l'Aigua (1:1 DOS `level.c:610-637, 1512-1534`, `sprite_type 4`)**:
  - Tiles d'aigua: tant `tt == 11` (aigua fons) com `tt == 12` (superfície/onada) són aigua oficial a DOS.
  - Ascens: prémer Jump/Up (`direction_ud == 1`) activa `s_vy = -16` (DOS `unk3D = 2`) només si el cap de Jake està submergit (`head_in_water`).
  - Línia de flotació: quan el cap arriba a la superfície (`head_in_water == 0`, DOS `tile0_num == 0 -> unk3D = 1`), l'ascens s'atura (`s_vy = 0`) i es clampa `py` a la superfície (`(head_r + 1) << 4`). Jake no pot sortir nedant per l'aire ni picar amb els blocs superiors (`di == 10`).
  - Danys i estrelletes: a DOS `level.c:1652, 1664` (`if (sprite_type != 4) special_anim = 18;`), a l'aigua mai no es disparen estrelles al cap (`s_dazed_timer`).
  - Descens i fons: Down/Crouch submergeix ràpidament (`s_vy = 16`); anar quiet deriva suaument (`s_vy = 4`). Si els peus toquen terra ferm de fons (`is_floor_solid`), s'atura (`s_on_ground = 1`).
  - Sortida: s'agafa directament l'escala (`tt == 7`) en contacte o caminant cap a terra ferm.

---

## 8. Llista de Documents de Suport

- [`docs/OPTIMITZACIO_BUILD.md`](file:///C:/Projects/bluesb_cpc/docs/OPTIMITZACIO_BUILD.md): arquitectura de la pipeline de compilació ràpida (C# ZX0, SHA-256 cache, convergència CHS).
- [`docs/DOS_CPC_COORDINATES.md`](file:///C:/Projects/bluesb_cpc/docs/DOS_CPC_COORDINATES.md): fórmules de conversió 1:1.
- [`docs/PLA_NIVELLS_UNIVERSAL.md`](file:///C:/Projects/bluesb_cpc/docs/PLA_NIVELLS_UNIVERSAL.md): pla d'extensió universal als 6 nivells.
- [`docs/LEVEL_PACKAGE.md`](file:///C:/Projects/bluesb_cpc/docs/LEVEL_PACKAGE.md): especificació del format de fitxers `.PAK` i `.ZX0`.
- [`docs/FIX_PREMSES_NIVELL2.md`](file:///C:/Projects/bluesb_cpc/docs/FIX_PREMSES_NIVELL2.md): anàlisi del bug de memòria de les premses.
- [`docs/INVENTARI_NIVELLS.md`](file:///C:/Projects/bluesb_cpc/docs/INVENTARI_NIVELLS.md): mides i contingut dels 6 nivells.
- [`docs/ESTAT_L3_C1_C3.md`](file:///C:/Projects/bluesb_cpc/docs/ESTAT_L3_C1_C3.md): registre històric del WIP de C1/L3 (pot contenir adreces antigues).
- [`tools/blues_dos/`](file:///C:/Projects/bluesb_cpc/tools/blues_dos/): descompilació DOS de referència absoluta.

---

## 9. Properes passes recomanades

1. **Harmonitzar disseny de la caixa (Bug 6)**: transferir el dibuix del Tile 19 (`level1_magasin/tileset.png`, textura de fusta i segell quadrat) als frames de càrrega (`player_jake/jake.png` i `player_elwood/elwood.png`).
2. **Validació a ZEsarUX en viu dels canvis recents**: comprovar en joc el tret del policia, la restauració del fons de les caixes en agafar-les i el comportament de la paret a la Sala 2.
3. **Commit** de la integració de l'accelerador ZX0, optimitzacions de `build.py` i correcció dels bugs 4, 5, 7 i 8.
