# Mapa de Memòria — Blues Brothers CPC (single buffer)

> Branca: `single-buffer-split` · Actualitzat: 17/11/2026
> Aquest és el mapa canònic. Si `HANDOFF.md`, `SINGLE_BUFFER.md` o `LEVEL_PACKAGE.md`
> divergeixen, mana aquest document.

## 1. Resum

El joc no està limitat pels 128 KB totals, sinó per **set pressupostos petits**:

| Pressupost | Límit | Coll actual |
|---|---|---:|
| C0 `_CODE` | 14.592 B (`0x0100..0x3A00`) | ~632 B de marge |
| C0 `_DATA` | 297 B (`0x3A00..0x3B29`) | canari a `0x3C40` |
| RAM2 code | 1.024 B (`0xB800..0xBBFF`) | 988 B (36 B) |
| C6 pak (`L1ENEMI`) | 8.064 B (16 sectors) | 7.988 B (76 B) |
| L2WORLD pak | 13.536 B (`0x8320..0xB800`) | 13.223 B (313 B) |
| C5 codi L1 / L5 | 16.384 B | **236 B / 300 B** |
| C7 | 16.384 B | ~384 B |

## 2. Bancs

### RAM 0 — resident (`0x0000..0x3FFF`)

| Zona | Contingut |
|---|---|
| `0x0038` | vector ISR IM1 (300 Hz) |
| `0x0100..0x38F9` | `_CODE` (14.585 B): `main`, física, sprite, tile blit, HUD wrapper, loader, carry |
| `0x3A00..0x3B29` | `_DATA` (297 B): globals, càmera, estat del jugador |
| `0x3C40` | canari de pila (8 words) |
| `0x3C40..0x3FFE` | pila Z80 (~958 B útils) |

### RAM 1 / C1 — shared + nivell

| Zona | Contingut |
|---|---|
| `0x4000..0x4C00` | player AKG (3.073 B) |
| `0x4C01..0x4E7E` | codi HUD/GAMEOVER dins MUSBANK (637 B) |
| `0x4E7F..0x4FC0` | **lliure** (321 B) |
| `0x4FC0..0x5000` | `_DATA` del HUD |
| `0x5000..0x7680` | imatge C1 del nivell: cançó + HUD strips + GAMEOVER + portes + restore + codi + frames |
| `0x7680..0x76DD` | `LevelParams` v3 + paleta (93 B) |
| `0x7700..` | `_DATA` del codi d'excepcions |
| `0x7800..0x7BFF` | còpia mestra de FDC.BIN (intocable) |
| `0x7C00..0x7F2D` | LVLCHS (814 B) |
| `0x7F2E..0x7FFF` | lliure (210 B) |

> `C1:0x6030` allotja la imatge de `RAM2.BIN` dins MUSBANK. **El primer pak de
> nivell sobreescriu aquesta zona**: la còpia a `0xB800` s'ha de fer abans de
> carregar el WORLD i no es pot repetir des de C1. Vegeu §6.

### RAM 2 — utilitat (`0x8000..0xBFFF`)

| Zona | Mida | Contingut |
|---|---:|---|
| `0x8000..0xB5FF` | 10.752 B | 16 cel·les d'enemic (512 B) + 5 caches H-flip (512 B) |
| gaps `0xX600..0xX75F` | 352 B/bloc | dades fredes (vegeu §3) |
| `0x8760..0x87FF` (+0x800..+0x3800) | 1.280 B | buffer fix del HUD (16 scanlines × 80 B) |
| `0xB600..0xB6FF` | 256 B | LUT de props de tile (`init_tile_props`) |
| `0xB700..0xB73F` | 64 B | bbox d'enemics |
| `0xB740..0xB75F` | 32 B | lliure |
| `0xB800..0xBBDB` | 988 B | codi resident RAM2 |
| `0xBBDB..0xBBFF` | 36 B | lliure |
| `0xBC00..0xBDFF` | 512 B | buffer de sector FDC; en joc allotja la caché de columna (`0xBC00` files 0..9, `0xBD00` files 10..19) |
| `0xBE00..0xBE0F` | 16 B | work FDC |
| `0xBE10..0xBE61` | 82 B | dades de càrrega (§3) |
| `0xBE62..0xBF5F` | 254 B | lliure |
| `0xBF60..0xBFFF` | 160 B | HUD scanline 7 |

> El pak de nivell (`0x8320..0xB7FF`) trepitja tot el que hi ha entre `0x8320`
> i `0xB800`: cel·les, HUD, LUT, bbox i les dades fredes dels gaps. Totes es
> reinicialitzen després de la càrrega.

### C4 — tileset
Usat: L1 14.848 · L2 12.224 · L3 13.440 · L4 13.312 · L5 13.120 · L6 10.112.
Lliure: 1.536 / 4.160 / 2.944 / 3.072 / 3.264 / 6.272.

### C5 — món + codi
Usat: L1 16.148 · L2 15.237 · L3 15.453 · L4 13.500 · L5 16.084 · L6 10.766.
Lliure real (build, `lliure_banc`): **236 / 1.147 / 931 / 2.884 / 300 / 5.618**.
El codi del món (`moving_bank.c` + `bank5_table.s`) és el coll: L1 i L5 no tenen
espai per a res més. No hi afegir codi: moure'l a C6/C1 o optimitzar-lo.

### C6 — enemics / motor
| Zona | Contingut |
|---|---|
| `0x4000..0x4B1F` | taula de cel·les + blocs ZX0 |
| `0x4B20..0x4C1F` | spawn (27 × 9 B) |
| `0x4C20..0x4FFF` | taula de restauració |
| `0x5000..0x51FF` | `_DATA` d'enemics |
| `0x5200..0x78FF` | codi (7.642 B carregat; ~2.342 B lliures) |
| `0x7900..0x79FF` | LUT de flip |
| `0x7A00..0x7FFF` | pool de fons (6 × 256 B) |

### C7 — jugador
Frames 14.400 B (`0x4000..0x7840`), hflip `0x7840`, crate `0x7A20`, paraigua
`0x7C00`, crate bg `0x7E00`, carry bg `0x7E80..` (nou). Lliure ~384 B.

## 3. Dades fredes als gaps de RAM 2

| Adreça | Dada | Mida | Reinicialització |
|---|---|---:|---|
| `0x8600` | `s_carry_bg_c0` | 320 B | scratch; s'escriu abans de cada blit |
| `0x8E80` | `s_lv` | 93 B | `level_params_load()` |
| `0x9600` | `g_mag_elevators` | 80 B | `moving_init()` (ldir 128 B) |
| `0x9E00` | `s_mn_*` | 19 B | `main()` |
| `0x9E20` | `s_cd_*` | 21 B | `carry_draw()` |
| `0x9E40` | `s_rep_*` | 13 B | `s_rep_n = 0` post-load |
| `0x9E50` | `s_carry_drawn` + span/rows/dst | 6 B | post-load / carry |
| `0x9E58` | caché de columna (valid/x4/row/col) | 6 B | invalidada a cada càrrega/repaint |
| `0xBE10` | `s_chs_buf` | 56 B | durant la càrrega (fora del pak) |
| `0xBE48` | `s_lvl_desc` | 8 B | durant la càrrega |
| `0xBE50` | `s_lp_*` | 17 B | `load_package()` |

Comprovacions:
- `0x8600+320 = 0x8740 < 0x8760` (HUD) i `> 0x85FF` (cel·la).
- `0x8E80+93 = 0x8EDD < 0x8F60`.
- `0x9600+128 = 0x9680 < 0x9760`.
- `0x9E00+0x56 = 0x9E56 < 0x9F60`.
- `0xBE10+82 = 0xBE62 < 0xBF60`.

## 4. Paks

| Nivell | WORLD | Marge fins 13.536 | C4 lliure | C5 lliure |
|---|---:|---:|---:|---:|
| L1 | 12.787 | 749 | 1.536 | 236 |
| L2 | **13.223** | **313** | 4.160 | 1.147 |
| L3 | 10.933 | 2.603 | 2.944 | 931 |
| L4 | 12.096 | 1.440 | 3.072 | 2.884 |
| L5 | 11.211 | 2.325 | 3.264 | 300 |
| L6 | 10.932 | 2.604 | 6.272 | 5.618 |

Els sectors AMSDOS (28) són només l'allocació de disc. El que compta és el
payload escrit a `0x8320`, limitat a **13.536 B**.

## 5. Colls d'ampolla i ordre de treball

1. **C5 L1/L5 (236/300 B)** - el codi del món és ple; no hi afegir res.
2. **L2WORLD 313 B** - qualsevol asset nou a L2 necessita reduir una altra secció.
3. **C6 pak 76 B** - el codi d'enemics està al límit de 16 sectors.
4. **C0 `_CODE`** - 632 B de marge (després de moure dades a RAM 2).
5. **C7 384 B** — frames del jugador.
6. **C1 ~900 B** — cançó + codi + frames del nivell.
7. **RAM2 code 36 B** — codi ràpid resident.

## 6. RAM2: còpia única i fragilitat

`load_level_file()` copia `RAM2.BIN` de `C1:0x6030` a `0xB800` només si
`*(u8*)0x7C00 != 'L'`. El primer pak de nivell sobreescriu `C1:0x6030`, així
que **no hi ha una segona font**. Si el codi RAM2 es corromp, el joc executa
brossa. Mesures pendents (Fase 5):
- CRC de `RAM2.BIN` a `disk_tables.h` i comprovació a l'inici de cada nivell.
- Si falla, recarregar `MUSBANK.BIN` des del disc a C1 i tornar a copiar a `0xB800`.
- Substituir el magic `'L'` per un flag resident inicialitzat a zero o un checksum.

## 7. Regles

- El codi nou va a un banc (C1/C6), **no** a `main.c`; C5 (L1/L5) i L2WORLD no tenen marge.
- No afegir res a `0x8000..0xB800` sense comprovar el pak i la reinicialització.
- No usar `0xC2`/`0xC3`.
- El codi que escriu VRAM es crida amb `0xC0`.
- Qualsevol canvi de mida de `main.c` ha de passar `py -3 tools/build.py --check`.
