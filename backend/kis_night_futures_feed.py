"""Read-only KIS KRX night-futures WebSocket feed for the quote relay."""
from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
import logging
import math
import os
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives import padding as symmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

REST_BASE = "https://openapi.koreainvestment.com:9443"
WS_URL = "ws://ops.koreainvestment.com:21000"
DEFAULT_SYMBOL = "101W9000"   # KIS example code; the live feed uses front_month_code()
SEOUL = ZoneInfo("Asia/Seoul")
STATE_DIR = Path("/var/lib/gaemigtp-news")
LAST_QUOTE_PATH = STATE_DIR / "kis-night-futures-last.json"
TOKEN_PATH = STATE_DIR / "kis-access-token.json"
REST_POLL_SECONDS = 60
LIVE_WINDOW_MS = 90_000
TRADES_TR_ID = "H0MFCNT0"
QUOTE_TR_ID = "H0MFASP0"

TRADE_FIELDS = [
    "futs_shrn_iscd", "bsop_hour", "futs_prdy_vrss", "prdy_vrss_sign",
    "futs_prdy_ctrt", "futs_prpr", "futs_oprc", "futs_hgpr", "futs_lwpr",
    "last_cnqn", "acml_vol", "acml_tr_pbmn", "hts_thpr", "mrkt_basis",
    "dprt", "nmsc_fctn_stpl_prc", "fmsc_fctn_stpl_prc", "spead_prc",
    "hts_otst_stpl_qty", "otst_stpl_qty_icdc", "oprc_hour",
    "oprc_vrss_prpr_sign", "oprc_vrss_nmix_prpr", "hgpr_hour",
    "hgpr_vrss_prpr_sign", "hgpr_vrss_nmix_prpr", "lwpr_hour",
    "lwpr_vrss_prpr_sign", "lwpr_vrss_nmix_prpr", "shnu_rate", "cttr",
    "esdg", "otst_stpl_rgbf_qty_icdc", "thpr_basis", "futs_askp1",
    "futs_bidp1", "askp_rsqn1", "bidp_rsqn1", "seln_cntg_csnu",
    "shnu_cntg_csnu", "ntby_cntg_csnu", "seln_cntg_smtn",
    "shnu_cntg_smtn", "total_askp_rsqn", "total_bidp_rsqn",
    "prdy_vol_vrss_acml_vol_rate", "dynm_mxpr", "dynm_llam",
    "dynm_prc_limt_yn",
]
QUOTE_FIELDS = [
    "futs_shrn_iscd", "bsop_hour",
    "futs_askp1", "futs_askp2", "futs_askp3", "futs_askp4", "futs_askp5",
    "futs_bidp1", "futs_bidp2", "futs_bidp3", "futs_bidp4", "futs_bidp5",
    "askp_csnu1", "askp_csnu2", "askp_csnu3", "askp_csnu4", "askp_csnu5",
    "bidp_csnu1", "bidp_csnu2", "bidp_csnu3", "bidp_csnu4", "bidp_csnu5",
    "askp_rsqn1", "askp_rsqn2", "askp_rsqn3", "askp_rsqn4", "askp_rsqn5",
    "bidp_rsqn1", "bidp_rsqn2", "bidp_rsqn3", "bidp_rsqn4", "bidp_rsqn5",
    "total_askp_csnu", "total_bidp_csnu", "total_askp_rsqn",
    "total_bidp_rsqn", "total_askp_rsqn_icdc", "total_bidp_rsqn_icdc",
]


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        result = float(str(value).strip().replace(",", ""))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _second_thursday(year: int, month: int) -> dt.date:
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(3 - first.weekday()) % 7 + 7)


def front_month_code(today: dt.date | None = None) -> str:
    """KOSPI 200 futures front month in the KIS code format, e.g. A01612 (Dec 2026).

    Quarterly contracts (Mar/Jun/Sep/Dec) expire on the second Thursday; the night
    session of the expiry day already trades the next contract.
    """
    today = today or dt.datetime.now(SEOUL).date()
    year, month = today.year, ((today.month - 1) // 3 + 1) * 3
    while today >= _second_thursday(year, month):
        month += 3
        if month > 12:
            year, month = year + 1, month - 12
    return "A01%d%02d" % (year % 10, month)


def _write_json(path: Path, data: dict) -> None:
    try:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".kis-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except OSError:
        pass


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_last_quote(path: Path = LAST_QUOTE_PATH) -> dict | None:
    """The last real price, so the widget never shows a dash after a restart."""
    quote = _read_json(path)
    price = _number(quote.get("price"))
    return quote if price and price > 0 else None


def save_last_quote(quote: dict, path: Path = LAST_QUOTE_PATH) -> None:
    _write_json(path, {k: quote.get(k) for k in ("symbol", "price", "change_pct", "time", "source")})


def get_access_token(app_key: str, app_secret: str, path: Path = TOKEN_PATH, now: float | None = None,
                     opener=urllib.request.urlopen) -> str:
    """REST access token, cached on disk for its lifetime (KIS limits how often one is issued)."""
    now = now or time.time()
    cached = _read_json(path)
    if cached.get("token") and float(cached.get("expires_at") or 0) - 600 > now:
        return str(cached["token"])
    body = json.dumps({"grant_type": "client_credentials", "appkey": app_key, "appsecret": app_secret}).encode()
    request = urllib.request.Request(REST_BASE + "/oauth2/tokenP", data=body, method="POST",
                                     headers={"content-type": "application/json; charset=utf-8"})
    with opener(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError("kis_access_token_missing")
    _write_json(path, {"token": token, "expires_at": now + (_number(payload.get("expires_in")) or 86400)})
    return token


def fetch_last_price(app_key: str, app_secret: str, symbol: str, opener=urllib.request.urlopen,
                     token: str | None = None) -> dict | None:
    """Last traded price over REST: the night session (CM) first, the day session (F) otherwise."""
    token = token or get_access_token(app_key, app_secret)
    for market, source in (("CM", "kis:rest-night"), ("F", "kis:rest-day")):
        query = urllib.parse.urlencode({"FID_COND_MRKT_DIV_CODE": market, "FID_INPUT_ISCD": symbol})
        request = urllib.request.Request(
            REST_BASE + "/uapi/domestic-futureoption/v1/quotations/inquire-price?" + query,
            headers={"authorization": "Bearer " + token, "appkey": app_key, "appsecret": app_secret,
                     "tr_id": "FHMIF10000000", "custtype": "P", "content-type": "application/json"})
        with opener(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        output = (payload or {}).get("output1") or {}
        price = _number(output.get("futs_prpr"))
        if price and price > 0:
            change = _number(output.get("futs_prdy_ctrt"))
            return {"symbol": symbol, "price": price,
                    "change_pct": change if change is not None and -100 < change < 10000 else None,
                    "source": source}
        time.sleep(0.6)       # KIS allows only a few REST calls a second
    return None


def get_approval_key(app_key: str, app_secret: str) -> str:
    """Request a KIS production WebSocket approval key without logging secrets."""
    body = json.dumps({
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret,
    }).encode("utf-8")
    request = urllib.request.Request(
        REST_BASE + "/oauth2/Approval",
        data=body,
        headers={"content-type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    approval_key = payload.get("approval_key") if isinstance(payload, dict) else None
    if not isinstance(approval_key, str) or not approval_key:
        raise RuntimeError("kis_approval_key_missing")
    return approval_key


def subscription_message(approval_key: str, tr_id: str, symbol: str) -> str:
    return json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1",
            "content-type": "utf-8",
        },
        "body": {"input": {"tr_id": tr_id, "tr_key": symbol}},
    }, ensure_ascii=False, separators=(",", ":"))


def _decrypt_payload(encoded: str, key: str, iv: str) -> str:
    """Decrypt KIS AES-CBC/base64 realtime payloads using the subscription response."""
    encrypted = base64.b64decode(encoded, validate=True)
    decryptor = Cipher(
        algorithms.AES(key.encode("utf-8")),
        modes.CBC(iv.encode("utf-8")),
    ).decryptor()
    padded = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = symmetric_padding.PKCS7(algorithms.AES.block_size).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    return plain.decode("utf-8")


def decode_realtime_frame(
    frame: str,
    expected_symbol: str = DEFAULT_SYMBOL,
    encryption: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Decode KIS caret-delimited KRX night-futures trade or order-book data."""
    parts = frame.split("|", 3)
    if len(parts) < 4 or parts[0] not in {"0", "1"}:
        return None
    tr_id = parts[1]
    fields = TRADE_FIELDS if tr_id == TRADES_TR_ID else QUOTE_FIELDS if tr_id == QUOTE_TR_ID else None
    if fields is None:
        return None
    data = parts[3]
    if parts[0] == "1":
        if not encryption or not encryption.get("key") or not encryption.get("iv"):
            return None
        try:
            data = _decrypt_payload(data, encryption["key"], encryption["iv"])
        except Exception:
            return None
    values = dict(zip(fields, data.split("^")))
    symbol = str(values.get("futs_shrn_iscd") or parts[2]).strip()
    if symbol != expected_symbol:
        return None
    result: dict[str, Any] = {
        "tr_id": tr_id,
        "symbol": symbol,
        "time": values.get("bsop_hour"),
    }
    if tr_id == TRADES_TR_ID:
        price = _number(values.get("futs_prpr"))
        change = _number(values.get("futs_prdy_ctrt"))
        if price is None or price <= 0:
            return None
        if change is not None and not -100 < change < 10000:
            change = None
        result.update({
            "price": price,
            "change_pct": change,
            "last_volume": _number(values.get("last_cnqn")),
            "accumulated_volume": _number(values.get("acml_vol")),
            "best_ask": _number(values.get("futs_askp1")),
            "best_bid": _number(values.get("futs_bidp1")),
        })
    else:
        result.update({
            "best_ask": _number(values.get("futs_askp1")),
            "best_bid": _number(values.get("futs_bidp1")),
            "ask_quantity": _number(values.get("askp_rsqn1")),
            "bid_quantity": _number(values.get("bidp_rsqn1")),
        })
    return result


async def run_kis_night_futures_feed(
    publish: Callable[[dict[str, Any]], None],
    symbol: str | None = None,
) -> None:
    """Keep one read-only KIS market-data connection alive and publish snapshots."""
    target = (symbol or os.getenv("KIS_NIGHT_FUTURES_CODE") or front_month_code()).strip()
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()
    last = load_last_quote()
    if last and last.get("symbol") == target:
        # Show the last real price at once ("closed" until a live trade arrives).
        publish(dict(last, connected=True, status="closed", received_at_ms=int(time.time() * 1000)))
    if not app_key or not app_secret:
        publish({
            "connected": False, "status": "credentials_missing",
            "symbol": target, "received_at_ms": int(time.time() * 1000),
        })
        logging.warning("KIS night-futures feed disabled: API credentials are not configured.")
        return

    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect
    live = {"trade_ms": 0}

    async def rest_poller() -> None:
        """Outside trading hours (no live trade for 90 s) keep the last price over REST."""
        while True:
            if int(time.time() * 1000) - live["trade_ms"] > LIVE_WINDOW_MS:
                try:
                    quote = await asyncio.to_thread(fetch_last_price, app_key, app_secret, target)
                    if quote and int(time.time() * 1000) - live["trade_ms"] > LIVE_WINDOW_MS:
                        quote.update({"connected": True, "status": "closed",
                                      "received_at_ms": int(time.time() * 1000)})
                        publish(quote)
                        save_last_quote(quote)
                except Exception as exc:
                    logging.warning("KIS night-futures REST price unavailable (%s)", type(exc).__name__)
            await asyncio.sleep(REST_POLL_SECONDS)

    poller = asyncio.create_task(rest_poller())
    retry_delay = 5
    while True:
        encryption_keys: dict[str, dict[str, str]] = {}
        try:
            approval_key = await asyncio.to_thread(get_approval_key, app_key, app_secret)
            async with connect(
                WS_URL, ping_interval=None, open_timeout=15, close_timeout=5,
                max_size=1024 * 1024,
            ) as websocket:
                await websocket.send(subscription_message(approval_key, TRADES_TR_ID, target))
                await websocket.send(subscription_message(approval_key, QUOTE_TR_ID, target))
                publish({
                    "connected": True, "status": "connected", "symbol": target,
                    "received_at_ms": int(time.time() * 1000),
                })
                logging.info("KIS night-futures WebSocket connected; symbol=%s", target)
                retry_delay = 5
                async for raw in websocket:
                    if not isinstance(raw, str):
                        continue
                    if raw.startswith("{"):
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        header = payload.get("header") or {}
                        body = payload.get("body") or {}
                        response_tr_id = header.get("tr_id")
                        output = body.get("output") or {}
                        if response_tr_id and output.get("key") and output.get("iv"):
                            encryption_keys[response_tr_id] = {
                                "key": str(output["key"]), "iv": str(output["iv"]),
                            }
                        if response_tr_id == "PINGPONG":
                            await websocket.pong(raw.encode("utf-8"))
                        elif body and str(body.get("rt_cd", "0")) not in {"0", ""}:
                            logging.warning("KIS night-futures subscription response: %s",
                                            str(body.get("msg1") or "subscription_error")[:120])
                        continue
                    frame_parts = raw.split("|", 3)
                    frame_tr_id = frame_parts[1] if len(frame_parts) > 1 else ""
                    decoded = decode_realtime_frame(raw, target, encryption_keys.get(frame_tr_id))
                    if not decoded:
                        continue
                    now_ms = int(time.time() * 1000)
                    if decoded["tr_id"] == TRADES_TR_ID:
                        live["trade_ms"] = now_ms
                        save_last_quote(dict(decoded, source="kis:websocket"))
                    elif now_ms - live["trade_ms"] > LIVE_WINDOW_MS:
                        continue      # order-book updates alone do not replace the last price
                    decoded.update({
                        "connected": True,
                        "status": "live",
                        "source": "kis:websocket",
                        "received_at_ms": now_ms,
                    })
                    publish(decoded)
        except asyncio.CancelledError:
            poller.cancel()
            raise
        except Exception as exc:
            logging.warning("KIS night-futures feed disconnected (%s)", type(exc).__name__)
            if int(time.time() * 1000) - live["trade_ms"] <= LIVE_WINDOW_MS:
                # Keep the last price on screen; only the state changes.
                publish({"connected": False, "status": "disconnected", "symbol": target})
            await asyncio.sleep(retry_delay)
            retry_delay = min(60, retry_delay * 2)
