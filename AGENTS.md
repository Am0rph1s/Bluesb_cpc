# Regles del Projecte Blues Brothers CPC

> **Punt d'entrada obligatori**: Per reprendre el projecte o canviar de sessió, consulta abans que res el document unificat [`docs/HANDOFF.md`](docs/HANDOFF.md).

## REGLES OBLIGATÒRIES DE DISSENY I IMPLEMENTACIÓ

### 1. PROHIBIT INVENTAR MECÀNIQUES O COMPORTAMENTS
* Tota mecànica de joc, comportament d'enemics, física del personatge, animacions, col·lisions i regles de nivell **s'han de contrastar sempre i sense excepció amb el codi font original de DOS**.
* El codi font original de referència està disponible localment a:
  - `tools/blues_dos/bb/` (`level.c`, `objects.c`, `tiles.c`, `game.c`, etc.)
  - `tools/blues_dos/ja/` (`level.c`, `staticres.c`, etc.)
* **MAI** implementar o modificar una mecànica basant-se en intuïcions, memòria o suposicions sense haver localitzat i llegit abans la funció original corresponent a la versió DOS.

### 2. FIDELITAT 1:1 A LA VERSIÓ DOS
* Aquest projecte és un port 1:1 fidel al comportament del joc original.
* Les col·lisions de sostre, terra, parets, caixes, globus, paraigües, enemics i projectils han de reproduir fidelment les fórmules, estats i valors del codi DOS.
* Si una mecànica no existeix a DOS (com aturar-se a terra immòbil per un cop al cap), **no s'ha d'afegir mai**.

### 3. VERIFICACIÓ
* Qualsevol canvi en mecàniques ha de ser verificat visualment i funcionalment executant l'emulador ZEsarUX i comparant els resultats amb el comportament DOS.

### 4. CONVERSIÓ DE COORDENADES DOS <-> CPC (PROHIBIT AJUSTAR A ULL)
* Les posicions inicials d'enemics, objectes, plataformes i personatges **s'han de calcular matemàticament** amb la fórmula oficial documentada a `docs/DOS_CPC_COORDINATES.md` o mitjançant l'eina `tools/dos_coord_converter.py`.
* A DOS, les coordenades són el **centre horitzontal** i la **base dels peus**:
  - `cpc_x = (dos_x - w_dos / 2) / 2 = dos_x / 2 - w_cpc / 2`
  - `cpc_y = dos_y - h_dos`
* Mai calcular fent simplement `dos_x / 2` ni moure coordenades manualment sense comprovar `staticres.c`.

### 5. REGLES CRÍTIQUES DE MEMÒRIA I LAYOUT DE DISC (MUSBANK, C1 I FDC)
* **MUSBANK.BIN a C1:0x4000**:
  - L'inici `0x4000..0x4C00` conté el reproductor de so **`player_akg.bin`** (`_akg_init = 0x4009`, `_akg_play = 0x40CE`, `_akg_stop = 0x40BC`). **MAI s'hi ha d'escriure cap dada ni taula**, ja que corrompre `0x4009` fa que `mus_init()` salti a dades invàlides i reinicii al Locomotive BASIC.
  - El fitxer té la mida completa reservada des de `build_music()` (8.238 B / 9 blocs DSK). Mai ampliar-lo a `package()` sobrepassant els blocs AMSDOS prèviament reservats, o `dsk.write_file_data()` desbordarà el fitxer següent (`FSELECT.ZX0`).
* **Taules de sectors dels nivells (`LVLCHS`, 814 bytes)**:
  - Resideixen a l'offset `0x1D00` de `MUSBANK.BIN` (`C1:0x5D00`, darrere `song_intro.bin`).
  - Format actual del pool: `WORLD` 56 B (fins a 28 sectors), `ENEMI` 32 B i `C1` 32 B per nivell.
  - Durant la càrrega del primer nivell, `main.c` (`load_level_file`) copia `LVLCHS` a **`C1:0x7C00..0x7F2D`**.
  - Aquesta zona (`0x7C00..0x7FFF`, 1.024 B) és l'única lliure permanent de RAM 1 per sobre de la còpia mestra de `FDC.BIN` (`0x7800..0x7BFF`) i mai és sobreescrita per cap paquet de nivell ni rutina resident.
* **Depuració amb ZEsarUX ZRCP**:
  - L'ordre `read-memory <addr> <len>` del port ZRCP utilitza un parser decimal (`atoi`). Si s'hi envia una adreça en hexadecimal sense format decimal (`read-memory 3C46 1`), ZEsarUX interpreta l'adreça `3` i llegeix la RST 0. Utilitzar **sempre `%d`** per a les adreces de memòria.
  - Després d'un crash a Locomotive BASIC, `PC` estarà a la Lower ROM (`0x1BD9..0x1E9D`); no confondre adreces de la ROM amb funcions del joc resident.


