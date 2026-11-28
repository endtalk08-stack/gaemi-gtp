#!/usr/bin/env python3
"""Read-only KIS KRX night-futures realtime feed tester.

Subscribes only to market data. It does not place or modify orders.
Credentials are read from environment variables and must never be committed.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any

import requests
import websocket

REST_BASE = "https://openapi.koreainvestment.com:9443"
WS_URL = "ws://ops.koreainvestment.com:21000"
DEFAULT_SYMBOL = "101W9000"  # Symbol shown in the KIS official sample
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


def get_approval_key(app_key: str, app_secret: str) -> str:
    """Issue a production WebSocket approval key."""
    response = requests.post(
        f"{REST_BASE}/oauth2/Approval",
        headers={"content-type": "application/json; charset=utf-8"},
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    approval_key = payload.get("approval_key")
    if not approval_key:
        raise RuntimeError(f"KIS approval-key response did not include approval_key: {payload}")
    return approval_key


def subscription_message(approval_key: str, tr_id: str, symbol: str) -> str:
    """Build the KIS WebSocket subscription envelope."""
    return json.dumps(
        {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {"input": {"tr_id": tr_id, "tr_key": symbol}},
        },
        ensure_ascii=False,
    )


def decode_realtime_frame(frame: str) -> dict[str, Any] | None:
    """Decode a KIS pipe/caret-delimited realtime frame into named fields."""
    parts = frame.split("|", 3)
    if len(parts) < 4 or parts[0] not in {"0", "1"}:
        return None

    tr_id = parts[1]
    raw_values = parts[3].split("^")
    if tr_id == TRADES_TR_ID:
        field_names = TRADE_FIELDS
    elif tr_id == QUOTE_TR_ID:
        field_names = QUOTE_FIELDS
    else:
        return {"tr_id": tr_id, "raw": frame}

    values = dict(zip(field_names, raw_values))
    result: dict[str, Any] = {
        "tr_id": tr_id,
        "symbol": values.get("futs_shrn_iscd", parts[2]),
        "time": values.get("bsop_hour"),
        "values": values,
    }
    if tr_id == TRADES_TR_ID:
        result.update(
            last_price=values.get("futs_prpr"),
            change_percent=values.get("futs_prdy_ctrt"),
            last_volume=values.get("last_cnqn"),
            accumulated_volume=values.get("acml_vol"),
        )
    else:
        result.update(
            best_ask=values.get("futs_askp1"),
            best_bid=values.get("futs_bidp1"),
            ask_quantity=values.get("askp_rsqn1"),
            bid_quantity=values.get("bidp_rsqn1"),
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="KIS KRX night-futures realtime quote tester")
    parser.add_argument("--symbol", default=os.getenv("KIS_NIGHT_FUTURES_CODE", DEFAULT_SYMBOL))
    parser.add_argument("--trades-only", action="store_true")
    parser.add_argument("--quotes-only", action="store_true")
    args = parser.parse_args()

    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    if not app_key or not app_secret:
        logging.error("Set KIS_APP_KEY and KIS_APP_SECRET as environment variables.")
        return 2
    if args.trades_only and args.quotes_only:
        parser.error("--trades-only and --quotes-only cannot be used together")

    subscriptions = []
    if not args.quotes_only:
        subscriptions.append(TRADES_TR_ID)
    if not args.trades_only:
        subscriptions.append(QUOTE_TR_ID)

    logging.info("Requesting production WebSocket approval key...")
    approval_key = get_approval_key(app_key, app_secret)
    logging.info("Approval key issued. Connecting to KIS production WebSocket.")
    logging.info("Symbol: %s | subscriptions: %s", args.symbol, ", ".join(subscriptions))

    def on_open(ws: websocket.WebSocketApp) -> None:
        for tr_id in subscriptions:
            ws.send(subscription_message(approval_key, tr_id, args.symbol))
            logging.info("Subscribed: %s / %s", tr_id, args.symbol)

    def on_message(ws: websocket.WebSocketApp, message: str) -> None:
        if message.startswith("{"):
            try:
                payload = json.loads(message)
                body = payload.get("body") or {}
                if body:
                    logging.info("KIS response: %s %s", body.get("rt_cd"), body.get("msg1"))
                elif (payload.get("header") or {}).get("tr_id") == "PINGPONG":
                    ws.send(message)
            except json.JSONDecodeError:
                logging.info("KIS message: %s", message)
            return

        decoded = decode_realtime_frame(message)
        if decoded is None:
            logging.info("Unparsed KIS frame: %s", message)
            return

        if decoded["tr_id"] == TRADES_TR_ID:
            logging.info(
                "[체결] %s %s 현재가=%s 등락률=%s%% 체결량=%s 누적량=%s",
                decoded.get("symbol"), decoded.get("time"),
                decoded.get("last_price"), decoded.get("change_percent"),
                decoded.get("last_volume"), decoded.get("accumulated_volume"),
            )
        elif decoded["tr_id"] == QUOTE_TR_ID:
            logging.info(
                "[호가] %s %s 매도1=%s(%s) 매수1=%s(%s)",
                decoded.get("symbol"), decoded.get("time"),
                decoded.get("best_ask"), decoded.get("ask_quantity"),
                decoded.get("best_bid"), decoded.get("bid_quantity"),
            )

    def on_error(ws: websocket.WebSocketApp, error: Any) -> None:
        logging.error("WebSocket error: %s", error)

    def on_close(ws: websocket.WebSocketApp, status_code: Any, message: Any) -> None:
        logging.warning("WebSocket closed: code=%s message=%s", status_code, message)

    while True:
        app = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        try:
            app.run_forever(ping_interval=30, ping_timeout=10)
        except KeyboardInterrupt:
            logging.info("Stopped by user.")
            return 0
        except Exception:
            logging.exception("WebSocket connection failed")
        logging.info("Reconnecting in 5 seconds...")
        time.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    sys.exit(main())
