"""Read-only HTTP adapter for the existing DigitalOcean Kiwoom US TOP20 file.

No Kiwoom calls, Render, Neon, R2, Redis, AI, or news worker.
Binds to loopback; HTTPS reverse proxy must be configured separately.
"""
import json
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

RANKING_FILE = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
ADDRESS = "127.0.0.1"
PORT = 8765
ALLOWED_ORIGINS = {
    "https://gaemigtp.com",
    "https://www.gaemigtp.com",
    "https://gaemigtp-news.pages.dev",
}
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")


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
    def do_GET(self):
        path = urlsplit(self.path)
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

    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=15" if status == 200 else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


def main():
    import sys
    if sys.argv[1:] not in ([], ["--tls"]):
        raise SystemExit("unsupported_api_mode")
    tls = sys.argv[1:] == ["--tls"]
    # Plain HTTP remains loopback-only; the separately managed TLS listener is public.
    host, port = ("0.0.0.0", 443) if tls else (ADDRESS, PORT)
    with ThreadingHTTPServer((host, port), Handler) as server:
        if tls:
            import ssl
            cert_dir = Path("/var/lib/gaemigtp-news")
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(
                certfile=str(cert_dir / "quotes-origin.crt"),
                keyfile=str(cert_dir / "quotes-origin.key"),
            )
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
