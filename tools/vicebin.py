#!/usr/bin/env python3
"""
vicebin.py - Client minimal per al Binary Monitor de VICE (port 6502).

Referencia: https://vice-emu.sourceforge.io/vice_13.html

Us:
  py vicebin.py --dump 0x0000 0x10000 -o mem.bin
  py vicebin.py --regs
  py vicebin.py --exit
  py vicebin.py --reset
  py vicebin.py --screenshot out.png
  py vicebin.py --feed "SYS 2049\n"
  py vicebin.py --step N
"""
import argparse
import socket
import struct
import sys
import time

STX = 0x02
API = 0x02

# command ids
CMD_MEM_GET = 0x01
CMD_MEM_SET = 0x02
CMD_CHECKPOINT_SET = 0x12
CMD_REG_GET = 0x31
CMD_DUMP = 0x41
CMD_ADVANCE = 0x71
CMD_KEYBOARD_FEED = 0x72
CMD_PING = 0x81
CMD_DISPLAY_GET = 0x84
CMD_EXIT = 0xAA
CMD_QUIT = 0xBB
CMD_RESET = 0xCC
CMD_AUTOSTART = 0xDD

RESP_STOPPED = 0x62
RESP_RESUMED = 0x63


class ViceBin:
    def __init__(self, host='127.0.0.1', port=6502, timeout=15):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        self.rid = 0

    def _send(self, ctype, body=b''):
        self.rid += 1
        hdr = bytes([STX, API]) + struct.pack('<I', len(body)) + \
            struct.pack('<I', self.rid) + bytes([ctype])
        self.s.sendall(hdr + body)
        return self.rid

    def _read_packet(self):
        # Sincronitza sobre STX i llegeix un paquet complet.
        while True:
            b = self.s.recv(1)
            if not b:
                raise EOFError("tancat")
            if b[0] == STX:
                break
        hdr = b''
        while len(hdr) < 11:
            d = self.s.recv(11 - len(hdr))
            if not d:
                raise EOFError("tancat")
            hdr += d
        api = hdr[0]
        length = struct.unpack('<I', hdr[1:5])[0]
        rtype = hdr[5]
        err = hdr[6]
        rid = struct.unpack('<I', hdr[7:11])[0]
        body = b''
        while len(body) < length:
            d = self.s.recv(length - len(body))
            if not d:
                break
            body += d
        return rtype, err, rid, body

    def recv_response(self):
        return self._read_packet()

    def wait_for(self, rtype, tries=400):
        for _ in range(tries):
            t, err, rid, body = self.recv_response()
            if t == rtype:
                return body
            if t in (RESP_STOPPED, RESP_RESUMED):
                continue
        raise TimeoutError("resp type 0x%02X no arribada" % rtype)

    def mem_get(self, start, end, memspace=0, bank=0):
        body = bytes([0]) + struct.pack('<HH', start, end) + \
            bytes([memspace]) + struct.pack('<H', bank)
        self._send(CMD_MEM_GET, body)
        b = self.wait_for(CMD_MEM_GET)
        ml = struct.unpack('<H', b[0:2])[0]
        return b[2:2 + ml]

    def mem_set(self, start, data, memspace=0, bank=0):
        end = start + len(data) - 1
        body = bytes([0]) + struct.pack('<HH', start, end) + \
            bytes([memspace]) + struct.pack('<H', bank) + data
        self._send(CMD_MEM_SET, body)
        self.wait_for(CMD_MEM_SET)

    def checkpoint_set(self, start, end, stop=True, op=0x04, temporary=False):
        body = struct.pack('<HH', start, end) + bytes([
            1 if stop else 0, 1, op, 1 if temporary else 0, 0])
        self._send(CMD_CHECKPOINT_SET, body)
        b = self.wait_for(0x11)
        return struct.unpack('<I', b[0:4])[0]

    def checkpoint_delete(self, cn):
        self._send(0x13, struct.pack('<I', cn))
        self.wait_for(0x13)

    def checkpoint_list(self):
        self._send(0x14)
        out = []
        while True:
            t, err, rid, b = self.recv_response()
            if t == 0x14:
                return out
            if t == 0x11:
                out.append(b)

    def regs(self):
        self._send(CMD_REG_GET, bytes([0]))
        b = self.wait_for(CMD_REG_GET)
        rc = struct.unpack('<H', b[0:2])[0]
        out = {}
        off = 2
        for _ in range(rc):
            isz = b[off]
            ri = b[off + 1]
            rv = struct.unpack('<H', b[off + 2:off + 4])[0]
            out[ri] = rv
            off += 1 + isz
        return out

    def exit(self):
        self._send(CMD_EXIT)
        try:
            self.wait_for(CMD_EXIT, tries=30)
        except Exception:
            pass

    def reset(self, kind=0):
        self._send(CMD_RESET, bytes([kind]))
        self.wait_for(CMD_RESET)

    def ping(self):
        self._send(CMD_PING)
        return self.wait_for(CMD_PING)

    def autostart(self, filename, run=True, index=0):
        fn = filename.encode('latin1')
        body = bytes([1 if run else 0]) + struct.pack('<H', index) + \
            bytes([len(fn)]) + fn
        self._send(CMD_AUTOSTART, body)
        self.wait_for(CMD_AUTOSTART)

    def screenshot(self):
        # body: FL(4) DW(2) DH(2) XO(2) YO(2) IW(2) IH(2) BP(1) BL(4) BD...
        self._send(CMD_DISPLAY_GET, bytes([1, 0]))
        b = self.wait_for(CMD_DISPLAY_GET)
        dw = struct.unpack('<H', b[4:6])[0]
        dh = struct.unpack('<H', b[6:8])[0]
        xo = struct.unpack('<H', b[8:10])[0]
        yo = struct.unpack('<H', b[10:12])[0]
        iw = struct.unpack('<H', b[12:14])[0]
        ih = struct.unpack('<H', b[14:16])[0]
        bl = struct.unpack('<I', b[17:21])[0]
        buf = b[21:21 + bl]
        return dw, dh, xo, yo, iw, ih, buf

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', nargs=2)
    ap.add_argument('--regs', action='store_true')
    ap.add_argument('--exit', action='store_true')
    ap.add_argument('--reset', action='store_true')
    ap.add_argument('--ping', action='store_true')
    ap.add_argument('--screenshot', default=None)
    ap.add_argument('--feed', default=None)
    ap.add_argument('--step', type=int, default=0)
    ap.add_argument('--port', type=int, default=6502)
    args = ap.parse_args()

    v = ViceBin(port=args.port)
    if args.ping:
        v.ping()
        print("pong")
    if args.regs:
        r = v.regs()
        print(r)
    if args.step:
        v._send(CMD_ADVANCE, bytes([0]) + struct.pack('<H', args.step))
        v.wait_for(CMD_ADVANCE)
        r = v.regs()
        print("PC=$%04X" % r.get(3, 0))
    if args.feed:
        t = args.feed.encode('latin1')
        v._send(CMD_KEYBOARD_FEED, bytes([len(t)]) + t)
        v.wait_for(CMD_KEYBOARD_FEED)
        print("feed ok")
    if args.dump:
        start = int(args.dump[0], 0)
        end = int(args.dump[1], 0)
        data = v.mem_get(start, end - 1)
        out = args.dump[0] + '.bin' if args.screenshot is None else None
        print("mem %04X-%04X len=%d" % (start, end, len(data)))
        if out:
            open(out, 'wb').write(data)
            print("escrit", out)
    if args.screenshot:
        from PIL import Image
        dw, dh, xo, yo, iw, ih, buf = v.screenshot()
        im = Image.new('RGB', (iw, ih))
        # buf son indexs de paleta; fem escala de grisos entretant
        im.putdata([(c, c, c) for c in buf[:iw * ih]])
        im.save(args.screenshot)
        print("screenshot", args.screenshot, "dbg %dx%d inner %dx%d @%d,%d" % (
            dw, dh, iw, ih, xo, yo))
    if args.reset:
        v.reset(0)
        print("reset")
    if args.exit:
        v.exit()
        print("exit")
    v.close()


if __name__ == '__main__':
    main()
