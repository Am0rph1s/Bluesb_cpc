# Informe del goal: HUD corromput en scroll

Data: 31/10/2026
Branca: `fix-c1-l3-unlock`
Commit de la correcció: `4d918ac`

---

## 1. Objectiu

Report de l'usuari:

> "la meitat inferior del hud es corromp amb l'scroll, la superior es veu be
> tota l'estona, arregla-ho"

És a dir: la fila **inferior** del HUD (la del logo "BLUES") sortia malament
mentre la càmera es movia; la **superior** (icones de vinils/cors/vides) es veia
bé sempre.

---

## 2. Diagnòstic

### 2.1 Com està construït el HUD

* El HUD són **2 files de caràcters** (20 i 21) dins l'anell de 2 KB.
* Cada fila = **8 scanlines de 80 bytes** a passos de `0x800` (interleavejat CPC).
* El contingut surt de `s_hud_strips[39][24]` (24 B per columna: 12 per a la
  fila 20 i 12 per a la 21), a `s_lv.hud_off` (`0x5658` a C0).
* `hud_blit_columns()` (a `src/hud_bank.c`, ASM) recorre les 40 columnes i pinta
  les dues files: ~1.585 T/columna → **~63.400 T ≈ 15,9 ms per frame d'scroll**.

### 2.2 Què s'ha provat

1. **Descodificar la VRAM** del HUD (`scratch/vram_hud.png`): amb el rebuild
   (`hud_blit_columns`) la VRAM conté les icones i el logo correctes.
2. **Captures en scroll** amb el camí ràpid de còpia actiu
   (`scratch/hud_bottom.png`): la fila inferior surt amb **barres** en lloc del
   logo.
3. **Prova de paritat**: escriure `0xAA` a l'offset de la fila 21 i comprovar
   que la banda apareix a la pantalla → confirma que l'offset calculat és el bo
   (`scratch/patch1_z.png`).
4. **A/B en calent** del camí ràpid (patch `hud_try_copy` → `xor a; ret`):
   14,7 fps amb còpia vs 13,7 fps amb rebuild.

### 2.3 Causa

El **camí ràpid del HUD** introduït al Pas A (`11ac841`): en lloc de
reconstruir el HUD, es copiava el de l'altra pàgina de VRAM
(`hud_try_copy` + `hud_copy_strip`). Amb aquest camí, la fila inferior sortia
corrompuda durant l'scroll. El rebuild és correcte.

---

## 3. Què s'ha fet

S'ha **revertit el camí ràpid** i s'ha tornat al comportament original:

* `src/main.c`: `hud_render(s_back_page, (page_dx != 0 || page_dy != 0))`
  (es torna a forçar el HUD quan hi ha scroll).
* `src/hud_bank.c`: es tornen a fer servir els comptadors per pàgina
  (`s_hud_lives/vinyls/hearts/inst[2]`), sense snapshot ni fast path.
* `src/render.c` i `engine/tile_blit.s`: s'eliminen `hud_try_copy` i
  `hud_copy_strip`.
* `tools/build.py`: `hb_data` torna a `0x4FA8` (el HUD original fa 917 B).

Efecte col·lateral positiu: **+110 B de resident** (`_CODE` `0x38CB`, **213 B**
de marge).

---

## 4. Què ha fallat i per què

| Què | Per què |
|---|---|
| **El camí ràpid (Pas A) corrompia la fila inferior** | El mecanisme exacte **no s'ha aïllat**. La còpia llegeix el HUD de l'altra pàgina a `s_hud_vram_start[page ^ 1]` i n'hi ha prou que aquesta zona no contingui el HUD vàlid (p. ex. perquè la finestra de l'anell s'ha mogut i el contingut antic ha quedat cobert, o per un desajust de la fila 21) perquè surtin barres. El rebuild no té aquesta dependència i és correcte. |
| **Primera mesura del Pas A ("+60%")** | Era un **artefacte**: el jugador es va quedar encallat a `px=76` i el comptador mesurava repòs. L'A/B en calent dona el valor bo: **+1,0 fps**. |
| **Pas C.1 (`HL+3`)** | Amb `cam_row` **senar** les parelles de subfiles són tiles diferents (el bucle del mapa avança la fila en el subfile senar) → gràfics corruptes. A més el guany era ~0,125 ms. Revertit. |
| **Mesura de pila inicial** | El primer watermark omplia la pila **viva** i feia petar el joc. Mesurat bé: **100 B** reals (n'hi ha 494). |
| **Diversos "penjaments" aparents** | ZEsarUX en pausa retorna sempre el mateix PC; cal reiniciar l'emulador després de cada DSK. |

---

## 5. Verificació de la correcció

```
smoke_test --dsk-only : game 32 sectors, 15632 B, CRC 0x961A -> RESULTAT: OK
boot L1 magic=0xB0, caminar dreta/esquerra, magic final=0xB0
canari de pila 55aa55aa55aa55aa55aa55aa55aa55aa (intacte)
captures: fix_q (quiet) i fix_w0..w5 (scroll) -> HUD amb icones + logo correctes
resident: _CODE 0x0100..0x38CB (213 B de marge), _DATA 0x39A0..0x3E10, pila 494 B
C1 HUD: codi 0x4C01..0x4F96 (917 B), dades a 0x4FA8
```

---

## 6. Què queda (rendiment)

No és el sostre. Estat actual: **quiet 16,7-16,9 fps** (3 VSYNCs) i **caminant
~13,7 fps**; el llindar de 25 fps és a 40 ms/frame i el de 16,7 a 60 ms.

| Cost | On | Estat |
|---|---|---|
| **~15,9 ms** | Rebuild del HUD a cada frame d'scroll | és el que s'ha revertit; **no optimitzat** |
| ~14 ms | Dibuix + restauració d'enemics (C6) | pendent |
| ~7,5 ms | `render_column` ×2 per frame (scroll) | pendent |
| ~2 ms | Repintat del conveyor | pendent |
| ~1-2 ms | ISR de música a 50 Hz | baixar a 25 Hz quan el joc vagi a 25 fps |

### Propostes, per guany/risc

1. **Optimitzar el rebuild del HUD** (segur, sense còpia): saltar `tile*24` per
   a les columnes amb tile 0, desenrotllar `hb_blit6$` i portar els offsets en
   registres → **~2-3 ms**.
2. **Enemics (C6)**: mesurar per secció amb `PROFILE_BORDER` i atacar el
   dibuix/restauració → fins a **~5-7 ms**.
3. **`render_column`**: parelles de columnes (Pas C.2) → ara el resident té
   213 B i hi cabria (~0,6-1 ms).
4. **Música**: quan el joc arribi a 25 fps, baixar el tick de la ISR a 25 Hz.

Objectiu realista: **25 fps en quiet** (<40 ms) i **16,7 fps caminant**
(~55-60 ms).
