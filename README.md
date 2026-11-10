# The Blues Brothers — Port per a Amstrad CPC 6128 (Mode 0)

Reimplementació completa i moderna, creada des de zero, del clàssic **The Blues Brothers** (Titus Software, 1991) per a maquinari **Amstrad CPC 6128 (128 KB)** en **Mode 0 (160×200, 16 colors)** a **25 Hz fixos**.

Aquest projecte substitueix la versió comercial històrica de CPC (que funcionava en Mode 1 amb només 4 colors i baixa fidelitat) per un motor d'alt rendiment que aprofita al màxim les capacitats del maquinari: scroll per maquinari mitjançant registres CRTC, doble buffer circular a VRAM sense cap parpelleig (*flicker-free*), blitter d'sprites per màscara en assemblador Z80 pur i física exacta subpíxel 1:1 rigorosament fidel a la versió original de MS-DOS.

El joc complet —amb els **6 nivells íntegres**, pantalles d'introducció, selecció de personatge, mapa de transició, seqüència de final i banda sonora multicanal— cap en un **únic disc de 180 KB (AMSDOS estàndard)** amb més de **24 KB de marge lliure**.

---

## 📖 Taula de Continguts
1. [Característiques Principals](#-característiques-principals)
2. [Els 6 Nivells del Joc i Arquitectura en Disc Únic](#-els-6-nivells-del-joc-i-arquitectura-en-disc-únic)
3. [Arquitectura del Sistema i Maquinari CPC](#-arquitectura-del-sistema-i-maquinari-cpc)
4. [Mapa de Memòria de 128 KB](#-mapa-de-memòria-de-128-kb)
5. [Motor Gràfic i Harmonització de Paletes Mode 0](#-motor-gràfic-i-harmonització-de-paletes-mode-0)
6. [Pipeline Gràfic i Edició d'Assets (`graphics_edit/`)](#-pipeline-gràfic-i-edició-dassets-graphics_edit)
7. [Estructura del Codi Font](#-estructura-del-codi-font)
8. [Compilació i Pipeline de Rendiment](#-compilació-i-pipeline-de-rendiment)
9. [Verificació i Testing Automatitzat](#-verificació-i-testing-automatitzat)
10. [Fonts d'Informació i Enginyeria Inversa](#-fonts-dinformació-i-enginyeria-inversa)

---

## 🌟 Característiques Principals

- **Mode 0 a 16 colors reals**: Paleta viva de 16 colors per nivell (escollits dels 27 colors de maquinari del Gate Array), amb colors dedicats per a Jake i Elwood (camisa blanca, pell, vestit negre i blau marí) harmonitzats sense conflictes amb els fons ni els enemics.
- **Scroll circular CRTC en maquinari**: Desplaçament suau per maquinari (registres R12/R13) en passos de 4 píxels (1 paraula CRTC), actualitzant només les vores entrants al ring buffer de 16 KB.
- **Doble buffer flicker-free a 25 Hz fixos**: Alternança de pàgines de VRAM (`0xC000` i `0x8000`) sincronitzada amb el VBL a 50 Hz (comptador a 12 interrupcions = 40 ms per quadre).
- **Física 1:1 rigorosa DOS**: Velocitats subpíxel, inèrcia, acceleració, caixes que es poden agafar i llançar, globus per planar, paraigües per frenar caigudes, ascensors magnètics, cintes transportadores i col·lisions de sostre, terra i parets fidels al codi original de Titus.
- **Carregador raw FDC directe**: Rutina de lectura directa de sectors de disquetera resident a la memòria C1 (`0x7800`), evitant les limitacions i lentituds d'AMSDOS durant la càrrega entre nivells.
- **Música chiptune multicanal**: Reproductor Arkos Tracker 2 (AKG) resident a C1:0x4000 amb totes les pistes de la banda sonora autèntica (Peter Gunn Theme, etc.).
- **Optimització extrema de disc**: Compressió ZX0 de tots els paquets d'escenari, enemics i codi de nivell, aconseguint encabir tot el contingut en una cara d'un disc estàndard de 3" (180 KB).

---

## 🎮 Els 6 Nivells del Joc i Arquitectura en Disc Únic

Tots els nivells originals estan completament desenvolupats, empaquetats i operatius:

1. **Nivell 1 — Magatzem (Magasin)**: Caixes de fusta, prestatgeries industrials, gossos guardians, caixes llançables i ascensors magnètics.
2. **Nivell 2 — Fàbrica (Factory / ENT)**: Maquinària pesada, cintes transportadores actives, canonades industrials i obrers armats.
3. **Nivell 3 — Presó (Prison)**: Murs de pedra, barrots de cel·les, policies amb porres i escuts, rates de claveguera i armes de foc.
4. **Nivell 4 — Clavegueres (Sewers)**: Túnels subterranis, plataformes flotants sobre aigua tòxica i perills dinàmics.
5. **Nivell 5 — Ciutat i Teulades (City)**: Edificis urbans, teulades de gran alçada, antenes i enemics saltadors.
6. **Nivell 6 — Concert Final (Concert)**: L'escenari final de l'actuació, la banda al complet i la conclusió de l'aventura.

### Layout del Disc (`bluesb.dsk`, 180 KB AMSDOS)
El disc conté 24 fitxers optimitzats al mil·límetre:
- `STARTER.BIN`: Carregador d'arrencada inicial en C/ASM.
- `GAME.BIN`: Motor principal resident (`_CODE` + `_DATA`).
- `MUSBANK.BIN`: Reproductor AKG + pistes d'àudio + taules de sectors FDC (`LVLCHS`).
- `PFRAMES.BIN`: 26 frames d'en Jake/Elwood en Mode 0 (12.480 B).
- `SPLASH.ZX0`, `MAP.ZX0`, `FSELECT.ZX0`, `END.ZX0`: Pantalles i seqüències comprimides en ZX0.
- `LVL1_W.ZX0` .. `LVL6_W.ZX0`: Paquets de món (tileset + matriu de mapa + triggers) per a cada nivell.
- `LVL1_E.ZX0` .. `LVL6_E.ZX0`: Paquets d'enemics (sprites Mode 0 + taula d'instanciació) per a cada nivell.
- `LVL1_C.ZX0` .. `LVL6_C.ZX0`: Codi resident de nivell (triggers específics, lògica de sala i ascensors).

---

## ⚙️ Arquitectura del Sistema i Maquinari CPC

El projecte està dissenyat per executar-se en un **Amstrad CPC 6128 real** (o CPC 464/664 amb ampliació DDI-1 / 128 KB):

- **Processador Z80 a 4 MHz** (1 MHz efectiu per cicles d'accés a memòria compartida amb el Gate Array).
- **Sincronització fixa a 25 Hz**: La interrupció vertical de l'Amstrad CPC genera 300 interrupcions per segon (6 per quadre de vídeo a 50 Hz). El comptador global `_g_ticks` gestiona un període de 12 ticks (40 ms = 25 FPS sòlids), eliminant qualsevol tearing o desincronització.
- **Scroll circular CRTC en maquinari (Ring Buffer de 16 KB)**:
  - S'utilitzen els registres R12 i R13 del CRTC per desplaçar l'adreça base de memòria (`MA = (cam_row * 40 + cam_x4) & 0x03FF`).
  - L'scroll avança en passos fins de 4 píxels (1 paraula de caràcter CRTC).
  - La pantalla visible fa 40 caràcters d'ample (160 píxels Mode 0) i 20 files de caràcters (160 línies de trama).
  - La funció de render només dibuixa la tira de mitja rajola que entra per la vora al backbuffer.
- **Doble Pàgina VRAM (Doble Buffer flicker-free)**:
  - Pàgina A: `0xC000 .. 0xFFFF`
  - Pàgina B: `0x8000 .. 0xBFFF`
  - El personatge i els elements mòbils es dibuixen sempre fora de pantalla a la pàgina oculta, alternant el punter del CRTC durant el VSYNC (`cpc_wait_vsync_start`).
- **Controlador de Disc FDC uPD765 directe**:
  - Les dades de cada nivell es llegeixen per sectors consecutius directament des del xip FDC a C1:0x7800, aconseguint lectures a màxima velocitat de transferència física sense la sobrecàrrega del firmware AMSDOS.

---

## 🗺️ Mapa de Memòria de 128 KB

L'Amstrad CPC 6128 disposa de 128 KB de RAM estructurats en 8 bancs de 16 KB cadascun (Bancs 0 a 7), commutats mitjançant el Gate Array (port `0x7Fxx`, configuracions `0xC0..0xC7`):

| Espai d'Adreces | Bloc Físic | Contingut / Funció | Mida |
| :--- | :--- | :--- | :--- |
| **`0x0100 .. 0x34AC`** | Banc 0 | **`_CODE`**: Codi executable resident (SDCC + ASM natiu: bucle principal, física, càmera, blitters, FDC bridge) | ~13,2 KB |
| **`0x34AD .. 0x35FF`** | Banc 0 | **Marge lliure de codi** al Bloc 0 | ~340 bytes |
| **`0x3600 .. 0x3B15`** | Banc 0 | **`_DATA`**: Variables globals residents, HUD, paràmetres de nivell, estat compartit | ~1.301 bytes |
| **`0x3B40`** | Banc 0 | **Canari de seguretat de la pila** (`0x55AA`) | 2 bytes |
| **`0x3B42 .. 0x3FFE`** | Banc 0 | **Pila del sistema Z80 (SP)** (espai lliure segur i verificat) | > 1.250 bytes |
| **`0x4000 .. 0x7FFF`** | Banc 4 (`0xC4`) | **Tileset i mapa actiu**: 256 tiles Mode 0 (16 KB) o dades descomprimides | 16.384 bytes |
| **`0x4000 .. 0x7FFF`** | Banc 5 (`0xC5`) | **Física i triggers de nivell**: Matriu de mapa (9 KB), taula TRIG (2,5 KB) i codi `BANK5.BIN` | 16.384 bytes |
| **`0x4000 .. 0x7FFF`** | Banc 6 (`0xC6`) | **Motor d'enemics**: 16 celes d'enemics Mode 0 (8 KB), codi IA (`ENEMYCODE.BIN`), pools de fons | 16.384 bytes |
| **`0x4000 .. 0x7FFF`** | Banc 7 (`0xC7`) | **Herois i objectes**: 26 frames d'en Jake/Elwood (12,5 KB), ascensors, caixes, globus, paraigües, taula LUT de flip | 16.384 bytes |
| **`0x8000 .. 0xBFFF`** | Banc 1 / 3 | **Pàgina VRAM B** (Doble buffer CRTC MA `0x2000`) | 16.384 bytes |
| **`0xC000 .. 0xFFFF`** | Banc 1 / 3 | **Pàgina VRAM A** (Pàgina principal CRTC MA `0x3000`) | 16.384 bytes |
| **`0x4000 .. 0x4BFF`** | RAM 1 (`0xC1`) | **Reproductor AKG** (Arkos Tracker 2: `_akg_init=0x4009`, `_akg_play=0x40CE`, `_akg_stop=0x40BC`) | ~3 KB |
| **`0x4C00 .. 0x5CFF`** | RAM 1 (`0xC1`) | **Banda sonora / Cançons**: Song intro i temes de nivell | ~4 KB |
| **`0x5D00 .. 0x602D`** | RAM 1 (`0xC1`) | **Taules de sectors de disc (`LVLCHS`)**: 814 bytes (món, enemics, codi per nivell) | 814 bytes |
| **`0x7800 .. 0x7BFF`** | RAM 1 (`0xC1`) | **Còpia mestra del carregador FDC raw** | 1.024 bytes |
| **`0x7C00 .. 0x7FFF`** | RAM 1 (`0xC1`) | **Buffer segur de taules de sectors** (zona permanent preservada) | 1.024 bytes |

---

## 🎨 Motor Gràfic i Harmonització de Paletes Mode 0

### Format de Píxels en Mode 0
En Mode 0, la resolució és de 160×200 píxels amb 16 colors per pantalla simultanis. Cada byte de la memòria de vídeo codifica **2 píxels**, entrellaçant els seus 4 bits de color en el format de maquinari del Gate Array d'Amstrad:
- **Píxel 0 (esquerra)**: Bits 7 (b0), 3 (b1), 5 (b2), 1 (b3)
- **Píxel 1 (dreta)**: Bits 6 (b0), 2 (b1), 4 (b2), 0 (b3)

### Harmonització Cromàtica dels 16 Pens
Per evitar conflictes de color entre els herois, els enemics i els elements d'escenari de cada nivell, la paleta s'organitza de forma estrictament coordinada:
- **Pen 0 (`0x4B`)**: Blanc Pur per a la camisa i reflexos d'en Jake/Elwood. Cap tile d'escenari no l'utilitza, assegurant que les canonades i parets mantenen els seus tons propis.
- **Pen 1 (`0x47`)**: Rosa / To de carn per a la cara i les mans.
- **Pen 11 (`0x54`)**: Negre sòlid per al vestit, barret i ulleres de sol.
- **Pens 4 i 12 (`0x44`, `0x50`)**: Blaus marí i reflexos del vestit.
- **Pens d'escenari i enemics (Pens 2, 3, 5, 6, 7, 8, 9, 10, 13, 14, 15)**: Harmonitzats per a cada nivell concret:
  - *Nivell 1 (Magatzem)*: Fons blaus industrials, fusta marró i metall gris.
  - *Nivell 2 (Fàbrica)*: Parets i canonades verdes, estructures de formigó i granotes vermelles (`0x5C` a pens 13/14) per als treballadors perquè destaquin nítidament.
  - *Nivell 3 (Presó)*: Murs de pedra fosca, barrots d'acer, uniformes policials en blau marí (`0x44`) i vermell (`0x5C`), sense malgastar cap dels 14 colors necessaris.

### Mida i Blitter dels Sprites (16 píxels Mode 0 / 8 bytes)
- **Amplada**: 16 píxels Mode 0 = 32 píxels DOS = 8 bytes per línia.
- **Alçada**: 30 línies de trama.
- **Estructura per línia**: 8 parells `[inv_mask, img_masked]` = 16 bytes per línia $	imes$ 30 línies = **480 bytes per frame**.
- **Blitter ASM sense branques (`engine/sprite.s`)**: desenrotllat en `.rept 8`, executa el blit amb màscara i desa el fons original simultàniament en un sol recorregut lineal (~21.000 T-states).
- **Gir horitzontal ultra-ràpid (`engine/sprite_hflip.s`)**: inverteix l'sprite cap a l'esquerra mitjançant una taula LUT de 256 valors a `0x7F00` en temps constant sense sobrecarregar la CPU.

---

## 🖌️ Pipeline Gràfic i Edició d'Assets (`graphics_edit/`)

El directori [`graphics_edit/`](graphics_edit/) conté tots els gràfics dels 6 nivells, personatges i pantalles fixes preparats per ser editats amb eines habituals (Aseprite, Photoshop, GIMP, GrafX2):

- **Importació directa al disc en un sol pas**:
  ```bash
  py -3 tools/graphics_tool.py import
  ```
  Llegeix els fitxers modificats, els converteix a Mode 0 de CPC, recompacta els binaris, comprimeix amb ZX0 natiu i reconstrueix la imatge de disc `bluesb.dsk`.
- **Exportació / Sincronització de recursos**:
  ```bash
  py -3 tools/graphics_tool.py export
  ```
  Genera mapes complets a escala 4:3 (`map_full.png`), mapes Mode 0 (`map_mode0.png`), graelles de rajoles (`tileset.png`), fulles d'enemics (`enemies.png`) i paletes JSON (`palette.json`).

Per a més informació, consulteu la guia detallada a [`graphics_edit/README.md`](graphics_edit/README.md).

---

## 📁 Estructura del Codi Font

```
bluesb_cpc/
├── assets/                  # Dades d'origen i binaris generats
│   └── bbdata/              # Paquets originals, tilesets, mapes i sprites
├── engine/                  # Capa de baix nivell i controladors Z80 en ASM pur
│   ├── cpc_hardware.s       # Primitives de maquinari del CPC (ports, CRTC, GA)
│   ├── video.s              # Inicialització del Mode 0 i taules de paleta
│   ├── sprite.s             # Blitter i restauració de fons d'en Jake/Elwood
│   ├── sprite_hflip.s       # Rutina ASM de gir horitzontal via taula LUT
│   ├── tile_blit.s          # Renderitzat ràpid de rajoles i columnes al ring buffer
│   ├── moving_blit.s        # Dibuix d'ascensors i elements mòbils
│   ├── enemy_table.s        # Taula de salts i rutines ASM del motor d'enemics
│   ├── starter.c            # Carregador primari amb FDC directe
│   ├── fdc.c / fdc.s        # Carregador de disc per sectors directes (raw FDC)
│   ├── isr.s                # Rutina d'interrupció (comptador 300 Hz i música)
│   └── stack_canary.h       # Verificador de seguretat de la pila Z80
├── src/                     # Lògica d'alt nivell del joc (C / ASM)
│   ├── main.c               # Bucle principal a 25 Hz, física subpíxel i cicle de joc
│   ├── enemy.c              # Motor d'enemics resident al Banc 6 (IA, trets)
│   ├── moving_bank.c        # Lògica de nivell resident al Banc 5 (triggers, ascensors)
│   ├── moving.c             # Gestor d'ascensors magnètics i cintes transportadores
│   ├── render.c             # Gestió de la càmera i sincronització de vores
│   └── player_frames.h      # Taula d'offsets i mides dels frames dels protagonistes
├── graphics_edit/           # Espai mestre d'edició d'imatges PNG i paletes JSON
├── docs/                    # Documentació tècnica d'enginyeria
│   ├── HANDOFF.md           # Estat actual detallat, tasques i decisions tècniques
│   ├── DOS_CPC_COORDINATES.md # Especificació matemàtica 1:1 de coordenades DOS <-> CPC
│   ├── OPTIMITZACIO_BUILD.md  # Arquitectura del pipeline de compilació ultraràpid
│   └── zrcp-control.md      # Manual de control remot via protocol ZEsarUX
├── tools/                   # Eines Python i auxiliars de construcció
│   ├── build.py             # Script principal de compilació, enllaç i generació de DSK
│   ├── graphics_tool.py     # Eina bidireccional d'importació/exportació de gràfics
│   ├── pack_level.py        # Empaquetador i optimitzador de dades de nivell
│   ├── dos_coord_converter.py # Convertidor matemàtic de coordenades DOS <-> CPC
│   ├── zx0_native.cs        # Compressor natiu ZX0 accelerat en C#
│   ├── smoke_test.py        # Suite de verificació ràpida (DSK, CRCs, arrencada)
│   ├── verify_all_levels.py # Suite de test complet dels 6 nivells en ZEsarUX
│   └── bbdata/              # Descompressor LZW Titus (unsqz.py) i eines d'enginyeria
├── AGENTS.md                # Regles d'or del projecte (fidelitat 1:1 obligatòria)
└── README.md                # Aquesta documentació
```

---

## ⚡ Compilació i Pipeline de Rendiment

### Requisits
1. **SDCC 4.5.0+** amb `sdasz80` (per defecte a `C:\Program Files\SDCC\bin`).
2. **Python 3.10+** amb la llibreria `Pillow` instal·lada (`pip install pillow`).
3. **.NET Framework 4.0+** (preinstal·lat a Windows moderns, utilitzat automàticament per `zx0_native.cs`).
4. Opcional: **ZEsarUX 13.0+** per a proves automatitzades via socket remot ZRCP.

### Compilació del Projecte
Des de l'arrel del repositori, executeu:

```powershell
py -3 tools/build.py
```

El pipeline de compilació és extremadament ràpid gràcies a l'arquitectura d'optimització (vegeu [`docs/OPTIMITZACIO_BUILD.md`](docs/OPTIMITZACIO_BUILD.md)):
- **Compilació incremental**: només **~6 segons**.
- **Compressor natiu ZX0 (`zx0_native.exe`)**: redueix el temps de compressió de 3 hores a menys de 6 minuts des de zero, o menys de 1 segon per a fitxers aïllats gràcies a la memòria cau SHA-256 a `obj/.zx0_cache/`.
- **Enllaç amb localització explícita de memòria**:
  - `--code-loc 0x0100`
  - `--data-loc 0x3600`
- **Generació automàtica del DSK**: construeix el disc de 40 pistes `bluesb.dsk` amb tots els 24 fitxers i sectors convergits.

---

## 🧪 Verificació i Testing Automatitzat

El projecte disposa d'un entorn complet de proves automatitzades:

### 1. Test Ràpid de Disc i Integritat (Smoke Test)
```powershell
# Comprovar catàleg, mides i CRCs CCITT dels 24 fitxers del DSK
py -3 tools/smoke_test.py --dsk-only

# Comprovar arrencada real a l'emulador (fins a magic=0xB0)
py -3 tools/smoke_test.py --boot-only
```

### 2. Verificació Automàtica de Tots els Nivells
```powershell
py -3 tools/verify_all_levels.py
```
Aquest script:
1. Engega l'emulador ZEsarUX en mode CPC 6128 amb la imatge `bluesb.dsk`.
2. Connecta per socket TCP al protocol remot ZRCP (port 10000).
3. Injecta la drecera per arrencar cadascun dels 6 nivells de manera independent.
4. Llegeix la memòria de l'emulador per verificar que el motor arrenca netament, que el canari de pila a `0x3B40` roman intacte (`0x55AA`) i que no hi ha cap caiguda al BASIC de Locomotive.

---

## 🔍 Fonts d'Informació i Enginyeria Inversa

Tota la lògica de moviment, mapes de nivell, rajoles, objectes i comportaments d'enemics s'extreuen directament del codi font i fitxers autèntics de Titus Software:

1. **Formats de fitxers de Titus Software (DOS)**:
   - Els paquets `.SQZ`, `.SQV`, `.SQL` empren una variant propietària de compressió LZW desenvolupada per Titus.
   - S'ha implementat el descompressor natiu a `tools/bbdata/unsqz.py` per desempaquetar els recursos autèntics.
   - `assets/bbdata/SPRITE.SQV`: conté tots els sprites originals en format planar de 4 plans de bits (16 colors).
2. **Codi font de referència original de DOS**:
   - `tools/blues_dos/bb/` (`level.c`, `objects.c`, `tiles.c`, `game.c`, `staticres.c`).
   - `tools/blues_dos/ja/` (`level.c`, `staticres.c`).
3. **Projecte de referència de la comunitat (`blues` / cyxx)**:
   - Enginyeria inversa del motor de Titus per Gregory Montoir (cyxx/blues), que documenta les estructures de dades dels nivells i patrons d'animació.\n