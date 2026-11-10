# Edició de Gràfics i Paletes - Blues Brothers CPC

Aquesta carpeta conté tots els gràfics dels 6 nivells, pantalles fixes i personatges protagonistes (Jake i Elwood), preparats per ser editats amb qualsevol editor (Aseprite, Photoshop, GIMP, GrafX2, etc.).

## Estructura per subcarpetes

### 1. Personatges protagonistes:
- `player_jake/`: Jake Blues (`jake.png`, **96 x 150 px**, graella de 6x5 cel·les de 16x30 px, RGBA transparent). Inclou `frames_guide.txt` i `palette.json`.
- `player_elwood/`: Elwood Blues (`elwood.png`, **96 x 150 px**, graella de 6x5 cel·les de 16x30 px, RGBA transparent). Inclou `frames_guide.txt` i `palette.json`.

### 2. Nivells de joc:
- `level1_magasin/` (Magatzem)
- `level2_factory/` (Fàbrica)
- `level3_prison/` (Presó)
- `level4_sewers/` (Clavegueres)
- `level5_city/` (Ciutat i teulades)
- `level6_concert/` (Concert final)

A cada carpeta de nivell trobaràs:
- `map_full.png`: **Mapa complet del nivell muntat** (**2048 x H px**, proporció 4:3 de pantalla CPC). Format Mode 'P' (16 colors) amb la paleta del nivell. **Ideal per provar paletes** en viu!
- `map_mode0.png`: El mateix mapa complet en resolució nativa Mode 0 (**1024 x H px**, tiles de 8x16 px).
- `tileset.png`: Graella de **16x16 tiles** (total 256 tiles, cadascun de 8x16 píxels). Mida imatge: **128 x 256 px**. Mode indexat (16 colors) amb la paleta exacte del nivell.
- `enemies.png`: Graella de **4x4 cel·les** d'enemics (total 16 cel·les, cadascuna de 16x32 píxels). Mida imatge: **64 x 128 px**. Els píxels transparents són canal Alpha transparent (o fons buit).
- `palette.json`: Descripció dels 16 colors (pens 0..15) emprats pel nivell.

### 3. Pantalles fixes:
- `screen_splash/`: Pantalla de títol / logo del joc (`splash.png`, **160 x 200 px**, Mode 0 indexat 16 colors) + `palette.json`.
- `screen_map/`: Pantalla del mapa de la ciutat entre nivells (`map.png`, **160 x 200 px**, Mode 0 indexat 16 colors) + `palette.json`.

## Com modificar la paleta
- Pots canviar els colors directament a la paleta del programa d'edició (o modificant `palette.json`).
- Consulta `CPC_27_COLORS_REFERENCE.json` per conèixer els 27 colors que la màquina real CPC pot reproduir. Quan importem els gràfics, cada color RGB s'ajustarà automàticament al color CPC equivalent més proper.

## Com integrar els canvis al joc
Quan acabis d'editar i desis els PNGs, avisa'm al xat o executa:
```bash
py -3 tools/graphics_tool.py import
```
L'eina reconstruirà automàticament els fitxers binaris, empaquetarà els nivells, recomprimirà pantalles ZX0, actualitzarà Jake i Elwood al Banc 7 i generarà el disc `bluesb.dsk` amb els teus canvis integrats 100%!
