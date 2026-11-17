# Incidències de test 1:1 (sessió 13/11/2026)

Flux: l'usuari prova el nivell i descriu el que falla; aquí s'anota la causa
tècnica contrastada amb el DOS abans d'aplicar cap canvi.

---

## BATCH 1 aplicat (14/11/2026)

1. **Bazuka: tret horitzontal** (`src/enemy.c`). El DOS, a `unk42 == 2`
   (`level.c:1430-1435`), sobreescriu el `yvelocity = 64` inicial amb
   `yvelocity = 0` i `yacc = 0`: el coet surt **horitzontal**. El hitbox passa
   a la caixa DOS tipus 2 (10 px): base a `peus - 18`, top a `peus - 28`
   (`g_en_y + 4`). Jake dret (26 px) el rep; ajupit (14 px) passa per sota.
2. **Bola del presidiari** (`src/enemy.c`): la cela correcta es la **13**
   (la 15 era buida, per aixo el projectil era invisible). Base a `peus - 3`
   (`level.c:1400`, `grab_type 12`), top `peus - 12` (files 9..17 de la cela).
3. **Rata boja**: eliminat el teletransport `bc_a +/- 80` de `en2_room_exit`.
   Deixava la rata dins una paret i el patrol girava `dir` cada frame. Ara es
   queda al seu punt de patrol valid.
4. **Guardia del slot 27 (L3)**: `ENEMY_N` 26 -> **27** i slots de fons
   empaquetats en 1 byte (`slot_bits`) perque els 512 B de `_DATA` del C6
   segueixin cabent (493 B). `gen_enemy_spawn.py` ja no descarta el t3 de
   (800,864) -> CPC (392,832).
5. **Respawn de mig nivell**: en tocar el checkpoint es desa `s_px8/s_py8` i
   la camera reals (`g_chk_*`); el respawn els restaura en lloc del
   `restart_*` estatic (L3 336,816) que quedava dins el mur.
6. **Items de les sales**: `check_room_bonus` ara prova les **dues columnes**
   de Jake (16 px) i la **fila dels peus** (`+30`), com `tiles.c` (`ypos16` i
   `_di`). Abans nomes mirava la columna central i 3 files des de `+28`.
   A mes, `pack_level.py` detecta el **tile real** de cada sala pel trigger
   (`add_vinyls` / `instrument`): L1 208, **L3 0xB5 (compact 161)**, L4
   **233** (abans s'assumia 208 i no es podia agafar), L5 24/65.
   `tile_empty` passa a ser el `bg_tile` del trigger (L1 20, L3 15, L4 19),
   com `do_level_update_tile(p[2])` del DOS.
   A L3 les **3x2 rajoles de discs** de la sala 3 (cols 64..66, files 80..81)
   son el tile 0xB5 = **+1 vinil**; el **"?"** de sobre la porta (col 68,
   fila 81) es el tile 0x90 = **+50 vinils + popup** (encara pendent: el
   camp `tile_vinyl` es unic i el resident nomes suma 1).

---

## 1. Rata (L3, tipus DOS t6 / kind 24): hitbox massa gran

**Què es veu**: la rata toca Jake quan és sobre una taula; les caixes
llançades no li passen per sobre com al DOS.

**DOS (referència)** — `tools/blues_dos/bb/staticres.c:962-971`:
- `level_obj_w[]` / `level_obj_h[]` són **per tipus DOS**:
  - rata `t6`: **w=10, h=10**
  - caixa `t2`: **w=8, h=10** (per això la caixa té la mateixa alçada que la rata)
  - Jake `t0/t1`: w=10, h=**26** (14 ajupit; `level.c:1603-1605`)
- La col·lisió (`level.c:1595-1682`) compara **peus + alçades**:
  `rata.top = rata.ypos - level_obj_h[6]`, `Jake.top = Jake.ypos - level_obj_h[0]`;
  hi ha toc si `rata.top <= Jake.ypos` i `Jake.top <= rata.ypos`.

**Port** — `src/enemy.c`:
- `en2_check_player_hit` (línia 680): `he = 10` per `kind 24` — **l'alçada ja és
  la correcta**.
- Però el test vertical (línia 681) és una aproximació:
  `(u16)((e->y8>>3) - bc_b + he - 4) < (u16)(26 + he)`
  No equival al test DOS de peus+alçades; el resultat depèn de la conversió
  top/peus (`e->y8` i `s_py8` són el **cap**, el DOS `ypos` és la **base**),
  i per això falla en plataformes/taules.
- `en2_check_crate_hit` (línies 696-697): caixa **fixa 32×48**; el DOS fa
  **8×10 (caixa) vs 10×10 (rata)** → el port detecta xocs que al DOS no hi són.

**Direcció de correcció** (pendent d'aplicar):
- Implementar el test DOS de dues caixes amb `level_obj_w/h` per tipus DOS.
- Guardar el **tipus DOS** (o w/h) a `Spawn`/`gen_enemy_spawn.py`, o una taula
  `kind -> w/h` a `enemy.c`.
- Usar l'alçada de Jake **26** (14 ajupit) i la caixa **8×10** a `en2_check_crate_hit`.
- Revisar la conversió top/peus (el port desa el cap; el DOS compara bases).

---

## 2. Bazuka (L3, t5 / kind 26): col·locació incorrecta — CONFIRMAT, PENDENT DE FIX

**Estat**: confirmat per l'usuari. El bazuka **no queda on toca**; no es tanca
com a correcte. S'ha de corregir la col·locació visual (y/ancoratge/capa) fins
que coincideixi amb el joc original. No es pren el `level_ypos` com a excusa.

**Cas slot 7**: sobre la barana, desplaçat respecte l'original.
Captura: `scratch/user_bazuka.png`.

**Cas slot 9 (#4)**: queda **a l'aire** sobre el blau. Captura:
`scratch/user_bazuka2.png`.

**Causa trobada (14/11)**: el tile dels peus es **foreground** al mapa DOS.
- Slot 7: `MAP2` a (col 84, row 16) = **0x9A** = `0x80 | 0x1A`.
  El DOS dibuixa **dues capes**: la base `0x1A` (CK1) i el foreground `0x9A`
  (CK2) amb el pen 0 (blau) transparent. El port només dibuixa el tile CK2
  `0x9A`, que te el **blau de fons** i la barana; falta la base CK1 (terra).
  Per aixo el bazuka queda sobre el blau.
- Mateix cas a slot 14 (`0x82`) i slot 22 (`0x84`): tots son foreground.
- **Fix pendent**: guardar/dibuixar la capa base CK1 i, despres dels enemics,
  fer un **blit emmascarat** del tile foreground CK2 (nomes els pixels no
  transparents). Es un canvi de renderer, no de coordenades de spawn.
- **Batch 1 (parcial)**: `enemy.c` pinta la base CK1 sota els peus abans de
  l'enemic per als foreground de L3 `0x9A->0x1A`, `0x82->0x02`,
  `0x84->0x04` (slots 7, 14 i 22). La barana foreground (CK2) encara no es
  redibuixa a sobre; queda pendent el blit emmascarat.
  El slot 9 (tile `0x0F`, gris solid) no es foreground; es deixa igual.

---

## 5. Respawn de mig nivell (checkpoint): Jake dins el mur - APLICAT (batch 1)

**Estat actual a l'emulador**:
- `s_lv.chk_px = 160`, `s_lv.chk_py = 784` (L3).
- En respawnar: `s_px8 = 1280` (x=160), `s_py8 = 6288` (top y=786).
- Resultat: Jake **dins el mur de maons, a mitja altura**. Captura:
  `scratch/user_respawn.png`.

**Causa probable**:
- El pack genera `chk_px = (DOS_RESTART_X - 16) / 2`,
  `chk_py = DOS_RESTART_Y - 32` a partir del `restart_*`
  (L3: `336,816` → `160,784`). Al DOS els `restart_xpos/ypos` són
  `static const` (`level.c:104-105`); no hi ha checkpoint dinàmic.
- El respawn no fa el mateix ajust que l'inici de nivell: el start
  (`start_py = 146`) acaba a `s_py8 = 162` (+16 px, snap a terra); el respawn
  només suma +2 px. Per això queda dins el mur en lloc de a terra.

**Fix pendent**:
- Fer el mateix snap a terra/conversió que l'inici de nivell (i comprovar el
  tile del punt de respawn).
- Revisar si el punt `restart_*` (336,816) és el correcte per a L3 o si cal el
  del checkpoint real que veu l'usuari.

---

## 6. Falta un guardià amb escut (L3) a la cel·la - APLICAT (batch 1)

**Estat**: a la cel·la de la captura (`scratch/user_room6.png`, Jake a
`382,850`) hi falta el guardià amb escut.

**Quin objecte és**: el `t3` del **slot 27** de L3: DOS `(800,864)` →
CPC `(392,832)`, exactament a la cel·la on és Jake.

**Causa**: L3 té **28 objectes** i `ENEMY_N = 26`. `gen_enemy_spawn.py`
prioritza `t23 > t5 > t4 > t6 > t3` i deixa fora el guardià del slot 27 (i el
`t23` del slot 10, que és a les sales). El jugador veu la cel·la sense guardià.

**Fix pendent**:
- Apujar `ENEMY_N` a **27/28** (spawn `27×9 = 243` B o `28×9 = 252` B; cap a
  `0x4C20` encara hi cap) i `s_enemies` a 27/28; o ajustar la prioritat per no
  deixar fora el slot 27.
- Actualitzar `build.py` (assert `26×9`) i el C6; comprovar l'espai de codi
  (C6 a 78 B lliures) i el layout de 0x4B20..0x4C20.

---

## 7. A les habitacions no es poden agafar els items (dibuixats però desactivats) - APLICAT (batch 1; pendent confirmar quins items)

**Estat comprovat** (`scratch/user_room7.png`): `s_in_room=1`, `px8=4282`,
`py8=10640` → columna `67`, fila dels peus amb `+28` = `84`.
- La fila real del terra és la `85` (`(py>>3 + 32) >> 4`).
- Les cel·les comprovades pel codi (84/83/82, col 67) tenen tile `0x22`; no
  són l'item.
- `tile_vinyl = 182 (0xB6)`, `tile_instr = 148 (0x94)`, `tile_empty = 90`.
- `room_cols = 20`, `room_rows = 10`, `room_total_cols = 120`,
  `room_rowoff = [0,120,240,...,1080]`, `rooms_off = 0x6400` (C5).

**Causa**: `check_room_bonus` (`main.c:488`) només mira:
- **una columna** (la central del jugador), però el jugador fa **2 columnes**
  (16 px); els items de la sala queden sovint a la columna adjacent;
- **3 files per sobre dels peus** (`((py>>3)+28)>>4`), però els items de terra
  són a la **fila dels peus** (`((py>>3)+32)>>4`).

Per això el `render_room` els dibuixa però la col·lisió no els detecta.

**Fix pendent**: provar la fila del terra i les **2 columnes** del jugador (o
la caixa DOS completa) a `check_room_bonus`.

---

## 8. (a) Rata boja en entrar/sortir de la cel·la; (b) bola del presidiari al túnel - APLICAT (batch 1)

Captura: `scratch/user_tunnel.png` (rata a dalt a l'esquerra, Jake a baix, el
presidiari i la bola petita al centre).

**(a) Rata pivotant al mateix punt en entrar/sortir de la sala**
- `en2_room_exit` reposiciona els enemics amb `e->x = bc_a ± 80` i
  `e->dir = (g_en_dx >= 0) ? 1 : -1` en sortir de la sala.
- El `en2_update` de patrol torna a girar el `dir` cada frame contra la paret
  (el `dir` queda alternant) → el sprite pivota sense moure's.
- DOS: `object_func_op1` (`objects.c:16`) només gira quan
  `triggers_get_tile_type(xpos16 + 2 - facing_left*4, ypos16) == 1`, posa
  `xvelocity = 0`, i la `x` es mou amb `direction_lr`.

**(b) Túnel: presidiari de bola amb projectil invisible i massa alt**
- El presidiari (slot 28, `kind 17` + `throw_cell 10`) **hi és** (x=384,
  y8=8704 → 1088).
- La bola és la **cel·la 15** (frame SQV 22): es dibuixa amb el **`+4`** dels
  projectils de 8 px i el contingut a la **meitat dreta** de la cel·la → només
  se'n veuen ~4 px (sembla invisible).
- A més surt a `g_en_y + 25` = **peus − 7**; al DOS (`do_level_update_projectile`,
  el presidiari/t23) surt a **`ypos − 3`** (peus − 3), arran de terra.
- Fix: cel·la 15 amb el contingut a l'esquerra + dibuix amb `h_off = 0`
  (16 px de bola) i `y8` a `peus − 3`/el valor DOS, amb caixa baixa.
- (a) repassar el `room_exit`/patrol de la rata contra `object_func_op1`.

---

## 3. Bazuka: el tret va HORITZONTAL (no diagonal) i s'evita ajupint

**Comportament real del joc original (referència de l'usuari, 100%)**:
- El projectil surt **horitzontal**, no en diagonal.
- Surt a l'alçada de l'espatlla: Jake **dret** el rep; **ajupit** passa per sobre.

**Port (abans)**:
- `src/enemy.c`: per `kind 26` feia `s_proj.vy = 64` → el projectil baixava
  en diagonal.
- Alçada: el projectil sortia a `(top + 14)` = `peus - 18`, però aquest és la
  **base** del projectil DOS (`ypos - 18`), no el top. El port hi posava el
  top i la caixa quedava 10 px massa avall.

**Fix aplicat (batch 1)**:
- `s_proj.vy = 0` (el DOS a `unk42 == 2`, `level.c:1430-1435`, posa
  `yvelocity = 0` i `yacc = 0`: el 64 inicial queda sobreescrit).
- Top a `peus - 28` (`g_en_y + 4`), `ht = 10` (caixa DOS tipus 2 `8×10`).
  Així el projectil ocupa `peus - 28..peus - 18`: Jake dret (`h = 26`) el rep;
  ajupit (`h = 14`, top `peus - 14`) passa per sota.
