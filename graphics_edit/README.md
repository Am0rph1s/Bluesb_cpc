# Edició de Gràfics i Paletes — Blues Brothers CPC

Aquest directori és l'espai de treball mestre per a l'edició cromàtica i artística de tots els recursos visuals del joc. Permet editar còmodament els gràfics en formats estàndard (PNG i JSON) utilitzant eines modernes com Aseprite, Photoshop, GIMP o GrafX2, i reintegrar-los al joc automàticament amb una sola comanda.

---

## 📁 Estructura del Directori

### 1. Personatges Protagonistes
- **`player_jake/`**: Sprites d'en Jake Blues.
  - `jake.png`: Full d'sprites en graella de 6×5 cel·les (96×150 px totals, cel·les de 16×30 px en Mode 0 / canal alfa transparent).
  - `frames_guide.txt`: Documentació de cada índex de frame (caminar, ajupir-se, saltar, caure, agafar caixes, etc.).
  - `palette.json`: Definició dels colors corporatius d'en Jake (camisa blanca, pell, vestit negre i blau marí).
- **`player_elwood/`**: Sprites d'en Elwood Blues.
  - `elwood.png`: Full d'sprites amb les mateixes dimensions i estructura de frames.
  - `frames_guide.txt` i `palette.json`.

### 2. Nivells de Joc (1 a 6)
- **`level1_magasin/`**: Nivell 1 — Magatzem (Magasin).
- **`level2_factory/`**: Nivell 2 — Fàbrica (Factory).
- **`level3_prison/`**: Nivell 3 — Presó (Prison).
- **`level4_sewers/`**: Nivell 4 — Clavegueres (Sewers).
- **`level5_city/`**: Nivell 5 — Ciutat i teulades (City).
- **`level6_concert/`**: Nivell 6 — Concert final (Concert).

A cada carpeta de nivell trobaràs:
- **`map_full.png`**: Mapa complet muntat a resolució d'aspect ratio 4:3 (2048 × H px, Mode indexat 16 colors). **És el fitxer ideal per provar noves paletes globals i visualitzar l'aspecte en pantalla real!**
- **`map_mode0.png`**: Mapa complet en píxels natius Mode 0 (1024 × H px, tiles de 8×16 px).
- **`tileset.png`**: Graella de 16×16 tiles (256 tiles de 8×16 px Mode 0, mida total 128×256 px). Mode indexat amb la paleta del nivell.
- **`enemies.png`**: Graella de 4×4 cel·les d'enemics (16 cel·les de 16×32 px Mode 0, mida total 64×128 px, canal alfa transparent).
- **`palette.json`**: Mapatge dels 16 Pens (0..15) del Gate Array d'Amstrad CPC, indicant nom del color, codi maquinari i codi RGB de visualització.

### 3. Pantalles Fixes i Seqüències
- **`screen_splash/`**: Pantalla de presentació / Logo del joc (`splash.png`, 160×200 px Mode 0) + `palette.json`.
- **`screen_map/`**: Pantalla del mapa de la ciutat entre nivells (`map.png`, 160×200 px Mode 0) + `palette.json`.

---

## 🎨 Regles de la Paleta Mode 0 (16 Pens)

L'Amstrad CPC en Mode 0 pot mostrar simultàniament **16 colors en pantalla** escollits d'una paleta total de **27 colors de maquinari** (vegeu `CPC_27_COLORS_REFERENCE.json`).

Per garantir que els herois, els enemics i l'escenari conviuen sense corrompre els colors dels altres:
1. **Slots Reservats per als Blues Brothers (Pens 0, 1, 4, 11, 12)**:
   - **Pen 0 (`0x4B` / `#FFFFFF`)**: Blanc pur (camisa i reflexos). Cap rajola d'escenari ni fons no hauria d'utilitzar el Pen 0 tret que vulgui blanc pur.
   - **Pen 1 (`0x47` / `#FFA07A`)**: To de carn / pell (cara i mans).
   - **Pen 11 (`0x54` / `#000000`)**: Negre pur (barret, ulleres de sol, vestit, contorns).
   - **Pen 4 / Pen 12 (`0x44`, `0x50` / Blaus)**: Ombres i reflexos del vestit blau fosc.
2. **Slots Compartits i d'Escenari (Pens 2, 3, 5, 6, 7, 8, 9, 10, 13, 14, 15)**:
   - Assignats als fons, parets, plataformes i enemics específics de cada nivell.
   - Exemple Nivell 2: Els obrers usen vermell (`0x5C` a pens 13/14) i verd de la fàbrica, evitant confusions amb les canonades.
   - Exemple Nivell 3: La presó empra tons de pedra fosca, barrots metàl·lics i vermell/blau per a l'uniforme dels guàrdies.

---

## 🔄 Flux de Treball d'Edició i Reintegració

1. **Editar Gràfics o Paletes**:
   - Modifica directament els PNGs (`tileset.png`, `enemies.png`, `jake.png`, `splash.png`, etc.) o el fitxer `palette.json` del nivell corresponent.
   - Quan modifiquis colors RGB, el convertidor assignarà automàticament cada píxel al color de maquinari CPC més proper.

2. **Reintegrar automàticament al joc**:
   Executa des de la línia d'ordres:
   ```bash
   py -3 tools/graphics_tool.py import
   ```
   Aquesta ordre:
   - Llegeix tots els fitxers modificats a `graphics_edit/`.
   - Converteix els gràfics al format natiu entrellaçat de 2 píxels per byte de Mode 0 CPC.
   - Recompacta els binaris d'escenari i enemics (`TILESET*.BIN`, `ENEMI*.BIN`, `PFRAMES.BIN`).
   - Comprimeix amb l'accelerador natiu ZX0.
   - Construeix una nova imatge de disc `bluesb.dsk` llesta per jugar.

3. **Exportar / Sincronitzar de nou des del joc**:
   Si s'han fet canvis al codi base o es vol regenerar la graella d'edició completa:
   ```bash
   py -3 tools/graphics_tool.py export
   ```\n