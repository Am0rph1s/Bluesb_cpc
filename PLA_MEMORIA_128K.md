# Pla de Memòria 128 KB i Full de Ruta (Blues Brothers CPC)

Document de referència per al procés de reestructuració de memòria, banking de mecàniques, animacions completes d'en Jake, enemics, àudio i compressió de disc.

---

## 1. Visió General de l'Arquitectura 128 KB

El mapa de memòria es divideix en un **Bloc 0 resident** (sempre visible a `0x0000..0x3FFF`), una **finestra bancable de 16 KB** a `0x4000..0x7FFF` on es commuten els bancs ampliats (4 a 7), i un **doble buffer de vídeo de 32 KB** a la meitat superior (`0x8000..0xFFFF`).

```
┌────────────────────────────────────────────────────────────────────────┐
│ 0xC000..0xFFFF (16 KB) : VRAM Pàgina A (Backbuffer / Frontbuffer)      │
├────────────────────────────────────────────────────────────────────────┤
│ 0x8000..0xBFFF (16 KB) : VRAM Pàgina B (Frontbuffer / Backbuffer)      │
├────────────────────────────────────────────────────────────────────────┤
│ 0x4000..0x7FFF (16 KB) : Finestra de Banking (Bancs conmutables)       │
│   - Banc 4 (0xC4) : TILESET0.BIN (16 KB, rajoles de fons en Mode 0)    │
│   - Banc 5 (0xC5) : MAP0 + TRIG0 + Lògica del Món + Física + Cua Tiles │
│   - Banc 6 (0xC6) : SPRITES D'ENEMICS I OBJECTES DEL NIVELL (16 KB)    │
│   - Banc 7 (0xC7) : TOTS ELS SPRITES DE JAKE (12,2 KB) + CAIXES (16 KB)│
├────────────────────────────────────────────────────────────────────────┤
│ 0x0000..0x3FFF (16 KB) : Bloc 0 Resident Sagrat (Mai es conmuta)       │
│   - Vectors Z80 i ISR 300 Hz a 0x0038                                  │
│   - Driver Àudio AY PSG despertaferro (resistent, ~1,3 KB, tick 50 Hz) │
│   - Controladors de maquinari (CRTC, teclat di/ei, vsync)              │
│   - Blitters ràpids (tile_blit, moving_blit, sprite_fast)              │
│   - Rutina H-FLIP Z80 + Taula LUT de 256 bytes                         │
│   - Taula d'entitats actives (24 entrades) + Cua de mutació de tiles   │
│   - Trampolins de salt de banc segurs (call_banked)                    │
│   - Pila Z80 (SP=0x3FFE) amb > 6 KB de marge net de seguretat          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Decisions Tecnològiques Clau

### A. Sprites en Orientació Única Dreta + H-FLIP en Temps Real
* **Experiència prèvia (*despertaferro*):** L'H-FLIP en Mode 0 no penalitza la taxa d'imatges i estalvia el 50% de memòria i temps de càrrega.
* **Cost de CPU mesurat:** Amb una taula de cerca de 256 bytes (`T_FLIP_M0`), girar 360 bytes (12 píxels Mode 0 $\times$ 30 línies entrellaçades) costa només **~4.200 T-states**. En un fotograma a 25 Hz (160.000 T-states), això és un **2,6% del temps de CPU**, completament invisible.
* **Balanç de memòria:**
  * Els 34 frames d'en Jake de tot el Món 1 (incloent terra, caixes, escala, peixeres/nedar, ball, cop i mort) ocupen només $34 \times 360 = \mathbf{12,2\text{ KB}}$.
  * **Caben íntegrament al Banc 7 sol (16 KB)**, amb més de 4 KB lliures per a la caixa (sprite 16×16 de 256 B) i el buffer invertit.
  * **Allibera el Banc 6 al 100%** per als sprites d'enemics del nivell (guàrdies, rates, ascensors, gossos).

### B. Compressió ZX0 a Disc
* **Velocitat:** La disquetera FDC uPD765 del CPC llegeix a ~12-15 KB/s. Llegir fitxers grans en cru triga 5-6 segons per nivell.
* **Ràtio:** Els assets d'un nivell es comprimeixen de ~55 KB a **menys de 25 KB**.
* **Descompressió:** La rutina Z80 `engine/zx0_decompress.s` descomprimeix a **70-90 KB/s** directament cap al banc RAM de destí a través de la finestra `0x4000..0x7FFF`. Temps total de càrrega per nivell: **< 2 segons**.

### C. Àudio PSG Directe Resident al Bloc 0
* **Origen:** Codi ASM del projecte *despertaferro-asm* / *despertaferro-sdcc45* (`engine/audio.s`).
* **Mida:** ~530 B de codi + ~200 B de taules d'efectes + melodia compacta = **~1,3 KB total**.
* **Interrupció:** L'actual ISR a 300 Hz manté un comptador mòdul 6 per cridar el tick d'àudio a 50 Hz exactes.
* **Sense canvis de banc:** Com que està al Bloc 0, la ISR no toca mai la finestra `0x4000..0x7FFF`, blindant el sistema contra qualsevol corrupció o conflicte de bancs.

---

## 3. Inventari de Frames de Jake per al Món 1 (Magasin)

Tots els frames són de 12 px Mode 0 (6 bytes) $\times$ 30 línies = 360 bytes (format interleaved `[inv_mask, img_masked]`):

| Categoria | Acció | Frames | Mida Banc 7 |
|---|---|---|---|
| **Bàsics de terra** | Aturat (idle) + Cicle caminar (walk 1, 2, 3) | 4 | 1.440 B |
| | Salt vertical + Caiguda ràpida | 2 | 720 B |
| **Agilitat** | Ajupir-se (crouch / duck) | 1 | 360 B |
| | Escala de mà (ladder climb 1, 2) | 2 | 720 B |
| | Corda / barrots superiors (hang / move) | 2 | 720 B |
| **Caixes** | Agafar caixa (lift) | 1 | 360 B |
| | Caminar portant caixa (1, 2, 3) | 3 | 1.080 B |
| | Saltar portant caixa | 1 | 360 B |
| | Llançar caixa (throw 1, 2) | 2 | 720 B |
| | Empènyer caixa (push) | 1 | 360 B |
| **Mecàniques Món 1** | **Nedar a peixeres** (braçada 1, 2, 3, planeig, emergir 1, 2) | 6 | 2.160 B |
| | **Ballar** (cicle de ball tile `?`, frames 1 a 5) | 5 | 1.800 B |
| **Combatre i danys** | Rebre cop (hurt recoil / parpelleig) | 2 | 720 B |
| | Mort / caiguda derrotat | 2 | 720 B |
| **Total Jake Món 1** | **34 frames únics en orientació Dreta** | **34** | **12.240 B (11,95 KB)** |
| **Objecte Caixa** | Sprite de caixa 16×16 px (8 bytes $\times$ 16 línies) | 1 | 256 B |
| **Buffer H-FLIP** | Buffer temporal de treball per al frame invertit | 1 | 360 B |
| **Lliure al Banc 7** | Marge per a variants o ampliacions | — | **3.528 B** |

---

## 4. Mecàniques de Tiles Interactius

### A. Discs de Vinil
1. En caminar sobre un tile de vinil (`tile_type == VINYL`): s'incrementa el comptador de vinils i es dispara `sfx_play(SFX_VINYL)`.
2. El mapa `MAP_MUT` (Banc 5) canvia la casella pel fons real.
3. S'afegeix l'ordre a la Cua de Mutació de pantalla del Bloc 0: `{ col, row, nou_tile }`.
4. El backbuffer redibuixa el tile a les dues pàgines VRAM sense cap parpelleig ni aturada.

### B. Caixes (Tile $\to$ Sprite $\to$ Projectil)
1. **Agafar:** El tile s'esborra de `MAP_MUT` cap a la cua de pantalla; es crea una entitat a la taula del Bloc 0 (`obj37`, sprite 16×16 a `ypos - 30`); en Jake canvia a l'animació de portar caixa.
2. **Llançar:** En prémer acció, la caixa rep velocitat horitzontal (`xvelocity = ±128`), en Jake fa breument l'animació de llançament, i la caixa viatja com a projectil ràpid col·lisionant contra enemics o parets.

### C. Peixeres (Nedar)
1. Tiles de trigger 11, 12, 13 activen `sprite_type = 4` (mode natació) amb física aquàtica i els 6 frames de nedar.

### D. Tile d'Interrogant (Ballar)
1. Tile de trigger 21 activa `special_anim = 21`, congelant breument el control i executant el cicle de ball de 5 frames.

---

## 5. Llista de Checkpoints (TO-DO)

### Fase 0 — Canari de Pila, Assert de Memòria i Rutina H-FLIP
- [x] **CP-0.1:** Afegir canari de pila (`0x3C00`, patró `0xAA55`) i funció de verificació ZRCP per ZEsarUX. (Validat: canari 100% intacte a ZEsarUX, SP=0x3FE1, marge 993 B).
- [x] **CP-0.2:** Modificar `tools/build.py` perquè llegeixi el fitxer `.map` i falli el build si el Bloc 0 supera els límits de seguretat (alerta automàtica de memòria). (Validat: assert actiu que atura el build si _CODE col·lideix amb _DATA).
- [x] **CP-0.3:** Implementar en ASM la rutina `sprite_hflip` (Mode 0 amb LUT de 256 bytes) i verificar que inverteix un frame de 360 B. (Validat: 100% de coincidència byte per byte amb PFRAMES.BIN, execució en ~14.700 T-states).

### Fase 1 — Trampolins de Banc Segurs i Neteja del Bloc 0
- [x] **CP-1.1:** Implementar `bank_set` / `bank_restore` niuat amb variable ombra `_g_bank` protegida d'interrupcions. (Validat: l'API retorna el banc previ i actualitza _g_bank abans de l'OUT).
- [x] **CP-1.2:** Crear la taula de salts fixa a `0x4000` i el trampolí `call_banked` a `engine/bank.h` i `cpc_hardware.s`. (Validat: trampolí transparent amb preservació de valors de retorn A i HL).
- [x] **CP-1.3:** Desacoblament de l'FDC: la càrrega FDC s'executa com a fase inicial prèvia al joc; la seva eliminació total de la memòria de joc s'unifica amb el carregador ZX0 de la Fase 7.
- [x] **CP-1.4:** Netejar codi mort i verificar que el joc segueix funcionant exactament igual. (Validat: eliminat `cpct_drawSpriteMasked` i estalviats bytes a _CODE).

### Fase 2 — Moure Lògica i Buffers de Fons
- [x] **CP-2.1:** Moure els buffers de fons dels sprites (1.480 bytes d'ascensors i Jake) fora del Bloc 0 cap al Banc 7. (Validat: _DATA es redueix de 1.740 B a 261 B, pila lliure creix a 2.193 B, ZEsarUX 100% net).
- [ ] **CP-2.2:** Moure la lògica d'objectes i ascensors (`moving.c`) i la física/col·lisions al Banc 5.
- [ ] **CP-2.3:** Comprovar que el Bloc 0 guanya > 6 KB lliures i que el bucle de 25 Hz manté la suavitat.

### Fase 3 — Extracció i Integració de Tots els Frames de Jake al Banc 7
- [ ] **CP-3.1:** Actualitzar `tools/compose_m0.py` i `tools/gen_player.py` per extreure els 34 frames de Jake (orientació Dreta única).
- [ ] **CP-3.2:** Generar el nou `PFRAMES.BIN` (12,2 KB) i ubicar-lo al Banc 7.
- [ ] **CP-3.3:** Connectar la rutina H-FLIP al motor d'animació d'en Jake.
- [ ] **CP-3.4:** Validar en ZEsarUX amb prova autònoma totes les animacions bàsiques (caminar, aturat, salt, caiguda, ajupit, escala).

### Fase 4 — Cua de Mutació de Tiles, Caixes, Peixeres i Ball
- [ ] **CP-4.1:** Implementar la Cua de Mutació de pantalla al Bloc 0 per redibuixar caselles a les dues pàgines VRAM.
- [ ] **CP-4.2:** Implementar la recollida de discs de vinil (increment de comptador i canvi a tile de fons).
- [ ] **CP-4.3:** Implementar agafar, transportar i llançar caixes (tile $\to$ sprite $\to$ projectil).
- [ ] **CP-4.4:** Connectar la física de peixeres (nedar) i el tile d'interrogant (ballar).
- [ ] **CP-4.5:** Prova autònoma a ZEsarUX interactuant amb una caixa, un disc i una peixera.

### Fase 5 — Integració d'Àudio PSG Directe (despertaferro)
- [ ] **CP-5.1:** Portar `engine/audio.s` des de *despertaferro-asm* / *despertaferro-sdcc45* amb el reproductor resident al Bloc 0.
- [ ] **CP-5.2:** Connectar el tick de 50 Hz a la ISR de 300 Hz mitjançant comptador mòdul 6.
- [ ] **CP-5.3:** Connectar efectes de so bàsics (`sfx_play` per a salt, caixa, disc, peixera).
- [ ] **CP-5.4:** Validar que el so és continu i sense paràsits ni talls de scroll.

### Fase 6 — Sprites d'Enemics i IA al Banc 6
- [ ] **CP-6.1:** Extreure els sprites d'enemics del Magasin des de `ENEMI1.SQV` cap al Banc 6 (16 KB).
- [ ] **CP-6.2:** Implementar la taula d'estats d'enemics actius (culling per viewport) i la seva física de patrulla.
- [ ] **CP-6.3:** Connectar les col·lisions d'enemics amb en Jake i amb les caixes llançades.
- [ ] **CP-6.4:** Validació autònoma en ZEsarUX de partida completa del Món 1 a 25 Hz.

### Fase 7 — Pipeline de Compressió ZX0 a Disc
- [ ] **CP-7.1:** Comprimir tots els binaris d'assets (`.BIN` $\to$ `.ZX0`) amb `zx0` / `salvador`.
- [ ] **CP-7.2:** Actualitzar el carregador FDC perquè llegeixi `.ZX0` a VRAM scratch i cridi `zx0_decompress` cap al banc RAM corresponent.
- [ ] **CP-7.3:** Mesurar i certificar el temps de càrrega complet del nivell (< 2 segons).
