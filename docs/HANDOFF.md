# Handoff Global — Blues Brothers CPC (Estat Actual i Guia de Continuació)

> **Document unificat de referència per reprendre el desenvolupament**  
> **Data d'actualització**: 28 d'octubre de 2026  
> **Branques / Repo**: `fix-c1-l3-unlock` (`127e306`) a `https://github.com/Am0rph1s/Bluesb_cpc`  
> **Target**: Amstrad CPC 6128 (128 KB RAM) — Z80, Mode 0 (16 colors), SDCC 4.5.0 + sdasz80, build amb Python 3.

---

## 1. Regles d'Or No Negociables (Llegir abans de tocar codi)

1. **Fidelitat 1:1 a DOS (Prohibit inventar mecàniques)**:
   - Tota física, col·lisió, IA d'enemics, animació i sincronització de nivell prové directament del codi font original de DOS:
     - `tools/blues_dos/bb/` (`level.c`, `objects.c`, `tiles.c`, `game.c`, `staticres.c`)
     - `tools/blues_dos/ja/`
   - Mai ajustar valors a ull ni per intuïció. Per a coordenades, utilitzar la fórmula oficial:  
     $cpc\_x = dos\_x / 2 - w_{cpc} / 2$, $cpc\_y = dos\_y - h_{dos}$ (`docs/DOS_CPC_COORDINATES.md`).
2. **Pressupost de memòria resident (Bloc 0: `0x0000..0x3FFF`)**:
   - `_CODE`: límit màxim a `0x3880`. Actualment a **`0x37D8`** (**168 bytes lliures!**).
   - Qualsevol lògica nova no trivial s'ha de compilar en bancs superiors (C1, C5 o C6), mai al resident.
3. **Regla de commutació de maquinari**:
   - Per cridar codi bancat que escriu a VRAM s'utilitza `0xC0`, mai `0xC1` (`0xC1` mostra la RAM 7 a `0xC000..0xFFFF` i tapa la pantalla; `0xC0` manté la VRAM visible a la pàgina 0).
4. **Idioma de comunicació**: Català.

---

## 2. Comandes Principals de Treball

```powershell
# 1. Regenerar paquets de dades d'un nivell (reordena tilesets, compacta TRIG, genera paràmetres)
py -3 tools/pack_level.py 0               # Nivell 1
py -3 tools/pack_level.py 1 --outdir obj/lvl1  # Nivell 2

# 2. Compilar el joc complet i generar bluesb.dsk
py -3 tools/build.py                      # Build incremental
py -3 tools/build.py -f                   # Rebuild complet (recomprimeix tots els ZX0)

# 3. Validació automàtica en emulador (Smoke test ZEsarUX en mode headless)
py -3 tools/smoke_test.py --skip-run      # Valida sectors DSK, CRCs i arrencada a RAM

# 4. Arrencar ZEsarUX amb connexió remota ZRCP (port 10000)
# Des de tools/ZEsarUX_windows-13.0:
.\zesarux.exe --machine CPC6128 --enable-dsk --dsk-file ..\..\bluesb.dsk --enable-remoteprotocol --remoteprotocol-port 10000
```

---

## 3. Arquitectura de Memòria de 128 KB

```
+---------------------------------------------------------------------------------+
| BLOC 0 (Resident 0x0000..0x3FFF, sempre mapejat a RAM 0)                         |
|  - 0x0100..0x37D8: _CODE del resident (motor genèric, vídeo, ISR, blit)          |
|  - 0x3880..0x3C9D: _DATA resident (globals, s_lv, càmera, estat del jugador)    |
|  - 0x3CA0..0x3FFF: Pila Z80 (lliure ~865 B)                                     |
+---------------------------------------------------------------------------------+
| FINESTRA BANCADA (0x4000..0x7FFF) commutada via 0x7F00                          |
|                                                                                 |
|  Banc C1 (0x4000..0x7FFF): Àudio + HUD + Mecanismes del nivell                  |
|    - 0x4000..0x4C00: Player àudio AKG (només starter/player)                    |
|    - 0x4C10..0x4FA5: HUD blitter ASM (src/hud_bank.c, mogut de resident)       |
|    - 0x4FA8..0x4FE1: _DATA de HUD (src/hud_bank.c)                              |
|    - 0x5000..0x5FFF: Cançó del nivell + GAMEOVER (0x5800)                      |
|    - 0x6000..0x63FF: Tires de renderització HUD Mode 0                          |
|    - 0x6900..0x6948: LevelParams (73 B, struct v2)                              |
|    - 0x6950..0x6DBF: level_code.c (codi ascensors L1 / premses L2)               |
|    - 0x6DC0..0x6DD4: _DATA de level_code (s_mover_dst)                          |
|    - 0x6E00..0x7118: Frames de sprite (ELEV.BIN 224 B / PRESS.BIN 792 B)        |
|    - 0x7200..0x7B48: Buffers de fons (restauració ascensors / premses)          |
|                                                                                 |
|  Banc C4 (0x4000..0x7FFF): Tileset compactat del nivell (fins a 256 tiles)     |
|                                                                                 |
|  Banc C5 (0x4000..0x7FFF): Món del nivell                                       |
|    - 0x4000..: Mapa del nivell                                                  |
|    - Sales d'habitacions interiors                                              |
|    - TRIG compacte (5 B per entrada: tipus, flags, op, b6, avt)                |
|    - 0x6E00..0x7E54: moving_bank.c (física de cintes, àcid, gel, animacions)   |
|                                                                                 |
|  Banc C6 (0x4000..0x7FFF): Enemics i objectes mòbils                            |
|    - 0x4000..: ENEMIn.BIN (frames d'enemics del nivell)                         |
|    - 0x5C00..0x7833: enemy.c (IA, patrulles, trampolins, projectils)            |
+---------------------------------------------------------------------------------+
| VRAM (0x8000..0xFFFF, doble buffer de pàgines 0 i 1 a Mode 0)                    |
|  - Pàgina 0: 0xC000..0xFFFF                                                     |
|  - Pàgina 1: 0x8000..0xBFFF (o segons configuració de scroll en anell)          |
+---------------------------------------------------------------------------------+
```

---

## 4. Estat dels Nivells

### Nivell 1 (`magasin`) — **COMPLETAT I ESTABLE**
- 5 ascensors verticals funcionals amb restauració de fons intacta.
- Cintes transportadores amb animació i empenyiment de velocitat correcta.
- Enemics terrestres (policia, iaies, rockers, grangers, cambrera), peixos a les peixeres i ocells als núvols.
- Caixes agafables i llançables, paraigües, globus, recollida de vinils i pas per habitacions interiors (botiga, cinema, etc.).

### Nivell 2 (`ent` / fàbrica i magatzem) — **EN PROGRÉS (Avançat)**
- **Operatiu**:
  - Mapa i tileset reordenats i empaquetats a `L2WORLD.PAK` i `L2ENEMI.ZX0`.
  - Animació de superfícies d'àcid i cintes transportadores de fàbrica operatives.
  - **Premses hidràuliques**: Màquines de xafament sincronitzades amb `PRESS.BIN` (24×33 px) i buffers a `0x7200`. La col·lisió de memòria prèvia està totalment resolta.
- **Tasques pendents per finiquitar el Nivell 2**:
  1. **Física del gel**:
     - Implementar la inèrcia de lliscament de Jake sobre les superfícies de gel (comportament `op` de gel a DOS `tiles.c` / `player.c`).
     - Revisar les plataformes a la zona de gel on en Jake actualment no pot pujar correctament per alçada de salt o col·lisió.
  2. **Dipòsit d'aigua del sostre / Desguàs**:
     - En Jake no cap pel forat de desguàs del dipòsit d'aigua superior a causa d'una col·lisió de caixa/paret massa estreta o manca de postura ajupida/gateig adequada en aquesta transició.
  3. **Trampolins elàstics**:
     - Validar i connectar el salt elàstic dels trampolins (rutina al Banc C6 `enemy.c` / `enemy_table.s`) un cop es pugui sortir fluidament del dipòsit d'aigua.

---

## 5. Rendiment i Optimització del Framerate (Octubre 2026)

- **Estat del motor**: Sòlid a **25 Hz** (40 ms / 2 VSYNCs) tant en repòs com en **scroll horitzontal**.
- **Fase 1 (Completada - Commit `127e306`)**:
  - `_hud_blit_col` i el bucle de redibuix del HUD s'han mogut del resident al Banc C1 (`src/hud_bank.c`) i reescrits en ASM directe (Mode 0, càlcul incremental de VRAM amb màscara wrap 2 KB).
  - Ha recuperat **388 línies de raster d'espera VSYNC** durant el scroll horitzontal.
  - Ha alliberat memòria resident a `_CODE`: el marge puja a **168 bytes lliures** (`0x0100..0x37D8`, sostre `0x3880`).
- **Fases 2 i 3 (Pausades / Documentades)**:
  - *Fase 2 (Render ràpid de tiles)*: Reordenació del tileset a la càrrega del nivell + blit via `POP`.
  - *Fase 3 (Còpia front->back en caiguda / Split CRTC)*: Queda descartada a curt termini per la complexitat dels sprites superposats i sincronització de raster; només es reconsideraria si la caiguda vertical impactés el gameplay.
- **Sincronització d'habitacions**:
  - Les habitacions interiors corren a **25 Hz exactes** (2 VSYNCs obligatoris a `src/main.c`). La sensació de rapidesa és deguda a la càmera immòbil en pantalla de 40 caràcters i física 1:1 de DOS.

---

## 6. Taula de Paràmetres del Nivell (`LevelParams` v2, 73 bytes)

Ubicada a `C1:0x6900` al paquet i copiada a `s_lv` a RAM resident:
- Offset 34: `start_px` (i16), Offset 36: `start_py` (i16)
- Offset 38: `cam0_x4` (i16), Offset 40: `cam0_row` (i16)
- Offset 42: `chk_px` (i16), Offset 44: `chk_py` (i16)
- Offset 52: `map_w` (u8), Offset 53: `map_h` (u8), Offset 54: `map_rows` (u8)
- Offset 56: `rooms_off` (u16)
- Offset 69: `trig_off` (u16)
- Offset 71: `code_exc_off` (u16) — **Valor contractual obligatori: `0x6950`**

---

## 7. Llista de Documents de Suport

- [`docs/DOS_CPC_COORDINATES.md`](file:///C:/Projects/bluesb_cpc/docs/DOS_CPC_COORDINATES.md): Fórmules de conversió de coordenades 1:1.
- [`docs/PLA_NIVELLS_UNIVERSAL.md`](file:///C:/Projects/bluesb_cpc/docs/PLA_NIVELLS_UNIVERSAL.md): Pla d'extensió universal als 6 nivells.
- [`docs/LEVEL_PACKAGE.md`](file:///C:/Projects/bluesb_cpc/docs/LEVEL_PACKAGE.md): Especificació del format de fitxers `.PAK` i `.ZX0`.
- [`docs/FIX_PREMSES_NIVELL2.md`](file:///C:/Projects/bluesb_cpc/docs/FIX_PREMSES_NIVELL2.md): Anàlisi detallada del bug de memòria de les premses i solucions tècniques.
- [`tools/blues_dos/`](file:///C:/Projects/bluesb_cpc/tools/blues_dos/): Descompilació DOS C de referència absoluta.
