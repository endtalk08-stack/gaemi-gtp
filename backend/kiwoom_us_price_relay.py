"""Relay existing Kiwoom FE real-time price ticks directly to Render.

Reads Neon only for Top-20 membership. Sends signed changed quotes over HTTPS.
NEVER persists prices to Neon, Redis or disk; does not touch news or AI.
"""
import asyncio
import base64
import datetime as dt
import json
import os
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.kiwoom_us_live_prices import (
    URL, _open_us_session, _parse_price_event, _ranked_symbols,
)
from backend.providers.kiwoom_us_quotes import issue_access_token

RELAY_ENDPOINT = "https://gaemi-gtp.onrender.com/internal/market/us-price-push"


def signing_key():
    """Derive an independent Ed25519 key from existing high-entropy DO secret.

    The public verification key can be safely set in Render environment.
    The private key and Kiwoom credentials never leave DigitalOcean.
    """
    secret = os.environ.get("GAEMI_KIWOOM_APP_SECRET", "").strip()
    if len(secret) < 16:
        raise ValueError("relay_signing_secret_unavailable")
    seed = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"gaemi-price-relay-ed25519-20261023",
        info=b"digitalocean-kiwoom-fe-to-render-v1",
    ).derive(secret.encode("utf-8"))
    return Ed25519PrivateKey.from_private_bytes(seed)


def send_quotes(key, rows):
    """One signed, bounded, outbound HTTPS request. No storage."""
    if not rows:
        return 0
    payload = {
        "sent_at_ms": int(time.time() * 1000),
        "prices": [
            {"symbol": symbol, "price": price, "change_pct": pct}
            for symbol, (price, pct) in sorted(rows.items())
        ],
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    timestamp = str(int(time.time()))
    signed_data = timestamp.encode("ascii") + b":" + raw
    signature = base64.b64encode(key.sign(signed_data)).decode("ascii")
    try:
        result = requests.post(
            RELAY_ENDPOINT,
            data=raw,
            timeout=4,
            allow_redirects=False,
            headers={
                "Content-Type": "application/json",
                "X-Gaemi-Timestamp": timestamp,
                "X-Gaemi-Signature": signature,
            },
        )
    except requests.RequestException:
        raise RuntimeError("relay_http_transport") from None
    if result.status_code != 204:
        raise RuntimeError("relay_http_" + str(result.status_code))
    return len(rows)


async def stream_once(dsn, initial, key):
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect

    token = issue_access_token()
    async with connect(URL, open_timeout=10, close_timeout=3,
                       ping_interval=30, max_size=1048576) as ws:
        await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
        login_ok = False
        until = asyncio.get_running_loop().time() + 12
        while asyncio.get_running_loop().time() < until:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=7))
            if msg.get("trnm") == "PING":
                await ws.send(json.dumps(msg))
            elif msg.get("trnm") == "LOGIN":
                login_ok = str(msg.get("return_code")) in ("0", "0000")
                break
        if not login_ok:
            print("US_RELAY_LOGIN=failed", flush=True)
            return

        snapshot_id, selected = initial
        if not selected:
            return

        def register(group):
            return {
                "trnm": "REG", "grp_no": "1", "refresh": "1",
                "data": [{
                    "item": [{"jmcode": symbol, "stex_tp": exchange}
                             for symbol, exchange in group.items()],
                    "type": ["FE"],
                }],
            }

        await ws.send(json.dumps(register(selected)))
        print("US_RELAY_REGISTERED_COUNT=" + str(len(selected)), flush=True)
        buffered = {}
        now = asyncio.get_running_loop().time()
        last_flush = now
        last_rank_check = now
        last_error = 0.0
        while _open_us_session():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3)
                msg = json.loads(raw)
                if isinstance(msg, dict):
                    if msg.get("trnm") == "PING":
                        await ws.send(json.dumps(msg))
                    elif msg.get("trnm") == "REG" and str(msg.get("return_code", 0)) not in ("0", "0000"):
                        print("US_RELAY_REG=failed", flush=True)
                        return
                    else:
                        buffered.update(_parse_price_event(msg, selected))
            except (asyncio.TimeoutError, ValueError):
                pass

            now = asyncio.get_running_loop().time()
            if buffered and now - last_flush >= 2:
                try:
                    sent = await asyncio.to_thread(send_quotes, key, dict(buffered))
                    buffered.clear()
                    # Throttle successful status to avoid generating enormous logs.
                    if int(now) % 30 < 3:
                        print("US_RELAY_DELIVERED=" + str(sent), flush=True)
                except Exception as exc:
                    if now - last_error >= 30:
                        print("US_RELAY_ERROR=" + str(exc)[:60], flush=True)
                        last_error = now
                last_flush = now

            if now - last_rank_check >= 55:
                try:
                    next_snapshot, next_symbols = await asyncio.to_thread(_ranked_symbols, dsn)
                    if next_symbols and (next_symbols != selected or next_snapshot != snapshot_id):
                        if next_symbols != selected:
                            await ws.send(json.dumps(register(next_symbols)))
                            selected = next_symbols
                            buffered = {k: v for k, v in buffered.items() if k in selected}
                            print("US_RELAY_REGISTERED_COUNT=" + str(len(selected)), flush=True)
                        snapshot_id = next_snapshot
                except Exception as exc:
                    if now - last_error >= 30:
                        print("US_RELAY_RANK_ERROR=" + type(exc).__name__, flush=True)
                        last_error = now
                last_rank_check = now

        if buffered:
            try:
                await asyncio.to_thread(send_quotes, key, dict(buffered))
            except Exception:
                pass


async def main():
    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        print("US_RELAY_NEON_MEMBERSHIP_UNAVAILABLE", flush=True)
        return 2
    try:
        key = signing_key()
    except Exception as exc:
        print("US_RELAY_SIGNER_ERROR=" + type(exc).__name__, flush=True)
        return 2
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    # Only an Ed25519 public verification key is printed, never a secret.
    print("US_RELAY_PUBKEY_B64=" + base64.b64encode(public).decode("ascii"), flush=True)
    while True:
        if not _open_us_session():
            await asyncio.sleep(60)
            continue
        try:
            initial = await asyncio.to_thread(_ranked_symbols, dsn)
            if initial[1]:
                await stream_once(dsn, initial, key)
            else:
                print("US_RELAY_NO_TOP20", flush=True)
        except Exception as exc:
            print("US_RELAY_CONNECTION_ERROR=" + type(exc).__name__, flush=True)
        await asyncio.sleep(12 if _open_us_session() else 60)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()) or 0)
