"""One-shot QQQ-only Kiwoom FE probe. No DB, orders, or news worker dependency."""
import asyncio
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_quotes import credentials_configured, issue_access_token

WS_URI = "wss://api.kiwoom.com:10000/api/us/websocket"
WATCH_SECONDS = 12


def _safe_number(value):
    try:
        number = float(str(value).strip().replace(",", "").replace("+", ""))
        return number if -1e12 < number < 1e12 else None
    except (TypeError, ValueError):
        return None


def _env_names():
    return sorted(name for name in os.environ
                  if "PRICE" in name.upper() or "RELAY" in name.upper())


async def _probe(token):
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect

    now = dt.datetime.now(ZoneInfo("America/New_York"))
    print("QQQ_FE_ET=" + now.isoformat(timespec="seconds"), flush=True)
    async with connect(WS_URI, open_timeout=8, close_timeout=2,
                       ping_interval=None, max_size=131072) as ws:
        print("QQQ_FE_WS=connected", flush=True)
        await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
        login_ok = False
        for _ in range(5):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=7)
            except asyncio.TimeoutError:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            frame = json.loads(raw)
            if not isinstance(frame, dict):
                continue
            trnm = str(frame.get("trnm", "")).upper()
            if trnm == "PING":
                await ws.send(json.dumps(frame))
            elif trnm == "LOGIN":
                login_ok = str(frame.get("return_code", "")) in ("0", "0000")
                print("QQQ_FE_LOGIN=" + ("ok" if login_ok else "rejected"), flush=True)
                break
        if not login_ok:
            print("QQQ_FE_RESULT=login_not_confirmed", flush=True)
            return 3

        await ws.send(json.dumps({
            "trnm": "REG", "grp_no": "1", "refresh": "1",
            "data": [{"item": [{"jmcode": "QQQ", "stex_tp": "ND"}],
                      "type": ["FE"]}],
        }))
        registered = False
        deadline = asyncio.get_running_loop().time() + WATCH_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=min(3, max(0.1, deadline - asyncio.get_running_loop().time()))
                )
            except asyncio.TimeoutError:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            frame = json.loads(raw)
            if not isinstance(frame, dict):
                continue
            trnm = str(frame.get("trnm", "")).upper()
            if trnm == "PING":
                await ws.send(json.dumps(frame))
                continue
            if trnm == "REG":
                registered = str(frame.get("return_code", "")) in ("0", "0000")
                print("QQQ_FE_REG=" + ("ok" if registered else "rejected"), flush=True)
                if not registered:
                    print("QQQ_FE_RESULT=registration_rejected", flush=True)
                    return 4
            if trnm != "REAL":
                continue
            rows = frame.get("data")
            if not isinstance(rows, list):
                continue
            for row in rows[:20]:
                if not isinstance(row, dict) or str(row.get("type", "")).upper() != "FE":
                    continue
                item = str(row.get("item", "")).upper()
                if item not in ("QQQ", "QQQ.ND", "ND:QQQ"):
                    continue
                values = row.get("values")
                if not isinstance(values, dict):
                    continue
                price = _safe_number(values.get("10"))
                change = _safe_number(values.get("12"))
                high = _safe_number(values.get("17"))
                low = _safe_number(values.get("18"))
                if price is None or price == 0:
                    continue
                event = {
                    "symbol": "QQQ", "price": abs(price),
                    "change_pct": change,
                    "high": abs(high) if high not in (None, 0) else None,
                    "low": abs(low) if low not in (None, 0) else None,
                }
                print("QQQ_FE_TICK=" + json.dumps(event, separators=(",", ":")), flush=True)
                print("QQQ_FE_RESULT=live_tick_received", flush=True)
                return 0
        print("QQQ_FE_RESULT=" + ("registered_no_tick_in_window" if registered
                                  else "registration_unconfirmed"), flush=True)
        return 0 if registered else 5


def main():
    names = _env_names()
    print("QQQ_FE_RELAY_ENV_NAMES=" + ",".join(names), flush=True)
    if not credentials_configured():
        print("QQQ_FE_ERROR=kiwoom_credentials_missing", flush=True)
        return 2
    try:
        token = issue_access_token()
        print("QQQ_FE_OAUTH=ok", flush=True)
        return asyncio.run(_probe(token))
    except Exception as exc:
        print("QQQ_FE_ERROR_TYPE=" + type(exc).__name__, flush=True)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
