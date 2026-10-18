# ESTAT DEL PROJECTE — The Blues Brothers (CPC, català)

Última actualització: 2026-10-18 — Cicle complet de Game Over, animació de ball de mort (1:1 DOS), resolució del crash en recarregar l'Splash (preservació de registres al FDC i protecció de la ISR musical), retorn net a FRONT_RUN i reinici de partida verificats en ZEsarUX.
Idioma de treball amb l'usuari: **català**.

## Estat vigent — Cicle de Mort, Game Over 1:1 DOS i Retorn Net a l'Splash

- **1) Cicle de Vides i Animació de Ball de Mort (1:1 DOS)**:
  - **Mecànica fidel a DOS (`level.c:1583-1658`)**: En perdre l'últim cor (`g_hearts_count == 0`), en Jake s'immobilitza completament (`move = jump = grab = crouch = 0`, velocitats a zero) i executa l'animació de ball de mort durant ~1,3 segons (`s_dying_timer = 64` a 50 Hz). L'input de l'usuari queda bloquejat com a l'animació de noqueig (`s_dazed_timer`).
  - **Respawn amb vides restants**: Si `g_lives_count > 1`, es resta una vida, es recuperen els 3 cors (`g_hearts_count = 3`) i en Jake reapareix a la posició inicial (o al checkpoint actiu `g_checkpoint`).
  - **Game Over**: Si `g_lives_count <= 1`, en Jake entra en l'última mort. Durant el ball de mort, la pancarta gràfica `GAME OVER` (`draw_gameover_banner`, 0x6A00 del Banc C0) es dibuixa directament sobre l'acció al backbuffer. En expirar el temporitzador, s'atura la música, es posa la paleta en negre i es recarrega el paquet `FRONT.PAK` per tornar a la pantalla d'inici (`FRONT_RUN`).

- **2) Diagnòstic i Resolució del Crash al Retorn a l'Splash (Ralles blanques i Reset a BASIC)**:
  - **Causa Arrel 1 (Clobber de DE al driver FDC)**: A `src/moving.c` dins de `fdc_load_file()`, per restaurar el driver FDC a RAM scratch `0x8000` des de `C0:0x7800`, hi havia un bloc `__asm` que feia `ld de, #0x8000` seguit de `ldir`. Segons la convenció ABI d'SDCC 4.5 (`__sdcccall(1)`), el segon paràmetre d'una funció (`const DiskFileDesc* desc`) es passa en el registre `DE`. Com que el bloc ASM no preservava `DE`, aquest acabava amb el valor `0x8311` (final del buffer de còpia). En cridar tot seguit `FDC_BANK_ENTRY(0x8000)`, el driver FDC intentava interpretar `0x8311` com a descriptor de fitxer, llegia sectors CHS brossa del disquet i escrivia bytes corruptes arreu de la RAM del sistema (generant les ratlles blanques i trencant la pila cap a BASIC).
  - **Solució 1**: Protegit el bloc d'assemblador amb `push de` / `pop de` i `push af` / `pop af`, preservant rigorosament el punter de descripció de disc i el banc previ.
  - **Causa Arrel 2 (ISR musical activa sobre banc buit)**: A `engine/mus.s`, `_mus_stop` aturava els xips AY però no netejava el flag `_g_mus_ready`. En recarregar `MUSBANK` a `0xC1`, la interrupció de 300 Hz podia cridar un player encara no inicialitzat o una zona buida de memòria. S'ha afegit `xor a; ld (_g_mus_ready), a` dins de `_mus_stop` com a blindatge atòmic.
  - **Solució 3 (Reinicialització de variables de vídeo i VRAM)**: Abans de saltar a `FRONT_RUN` a `main.c`, es reajusten `s_back_page = 1` i `g_vram_base_hi = 0x80` per assegurar que la VRAM estigui sincronitzada amb el mòdul d'arrencada.

- **3) Verificació de Regressió Completa en Temps Real (ZEsarUX)**:
  - Desenvolupat el test de regressió `tools/test_gameover_natural.py`, que inicia el joc des de disquet, navega per selecció i mapa, carrega el Nivell 1 i fa avançar en Jake contínuament contra els enemics al llarg de 3 cicles complets de mort.
  - S'ha verificat:
    - Pèrdua progressiva de cors amb parpelleig d'invulnerabilitat.
    - Ball de mort a cada caiguda i reaparició neta (vides: 3 -> 2 -> 1).
    - Última mort amb pancarta de Game Over.
    - Retorn net a la pantalla d'Splash (`FSPLASH`) sense cap píxel corrupte ni ratlles blanques.
    - So i música d'inici reproduint-se correctament.
    - Transició immediata a la selecció de personatge en prémer la barra d'espai.

- **4) Paritat 1:1 DOS Prèvia (Discos d'Habitacions, Salt amb Caixa, Memòria Neta)**:

- **3) Optimització Radical de Memòria i Expansió de Pila i Codi**:
  - **Causa**: Els buffers de restauració de fons d'objectes portats (`_s_carry_bg_c0` i `_s_carry_bg_80`, 640 B) i de caixes (`s_crate_bg[2][64]`, 128 B) residien a `_DATA` a la Base RAM 0, deixant la pila perillosament reduïda i el marge de `_CODE` molt ajustat.
  - **Solució**:
    - Reubicats els buffers de globus/paraigües al Banc 7 d'expansió (`0x7100` i `0x7240`) a `engine/sprite.s`, protegits per `bank_set(0xC7)`.
    - Reubicats els buffers de fons de caixes al Banc 7 (`0x7380` i `0x73C0`) via macro `CRATE_BG_PAGE(p)` a `src/main.c`.
    - **Alliberats 768 bytes nets** de la memòria resident `_DATA`!
    - L'àrea `_DATA` s'ha reduït d'1.113 B a **només 345 B** (`0x3880..0x39D9`).
    - L'espai lliure de pila fins a `SP = 0x3FFE` ha crescut de 933 B a **1.573 bytes lliures** (>1,5 KB!).
    - Marge de seguretat de `_CODE` ampliat a **+205 bytes lliures** (amb `--data-loc 0x3880`).
    - Eliminades commutacions redundants de banc al bucle d'enemics.

- **4) Eliminació de Glitches Gràfics Aleatoris i Alineació de Caixes**:
  - `carry_draw()` força sempre alineació de byte parell (`& ~1`) a `cx`, evitant accessos de 5 bytes que desbordaven el buffer de 64 bytes de la caixa.
  - `enemy_room_exit()` neteja `g_mag_elevators[i].drawn[0..1] = 0` per garantir que cap ascensor restauri fons stale.
  - `enter_door()` neteja a zero tots els flags de dibuix i repintat (`s_rep_n = 0`, `s_have_drawn[0..1] = 0`, `s_carry_drawn[0..1] = 0`).

- **5) Animació d'Estrelles de Noqueig d'en Jake 1:1 DOS**:
  - Quan en Jake rep un cop (`s_dazed_timer`), s'activen seqüencialment els frames 26, 27 i 28 de DOS (posició ajupida amb estrelles blanques i roses girant en cercle tridimensional al voltant de la gorra), tal com verificat a `verify_dazed_stars_0.png` i `verify_dazed_stars_1.png`.

- **6) Pressupost de Memòria i Marges Actuals**:
  - **Bloc 0 (`_CODE`)**: `0x0100..0x37B3` (14.003 B) | **+205 B** de marge net abans de `_DATA` (`0x3880`).
  - **Bloc 0 (`_DATA`)**: `0x3880..0x39D9` (345 B) | **1.573 B lliures** de pila fins a `SP = 0x3FFE`.
  - **Banc 5 (`BANK5.BIN`)**: `0x6E00..0x7FC4` (4.112 B de codi, **368 B lliures**).
  - **Banc 6 (`ENEMYCODE.BIN`)**: 6.219 B | marge positiu (+1.816 B lliures a `0x78E8..0x7FFF`).
  - **Banc 7 (`0xC7`)**: `0x7100..0x73FF` buffers d'objectes/caixes, `0x7660..0x783F` buffers Jake, `0x7840..0x7A1F` H-flip, `0x7A20..0x7DFF` EXTRA.BIN. Marge sobrant ample (>1 KB).
  - **Banc 5 (`BANK5.BIN`)**: `0x6E00..0x7FC4` (4.112 B de codi, **368 B lliures**).
  - **Banc 6 (`ENEMYCODE.BIN`)**: 6.219 B | marge positiu (+1.816 B lliures a `0x78E8..0x7FFF`).
  - **Banc 7 (`0xC7`)**: `0x7100..0x73FF` buffers d'objectes/caixes, `0x7660..0x783F` buffers Jake, `0x7840..0x7A1F` H-flip, `0x7A20..0x7DFF` EXTRA.BIN. Marge sobrant ample (>1 KB).

## Històric anterior — Paquet de Nivell Data-Driven al Banc 5, Peixeres (Natació + Aigua Animada) i Fix del Border Vermell

- **Arquitectura desacoblada Motor Resident (Bloc 0) vs. Paquet de Nivell (Banc 5)**:
  - **Empaquetador automàtic (`tools/pack_level.py` → `src/level_pkg.h`)**: Extreu de les dades originals de DOS (`tools/blues_dos/bb/staticres.c`, `MAP0.BIN`, `TRIG0.BIN`) les dimensions del nivell, coordenades d'inici i càmera, posicions dels ascensors i els **18 trams de tiles animats (`s_level_anim_spans`)** amb les seves **7 seqüències de 6 fases (`s_level_anim_seqs`, MCM de 2 i 3)**.
  - **Mòdul de Nivell al Banc 5 (`src/moving_bank.c`, `0x6E00..0x7DFF`)**: Com que al Banc 5 (`0xC5`) tant `MAP0.BIN` (`0x4000`) com `TRIG0.BIN` (`0x6400`) hi estan mapejats directament, s'hi executen sense commutació de bancs l'actualització d'entitats, l'animació dels 18 spans a `MAP_MUT`, el repintat d'spans visibles al backbuffer, l'empenta de cintes (`op == 27/28`), els efectes dels tiles sobre en Jake (escala `tt==7`, aigua `tt==11`, recollida de globus `tt==8`, paraigua `tt==9`, caixa `tt==5`, pop del globus al sostre `tt > 5`) i la màscara de reixes de primer pla (`TRIG_PTR` byte 9 `avt_num` 12..17).
  - **Motor Genèric Resident (`src/main.c`, Bloc 0)**: Sense cap coordenada ni tile ID hardcodejat del Nivell 1; conté únicament el bucle de doble buffer a 25 Hz, la física genèrica de col·lisió sòlida i la màquina d'estats d'animació d'en Jake.

- **Peixeres i Natació fidel a DOS**:
  - **5 Frames autèntics de natació (`PFRAMES.BIN`, índexs `21..25`)**: Extrets de `SPRITE.SQV` amb `tools/generate_cpc_jake_dos.py`:
    - `21`: `swim_idle` (DOS frame 48) — flotant a l'aigua.
    - `22, 23`: `swim_stroke1`, `swim_stroke2` (DOS frames 46, 47) — braçada horitzontal (cicle `21 -> 22 -> 23`).
    - `24`: `swim_vert` (DOS frame 49) — impuls vertical amunt/avall (alterna `21 <-> 24`).
    - `25`: `swim_floor` (DOS frame 45) — estirat al fons de grava de la peixera quan `s_on_ground == 1`.
  - **Física d'aigua (`tile_type == 11`, `climbing == 2`)**: Enfonsament suau (`s_vy = +8`), ascens fins a la superfície (`s_vy = -12` mentre el tile superior sigui `11`), descens ràpid (`s_vy = +16`) i despresa automàtica d'objectes en entrar a l'aigua.
  - **Animació de la superfície de l'aigua i vores de les peixeres**: Dirigida automàticament pel byte 4 (`anim_idx`) de `TRIG0.BIN` a través de `s_level_anim_spans` (fila 30, columnes 46..58 i 68..80: superfície `131 <-> 199`, vora dreta `149 <-> 217`, vora esquerra `170 <-> 247`).

- **Correcció del Border Vermell (`CANARY_ADDR`)**:
  - `CANARY_ADDR` a `engine/stack_canary.h` s'ha reubicat de `0x3900` (on l'àrea `_DATA`, que arriba fins a `0x3AC6`, el sobreescrivia legítimament disparant l'alarma `cpct_setBorder(0x4C)`) a `0x3B40` (per sobre de `_DATA` i per sota de `SP = 0x3FFE`). El border es manté 100% negre (`RGB=(0,0,0)`).

- **Pressupost de Memòria i Compilació**:
  - Temps de compilació reduït a **~30 segons** (`--max-allocs-per-node 15000`).
  - **Bloc 0 (`_CODE`)**: `0x0100 .. 0x3229` (12.585 B), **1.143 bytes lliures** abans de `_DATA` (`0x36A0`).
  - **Bloc 0 (`_DATA`)**: `0x36A0 .. 0x3AC6` (1.062 B), **1.336 bytes lliures** de pila fins a `0x3FFE`.
  - **Banc 5 (`BANK5.BIN`)**: `0x6E00 .. 0x7DFF` (4.096 B carregats, **512 B de marge** a la finestra i >1.000 B lliures de codi intern).

## Històric recent — Vol en globus vermell i Paraigües 100% ASM i sprites autèntics

- **Visualització del Paraigües (`s_carry_kind == 8`)**:
  - **Sprite autèntic de DOS**: Extret de `SPRITE.SQV` frame 107 (48×32 px DOS = 12 bytes × 16 línies en Mode 0 + 12B màscara = 640 B empaquetats a `EXTRA.BIN`).
  - **Animació i poses d'en Jake**:
    - **En repòs o a l'aire**: Utilitza el frame 20 (`carry_float`, frame 39 de DOS), amb ambdós braços alçats subjectant el mànec del paraigües i les cames enrere.
    - **En moviment/caminar**: Utilitza l'animació de carregar objectes de DOS (`g_crate_walk` = frames 14, 12, 13, 15).
  - **Renderització ASM**: Implementat `_sprite_blit_umbrella` (12 bytes/línia) i restauració unificada a `_sprite_restore_umbrella` / `_sprite_restore_carry`.

- **Vol en Globus vermell (`s_carry_kind == 2`)**:
  - Utilitza l'sprite del globus (DOS frame 103) i en Jake utilitza estrictament el frame 20 (`carry_float`, frame 39 de DOS) amb els dos braços amunt agafant la corda.

- **Eliminació definitiva del rastre visual (Bug del registre BC en ASM)**:
  - **Causa arrel**: A `_sprite_blit_balloon` i `_sprite_blit_umbrella` (`engine/sprite.s`), la commutació `_bank_set` es realitzava després de carregar `BC = #_s_carry_bg_c0`. Com que `_bank_set` utilitza internament `ld bc, #0x7F00; out (c), a`, destruïa `BC` fixant-lo a `0x7F00`.
  - El fons net es guardava a `0x7F00` (corrompent la taula LUT d'H-flip), mentre el buffer real quedava a `0x00` (Pen 0 = Blanc). En restaurar, deixava un rastre permanent.
  - **Solució**: L'assignació de `BC` s'executa estrictament DESPRÉS de `call _bank_set`. El fons es restaura de forma 100% neta i transparent.


## Estat vigent — Sprites de Jake 16 px Mode 0, camisa blanca i animacions completes

- **Amplada d'Sprite real (16 píxels Mode 0 / 8 bytes × 30 línies)**:
  - Superat el límit anterior de 12 px (6 bytes) que tallava les extremitats d'en Jake.
  - El salt amb cames separades subjectant el barret (frame 7 de DOS, 32 px DOS = 16 px Mode 0 = 8 bytes) ara es mostra **complet de cap a peus**, amb els dos peus, sabates i mitjons sencers sense cap retall.
  - Els frames d'ajupit i arrossegar-se (frames 4, 5 i 6 de DOS) es mostren amb l'amplada i silueta reals.
  - Blitter ASM (`engine/sprite.s`) i restauració de fons desenrotllats a `.rept 8` i `ld bc, #8`.
  - Llindar de wrap VRAM ajustat a `0xF8` ($256 - 8$) per evitar corrupcions de memòria en els extrems de línia.

- **Solució definitiva de la Paleta de Colors**:
  - **Pen 0 (`0x4B`) — Blanc Pur exclusiu per a Jake**: En analitzar les 256 rajoles de `TILESET0.BIN`, s'ha comprovat que cap rajola de l'escenari utilitza el Pen 0 (0 píxels totals). Assignar el blanc al Pen 0 permet una camisa completament blanca i sòlida sense alterar l'escenari.
  - **Pen 2 i Pen 15 (`0x40`) — Gris Metàl·lic original restaurat**: Totes les canonades, bigues i parets de l'escenari recuperen el seu to gris metàl·lic original, solucionant el problema on tot el nivell s'havia tornat blanc.
  - **Pen 1 (`0x47`) — Carn / pell**: Cara i mans d'en Jake.
  - **Pen 11 (`0x54`) — Negre sòlid**: Vestit, barret i ulleres de sol.
  - **Pen 4 (`0x44`) i Pen 12 (`0x5F`)**: Detalls blaus del vestit.

- **Gir Horitzontal (H-Flip) sòlid i sense fallades (`engine/sprite_hflip.s`)**:
  - Rutina ASM de reflex horitzontal adaptada a 8 parells per línia (`.rept 8`), amb offset inicial de màscara a 14 i salts de 32 bytes entre línies font.
  - Buffer de gir dedicat al Banc 7 a `0x7700 .. 0x78DF` (480 bytes), aïllat de qualsevol buffer d'ascensors o fons.
  - Moviment cap a l'esquerra fluid, sense escombraries gràfiques ni reinicis del CPC.

- **Mapa de Memòria al Banc 7 (`0xC7`)**:
  - `0x4000 .. 0x70BF`: 26 frames d'en Jake (`PFRAMES.BIN`, 12.480 B).
  - `0x70C0 .. 0x751F`: Buffers dels 5 ascensors magnètics (1.120 B).
  - `0x7520 .. 0x760F`: Buffer restauració fons Jake pàgina C0 (240 B).
  - `0x7610 .. 0x76FF`: Buffer restauració fons Jake pàgina 80 (240 B).
  - `0x7700 .. 0x78DF`: Buffer de gir horitzontal H-FLIP (480 B).
  - `0x78E0 .. 0x7EFF`: **1.568 bytes lliures** de seguretat.
  - `0x7F00 .. 0x7FFF`: Taula LUT H-FLIP (256 B).

- **Pressupost de Memòria del Bloc 0 (`0x0000..0x3FFF`)**:
  - `_CODE`: `0x0100 .. 0x368D` (13.709 B), marge positiu de 19 B fins a `_DATA`.
  - `_DATA`: `0x36A0 .. 0x37A5` (261 B).
  - Canari de pila a `0x37E0`.
  - Marge de pila lliure (SP fins a `0x3FFE`): **2.137 bytes lliures**.

- **Verificació Automatitzada amb ZEsarUX**:
  - Testejat amb `tools/verify_all_actions.py` cobrint repòs, caminar dreta, caminar esquerra, ajupir-se, arrossegar-se i saltar a l'aire. Totes les accions validades i capturades correctament.

## 📚 Històric — sessió de neteja del motor Mode 0

En aquesta etapa es va reescriure el motor de vídeo **des de zero** (sense codi
Mode 1). Les notes següents documenten aquella iteració; l'arquitectura vigent
és la descrita al principi d'aquest fitxer i a `DOCS_128K_ARCHITECTURE.md`.

### Bug CRÍTIC: variables `static` amb inicialitzador > 0 no es copien
`--no-std-crt0` → els valors inicialitzats (`_INITIALIZED`) NO es copien a RAM.
`static u16 g_cam_col = 22;` quedava a 0! Cal **inicialitzar explícitament al `main`**
(`g_cam_col = CAM0_COL;`). Això va fer que la càmera comencés a (0,0) i no es mogués.

### Els tiles estan BÉ convertits
`TILESET0.BIN` correcte (tile 16×16 = 64 B, 2 subtiles 8×8 de 32 B). El que passava
era la càmera i l'inicialització de variables.

### Estat actual del motor (`src/main.c`, `src/render.c`, `engine/sprite.s`)
- Fons del magasin es dibuixa correcte (càmera inicial col 22, row 110).
- **Sprites en ASM Z80 pur (`engine/sprite.s`)**:
  - `_sprite_restore_player`: restauració ultra-ràpida amb `LDIR` (~9.000 T-states, 30 línies).
  - `_sprite_blit_player`: blit amb màscara i desat de fons simultani (~35.000 T-states, 30 línies).
  - **Arreglat el bug de barres verticals mirant a la dreta**: eliminat `ex af, af'` que acumulava deixalles entre bytes.
  - **Resolució definitiva del tall de la meitat inferior (carrera del feix / V-Blank)**:
    1. **Identificació de la causa física real**: La rutina anterior de blit era molt lenta (~48.000 T-states) a causa d'indexació amb `IY`, salts condicionals i variables temporals a memòria per cada byte. Sumant la restauració de fons (`LDIR`, ~9.000 T-states), el temps total des del VSYNC pujava a ~58.000 T-states.
    2. Com que el feix d'electrons arriba a la línia 98 de Jake als 43.520 T-states i es mou 5,5 vegades més ràpid que el blitter (256 T-states/línia vs ~1.400), **el feix avançava al blitter a mitja alçada de l'sprite (línia ~111)**. La meitat inferior encara tenia el fons restaurat i es dibuixava a VRAM un cop el feix ja havia passat, sent esborrada al següent VSYNC abans que el feix pogués tornar-la a mostrar. Per això a la pausa d'scroll (on no es cridava el restore) l'sprite es veia sencer, però en joc normal només la meitat superior.
    3. **Nou blitter desenrotllat ultra-ràpid (`engine/sprite.s`)**: Format `[inv_mask, img_masked]` precalculat a `tools/gen_player.py`. Per cada byte s'eliminen totes les branques, l'ús d'`IY` i els accessos a RAM: `ld a,(de) ; ld (bc),a ; inc bc ; and (hl) ; inc hl ; or (hl) ; inc hl ; ld (de),a ; inc de`. Blit complet de 30 línies en només **~21.000 T-states** (més del doble de ràpid).
    4. Temps total de restauració + blit = ~30.000 T-states, acabant **13.000 T-states abans que el feix arribi a Jake**. L'sprite és 100% visible, sòlid i complet (cap, cos, cames i sabates) a 50 FPS reals sense cap tall.
    5. **Optimització d'estat aturat (`src/main.c`)**: Quan Jake està quiet a la mateixa posició i fotograma, s'evita la restauració i redibuix innecessaris, deixant l'sprite absolutament ferm i sense parpalleig.
- **Sprites Mode 0 (C64 24×30 px, 4 frames únics)**:
  - Peces autèntiques C64 (`1.bmp`): `cap 00` + `cames 01..03` (idle/caminar), `cap 04` + `peus 05` (salt), `BODY_OFF = 13`.
  - Format ajustat: 24×30 píxels (eliminades 4 línies buides a sota). Sola de sabata a la fila 29, recolzant exactament sobre la línia de superfície.
  - Deduplicació: idle i pas 1 comparteixen frame.
  - Blitter ASM ultra-ràpid: 30 línies en només ~21.000 T-states, buffer de fons de 360 bytes.
- **Física i col·lisions de plataformes 1:1 (Titus)**:
  - *One-Way Platforms* (caixes, taules, graons d'escala, op 14): mai bloquegen horitzontalment ni des de sota. En Jake les pot travessar caminant o saltant cap amunt.
  - Únicament quan en Jake cau cap avall (`s_vy >= 0`) des de dalt, actuen com a suport i aterra a sobre.
  - Sostres sòlids reals (`op == 20`) bloquegen el cap; plataformes no.
  - En aturar-se (`move == 0`), torna fidelment a *idle* (peus junts a terra).
- **Scroll en memòria amb `scroll_shift_*` (històric, substituït 2026-10-05)**:
  - Aquesta implementació desplaçava les dues pàgines amb `LDIR`/`LDDR` i
    provocava una baixada forta de rendiment.
  - El model vigent és el ring CRTC documentat a `DOCS_128K_ARCHITECTURE.md`:
    R12/R13 mouen l'origen i només es renderitza la tira entrant.
- **Dades i memòria**: Codi = 11.950 B (límit 0x3600, marge lliure de **1.618 bytes**), `bluesb.dsk` llest per executar (`RUN"BLUESB"`).

## Objectiu
Remake de *The Blues Brothers* per Amstrad CPC, text en català.
- **ARQUITECTURA DECIDIDA: MODE 0** (160×200, 16 colors) per l'estètica Titus.
  - Titus the Fox, Prehistorik 2, Super Cauldron (Titus, CPC natiu) són tots mode 0.
  - La versió C64 de Blues Brothers és 160×200 multicolor → encaixa quasi 1:1 amb mode 0.
- Motor bare-metal SDCC 4.5 (sense CPCtelera), a `C:\Projects\bluesb_cpc`.
- Referència d'estil de motor: `C:\Projects\despertaferro-sdcc45`.

## Per què mode 0 (fets tècnics)
- Mode 0 i mode 1 fan servir **la mateixa memòria de pantalla** (80 bytes/línia, 16 KB).
  Només canvia la interpretació: mode 1 = 4 px/byte (4 colors), mode 0 = 2 px/byte (16 colors).
- Per tant l'scroll és **més fi** en mode 0 (passos de 2 px), no més senzill mecànicament.
- El tileset en mode 0 ocupa el **doble** (un tile 16×16 = 16 línies × 8 bytes = 128 B vs 64 B en mode 1).
  Caldrà vigilar la memòria (no hi ha estalvi; la idea prèvia de "doble buffer gratuït" era ERRÒNIA).
- El parpalleig (flicker) **NO es resol sol** amb mode 0: és un tema de com esborres/dibuixes l'sprite.

## Estat del codi actual (ABANS de migrar)
- Funcionava a mitges en **mode 1**: títol via FDC, nivell renderitzat (TILESET+MAP+TRIG del disc),
  Jake es mou, col·lisions de terra OK, ~50 FPS.
- Problemes coneguts: **parpalleig de l'sprite**, **scroll a saltirons**, sensació poc àgil.
- **REGRESSIÓ ACTUAL**: l'intent de "dirty-rect sprite update" en C (`src/sprite_update.c`) va fer
  créixer `_DATA` fins a xocar amb els buffers FDC/stack → corrupció de memòria → Jake cau fora del món.
  - Mitigat reduint `SPR_SAVE_MAX` de 640 a 256 a `src/sprite_update.c` (màx. sprite = 8×31=248 B).
  - `_DATA` va quedar a 1681 B (0xA000–0xA691). Cal re-verificar que l'sprite es veu bé.
- **Aquest codi mode 1 s'abandonarà** en migrar a mode 0, però queda com a referència.

## Git
- Repo inicialitzat. Commits:
  - `7c52014` initial snapshot (mode 1, pre mode-0 migration)
  - `f5adff5` add .gitignore; drop emulator and build artifacts
- `.gitignore` exclou `tools/ZEsarUX_windows-13.0/`, `obj/`, `*.dsk/*.bin/*.ihx/*.map`, `tools/*.bmp`, `tools/*.png`, `__pycache__/`.
- **NO hi ha hagut mai control de versions abans d'avui** → cada canvi gran havia trencat coses sense revertir.

## Mapa de memòria (mode 1 actual; es revisarà per mode 0)
- Codi `0x0100..<0x3000` (límit dur: no passar de 0x3000 o xoca amb TILESET).
- `TILESET` @ `0x3000` (16 KB), `MAP` @ `0x7000` (9216 B), `TRIG` @ `0x9400` (2560 B).
- `_DATA` @ `0xA000`. Buffers FDC @ `0xB800`/`0xBA00`. Stack top `0xBFFE` (creix cap avall). VRAM @ `0xC000` (16 KB).
- **CRÍTIC**: `_DATA` NO pot créixer més enllà de ~0xB800 (FDC) / 0xBFFE (stack). Verificar sempre
  la mida de `_DATA` a `obj\bluesb.map` després d'afegir arrays grans.

## Restriccions del projecte (apreses)
- `--no-std-crt0`: BSS NO s'inicialitza → inicialitzar explícitament tota variable estàtica/global.
- `sdcccall(1)`: primer punter/16-bit a HL. **Crides C amb molts arguments (≥14) es garbellen a SDCC** → mantenir pocs arguments; buffers com a globals file-local.
- `sdasz80`: les etiquetes de codi no poden compartir nom amb símbols de dades; taules `.db` a dalt de `_CODE`.
- Tile sòlid = byte `op_func` a `GTRIG[num*10+2] != 25` (25 = buit). Nivell usa op_func 14/20 (terra) / 25 (buit).
  Model de terra portat de cyxx/blues: `level_floor_yoff` retorna 0 per op_funcs {14,20,31,34,36,38} (superfície a dalt del tile).
- Player: sense caixa de paret horitzontal; head-block + foot-land, plataformes one-way.
- Inici DOS del jugador: `level_xpos[39]=64 px`, `level_ypos[39]=1136 px`; `PH=16`.

## Flux de treball build/run
- `py.exe tools\build.py` des de `C:\Projects\bluesb_cpc`.
- L'usuari llança l'emulador i fa `RUN"BLUESB"` manualment (els send-keys de ZRCP NO arriben a BASIC).
- Comanda d'emulador:
  `tools\ZEsarUX_windows-13.0\zesarux.exe --noconfigfile --machine CPC6128 --enable-dsk --dsk-file C:\Projects\bluesb_cpc\bluesb.dsk --enable-remoteprotocol --remoteprotocol-port 10000`
- Eines de debug: `tools/zrcp.py` (client ZRCP port 10000), `tools/dbg.py` (`save-screen` dona la pantalla visible; `set-memory-zone -1` abans de `disassemble`), `tools/vram2png.py`.

## Pipeline de gràfics (mode 1, existent)
`tools/bbdata/`: unsqz, ilbm, mode1, bbconvert, sprites, bbspr*, bgtiles, bbmap, test_pipeline.
Genera `TILESET.BIN / MAP.BIN / TRIG.BIN` (MAGASIN.BIN = TRIG).
Font: `assets/bbdata/` (versió PC/DOS, `.EXE`, `.SQV`, `.SQL`, `.BIN`, `.CK1/.CK2`).

## ACTIU ARA: destripament del disc C64 (ESTAT: parcial, encallat al loader)
Discos a `assets/`:
- `Blues_Brothers_The_1991_Titus_Software_cr_B_t_3_B.d64` — versió original Titus (carregador encriptat).
- `BB.d64` — crack "Skelotor/The Unbeatable" (fitxers numerats, també comprimits).
- `Blues_Brothers_Chain.t64` — cinta (multi-load, s'atura esperant playback).

### Eines creades (per a futures sessions)
- `tools/d64.py` — parser/listador/extractor de D64 pur Python. `list` / `bam` / `extract`.
- `tools/vicebin.py` — client del **Binary Monitor** de VICE (port 6502): mem_get/set,
  regs, checkpoints, autostart, screenshot, keyboard feed. (Cal arreglar: `screenshot`
  → display_get dona frames amb glitches en headless; usar render des de RAM.)
- `tools/vicemon.py` — client del monitor remot **de text** de VICE (port 6510).
- `tools/cpu6502.py` — **emulador 6502 complet + desassemblador** en Python. Validat.
- `tools/run_dec.py` — harness per executar el decrunch de Titus (`07_7`) offline.
- `tools/c64gfx.py` — renderitzador VIC-II (bitmap/chars/sprites) + paleta Pepto.
- `tools/c64_decrunch.py` — captura del decrunch via VICE (breakpoints).
- **VICE 3.x instal·lat a `C:\VICE`** (x64sc, c1541, ROMs). Clau per a tot el flux C64.

### Fets tècnics apresos (IMPORTANT)
- VICE emula el joc i **arriba a executar codi real del joc** (PC per $15xx–$3Dxx).
- La **intro es mostra bé**: "PROUDLY PRESENTS: THE BLUES BROTHERS!" (pantalla a $3400,
  color RAM a $3600; rutina de còpia a $0842). Capturada a `tools/screen_now.png`.
- Després de la intro el PC queda en **bucle mort a $083F (`JMP $083F`)** dins el fitxer
  de l'etapa 1. El loader no continua amb l'autostart de VICE → probablement cal el
  trigger multi-load (NMI/timer) o l'ordre real del loader original.
- Els **fitxers numerats del disc NO coincideixen amb la RAM del joc** (match <2%) →
  estan **comprimits**. Cal el descompressor.
- El **descompressor de Titus** és el fitxer `7` (extret `assets/c64rip/07_7.prg`),
  carrega a **$CE00**, és un **LZ77 amb bitstream MSB-first + gamma coding** (taula a $CF08);
  `$CEFF` = getbyte (CHRIN), `$CEA7` = getbit, `$CED6` = copy/back-ref, destí a $FC/$FD.
  A `assets/vice_rip/ram_game.bin` hi és present a $CE00 però **no s'executa** durant
  l'autostart (breakpoint a $CE36 no dispara).
- El crack `BB.d64` té cracktro que espera **foc** (bucle $1704–$170C, `LDA $DC00/$DC01`).
  Patchant `$170A` de `29 10` a `29 00` s'avança, però el flux no acaba de carregar el joc.
- `tools/c64gfx.py` render de la RAM de `ram_game.bin` mostra un **charset/tiles de text**
  a $5400 (regió densa $5400–$8100). Pendent identificar tileset/mapa/sprites del nivell.
- **PISTA CLAU del multi-load:** a `ram_game.bin` el vector IRQ ($0314) = $0647 i hi ha
  codi de **LOAD** del loader a **$0690** (`LDA #8/TAX/TAY/JSR $FFBD(SETNAM)/...`), més
  rutines a $0650/$0673 que mouen dades $FD00↔$5000. El fitxer d'etapa 1 acaba amb
  `CLI; JMP $083F`, o sigui **l'avanç d'etapa depèn de l'IRQ/timer** (per això amb el
  monitor remot aturat no avança i sembla penjat). Cal reproduir-ho amb l'IRQ corrent.

### DESBLOQUEIG: el descompressor FUNCIONA (validat!)
Extrets els PRG en **format PC64 `.p00`** a `assets/prgs/` (26-byte header + PRG amb load
address). Fitxers del disc original i les seves adreces:
- `1`→$5D22, `2`→$5B1D, `3`→$7524, `4`→$7322, `5`→$A629, `6`→$271C, `7`→$CE00 (decrunch).
- `blues bros3-[b]`→$0801, `blues pic`→$0801.

Mètode validat (`tools/vice_dec_all.py` + `tools/vice_dec_test.py`):
1. Carrega el codi del decrunch ($CE00, el fitxer `7`) a VICE.
2. Patcha les 2 crides CHRIN `$EE13` → lector de RAM a `$CF20` (punter `$E0/$E1`).
3. Patcha el bucle de banks (`$CE2E`) i la sortida (`$CE30`) perquè acabi net.
4. Posa el fitxer comprimit a RAM, arrenca a `$CE14`, executa.
5. L'output s'escriu a `dest` ($FC/$FD) i **decreixent**.
- **Validat**: el fitxer `1` descomprimeix 771 B a $DDFE-$E100, que coincideixen
  **256/256** amb `ram_game.bin` (la RAM real del joc). O sigui el descompressor és
  correcte i `assets/vice_rip/dec_out1.bin` conté el resultat bo.
- El destí ve del **header de 5 bytes** del fitxer: file[4]→$FB, file[3]→$FC, file[2]→$FD,
  file[1]→$FE, file[0]→$FF. dest = $FC|($FD<<8).
- `tools/vice_dec_all.py` incorpora un **sentinella de final de stream**: el lector patxejat
  salta a $CFFF quan el punter font arriba a `src+len` (detectable per polling). Funciona
  (s'arriba a PC=$CFFF), pero **la direcció/i mida exacta de l'output encara no està
  clarificada**: per al fitxer `1` l'output validat és $DDFE-$E100 (771 B, match 100% amb
  `ram_game.bin`), però el punter $FC/$FD final dóna valors que no quadren amb un simple
  escriptura decreixent. Cal acabar d'entendre el moviment del punter de destí.
- El meu emulador `cpu6502.py` té un **bug** al decrunch (produeix zeros); la referència
  correcta és l'execució a VICE. Un cop arreglat, descomprimiria offline ràpid.
- **METODE ROBUST VALIDAT (doble execució)** a `tools/dec_all3.py`: s'executa el decrunch
  DUES vegades amb la regió de destí inicialitzada amb $00 i amb $FF; els bytes que
  coincideixen són output real (independents de l'estat inicial). L'span es detecta des de
  `dest` cap avall mentre els bytes són estables.
  - Fitxer `1` → 257 B a $E000-$E100, **match 257/257 amb `ram_game.bin`**.
  - Fitxer `4` → 513 B a $E000-$E200.
- **Detalls del format que falten per quadrar**:
  - El decrunch s'atura sol al cap de ~2297 bytes del fitxer `1` (llegeix 2297/8800). La
    resta del fitxer no es processa en una sola crida → hi ha múltiples blocs/estadis.
  - Els fitxers amb **bit buffer inicial $FB ≠ 0** (`2`=`c1 c3 80 dd b4`, `3`, `5`, `6`)
    no convergeixen amb el mètode actual → cal entedre el seu header/terminació.
  - `$FB` ve de file[4] (header de 5 bytes); els fitxers `1,4` tenen $FB=0 i funcionen.
- El meu emulador `cpu6502.py` **coincideix amb VICE exactament fins al 2n write** però
  després divergeix (bug subtil pendent al voltant del copy/back-ref). La referència bona
  és VICE.
- **El fitxer `1` (257 B) és output net i validat**; `assets/dec/` conté els intents.

## ANÀLISI DEL MOTOR TITUS (referència: Titus the Fox CPC)
L'usuari ha deixat dos DSK: `assets/Titus the Fox (1992)(Titus).dsk` (original) i el
crack `[cr NPS][t NPS].dsk`. El BB CPC és un mal port d'Spectrum → no serveix; el
**Titus the Fox CPC** (Titus natiu, mode 0) és la referència del **motor**.

### Eines creades
- `tools/dsk.py` + suport **Extended DSK** a `tools/dskutil.py` (llista/extreu DSK CPC).
- `tools/z80.py` — **desassemblador Z80** (base+CB+ED+DD/FD; validat).
- `tools/scan_ports.py` — escaneja accessos a ports (CRTC/GA/PPI).

### Troballes
- Disc original: `FOX.BIN` (15 KB, loader+engine amb editor de nivells de dev),
  `FOX0..9.SQZ` (assets), `UNSQZ.BIN` (descompressor).
- **Format SQZ del CPC = arbre tipus Huffman** (NO el diccionari LZ del DOS):
  node: byte0=byte de sortida (fulla); word a +5 = fill si bit=0; word a +7 = fill si bit=1;
  bits MSB-first; punters de fills = adreces absolutes. Capçalera 4 B (mida u16 + dict_len u16).
  `py` equivalent a `unsqz16` dona les mides correctes però no descodifica (falta l'arbre).
- `FOX.BIN` fa un **checksum de tota la RAM** (protecció) i crida firmware `0xBC00`.
  Usa ports PPI `0xF4–0xF7` (teclat/sound), GA `0x7F`, i CRTC a 0x2AAC/0x3362.
- El crack pre-descomprimeix: el main carrega a **0x5A26** i els **overlays/nivells a
  0x40AE–0x60EF** → banc **0x4000–0x7FFF** (model 6128: pantalla 0xC000, codi 0x0100,
  nivells/overlays al banc 0x4000 amb bank-switching). Però main i overlays surten
  **empaquetats/proteigits** (desassemblatge i render donen soroll).
- ZEsarUX **no arrenca en aquest entorn** (sense pantalla) → l'anàlisi dinàmica (traça)
  cal fer-la amb l'emulador de l'usuari en marxa + ZRCP.

### MOTOR TITUS: TROBAT I CAPTURAT (via ZEsarUX ZRCP en viu)
**Captures guardades:**
- RAM completa **128 KB**: `assets/fox_full128k.bin` (via `set-memory-zone 0` + `read-memory`).
- RAM mapejada 64 KB: `assets/fox_mapped64k.bin`, `assets/fox_ram_game.bin`, `fox_ram_move.bin`.
- Estat: `assets/fox_io_final.txt` (CRTC+GA+PPI+AY), `fox_regs_final.txt`, `fox_pages_final.txt`.
- Pantalles reals (`save-screen`): `tools/fox_real.png`, `tools/fox_final.png`, `tools/play_*.png`.
- Disc: extrets a `assets/fox_cpc/` (original) i `assets/fox_crack/` (crack).
**Entropia per banc (128 KB):** banc 0=codi (7.02); banc 3=gràfics (4.61, 0% zeros);
banc 5=buid (0.74). Els gràfics donen **franges** al render lineal → format **no-lineal**
(planar/empaquetat), pendent de desxifrar.
**Nota**: el joc **remapea bancs dinàmicament** (codi i pantalla canvien de regió).
Workflow que funciona: ZEsarUX amb `--enable-remoteprotocol`; l'usuari fa RUN i juga;
l'assistent connecta per ZRCP (`tools/zrcp.py`) i usa:
- **`save-screen file.bmp`** — pantalla REAL renderitzada (resol el dubte de mode/interleave).
- **`get-io-ports`** — dona **CRTC Registers**, **Gate Registers**, PPI i AY.
- **`get-memory-pages`** — bancs; **`disassemble`**; `get-memory-zones` (RAM size).
- `help` llista 129 comandes (no hi ha lectura directa de CRTC però sí via get-io-ports).

**Troballes del motor (Titus the Fox CPC, mode 0):**
- **SCROLL = per maquinari via CRTC R12/R13** (Display Start Address). En gameplay
  R12/R13 = `0x3311`. **R3 = 0x06** (HSW petit → possible scroll/raster fi; el CPC usa
  R3 per desplaçar la imatge uns píxels).
- **Mode 0** (Gate Array reg 02 = `0x8C`), **ROMs desactivades**.
- **Màquina 128 KB** (RAM 131072).
- **Mapa de memòria**: codi a `0x0000–0x3FFF` (banc 0); **nivell/tiles a `0x4000–0x7FFF`**
  (banc 1); **pantalla a `0xC000`**.
- **Assets = overlays** carregats del disc (SQZ) cap a `0x4000–0x7FFF` segons convingui.
- Captures guardades: `tools/fox_real.png` (gameplay real), `assets/fox_scr_game.bin`,
  `assets/fox_ram_game.bin`, `assets/fox_ram_move.bin`.

### RUTINA D'SPRITE trobada (flicker-free sense doble buffer)
Amb un **memory breakpoint d'escriptura** (`set-membreakpoint addr 2 len`) sobre la
pantalla, ZEsarUX atura a **`0x314A`** → la rutina d'sprite és a **`0x30E9–0x3152`**.
Anàlisi:
```
30E9 PUSH BC / PUSH HL
30EB LD B,0x07                 ; ~8 files d'sprite
30ED LD A,(IX)                 ; font de l'sprite
30F4 AND 0x55 / AND 0xAA       ; MASCARES de grups de pixels (transparencia)
30FE XOR (HL)                  ; combina amb la pantalla
30FF LD (DE),A                 ; desa el resultat a (DE)  [buffer de fons]
3100 LD (HL),C                 ; dibuixa a (HL)  [pantalla]
310B LD A,H / ADD A,8 / AND 0x38 / CALL Z,0x3B45  ; adreçament interleaved CPC
```
**Tècnica (la clau del "sense parpalleig"):** blit amb màscara + **desat del fons en
una sola passada** (llegeix pantalla, combina amb sprite, desa el fons i dibuixa alhora).
Així el fons es pot restaurar i mai hi ha un frame amb l'sprite esborrat → sense flicker.
Màscares `0x55`/`0xAA` resolen la transparència per grups de pixels.
El **scroll** és per CRTC (R12/R13), per tant el fons no es redibuixa mai.
`set-membreakpoint` + `enable-breakpoints` + `clear-membreakpoints` són les comandes clau.

### Proper pas per al motor (requereix ZEsarUX obert per l'usuari)
1. Carregar el crack i fer `RUN`.
2. Via ZRCP: dump del mapa de memòria (on queda cada overlay), veure escriptures CRTC
   (R12/R13/R3 = scroll) i GA `0x7F` (bank-switching 128K).
3. Capturar la RAM carregada → format de tiles/sprites mode 0.

## AVENÇ: pipeline Mode 0 des de DOS/EGA + sprites C64
Hem pivotat amb èxit: **tiles/mapa del DOS/Amiga → Mode 0** i **sprites del C64 → Mode 0**.
- `tools/bbdata/mode0.py` — conversió Mode 0 (160×200, 16 colors, 2 px/byte).
- `tools/bbdata/bbmap0.py` — genera `TILESET0.BIN` (16 KB), `MAP0.BIN` (9216),
  `TRIG0.BIN` (2560) del nivell 1 (Magasin). **Preview validat**: `tools/level1_m0.png`
  (el nivell sencer es veu correcte). Un tile 16×16 DOS → 8×16 Mode 0 = 64 B;
  256 tiles = 16 KB (mateixa mida que Mode 1!). Crida: `py tools\bbdata\bbmap0.py --prefix MAG --preview ...`
- `tools/je2m0.py` — converteix les fulles C64 (BMP 8×8 sprites de 24×21) a Mode 0 amb
  **màscara** (`[mask,img]` per byte; blit `scr=(scr&~mask)|(img&mask)`). Colors C64
  (crema=transparent) → pens CPC: negre→0, gris→15, blau→1.
  - Jake: `assets/jake_elwood_sprites/jake_m0.bin`, Elwood: `elwood_m0.bin`
    (64 frames × 504 B = 32256 B cadascun).
  - Previews: `tools/jake_ega.png`, `tools/elwood_ega.png`.
- **ATENCIÓ memòria sprites**: 32 KB per personatge (2 = 64 KB) → caldrà reduir
  (frames compartits, cames compartides com diu l'usuari, o menys estats).
- Fonts dels sprites: `assets/jake_elwood sprites/1.bmp` (Jake) i `2.bmp` (Elwood),
  graella 8×8 de 24×21.

### Sistema de PECES (sprites C64) — CLAU
Els sprites C64 són una **llibreria de peces**: un personatge = 1 sprite de **CAP** +
1 de **CAMES/COS**, apilats **en vertical** (offset vertical; a `tools/compose_m0.py`
`BODY_OFF=13`, alcada final 24×34). Un cap serveix per a varies cames. Nedar/arrossegar-se
= **dues meitats en horitzontal** (pendent). Jake i Elwood **no comparteixen cames**.
H-flip a runtime per la direcció oposada (no hi ha miralls a les fulles).

**Taula d'animacions (índexs de la fulla `jake_XX`), proporcionada per l'usuari:**
- `00` cap normal · `01,02,03` cames caminar · `04` cap salt · `05` peus salt
- `06` cap portant caixa/objecte · `07,08,09` cames portant objecte
- `10,11` pujar escales · `12` cap de 13/14 (?) · `15,16,17` ajupit + caminar ajupit
- `18,19` Elwood pujant escales · `20,21` cop amb el sostre · `22,23` patacada
- `25-30` combinacions de nedar · `31-36` ball (amb cap de caminar)
- `37-40` espera massa estona / llegint revista · `41-48` animació desconeguda (mirar codi open)
- `49,50` volar amb globus · `51,52` ? · `53-56` Elwood caminant · `57,58` Elwood saltant
- `59-62` Elwood amb objecte sobre el cap · `63` repetit amb `10`
**Elwood (`elwood_XX`):** `00` repetit · `04,05,06` Elwood ajupit-caminant · `07,08` escales
(repetit) · `09-12` cop al cap + assegut a terra · `13-19` Elwood nedant · `20-25` Elwood ballant
· `26-29` espera massa estona · `30-37` animació desconeguda · `38,39` volar amb globus
· `40,41` semblen repetits · `42-63` **escombraries (no usar)**.

Implementat: `tools/compose_m0.py` (munt cap+cames → Mode 0 amb màscara) amb
`idle/walk/jump`. Sortida: `assets/jake_elwood_sprites/jake_composed_m0.bin` (5 frames).
Preview: `tools/jake_anim.png`.

## PLA DE PORT A MODE 0 (arquitectura, inspirat en Titus Fox + cyxx/blues)
**Objectiu:** motor CPC mode 0, 128 KB, scroll CRTC, sprites flicker-free, lògica de
cyxx/blues portada mòdul a mòdul.

### Model de memòria proposat (128 KB)
- `0x0000–0x3FFF` codi principal (banc fix).
- `0x4000–0x7FFF` **overlay** (nivell actiu: tiles+mapa+triggers) — es carrega del disc.
- `0x8000–0xBFFF` buffers (back buffer d'sprite, taules, HUD).
- `0xC000–0xFFFF` pantalla.
- La resta de bancs (4-7): assets/nivells pre-carregats o codi extra.

### Formats
- **Tileset**: DOS `CK1`+`CK2` (2×320×200 ILBM) → Mode 0 (tile 16×16 → 8×16 = 64 B).
- **Mapa** `SQL`: 128×72, 1 byte/tile (bit7=half CK1/CK2, bits0-6=tile num).
- **Triggers** `BIN`: 256×10 (op_func a byte 2; solidesa = 14/20/31/34/36/38).
- **Sprites**: DOS `SQV` (planar 4bpp) → Mode 0 amb màscara `[mask,img]`.

### Física (de cyxx/blues, unitats 1/8 px; object_t a game.h)
- `xmaxvelocity=48` (=6 px/f), `ymaxvelocity=15`, `xacc=0`, `yacc=2` (grav.).
- Salt: `yvelocity=-4`; alguns cops `-1`/`-3`. Velocitat de pantalla = `xvelocity/8`.
- `yfriction`/`unk2D` (xfriction) controlen fregament.
- Player: objectes 39 (Jake) / 40 (Elwood); 41 objectes, 30 portes, 6 nivells.
- Màquina d'estats d'animació via `animframes_ptr` + `anim_num`/`anim_frame`.
- **Model sub-píxel**: val la pena adoptar-lo (posicions i velocitats en 1/8 px) per clavat.

### PROGRÉS DEL PORT (fet)
- `src/scroll.c`: `level_floor_yoff` ara usa les **taules `op_table1`** de cyxx/blues
  (`g_optab1[4][16]`, `yoff = table[xpix]-1`) → suporta terra pla i **pendents**.
- `src/main.c`: **física refactoritzada a SUB-PÍXEL (1/8 px)** com l'original:
  posició `s_px8/s_py8` (1/8 px), velocitats `s_vx/s_vy`, `GRAV=2`, `SPEED_MAX=48`,
  `VY_MAX=15`, `JUMP_VY=-30`, acceleració `MOVE_ACC=8`. Aterratge amb `op_table1`.
- **Build OK** (`bluesb.dsk`, 13154 B). **Nou mapa de memòria**:
  codi `0x0100–0x3462`; TILESET `0x3600`; MAP `0x7600`; TRIG `0x9A00`; `_DATA 0xA400`
  (fins 0xB093); FDC `0xB800`; stack `0xBFFE`; VRAM `0xC000`.
- Constants de física fàcilment ajustables a `src/main.c` (per calibrar el salt/velocitat).

### Ordre de port
1. Motor base Mode 0 (fet: scroll CRTC, tiles, sprite, física simple).
2. **Lògica de nivell** (level.c): `do_level_update_tile`, portes, triggers.
3. **Sistema d'objectes/enemics** (objects.c + object_t): AI, projectils, agafar objectes.
4. **Animacions** completes (taules `animframes_*`).
5. HUD, so, transicions, música.

## MOTOR PORTAT A MODE 0 (en proves)
- `src/scroll.c`: render de tiles Mode 0 en **C** (substituint l'ASM `asm_row/column`),
  geometria nova (tile 8x16 = 2 subtiles; nivell 128 subtiles ample x 144 alt; area 20x20).
  MA del CRTC en paraules; `s_ma_base = s_step*2 + cam_subrow*40`.
- `src/sprite_update.c`: blit Mode 0 amb mascara nibble `(bg & ~mask) | (img & mask)`.
- `src/main.c`: `cpct_setVideoMode(0)`, paleta de 16 colors del nivell, fisica en píxels.
- `src/player_frames.h`: generat per `tools/gen_player.py` (5 frames Jake Mode 0, 24x34).
- `tools/build.py`: carrega `TILESET0/MAP0/TRIG0`.
- **Nou mapa de memoria**: codi `0x0100-0x32DF`; TILESET `0x3400`; MAP `0x7400`;
  TRIG `0x9800`; `_DATA 0xA200` (fins 0xAE90); FDC `0xB800`; stack `0xBFFE`; VRAM `0xC000`.
  Codi gairebé al límit (0x3400): ~300 B de marge.
- Build OK: `bluesb.dsk` (exec 0x2E1E). **Pendent de provar a l'emulador.**

## ATURAT: rip C64 (només per tiles/fons) no dona gràfics nets
S'ha aconseguit executar el joc a VICE (disc i cinta) i capturar la RAM del **gameplay**
(`assets/vice_rip/gameplay.bin`, PC=$C579, VIC bitmap multicolor + 7 sprites). Però:
- El joc fa **bank-switching i raster tricks** → una sola config VIC no renderitza la pantalla.
- Els renders surten amb franges; els sprites surten com a soroll.
- Els fitxers de disc i de cinta estan **comprimits** i no s'ha desxifrat el format.
- Conclusió: el rip C64 no és rendible sense invertir molt més temps en el packer/timing.

## DECISIÓ PROPOSADA: pivotar a DOS/Amiga → Mode 0
El material DOS/Amiga ja està extret i el pipeline Mode 1 funciona. Per a un *remake*
(no port 1:1) és suficient. Fer servir `assets/bbdata/` + `tools/bbdata/` per generar
els assets en Mode 0 (160×200, 16 colors). Les eines C64 (`tools/d64.py`, `vicebin.py`,
`cpu6502.py`, `c64gfx.py`) queden disponibles per si mai es reprèn.

## Properes passes (C64, si es reprèn)
1. Resoldre el trigger multi-load: inspeccionar vectors NMI/IRQ ($0318/$0314) i el loader
   a $0800–$0900; veure com avança d'etapa el loader original.
2. Alternativa robusta: **acabar el harness `run_dec.py`** (l'emulador ja descodifica bé el
   LZ; falta quadrar el destí i el bucle de banks $01) i descomprimir tots els fitxers
   offline. Després identificar tiles/sprites/mapa.
3. Comparar els assets descomprimits amb el material DOS/Amiga ja existent.
4. **Fallback**: escalat DOS/Amiga → Mode 0 160×200 (pipeline `tools/bbdata/` ja funciona).

## Properes passes (motor)
1. Documentar/planificar arquitectura mode 0: mida de tiles, pipeline gràfics, sprites sense flicker.
2. Migrar el motor a mode 0.
3. Enemies + música.

## Notes de sessió (incidències)
- Sessió molt llarga de rip C64. Es va acabar invertint molt de temps al loader/comprés.
- VICE headless: `display_get` dona frames amb glitches → no refiar-se'n; renderitzar des de RAM.
- El monitor remot de text bloqueja mentre VICE corre en warp; preferir binary monitor.
- L'assistent va quedar encallat en bucle generant comandes (tool calls) diverses vegades;
  per això part de la feina es va fer amb comandes manuals de l'usuari. Un xat nou hauria d'anar bé.

## Sessio CP-2.2 + SugarBoxV2 (2026-10-08)
- Objectiu: alliberar Bloc 0 (logica moving.* al Banc 5 via call_banked + slots 0x6E00+3k).
- Estat: boot (loads FDC, video, init/draw bankejats, render) OK intermitent;
  loop principal inestable (freeze amb vora verda / corrupcio creixent / reboot a BASIC).
- Bugs reals trobats i arreglats:
  1. cpct_setBorder llegia L en comptes de A (sdcccall1 passa u8 en A).
  2. render_tile_world, level_get_tile_type, get_tile_flags/op, world_set_tile
     feien cpc_bank_restore() cec (->C0) fins i tot cridats des del banc:
     ara prev=bank_set(...); ...; bank_restore(prev).
  3. moving_bank_push: eliminat set/restore (C5 garantit a l’entrada).
  4. stack_canary a 0x37E0 col-lisionava amb _DATA (ara a 0x3900).
  5. build.py: convergencia 3 iteracions (disk_tables.h <-> DSK); no matar-lo a la meitat.
- ZEsarUX ZRCP amb canals trencats (read-memory/save-binary retornen un buffer fix,
  breakpoints no disparen mai, CRTC dubtos). Fiables: screenshots, FDC track/motor, PC, border.
- SugarBoxV2 v2.1.1 instal-lat a tools/SugarboxV2 (TCP DebugServer JSON port 1234):
  getState/readRegisters/readMemory(ok, amb roundtrip)/writeMemory/disassemble/
  breakpoints/step/getScreen(PNG)/getGateArrayState(border,mode,ROMs,ramcfg,finestres)/
  getCrtcState/getFdcState(motor,pistes,sectors,CRC)/insertDisk/sendKey(line,bit).
  Llancament: Sugarbox.exe --cfg CPC6128UK [--hide] [-d] --ds 1234. ULL: connectar
  ATURA l’emulacio (cal continue); LimitSpeed=T per teclejar al 100%.
- sendKey: lletres simples OK pero amb perdues (~1/3 arriba); SHIFT trencat.
  Boot fiable = teclejar manualment a la finestra.
- Client: sb.py + scripts sb*.py (fora del repo, temp opencode).
- PENDENT: validar boot verd + loop (elevators DOS 60px/s, cintes, Jake amb input),
  treure marcadors DIAG TEMP, restaurar waits 12ticks+vsync per 25Hz reals.

## Sessio 2026-10-08 tarda: init DATA + validacio SugarBox
- TROBALLA CLAU: el start propi (LD SP + JP main) salta el CRT: _DATA (BSS)
  i _INITIALIZED (s_belts, taules belt, etc.) queden amb brossa de power-on.
  A SugarBox la RAM s’inicia amb patro 41 98 -> s_belts salvatge -> tiles
  salvatges per pantalla (franges) + crash. A ZEsarUX la RAM surt a zero
  (per aixo alla funcionava).
- FIX: CRT manual al principi de main() (memset BSS 0x36A0 398B + memcpy
  INITIALIZED 30B de 0x3850 a 0x382E). ATENCIO: adreces hardcoded del mapa
  actual; si creix _DATA/_CODE cal revisar (millor: simbols del linker).
- AMB waits restaurats (12 ticks + vsync) per test real a 25Hz (SugarBox VSYNC ok).
- PENDENT: boot verd + loop (validar amb sbvalidate.py quan l’usuari teclegi).

## Sessio 2026-10-08 nit: imatge truncada + build ranci + morts SugarBox
- TROBALLA 1: obj/bluesb.bin nomes cobria _CODE; _DATA/_INITIALIZED/_INITIALIZER
  (0x36A0..0x386D) MAI al DSK. FIX build.py: image_length() fins a fi de
  _INITIALIZER (bin 14190 B, BLUESB 14 blocs) + src/crt_addrs.h generat del mapa.
- TROBALLA 2 (build ranci): newer() per mtime saltava recompilar main.c ->
  binari amb descs {3903,8} vells vs taules {4259,10} -> spin de fail (PC 0x195B).
  FIX: clean total + force rebuild + frescor per hash (mtime O hash). Verificat:
  stale fora, fresh dins, start=0x13AF, marges OK (code 2947 B, pila 2000 B).
- PROVAT: firmware carrega 14190 B amb 0 mismatches; transfer a start OK (bp);
  teclejat automatic via chords sendKey (SHIFT-hold + tecla).
- OBERT: SugarBox DESAPAREIX (sense crash-log) durant el boot (~25 s dins el
  nostre loader, fase TILES/MAP), 4 cops. Sense determinar: crash app vs tancament.
- PENDENT: (a) datar mort / color marc per fitxer; (b) si cal revert (stash) a HEAD;
  (c) treure DIAG TEMP (BANK5-first, marcadors).

## Sessio 2026-10-09: BLUESB-first + DAT.BIN + ZEsarUX verd
- HEAD aa8acd0 arrenca SEMPRE a ZEsarUX (joc visible T+25/50/80). Saga no -> regressio nostra.
- CAUSA: posicio BLUESB al DSK (pistes 15-18 = reboot <8 s; pistes 0-2 = boot).
  FIX build.py: package() posa BLUESB PRIMER (blocs 2-12). Comprovat: saga boota (Jake idle T+25/50/80).
- DAT.BIN (30 B plantilla _INITIALIZER de l'ihx) com a fitxer DSK; main el carrega
  a scratch 0x3000 i fa memcpy a _INITIALIZED (fi del hardcode 0x3850 i de la imatge completa).
- Neteja DIAG: fora toggle per-frame i marcadors boot/bank (nomes alarma canari).
- SugarBox: FDC flaky (Exp1 0 mismatches vs 10262/10781 despres, mateix DSK) +
  lectures memType bancs incoherents. No es culpa del nostre codi (mateix DSK boota a ZEsarUX).
  Plataforma de test: ZEsarUX.
- PENDENT: retest boot DAT.BIN + estabilitat + input; valors START_PX/PY test (616/642).

## Sessio 2026-10-09 (2): starter reubicable + boot verificat fins al joc
- DISSENY: BLUESB = starter ~2 KB (load 0x3000) + GAME.BIN 14 KB (imatge 0x100..0x3869).
  DAT.BIN eliminat (la imatge completa porta _INITIALIZER).
- BUG 1 (auto-trepetjament): GAME [0x100..0x3869] cobreix l'starter [0x3000..0x37FF];
  al 91% el CALL final quedava corromput (PC 0x136C/0x0C06 -> BASIC). FIX: s_start
  PIC es copia a VRAM 0xC000 i salta a _s_main reubicat (exec hdr = 0x3000+offset).
- BUG 2 (ROM alta): a 0xC000 la CPU llegeix la ROM del BASIC (upper ROM ON al boot);
  la copia era invisible (JP a brossa ROM -> carry). FIX: s_start fa DI + RMR 0x8C
  (Mode 0 + ROMs OFF) ABANS de copiar. Lower ROM ja ve OFF de RUN (in-place funcionava).
- BUG 3 (RST 0x38): l'FDC fa EI intern amb ROMs OFF i sense ISR -> VSYNC = salt a
  brossa = reboot net (T+2.6->3.7). FIX: stub RET (0xC9) a 0x0038 a s_start (el joc
  instal-la la seva ISR despres). MCR (bank_set 0xC0-0xC7) NO toca ROMs (son RMR).
- Verificacio: CRC16-CCITT de GAME.BIN (build.py -> starter_tables.h GAME_LEN/CRC);
  starter: blau=s_main, groc=FDC ok, verd=CRC ok, vermell=corrupte (spin).
- Build robust: is_stale/mark_fresh (hash DESPRES de compilar; abans un kill
  enverinava i el seguent build enllacava ranci), placeholders nomes si falten
  (+ sentinella GAME_CRC), 3 iteracions convergeixen. NO matar builds a la meitat;
  correr en background (Start-Process) + sondejar (els logs per redirect perden la cua).
- ZEsarUX ZRCP après de debò: send-keys-string 250ms + chords SHIFT (").
  send-keys-string PERD els chars +&() (cal chord o evitar-los); '"' = SHIFT+50,
  ENTER esdeveniment 129. Breakpoints: enable-breakpoints PRIMER, despres set
  (index 1+; l'index 0 dona error); es perden amb cada restart; get-breakpoints/
  get-breakpointspasscount llegeixen, pero MAI s'ha vist un tret (dubtosos).
  read-memory/save-binary retornen brossa fixa (inservibles). Fiables: PC/SP,
  screenshots (save-screen BMP 800x544), vora per pixels. FDC: motor/pistes no exposats.
- `load"bluesb` dona `Memory full` (binari a 0x3000 sota HIMEM): cal RUN (els usuaris!).
- BOOT VERIFICAT: RUN -> firmware -> starter (verd) -> FDC (blau/groc) -> CRC (verd)
  -> joc (vora negra, nivell 1 dibuixat T+30). PENDENT: el joc es congela despres
  del primer render (PC 0xBA55/0xC07x, SP=(0xCD05), sense resposta a input);
  marcadors 0x41-46 a init per trobar la crida que ho penja (build en curs).
- Fitxers: engine/starter.c (DI/stub/RMR/copia/PIC + CRC + semafors),
  tools/build.py (ST_LOAD/RUN/DATA/WIN, exec=load+offset, GAME_LEN/CRC, crc16_ccitt,
  is_stale/mark_fresh, llavors nomes si falten), src/starter_tables.h (generat).

## Sessio 2026-10-09 (3): CP-2.2b + JOC JUGABLE (input, scroll, ascensors)
- Símptoma: boot perfecte (starter, CRC, loads, video, renders) pero el joc moria
  als primers frames (PC errant per 0xB8xx-0xC0xx, SP esclafat, canari tret,
  de vegades reboot net a BASIC). Determinista per build, variable entre builds.
- TROBALLA (disciplina bancs): el codi bancat MAI pot niuar a un ALTRE banc.
  En commutar C5->C7 des de moving_bank_draw/restore, la CPU continua llegint
  0x4000-0x7FFF: el propi codi (a 0x6E00+) desapareix i s'executen dades
  (ELEV.BIN/PFRAMES) -> salt salvatge -> canari + reboot/congelat. Només el
  codi CENTRAL pot commutar bancs (el seu codi a 0x0100-0x38xx no es desmapeja).
  C5-noop (mateix banc) sí és segur. PROVAT: niat C7 en init -> reboot;
  sense niat -> spin correcte.
- FIX: moving_bank_draw/restore TRASLLADATS a moving.c (residents, amb els
  mateixos bank_set(C7) segurs des de central). bank5_table slots 1-2 queden
  RETs morts (es conserven adreces). moving_bank_init/update/conveyor/push/find
  segueixen bancats (C5 o sense niat). ELEVATOR_OBJECT_H/SPR_HALF_W -> moving.h.
- TROBALLA 2 (bonus, mateixa sessió): l'SDCC genera epílegs desequilibrats
  (POP HL/POP AF + JP(HL)/caiguda, sense PUSH previs) als wrappers C de 3+ args
  (draw/conveyor/push/find). Els de 0-2 args (init/update/restore) fan cua JP
  neta i funcionen. FIX: wrappers void + bloc bc_* (com init); call sites
  posen bc_a..e i llegeixen bc_r. Verificat al binari (cues C3/JP).
- FIX 3 (mateixa sessió): call_banked feia OUT al port 0x7F00|prev (0x7FC0)
  en comptes de 0x7F00 (com bank_set/RMR). Ara LD BC,0x7F00 als dos OUTs
  (switch + restore). No era l'arrel (la GA ignora el byte baix) pero queda bé.
- Robustesa FDC (troballa paral·lela): el FDC de vegades llegeix un sector
  malament (mateix DSK: un boot carrega bé, un altre no). FIX: cada fitxer de
  dades es carrega amb CRC16 + fins a 3 reintents (taula CRC_* a disk_tables.h
  generada per build.py; falla total = vora 0x40+i + spin). GAME CRC ja hi era.
  DSK verificat byte a byte (GAME+8 fitxers OK) i CHS del starter verificat
  (14185/14185) abans de buscar el bug lògic.
- VERIFICAT JUGABLE a ZEsarUX: RUN"BLUESB -> starter (verd/blau/groc) -> joc
  (vora negra) -> nivell 1 + Jake idle; dreta 3 s (camina + scroll + zona nova
  amb ascensor), esquerra (torna), 30 s idle + 2 min totals sense crash
  (PC/SP sans, ISR/bancs corrents). Jump no provat (tecla curta al test).
- PENDENT USUARI: jugar de debò (escales, cintes, caure/dany, portes, nivells
  2+); el so encara exclòs (audio.s) i el títol és Mode 1 (TITLE.BIN).
- Nota ZEsarUX: breakpoints ZRCP es programen (enable primer, índex 1+) pero
  MAI s'ha vist un tret (passcount sempre 0; un bp a 0xBA00 va aturar la CPU
  en idle BASIC). read-memory retorna brossa fixa. PC/SP + screenshots sí fiables.

## Sessio 2026-10-10: CAIXES THROWING (grab/carry/throw + controls DOS)
- Triat per usuari: Caixes throwing. Referencia DOS tools/blues_dos/bb/level.c:
  SPACE=accio (agafar/llencar), UP=salt (SPACE+UP=canvi jugador); caixa _si==5,
  vol recte xvelocity +-128 sense gravetat, vanish vora/mur, erase UN tile.
- FIX 1 controls (src/main.c): SPACE/X/Fire1/Fire2=GRAB, salt nomes CursorUp/
  Joy0_Up inhibit amb SPACE (DOS inp_key_up && !inp_key_space). Abans SPACE
  saltava i bloquejava el test de caixes. Verificat: UP salta (3728), SPACE
  agafa (1032), sense interferencies.
- FIX 2 erase: filera (max 8 tiles) -> UN tile world_set_tile(gcol,grow,0)
  (paritat DOS do_level_reset_tiles). Forat 1 tile confirmat en captura.
- FIX 3 vol (bug real): s_carry_drawn/dx/dy compartits entre les 2 pagines
  (restore a posicio/pagina equivocada + slot BSS zero = QUADRAT BLANC 0x4B +
  parpelleig + resta congelada). Patro ascensors: drawn[2]/dx[2]/dy[2] per
  pagina; vanish restaura LES DUES pagines; carry_abort() (escala/aigua) idem.
  Resultat: vol recte +-154 SUB/f, vanish mur/vora, restore pixel-perfect
  (12 frames post-throw estatics, diff 0).
- Carry visual = frames jugador amb caixa (quiet 14, camina 15/13/14/16, aire
  16, salt feble -96); intent carry_held_draw separat REVERTIT (doble/brossa).
- Harness: settle 3 s post-boot OBLIGATORI (spawn 180/1050 cau ~2 s; taps en
  caiguda es perden: feet != caixa). Spawn hack 180/1050 REVERTIT a 32/1106.
- Build final: GAME.BIN 14190 B (0x0100..0x3208), marge 1176 B, pila 1996 B.
  Boot sanity des de spawn real: 4 s dreta fins al teatre (marquesina BLUE
  BROTHERS), scroll OK, PC/SP sans. Nota: build.py triga ~10-15 min (SDCC
  --max-allocs 200000); no matar-lo (un kill va deixar un DSK que no bootava).
  Flake FDC: 2 boots fallits (vora vermella/verda + brossa, PC=C4xx) amb DSK
  bons; retest amb DSK fresc OK.
- PENDENT: globus (2)/paraigua (8) agafar/volar/pop; walk-carry llarg; enemics/
  portes/transicions; so; t�tol Mode 1.

## Sessio 2026-10-10 (2): CAIXES FIDELS DOS (crouch+terra, reset gris, repaint post-restore)
- Mecanica corregida segons usuari+DOS (level.c:1227 _si=(xpos16,ypos16), ypos=snap peus-1; op14 unk2B):? agafar AJUPIT A TERRA (peus-1=fila caixa), MAI des de sobre; DOWN travessa one-ways incloses caixes (drop); caixa=plataforma (dret a sobre OK).
- FIX mostreig: grow=(py+PH-1)>>4 (era py+PH: agafava dret a sobre). Revertida exempcio drop en caixes.
- FIX forat invisible (bug real): world_set_tile pintava a l'input pero sprite_restore_player (fons stale amb caixes) ho Ressuscitava cada frame. Prova: marcador blau temporal OK, caixa intacta. Solucio: cua s_rep_* (3) + world_flush_repaints() post-restore pre-save+draw, amb camera fresca; MAP logic immediat.
- Verificat: control vs grab (mateixa banda: 848 vs 424 px vermells = 1 caixa menys), forat GRIS vei (tile20, mai blau), persisteix amb scroll (h_00 vs h_02 diff 0), vol+vanish nets (tl_f0 caixa volant, tl_f1 net).
- Spawn hack 180/1050 REVERTIT a 32/1106. Build final: GAME.BIN 14203 B (0x0100..0x3418), marge 648 B, pila 1983 B. Sanity spawn real: carrer + 4 s dreta fins teatre BLUE BROTHERS, PC sans.

## Sessio 2026-10-10 (3): GLOBUS AUTO-GRAB + VOL OK; SOBRE NO VISIBLE (obert) + REVERT EXPERIMENTS
- Referencia DOS (tools/blues_dos/bb/level.c:1227,1269-1287,934,1521-1528): `_si=type(xpos16,ypos16)` amb ypos=peus; globus (8)/paraigua (9) AUTOMATICS sense flag (nomes caixa demana carry_crate_flag); reset 2 files (obj + -1); unk3D=2 pujada yacc=-1 (~1px/f), unk3D=1 paraigua caiguda lenta; pop si type>5 2 files sobre l'obj37 o y<32.
- Implementat (src/main.c, NO commit): auto-grab `if(!carry && !climbing)` mostra (px+8,py+PH-1) -> 8/9, reset 2 files, kind=2/8 (caixa queda AJUPIT+TERRA+flanc SPACE); rise vy=-8 (kind 2); paraigua clamp vy<=8; pop DOS (bb=py-1, brow=fila-2, type>5 o bb<32 -> kind=0, vy=0); alliberar amb SPACE.
- Visual: `s_bloon_frame[128]` = cella 156 TILESET (banc 4) a parells [inv=0,img] (build 1 cop al grab); `bloon_draw` a (px+4,py-17) despres sprite (ultim); save/restore per pagina amb `s_crate_bg` compartit (estalvi 128 B); sprite jugador DOS 39 brac amunt (EXTRA_BASE) quan kind 2/8.
- Mapa: trio cols 23-25, fila 54 = 155 cordill (type 0) + fila 55 = 156 sobre (type 8); terra fila 56-57. Dempeus la mostra cau a 56 (terra) -> el trio S'AGAFA SALTANT (peus travessen 55), igual que DOS. Spawn hack 184/860 (cau a col 24).
- VALIDAT USUARI: auto-grab + vol sostingut OK (Jake puja, camera segueix, cordill mapa al costat).
- BUG OBERT (report usuari): el sobre vermell MAI apareix al cap; el que es veu es plataforma hazard estatica del fons ("ascensor"). Verificat en captures netes (cel obert, kind==2 estable a la fisica).
- Dades dures acumulades: cella 156 = sobre vermell (hexdump: fons CC + motiu files 1-12; res de groc/negre); blitter span4=8px opacs OK; ring_address amb mon OK (mateix patro carry_fly/elevadors); paleta: 0xFF = blanc pen15; type = TRIG0[tile*10]; cel columna pujada te tiles type 10 (132/17/230) -> pop hi peta (legitim si DOS te mateixos types; per verificar).
- Via d'investigacio (massa llarga, sense conclusio): mostreig/pop/gate/unitats SUB/paleta/adreces, tot correcte sobre el paper. Unica peca no verificada: contingut real de `s_bloon_frame` (lectura runtime banc C4) vs blit/restore.
- EXPERIMENTS REVERTITS (ordre usuari, glitches nous): marcadors blancs cantonada + blit forcat + tile 156 forcat a la cantonada cada frame (AQUEST embrutava el mapa = glitches); un overflow _CODE (-24B) pel cami; trail debug (19 si llegeix 8) ELIMINAT per fer lloc i NO restaurat (dormant, nomes podia pintar graffiti; declarat a l'usuari).
- Estat final: bloon_draw original + auto-grab + pop + spawn 184/860; cap resta DIAGNOSTIC/DEBUG/TRAIL (grep net); build GAME.BIN 14341 B, marge 219 B, pila 1845 B, DSK regenerat. Sense commit, sense test (aturat per parlar).
- PENDENT: (1) un sol experiment net: pintar `s_bloon_frame` aillat amb pipeline de tiles (que funciona) -> vermell = frame bo (bug al blit/restore) vs brossa = bug lectura banc; (2) tema separat aparcat: des de l'spawn quiet UP no salta fins que camines (s_on_ground/climbing?); (3) verificar type 132 en DOS per decidir si el pop al cel es fidel.

## Sessio 2026-10-11: HUD C64 (1 banda, 5 slots) + dieta Bloc 0
- HUD estil C64 en UNA banda (files 20-21, R6=22 intacte): cara, vides 1 digit, 5 cors, icona+digits vinils, 5 slots col.leccionables gris->color (cols 24-33). 39 tires (936 B). Verificat en pixels (3/3 cors/00/slots grisos).
- Vides inicials = 3 intents (2,1,0), confirmat per usuari; el codi ja posava 3. Maxim real 8 -> 1 digit suficient.
- pack_level.py: extreu els 5 parells 135-139/140-144 (abans nomes el del nivell); indices nous 19..38, 0..18 intactes en esperit (vinil/cor/digits renumerats: digits base 13->9).
- DIETA (~-320 B nets): `_scr_addr_table` 400 B -> `scr_raw_first` (calcul exacte) + `scr_raw_next` (bump +0x800 / +0x50 al wrap, verificat inclos wrap 2KB) en 6 loops (restore/blit + 4 carry via first/next). Sprites identics + pila sana en viu.
- Neteja: `engine/render.s` (_render_hud Mode 1 mort) i `engine/level.s` (Mode 1 mort) esborrats; `verify_bonus_live.py` versionat (mai executat: scratch/ no existeix).
- BUG canari (preexistent): _DATA havia crescut per sobre de CANARY_ADDR 0x3B40 (trepitjava `_s_carry_drawn`: falsa alarma permanent + corrupcio al boot). Mogut a 0x3C00; build.py avorta (FATAL) si _DATA hi arriba. Vora negra confirmada en captures.
- Marge Bloc 0: +114 B (amb HUD 5 slots). PENDENT DECISIO per 500+: FDC fora del GAME (~2000 B, nomes boot) o banquejar fisica (~2000 B) o 1 slot (+384 B).

## Sessió 2026-10-10 (4): RESOLT BUG DEL GLOBUS (SPRITE AUTÈNTIC DOS 103 + JAKE 39 + COL·LISIÓ MEMÒRIA BANC 7 RESOLTA)
- **Diagnosi del bug de l'ascensor i mida gegant**:
  1. *Col·lisió de memòria al Banc 7*: `ELEV.BIN` (448 B) es carregava a `0x78E0`, acabant a `0x7AA0`. Però `EXTRA.BIN` (Jake braç amunt) es carregava a `0x79A0`. Per tant, `ELEV.BIN` sobreescrivia els primers 256 bytes d'`EXTRA.BIN`! Quan en Jake agafava el globus i demanava `EXTRA_BASE`, el personatge es convertia en l'ascensor!
  2. *Sprite i posició incorrecta*: Abans es copiava la cella estàtica 156 del tileset a `py - 17`, tapant 11 línies de la cara/pit d'en Jake.
- **Solució implementada**:
  1. *Sprite autèntic de DOS*: Extret el frame 103 de `SPRITE.SQV` de DOS (16 DOS px / 8 Mode 0 px = 4 bytes $\times$ 28 línies d'alçada), un globus vermell rodó amb reflex blanc, nus i cordill blanc que arriba just a la mà alçada d'en Jake.
  2. *Reorganització del Banc 7 (`0xC7`)*:
     - `0x78E0 .. 0x7A9F`: `ELEV.BIN` (448 B)
     - `0x7AA0 .. 0x7DDF`: `EXTRA.BIN` (832 B) [Jake frame 39 braç amunt: 480 B + Caixa: 128 B + Globus frame 103: 224 B]
     - `0x7DE0 .. 0x7EBF`: Buffers fons globus (`BLOON_BG_PAGE0` 112 B + `BLOON_BG_PAGE1` 112 B)
     - `0x7F00 .. 0x7FFF`: H-FLIP LUT (256 B)
  3. *Optimització de RAM*: Eliminat l'array `s_bloon_frame[128]` de `_DATA` i el codi de construcció de frame a `main.c`.
  4. *Posicionament*: El globus es dibuixa a `(px + 4, py - 27)`.
- **Verificació a ZEsarUX**:
  - Validat en execució real (`scratch/trace_game.py`):
  - Captures reals preses durant el vol (`trace_float1.png`, `trace_float2.png`): en Jake puja agafant el cordill d'un globus vermell rodó perfecte, camisa blanca impecable, corbata, ulleres de sol, fons net sense rastre d'ascensors ni corrupció visual.


## Sessio 2026-10-11 (2): F1 loader verd + ARREL del reboot (scratch paginable)
- F1 infra build verd: FDC.BIN 784 B (entry 0x8000) -> slot C6:0x7000; starter N-fitxers (GAME 30 sectors + FDC 2 sectors) amb vores blau/groc/verd/vermell+gris pre-salt; GAME_LEN/CRC + FDC_LEN/CRC_FDC regenerats; DSK byte-verificat (BLUESB/GAME/FDC identics a obj/).
- ARREL (debug 6 h, 30+ hipotesis mortes): l'scratch del motor a 0x7000 central cau DINS la finestra paginable 0x4000-0x7FFF. Al primer bank_select el motor es pagina ell mateix i executa dades (PC al buffer 0xB9xx, SP volat, backtrace amb cadena 70EB/70C2/7036 intacta). Hang o reboot segons la deriva (brossa depenent de sector).
- FIX (1 adreca): scratch 0x7000 -> 0x8000 (VRAM pag.2, no paginable, invisible, esborrat pel memset post-carregues). build.py FDC_BANK_BASE/DATA 0x8000/0x8300; stub copia 2x512 C6:0x7000 -> 0x8000 + verifica CRC + reintenta; slot C6:0x7000 intacte (emmagatzematge). BOOT VERD: 7 assets + video_init (vora negra +58 s) + render + loop (PC 03EB) + input (Jake dreta + scroll verificats).
- Robustesa shippada: starter verifica CRC_FDC (abans skip) via s_bank_apply; stub verifica+reintenta scratch (penja blanc 0x4B si falla); gris pre-salt 0x40 conservat. DIAG temporals revertits (t9/V2/V3/marcadors GAME/delay/ELEV-only/RET-stub).
- Marges: _CODE 0x0100..0x35C1 (447 B lliures), _DATA ..0x3BCD (pila 1073 B), Banc5 marge 175 B, STARTER 1809 B. Llico ZRCP apresa: send-keys-string perd '"',;() -> '"' per chord SHIFT+50, ENTER=129; save-screen ranci durant motor (frames buits/fantasma); read-memory retorna buffer estatic (inutil); cpu/breakpoints disponibles pero no calgueren.
- APARCATS (no reboot): hflip 0x7700 cau en finestra paginable (possible corrupcio silenciosa sprites mirallats, F0-shipped); OVERFLOW _CODE detectat en afegir disk_tables.h sencer a moving.c (resolt amb extern g_crc_fdc 2 B). PENDENT usuari: commit?; seguent F1 (FRONT/ZX0/musica) o test gameplay nivell 1.

## Sessio 2026-10-11 (3): Deute F1 (hflip, warnings, marges)
- hflip 0x7700 EXONERAT en viu (LEFT 1.5 s: Jake mirallat coherent amb caixa): el call-site pagina C7 als dos costats, flip+blit toquen C7:0x7700 (gap lliure 0x7120-0x78E0, 480 B exactes) i la LUT C7:0x7F00. Afegit contracte en comentari (0 B). Fragil per obscuritat, correcte per construccio.
- Warnings starter eliminats: delay C -> ASM (LD BC,60000; DEC/JR, ~0.3 s) i s_main u8+return -> void (36 B menys aprox). Build net, pressupostos iguals (_CODE 447 B, pila 1073 B). Boot retestat verd (groc/verd/gris/negre + render + loop PC 03D6).
- Marge _CODE 447 B declarat SA (mesura per gaps de mapa massa sorollosa per dietes cegues; hflip desenrotllat intocable per perf). Retall futur si cal: stub-verify (~70 B) quan l'scratch sigui de confiansa + gris pre-salt (12 B).

## Sessio 2026-10-12 (1): F1 FRONT verd (splash -> boot jugable sense tecles)
- ARREL splash-escombraria (3 bugs encadenats, tots reals, tots fixats):
  1. Decoder v1-fitxers vs v2-decoder: `zx0_decompress.s` era el `dzx0_standard` ACTUAL (v2, MSB invertida) pero el build comprimeix `classic=True` (v1, MSB pla). Coincideixen en literals/last/len/MSB=1 (12 primers blocs be) i divergeixen a la primera gamma MSB multi-bit (bloc 13: V=2 -> C=137, ASM=265). Trobat per lockstep C-vs-sim bit a bit + encoder com a arbitre ((D-1)//128+1, (127-x)<<1). FIX: core verbatim `OLD_V1/dzx0_standard_CLASSIC.asm` (69 B, +1 B), validat al sim (16000/16000 identic, END net).
  2. Suicidi 0x8000: `s_fshow` carregava el .ZX0 a 0x8000 = casa del motor (PC=0x80F4 executant bytes ZX0). FIX: scratch 0x8400 (motor fins 0x8310, FDC_BUF 0xB800; pitjor cas MAP ~6.7 KB < 0xB800).
  3. .BIN lineal vs HW entrellacat: `gen_screens.py` escrivia lineal (preview be) pero el 6845 llegeix `((L%8)*2048)+((L//8)*80)` (ratlles). FIX: .BIN pre-entrellacat 16384 B + preview `_hw.png` WYSIWYG (render HW del fitxer; ha de ser identic a `_m0.png`).
- home-bank FDC (FUTUR banked): `fdc_load_file(home,...)` 1r param (A) -> byte `g_fdc_home_bank` (NO AF': EX es SWAP, restores parells brossa) + restore via `LD A,(0x8308)` + fail-path restore. REGRESSIO cacada: FDC.BIN 784->785 B trenca `FDC_IMAGE_LEN` hardcoded (white-hang). FIX robust: `g_len_fdc` (main.c) + assert FATAL al build si difereix (mai mes hang silencios).
- Wait tecla: `return 0` + test-en-A(SDCC) = espera infinita -> `s_fkres` static + `ld a,(s_fkres)` (convencio _bank_get); despres wait amb TIMEOUT 8000 scans (~4 s): si scan be espera tecla, si retorn encallat auto-avanca. `quantize()` no-determinista entre runs (previews valids pero varien; no afecta format).
- VERD en emu: splash correcte (cara/barret/titol/paleta) -> timeout -> 7 assets (motor home) -> video/render/HUD -> nivell 1 JUGABLE sense tecles (captures auto2/auto3/auto4). Marges: _CODE ..0x372A (86-113 B), STARTER 1809 B, FDCBANK 785 B. PENDENT: SELECT/MAP (re-activar + FRONT.BIN C4 per marge), press-escurca (retorn s_fkey sospitos, timeout ho cobreix), musica AKY, commit.

## Sessio 2026-10-12 (2): FRONT.BIN banked C4 + 3 pantalles verdes
- Overlay C4:0x4000 (523 B: `engine/front.c` f_fkey/f_fpal/front_run + `front_table.s` slot JP + `front_ext.s` EQU generats del mapa resident). Args per memoria central (`FrontArgs g_front_args`: home/desc/palhw; patro motor FDC, cap ABI fragil). Nomes toca central/VRAM/PPI/GA (mai finestra bancable); el TILESET el sobreescriu en acabar. `build_front()` amb asserts FATAL (entry, overlap, mida) + `g_len_fdc`-style: no hi ha magic.
- `main.c`: s_fkb/s_fkey/s_fpal/s_fshow eliminats (~100 linies) -> `front_one()` (omple args + bank_set/call/restore) x3 (SPLASH/SELECT/MAP). `starter.c` carrega FRONT.BIN a C4:0x4000 amb CRC (vermell si corrupte). DATA_FILES + FRONT.ZX0 x3 + `g_file_front`/`CRC_FRONT`.
- Entrebanc: FRONT.BIN 15883 B (gap _CODE 0x4000 -> _DATA 0x7E00 ple de zeros). FIX: FRONT_DATA 0x4200 (codi real 254 B) -> 523 B.
- VERD en emu (un sol boot, sense tecles): splash (cara+titol) -> SELECT (escenari CHOOSE YOUR PLAYER) -> MAP (fabrica CHEMICALS) -> nivell 1 JUGABLE (PC 03b4). FSELECT.ZX0 verificat byte-identic a SELECT.BIN (el "select==map" era artefacte de timing del harness, no contingut). Marges: _CODE ..0x3706 (122 B), GAME 15064 B, STARTER 1810 B. PENDENT: musica AKY, commit.

## Sessio 2026-10-12 (3): Fix meitat-esquerra FRONT (pack 320->160 real)
- Bug real (l'usuari el veu a l'emu): el pack feia `qi[y*320+xb*2]` amb xb 0..79 = pixels 0..159 (meitat ESQUERRA 1:1); el preview feia `x*2` amb x 0..159 (fila sencera). El `rows=[row[0::2]]` correcte era codi mort. Per aixo nomes sortia la meitat horitzontal (cara sola, THE BLUES tallat). El "quantize no-determinista" de la sessio 1 era un misdiagnostic: _m0 vs _hw diferien pel contingut, no per l'atzar.
- FIX: `sub=[qi[y*320+x*2]...x 0..159]` + pack des de `sub` + PORTA WYSIWYG (assert _hw==_m0 pixel a pixel; mateix qi/mateix run = identics obligats). Previews: SPLASH 2 cares + titol sencer, SELECT 2 focus + PRESS FIRE TO START, MAP fabrica sencera.
- Entrebanc: vermell a l'emu despres del rebuild (PC=C434 starter, A=4C). Arrel: els ZX0 mes grans + FSELECT/FMAP mouen el GAME 2 cops seguits i el loop de 4 iteracions s'exhaureix amb l'starter ranci (CRC vell) al DSK. FIX: range(4)->range(8) + FATAL si no convergeix (mai un DSK incoherent).
- VERD en emu: splash/map/select SENCERS + nivell 1 jugable (PC 0475). Marges: _CODE ..0x3718 (104 B). PENDENT: musica AKY, commit.

## Sessio 2026-10-12 (4): MAP retocat per l'usuari (via directa)
- `assets/bbdata/MAP_mode0.png` (160x200 P, usuari): 20 RGB unics (tots HW exactes) en 21 indexs (negre duplicat + 5 residuals d'antialiasing). `convert_direct()` nou a gen_screens.py: empaqueta SENSE tocar resolucio/colors (top-16 per pixels; 31 px residuals al proper amb informe) + .PALHW per match EXACTE (assert, res de nearest) + porta WYSIWYG. MAP via directa (SPLASH/SELECT segueixen VGA+quantize).
- VERD en emu: el mapa de l'usuari pixel-clavat (CHEMICALS, edificis, STORE) + boot al joc. FMAP 8572 B, convergencia en 3 iters (sense FATAL). PENDENT: musica AKY, commit.

## Sessio 2026-10-12/13 (5): Musica AKG (intro FRONT + tema nivell 1) + REGLA C1 + assert anti-ranci
- Player AT3 MIT a tools/akg/PlayerAkg.asm (+LICENSE) + conversor propi tools/akg_rasm2sdas.py (RASM/Disark->sdas: macros reals expandides, REPEAT desenrotllat, IF/ELSE/ELSEIF avaluats aqui (sdas .if nomes ==/!=), .if amb valors sempre-cert, FAIL->.fail, #-immediats, %bin->dec, (ix+d)->d(ix), meitats IX/IY->opcode cru, db/dw multi, label: db, {expr}, dknr3-prefix fora). Player 3073 B (init 0x4009/play 0x40CE, C1:0x4000) + intro 3091 B (Peter Gunn) + main 1619 B (Main Theme 50 Hz loop) a MUSBANK (7187 B, C1:0x4000, song slot 0x5000) + MUSMAIN (C1:0x5000). Stubs engine/mus.s (DI, salva tot, bank_set(C1), crida, restore, EI) + hooks: FRONT mus_play cada 6 ticks (300 Hz) + game loop 2x/frame + mus_init#2 post-MUSMAIN.
- ARREL reboot-fase-2 (determinista 6+ runs: groc->blau+ROM0+BASIC): C1 MAI des de slot 3 ni slot 1. Config C1 del 6128 mapeja slot3->banc7: l'starter (0xC000) i el FRONT (0x4000) DESAPAREIXEN en paginar = reboot (no hang). Nomes slot 0 (GAME, banc 0 en totes les configs) pot paginar C1; els banked hi accedeixen via trampoli central (stub/mus.s sobreviuen + restauren abans del RET). FIX: MUSBANK el carrega el FRONT (splash, load_mus=1, FrontArgs += musbank/load_mus) via stub central home=C4 + mus_init EQU (cap bank_set banked); el GAME nomes inicia MUSMAIN. MUSBANK al DSK pero mai tocat per l'starter. C4-C7 segurs des de tot arreu (slot3->banc3 en configs 0/4-7); C1/C2/C3 prohibits fora de slot 0/trampoli (CP-2.2 addendum).
- Incident starter-ranci (concurrent): CALL a GAME era 0x1F6D vs header/mapa 0x1F6B (2 B = salta LD SP). FIX: verify_starter_jump() al build (escaneja CALL xxxx;JR $ al BIN vs GAME_START, FATAL si difereix).
- Bloc 0 al limit: carrega MUSBANK al GAME (+165 B = overflow 158 B FATAL) revertida; disseny final +~10 B GAME (marge 9 B!), FRONT 523 B (pad fins _DATA 0x420B; codi 469 B « 4 KB). MUSBANK FRONT sense CRC (sector-CRC FDC + 3 intents; imatge build-verificada).
- VERIFICAT en emu (build final): splash->select->map->nivell 1 jugable (c1_0/c1_10) + 8 min estable (~25k ticks, cap crash) + PC enxampat a 0x40CE (Play executant) + AUDIO REAL (--aofile raw): silenci fins mostra 447486, despres ona PSG continua i variant (intro FRONT -> tema nivell). Breakpoints ZRCP no disparen mai (inutils); read-memory escombraria fixa (inutil); get-memory-pages + PC + vora + screenshots = instrumentacio que funciona.
- PENDENT: Theme1/Theme2 (mapping nivells 2-6), marge Bloc 0 critic (9 B), commit.

## Sessio 2026-10-13 (6): Musica ISR 50 Hz + mutes anti-drone + dieta P0 (marge 20->350 B)
- Queixes usuari (3): (1) a cada transicio FRONT la musica es para i queda nota penjada; (2) carregant el nivell la nota no para; (3) al joc el tempo va lligat al frame rate (meitat de tempo movent en Jake). Arrel comuna: ticks des del game-loop (2x/frame 25 Hz nominal, ritme real variable) + zero ticks durant lectures FDC (AY congelat = drone).
- FIX tempo: musica propietat de la ISR (300 Hz / 6 = 50 Hz exactes, independent del frame). isr.s: comptador _mus_div + `call _mus_play` cada 6; mus_play ISR-ONLY (sense DI/EI: la ISR ja es DI; re-activar = ISR niuada + player reentrant = crash). Main loop i FRONT ja no criden mus_play (trets). Segur vs bank_set/game per l'invariant _g_bank-abans-de-l'OUT (llegit abans de cada OUT: qualsevol intercalat es resol be).
- FIX drones: HOLD 0xBA10 (absolut, compartit 3 links): el motor l'activa en entrar i el neteja en sortir (exit+fail); la ISR salta el tick si HOLD (bancs a mitges / slot C1 sobreescrint-se). + mus_stop() (Stop: vols 0 + mixer 0x3F, posicio intacta; segur en player no-iniciat) cridat pre-lectura al FRONT (3 pantalles) i a l'asset-loop (8 fitxers); la ISR repren sola (posicio congelada: pausa, no restart). Play reescriu TOTS els regs per tick (SendPSG incondicional): resume/init sempre nets.
- FIX cursa pre-init (reboot!): el 6e tick (~20 ms) podia caure dins la copia+verify de l'stub o abans del mus_init (C1 buit) = Play sobre zeros. `g_mus_ready` (main.c, =0): mus_init el posa a 1; la ISR exigeix ready && !HOLD. Starter neteja HOLD a s_start (reboot calent).
- ARREL reboot-serie (troballa): CRC-helper al slot 2 del banc 5 cridat per TILES (index 0) quan BANK5 (index 6) encara no era resident = salt a brossa/zeros = reboot (o hang gris si RET ranci). Llico: verificadors han de ser residents abans del primer us (CRC inline al GAME, com abans). Cost de trobar-ho: bisseccio A-E + traca xlog + step-mode + marcadors de vora (verd/groc/blanc/vermell/negre).
- DIETA P0 (20->350 B _CODE!): TITLE mort fora del DSK (g_title 107 B, 34 sectors; res el carregava) + CHS 3B->2B (head sempre 0: build.py x2 linies + motor -1 inc; ~160 B) + s_fdc_crc16 compartit (static->global fdc_crc16, main.c l'usa; ~45 B). _DATA ..0x3BD6, pila 1064 B, BANK5 marge 80 B, FRONT 523 B, STARTER 1810 B.
- VERIFICAT en emu: boot sencer fins nivell 1 (v3_end) + AUDIO REAL: musica des de ~66 s (FRONT), 0 drones >0.5 s en tot el fitxer (mutes+HOLD), tempo quiet vs JoyRight IDENTIC (mediana IOI 0.095 s als dos; 160/159 onsets) = tempo independent del frame rate. Eines: set-ui-io-ports pel joystick (hold Right), --aofile raw (amb --ao null escriu DC quan calla).
- PENDENT: Theme1/Theme2 (nivells 2-6), neteja DIAGs (cap resta al codi: tots revertits/marcats?), commit.

## Sessio 2026-10-13 (7): Queixes musica (drone + talls + auto-pass) + ARREL HOLD a VRAM
- Queixes usuari (4): (1) splash/select/map passen sols (timeout 8000); (2) la musica es para amb la disquetera i repren; (3) SELECT sense ballarins per triar; (4) al joc no hi ha musica, nota drone persistent.
- ARREL del drone (troballa): HOLD era un absolut 0xBA10 = dins la VRAM (pagina 2, 0x8000-0xBFFF). El memset(0x8000) post-carregues el posava a 0xFF i el render el trepitjava cada frame: la ISR el llegia !=0 per sempre = ni un tick mes + AY congelat = drone. Ho explicava tot (FRONT sonava, loads muts, joc drone). FIX: HOLD reubicat a _DATA (`_g_mus_hold`, isr.s) amb EQU generat (obj/fdc_hold.s, patro front_ext: MUS_HOLD=_g_mus_hold del mapa) linkat al FDC bank + starter; la ISR el llegeix com a simbol; starter el neteja via MUS_HOLD_ADDR (starter_tables.h); crt_addrs.h tambe el publica. + blindatge `g_mus_hold=0` post-memset a main.c (mus.h: extern).
- FIX (1) espera infinita: `while(pressed){} while(!pressed){}` (guarda release anti-salt-encadenat; f_fkey cobreix teclat + joystick fila 9). Sense timeouts. NOTA EMU: ZEsarUX no injecta tecles a l'scan directe (nomes nivell firmware: el boot escriu pero l'splash no avanca mai en emu); en HW real l'scan es verbatim cpct (provat via game input) = OK. Verificat en emu per timeout-temporal (build amb 8000) i final amb espera (splash quiet 20 s+).
- FIX (2) musica continua al FRONT: el motor nomes posa HOLD si dest!=C0 (branch a _assets_fdc_load_generic): les pantalles (scratch 0x8400, RAM no bancable) sonen pel mig sense risc (fora de 0x4000-0x7FFF + re-assert de bancs + DI en transfer). Treu mus_stop() del loop FRONT (era el silenci). Verificat en audio: 0 talls en 16 min de FRONT. En loads de nivell (bancades) HOLD+mus_stop d'un sol cop pre-loop (l'usuari prefereix un silenci continu a stop-start).
- FIX (4) verificat: 0 drones en tot el fitxer; musica al joc; tempo quiet==run (IOI 0.093 s).
- (3) SELECT: continua static (qualsevol tecla/boto continua, Jake per defecte). La tria amb ballarins (sprites + cursor + plumbing) queda pendent (Bloc 0 te 257 B ara).
- PENDENT: mid-game loads: l'scratch 0x8000 mor al memset (s_fdc_ready=1 ranci = cridaria brossa; cal resetejar-lo quan hi hagi loads a mig joc) + C6 persisteix (be). Theme1/2. Marge Bloc 0: 257 B. Commit.

## Sessio 2026-10-13 (8): Pantalla blava amb brossa post-RUN (tintes a negre)
- Sintoma usuari (historic, mai regressio): just despres de RUN, pantalla blava amb brossa que no afecta res. Arrel estructural: s_start posa Mode 0 + ROMs OFF i copia l'starter (2 KB) a 0xC000 (dalt de VRAM); s_main carrega segons amb vora blava/groga. La pantalla mostra restes BASIC (paper blau) + la copia starter com a pixels.
- FIX (idea usuari): loop a s_start (post-RMR, pre-LDIR) que posa les 16 tintes a negre HW 0x54 (~18 B, PIC-safe: nomes LD/OUT). Pantalla negra neta en carregues; FRONT (f_fpal) i video_init posen la seva paleta despres. Vores diagnostics intactes (decisio usuari).
- Detall cacat en verificar: quedaven punts grocs de text (captura ib_10). Arrel: el parpelleig LED del motor commuta la ink 2 (groc 0x4A/negre) per sector i la brossa Mode-0 te pixels en tinta 2. FIX: NAU_FDC_BLINK=0x80 (bit 7 = silenci, que el motor ja respecta) a s_start (+5 B). El LED fisic no en depen; el blink-ink2 desapareix del tot (el stub del GAME ja operava en silenci).
- Nota build: STARTER.BIN fa 1810 B constants (la mida la fixa la _DATA 0xC700.., no el CODE); verificat al byte (loop inks + BLINK=0x80 + RMR en ordre). Marge starter ~224 B.
- VERIFICAT en emu: fase groga = negre total + vora groga; splash igual. Commit.

## Sessio 2026-10-13 (9): FRONT no detectava tecla/boto en HW real (scan via cpct)
- Sintoma usuari (HW real): splash no respon ni a teclat ni a joystick; impossible avancar al select. Arrel: l'scan ASM duplicat de front.c (`f_fkey_pressed`: seq PPI + `ini` + OR) no detectava mai (sempre 0) en HW real; el timeout 8000 ho emmascarava (auto-pass) i en emu ni tan sols la injeccio hi arribava.
- FIX (lliço fdc_crc16: no duplicar): el FRONT crida EXACTAMENT el codi provat del joc (`_cpct_scanKeyboard_f` + buffer `_cpct_keyboardStatusBuffer`, el que mou en Jake) via EQU central a front_ext.s (patro mus.s) + deteccio en C (`OR 10 files != 0xFF`). 0 bytes al Bloc 0 (funcions ja linkades); FRONT 523->512 B (fora statics f_fkb/f_fkres); espera infinita + guarda release intactes.
- VERIFICAT: build verd (CALL 0177 al FRONT.BIN, zero seq PPI propies F782/F40E); emu: splash espera amb PC=0198 (dins l'scan central = el FRONT executa el cami nou). La premuda real la ha de confirmar l'usuari en HW (l'emu no injecta a l'scan directe). Si encara avanca sol = fila sorollosa (pas seguent: check per tecla concreta); si no avanca prement = revisar altre cop.
- PENDENT: confirmacio HW usuari; despres SELECT amb tria (P0 del pla) i enemics (P1-P3).

## Sessio 2026-10-13 (10): DIAG-REALHW vora viu (l'scan tampoc via cpct)
- Sintoma usuari (HW real, build b6696a2): ni foc ni tecla avancen l'splash. Ni tan sols el cami cpct provat detecta. Hipotesis esgotades en teoria (buffer central, EQU verificat, CALL 0177 al BIN, PC=0198 en emu).
- DIAG temporal (a revertir): l'espera del FRONT mostra l'estat VIU de f_fkey_pressed() a la vora (NEGRE=idle / VERMELL=premut) i avanca en detectar; sense guarda release (diagnostic pur). Mateix patro OUT provat. FRONT 512 B, Bloc 0 intacte (257 B).
- Verificat en emu: splash + vora NEGRA + PC=01a3 (cami nou executantse; injeccio cega = idle per sempre, esperat).
- PENDENT: test HW usuari amb 3 resultats possibles: (a) negre->vermell + avanca = FUNCIONA (restauro guarda + commit final); (b) vermell sempre des de l'inici = fila sorollosa (pas a check per tecla concreta); (c) negre sempre prement = scan cec de deb (replantejar: PPI/PSG, ISR, context banked).

## Sessio 2026-10-13 (11): Fix espera FRONT amb el Loader de nau_dx (usuari)
- L'usuari aporta el seu repo anterior (local a C:\Projects\nau_dx-release_candidate, el git donava 404): el seu Loader va tenir EL MATEIX problema (splash encallat) i ho va resoldre amb `read_keyline_e` + `check_any_input` (loader/loader.s:170-208). Diferencies clau vs el nostre scan (i vs cpct): NO fa `F782<-0x82` inicial, NO usa `INI`, selecciona fila per `F64x` (valor = 0x40+linia), llegeix per `F44x` amb `IN A`, cua `F600<-0`, i nomes mira DUES linies (SPACE = linia 5 bit 7, Joy0_Fire1 = linia 9 bit 4) en comptes d'OR de 10.
- FIX: port VERBATIM a `f_fkey_pressed()` (front.c): `E=5 -> AND 0x80 / E=9 -> AND 0x10`, 1 si actiu-baix. Fora DIAG vora (revertit a espera neta + guarda release), fora EQU cpct de build.py/front.c (no calien; el cami cpct tampoc detectava). FRONT 512->513 B, Bloc 0 intacte (257 B).
- VERIFICAT: build verd; BIN amb `call 401F` + `and 80/10` ben resolts, zero `CALL 0177`; en emu AVANCA SOL fins al nivell 1 (pantalla de joc perfecta): el bus flotant llegeix 0 -> "sempre premut". En HW real hi ha pull-ups (0xFF idle, com al Loader) -> espera. Efecte colateral bo: pipeline sencer (select/map/loads/joc) verificat en emu de retruc.
- PENDENT: test HW usuari (SPACE o foc = avanca). Si funciona: SELECT amb tria (P0) + enemics (P1-P3).

## Sessio 2026-10-13 (12): DIAG2 barres VRAM (l'usuari no avanca ni amb nau_dx)
- Sintoma usuari (HW real, build 4c228fe): ni SPACE ni foc fan avancar; "com si arrenquessis amb tecla premuda" (salta sol) + musica que para a les transicions. Nota: el salt rapid agrupat explica la musica (loads junts = ratxes DI sense ticks), no es un segon bug (una variable!).
- DIAG2 temporal (a revertir): `f_raw5/f_raw9` (valors crus) + `f_bars()` que pinta 2 barres a files VRAM 0-1 (0xC000/0xC800, long=valor>>1): barra0=linia5, barra1=linia9. Cridada als dos loops d'espera. Nomes VRAM (segur banked). FRONT 513->515 B.
- VERIFICAT: build verd; BIN amb calls+barres; emu: MAP amb franja a dalt + pipeline fins al joc (bus flotant=0 = "sempre premut", esperat).
- PROTOCOL TEST HW (dir a l'usuari): foto de l'splash quiet (longituds barres?) + mantenint SPACE (barra0 ha d'ENCONGIR 0x80) + mantenint FOC (barra1 -0x10) + diu si avanca + si sona la musica. Lectura: FF estable + caiguda en premer = OK; constant !=FF = bit encallat; ballant = flotant (caldra debounce).

## Sessio 2026-10-13 (13): Barres llargues+tremolant -> DI al check (cursa ISR-PSG)
- Report usuari (HW real, DIAG2): barres LLARGUES i TREMOLANT. Lectura: valors ~0xFF inestables (no cec, no encallat) = la ISR (300 Hz, player PSG cada 20 ms) trepitja la fila seleccionada entre l'OUT i l'IN del check (el port nau_dx no feia DI; el cami cpct si que en fa = per aixo al joc funciona).
- FIX (2 B): `di` a l'inici + `ei` a la convergencia 00012$ del check (seccio atomica ~100 cicles; retard ISR inaudible). Barres es mantenen per verificar estabilitat.
- VERIFICAT: build verd; BIN amb F3 ... FB + stores + read verbatim; emu: MAP amb franja + pipeline (bus flotant = auto-avanca, esperat).
- PROTOCOL RETEST HW: splash quiet (barres ESTABLES ara?) + SPACE (barra0 cau + avanca?) + FOC (barra1 cau + avanca?) + musica en espera. Si estable + avanca = TREURE BARRES + SHIP. Si encara tremola = seguent teoria (config PPI pre-video_init? llegir video.s).

## Sessio 2026-10-15 (14): Enemics L1 1:1 (bfbf882, 611d229, 9697ce1, e429654, c6ff1a9)

- **10 walkers** (slots DOS 1,2,5,11,12,24,25,26,27,28; kinds 8/15/19) al **banc C6**: frames ENEMI1.BIN 9x512 a 0x4000, taula de salts fixa 0x5200+3k (update/restore/draw/init), codi+dades (ENEMY_DATA 0x6590). `ENEMI.BIN 13024` (limit scratch 13536, marge ~512!), `GAME.BIN 15078`. Fitxers: `src/enemy.c`, `src/enemy.h`, `engine/enemy_table.s`, `tools/gen_enemy_frames.py`, `tools/build.py` (build_enemybank + asserts de slots).
- **Spawn** (`s_spawn` a CODE): `left=dos_x/2, top=dos_y-32`. EVIDENCIA: amb centre (dos_x/2-8) s27 queia de la 2a planta a terra; amb left aterra top 528 tocant la plataforma col66.
- **Flips**: pre-flip una vez a `en2_init` (`s_flip_frames[6][512]` a _DATA; F0..F5 = celes walk 0,1,2,3,7,8). El flip per LUT a cada frame era massa car i feia flamarades blanques en dir=-1 (eliminat `moving_blit_span_hflip` + `g_flip_lut_hi` + `enemy_flip_lut.s` del link). ATENCIO: la cela flipejada JA es la imatge final, s'indexa amb el mateix offset (intent de "fix" revertit, veure e429654).
- **Pool de fons**: 6x512 a scratch central **0x8320** (lliure post-carrega: motor a 0x8000-0x8311, buffers a 0xB800+). _DATA no el paga al fitxer (la imatge ENEMI va padded: _DATA zeros SI ocupen fitxer!).
- **Restore LIFO** (invers al draw): dins d'enemics slots al reves (`en2_restore`), ascensors al reves (`moving_restore`), i a `main.c` enemic abans que ascensors (l.744-747). Solapats nets, sense fantasmes. El jugador ja era LIFO (restaura primer, dibuixa ultim).
- **Sonda X DOS 1:1** (`level.c:fixup_xpos16` + `object_func_op0`): penya-segat = `tile_type==1` (aire, byte 0 TRIG) a `(x>>3)+-2`, fila de peus -> mitja volta i avanca; paret = `tile_flags` bit (1 dreta / 2 esquerra) a `(nx+-4)>>3`, files peus i peus-1 (camp `unk2E`, 1 si aire a sobre) -> mitja volta sense avancar. Velocitat 3 CPC px/f (ENEMY_VX 24 = 150 px/s DOS). Abans la sonda mirava files del cos: queien al buit (faltava la 1a iaia) i s'amuntegaven fent esteles. Bbox activacio DOS/2: x [view-70,view+230], y [view-100,view+350] (fora = congelat).
- **`tile_type()`** nou a `main.c` (byte 0 TRIG via C5; fora de mapa retorna 1=aire) + declarat a `moving.h`.
- **Forats coneguts (no 1:1 encara)**: Y walkers nomes pla (sense pendents DOS 2/3/14/15 ni yoffset); sense comportament d'atac proxim (op1: `special_anim=2` quan el jugador es a prop); `engine/enemy_flip_lut.s` orfe (15 linies, es pot esborrar); ENEMY_DATA molt just (qualsevol creixement de codi C6 demana pujar-lo; el build ho detecta amb FATAL).
- **VERIFICAT emu** (ZEsarUX ZRCP `--vo null`, `save-screen` BMP + PIL, diffs llindar 90): boot 60s + 3x SPACE + 45s carrega. s26 viva al terrat (279,144, patrulla); cotxes s1/s2/s5 patrullant a terra (s1 fins al limit 0); iaia+Jake solapats nets (HI-FI/STORE, sense esteles); s27 2a planta; sim host-side amb MAP0/TRIG0 reals: cap walker al buit. En Jake mor atropellat pels cotxes (col-lisio letal OK) i el border es torna vermell en morir (sembla flaix DOS, no bug).
- **Protocol rapid per continuar**: `snapshot-save/load scratch/snap_*.zsf` = estat instantani (OJO: el snapshot guarda el BINARI vell; despres de rebuild cal boot fresc!). Mirall d'estat (revertit; re-afegir a `en2_update`): 6B/walker a 0x3BC0 (x_lo,hi,y_lo,hi,dir,ground) + `read_mem`. Walkers congelats (bbox) no escriuen el mirall (surten zeros/brossa vella).
- **Comandos**: `py -3 -u tools/build.py` (~12min, FATAL si Bloc 0/C6 envaeixen); emu: `zesarux --noconfigfile --machine CPC6128 --vo null --ao null --aofile NUL --enable-remoteprotocol bluesb.dsk`; tecles ZRCP: 128 espai, 142 esq, 143 dreta, 145 amunt; `read_mem 0x378C 2` = ticks (Compte: COMPTA ENRERE!), `0x3B19` = cam_x4 (u16le), view_x = cam_x4*4, view_y = cam_row*8.
- **PENDENT usuari**: validar posicions DOS reals (s26@top144? s27@112 o @528?).

## Sessio 2026-10-18 (23): Spawns d'enemics a la formula oficial + sondes a la columna del centre

- **Arrel trobada (regla 1, lectura del codi DOS)**: la taula `s_spawn[20]` de `src/enemy.c` estava desfasada **+8 en x i +16 en y** de la formula oficial (`dos_x/2-8`, `dos_y-32`) a 13 de 20 entrades. La hipotesi inicial (que el +16 compensava una mecanica de terra absent) **era FALSA**: al L1 tots els tiles tenen `unk16` (TRIG byte 7) = 0, aixi que `level_call_trigger_func` (`tiles.c:607`) sempre resol `case 25: break` (no-op); el terra del carrer es el **clamp del mapa** de `do_level_fixup_object_ypos16` (`ypos > tilemap_h -> tilemap_h-16` = 1136 = top 1104), que el motor ja reprodueix via `is_floor_solid` (`row >= MAP_H-1`). L'unica excepcio real son els esglaons `op=14` (files 70, cols 77-81).
- **Canvis a `src/enemy.c`**:
  - `s_spawn[20]` regenerada amb `py -3 tools/dos_coord_converter.py --level 0`: `cpc_x = dos_x/2-8`, `cpc_y = dos_y-32`. 19/20 coincideixen exact amb el slot DOS (comentari `[slot N]` a cada fila); l'unic sense parell es la fila 4 (policia "repla raco", posicio no trobada a `staticres.c` — pendent de contrastar amb captura DOS).
  - Sondes de tile a la **columna del centre** (`(x+8)>>3` = `xpos16` a DOS), mai les del cos: penya-segat `tile_type==1` a centre±2 (fila peus), paret `tile_flags` bit 1/2 a `(nx±)>>3` a files peus/peus-1/peus-2 (`fixup_xpos16` + `unk2E`).
  - Sonde de terra (`is_floor_solid`) a la columna del centre (abans dues columnes del cos `x+3`/`x+12`).
  - Bbox d'activacio derivat de DOS: `x ∈ [view-78, view+222]` (abans ±70/230, valid per a `x`=centre) i `y ∈ [view_y-132, view_y+318]` (ja correcte: `[yo-100, yo+350]` passat a coordenada *top* amb `-32`).
- **Eina nova `tools/sim_enemies.py`**: simulador host-side fidel a `src/enemy.c` (gravetat + snap + sondes + re-chequeo de terra cada 4 ticks) amb `MAP0.BIN`/`TRIG0.BIN` reals. Compara la taula contra la formula oficial slot a slot i detecta enemics que cauen al buit oDerived de la partida. `py -3 tools/sim_enemies.py [--slot N --verbose]`.
- **VERIFICAT**: sim → tots 20 aterren (`terra`), cap al buit; emu → iaia 3walking al 1r pis (x 592-618, y 976), policia 1 al carrer (744, 1104), iaia 2 fent exactament el que prediu el sim (puja l'esglaon a y 1088 en x 632-656 i **baixa al carrer a y 1104 en x≈660**, cam x 664→624). sense artefactes visuals.
- **Forats encara oberts (evidencia, no implementats)**:
  - **Velocitats per op DOS** (`objects.c`, `xmaxvelocity`, pas `>>3`): op0 (iaia/peix) 40 = 2,5 px/f CPC, op1 (granger/rocker) 40, op2 (policia) 24 = 1,5 px/f, op8 (ocell) 48 = 3 px/f, op10 (cambrera) 32 = 2 px/f. Ara hi ha `vx` per tipus (iaia 36, policia 24, ocell 32, cambrera 20, peix 16) → la iaia va un 60% rera i la policia al doble. Cal pas fraccionari (acumulador 1/8 px) per a 2,5 i 1,5.
  - **Ocell**: DOS `object_func_op8` té pics (`player_ydist<=100 && |player_xdist|<90` -> `unk42=1`,anada enpic) i NO te caixa de patrulla; el codi fa +-96 inventat.
  - **Peixos**: DOS fa servir `object_func_op0` (caminar amb gir a penya-segat), no una caixa de nedar.
  - **Rang de tir de la policia**: DOS `|player_xdist| < 80` i `player_ydist <= 20`; el codi fa 75/85 i -16..24.
  - `op14` (esglaons) es tracta com a terra solida (la referencia DOS deixa `trigger_func_op14` sense implementar).
  - Els 2 rockers de slots 4 i 8 de `staticres.c` son dins d'habitacions (fila 80) i no s'han afegit.

- **REGRESSIO detectada per l'usuari i corregida (pivot en punt fixe)**: en afegir la **fila de peus** a la sonda de paret (`tile_flags(acol, frow)`), tots els walkers del carrer giraven sense moure's. Causa: al L1 les rajoles del terra (op20, fila 71) tenen `flags = 3` a TOT arreu del mapa, aixi que la sonda donava "paret" sempre. La sonda de paret només ha de mirar les files **peus-1 i peus-2** (`unk2E` 1/2 de `fixup_xpos16`); la de penya-segat mira `tile_type` a files peus i peus-1. Sim: abans 0 px recorreguts, ara 48-192 px per enemic. Emu: iaia 2 patrolling x 624-706 i iaia 3 al 1r pis x 624-672.
- **Truc de verificacio**: `write-memory` a `s_px8` (`0x3C1C`) teleporta en Jake per arribar a una zona sense que el matin ningun cotxe (a peu de mort constant en recar); la camera el segueix i els enemics del bbox desperten.

## Sessio 2026-10-18 (24): Policia del repla i paraigues (revert d'un canvi estructural)

- **Policia "flotant" del replà d'ascensors (report usuari)**: era la fila 4 de `s_spawn`, sense parell a `staticres.c`, posada a (816,784) amb `vx=0` (estatica, `on_ground=1` -> no queia mai i pivotava). **Corregit amb el slot DOS 0 oficial** `(280, 1088)` (policia de carrer al PB Store), `vx=24`. Les 5 policies del L1 son els slots 0/3/7/18/29 i ara hi son tots.
- **Paraigues que no desapareixia (report usuari)**: `sprite_abort_balloon()` (ASM) nomes posa a zero els flags `_s_bloon_drawn_c0/80` **sense restaurar el fons**, aixi que el sprite quedava congelat a pantalla. Fix: en deixar anar el paraigues (`moving_bank.c`) i en `carry_abort()` **ja no s'aborta**: deixa que el restore normal del frame seguent torni el fons. **VERIFICAT emu**: `write-memory` a `s_carry_kind=8`, SPACE -> el sprite i el seu fons desapareixen nets.
- **REVERT: canvi estructural del mirror d'enemics (error meu, no demanat)**. Havia substituït el flip ASM (`en2_flip_cell` + LUT, cel·la sencera de 512 B, **1 blit per enemic i frame**) per un mirror en C **fila a fila** (buffer de 16 B, **32 blits per enemic i frame**), per poder encabir una 15a cel·la (pose de tirc de la policia) al banc C6. **S'ha revertit sencer** (`src/enemy.c`, `engine/enemy_table.s`, `tools/gen_enemy_frames.py`, `tools/build.py`, `assets/bbdata/ENEMI1.BIN` tornats a l'estat verificat de `e7de571`).
  - **Errors que va causes**:
    1. El mirror per files no respectava la matematica de clipping horitzontal (`start_byte`/`byte_count`): un enemic **tallat pel costat** de la pantalla sortia **escombrat** (fals) — error reportat per l'usuari en captura als primers segons de partida, amb un enemic a la vora dreta.
    2. 32 crides de blit per enemic i frame en comptes d'1: mes lent, i trencava la llogica de fons/owner per fila del pool.
    3. Es va fer **sense consultar** i amb uns tests invalids (només crops d'un policia en punt fix; mai pantalla sencera ni els primers segons ni les vores).
  - **Regla que hi afegeixo**: **cap canvi estructural** (pipeline de render/blit, mirror, layout de bancs o de RAM) sense proposta explicita i **aprovacio**; i validacio obligatoria amb (a) pantalles senceres 1:1 dels **primers segons** de partida, (b) enemics a les **vores de pantalla** amb clipping en les dues direccions, (c) diff objectiu entre frames consecutius.
  - **Consequencia**: la **pose de tirc de la policia NO s'implementa** (necessita 512 B mes al banc C6). Abans de tocar el layout del banc cal proposar opcions (reducir el pool de 6 a 4 slots, o un altre banc), no un canvi unilateral.
- **Mides (estat revertit, = estat verificat)**: `ENEMYCODE.BIN 6342 B` (base `0x5C00`..`0x74C6`), `ENEMI.BIN 13510 B` (frames 7168 + codi 6342), Bloc 0 `_CODE 0x0100..0x37F3` (141 B de marge), Banc 5 amb 371 B de marge.
- **Nota de RAM (de l'error anterior, es manten)**: no hi ha RAM central lliure per a buffers de sprite: `FDC_BANK_DATA = 0x8300`, finestra FDC `0x8000..0x8FFF`, `0x9000+` es la pagina VRAM B.
- **VERIFICAT emu després del revert**: 20 s de partida real (nivell 1, botiga PB + cinema) amb captura **pantalla sencera 1:1 cada 0,5 s**; enemics a les dues vores amb clipping; policia en les dues orientacions i iaia caminant a l'esquerra (runt invertit). **Cap escombraria.** Escena de referència utilitzada: `scratch/start_p13.png` (policia neta dins la botiga) i `scratch/start_p09.png` (iaia invertida neta). Scripts: `scratch/verify_start_seconds.py`, `scratch/verify_flip_only.py`.
- **PENDENT (gran)**: al morir i tornar al checkpoint, el **comptador de discos torna a 0 i el mapa (MAP_MUT al Banc 5, modificat in-place) i els enemics (`enemy_room_exit`) es reinicien** -> cal repetir la zona. Cal un estat de checkpoint: (a) log de tiles modificats des del checkpoint (col,row,valor antic) per reproducir-los enrere, (b) copia de `s_enemies[20]`, (c) comptadors (discos/cors). Avui no hi ha lloc per a una copia de 9216 B del mapa.
- **Adreces globals no estatics** (compovar `obj/bluesb.map`): `g_ticks` = `0x388C`, `g_cam_x4` = `0x3C18`, `s_px8` = `0x3C1C`, `s_carry_kind` = `0x3C27`, `g_hearts_count` = `0x3C12`.

## Sessio 2026-10-18 (25): Ascensor = 1 sol frame (criteri Amiga) + fix de transparencia

- **Que es realment l'ascensor**: es un **SPRITE** de 2 frames (`ENEMI1.SQV` locals 0 i 1, 32x14), no cap tile animat. Son la mateixa peca amb la banda del motor en fase oposada (pens 11/4). El nostre codi ja els alternava (`moving_bank.c: e->frame = (anim_tick>>2)&1`).
- **CANVI (criteri Amiga, desviacio deliberada del DOS)**: s'exporta **NOMES el frame 0**, sense l'animacio del motor. A la versio Amiga el grafic es identic pero estatic; es una animacio molt subtil que costava un swap per frame i 224 B al banc C0.
  - `tools/gen_elevator_frames.py`: `converted = [convert_frame(frames[0])]`, `assert len == 224`.
  - `src/moving.c`: `frame = ELEVATOR_FRAMES_BASE;` (sense ternari). `src/moving_bank.c`: fora el swap de `e->frame`.
  - `assets/bbdata/ELEV.BIN`: **448 -> 224 B**. `elev=664` al PAK. Marges: Banc 5 code 4.080 B (marge 400 B) i Bloc 0 `_CODE` amb 342 B de marge (abans 141).
- **BUG de transparencia corregit (era imprescindible perque el frame unic sigui complet)**: `gen_elevator_frames.py` feia `None if pen in (0, 11)`, es a dir marcava el **pen 11 com a transparent**; pero en aquest sprite el pen 11 es un **color visible** (ho demostra que tots els 47 frames d'ENEMI1.SQV usen el pen 11, i l'exportador d'enemics nomes fa transparent el pen 0: `gen_enemy_frames.py`). Amb el bug, **desapareixia tota la meitat esquerra de la banda del motor** (verificat renderitzant l'ELEV.BIN vell contra el DOS).
- **PENDENT (colors)**: l'sprite surt sencer pero les tintes no son les del DOS. `dos_to_cpc_pen[11] = 11` -> ink `0x54` (negre) a la meitat esquerra. El projecte ja te la taula exacta DOS->CPC: **`MAP.PALHW`** (16/16 coincideix element a element amb els RGB de `MAP.PAL`): aplicant-la el resultat s'apropa molt al DOS. *(Nota: no s'ha aplicat perque l'usuari nomes va aprovar la simplificacio.)*
- **VERIFICAT emu**: Jake teleportat sobre la plataforma (304,784) la munta i puja amb ella; l'ascensor es dibuixa **sencer** (banda blanca + escacat salmon + banda vermella). Captures: `scratch/lv_last.png`, `scratch/lv_zoom.png`, comparativa DOS vs vell vs nou: `scratch/cx_final.png`.
- **Truc de teleport (CORRECCIO IMPORTANT)**: el protocol remot de ZEsarUX vol les adreces de **`write-memory`/`read-memory` en DECIMAL**. Escriure-les en hex fa que la escriptura no s'apliqui (semblava que el joc "resetejava" en Jake). `zrcp.py` ja fa servir decimal a `read_mem`.
- **Altres pendents d'aquest fil (no tocats)**: (a) les 5 plataformes tenen les coordenades a ma a `tools/pack_level.py` (`y = dos_y`, sense el −32 oficial) -> surten 18 px baixes; (b) falta l'objecte DOS `op4` (tipus 16) a CPC (816,768), l'ascensor de debò; (c) el DOS anima tambe els tiles de les cintes (29-32) i les peixeres (76-78) — aixo SI que ho tenim — i n'hi ha d'altres (53/54/55/63) que no.

## Sessio 2026-10-16 (15): Taula d'Enemics L1 a 20 slots + 14 celes Mode 0 al Banc C6
- **Ampliació de la plantilla d'enemics a 20 slots**: 3 iaies (kind 15), 5 policies (kind 4), 2 peixos (kind 8), 3 ocells (kind 19), 2 grangers (kind 18), 1 cambrera (kind 17), 4 rockers (kind 20).
- **Extracció de celes `tools/gen_enemy_frames.py`**: 14 celes Mode 0 de 16 px × 32 línies (512 B cadascuna, total 7.168 B) generades des d'ENEMI1.SQV de DOS i col·locades al Banc C6 (`0x4000..0x5BFF`). Codi del motor C6 reubicat a `0x5C00..0x7486` (`ENEMYCODE.BIN`, 6.278 B).
- **Taula de salts fixa d'interfície resident C6**: `en2_init` (0x5C00), `en2_update` (0x5C03), `en2_draw` (0x5C06), `en2_restore` (0x5C09), `en2_check_player_hit` (0x5C0C), `en2_check_crate_hit` (0x5C0F).
- **Pool de fons reutilitzable**: 6 slots de 256 bytes a Banc C6 `0x7A00..0x7FFF` (`BG_SLOT`). L'enemic només desa fons quan és visible a pantalla, alliberant el slot quan surt de la vista.

## Sessio 2026-10-16 (16): Comportament de tret 1:1 (Policia, Cambrera i Ocell) + Projectils
- **S'aturen per disparar (1:1 DOS `level.c:op1`)**:
  - Els enemics armats (policia i cambrera) NO continuen caminant mentre disparen. Quan la distància amb en Jake és inferior al rang (`abs(x - px) < 120`), s'aturen (`vx = 0`), encaren en Jake (`dir = px > x ? 1 : -1`), inicien el temporitzador de tir i reprodueixen el frame d'apuntar.
- **Projectils (bala, plat, ou)**:
  - Gestionats a `Projectile s_proj` amb velocitat horitzontal 1:1 (`vx = 64` a DOS = 8 px/frame a CPC).
  - Alçada i offset per projectil: bala (6 línies), plat (11 línies), ou (13 línies).
  - Dibuix amb clipping de pantalla complet i buffer de fons dedicat `s_proj_bg[2][64]`.
  - Impacte letal sobre en Jake amb reducció de cors al HUD (`en2_check_player_hit`).

## Sessio 2026-10-16 (17): Correccions 1:1 mecàniques de salts, sostres i escales
- **Col·lisió de sostre 1:1 (`player_physics_step`)**:
  - Abans en Jake queia ajupit a qualsevol cop al sostre. Al DOS (`level.c`), Jake només queda estabornit (amb estrelles) si el sostre és un bloc dur infranquejable i la distància al sostre en saltar és molt curta (passadís estret).
  - Si l'alçada del sostre és alta, el salt simplement s'atura (`vy = 0`) i cau de peus sense quedar estabornit.
- **Escala peixera (tram blau vs tram negre)**:
  - Corregit el desfasament de velocitat a les peixeres: la pujada per escala té la mateixa velocitat constant a tot el tram independentment del color o patró del tile.

## Sessio 2026-10-17 (18): Globus i Paraigües 1:1
- **Globus (`s_carry_kind == 2`)**:
  - El globus puja a través de l'aire lliure; no explota amb ombres negres decoratives sinó únicament en col·lidir amb rajoles sòlides de sostre dur (`tp[2] == 20/21/27/28`).
  - Quan en Jake el deixa anar amb la tecla d'acció, el globus continua ascendint sol cap amunt fins a sortir de la pantalla o explotar contra un sostre.
- **Paraigües (`s_carry_kind == 8`)**:
  - Animació de planejar (frame 24) en comptes de caminar mentre es descendeix lentament.
  - Quan aterra sobre plataformes o núvols, posa immediatament els peus a terra i tanca l'estat de caiguda.

## Sessio 2026-10-17 (19): Portar i llançar caixes 1:1 (Cap, Mans, Trajectòria i Impacte)
- **Posició de portar caixa (`carry_draw`)**:
  - 1:1 DOS (`bb/level.c:907`): la caixa es recolza sobre el cap i les mans (`cx = px + 4`, `cy = py - 15`), tant mirant a la dreta com a l'esquerra.
  - Seqüència de passos de caminar portant caixa actualitzada als 6 frames de DOS `{15, 13, 14, 16, 13, 14}` (`animframe_00cd`).
  - Idle carry utilitza el frame 14 (`animframe_00c7 = 0x0E`) amb les mans alçades.
- **Dibuix de la caixa volant (`player_physics_step` i `carry_draw`)**:
  - Eliminada la comprovació errònia `is_floor_solid(ncol, nrow)` que la destruïa al primer frame sobre la cinta transportadora/sòl.
  - Al DOS (`level.c:1773, 1811`), la caixa llençada té `if (obj->type != 2)`, ignorant sòls i només xocant contra parets sòlides (`tile_type == 6`), enemics (`enemy_check_crate_hit`) o límits de pantalla.
  - Retallat dinàmic implementat a `carry_draw` amb càlcul precís de `g_moving_span` i `g_moving_rows`, registrant la mida real dibuixada a `s_carry_drawn_span[page]` per restaurar el fons sense taques.
  - Verificat amb ZEsarUX en vol complet a través de la pantalla i impacte contra enemics.

## Sessio 2026-10-17 (20): Fórmula Oficial de Conversió de Coordenades DOS <-> CPC
- **Arrel matemàtica de les discrepàncies trobada a `tools/blues_dos/bb/screen.c:40`**:
  - A DOS: `(dos_x, dos_y)` és el **centre horitzontal** i la **base dels peus** de l'sprite (`draw_x = dos_x - w/2`, `draw_y = dos_y - h`).
  - A CPC (Mode 0): `(cpc_x, cpc_y)` és la **vora esquerra** i la **vora superior** (top-left). Resolució horitzontal a la meitat (160 px vs 320 px de DOS).
  - Fórmula oficial:
    $$X_{\text{CPC}} = \frac{X_{\text{DOS}}}{2} - \frac{W_{\text{CPC}}}{2} = \frac{X_{\text{DOS}}}{2} - 8$$
    $$Y_{\text{CPC}} = Y_{\text{DOS}} - H_{\text{DOS}} = Y_{\text{DOS}} - 32$$
    $$\text{Línia de terra (Floor } Y) = Y_{\text{DOS}}$$
  - Rajoles: $\text{Col}_{\text{CPC}} = \text{Col}_{\text{DOS}} = X_{\text{DOS}} \gg 4$.
- **Eines i documentació creades**:
  - `tools/dos_coord_converter.py`: eina CLI que converteix coordenades interactives i permet bolcar automàticament qualsevol dels 6 nivells des de `staticres.c`.
  - `docs/DOS_CPC_COORDINATES.md`: especificació tècnica completa.
  - `AGENTS.md`: afegida la regla 4 que prohibeix explícitament ajustar posicions a ull.


## Sessio 2026-10-17 (21): Sistema de Portes i Habitacions 1:1 (Nivell 1 i Estudi Resta de Nivells)
- **Estudi exhaustiu 1:1 dels 6 nivells de DOS (`level_door`, `pos[] = { 74, 74, 77, 66, 102 }`)**:
  - Nivell 0 (PB Store / Magasin): 23 portes, 5 habitacions (Rooms 0..4) de 20 columnes d'ample cadascuna a la fila 74..83 (20x10 = 200 rajoles per habitació, 1000 rajoles en total).
  - Nivell 1: 0 portes (sense habitacions).
  - Nivell 2: 24 portes (habitacions a fila 77).
  - Nivell 3: 20 portes (habitacions a fila 66 + passatges secrets).
  - Nivell 4: 2 portes (1 parell anada i tornada).
  - Nivell 5: 6 portes (teleports directes al mateix mapa exterior).
- **Arquitectura de Memòria i Bancs per a Portes i Sales (Opció A)**:
  - `ROOMS0.BIN` (1000 B) empaquetat a `MUSMAIN.BIN` a l'offset 0x1400 (`0xC1:0x6400`).
  - Taula de 23 portes (92 B) empaquetada a `MUSMAIN.BIN` a l'offset 0x1800 (`0xC1:0x6800`).
  - Lectura transparent a cost 0 de RAM estàtica de Bloc 0.
- **Transició de pantalla i renderitzat**:
  - `palette_black()` i `palette_restore()` a `engine/video.s` per a fos a negre net.
  - `render_room(room_idx)` a `src/render.c` que dibuixa els 20x10 tiles de la sala amb rajoles bancades de 0xC1.
  - Bloqueig horitzontal de càmera (`s_scrolling_locked = 1`, `g_cam_x4 = room_idx * 40`, `g_cam_row = 148`).
- **Detecció i col·lisió 1:1**:
  - Activador `SPACE + UP` coincident amb DOS (`level.c:1210`).
  - Coordenades de rajola de peus: `(py + 29) >> 4` (70 exterior, 82 interior), coincidents amb `ypos16 = 70` de DOS.
  - Destinació de peus ajustada a `(dst_row + 1) * 16 - 30` (terra a fila 71 exterior, 83 interior).
  - Centrat horitzontal amb `(dst_col << 6) - 32` per col·locar Jake centrat sobre la rajola de la porta.
  - Col·lisió vertical a `src/main.c` adaptada amb `max_r = s_in_room ? 84 : LEVEL_MAP_H` per permetre aterratge sòlid sobre el terra de l'habitació a la fila 83.
- **Optimitzacions SDCC i correcció FDC**:
  - Desacoblament de pantalles inicials a `engine/front_tables.h` i execució única via `FRONT_RUN` a `engine/front.c`.
  - Correcció a `engine/assets_fdc.s` (canviat `0xC0` hardcoded per `_g_fdc_home_bank`), mantenint mapejat el banc 4 durant les lectures de disc del FRONT.
  - Protecció de registre `d` a `src/moving.c` contra clobbering per LDIR de còpia FDC scratch.
  - Marge de memòria del Bloc 0 optimitzat: `_CODE` acaba a `0x3661` amb un marge positiu de **+287 BYTES** abans de `_DATA` (`0x3780`).
- **Verificació en emulador ZEsarUX**:
  - Script `tools/verify_door_live.py`: cicle complet validat amb captures (`verify_door_outside_before.png`, `verify_door_room_inside.png`, `verify_door_room_walking.png`, `verify_door_room_at_exit.png`, `verify_door_outside_after.png`).

## Sessio 2026-10-17 (22): Correcció Definitiva de l'Scroll i Franges Verticals en Sortir del Cinema
- **Diagnòstic de l'avaria**:
  - Les captures mostraven franges verticals de color blau/gris a la meitat de les columnes en caminar/desplaçar-se després de sortir d'una habitació o cinema.
  - **Causa arrel 1 (Double Buffer dx == 2)**: Al bucle principal a 25 Hz amb doble buffer, quan en Jake es mou de manera continuada (`move_x != 0`), el desplaçament relatiu acumulat per buffer (`page_dx = s_pending_x + move_x`) és de **2 caràcters CRTC** (4 Mode 0 pixels cada un = 8 bytes per línia). La rutina `sync_backbuffer` anteriorment només pintava la columna d'extrem (`sx = 39` en anar a la dreta o `sx = 0` en anar a l'esquerra), deixant la columna intermèdia (`sx = 38` o `sx = 1`) sense actualitzar. En sortir d'una habitació (on tota la VRAM contenia les rajoles de la sala), aquesta columna intermèdia no pintada mantenia les rajoles antigues de la sala, creant franges verticals alternades.
  - **Causa arrel 2 (Estat d'entitats pendent)**: En canviar d'habitació o sortir-ne, els flags `drawn[page]` d'ascensors, enemics, caixes i popups conservaven el valor `1` de la posició prèvia. En el primer frame post-transició, `moving_restore()` i `enemy_restore()` restauraven els blocs de fons de la ubicació antiga directament sobre la pantalla acabada de carregar de la nova sala.
- **Solució implementada**:
  - **`sync_backbuffer` multicolumna i multifila (`src/main.c`)**:
    - Si `dx > 0`: si `dx > 1`, dibuixa la columna `sx = 38` i després la columna `sx = 39` a la posició `target_row`.
    - Si `dx < 0`: dibuixa la columna `sx = 0` i si `dx < -1`, la columna `sx = 1`.
    - Si `dy > 0`: si `dy > 1`, dibuixa la fila `sy = 18` i després la fila `sy = 19`.
    - Si `dy < 0`: dibuixa la fila `sy = 0` i si `dy < -1`, la fila `sy = 1`.
  - **Neteja d'estat d'entitats a `enter_door` (`src/main.c`)**:
    - Neteja de `g_mag_elevators[i].drawn[0..1] = 0`.
    - Cridada a `enemy_init()` per reinicialitzar els slots de walkers i projectils.
    - Neteja de `s_carry_drawn[0..1] = 0`, `s_have_drawn[0..1] = 0`, `s_rep_n = 0`.
    - Redibuix immediat d'ascensors visibles en cas de retorn al mapa exterior (`moving_draw(0, ...)`, `moving_draw(1, ...)`).
- **Pressupost de memòria del Bloc 0 (`0x0000..0x3FFF`)**:
  - `_CODE`: `0x0100..0x3723` (13.859 B).
  - Marge positiu fins a `_DATA` (`0x3780`): **+93 BYTES**.
  - Pila lliure (`SP` fins a `0x3FFE`): **1.065 BYTES**.
- **Validació en viu a ZEsarUX**:
  - Script automatitzat `tools/test_verify_scroll.py`: cicle complet d'entrada al cinema (`fix_cinema_inside.png`), sortida a l'exterior (`fix_cinema_outside_before_scroll.png`), scroll continu a la dreta (`fix_cinema_outside_after_scroll_right.png`) i scroll continu a l'esquerra (`fix_cinema_outside_after_scroll_left.png`).
  - Resultat: 0 franges verticals, 0 restes de la sala, transició i desplaçament 100% sòlids i nets.

