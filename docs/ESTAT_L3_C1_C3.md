# Estat L3 / C1 / C2-C3 (27/10/2026)

Document de treball per no perdre el fil. **No és documentació de disseny
definitiva**; és l'estat real de la feina i dels intents fets.

## 1. Estat estable actual

- Branca `master`: **`04e47ae`**.
- `bluesb.dsk` del projecte principal: **base estable**.
- Verificat visualment amb ZEsarUX:
  - splash de The Blues Brothers;
  - select;
  - mapa;
  - **L1 jugable** (Jake, HUD, nivell).
- `test_gameover_banner_and_splash.py` passa, però **no valida les imatges**;
  les captures `gameover_04_level1_live` poden ser el splash o el mapa.
  No serveix com a prova que L1 hagi carregat.

## 2. On és el WIP

La feina de C1 variable / C2-C3 / L3 **no està a `master`**. Està aïllada:

- Branca: `wip-c2` (`2789210`).
- Stash: `wip C1/C2/L3`.
- Worktree de proves:
  `C:\Users\esquerra\AppData\Local\Temp\opencode\bluesb_wip`.
- Worktree de la base:
  `C:\Users\esquerra\AppData\Local\Temp\opencode\bluesb_base`.

El `master` es va tornar a `04e47ae` i el DSK es va restaurar des de la base.

## 3. Símptomes

### Base

Tot funciona: splash → select → mapa → L1.

### WIP

- Amb la càrrega `LVLCHS` al FRONT abans del splash: **pantalla negra** o
  splash sense avançar.
- Traient/movent aquesta càrrega: el splash torna a sortir, però **no arriba
  a L1**.
- En alguns intents la captura de "L1" és el **mateix splash** o el **mapa**;
  el test donava fals positiu perquè només mirava memòria (`hearts/lives`).
- Amb C2 com a banc de la taula de disc: la màquina es penja. És el motiu pel
  qual el projecte ja evitava C2 en un altre lloc (`OUT(0x7F00,0xC2)`).

## 4. Què s'ha provat

1. **C1 variable per nivell**
   - Cançó → HUD → GAMEOVER → portes → restore → codi → frames.
   - `LevelParams` ampliat a 77 B amb `hud_off`/`gameover_off`.
   - Params a `C1:0x7F00`.
   - Frames a `C1:0x7100` i buffers de fons a `0x7500`.
   - Motiu: Theme2 de L3 (4.670 B) no cap amb el HUD fix a `0x6000`, i les
     sales/restore de L3 són més grans.

2. **C2/LVLCHS**
   - Taula de descriptors de nivell a C2 per treure CHS del resident.
   - Resultat: **C2 penja la màquina**.
   - Provat després amb **C3**. La càrrega a C3 no és la causa del splash negre
     original, però el WIP encara no arriba a L1.

3. **Càrrega LVLCHS al FRONT**
   - Al splash, abans de FSPLASH/FSELECT/FMAP, trencava la imatge.
   - Moguda després del splash: el splash funciona, però el joc no avança.
   - Finalment treta del FRONT i carregada pel GAME.
   - El joc estable no en té cap necessitat.

4. **C1 en paquet separat**
   - Es va separar C1 de WORLD perquè L3 no cabia al scratch FDC de 14.560 B.
   - Es va provar C1 sencer comprimit i després contingut comprimit + codi,
     frames, params i dades en cru.
   - El contingut C1 es carregava, però el **codi C1 quedava a zero** en
     alguns intents.
   - També es va provar de tornar a portar la C1 dins WORLD per L1/L2 i deixar
     el split només per L3.

5. **L1/L2 WORLD amb C1 a dins + taula C3**
   - Objectiu: L1/L2 com la base, L3 amb split.
   - Resultat: el WIP encara es queda al splash; no s'ha pogut verificar L1.
   - Els tamanys de paquet obtinguts eren:
     - `L1WORLD` 14.025 B;
     - `L2WORLD` 14.411 B;
     - límit de scratch: 14.560 B.

6. **L3**
   - `ENEMI3.BIN` generat des de `ENEMI3.SQV`:
     - tipus 3 (policia op2): frames 0-4;
     - tipus 4 (llançador op3): frames 5-11;
     - tipus 6 (gos/walker op1): frames 26-27;
     - cela 13: projectils copiats d'ENEMI1.
   - Spawns L3 per tipus 3/4/6.
   - C6 de L3: 7.419 B de codi, acabava a `0x78FB`.
   - Amb `ENEMY_N=24` C6 arribava a `0x791F` i trepitjava la LUT de `0x7900`.
   - Solució temporal: `ENEMY_N=20`; **es perden 2 policies** dels 11 de L3.
   - Tipus 5/op4 (4 movers) i tipus 23/op11 (2 movers) **no implementats**.
   - Els sprites de movers estan identificats, però són movers, no walkers de C6.

7. **Debug**
   - Es van afegir vores de debug (`0x45` world, `0x46` C1, `0x47` params,
     `0x48` enemy) i bytes d'estat (`0x3D10`/`0x3D11`).
   - Amb això es va veure que el world de L2 tornava, però el C1 no.
   - El debug es va retirar després; el problema del WIP va continuar.

## 5. Mesures de memòria que condicionen el disseny

- Resident `_CODE` base: 14.157 B (marge 31 B).
- WIP amb C3 i sense CHS L1/L2 al resident: 14.202 B (marge 6 B).
- Si es tornen a posar els CHS de L1/L2 al resident: 14.423 B; **no cap**
  (sobrepassa `_DATA`, que comença a `0x3880`).
- Conclusió: per a 6 nivells, els CHS de nivell **no poden viure al resident**;
  cal una taula en banc (C3) o una altra solució equivalent.
- `PAK_SCRATCH_MAX` = 14.560 B. L1/L2 amb C1 a dins hi caben, però L3 no.
- C6: el codi no pot passar de `0x7900`; el pool de fons d'enemics viu a
  `0x7A00..0x7FFF`.

## 6. Punts que encara no estan resolts

1. **No se sap del cert per què el WIP no arriba a L1** quan la C1 va dins
   WORLD per L1/L2 i la taula és a C3. La base equivalent sí que hi arriba.
2. El **FRONT del WIP** encara pot tenir una regressió pròpia:
   - MUSBANK/HUD/GAMEOVER;
   - càrrega de LVLCHS;
   - ordre de càrrega respecte FSPLASH/FSELECT/FMAP.
3. El **C1 split** no està verificat en cap nivell del WIP.
4. **C2 no s'ha de fer servir**; si cal un banc per a la taula, usar C3.
5. L3 encara no té:
   - els 22 enemics complets (n'hi ha 20 per la limitació de C6);
   - els movers op4/op11;
   - verificació de mapa/sales/portes.

## 7. Proper pas recomanat

Fer-ho **molt petit**, sempre sobre la base `04e47ae`:

1. Crear una branca nova des de la base.
2. Aplicar **només** el layout C1 variable, sense C2/C3 ni split.
3. Mantenir L1/L2 amb la C1 dins WORLD i els CHS de sempre.
4. Compilar i verificar **visualment** splash → select → mapa → L1, amb una
   espera llarga i una captura del nivell (no només `test_gameover`).
5. Només si L1 funciona, afegir la taula C3 i verificar de nou.
6. Després separar la C1 només per L3 i verificar L3.
7. Finalment ENEMI3 complet (22) i movers op4/op11.

## 8. Comandes útils

```powershell
# Estat
git status
git log --oneline -3
git stash list
git branch -a

# Base estable
git checkout 04e47ae

# WIP
git checkout wip-c2
git stash apply 'stash@{0}'

# Build
py -3 tools\build.py

# Verificació visual
py -3 tools\test_gameover_banner_and_splash.py
```

No hi ha cap commit nou d'aquesta feina de L3/C1/C2-C3. El `master` i el DSK
del projecte principal continuen sent la base estable.
