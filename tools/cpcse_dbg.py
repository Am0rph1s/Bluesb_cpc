"""Client Python per a l'API externa de CPCSyntaxError (port 6128).

Permet automatitzar arrencada, carrega de DSK/simbols, lectura/escriptura de
memoria i registres, breakpoints condicionals, watchpoints, avanç per frames
i captures de pantalla.
"""
import json
import os
import re
import socket
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
CPCSE_DIR = os.path.join(HERE, "CPCSyntaxError-win64-v0.17.0")
CPCSE_EXE = os.path.join(CPCSE_DIR, "cpcse.exe")
CPCSE_CTL = os.path.join(CPCSE_DIR, "cpcse-ctl.exe")
DSK = os.path.join(PROJ, "bluesb.dsk")
SYM_PATH = os.path.join(PROJ, "obj", "bluesb.sym")
DEFAULT_PORT = 6128


def export_symbols(out_path=SYM_PATH):
    """Genera un fitxer .sym (format `nom EQU 0xXXXX`) des d'obj/bluesb.noi i obj/main.rst."""
    syms = {}
    noi = os.path.join(PROJ, "obj", "bluesb.noi")
    if os.path.exists(noi):
        with open(noi, "r", errors="replace") as f:
            for line in f:
                m = re.match(r"DEF\s+([A-Za-z_][A-Za-z0-9_]*)\s+0x([0-9A-Fa-f]+)", line)
                if m:
                    name, val = m.group(1), int(m.group(2), 16)
                    if not name.startswith(("l__", "s__", ".")):
                        syms[name] = val

    rst = os.path.join(PROJ, "obj", "main.rst")
    if os.path.exists(rst):
        with open(rst, "r", errors="replace") as f:
            for line in f:
                m = re.match(r"([0-9A-F]{8})\s+\d+\s+(_s_[A-Za-z0-9_]+|_[A-Za-z0-9_]+)::?$", line.strip())
                if m:
                    val, name = int(m.group(1), 16), m.group(2)
                    syms.setdefault(name, val)
                else:
                    m2 = re.match(r"[0-9A-F]{8}\s+\d+\s+(_[A-Za-z0-9_]+)\s*=\s*0x([0-9A-Fa-f]+)$", line.strip())
                    if m2:
                        syms.setdefault(m2.group(1), int(m2.group(2), 16))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        for name in sorted(syms):
            f.write(f"{name} EQU 0x{syms[name]:04X}\n")
    return syms


class CpcseClient:
    def __init__(self, port=DEFAULT_PORT, timeout=15.0):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(timeout)
        self.s.connect(("127.0.0.1", port))
        self._buf = b""
        self._next_id = 1

    def cmd(self, payload):
        if isinstance(payload, str):
            line = payload.strip()
            self.s.sendall(line.encode("utf-8") + b"\n")
            return self._read_json()
        req = dict(payload)
        rid = req.setdefault("id", self._next_id)
        self._next_id += 1
        self.s.sendall((json.dumps(req) + "\n").encode("utf-8"))
        while True:
            msg = self._read_json()
            if msg.get("id") == rid or "id" not in msg:
                return msg

    def _read_json(self):
        while b"\n" not in self._buf:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("CPCSyntaxError API tancada")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8", errors="replace"))

    def status(self):
        return self.cmd({"cmd": "status"})

    def pause(self):
        return self.cmd({"cmd": "pause"})

    def run(self, addr=None):
        req = {"cmd": "run"}
        if addr is not None:
            req["addr"] = addr
        return self.cmd(req)

    def reset(self, run=True):
        return self.cmd({"cmd": "reset", "run": 1 if run else 0})

    def regs(self):
        return self.cmd({"cmd": "regs"})

    def read(self, addr, length):
        r = self.cmd({"cmd": "read", "addr": addr, "len": length, "format": "bytes"})
        if not r.get("ok"):
            raise RuntimeError(r)
        return bytes(r["bytes"])

    def r8(self, addr):
        return self.read(addr, 1)[0]

    def r16(self, addr):
        b = self.read(addr, 2)
        return b[0] | (b[1] << 8)

    def r16s(self, addr):
        v = self.r16(addr)
        return v - 65536 if v >= 32768 else v

    def write(self, addr, data_bytes):
        return self.cmd({"cmd": "write", "addr": addr, "data": list(data_bytes)})

    def bp_add(self, addr, condition=None):
        req = {"cmd": "bp", "action": "add", "addr": addr}
        if condition:
            req["condition"] = condition
        return self.cmd(req)

    def bp_clear(self):
        return self.cmd({"cmd": "bp", "action": "clear"})

    def wp_add(self, start, end=None, length=None, mode="w"):
        req = {"cmd": "wp", "action": "add", "start": start, "mode": mode}
        if length is not None:
            req["len"] = length
        elif end is not None:
            req["end"] = end
        return self.cmd(req)

    def wp_clear(self):
        return self.cmd({"cmd": "wp", "action": "clear"})

    def wait_stop(self, timeout_ms=10000):
        return self.cmd({"cmd": "wait", "for": "stop", "n": timeout_ms})

    def frames(self, n):
        return self.cmd({"cmd": "frames", "n": n})

    def step(self, count=1):
        return self.cmd({"cmd": "step", "count": count})

    def over(self):
        return self.cmd({"cmd": "over"})

    def out(self):
        return self.cmd({"cmd": "out"})

    def runto(self, addr):
        return self.cmd({"cmd": "runto", "addr": addr})

    def disasm(self, addr, count=10):
        return self.cmd({"cmd": "disasm", "addr": addr, "count": count})

    def key(self, code, shift=False):
        req = {"cmd": "key", "key": code}
        if shift:
            req["shift"] = 1
        return self.cmd(req)

    def type_text(self, text, wait=True):
        return self.cmd({"cmd": "type", "text": text, "wait": 1 if wait else 0})

    def shot(self, path):
        path = os.path.abspath(path)
        if os.path.exists(path):
            os.remove(path)
        return self.cmd({"cmd": "screenshot", "path": path})

    def quit(self):
        try:
            self.cmd({"cmd": "quit"})
        except Exception:
            pass
        self.close()

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def launch(dsk=DSK, port=DEFAULT_PORT, symbols=True, extra_args=()):
    subprocess.run(["powershell", "-Command", "Stop-Process -Name cpcse -Force -ErrorAction SilentlyContinue"])
    time.sleep(0.4)
    sym_file = SYM_PATH if symbols else None
    if symbols:
        export_symbols(sym_file)
    args = [CPCSE_EXE, f"--api={port}"]
    if sym_file:
        args += ["--symbols", sym_file]
    if dsk:
        args += ["--load", dsk, "--command", 'RUN"BLUESB\n']
    args += list(extra_args)
    subprocess.Popen(args, cwd=CPCSE_DIR)
    t0 = time.time()
    while time.time() - t0 < 15.0:
        try:
            c = CpcseClient(port=port)
            if c.cmd({"cmd": "ping"}).get("ok"):
                return c
            c.close()
        except Exception:
            time.sleep(0.25)
    raise TimeoutError("No s'ha pogut connectar a l'API de CPCSyntaxError")


def boot_level(level=1, dsk=DSK, port=DEFAULT_PORT, timeout=45.0):
    """Arrenca cpcse, carrega bluesb.dsk i entra al nivell 1..6."""
    c = launch(dsk=None, port=port)
    c.cmd({"cmd": "load", "path": dsk, "reset": 1, "command": 'RUN"BLUESB\n', "wait": 1})
    key_code = f"Digit{int(level)}"
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.4)
        if c.r8("_s_lv") == 0xB0 and c.r16("_s_px8") != 0:
            return c
        if not c.status().get("typing") and (time.time() - t0) > 2.5:
            c.key(key_code)
            c.key("Space")
    raise TimeoutError(f"Nivell {level} no ha carregat en {timeout}s")


if __name__ == "__main__":
    export_symbols(SYM_PATH)
    subprocess.Popen(
        [CPCSE_EXE, f"--api={DEFAULT_PORT}", "--mcp=6129",
         "--symbols", SYM_PATH, "--load", DSK, "--command", 'RUN"BLUESB\n'],
        cwd=CPCSE_DIR,
    )
    print(f"CPCSyntaxError iniciat amb API:6128, MCP:6129 i simbols: {SYM_PATH}")
