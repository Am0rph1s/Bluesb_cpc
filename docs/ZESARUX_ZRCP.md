# Manual Ràpid de Connexió i Depuració amb ZEsarUX (ZRCP)

ZEsarUX inclou el protocol remot **ZRCP** (*ZEsarUX Remote Command Protocol*) per TCP al port `10000` (per defecte), que permet controlar l'emulador, enviar tecles, llegir/escriure memòria, consultar registres, fer captures de pantalla i automatitzar proves tant en **mode silenciós (headless)** com sobre una **sessió gràfica ja engegada**.

---

## 1. Arrencar ZEsarUX amb ZRCP activat

Des de `tools/ZEsarUX_windows-13.0`:

### A. Mode normal (amb finestra i so, per depurar en viu)
```powershell
.\zesarux.exe --machine CPC6128 --enable-dsk --dsk-file ..\..\bluesb.dsk --enable-remoteprotocol --remoteprotocol-port 10000
```

### B. Mode silenciós / headless (sense finestra ni àudio, per a scripts/CI)
```powershell
.\zesarux.exe --vo null --ao null --noconsole --machine CPC6128 --enable-dsk --dsk-file ..\..\bluesb.dsk --enable-remoteprotocol --remoteprotocol-port 10000
```
*(Nota: si el llançament es fa des de Python amb `subprocess.Popen`, convé passar `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL` i `cwd=r"tools\ZEsarUX_windows-13.0"`).*

---

## 2. Connectar-se a una sessió ja engegada

Si ja tens ZEsarUX obert amb `--enable-remoteprotocol --remoteprotocol-port 10000`, et pots connectar des de qualsevol terminal o script Python sense reiniciar-lo.

### Amb el helper del projecte (`tools/zrcp.py`)
```powershell
py -3 -c "import sys; sys.path.insert(0, 'tools'); from zrcp import Zrcp; z = Zrcp('127.0.0.1', 10000); print(z.regs()); z.s.close()"
```
> **Important**: `z.close()` a `tools/zrcp.py` envia la comanda `quit` (que tanca la sessió TCP de ZRCP; fes `z.s.close()` si només vols tancar el socket).

### Connexió manual per TCP (telnet / netcat / PowerShell)
```powershell
# Exemple ràpid amb Python interactiu per enviar comandes puntuals
py -3 -c "
import socket
s = socket.create_connection(('127.0.0.1', 10000), timeout=5)
s.recv(4096)
s.sendall(b'get-registers\r\n')
print(s.recv(4096).decode('latin1'))
s.close()
"
```

---

## 3. Comandes ZRCP més útils

### Estat de CPU i memòria
> **ATENCIÓ (`AGENTS.md`)**: `read-memory` i `write-memory` usen un parser **decimal (`atoi`)**. Passa sempre les adreces en **decimal (`%d`)**, mai en hexadecimal (si envies `3C46`, llegirà l'adreça `3`).

| Comanda | Descripció | Exemple |
| :--- | :--- | :--- |
| `get-registers` | Mostra `PC`, `SP`, `AF`, `BC`, `HL`, `DE`, `IX`, `IY`, etc. | `get-registers` |
| `read-memory <addr_dec> <len>` | Llegeix `<len>` bytes en hex a partir de `<addr_dec>` | `read-memory 14600 4` |
| `write-memory <addr_dec> <val_dec>` | Escriu un byte (0..255) a `<addr_dec>` | `write-memory 14520 1` |
| `get-ocr` | Llegeix el text reconegut de la pantalla (útil per detectar `"Ready"` al BASIC) | `get-ocr` |
| `save-screen <ruta.bmp>` | Desa captura de pantalla actual en BMP (rutes amb `/`) | `save-screen c:/Projects/bluesb_cpc/scratch/cap.bmp` |
| `hard-reset-cpu` / `reset-cpu` | Reinicia la màquina virtual | `reset-cpu` |

### Enviar tecles al CPC
| Comanda | Descripció | Exemple |
| :--- | :--- | :--- |
| `send-keys-string <delay_ms> <text>` | Escriu text (no inclou `Enter` ni `"`) | `send-keys-string 40 bluesb` |
| `send-keys-event <codi> <1\|0>` | Prem (`1`) o allibera (`0`) una tecla | `send-keys-event 128 1` |

Codis de tecla principals (`tools/zrcp.py`, `enum util_teclas` de ZEsarUX):
- `128`: `SPACE`
- `129`: `ENTER`
- `133`: `SHIFT`
- `142`: `LEFT`, `143`: `RIGHT`, `144`: `DOWN`, `145`: `UP`
- `168`: `FIRE`
- `49..54`: tecles `'1'..'6'` (al menú del joc seleccionen nivell `L1..L6` si es mantenen en prémer `SPACE`)
- Per escriure cometes `"` al Locomotive BASIC (`run"bluesb"`): enviar `SHIFT(133)` premut + `'2'(50)` + alliberar `SHIFT(133)`.

---

## 4. Llegir variables del joc en una sessió en viu (`obj/bluesb.map`)

Pots traduir automàticament qualsevol símbol C/ASM des de `obj/bluesb.map` i consultar-lo en calent sense aturar el joc:

```python
import sys, time
sys.path.insert(0, "tools")
from zrcp import Zrcp

def load_map(path="obj/bluesb.map"):
    syms = {}
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) >= 2 and len(p[0]) == 8:
                try:
                    syms[p[1]] = int(p[0], 16)
                except ValueError:
                    pass
    return syms

sym = load_map()
z = Zrcp("127.0.0.1", 10000)

def r8(name):
    return z.read_mem(sym[name], 1)[0]

def r16s(name):
    b = z.read_mem(sym[name], 2)
    v = b[0] | (b[1] << 8)
    return v - 65536 if v >= 32768 else v

print("Registres:", z.regs())
print("Nivell:", r8("_g_map_level") + 1, "px8:", r16s("_s_px8"), "py8:", r16s("_s_py8"))
print("Cam x4:", r16s("_g_cam_x4"), "Cam row:", r16s("_g_cam_row"))
print("Vides:", r8("_g_lives_count"), "Cors:", r8("_g_hearts_count"))

# Exemple: forçar salt de nivell (g_level_complete = 1)
# z.cmd(f"write-memory {sym['_g_level_complete']} 1")

z.s.close()
```

---

## 5. Notes importants per a proves i recàrrega de DSK

- ZEsarUX manté la imatge `bluesb.dsk` **en memòria** un cop oberta: si executes `py -3 tools/build.py` mentre ZEsarUX és obert, la sessió en curs no veurà el nou `.dsk` fins que tornis a inserir el disc des del menú o reiniciïs ZEsarUX.
- Si el CPC cau al Locomotive BASIC per un crash, `PC` estarà a la Lower ROM (`0x1BD9..0x1E9D`).
