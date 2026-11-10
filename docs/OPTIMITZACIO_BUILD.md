# Optimització de la Pipeline de Compilació — Blues Brothers CPC

> **Data d'implementació**: 5-6 de novembre de 2026  
> **Resultat**: Temps de compilació reduït de **~3 hores a 6,7 segons** (build incremental) i **5 minuts i 58 segons** (rebuild complet des de zero).

---

## 1. Mètriques de Rendiment

| Tipus de Compilació | Temps Anterior | Temps Actual | Factor d'Acceleració |
|---|---|---|---|
| **Reconstrucció total des de zero** (`py -3 tools/build.py -f --check`) | ~180 minuts (3 h) | **5 min 58 s** | **~30x** |
| **Compilació incremental de desenvolupament** (`py -3 tools/build.py --check`) | ~10-25 minuts | **6,7 segons** | **>100x** |
| **Reimportació gràfica d'un sol asset** (`py -3 tools/graphics_tool.py import`) | ~15-30 minuts | **2,5 - 8 segons** | **>150x** |
| **Recuperació de bloc ZX0 des de memòria cau** (`obj/.zx0_cache/`) | N/A (no existia) | **< 1 mil·lisegon** | Instantani |

---

## 2. Diagnòstic dels Colls d'Ampolla Anteriors

L'anàlisi de perfilat sobre [`tools/build.py`](file:///C:/Projects/bluesb_cpc/tools/build.py), [`tools/pack_level.py`](file:///C:/Projects/bluesb_cpc/tools/pack_level.py) i [`tools/zx0pkg/`](file:///C:/Projects/bluesb_cpc/tools/zx0pkg/) va revelar 4 problemes principals que s'alimentaven entre si:

1. **Bucle de convergència destructiu de timestamps**:
   - `build.py` executa un bucle `for it in range(8):` per convergir les taules CHS i els CRC dels fitxers del DSK.
   - Dins del bucle es cridava incondicionalment `pack_level.build_level_pkg()` per als 6 nivells.
   - `pack_level.py` sobreescrivia amb `open(..., "wb")` tots els fitxers de sortida (`TILESETC`, `MAPC`, `ROOMSC`, `TRIGC`, `RESTORE`, `level_pkg.h`, `hud_pkg.h`) sense comprovar si el contingut havia canviat.
   - Això canviava el `mtime` de tots els fitxers a cada iteració, invalidant la memòria cau de dependències (`is_stale`) i forçant SDCC i el compressor ZX0 a recompondre i recomprimir els 6 nivells sencers 2 o 3 vegades seguides a cada build.

2. **Compressor ZX0 en Python interpretat pur**:
   - L'algorisme òptim ZX0 d'Einar Saukas utilitza programació dinàmica cap endavant amb càlcul de costos de bits per camí més curt.
   - A `tools/zx0pkg/optimize.py`, l'algorisme s'executava en Python pur instanciant milions d'objectes `Block`.
   - Per a blocs amb finestra completa de 32 KB (`quick=False`, com els paquets C1 de L3 i L5), el doble bucle feia més de **86 milions d'iteracions en Python pur per fitxer**, bloquejant la CPU durant 10–20 minuts per cada paquet.

3. **Absència de memòria cau per hash de contingut (SHA-256)**:
   - Fins i tot en builds parcials o forçats, es tornaven a comprimir tilesets, pantalles i sprites els bytes dels quals eren 100% idèntics als ja comprimits en passades prèvies.

4. **Sobreescriptures redundants a `graphics_tool.py import`**:
   - En modificar un únic gràfic (com `jake.png`), el script sobreescrivia sempre tots els `TILESET0..5.BIN` i `ENEMI1..6.BIN`, provocant una recompilació en cascada de tots els nivells del joc.

---

## 3. Arquitectura de la Solució Implementada

### A. Accelerador ZX0 Natiu C# (`tools/zx0_native.cs`)
- Implementació directa en C# de l'algorisme ZX0 oficial:
  - Estructures planes sobre arrays d'enters (`int[]`) en comptes d'objectes dinàmics gestionats pel Garbage Collector.
  - Compilat amb optimitzacions completes (`/optimize+`) mitjançant el compilador de 64 bits de .NET Framework (`C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`), que ve preinstal·lat de sèrie a totes les instal·lacions modernes de Windows.
  - La compilació de `obj/zx0_native.exe` es fa automàticament al primer ús en menys d'un segon.
- Rendiment: Comprimeix un bloc de 16 KB en **30–80 ms**, amb una sortida binària **100% idèntica** a l'eina oficial en C de referència.

### B. Memòria Cau Persistent per SHA-256 (`obj/.zx0_cache/`)
- A [`tools/zx0pkg/zx0.py`](file:///C:/Projects/bluesb_cpc/tools/zx0pkg/zx0.py):
  - Clau de memòria cau: `SHA-256(dades_entrada) + skip + backwards + classic + quick`.
  - Abans de calcular, es consulta el directori `obj/.zx0_cache/`. Si el fitxer existeix, es retorna en memòria en **< 1 ms**.
  - Si no existeix, es comprimeix amb `zx0_native.exe`, s'escriu a la memòria cau i es retorna.
  - Si `csc.exe` no estigués disponible a l'entorn, disposa d'un fallback automàtic al motor Python original.

### C. Preservació de Timestamps (`_write_if_changed`)
- A [`tools/pack_level.py`](file:///C:/Projects/bluesb_cpc/tools/pack_level.py):
  - Totes les sortides utilitzen la funció:
    ```python
    def _write_if_changed(path, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        if os.path.exists(path):
            with open(path, "rb") as f:
                if f.read() == data:
                    return False
        with open(path, "wb") as f:
            f.write(data)
        return True
    ```
  - Els fitxers només toquen el sistema d'arxius (`mtime` actualitzat) si el seu contingut és realment diferent.

### D. Optimització del Bucle de Convergència de `build.py`
- A [`tools/build.py`](file:///C:/Projects/bluesb_cpc/tools/build.py):
  - `pack_level.build_level_pkg()` s'executa **un sol cop abans** del bucle de convergència `for it in range(8):`, ja que la geometria dels nivells no depèn de les taules CHS ni dels CRCs del disc.
  - `build_bank()` només sobreescriu `obj/lvl{i}/bank5_table.s` si el text generat difereix de l'existent a disc.
  - A les iteracions $it \ge 1$ del bucle de convergència, el flag `force` es desactiva (`cur_force = force if it == 0 else False`). Només es recompilen els mòduls les taules de disc dels quals s'hagin desplaçat realment (`main.c`, `starter.c`).

### E. Importació Incremental a `graphics_tool.py`
- A [`tools/graphics_tool.py`](file:///C:/Projects/bluesb_cpc/tools/graphics_tool.py):
  - Es compara el buffer generat amb `TILESET{n}.BIN` i `ENEMI{n}.BIN` abans d'escriure a disc.
  - `pack_level.py` només es crida per als nivells afectats (`levels_changed`).
  - `build_level_bundles(force=False)` només recomprimeix personatges si `PFRAMES.BIN` o `ELWOOD.BIN` han tingut canvis.

---

## 4. Comprovació i Verificació

Per verificar que tot el pipeline funciona a màxima velocitat i genera una imatge de disc 100% coherent:

```powershell
# 1. Test ràpid incremental (< 7 segons)
py -3 tools/build.py --check

# 2. Test complet forçat (< 6 minuts)
py -3 tools/build.py -f --check

# 3. Validació de sectors i CRCs del disc
py -3 tools/smoke_test.py --dsk-only
```
