# Regles del Projecte Blues Brothers CPC

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

