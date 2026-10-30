# Informe de captura de FPS — L1 i L2

Data: 30/10/2026
Fitxer de dades: `scratch/perf.log` (4.320 mostres, 1.800 s)
Monitor: `scratch/perf_monitor.py` (llegeix `s_conveyor_phase`, que avança 1 cada 4 frames)

## Mètode

- `fps = increments(s_conveyor_phase) * 4 / temps`, en una finestra lliscant de ~2 s.
- Cada mostra (4/s) inclou: `px, py, vx, vy, s_on_ground, s_carry_kind,
  s_climb_prev, g_cam_x4, g_cam_row`, si la càmera s'ha mogut i el `level_id`.
- Resolució del càlcul: ~2 fps (la finestra és de 2 s i la fase és entera).
- Només es compten mostres amb joc actiu (`fps > 0`, `level_id` 0/1, `fps < 60`).

## Resultat global

| Mètrica | Valor |
|---|---|
| Mostres vàlides | **3.533** |
| FPS mitjà | **12,2** |
| FPS mediana | **10,5** |
| p10 / p25 / p75 / p90 | 6,3 / 8,4 / 12,6 / 14,7 |
| Mínim / màxim (vàlid) | 2,0 / 33,5 |

### Histograma

```
  0- 5 fps :   24   0,7%
  5- 8 fps :  505  14,2%  ########
  8-10 fps :  829  23,4%  ##############
 10-12 fps :  837  23,6%  ##############
 12-14 fps :  744  21,0%  ############
 14-16 fps :  361  10,2%  ######
 16-20 fps :  157   4,4%  ##
 20-26 fps :   31   0,9%
 26-100 fps:   46   1,3%   (transicions)
```

El 90% del temps el joc està entre **6 i 15 fps** (objectiu: 25).

## Per nivell

| Nivell | n | mitjà | mediana | p10 | p90 |
|---|---|---|---|---|---|
| L1 (id 0) | 2.027 | 12,4 | **12,5** | 8,4 | 16,5 |
| L2 (id 1) | 1.506 | 8,6 | **8,4** | 6,3 | 12,5 |

**L2 va gairebé la meitat de ràpid que L1.**

## Per situació

| Situació | n | mitjà | mediana |
|---|---|---|---|
| Quiet (càmera fixa) | 2.177 | 10,8 | 10,4 |
| Scroll (caminant) | 1.356 | 10,9 | 10,5 |
| A terra | 2.739 | 10,6 | 10,4 |
| A l'aire | 794 | 11,5 | 10,5 |
| Amb caixa | 467 | 10,9 | 10,5 |
| Amb paraigües | 284 | 11,5 | 12,4 |
| Escala / reixa | 86 | 9,4 | 8,4 |

**No hi ha diferència significativa** entre quiet i scroll, ni entre terra i aire,
ni entre portar caixa o no. El cost no depèn de l'escena: domina un cost base.

## Sèrie temporal (mitjana per 2 minuts)

| t (s) | n | mitjà | mediana | nivell |
|---|---|---|---|---|
| 0 | 270 | 15,4 | 12,6 | L1 |
| 120 | 313 | 12,2 | 12,5 | L1 |
| 240 | 314 | 12,9 | 12,6 | L1 |
| 360 | 313 | 10,9 | 10,5 | L1 |
| 480 | 313 | 11,7 | 12,4 | L1 |
| 600 | 305 | 11,7 | 12,4 | L1 |
| 720 | 277 | 10,3 | 10,4 | L2 |
| 840 | 305 | 9,2 | 8,4 | L2 |
| 960 | 310 | 7,4 | 6,3 | L2 |
| 1080 | 301 | 7,1 | 6,3 | L2 |
| 1200 | 313 | 9,3 | 8,4 | L2 |
| 1680 | 193 | 12,9 | 10,4 | L1 (tornada) |

## Valors extrems

- **Pitjors (2-3 fps)**: sempre en càrregues de nivell / respawn (`px=0, py=0`
  o `px=32, py=1106` acabat de reiniciar). No és rendiment del joc sinó la
  transició (FDC + descompressió).
- **Millors (31-33 fps)**: mostres aïllades de L1 cap al minut 1,5; valors
  espuris de la finestra (la fase pot avançar més d'un pas entre lectures).

## Conclusions

1. El joc va a **~10-12 fps** de mitjana, no als 25 objectiu. El cos del frame
   és d'uns **85 ms** (per 25 fps en calen 40).
2. El rendiment **no depèn de l'escena** (quiet/scroll/caixa/aire donen el mateix).
   Hi ha un cost base constant que domina.
3. **L2 és molt més lent** (8,4 vs 12,5 de mediana): els spans animats i les
   premses/ascensors de L2 passen factura al banc C5.
4. El perfil de CPU (mostreig del PC amb `g_bank`) reparteix el temps:
   **C5 42%** (lògica de nivell: `anim_tick_c5`, `moving_bank_update`,
   `moving_bank_find`), **C0 22%** (música ISR, HUD, espera VSYNC),
   **C6 16%** (enemics), **C7 16%** (blits del Jake).

## Següent pas proposat

1. Alliberar espai al resident (moure `carry_draw` a un banc) i activar
   `PROFILE_BORDER` per tenir temps per secció.
2. Optimitzar les seccions més cares (C5 anim tick / find, enemics, HUD).
3. Tornar a capturar amb el mateix mètode i comparar.
