"""Read-only KIS KRX night-futures WebSocket feed for the quote relay."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import time
import urllib.request
from typing import Any, Callable

from cryptography.hazmat.primitives import padding as symmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

REST_BASE = "https://openapi.koreainvestment.com:9443"
WS_URL = "ws://ops.koreainvestment.com:21000"
DEFAULT_SYMBOL = "101W9000"
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
    target = (symbol or os.getenv("KIS_NIGHT_FUTURES_CODE") or DEFAULT_SYMBOL).strip()
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()
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
                    decoded.update({
                        "connected": True,
                        "status": "live" if decoded["tr_id"] == TRADES_TR_ID else "connected",
                        "source": "kis:websocket",
                        "received_at_ms": int(time.time() * 1000),
                    })
                    publish(decoded)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.warning("KIS night-futures feed disconnected (%s)", type(exc).__name__)
            publish({
                "connected": False, "status": "disconnected", "symbol": target,
                "received_at_ms": int(time.time() * 1000),
            })
            await asyncio.sleep(retry_delay)
            retry_delay = min(60, retry_delay * 2)
