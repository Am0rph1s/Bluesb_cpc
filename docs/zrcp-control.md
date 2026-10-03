# Control del CPC des de ZRCP (ZEsarUX remote protocol)

Aquest document explica com interactuar amb el CPC emulat a ZEsarUX per línia
de comandes, sense necessitat de tocar el teclat manualment. És la manera
d'arrencar el joc (`RUN"BLUESB"`), enumerar el disc, prémer tecles, moure
l'sprite, etc. des d'un script Python.

## Per què abans "no funcionava"

Semblava que no es pogués interactuar amb el CPC per consola per dos esculls
tècnics de ZEsarUX/Locomotive BASIC:

1. **Les cometes dobles (`"`, ASCII 34).** A `ascii_to_keyboard_port` de
   ZEsarUX el caràcter `"` no està mapejat directament a la matriu del CPC i el
   parser de ZRCP se'l menja. Enviar `run"bluesb"` fa que el CPC rebi
   `runbluesb` (sense cometes) → `Syntax error`. Cal enviar-lo com
   **Shift (133) + `2` (50)**.

2. **La tecla Intro/Return.** `send-keys-string` només envia text; **no**
   tramet el retorn de carro. Cal enviar l'event de tecla
   **Intro = 129** (`send-keys-event 129 1` / `send-keys-event 129 0`).

## Comandes ZRCP (port 10000)

### 1. `send-keys-string <pausa_ms> <cadena>`
Envia caràcters alfanumèrics (a-z, 0-9, espai).
```
send-keys-string 60 cat
```

### 2. `send-keys-event <key_code> <event>`
La comanda més potent: simula prémer (`event = 1`) o deixar anar (`event = 0`)
qualsevol tecla física o moviment de joystick. Els codis vénen de l'enum
`util_teclas` de `utils.h` de ZEsarUX.

| Tecla / Acció      | Codi | Prémer                    | Alliberar                 |
|--------------------|------|---------------------------|---------------------------|
| Intro (Return)     | 129  | `send-keys-event 129 1`   | `send-keys-event 129 0`   |
| Espai              | 128  | `send-keys-event 128 1`   | `send-keys-event 128 0`   |
| Shift (esquerre)   | 133  | `send-keys-event 133 1`   | `send-keys-event 133 0`   |
| Cursor esquerra    | 142  | `send-keys-event 142 1`   | `send-keys-event 142 0`   |
| Cursor dreta       | 143  | `send-keys-event 143 1`   | `send-keys-event 143 0`   |
| Cursor amunt       | 145  | `send-keys-event 145 1`   | `send-keys-event 145 0`   |
| Cursor avall       | 144  | `send-keys-event 144 1`   | `send-keys-event 144 0`   |
| Joystick Fire      | 168  | `send-keys-event 168 1`   | `send-keys-event 168 0`   |
| Joystick dreta     | 172  | `send-keys-event 172 1`   | `send-keys-event 172 0`   |
| Joystick esquerra  | 171  | `send-keys-event 171 1`   | `send-keys-event 171 0`   |
| Lletres / números  | ASCII| `send-keys-event 50 1`    | `send-keys-event 50 0`    |

(ASCII: `'2'` = 50, `'a'` = 97, etc.)

## Comandes útils addicionals

- `get-registers` — registres de la CPU (útil per saber si el joc corre: PC dins
  del codi, p. ex. el bucle de waitVSYNC).
- `get-io-ports` — estat dels ports (CRTC, PPI, Gate Array, AY).
- `save-screen <file.bmp>` — guarda la pantalla actual.
- `read-memory <addr> <len>` — llegeix memòria (hex).
- `write-memory <addr> <bytes...>` — escriu memòria.
- `write-port <port> <value>` — escriu un port d'I/O.
- `get-visualmem-read-dump` — llista les adreces que llegeix el vídeo.

## Arrencar el joc (`RUN"BLUESB"`)

Al teclat del CPC, les cometes `"` són **Shift + 2**. Seqüència:
```
send-keys-string 60 run
Shift:  send-keys-event 133 1
'2':    send-keys-event 50 1
        send-keys-event 50 0
Shift:  send-keys-event 133 0
send-keys-string 60 bluesb
        (cometes altra vegada: Shift + 2)
Intro:  send-keys-event 129 1
        send-keys-event 129 0
```

## Helpers a `tools/zrcp.py`

S'han afegit com a mètodes de la classe `Zrcp`:

```python
def press_key(self, key, duration=0.12): ...
def type_cpc_quotes(self): ...          # Shift + '2'
def cpc_run(self, program="bluesb"): ...# run"program" + Intro
def cpc_cat(self): ...                  # cat + Intro
def send_string(self, s, delay=60): ...
def send_event(self, key, event): ...
```

Exemple d'ús:
```python
import sys, time; sys.path.insert(0, 'tools')
from zrcp import Zrcp
z = Zrcp(port=10000)
z.cpc_run("bluesb")        # arrenca el joc
time.sleep(10)
print(z.cmd("get-registers"))
z.cmd("save-screen C:/tmp/shot.bmp")
z.close()
```

Moure l'sprite:
```python
z.press_key(z.KEY_RIGHT, duration=0.5)   # cursor dreta
z.press_key(z.KEY_SPACE)                 # saltar
```

## Notes

- El joc carrega els assets per FDC raw, així que entre el `RUN` i que arrenqui
  el mode gràfic poden passar uns segons; convé esperar (p. ex. `time.sleep(10)`)
  abans de capturar o comprovar els registres.
- Per saber si el joc ha arrencat: `get-registers` i mirar que el `PC` sigui
  dins del codi del joc (no al firmware/BASIC).
