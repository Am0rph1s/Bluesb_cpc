# The Blues Brothers — Port per a Amstrad CPC 6128 (Mode 0)

Reimplementació moderna, creada des de zero, del clàssic **The Blues Brothers** (Titus Software, 1991) per a maquinari **Amstrad CPC 6128 (128 KB)** en **Mode 0 (160×200, 16 colors)** a **25 Hz fixos**.

Aquest projecte substitueix la versió comercial històrica de CPC (que funcionava en Mode 1 amb 4 colors i baixa fidelitat) per un motor d'alt rendiment que aprofita al màxim les capacitats del maquinari: scroll per maquinari per registres CRTC, doble buffer circular a VRAM sense parpelleig, blitter d'sprites per màscara en assemblador Z80 pur i física exacta subpíxel 1:1 basada en l'enginyeria inversa dels fitxers originals de Titus.

---

## 📖 Taula de Continguts
1. [Fonts d'Informació i Enginyeria Inversa](#-fonts-dinformació-i-enginyeria-inversa)
2. [Arquitectura del Sistema i Maquinari CPC](#-arquitectura-del-sistema-i-maquinari-cpc)
3. [Mapa de Memòria de 128 KB](#-mapa-de-memòria-de-128-kb)
4. [Motor Gràfic i Sistema de Paleta Mode 0](#-motor-gràfic-i-sistema-de-paleta-mode-0)
5. [Estructura del Codi Font](#-estructura-del-codi-font)
6. [Eines i Pipeline d'Assets](#-eines-i-pipeline-dassets)
7. [Instruccions de Compilació i Execució](#-instruccions-de-compilació-i-execució)
8. [Verificació i Testing Automatitzat](#-verificació-i-testing-automatitzat)

---

## 🔍 Fonts d'Informació i Enginyeria Inversa

Tota la lògica de moviment, mapes de nivell, rajoles i sprites s'extreuen fidelment de les versions originals per a MS-DOS i Amiga de Titus:

1. **Formats de fitxers de Titus Software (DOS)**:
   - Els fitxers empaquetats de dades (`.SQZ`, `.SQV`, `.SQL`) empren un algorisme de compressió propietari LZW desenvolupat per Titus.
   - S'ha implementat el descompressor natiu a `tools/bbdata/unsqz.py` per desempaquetar els recursos autèntics.
   - `assets/bbdata/SPRITE.SQV`: conté tots els sprites originals de Jake, personatges secundaris i objectes en format planar de 4 plans de bits (16 colors).
   - `assets/bbdata/CHOIX.SQZ`: pantalles de selecció i menú.
   - `assets/bbdata/1.EXE` i `assets/bbdata/2.EXE`: binaris MS-DOS desensamblats d'on s'ha extret la màquina d'estats, la física subpíxel i les taules d'animació originals.
2. **Projecte de referència de la comunitat (`blues` / cyxx)**:
   - S'ha utilitzat com a referència documental l'enginyeria inversa del motor de Titus feta per Gregory Montoir (cyxx/blues), que documenta les estructures de dades dels nivells, taules d'activació i patrons d'animació.
3. **Nivell 1 — Magatzem / Magasin**:
   - `TILESET0.BIN`: 256 tiles de 16×16 píxels en format nadiu Mode 0 de CPC (16 KB).
   - `MAP0.BIN`: Mapa matricial de 128 columnes × 72 files de rajoles (9.216 bytes).
   - `TRIG0.BIN`: Taula de propietats de física per a cada rajola (tipus de sòl, parets sòlides, ascensors, cintes transportadores i pendents).

---

## ⚙️ Arquitectura del Sistema i Maquinari CPC

El projecte està dissenyat per executar-se en un **Amstrad CPC 6128 real** (o qualsevol CPC 464/664 equipat amb ampliació de memòria DDI-1 / 128 KB):

- **Processador Z80 a 4 MHz (1 MHz efectiu per cicles de memòria de 4 T-states)**.
- **Sincronització fixa a 25 Hz**: La interrupció vertical de l'Amstrad CPC genera 300 interrupcions per segon (50 Hz amb 6 interrupcions per quadre de vídeo). El comptador global `_g_ticks` gestiona un període fix de 12 ticks (40 ms = 25 FPS sòlids), eliminant qualsevol tearing o desincronització de velocitat.
- **Scroll circular CRTC en maquinari (Ring Buffer de 16 KB)**:
  - S'utilitzen els registres R12 i R13 del CRTC per desplaçar l'adreça base de memòria (`MA = (cam_row * 40 + cam_x4) & 0x03FF`).
  - L'scroll avança en passos fins de 4 píxels (1 paraula de caràcter CRTC).
  - La pantalla visible fa 40 caràcters d'ample (160 píxels Mode 0) i 20 files de caràcters (160 línies de trama).
  - La funció `render_column()` i `render_row()` només dibuixa la tira de mitja rajola que entra per la vora al backbuffer.
- **Doble Pàgina VRAM (Doble Buffer flicker-free)**:
  - Pàgina A: `0xC000 .. 0xFFFF`
  - Pàgina B: `0x8000 .. 0xBFFF`
  - El personatge i els elements mòbils es dibuixen sempre fora de pantalla a la pàgina oculta, alternant el punter del CRTC durant el VSYNC (`cpc_wait_vsync_start`).

---

## 🗺️ Mapa de Memòria de 128 KB

L'Amstrad CPC 6128 disposa de 128 KB de RAM estructurats en 8 bancs de 16 KB cadascun (Bancs 0 a 7), commutats mitjançant el Gate Array (port `0x7Fxx`, configuracions `0xC0..0xC7`):

| Espai d'Adreces | Bloc Físic | Contingut / Funció | Mida |
| :--- | :--- | :--- | :--- |
| **`0x0100 .. 0x3412`** | Banc 0 | **`_CODE`**: Codi executable resident (SDCC + ASM natiu) | ~13,0 KB |
| **`0x3413 .. 0x377F`** | Banc 0 | **Marge lliure de codi** al Bloc 0 | ~878 bytes |
| **`0x3780 .. 0x3BDF`** | Banc 0 | **`_DATA`**: Variables globals, HUD, comptadors i buffers | 1.119 bytes |
| **`0x3BE0 .. 0x3FFE`** | Banc 0 | **Pila del sistema Z80 (SP)** (espai lliure segur) | > 1.050 bytes |
| **`0x4000 .. 0x7FFF`** | Banc 4 (`0xC4`) | **`TILESET0.BIN`**: Rajoles del nivell en Mode 0 (256 tiles × 64 B) | 16.384 bytes |
| **`0x4000 .. 0x63FF`** | Banc 5 (`0xC5`) | **`MAP0.BIN`**: Matriu del mapa del nivell (128 × 72 rajoles) | 9.216 bytes |
| **`0x6400 .. 0x6DFF`** | Banc 5 (`0xC5`) | **`TRIG0.BIN`**: Dades de col·lisió i física de tiles (256 × 10 B) | 2.560 bytes |
| **`0x6E00 .. 0x7FC4`** | Banc 5 (`0xC5`) | **`BANK5.BIN`**: Codi de nivell resident, gestor de triggers i ascensors | 4.548 bytes |
| **`0x4000 .. 0x5BFF`** | Banc 6 (`0xC6`) | **`ENEMI1.BIN`**: 14 celes d'enemics en Mode 0 (14 × 512 B) | 7.168 bytes |
| **`0x5C00 .. 0x7486`** | Banc 6 (`0xC6`) | **`ENEMYCODE.BIN`**: Motor d'IA d'enemics, projectils i taula de salts | 6.278 bytes |
| **`0x7A00 .. 0x7FFF`** | Banc 6 (`0xC6`) | **Pool de fons d'enemics** (6 slots dinàmics de 256 B) | 1.536 bytes |
| **`0x4000 .. 0x70BF`** | Banc 7 (`0xC7`) | **`PFRAMES.BIN`**: 26 frames d'en Jake (16 px Mode 0 × 30 línies) | 12.480 bytes |
| **`0x70C0 .. 0x751F`** | Banc 7 (`0xC7`) | Buffers de fons dels 5 ascensors magnètics (pàgines A i B) | 1.120 bytes |
| **`0x7520 .. 0x76FF`** | Banc 7 (`0xC7`) | Buffers de fons d'en Jake per a VRAM A i B (2 × 240 B) | 480 bytes |
| **`0x7700 .. 0x78DF`** | Banc 7 (`0xC7`) | Buffer de flip horitzontal dinàmic (H-FLIP, 16 B/l × 30 l) | 480 bytes |
| **`0x78E0 .. 0x7A9F`** | Banc 7 (`0xC7`) | **`ELEV.BIN`**: Frames d'ascensors | 448 bytes |
| **`0x7AA0 .. 0x7E7F`** | Banc 7 (`0xC7`) | **`EXTRA.BIN`**: Caixa (128 B), globus (224 B), paraigües (640 B) | 992 bytes |
| **`0x7F00 .. 0x7FFF`** | Banc 7 (`0xC7`) | Taula LUT de swap de píxels Mode 0 (`sprite_hflip_init_lut`) | 256 bytes |
| **`0x8000 .. 0xBFFF`** | Banc 1 / 3 | **Pàgina VRAM B** (Doble buffer CRTC MA `0x2000`) | 16.384 bytes |
| **`0xC000 .. 0xFFFF`** | Banc 1 / 3 | **Pàgina VRAM A** (Pàgina principal CRTC MA `0x3000`) | 16.384 bytes |

---

## 🎨 Motor Gràfic i Sistema de Paleta Mode 0

### Format de Píxels en Mode 0
En Mode 0, la resolució és de 160×200 píxels amb 16 colors per pantalla simultanis. Cada byte de la memòria de vídeo codifica **2 píxels**, entrellaçant els seus 4 bits de color en un format específic del Gate Array d'Amstrad:
- Píxel 0 (esquerra): Bits 7 (b0), 3 (b1), 5 (b2), 1 (b3)
- Píxel 1 (dreta): Bits 6 (b0), 2 (b1), 4 (b2), 0 (b3)

### Resolució del conflicte de colors entre el Nivell i la Camisa d'en Jake
Inicialment, la camisa d'en Jake compartia el Pen 2 amb les canonades del nivell. En reassignar el Pen 2 a blanc, tot l'escenari va perdre el to gris metàl·lic.

Mitjançant una anàlisi exhaustiva de `TILESET0.BIN`, es va determinar que **el Pen 0 tenia exactament 0 píxels utilitzats a tot el nivell 1** (totalment desocupat). Això va permetre aïllar la paleta de forma òptima:
- **Pen 0 (`0x4B`)**: Blanc Pur per a la camisa i reflexos d'en Jake. Com que cap tile utilitza el Pen 0, les canonades no es veuen afectades en absolut.
- **Pen 1 (`0x47`)**: Rosa / To de carn per a la cara i les mans.
- **Pen 2 (`0x40`)**: Gris metàl·lic original de les canonades i estructures de l'escenari.
- **Pen 4 (`0x44`)**: Blau fosc per a detalls del vestit.
- **Pen 8 (`0x57`)**: Blau cel per al fons de l'escenari.
- **Pen 11 (`0x54`)**: Negre sòlid per al vestit, barret i ulleres de sol d'en Jake.
- **Pen 15 (`0x40`)**: Gris clar per a les parets i bigues de fons.

### Mida i Format dels Sprites (16 píxels Mode 0 / 8 bytes)
- **Amplada**: 16 píxels Mode 0 = 32 píxels DOS = 8 bytes per línia.
- **Alçada**: 30 línies de trama.
- **Estructura per línia**: 8 parells `[inv_mask, img_masked]` = 16 bytes per línia $\times$ 30 línies = **480 bytes per frame**.
- **Blitter ASM sense branques (`engine/sprite.s`)**: desenrotllat en `.rept 8`, executa el blit amb màscara i desa el fons original simultàniament en un sol recorregut lineal (~21.000 T-states).
- **Gir horitzontal ultra-ràpid (`engine/sprite_hflip.s`)**: inverteix l'sprite cap a l'esquerra mitjançant una taula LUT de 256 valors a `0x7F00` en temps constant sense sobrecarregar la CPU.

---

## 📁 Estructura del Codi Font

```
bluesb_cpc/
├── assets/
│   └── bbdata/              # Dades autèntiques extretes del joc (bancs, tiles, mapes)
│       ├── PFRAMES.BIN      # 26 frames d'en Jake en Mode 0 (12.480 B)
│       ├── TILESET0.BIN     # 256 tiles 16x16 Mode 0 (16.384 B)
│       ├── MAP0.BIN         # Matriu 128x72 del nivell 1 (9.216 B)
│       ├── TRIG0.BIN        # Propietats de física i col·lisió de tiles (2.560 B)
│       └── SPRITE.SQV       # Fitxer planar d'sprites original de Titus DOS
├── engine/                  # Capa de baix nivell i controladors Z80
│   ├── cpc_hardware.s       # Primitives de maquinari del CPC (ports, CRTC, GA)
│   ├── video.s              # Inicialització del Mode 0 i taula de paleta de colors
│   ├── sprite.s             # Blitter i restauració de fons d'en Jake (8 bytes/línia)
│   ├── sprite_hflip.s       # Rutina ASM de gir horitzontal 1:1 via taula LUT
│   ├── tile_blit.s          # Renderitzat ràpid de rajoles i columnes al ring buffer
│   ├── moving_blit.s        # Dibuix d'ascensors i elements mòbils
│   ├── enemy_table.s        # Taula de salts i rutines ASM del motor d'enemics al Banc 6
│   ├── starter.c            # Carregador primari amb FDC directe
│   ├── fdc.c / fdc.s        # Carregador de disc per sectors directes (FDC raw)
│   ├── isr.s                # Rutina d'interrupció del sistema (comptador 300 Hz i música)
│   └── stack_canary.h       # Verificador de seguretat de la pila Z80
├── src/                     # Lògica d'alt nivell del joc
│   ├── main.c               # Bucle principal a 25 Hz, física subpíxel i seguiment
│   ├── enemy.c              # Motor d'enemics resident al Banc 6 (20 slots, IA, trets)
│   ├── moving_bank.c        # Lògica de nivell resident al Banc 5 (triggers, ascensors)
│   ├── moving.c             # Gestor d'ascensors magnètics i cintes transportadores
│   ├── render.c             # Gestió de la càmera i sincronització de vores
│   ├── player_frames.h      # Taula d'offsets i mides dels 26 frames d'en Jake
│   └── moving.h             # Definicions d'estructures d'ascensors i buffers
├── docs/                    # Documentació tècnica i referències
│   ├── DOS_CPC_COORDINATES.md # Especificació matemàtica oficial 1:1 de coordenades
│   └── zrcp-control.md      # Manual de control remot via protocol ZEsarUX
├── tools/                   # Eines Python de construcció i generació
│   ├── build.py             # Script principal de compilació, enllaç i creació de DSK
│   ├── dos_coord_converter.py # Convertidor matemàtic de coordenades DOS <-> CPC
│   ├── gen_enemy_frames.py  # Generador de celes d'enemics Mode 0 per al Banc 6
│   ├── generate_cpc_jake_dos.py # Convertidor d'sprites DOS SQV -> Mode 0 CPC
│   ├── export_dos_vga_sheet.py  # Exportador del full de referència dels 50 frames
│   ├── verify_all_actions.py    # Suite de test automàtic amb l'emulador ZEsarUX
│   └── bbdata/              # Llibreries d'enginyeria inversa (unsqz, sprites)
├── AGENTS.md                # Regles d'or del projecte (fidelitat 1:1 obligatòria)
├── ESTAT.md                 # Diari detallat de progrés i sessions tècniques
└── README.md                # Aquesta documentació
```

---

## 🛠️ Eines i Pipeline d'Assets

### 1. Extracció d'sprites originals
L'script `tools/export_dos_vga_sheet.py` llegeix `SPRITE.SQV`, extreu els 50 frames d'en Jake i genera una fulla completa amb les mides i coordenades exactes.

### 2. Conversió a Mode 0 de CPC
L'script `tools/generate_cpc_jake_dos.py`:
- Carrega els frames seleccionats de `SPRITE.SQV`.
- Escala horitzontalment al 50% per compensar l'aspect ratio del Mode 0 (on cada píxel és el doble d'ample que en VGA/EGA).
- Centra l'sprite dins de la caixa estàndard de 16 píxels Mode 0 (8 bytes) $\times$ 30 línies de trama.
- Aplica el mapatge de colors al Pen 0 (blanc per a la camisa), Pen 1 (carn per a la cara/mans), Pen 11 (negre per al vestit/barret/ulleres) i Pen 4/12 (blaus del vestit).
- Genera les màscares invertides (`inv_mask`) i imatges màscara (`img_masked`) llestes per a consum directe del blitter en assemblador.
- Escriu directament `assets/bbdata/PFRAMES.BIN` (12.480 B) i actualitza automàticament `src/player_frames.h`.

---

## 🚀 Instruccions de Compilació i Execució

### Requisits
1. **SDCC 4.5+** (Small Device C Compiler) amb `sdasz80` instal·lat (per defecte a `C:\Program Files\SDCC\bin`).
2. **Python 3.8+** amb la llibreria `Pillow` instal·lada (`pip install pillow`).
3. Opcional: **ZEsarUX 13.0+** per a proves automatitzades via socket remot.

### Compilació del projecte
Des de l'arrel del projecte, executeu:

```powershell
py -3 tools/build.py
```

El procés de compilació realitza:
1. Assemblat de tots els fitxers Z80 (`.s`) a fitxers objecte (`.rel`) amb `sdasz80`.
2. Compilació de tots els fitxers C (`.c`) amb optimització de codi i registre Z80 (`--opt-code-size`).
3. Enllaç amb localització explícita de memòria:
   - `--code-loc 0x0100`
   - `--data-loc 0x36A0`
4. Comprovació automàtica del pressupost de memòria del Bloc 0 (assegura que `_CODE` no envaeixi `_DATA` i que la pila disposi de més de 2.000 bytes lliures).
5. Conversió d'`ihx` a format binari executable AMSDOS.
6. Creació de la imatge de disc virtual `bluesb.dsk` amb format AMSDOS de 40 pistes.

---

## 🧪 Verificació i Testing Automatitzat

El projecte disposa d'un entorn de proves d'integració contínua completament automatitzat amb l'emulador **ZEsarUX**:

```powershell
py -3 tools/verify_all_actions.py
```

Aquest script:
1. Engega ZEsarUX en mode emulació de CPC 6128 amb la imatge `bluesb.dsk`.
2. Connecta per socket TCP al protocol remot de l'emulador.
3. Injecta la comanda `run"bluesb"` al teclat virtual del CPC.
4. Espera la càrrega des del disc i executa la seqüència d'accions:
   - Repòs (Idle dreta)
   - Caminar cap a la dreta
   - Caminar cap a l'esquerra (test del buffer H-FLIP i blitter invers)
   - Ajupir-se (test de la caixa de col·lisió i frame duck)
   - Arrossegar-se (test de l'animació de crawl 16 px)
   - Salt a l'aire amb el barret (test de l'amplada completa de cames sense retalls)
5. Captura les pantalles de vídeo del CPC directament des de la VRAM de l'emulador per verificar la integritat visual i absència de fallades.
