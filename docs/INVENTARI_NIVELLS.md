# Inventari dels 6 nivells (generat per tools/inventory_levels.py)

> Mides **reals** del tilemap: a DOS les habitacions son files del mateix
> array de 128 columnes (`level.c:1135 pos[]`, `resource.c:381 y*128+x`),
> per sobre de l'alcada visible. Per tant `Mapa = ample x max(alcada, pos+10)`.
> `TRIG` = 2.560 B (256 entrades x 10 B). Un banc CPC = 16.384 B.

| Nivell | Nom | Ample | Alt visible | pos sala | Files reals | Mapa (B) | +TRIG (B) | Cap a C5? | Objectes | Ascensors | Portes | Portes amb sala | Cançó (#) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | magasin | 128 | 72 | 74 | 84 | 10.752 | 13.312 | SI | 30 | 5 | 23 | 23 | 1 |
| 2 | ent | 128 | 72 | - | 72 | 9.216 | 11.776 | SI | 19 | 0 | 0 | 0 | 2 |
| 3 | prison | 128 | 72 | 77 | 87 | 11.136 | 13.696 | SI | 28 | 0 | 24 | 24 | 3 |
| 4 | egou | 128 | 61 | 66 | 76 | 9.728 | 12.288 | SI | 31 | 0 | 20 | 10 | 1 |
| 5 | ville | 128 | 95 | 102 | 112 | 14.336 | 16.896 | NO (-512) | 33 | 0 | 2 | 2 | 2 |
| 6 | concert | 128 | 49 | - | 49 | 6.272 | 8.832 | SI | 11 | 0 | 6 | 0 | 3 |

> `Cap a C5?` compara **mapa + TRIG** amb els 16.384 B del banc, **sense**
> comptar-hi el codi del mon (`moving_bank`, 4.548 B avui). Amb el codi, cap
> nivell hi cap (nivell 1: 17.860 B).

## Fitxers DOS al disc (bytes, comprimits tal com son a assets/bbdata)

| Nivell | CK1 | CK2 | SQL (mapa) | BIN (TRIG) | AVT | SQV (enemics) | Total |
|---|---|---|---|---|---|---|---|
| 1 | 12.633 | 13.676 | 7.154 | 2.560 | 3.069 | 14.619 | 53.711 |
| 2 | 13.892 | 10.606 | 5.830 | 2.560 | 2.067 | 12.952 | 47.907 |
| 3 | 15.546 | 13.194 | 7.879 | 2.560 | 3.219 | 11.135 | 53.533 |
| 4 | 13.685 | 12.964 | 6.746 | 2.560 | 2.685 | 7.957 | 46.597 |
| 5 | 13.178 | 13.534 | 8.955 | 2.560 | 2.113 | 12.143 | 52.483 |
| 6 | 9.487 | 10.229 | 4.523 | 2.560 | - | 5.108 | 31.907 |

## Tipus d'objecte per nivell (tipus DOS: quantitat)

- Nivell 1 (magasin): 4:5, 7:5, 8:4, 15:3, 16:1, 17:1, 18:2, 19:3, 20:6
- Nivell 2 (ent): 11:1, 12:7, 13:5, 14:1, 21:2, 22:3
- Nivell 3 (prison): 3:11, 4:4, 5:4, 6:7, 23:2
- Nivell 4 (egou): 25:4, 26:1, 27:1, 28:6, 29:2, 30:2, 31:4, 32:2, 33:1, 34:8
- Nivell 5 (ville): 4:5, 21:2, 35:7, 36:5, 37:6, 38:5, 39:3
- Nivell 6 (concert): 3:6, 4:3, 40:2
