# Registre HistÃ²ric de Canvis â€” Blues Brothers CPC

Aquest fitxer recull el detall cronolÃ²gic de les sessions i fites del projecte. Per a l'estat actual, regles i arquitectura vigent, consulta [`docs/HANDOFF.md`](HANDOFF.md).

---

### 22/11/2026 - Primera passada L4 (egou): animacions i spawns

Auditoria comparativa DOS vs port del nivell 4 (`level_idx=3`, MAP3/TRIG3/
ENEMI4/DOORS3). Canvis:

- **Animacions**: el DOS te 20 sequencies animades al L4
  (`level_tilesdata_1e8c`: b4 33,35-44,47-52,66,67,68,83). El port nomes
  n'empacava 2 (les comportes 67/68). `tools/pack_level.py` ara extreu les
  sequencies directament de la taula DOS (nomes per L4, per no fer petar el
  Banc 5 de L1). Resultat: **165 spans animats** (abans 8) i 238 tiles.
- **Enemics**: hi ha 31 objectes DOS; 30 dins el mapa i 1 a les sales
  (slot 28, y=1168). El motor te `ENEMY_N=26`: abans es truncava per ordre
  de slot i es perdien 4 enemics de joc (slots 26,27,29,30: 3 patrullers i
  1 policia). Ara s'exclou l'enemic de sales i es prioritzen policies/
  rates/walkers/aranyes; queden fora 4 peixos grans (slots 20,23,24,29)
  pel limit d'estat.
- **Cel.les aim/throw L4**: corregides (26/34 -> 4/5, 27 -> 6/7, 28 -> 2/3,
  29 -> 8/9, 31 -> 10/11, 33 -> 14/15). Abans apuntaven a 8/10/12/16, fora
  de les 16 cel.les d'ENEMI4 o a l'art d'un altre enemic.
- **Portes/tuberies**: s'havia canviat `+29` -> `+PH` (30), pero la taula
  DOS indexa la fila de l'**ultim pixel** dels peus (`top + PH - 1`); amb
  `+PH` les portes deixaven de detectar-se. Revertit a `+PH - 1` (=29).
  El problema de les tuberies del L4, si hi es, es una altra cosa.

**Build**: resident 13.562 B (marge 6 B); L4WORLD **13.487 B** (tiles=4.354
B, 165 spans), L4ENEMI 2.331 B; DSK generat. L4 arrenca (magic B0, level
03). Pendent: ENEMY_N=26 per encabir els 4 peixos, comportaments op5/op12/
op14/op15 (aranya vertical, velocitats DOS) i test manual de portes.

### 21/11/2026 - Tiles animades al scroll (M1 v9)

`sync_backbuffer` pinta les columnes/files noves amb el tile BASE del mapa;
les animades (`s_anim` spans: retols/vinils) nomes es redibuixen al canvi de
fase (fins a 4 frames). Al caire dret/superior del scroll es veia el base i
despres l'animat: els discos/retols que parpellejaven. Ara, si `dx`/`dy`,
s'invalida `s_page_conveyor_phase[s_back_page]` (+0x80) i
`moving_draw_conveyor_tiles` les redibuixa en el mateix frame.

**Nota**: la primera bateria estàtica es va fer amb coordenades fora del mapa
(`cam_x4=317`, `px=1350`) i les seves conclusions no són vàlides. L'evidència
bona és l'A/B de VRAM de sota.

**A/B controlat (fase d'animació congelada, mateix escenari)**:
- Worktree `C:\Projects\bluesb_cpc_v8` al commit pre-fix `8a4d0bc` (inclou v8,
  sense v9): build `WT4_EXIT=0`, resident 13.529 B.
- Escenari: L1, prestatge de la fila 36 (cols 84-86), inserció per scroll
  `cam_row` 78→72 amb `cam_x4=139`, `px=676`, `py=608`; breakpoint dins
  `moving_bank_conveyor` (C5:0x7B01) al frame d'inserció.
- **Pre-fix**: `s_page_conveyor_phase` queda `40/40` i la passada **no escriu
  cap byte** a la pàgina (0 B): la fila nova conserva el tile BASE.
- **Fix del scroll**: `sync_backbuffer` invalida la pàgina a `0xC0`; la
  mateixa passada escriu **42 B** (i **1.219 B** en la passada completa amb
  tots els spans visibles) a `0xC000`; les captures del mateix frame difereixen
  en **296 píxels** a l'element animat.
- Nota de coordenades: el mapa L1 fa 128×8 px = **1.024 px** d'ample
  (`cam_max_x4=236`). Els teleports previs (`cam_x4=317`, `px=1350`) queien
  **fora del mapa** i invalidaven el test; les coordenades correctes són
  `cam_x4=139`, `px=676`, `cam_row=72`.

**Build**: resident 13.562 B (marge 6 B), C6 8.156 B (0x79DC), paks iguals;
L1/VILLE arrenquen. Retall del marge: `if (dx || dy)` -> `if (dx | dy)`
(mateixa semantica, OR de registres).

### 21/11/2026 - Repaint de tiles animades (M1 v8)

Els retols/vinils animats (`s_anim` spans) nomes es redibuixen quan canvia la
fase (`s_page_conveyor_phase[page] != s_conveyor_phase`). Despres d'un repaint
(inici de nivell, entrada de sala, respawn) les dues pagines quedaven amb el
tile BASE i les animades no tornaven fins al seguent canvi de fase (fins a 4
frames): discs/retols que parpellegen o desapareixen. `repaint_both_buffers`
ara invalida `s_page_conveyor_phase[0/1]` amb `+0x80` perque el proper
`moving_draw_conveyor_tiles` de cada pagina les redibuixi.

**Build**: resident 13.529 B (marge 39 B), C6 8.156 B (0x79DC), L1WORLD
13.377 B, L1ENEMI 7.474 B. L1 i VILLE arrenquen nets; comptador policia+iaia
5/80 (la cache de 6 slots, intacta).

### 21/11/2026 - Cache d'enemics de 6 slots (M1 v7)

**El problema**: un shooter sol omple la cache de 4 slots (2 walk + aim + projectil);
amb un altre enemic visible (5-6 claus) la FIFO fallava ~6 cops per cicle. Cada
fallada d'una cela girada feia ZX0 + flip de 512 B (8-10 ms), que es veu com les
cames del policia lentes i pot fer perdre un vsync. Un 5e slot sol no ajuda: amb
6 claus segueixen 6 fallades/cicle; calen 6 slots.

**Solucio**: cache de 6 slots a C6:0x4C00..0x57FF. Per alliberar 0x4C00..0x4FB4,
la taula de restore de tiles del nivell passa a C1 (forat abans dels frames/params;
descriptor a C1:0x76E0, fora del LevelParams de 93 B) i `s_spawn` baixa a 0x4B14. VILLE mou SCAFFOLD a 0x6B80 i
els BG a 0x6E00 perque la seva taula de 638 B hi cap sencera (el split de dos
punters no cabia al resident: 23 B de mes). C6: blocs 0x4000, spawn 0x4B00,
cache 0x4C00..0x57FF, dades 0x5800, codi 0x5A00, pool 0x7A00.

**Build**: resident 13.513 B (marge 55 B), C6 8.156 B (0x79DC, 36 B fins al
pool de fons), L1WORLD 13.377 B (27 sectors), L1ENEMI 7.474 B (15 sectors),
L5C1 3.758 B. L1 arrenca net (magic B0, mapa i paleta correctes) i el comptador
`g_enemy_decomp_cnt` baixa de **10/80** a **4/80** frames en el cas policia+iaia
(teleport, 80 frames). L5 (VILLE) tambe arrenca net (magic B0, level 4, pantalla
correcta): SCAFFOLD a 0x6B80 i BG a 0x6E00; el test de joc ha de cobrir les zones
de bastides.

### 21/11/2026 - Guard del projectil sobre Jake + layout ENEMI de 20 sectors

**L'artefacte de la bala**: el guard de col·lisio nomes mirava enemics. Quan la bala
(ou/plat) passava sobre el Jake quiet, el dirty-flag saltava el restore+blit i el
save/restore creuat deixava l'error de restauracio (test real 21/11). S'ha afegit el
check del projectil al `_spr_key_ops` en ASM compacte (caixa 8x13 contra 16x30, en
coordenades de mon).

**Espai**: el C6 no tenia lloc per la versio C (190 B; desbordava el pool) i el pak
L1ENEMI de 16 sectors no arribava. Solucio: el pool de sectors ENEMI passa de 16 a
**20 sectors** (`LVLCHS` 814 -> **862 B**; ENEMI 32 -> 40 B; stride 120 -> 128;
typ_stride 88 -> 96). Actualitzats build.py, main.c, check_dsk_banks.py, smoke_test.py,
AGENTS.md i HANDOFF.md. La zona 0x7C00..0x7FFF (1.024 B) encara sobra (LVLCHS acaba a
0x7F5E) i MUSBANK queda a 8.286 B / 9 blocs.

**Build**: C6 8.146 B (0x79D2), L1ENEMI 8.094 B (**18 sectors**), MUSBANK 8.286 B,
resident 13.519 B (marge 49 B).

**Ralentitzacio amb la bala / cames del policia**: diagnosticada com la cache de 4
cel·les. Les cames del policia del primer pis son el seu sprite GIRAT; quan la cache
ha d'expulsar la cela girada, `en2_flip_cell` refa el gir de 512 B cada frame (~4-6 ms).
Amb el policia de planta 0 disparant, la pose de tret + el projectil afegeixen claus i
empitjoren el thrash. Al doble buffer no hi ha espai per a mes cache ni LUT de flip
(C6 lliure 46 B); el remei de fons es la RAM2/single-buffer (descartada per estabilitat).
El guard del projectil nomes afegeix dirty frames mentre la bala es sobre el Jake.


### 21/11/2026 - Guard de col·lisio enemic x Jake: artefacte persistent tancat

**El bug**: amb el dirty-flag actiu i el Jake quiet (o estabilitzat despres d'una
col·lisio), l'enemic es dibuixa ABANS del Jake; si l'enemic el trepitja, el Jake es
saltava el restore+blit i el save/restore creuat deixava un error grafic persistent
al lloc de la colisio (test real d'usuari 21/11).

**El guard**: `en2_update` (que ja recorre els enemics actius) marca `g_en_overlap`
si la caixa 16x32 d'un enemic interseca la 16x30 del Jake, i `_spr_key_ops` el
llegeix (1 byte): si es 1, flux original (restore+blit). Cost ~0,05 ms al frame
(dins del bucle existent) i ~90 B al C6.

**El primer intent fallava**: comparava el `y8>>3` de MON de l'enemic amb la
`s_mn_dsy` de PANTALLA del Jake; el check Y no coincidia mai (flag 0 i el bloc
corrupte al test artificial). Arreglat amb `g_en_jake_x/y` (les coordenades de mon
que en2_update ja calcula abans del bucle).

**Validacio controlada**: spawn 0 (iaia kind 15) teleportat a la caixa del Jake;
`g_en_overlap = 01`, slots 00/FF, imatge NETA (Jake sencer, sense bloc ni fantasma).
Build: C6 8073 B (0x7989), L1ENEMI 8043/8064 (21 B de marge).

**Pendent**: la ralentitzacio amb la bala del poli. La causa probable es la cache de
4 cel·les: la pose de tret del policia i la cela del projectil afegeixen claus i
provoquen descompressio ZX0 (~3,5 ms) durant el cicle de tir. El remei real seria
mes cache/RAM2 (arquitectura single-buffer), no un pedac a la doble buffer.


### 21/11/2026 - Restore del jugador mogut a C7:0x7E80: marge resident 5 -> 42 B

**Canvi**: el bucle de 30 linies de `sprite_restore_player` (resident) passa a
`engine/player_restore_c7.s`, muntat a C7:0x7E80 (75 B, area lliure de 128 B entre
el carry bg i la LUT). El resident nomes calcula el punter de fons i la VRAM i fa
`call 0x7E80` amb C7 mapejat. La rutina es self-contained (nomes AF/BC/DE/HL: l'ISR
de la musica no preserva els alternatius) i s'incrusta als dos bundles de jugador
(JAKE/ELWOOD, 16.128 B descomprimits).

**Build**: `_CODE` 13.526 B (0x35D6), **marge 42 B** (abans 5); C6 intacte (7.986 B);
L1ENEMI 7.983 B. JAKE 2.901 B / ELWOOD 2.803 B comprimits.

**Validacio visual**: Jake camina de px 24 a 76; la posicio anterior queda neta
(sense rastre ni clon). El restore funciona amb el bucle a C7.

**Mesura del frame** (2 breakpoints amb les adreces NOVES: MU=0x0FCD, VS=0x03C2;
el `obj/bluesb.sym` era vell i s'ha regenerat del mapa):
```
MU>VS: 46 43 39 39 (cicle de 4 frames), avg 63,1 ms  (abans 63,9)
```
El frame queda al tier de 60 ms; el C7 no el mou (guany teoric ~0,1 ms).

**Adreces noves** (resident desplacat 37 B): moving_update 0x0FCD, wait 0x03C2,
sprite_blit 0x03CF, hud_render 0x0FA9, enemy_restore 0x1066... Els scripts que
tenien adreces hardcodejades (0x0FF2/0x03E7) han d'usar el sym regenerat.

**Pendent per creuar el tier de 40 ms**: els frames de 39 ms necessiten <=37 ms.
Els 42 B de marge permeten inlinar `calc_tile_hl` i el check de la reixa (~0,3 ms),
no els ~2 ms que falten. El candidat real es fusionar els probes de tiles
(`is_floor_solid`/`tile_type`, un canvi de banc C5 per crida) en un helper resident,
amb risc sobre la fidelitat 1:1 de les decisions dels enemics.


### 21/11/2026 - Micro-talls del doble buffer esgotats: el sostre es 16,7 amb enemics+scroll i 25 en quiet

**Dedup de probes a enemy_update, mesurat al FRAME SENcer** (2 breakpoints MU/VS,
px 24-280, 69 frames):
```
Sense dedup: 39 46 43 39 39 46 43 39...   (avg 63,9 ms)
Amb dedup:   39 46 43 39 39 46 43 39...   (avg 63,9 ms)  -> CAP guany
```
El dedup dels probes de tile no mou el frame (el cost no es al cami critic o queda
solapat). Revertit per preservar el marge del paquet L1ENEMI (8027/8064).

**Tiers reals mesurats** (mateix protocol):
- 1-2 enemics + scroll: treball 39-46 ms -> frame **60 ms = 16,7 fps**.
  Els frames de 39 ms freguen el tier de 40 (25 fps), pero hi entren nomes si el
  treball baixa a <=37 ms (calen 2-9 ms mes).
- 0-1 enemics sense scroll / quiet: **25 fps** (mesurat a la sessio).
- 5 enemics (clúster px 452): treball ~83 ms -> **80 ms = 12,5 fps** (acceptat).

**Per que no hi ha mes micro-talls segurs**:
- La copia de columna entre pagines es 7,0 ms vs 5,3 ms del render (descartada, e4b5620).
- El resident te nomes 5 B de marge; el sync (10,9) i el HUD (10,3) son al limit de
  banda/CPU; el blit d'enemics es 59 T/byte (bbox F3 no cap al paquet).
- L'unic cami als 2-3 ms que falten es alliberar resident (moure el restore del
  jugador a C7:0x7E80) i optimitzar sync/player; es un canvi gran i de risc, no
  justificat pel guany (no garanteix creuar el llindar de 40 ms).

**Conclusio**: el doble buffer estable te aquest sostre. 25 fps en moviment amb
enemics+scroll no es assolible amb els talls segurs identificats; 16,7 es el resultat
practic, 25 en quiet i 12,5 als clústers densos.


### 21/11/2026 - Descartada la copia de columna entre pagines: 7,0 ms vs 5,3 ms del render

**Hipotesi**: amb el doble buffer, les 2 columnes noves de la pagina del darrere ja
existeixen a la del davant (1 unitat de camera de distancia); copiar-les (320 B per
columna, 2 bytes x 160 linies al ring) hauria de ser mes rapid que renderitzar tiles.

**Mesura** (`tools/f1_colcopy.s`, RAM0:0x3C00, g_ticks, 10 còpies):
```
15 ticks / 10 còpies = 1,5 ticks/còpia = 7,0 ms per columna de 320 B
Render actual d'una columna = 5,3 ms
```
La copia es **1,7 ms MES LENTA**. El render de tiles ja esta optimitzat per al ring
(75 T/linia amb el salt de bloc D+=8); la copia ha de fer el salt de 78 bytes per fila
i el comptador, i surt pitjor. **Descartada** (no es cableja).

**Conclusio de sostre del doble buffer** (dades de la sessio):
- 0-1 enemics, sense scroll: ~35-40 ms -> **25 fps**.
- 1 enemic + scroll: ~50-60 ms -> **16,7 fps** (tier de 60 ms).
- 5 enemics (clúster): ~80 ms -> **12,5 fps**, acceptat pel test d'usuari.
- El tier de 40 ms amb scroll demana ~25 ms de retall; no hi ha cap tall identificat
  que els doni (sync 10,9 + HUD 10,3 son al limit de banda/CPU).

**Pendent realista**: micro-optimitzacions de player/enemy (~2-3 ms en total) per
estabilitzar l'1-enemic+scroll dins del tier de 60 ms; no per creuar a 40.


### 21/11/2026 - HUD split: el redibuix de 18,4 ms en scroll passa a copia de 5,9 ms

**El coll**: en moviment, `hud_render(force=1)` refer els 40 tiles del HUD a cada
frame de scroll (40 columnes x 16 linies amb calcul d'adreca per tile) = **18,4 ms
mesurats** amb 2 breakpoints (HUD 0x0FCE -> SEL 0x1959), constants 16,7-20 ms.

**La solucio (recepta del single-buffer)**: el HUD de la pagina oposada ja te els
pixels correctes; si els valors (vides/vinils/cors/instrument) no han canviat
nomes cal COPIAR les 2 files. Implementacio:
- C1 decideix amb una signatura de valors `s_hud_sig[2]` (0xFFFF = pagina buida) i
  crida el banc C6 amb l'arg empaquetat (base de la pagina font | offset) en HL.
- C6 slot 6 (`_en_room_exit`) passa a ser un dispatcher: `_bc_b == 0xA5` (valor
  impossible per `enemy_room_exit`, que hi posa 0 o 0xFF) -> `_hud_copy`; si no,
  `_en2_room_exit` intacte.
- `_hud_copy` copia 8 blocs de 2 KB x 2 files de 80 B amb LDIR (16 LDIR = 1.280 B),
  calculant src20/src21 i dst20/dst21 amb la MATEIXA formula/res 3,h que el dibuix.
- Quan un valor canvia, la pagina que ho detecta fa el render complet i l'altra
  tambe (les signatures no coincideixen) -> mai es copia un HUD vel.

**Espai**: el `_DATA` del HUD passa de 0x4FA8 a 0x4FCB (53 B, acaba exacte a
0x5000) i el codi cap just: **967 B / 968**. El C6 creix 103 B i acaba a 0x7932
(206 B de marge fins al pool 0x7A00). Resident INTACTE (marge 5 B).

**Mesura neta (nomes 2 breakpoints)**: HUD->SEL **5,9 ms** de mitjana (abans 18,4).
Perfil del frame en moviment: el treball tipic baixa de ~76-83 ms a ~49-59 ms.
Visual validat: HUD identic a les dues pagines (0 diffs de bytes en repòs), digits
de vinils 00->05 en recollir (render complet), alineacio correcta en scroll.

**Llicons**:
- Amb C6 mapejat la VRAM de 0xC000/0x8000 SEGUEIX visible (test d'OUT 0x7F00,0xC6:
  0xC000/0x8000 no canvien, nomes 0x4000). La regla de la RAM 1 aplica a 0xC1, que
  mapeja RAM 7 a 0xC000; no a C4-C7.
- `call_banked` no toca IX/IY pero si BC/HL: els arguments per registre han de
  viatjar en IX/IY o (com aqui) arribar en HL i passar-se a IX abans del call.
- El linker de SDCC posa els inicialitzadors a CODE (no hi ha crt0 al banc C1):
  les dades inicialitzades NO es copien a _DATA en carregar el blob.


### 21/11/2026 - v5 VALIDADA pel test real: artefactes de caixes/globus/paraigues tancats

**El bug**: amb el dirty-flag actiu, el `carry_draw` (1263) desava el fons DESPRES
del punt on el Jake hauria d'haver estat restaurat (1237): el seu save capturava el
propi Jake i el heal capturava la caixa -> intercanvi de pixels (remanent de 9 B
mesurat al lloc de l'throw + punts/linies al joc real, i la bala parpallejant era
el mateix intercanvi al voltant del projectil).

**El guard (v5)**: `_spr_key_ops` retorna dirty si `s_carry_kind != 0` (qualsevol
carry actiu: caixa 1, globus 2, paraigues 8) -> flux original (l'ordre
restore Jake -> carry save/blit -> Jake blit, i al frame seguent el restore del
carry cobreix els solapaments). 6 B al pak C6, zero cost en repos normal.

**Validat pel test real d'en usuari**: "ara si es net. Validat."

**Lliçons de metode (per la propera sessio de proves)**:
- El diff de pagines per bytes es RACY si no es pausa la maquina entre les dues
  lectures (poden caure a frames diferents): pausar sempre abans de comparar.
- El feed per la matriu de teclat patchejada es INTERMITENT: si un moviment no
  respon, verificar el patch (0x177 == C9) i el buffer abans de concloure res.
- Els guards del dirty-flag son per CLASSES d'estat que canvien l'ordre del
  render (scroll, carry...): si apareix una classe nova amb save/restore propi
  (p.ex. revisar el projectil si torna a fer coses rares), afegir-li guard.

**Pendent**: cost 4-periodic in-mall (spans animats ~7 ms + ticks d'anim dels
enemics), marge resident 5 B (alliberar abans de tocar-lo), i el render
especialitzat de spans (render_tile_world a ~1,2 ms/tile = el crim).


### 20/11/2026 (nit III) - Mesura final: 25,0 fps EXACTES en zones tranquil-les; els 57-60 ms in-mall NO son la cinta

Correcio d'atribucio (mètode: bp al render_tile_world + comptador de cache):
- **Zones tranquil-les (sense enemics/cinta visibles, p.e. l'spawn): periode
  40 ms EXACTES = 25,0 fps** (el doble VSYNC clavat). Aconseguit.
- **In-mall (enemics a pantalla): ~20 fps** amb frames 4-periòdics a 57-60 ms.
  AQUEST cost NO es la cinta (0 crides a render_tile_world a la zona!) ni les
  descompressions de cache (comptador pla, per verificar amb simbol fresc):
  l'atribucio "cinta bimodal 3/10" de la sessio anterior ERA UNA HIPOTESI MEVA
  ERRONIA. La propera sessio: capturar el cost dels frames 4-periòdics amb els
  anchors de fase a la posicio in-mall (sospitos: el blit de l'enemic amb flip
  al tick d'anim (>>2)&1, l'update, o el hit-check).

**Protocol de mesura net (per la propera)**: teleport amb invuln + px8/py8
correctes (compte: un teleport a l'aire o paret = mort + respawn a l'spawn i
fa perdre la mesura); deixar SETTLEJAR la camera fins cam_x4 estable ABANS
de perfilar (el catch-up del pending es scroll actiu ~60-127 ms/frame i
contamina tota la finestra).


### 20/11/2026 (nit II) - M1 COMPLET: dirty-flag del sprite_restore_player (v4) + flip sense LUT + _spr_key_ops al pak C6

**Resultat mesurat (L1 idle, cpcse)**: `sprite_restore_player` 0 crides en 30 frames
en repòs (abans: cada frame). Periode idle: 60 -> 50 ms de mitjana (17 -> 20,1 fps):
els frames de no-fase de cinta cauen al bucket de 40 ms del doble VSYNC. Els frames
de canvi de fase de la cinta encara desborden (~57-60): la cinta es l'ultim tall
per als 25 fps.

**El cami (3 bugs trobats amb test real, un per versio)**:
- v1 (skip nomes del restore): el blit del jugador TAMBE desa el fons -> amb la
  pantalla sense restaurar desava el propi sprite al buffer C7 -> en moure's el
  restore plantava un "clon" persistent. Fix: skip del restore I del draw.
- v2 (+ stomp flag de la cinta): no arreglava res: el bug real era que CAMINANT
  la camera fa tracking 1:1 -> la dsx es CONSTANT -> la clau de posicio coincidia
  amb el darrer frame de caminar -> les pagines congelaven poses diferents del
  cicle i les INTERCALAVEN (el "estat anterior parpallejant"). Fix v3: compare
  de l'ANIM (s_mn_cur fresc) al draw site amb "heal tarda" (restore tarda + repinta).
- v3: l'heal tarda corria DURANT el scroll amb la base del draw (g_vram_start
  s'assigna DOS cops per frame: cam - page_dx pels restores, cam pel draw!) ->
  restaurava a l'adreça equivocada -> artefacte congelat a l'aturar. Fix v4 (la
  definitiva): GUARD DE SCROLL al check ASM: amb page_dx/dy != 0 -> dirty -> flux
  original complet. L'skip nomes opera en repòs total, on totes les bases son
  iguals i es matematicament segur.

**_spr_key_ops (slot 7 del pak C6, 0x5A15)**: tota la logica del check/save en ASM
al pak (~60 B) per no pagar l'allocator del SDCC al bucle de main() (el mateix
disseny en C costava +223 B de re-flow mesurats). Clau: k0 = dsx|dsy<<8,
k1 = face. Guards: mn_move/mn_jump != 0 + el guard de scroll v4. L'anim NO es a la
clau: el compare el fa el C al draw site (al check encara no s'ha seleccionat).
Modes del draw site: 0 = skip total, 1 = heal tarda (stomp o anim canviat:
restore tarda + repinta + desa clau i anim), 2 = flux normal.

**g_spr_tile_stomp**: el paren moving_bank_conveyor (C5, via bank_equ) i
world_flush_repaints quan escriuen tiles sobre la caixa del Jake quiet ->
el draw site fa l'heal (mode 1).

**LUT de H-Flip ELIMINADA (en2_init_lut fora)**: el gir Mode 0 es un swap de
pixels interleaved: flip(b) = ((b & 0x55) << 1) | ((b & 0xAA) >> 1) — EXACTAMENT
la formula que la init_lut precomputava. La dansa directa (sk_flip$, ~48 T/byte)
viu al cami fred de la cache i allibera els 256 B de 0x7900: el sostre del codi
C6 passa de la LUT (0x7900) al POOL DE FONS (0x7A00) = +256 B d'habitacio.
en2_flip_cell: .rept 8 -> loop (-75 B mes). C6: 0x78C6 (marge fins al pool: 330 B).

**Metode de verificacio (apres a pells, per futures sessions)**:
- El feed de tecles de l'API NO arriba a la matriu del joc. SOLUCIO: patchejar
  _cpct_scanKeyboard_f (0x177, el byte di -> C9=RET) i pokejar
  _cpct_keyboardStatusBuffer (0x3601, 10 B actiu-baix: bit A ZERO = tecla
  premuda; CursorRight = linia 0 bit 1 = FD). Aixo condueix el Jake amb l'INPUT
  REAL del joc (fisica, anim, camera): reproduccio dirigits completa sense
  dependre del teclat. RESTAURAR el byte 0xF3 (di) abans de tornar el control.
- L'evidencia grafica son DADES: la caixa del Jake llegida de la VRAM de cada
  pagina (ring: addr = (base_hi|(y&7)<<3|hi(off))<<8 | lo(off), off =
  (y>>3)*80+(x>>1)) i comparada byte a byte. Pagines iguals = correcte.
- El marge resident queda a 5 B: la propera feina resident REQUEREIX alliberar
  espais primer (portar C a banc o ASM a ma).

**Pendent (per els 25 fps)**: moving_draw_conveyor_tiles (bimodal 3/10 ms, el
darrer tall gros), probes de player_physics (~0,5 ms real en idle), early-out del
hit-check (~1 ms).


### 20/11/2026 (nit) - Dirty-flag del sprite_restore_player: disseny verificat, BLOQUEJAT pel pressupost resident (+223 B de l'allocator)

**Objectiu mesurat (19/11)**: el `sprite_restore_player` costa ~4 ms per frame en repòs
(redibuixa el fons de sota en Jake encara que no es mogui). El dirty-flag (skip del restore
quan aquesta passada repintara EXACTAMENT els mateixos pixels) estalviaria ~4 ms/frame.

**Disseny (verificat semanticament abans de codificar)**:
- El blit amb mascara es IDEMPOTENT per un redraw identic: dst = (dst & mask) | img
  conserva el que ja hi ha a les zones transparents. El draw del jugador sempre repinta
  el sprite sencer i sana sol qualsevol tropa (un enemic que hagues passat per sobre i el
  seu restore hagues esborrat la zona de solapament).
- Condicions de skip: repos pur (mn_move==0, mn_jump==0) + posicio de pantalla (dsx/dsy
  + sentit) + estat (climb/crouch/carry) iguals a l'ultim draw D'AQUELLA pagina + cap
  animacio ciclica en repòs: s_dying_timer/s_dazed_timer/s_dance_timer fan CICLAR l'anim
  (select_player_anim els llegeix!) i el parpalleig d'invulnerabilitat amaga frames.
- Analitzats i tancats els forats: caminar amb clamp de pantalla (dsx congelat pero
  l'anim cicla: exclòs amb el gate mn_move==0), toggle de crouch en repòs (clau de
  crouch), transicio d'escala (clau de climb), recollir caixa (clau de carry).

**BLOQUEIG (mesurat, 3 builds)**: el resident te 119 B de marge post-F1, pero afegir el
codi al bucle de main() dispara l'ALLOCATOR de l'SDCC: +146 B amb la versio hoist (el
call desubicat forca spills), +223 B inline, +227 B amb helper propi + claus empaquetades
(2 u16 per pagina). El cost NO es el codi del feature (~90-100 B) sino el re-flow global
de l'assignacio de registres de la funcio main() de ~1.400 linies amb --max-allocs-per-node
15000. REVERT net.

**Via per la propera sessio**: implementar `spr_rest_is_clean` com a ASM a ma (~40-50 B
en un .s: cadenes de comparacions globals sense passar per l'allocator del C) o alliberar
200+ B de resident abans de tornar-ho a provar en C. Els altres objectius mesurats
(conveyor bimodal 3/10 ms, probes de player_physics ~2 ms, early-out del hit-check ~1 ms)
no tenen aquest problema: son canvis de BANC (C5/C6), no del resident.


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


