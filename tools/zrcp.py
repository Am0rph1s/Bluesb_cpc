import socket, time

class Zrcp:
    def __init__(self, host="127.0.0.1", port=10000):
        self.s = socket.socket()
        self.s.settimeout(10)
        self.s.connect((host, port))
        time.sleep(0.2)
        try:
            self.s.recv(4096)
        except Exception:
            pass

    def cmd(self, line, wait=0.15):
        self.s.sendall(line.encode() + b"\r")
        time.sleep(wait)
        buf = b""
        try:
            while True:
                d = self.s.recv(65536)
                if not d:
                    break
                buf += d
                if buf.rstrip().endswith(b">"):
                    break
        except Exception:
            pass
        t = buf.decode("latin1")
        # Normalitza: el prompt es "<algo>command> " o "<algo>command@cpu-step> "
        # Treu la darrera part "command...> " o "command@...> ".
        for marker in ("command@cpu-step> ", "command> "):
            if marker in t:
                t = t.split(marker)[0]
        return t.strip("\r\n ")

    # ------------------------------------------------------------
    # Interaccio amb el CPC (ZEsarUX utils.h enum util_teclas)
    # ------------------------------------------------------------
    # Llancament del joc a Locomotive BASIC. Problemes coneguts:
    #  - ascii_to_keyboard_port de ZEsarUX no mapeja '"' (ASCII 34):
    #    cal enviar-lo com Shift(133) + '2'(50).
    #  - send-keys-string no envia el Retorn: cal send-keys-event 129.
    KEY_ENTER = 129
    KEY_SPACE = 128
    KEY_SHIFT = 133
    KEY_LEFT  = 142
    KEY_RIGHT = 143
    KEY_UP    = 145
    KEY_DOWN  = 144
    KEY_FIRE  = 168

    def send_string(self, s, delay=60):
        return self.cmd("send-keys-string %d %s" % (delay, s), wait=0.1)

    def send_event(self, key, event):
        return self.cmd("send-keys-event %d %d" % (key, event), wait=0.02)

    def press_key(self, key, duration=0.12):
        self.send_event(key, 1)
        time.sleep(duration)
        self.send_event(key, 0)

    def type_cpc_quotes(self):
        # '"' = Shift + '2'
        self.send_event(self.KEY_SHIFT, 1)
        self.press_key(50, 0.05)          # '2'
        self.send_event(self.KEY_SHIFT, 0)

    def cpc_run(self, program="bluesb"):
        self.send_string("run")
        self.type_cpc_quotes()
        self.send_string(program.lower())
        self.type_cpc_quotes()
        self.press_key(self.KEY_ENTER)

    def cpc_cat(self):
        self.send_string("cat")
        self.press_key(self.KEY_ENTER)

    def read_mem(self, addr, length):
        # read-memory <addr> <len> -> hex pla (sense espais ni adreces)
        out = self.cmd("read-memory %d %d" % (addr, length), wait=0.3)
        # agafa nomes caracters hex
        hexs = "".join(c for c in out if c in "0123456789abcdefABCDEF")
        if len(hexs) % 2:
            hexs = hexs[:-1]
        return bytes.fromhex(hexs)

    def regs(self):
        return self.cmd("get-registers")

    def close(self):
        try:
            self.cmd("quit")
        except Exception:
            pass
        self.s.close()
