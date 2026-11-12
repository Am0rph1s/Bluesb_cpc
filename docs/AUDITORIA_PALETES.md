# Auditoria de Paletes Mode 0 — 6 Nivells (16 pens)

> Data: 12/11/2026 · Eines: [`tools/palette_audit.py`](../tools/palette_audit.py) (auditoria),
> [`tools/palette_fit.py`](../tools/palette_fit.py) (ajust) i
> [`tools/refresh_enemy_png.py`](../tools/refresh_enemy_png.py) (reexportació d'enemics).
> Estat actual i regles: [`docs/HANDOFF.md`](HANDOFF.md) §4.1.

---

## 1. Com funciona realment el pipeline de colors

El que sembla "la paleta del nivell" és, en realitat, **la quantització de l'art editat**:

```
graphics_edit/levelN/tileset.png   (master editable, RGB)
        |  graphics_tool.py import: cada pixel -> pen mes proper de la paleta
        v
assets/bbdata/TILESET<N>.BIN       (1 byte = 2 pixels Mode 0, index = pen)
        |  pack_level.py: compacta els tiles usats
        v
assets/bbdata/TILESETC<N>.BIN  ->  C4 del banc
```

Conseqüències **crítiques**:

1. **Un color que no existeix a la paleta es converteix silenciosament** al color més proper.
   No hi ha cap avís: el píxel canvia de color i el joc no ho sap.
2. **La paleta és la font de la veritat dels colors**, no el PNG. El PNG és el master
   *d'edició*; la paleta és el master *de colors*.
3. Per tant, **abans d'editar un PNG amb un color nou, cal afegir un pen nou a la paleta**
   (o acceptar que el color es converteixi en un altre).
4. La paleta de runtime és `LEVEL_PALETTES[nivell]` → `s_lv.palette` → `palette_table`
   (`src/main.c:836`). **Els 16 pens els comparteixen el jugador, el HUD, els enemics
   i l'escena** alhora.

### 1.1 `palette.json` del jugador NO és la paleta de runtime

`graphics_edit/player_jake/palette.json` i `player_elwood/palette.json` només són el
**mapa d'importació RGB → pen** que fa servir `graphics_tool.py import`. La paleta que
es veu al joc és sempre la del nivell. Com que `PFRAMES.BIN` i `ELWOOD.BIN` són
compartits pels 6 nivells, **els pens que facin servir el jugador han de tenir el mateix
color a totes les paletes de nivell**.

---

## 2. Resultat de l'auditoria (12/11/2026)

### 2.1 Pens que fa servir cada asset compartit

| Asset | Pens |
|---|---|
| **Jake** | `0, 1, 4, 5, 11, 12` |
| **Elwood** | `0, 1, 4, 5, 10, 11, 13` |
| **HUD** (logotip + icones) | `0, 1, 2, 4, 7, 11, 12, 13` |
| Enemics | `0, 1, 4, 9, 10, 11, 12, 13` |

El contracte d'identitat que proposa `palette_fit.py` és **`0` = blanc (camisa),
`1` = pell, `4` = blau marí (vestit), `11` = negre**. Són els 4 pens que el jugador
usa a més de 900 píxels cadascun: han de ser idèntics a tots els nivells.

### 2.2 Problemes detectats

| # | Problema | Impacte |
|---|---|---|
| **P1** | **L4 no tenia blau marí a la paleta.** L'art editat de L4 usa `#000080` (8.333 px del tileset + 1.132 d'enemics) i el palette el converteixia a **cian**. | El **vestit d'en Jake/Elwood surt cian** a les clavegueres, i 9.465 px d'art (estructures, canonades) tenen el color equivocat. |
| **P2** | **PNG d'enemics obsolets a L2 i L4.** Els `edit/enemies_cpc.png` eren l'art *anterior* a l'extracció DOS 1:1 del 12/11. Amb `import` l'art DOS es **regressava**. | Regressió silenciosa de l'art 1:1 en cada import. |
| **P3** | **Colors repetits.** L4 tenia només **8 colors diferents** de 16 (L2: 9, L6: 11). | 8 pens malgastats i sense colors nous per a l'edició. |
| **P4** | **Contracte incompleta.** El handoff declarava reservats `0,1,4,11,12`, però el jugador usa també `5` i `10/13`, i el HUD usa `2` i `7`. | Aquests pens canviaven de color entre nivells sense que ningú ho sabés. |
| **P5** | **L6**: 464 px amb colors fora de paleta (magenta, teal, negre suau). | Quantització silenciosa. |

### 2.3 Coherència PNG ↔ binaire (abans de la correcció)

```
AVIS   L2 enemies.png             3821/ 4721 pixels desincronitzats
AVIS   L2 edit/enemies_cpc.png    3821/ 4721 pixels desincronitzats
AVIS   L4 tileset.png             8553/32768 pixels desincronitzats
AVIS   L4 enemies.png             2621/ 3012 pixels desincronitzats
AVIS   L4 edit/tileset_edit.png   8553/32768 pixels desincronitzats
AVIS   L4 edit/enemies_cpc.png    2621/ 3012 pixels desincronitzats
AVIS   L6 tileset.png              464/32768 pixels desincronitzats
AVIS   L6 edit/tileset_edit.png    464/32768 pixels desincronitzats
```

---

## 3. Correcció aplicada (12/11/2026)

### 3.1 Paletes ajustades als colors reals de l'art

`palette_fit.py` construeix, per nivell, una paleta que:

1. fixa els pens del contracte (`0, 1, 4, 11`),
2. **conserva** el color actual de tot pen que l'art fa servir (canvi mínim),
3. dona un pen a **tot color de l'art que abans no en tenia**,
4. assigna colors inedits als pens sobrants → **cap color repetit**.

| Nivell | Canvis | Colors únics |
|---|---|---|
| L1 | `pen3 40→55`, `pen14 5C→58`, `pen15 40→5D` | 13 → **16/16** |
| L2 | `pen5 47→55`, `pen7 47→58`, `pen9 5E→5D`, `pen10 5E→4C`, `pen12 40→45`, `pen14 5C→4D`, `pen15 40→56` | 9 → **16/16** |
| L3 | `pen6 47→55`, `pen15 4B→58` | 14 → **16/16** |
| L4 | `pen4 46→44` (**blau marí**), `pen5 47→57`, `pen8 54→45`, `pen9 40→58`, `pen10 40→5D`, `pen12 40→5C`, `pen13 5E→4C`, `pen14 46→55` | 8 → **16/16** |
| L5 | `pen12 5B→55`, `pen13 54→5D`, `pen14 58→4C`, `pen15 4B→4D` | 12 → **16/16** |
| L6 | `pen2 40→58`, `pen3 40→57`, `pen7 47→5B`, `pen9 5C→55`, `pen12 54→5D`, `pen13 5C→4C` | 11 → **16/16** |

Paletes finals (16 colors inèdits cada una):

```
L1  4B 47 40 55 44 43 5B 4C 57 56 52 54 5F 5C 58 5D
L2  4B 47 40 46 44 55 5E 58 57 5D 4C 54 45 5C 4D 56
L3  4B 47 40 5F 44 43 55 5C 57 56 52 54 5B 4C 5E 58
L4  4B 47 5E 46 44 57 5F 40 45 58 5D 54 5C 4C 55 5B
L5  4B 47 5E 40 44 5C 45 4F 46 58 5B 54 55 5D 4C 4D
L6  4B 47 58 57 44 43 5C 5B 46 55 4E 54 5D 4C 4A 5F
```

Els 4 pens del contracte (`0` blanc, `1` pell, `4` blau marí, `11` negre) són **idèntics
als 6 nivells**.

### 3.2 PNG d'enemics refrescats

`refresh_enemy_png.py` reexporta `enemies.png` des del binaire vigent (i actualitza
l'override `edit/enemies_cpc.png`), de manera que el master editable torna a ser
l'art DOS 1:1 i `import` ja no el regressa.

### 3.3 Reimportació i reconstrucció

`graphics_tool.py import` reimporta l'art amb les paletes noves (el blau marí de L4
deixa de convertir-se en cian) i reconstrueix el disc. Per iterar ràpid sobre un
sol nivell hi ha `tools/reimport_level.py` (mateixa lògica de quantització, però
només dels nivells indicats).

### 3.4 Verificació (12/11/2026)

| Comprovació | Resultat |
|---|---|
| `smoke_test.py --dsk-only` | **OK** — CRC correctes de tots els fitxers del DSK |
| `smoke_test.py --boot-only` | **OK** — `magic=0xB0`, `px8=192`, `py8=8848` |
| `palette_audit.py` | **0** PNG desincronitzats, **16/16** colors únics als 6 nivells |
| `verify_palettes.py` (ZEsarUX, 6 nivells) | paleta a la VRAM **IDÈNTICA** a l'esperada als 6 nivells i contracte `0/1/4/11` **OK** als 6 |

Captures: `scratch/palette_fit/L1..L6_screen.bmp`. A L4 es confirma visualment que
el **vestit de Jake ja és blau marí** (abans cian) i que l'aigua de les clavegueres
recupera el blau marí del master editat.

---

## 4. Eines

```powershell
# Auditoria completa (sincronia, pens per asset, duplicats, coherencia PNG<->binari)
py -3 tools/palette_audit.py

# Proposta de paleta ajustada als colors de l'art (+ previews a scratch/palette_fit/)
py -3 tools/palette_fit.py --preview

# Aplicar la proposta (escriu pack_level.py, graphics_tool.py i els palette.json)
py -3 tools/palette_fit.py --apply

# Reexportar els PNG d'enemics des dels binaris (i l'override edit/)
py -3 tools/refresh_enemy_png.py 1 3 --edit

# Reimportar UN nivell i reconstruir (mateixa logica que graphics_tool import)
py -3 tools/reimport_level.py 3

# Verificar al ZEsarUX que la paleta arriba a la pantalla i que el contracte es compleix
py -3 tools/verify_palettes.py
```

`palette_audit.py --strict` retorna codi d'error si hi ha desincronitzacions, de modo que
es pot afegir al `--check` del build.

---

## 5. Pendent conegut

* Els pens `5`, `10`, `12`, `13` (accent petits de Jake/Elwood: brillos del barret i
  estrelles del "dazed") i `2`, `7` (HUD) **continuen canviant de color per nivell**.
  Són pocs píxels (20–32 per pen) i el HUD, al DOS, també sharing la paleta del nivell
  (a VGA 16 colors el HUD canviava de color entre nivells), però per tenir el jugador
  100% idèntic caldria remapear l'art del jugador a només `0, 1, 4, 11` (pas pendent
  de revisió visual: el brillos del barret passarien a blanc i les estrelles del
  "dazed" a blanc/negre).
* Els enemics comparteixen pens amb el jugador (`9`, `12`, `13`): com que el codi i
  els frames d'enemics són per nivell, això és acceptable, però vol dir que un enemic
  del mateix tipus pot tenir un color lleugerament diferent segons el nivell.
* `palette_audit.py --strict` es pot afegir al `--check` del build perquè cap
  desincronització torni a colar-s'hi en silenci.
