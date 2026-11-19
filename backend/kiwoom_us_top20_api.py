"""Read-only HTTP adapter for the existing DigitalOcean Kiwoom US TOP20 file.

No Kiwoom calls, Render, Neon, R2, Redis, AI, or news worker.
Binds to loopback; HTTPS reverse proxy must be configured separately.
"""
import base64
import hashlib
import json
import os
import re
import select
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

RANKING_FILE = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
ADDRESS = "127.0.0.1"
PORT = 8765
ALLOWED_ORIGINS = {
    "https://gaemi-gtp.onrender.com",
    "https://gaemigtp.com",
    "https://www.gaemigtp.com",
    "https://gaemigtp-news.pages.dev",
    "https://gaemigtp-main.pages.dev",
}
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")

_QQQ_LOCK = threading.Lock()
_QQQ_CHANGED = threading.Condition(_QQQ_LOCK)
_QQQ_QUOTE = None
_QQQ_WS_CLIENTS = threading.BoundedSemaphore(48)
_QQQ_STALE_MS = 25000
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _origin_allowed(origin):
    if origin in ALLOWED_ORIGINS:
        return True
    try:
        parsed = urlsplit(origin)
        host = (parsed.hostname or "").lower()
        return (parsed.scheme == "https" and
                (host == "gaemigtp-main.pages.dev" or
                 host.endswith(".gaemigtp-main.pages.dev")))
    except (TypeError, ValueError):
        return False


def _publish_qqq_quote(quote):
    global _QQQ_QUOTE
    if not isinstance(quote, dict):
        return
    price = quote.get("price")
    change = quote.get("change_pct")
    if (quote.get("symbol") != "QQQ" or type(price) not in (int, float)
            or not 0 < price < 10000000):
        return
    if change is not None and (type(change) not in (int, float)
                               or not -100 < change < 10000):
        change = None
    safe = {
        "symbol": "QQQ", "price": float(price),
        "change_pct": float(change) if change is not None else None,
        "received_at_ms": int(time.time() * 1000), "stale": False,
    }
    with _QQQ_CHANGED:
        _QQQ_QUOTE = safe
        _QQQ_CHANGED.notify_all()


def _qqq_snapshot():
    with _QQQ_LOCK:
        quote = dict(_QQQ_QUOTE) if _QQQ_QUOTE else None
    if quote is not None:
        quote["stale"] = int(time.time() * 1000) - quote["received_at_ms"] > _QQQ_STALE_MS
    return quote


def _websocket_text_frame(payload, opcode=0x1):
    length = len(payload)
    first = 0x80 | opcode
    if length < 126:
        header = bytes((first, length))
    elif length <= 65535:
        header = bytes((first, 126)) + struct.pack("!H", length)
    else:
        header = bytes((first, 127)) + struct.pack("!Q", length)
    return header + payload


def _start_qqq_feed():
    import asyncio
    from backend.kiwoom_us_live_prices import run_qqq_fe_stream

    def runner():
        asyncio.run(run_qqq_fe_stream(_publish_qqq_quote))

    thread = threading.Thread(target=runner, name="kiwoom-qqq-fe", daemon=True)
    thread.start()
    print("KIWOOM_QQQ_FE_THREAD_STARTED", flush=True)



def read_top20(path=RANKING_FILE):
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("top20_local_file_unavailable")
    if path.stat().st_size > 128000:
        raise ValueError("top20_file_too_large")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(data.get(k) != v for k, v in (
        ("schema_version", 1), ("source", "kiwoom"), ("market", "US"),
        ("rank_type", "trading_value"))):
        raise ValueError("top20_invalid_metadata")
    rows = data.get("items")
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("top20_incomplete")
    seen = set()
    items = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("top20_invalid_row")
        symbol = row.get("symbol")
        if row.get("rank") != index or not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol) or symbol in seen:
            raise ValueError("top20_invalid_ranking")
        seen.add(symbol)
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("top20_invalid_name")
        item = {
            "rank": index,
            "symbol": symbol,
            "name": name,
            "exchange": row.get("exchange"),
            "company_key": row.get("company_key"),
            "price": row.get("price"),
            "change_pct": row.get("change_pct"),
            "trading_value": row.get("trading_value"),
            "volume": row.get("volume"),
        }
        value = item["trading_value"]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            item["trading_value_text"] = "$" + format(value, ",.0f")
        else:
            item["trading_value_text"] = None
        items.append(item)
    return {
        "ok": True, "market": "us", "source": "kiwoom",
        "currency": "USD", "captured_at": data.get("captured_at"),
        "items": items,
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/ws/us-live-quotes":
            return self._serve_qqq_websocket()
        if path.path == "/health":
            return self._json(200, {"ok": True, "service": "kiwoom-us-top20-api"})
        if path.path != "/market/trading-value" or parse_qs(path.query).get("market") != ["us"]:
            return self._json(404, {"ok": False, "error": "not_found", "items": []})
        try:
            result = read_top20()
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            # Expose only the error class, never private filesystem details.
            return self._json(503, {"ok": False, "items": [], "error": type(exc).__name__})
        self._json(200, result)


    def _serve_qqq_websocket(self):
        if not getattr(self.server, "qqq_feed_enabled", False):
            return self._json(503, {"ok": False, "error": "qqq_feed_unavailable"})
        origin = self.headers.get("Origin", "")
        if not _origin_allowed(origin):
            return self._json(403, {"ok": False, "error": "origin_not_allowed"})
        key = self.headers.get("Sec-WebSocket-Key", "")
        if (self.headers.get("Upgrade", "").lower() != "websocket"
                or "upgrade" not in self.headers.get("Connection", "").lower()
                or not key):
            return self._json(400, {"ok": False, "error": "websocket_upgrade_required"})
        try:
            decoded_key = base64.b64decode(key, validate=True)
        except (ValueError, TypeError):
            return self._json(400, {"ok": False, "error": "invalid_websocket_key"})
        if len(decoded_key) != 16:
            return self._json(400, {"ok": False, "error": "invalid_websocket_key"})
        if not _QQQ_WS_CLIENTS.acquire(blocking=False):
            return self._json(503, {"ok": False, "error": "websocket_capacity_reached"})

        try:
            accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()
            ).decode("ascii")
            self.close_connection = True
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.flush()
            last_signature = object()
            last_heartbeat = 0.0
            while True:
                quote = _qqq_snapshot()
                signature = ((quote["received_at_ms"], quote["stale"])
                             if quote is not None else None)
                now = time.monotonic()
                if signature != last_signature or now - last_heartbeat >= 10:
                    payload = json.dumps(
                        {"type": "quote", "quote": quote},
                        separators=(",", ":"), allow_nan=False,
                    ).encode("utf-8")
                    self.connection.sendall(_websocket_text_frame(payload))
                    last_signature = signature
                    last_heartbeat = now
                with _QQQ_CHANGED:
                    _QQQ_CHANGED.wait(timeout=1.0)
                readable, _, _ = select.select([self.connection], [], [], 0)
                if readable:
                    incoming = self.connection.recv(4096)
                    if not incoming or (incoming[0] & 0x0F) == 0x8:
                        break
        except (OSError, ValueError, select.error):
            pass
        finally:
            _QQQ_WS_CLIENTS.release()

    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=15" if status == 200 else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin", "")
        if _origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass



class BoundedTLSServer(ThreadingHTTPServer):
    """Do TLS handshakes with a timeout, not on the listening socket.

    A stalled client must not prevent the entire TOP20 HTTPS listener from
    accepting later requests. No market, storage or authentication changes.
    """
    request_queue_size = 128
    daemon_threads = True

    def get_request(self):
        sock, address = self.socket.accept()
        sock.settimeout(4)
        try:
            wrapped = self.ssl_context.wrap_socket(sock, server_side=True)
            wrapped.settimeout(10)
            return wrapped, address
        except OSError:
            sock.close()
            raise


def main():
    import sys
    if sys.argv[1:] not in ([], ["--tls"]):
        raise SystemExit("unsupported_api_mode")
    tls = sys.argv[1:] == ["--tls"]
    # Plain HTTP remains loopback-only; the separately managed TLS listener is public.
    host, port = ("0.0.0.0", 443) if tls else (ADDRESS, PORT)
    server_class = BoundedTLSServer if tls else ThreadingHTTPServer
    with server_class((host, port), Handler) as server:
        if tls:
            import ssl
            cert_dir = Path("/var/lib/gaemigtp-news")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(
                certfile=str(cert_dir / "quotes-origin.crt"),
                keyfile=str(cert_dir / "quotes-origin.key"),
            )
            server.ssl_context = ctx
        server.qqq_feed_enabled = tls
        if tls:
            _start_qqq_feed()
        server.serve_forever()


if __name__ == "__main__":
    main()
