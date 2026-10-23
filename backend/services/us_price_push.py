"""Memory-only signed DigitalOcean Kiwoom FE price relay for the US Top 20.

No quote is saved to Neon, Redis, disk or a background job. One Gunicorn
worker / one Render instance is expected for this in-process feed.
"""
import base64
import json
import math
import os
import re
import threading
import time

_LOCK = threading.Lock()
_LAST_SEND_MS = 0
_QUOTES = {}
_LAST_RECEIPT = 0.0
_VALID_SYMBOL = re.compile(r"[A-Z0-9.\\-]{1,20}")


def _verify_signature(raw, timestamp, signature):
    """Verify sender identity with a public key; private Kiwoom key never leaves DO."""
    pub = os.environ.get("GAEMI_PRICE_RELAY_PUBKEY", "").strip()
    if not pub or len(raw) > 6000 or len(raw) == 0:
        return False
    try:
        import cryptography.exceptions
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        if not re.fullmatch(r"[0-9]{10}", timestamp):
            return False
        if abs(time.time() - int(timestamp)) > 20:
            return False
        key = base64.b64decode(pub, validate=True)
        sig = base64.b64decode(signature, validate=True)
        if len(key) != 32 or len(sig) != 64:
            return False
        Ed25519PublicKey.from_public_bytes(key).verify(
            sig, timestamp.encode("ascii") + b":" + raw
        )
        return True
    except (ValueError, TypeError, UnicodeError, cryptography.exceptions.InvalidSignature):
        return False


def accept_signed_quotes(raw, timestamp, signature):
    """Return (ok, reason). Verify before decoding or changing the in-memory state."""
    if not _verify_signature(raw, timestamp, signature):
        return False, "not_authorized"
    try:
        data = json.loads(raw)
        sent_ms = data["sent_at_ms"]
        rows = data["prices"]
        if type(sent_ms) is not int or abs(time.time() * 1000 - sent_ms) > 20000:
            return False, "outdated"
        if not isinstance(rows, list) or not 1 <= len(rows) <= 20:
            return False, "invalid_payload"
        updates = {}
        for row in rows:
            if not isinstance(row, dict):
                return False, "invalid_payload"
            symbol = row.get("symbol")
            price = row.get("price")
            change = row.get("change_pct")
            if (not isinstance(symbol, str) or not _VALID_SYMBOL.fullmatch(symbol)
                    or symbol in updates or type(price) not in (int, float)
                    or not math.isfinite(price) or not 0 < price < 10000000):
                return False, "invalid_payload"
            if change is not None and (type(change) not in (int, float)
                                       or not math.isfinite(change) or not -100 < change < 10000):
                return False, "invalid_payload"
            updates[symbol] = {"symbol": symbol, "price": float(price),
                               "change_pct": float(change) if change is not None else None}
    except (TypeError, KeyError, ValueError, UnicodeError, json.JSONDecodeError):
        return False, "invalid_payload"

    global _LAST_SEND_MS, _LAST_RECEIPT
    with _LOCK:
        if sent_ms <= _LAST_SEND_MS:
            return False, "duplicate"
        _LAST_SEND_MS = sent_ms
        _LAST_RECEIPT = time.time()
        # Only the last quote per symbol is retained in process memory.
        for symbol, row in updates.items():
            _QUOTES[symbol] = {**row, "received_at": _LAST_RECEIPT}
        if len(_QUOTES) > 20:
            # The ranking may rotate; discard old arrivals, not current prices.
            oldest = sorted(_QUOTES, key=lambda k: _QUOTES[k]["received_at"])
            for symbol in oldest[:-20]:
                _QUOTES.pop(symbol, None)
    return True, "accepted"


def read_memory_quotes():
    with _LOCK:
        if not _QUOTES:
            return None
        now = time.time()
        return [
            {
                "symbol": item["symbol"], "price": item["price"],
                "change_pct": item["change_pct"],
                "received_at_ms": round(item["received_at"] * 1000),
                "stale": now - item["received_at"] > 25,
            }
            for item in _QUOTES.values()
        ]


def relay_is_configured():
    return bool(os.environ.get("GAEMI_PRICE_RELAY_PUBKEY", "").strip())
