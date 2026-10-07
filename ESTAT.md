# ESTAT DEL PROJECTE — The Blues Brothers (CPC, català)

Última actualització: 2026-10-07 — Càmera uniforme 116/32 (fora freeze): segueix baixades, plans 0 tires; trigger cintes provat exacte (telemetria). Marge _CODE +378B.
Idioma de treball amb l'usuari: **català**.

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
