# Equivalència i Conversió de Coordenades 1:1 DOS <-> CPC

Aquest document estableix la **fórmula matemàtica oficial i immutable** per traspassar qualsevol posició, entitat o objecte entre la versió original de PC DOS (*The Blues Brothers*, 1991) i el port a Amstrad CPC (Mode 0).

---

## 1. Per què hi havia discrepàncies?

A la versió original de DOS (`tools/blues_dos/bb/`):
1. **L'ancoratge no és el mateix**:
   * A DOS, segons `screen.c:40` (`render_add_sprite(..., x - w/2, y - h)`):
     * `dos_x` és el **CENTRE HORITZONTAL** de l'sprite.
     * `dos_y` és la **BASE DELS PEUS / LÍNIA DE TERRA** (contacte amb el terra).
   * A CPC, en canvi:
     * `cpc_x` és la **vora ESQUERRA** de l'sprite (top-left).
     * `cpc_y` és la **vora SUPERIOR / CAP** de l'sprite (top-left).
2. **L'escala horitzontal de resolució**:
   * DOS corre a 320x200 píxels.
   * CPC corre en Mode 0 a 160x200 píxels (aspect ratio 2:1, 1 byte = 2 píxels).
   * Per tant, 1 píxel Mode 0 de CPC equival a 2 píxels horitzontals de DOS:
     $$\text{ample}_{\text{CPC}} = \frac{\text{ample}_{\text{DOS}}}{2}$$
3. **L'escala vertical**:
   * Les dues versions tenen 200 línies de pantalla i rajoles de 16 línies d'alçada. L'escala vertical és **1:1**.

Si es feia directament $X_{\text{CPC}} = X_{\text{DOS}} / 2$, l'sprite quedava desplaçat $\frac{W_{\text{CPC}}}{2}$ (8 píxels Mode 0 = 4 bytes) cap a la dreta, encastant-se dins les parets.
Si es feia directament $Y_{\text{CPC}} = Y_{\text{DOS}}$, l'sprite quedava enfonsat 32 línies dins el terra.

---

## 2. La Fórmula Oficial de Conversió

Donades les coordenades DOS $(X_{\text{DOS}}, Y_{\text{DOS}})$ d'un objecte i les seves dimensions a DOS $(W_{\text{DOS}}, H_{\text{DOS}})$:

### A) De DOS a CPC (Mode 0)
$$X_{\text{CPC}} = \frac{X_{\text{DOS}} - \frac{W_{\text{DOS}}}{2}}{2} = \frac{X_{\text{DOS}}}{2} - \frac{W_{\text{CPC}}}{2}$$

$$Y_{\text{CPC}} = Y_{\text{DOS}} - H_{\text{DOS}}$$

$$\text{Floor } Y = Y_{\text{DOS}}$$

*Per personatges estàndard ($W_{\text{DOS}} = 32$, $H_{\text{DOS}} = 32$, $W_{\text{CPC}} = 16$ píxels Mode 0):*
$$X_{\text{CPC}} = \frac{X_{\text{DOS}}}{2} - 8$$
$$Y_{\text{CPC}} = Y_{\text{DOS}} - 32$$

### B) De CPC a DOS
$$X_{\text{DOS}} = 2 \cdot X_{\text{CPC}} + \frac{W_{\text{DOS}}}{2} = 2 \cdot X_{\text{CPC}} + W_{\text{CPC}}$$
$$Y_{\text{DOS}} = Y_{\text{CPC}} + H_{\text{DOS}}$$

---

## 3. Coordenades de Rajola (Tile Grid)

* **DOS**: Rajoles de 16x16 píxels $\rightarrow \text{Col} = X_{\text{DOS}} \gg 4, \quad \text{Row} = Y_{\text{DOS}} \gg 4$.
* **CPC**: Rajoles de 8x16 píxels (Mode 0) $\rightarrow \text{Col} = X_{\text{CPC}} \gg 3, \quad \text{Row} = Y_{\text{CPC}} \gg 4$.

Com que $16 \text{ px DOS} / 2 = 8 \text{ px CPC}$, la columna de rajola és **idèntica**:
$$\text{Col}_{\text{CPC}} = \text{Col}_{\text{DOS}}$$

---

## 4. Eina Automàtica (`tools/dos_coord_converter.py`)

Hem creat l'eina `tools/dos_coord_converter.py` per consultar o bolcar qualsevol coordenada sense fer càlculs manuals:

### Convertir coordenades puntuals:
```bash
# Convertir coordenada DOS (X=576, Y=1120) a CPC per a un enemic estàndard (32x32):
py tools/dos_coord_converter.py --dos 576 1120

# Convertir coordenada CPC a DOS:
py tools/dos_coord_converter.py --cpc 280 1088
```

### Bolcar les coordenades exactes de tots els objectes d'un nivell des de `staticres.c`:
```bash
py tools/dos_coord_converter.py --level 0   # Nivell 1: Magasin
py tools/dos_coord_converter.py --level 1   # Nivell 2: Entrepot
py tools/dos_coord_converter.py --level 2   # Nivell 3: Prison
py tools/dos_coord_converter.py --level 3   # Nivell 4: Egout
py tools/dos_coord_converter.py --level 4   # Nivell 5: Ville
py tools/dos_coord_converter.py --level 5   # Nivell 6: Concert
```
