"""Read-only quote endpoint and websocket counts after the recovery deploy."""
import base64
import json
import os
import socket
import ssl
import struct
from urllib.request import urlopen

context = ssl._create_unverified_context()
for path in ("/market/trading-value?market=us", "/market/us-industry-etf-quotes", "/market/us-etf-quotes"):
    try:
        with urlopen("https://127.0.0.1" + path, timeout=25, context=context) as reply:
            data = json.load(reply)
        items = data.get("items") or []
        print("API", path, "count", len(items), "with_change",
              sum(type(x.get("change_pct")) in (int, float) for x in items),
              "sample", [(x.get("symbol"), x.get("change_pct"), x.get("source"), x.get("stale"))
                         for x in items[:3]], flush=True)
    except Exception as exc:
        print("API_ERROR", path, type(exc).__name__, flush=True)

try:
    with socket.create_connection(("127.0.0.1", 443), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname="quotes.gaemigtp.com") as sock:
            sock.settimeout(5)
            key = base64.b64encode(os.urandom(16)).decode()
            request = ('GET /ws/us-live-quotes HTTP/1.1\r\nHost: quotes.gaemigtp.com\r\n'
                       'Origin: https://gaemigtp-main.pages.dev\r\nUpgrade: websocket\r\n'
                       'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                       'Sec-WebSocket-Key: ' + key + '\r\n\r\n')
            sock.sendall(request.encode())
            received = b""
            while b"\r\n\r\n" not in received:
                received += sock.recv(4096)
            head, payload = received.split(b"\r\n\r\n", 1)
            print("UPGRADE", head.split(b"\r\n", 1)[0].decode(), flush=True)
            for _ in range(12):
                try:
                    while len(payload) < 2:
                        payload += sock.recv(4096)
                    length, start = payload[1] & 127, 2
                    if length == 126:
                        while len(payload) < 4: payload += sock.recv(4096)
                        length, start = struct.unpack("!H", payload[2:4])[0], 4
                    elif length == 127:
                        while len(payload) < 10: payload += sock.recv(4096)
                        length, start = struct.unpack("!Q", payload[2:10])[0], 10
                    while len(payload) < start + length:
                        payload += sock.recv(4096)
                    message = json.loads(payload[start:start + length])
                    payload = payload[start + length:]
                    items = ([message.get("quote")] if message.get("type") == "quote"
                             else message.get("items") or [])
                    valid = [x for x in items if isinstance(x, dict)]
                    print("FRAME", message.get("type"), len(valid),
                          sum(type(x.get("change_pct")) in (int, float) for x in valid), flush=True)
                except socket.timeout:
                    print("FRAME_TIMEOUT", flush=True)
                    break
except Exception as exc:
    print("WS_ERROR", type(exc).__name__, flush=True)
