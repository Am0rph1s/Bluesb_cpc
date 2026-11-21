# Arquitectura per als 25 fps en moviment — exploració de l'opció (b)

> **Branca segura**: `fix-c1-l3-unlock` @ `df23378` (HUD split, C7 restore, marge resident 42 B).
> **Data**: 21/11/2026. **Estat**: anàlisi amb les dades mesurades de la sessió.

## 1. On som

| Situació | Frame | Fps |
|---|---|---|
| Quiet / 0-1 enemics sense scroll | 40 ms | 25 |
| 1-2 enemics + scroll | 60 ms (cicle 39/43/46) | 16,7 |
| 5 enemics (clúster) | 80 ms | 12,5 |

Els 25 fps en moviment amb enemics+scroll exigeixen baixar els frames de 60 a 40 ms:
calen **~20 ms** en els frames amb scroll i **~2-9 ms** en els de 39 (perquè entrin al
tier de 40).

## 2. Opció (b): single buffer amb una sincronització nova

### 2.1 El que va mesurar la F1 (`sb-nou-enfoc`)

- Una franja de 512 B de blit cap a la finestra de 20 ms del feix: **16,8 ms** amb
  comptador conservador (marge 3,2 ms; a 59 T/B reals ~10,9 ms de marge).
- Però el **total del frame** (sprites + scroll + HUD + restores) és **~73-83 ms**.
  El feix passa cada 20 ms: el CPU no pot escriure totes les zones sense que el feix
  el caqui. La inestabilitat de la branca antiga (draw order/beam racing) és inherent
  a aquesta relació CPU/feix, no un bug d'ordre.

### 2.2 El que la single-buffer SÍ estalviaria

- La captura de **2 columnes → 1** per frame (~5 ms en els frames de scroll).
- RAM 2 lliure per a cèl·lules d'enemics descomprimides + bbox F3 (~1-2 ms).
- La còpia del HUD **no** desapareix: si el scroll és per CRTC start, el HUD es mou i
  s'ha de copiar (10 ms); fixar-lo amb R4/R6/R7 va ser el que va desestabilitzar la
  branca antiga.
- Els frames de 39 ms (sense scroll) no es toquen: el guany és als de scroll.

**Veredicte**: la nova sync sola deixa els frames de scroll en ~50-55 ms (encara 60) i
no mou els de 39. No arriba als 25, i afegeix el risc de tearing.

## 3. El veritable coll: els bytes de blit

El blit d'enemics és **59 T/byte** (save+mask+OR) i el del jugador igual. Amb 1-2
enemics+scroll el treball és ~50-60 ms. Per baixar a 40 cal **reduir els bytes**, no
reordenar el dibuix.

### 3.1 Mode 1 (4 colors): la meitat de bytes

| Element | Mode 0 (16 colors) | Mode 1 (4 colors) |
|---|---|---|
| Sprite 16 px | 8 B/fila | 4 B/fila |
| Tile 8×8 | 32 B | 16 B |
| HUD 40 columnes | 80 B/fila | 40 B/fila |
| Blit enemic | 59 T/B × 256 B | 59 T/B × 128 B |

El treball de render es **~half**: els frames de scroll ~65 → ~33 ms, els de 39 →
~22. Els 25 fps amb enemics+scroll hi caben de sobres. **Cost**: el joc DOS és de 16
colors; el Mode 1 en té 4. És un compromís visual gran i trenca la fidelitat 1:1 de
l'art (regla del projecte), no la mecànica.

### 3.2 Altres vies (descartades amb dades)

- **Blitter/Placa Plus (GX4000)**: el objectiu és el 6128; no té blitter ni sprites
  hardware. L'emulador és `cpc6128`.
- **Còpia de columnes entre pàgines**: 7,0 ms vs 5,3 ms del render (pitjor).
- **Fusió de probes de tiles**: ~0,4-0,85 ms de bancs en el millor cas; el dedup
  equivalent no va moure el frame (39/43/46 idèntic).
- **F3 bbox**: no cap al paquet L1ENEMI (81 B) i el guany ~20% del blit (~2 ms).

## 4. La decisió

1. **Acceptar el sostre actual**: 25 fps en quiet, 16,7 amb enemics+scroll, 12,5 als
   clústers. És l'estat estable i 1:1 de la branca `fix-c1-l3-unlock`.
2. **Compromís visual Mode 1**: conversió d'art (sprites, tiles, HUD, paletes) a 4
   colors; el render baixa a la meitat i els 25 fps en moviment són abastables. Trenca
   la fidelitat cromàtica del DOS.
3. **Nova arquitectura de sync** (single buffer estable): no redueix els bytes; el
   guany teòric (~5-7 ms als frames de scroll) no arriba als 20 ms que falten i manté
   el risc de beam racing.
