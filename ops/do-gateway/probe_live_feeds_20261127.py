"""Read-only: what the public quote service currently sends (REST + websocket)."""
import base64
import json
import os
import socket
import ssl
import struct
import subprocess
import time
import urllib.request

CTX = ssl._create_unverified_context()
ORIGIN = "https://gaemigtp-main.pages.dev"


def rest(path):
    req = urllib.request.Request("https://127.0.0.1" + path, headers={"Origin": ORIGIN})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX))
    with opener.open(req, timeout=60) as resp:
        return json.load(resp)


def ws_messages(seconds=20):
    raw = socket.create_connection(("127.0.0.1", 443), timeout=10)
    sock = CTX.wrap_socket(raw, server_hostname="quotes.gaemigtp.com")
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(("GET /ws/us-live-quotes HTTP/1.1\r\nHost: quotes.gaemigtp.com\r\n"
                  "Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                  "Sec-WebSocket-Version: 13\r\nOrigin: %s\r\n\r\n" % (key, ORIGIN)).encode())
    head = b""
    while b"\r\n\r\n" not in head:
        head += sock.recv(1)
    print("WS_STATUS " + head.split(b"\r\n")[0].decode(), flush=True)
    out, buf, end = [], b"", time.time() + seconds
    sock.settimeout(2)
    while time.time() < end:
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
        while len(buf) >= 2:
            length = buf[1] & 0x7F
            pos = 2
            if length == 126:
                if len(buf) < 4: break
                length = struct.unpack(">H", buf[2:4])[0]; pos = 4
            elif length == 127:
                if len(buf) < 10: break
                length = struct.unpack(">Q", buf[2:10])[0]; pos = 10
            if len(buf) < pos + length: break
            payload, buf = buf[pos:pos + length], buf[pos + length:]
            try:
                out.append(json.loads(payload))
            except ValueError:
                pass
    return out


def show(label, items):
    items = [i for i in items or [] if isinstance(i, dict)]
    rated = [i for i in items if isinstance(i.get("change_pct"), (int, float))]
    now = int(time.time() * 1000)
    ages = sorted((now - i["received_at_ms"]) // 1000 for i in items if isinstance(i.get("received_at_ms"), int))
    print("%s items=%d rated=%d stale=%d age_s(min/max)=%s sample=%s" % (
        label, len(items), len(rated), sum(bool(i.get("stale")) for i in items),
        (ages[0], ages[-1]) if ages else None,
        [(i.get("symbol"), i.get("price"), i.get("change_pct"), i.get("stale"), i.get("source")) for i in items[:3]]),
        flush=True)


def main():
    print("ACTIVE " + subprocess.run(["systemctl", "is-active", "gaemigtp-kiwoom-us-top20-https.service",
                                      "gaemigtp-kiwoom-us-top20-api.service", "gaemigtp-kiwoom-us-value.timer"],
                                     text=True, capture_output=True).stdout.replace("\n", " "), flush=True)
    show("REST_SPY_DIA", rest("/market/us-etf-quotes").get("items"))
    show("REST_SECTOR_ETF", rest("/market/us-industry-etf-quotes").get("items"))
    show("REST_TOP20", rest("/market/trading-value?market=us").get("items"))
    msgs = ws_messages()
    kinds = {}
    for m in msgs:
        kinds.setdefault(m.get("type") or ("qqq" if m.get("symbol") == "QQQ" else "other"), []).append(m)
    print("WS_TYPES " + json.dumps({k: len(v) for k, v in kinds.items()}), flush=True)
    for kind, group in kinds.items():
        last = group[-1]
        if isinstance(last.get("items"), list):
            show("WS_" + kind, last["items"])
        else:
            print("WS_%s %s" % (kind, json.dumps(last)[:300]), flush=True)


if __name__ == "__main__":
    main()
