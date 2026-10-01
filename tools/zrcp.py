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
