import socket, time

s = socket.socket()
s.settimeout(5)
s.connect(("127.0.0.1", 10010))
time.sleep(0.5)
s.recv(4096)

def send_cmd(c, delay=0.05):
    s.sendall(c.encode("latin1") + b"\r\n")
    time.sleep(delay)
    buf = b""
    while True:
        d = s.recv(65536)
        buf += d
        if buf.rstrip().endswith(b">"): break
    return buf.decode("latin1", errors="replace")

def press_key(key, event):
    send_cmd(f"send-keys-event {key} {event}")

time.sleep(1)

# Type run"bluesb"
send_cmd("send-keys-string 60 run")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
send_cmd("send-keys-string 60 bluesb")
time.sleep(0.2)
press_key(133, 1); time.sleep(0.05); press_key(50, 1); time.sleep(0.05); press_key(50, 0); time.sleep(0.05); press_key(133, 0)
time.sleep(0.1)
press_key(129, 1); time.sleep(0.1); press_key(129, 0)

s.close()
print("Boot enviat correctament!")
