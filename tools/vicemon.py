#!/usr/bin/env python3
"""
vicemon.py - Client per al monitor remot de text de VICE (x64sc/x64).

El monitor remot de VICE escolta en un port TCP i accepta comandes text
seguides de newline. Per exemple:
  - machine-resources
  - read-memory 0x0400 0x400
  - registers

Us:
  py vicemon.py <comanda...>          # executa una comanda
  py vicemon.py --dump 0x0000 0x10000 -o mem.bin
  py vicemon.py --regs
  py vicemon.py --screenshot out.png
"""
import argparse
import socket
import sys
import time


class ViceMon:
    def __init__(self, host='127.0.0.1', port=6510, timeout=10):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        time.sleep(0.2)
        self._drain()

    def _drain(self):
        try:
            while True:
                d = self.s.recv(65536)
                if not d:
                    break
        except socket.timeout:
            pass
        except Exception:
            pass

    def raw(self, line, wait=0.15):
        self.s.sendall(line.encode('latin1') + b'\n')
        time.sleep(wait)
        buf = b''
        try:
            while True:
                d = self.s.recv(65536)
                if not d:
                    break
                buf += d
        except socket.timeout:
            pass
        except Exception:
            pass
        return buf

    def read_mem(self, addr, length):
        # resposta a "read-memory" es hexadecimal amb salts de linia
        out = self.raw('read-memory 0x%X 0x%X' % (addr, length), wait=0.3)
        txt = out.decode('latin1', 'replace')
        hexs = ''.join(c for c in txt if c in '0123456789abcdefABCDEF')
        if len(hexs) % 2:
            hexs = hexs[:-1]
        return bytes.fromhex(hexs)

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', nargs='*')
    ap.add_argument('--dump', nargs=2)
    ap.add_argument('-o', '--output', default='mem.bin')
    ap.add_argument('--regs', action='store_true')
    ap.add_argument('--port', type=int, default=6510)
    args = ap.parse_args()

    m = ViceMon(port=args.port)
    if args.regs:
        print(m.raw('registers', wait=0.5).decode('latin1', 'replace'))
    elif args.dump:
        start = int(args.dump[0], 0)
        length = int(args.dump[1], 0)
        data = m.read_mem(start, length)
        open(args.output, 'wb').write(data)
        print("escrit", args.output, len(data), "bytes")
    elif args.command:
        print(m.raw(' '.join(args.command), wait=0.5).decode('latin1', 'replace'))
    m.close()


if __name__ == '__main__':
    main()
