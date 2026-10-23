"""One NVDA-only, 14-second, read-only Kiwoom US FE WebSocket probe.

Only LOGIN and REG FE for NVDA (ND), no order/account operations.
Logs only field-allowlisted market values; no token, full frames or headers.
An empty tick stream outside trading hours is not falsely called live.
"""
import asyncio
import datetime as dt
import json
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_quotes import issue_access_token

WS_URI = "wss://api.kiwoom.com:10000/api/us/websocket"
LOGIN_TIMEOUT = 7
WATCH_SECONDS = 14

def _safe_number(raw):
    try:
        number = float(str(raw).strip().replace(",", ""))
        if not -1e12 < number < 1e12:
            return None
        return number
    except (TypeError, ValueError):
        return None

def _packet(payload):
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None

async def _read(ws, seconds):
    raw = await asyncio.wait_for(ws.recv(), timeout=seconds)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return _packet(raw)

async def _probe(token):
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect
    now_et = dt.datetime.now(ZoneInfo("America/New_York"))
    print("KIWOOM_FE_PROBE_ET=" + now_et.isoformat(timespec="seconds"), flush=True)
    try:
        async with connect(
            WS_URI, open_timeout=8, close_timeout=2, ping_interval=None, max_size=131072
        ) as ws:
            print("KIWOOM_FE_WS_CONNECTED=true", flush=True)
            await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
            login_ok = False
            for _ in range(5):
                frame = await _read(ws, LOGIN_TIMEOUT)
                if frame is None:
                    continue
                trnm = str(frame.get("trnm", "")).upper()
                if trnm == "PING":
                    await ws.send(json.dumps(frame))
                    continue
                if trnm == "LOGIN":
                    code = str(frame.get("return_code", "unknown"))
                    login_ok = code in ("0", "0000")
                    print("KIWOOM_FE_LOGIN_ACK=" + ("ok" if login_ok else "rejected"), flush=True)
                    break
                print("KIWOOM_FE_LOGIN_UNEXPECTED_PACKET=" + trnm[:15], flush=True)
                break
            if not login_ok:
                print("KIWOOM_FE_PROBE_RESULT=login_not_confirmed", flush=True)
                return 4

            packet = {
                "trnm": "REG", "grp_no": "1", "refresh": "1",
                "data": [{"item": [{"jmcode": "NVDA", "stex_tp": "ND"}], "type": ["FE"]}],
            }
            await ws.send(json.dumps(packet))
            print("KIWOOM_FE_NVDA_REG_SENT=true", flush=True)
            reg_ok = False
            seen_real = 0
            seen_fe = 0
            captured = 0
            loop = asyncio.get_running_loop()
            deadline = loop.time() + WATCH_SECONDS
            while loop.time() < deadline:
                try:
                    frame = await _read(ws, min(3, max(0.1, deadline-loop.time())))
                except TimeoutError:
                    continue
                if frame is None:
                    continue
                trnm = str(frame.get("trnm", "")).upper()
                if trnm == "PING":
                    await ws.send(json.dumps(frame))
                    continue
                if trnm == "REG":
                    code = str(frame.get("return_code", "unknown"))
                    reg_ok = code in ("0", "0000")
                    print("KIWOOM_FE_REG_ACK=" + ("ok" if reg_ok else "rejected_or_unknown"), flush=True)
                    if not reg_ok:
                        print("KIWOOM_FE_PROBE_RESULT=registration_rejected", flush=True)
                        return 5
                elif trnm == "REAL":
                    seen_real += 1
                    rows = frame.get("data")
                    if not isinstance(rows, list):
                        continue
                    for row in rows[:20]:
                        if not isinstance(row, dict) or str(row.get("type", "")).upper() != "FE":
                            continue
                        seen_fe += 1
                        name = str(row.get("item", "")).upper()
                        if name and not name.startswith("NVDA"):
                            continue
                        values = row.get("values")
                        if not isinstance(values, dict):
                            continue
                        price = _safe_number(values.get("10"))
                        direction = _safe_number(values.get("12"))
                        session = str(values.get("290") or "")[:16]
                        trade_time = str(values.get("51020") or "")[:16]
                        trade_date = str(values.get("22") or "")[:12]
                        print("KIWOOM_FE_NVDA_EVENT=" + json.dumps({
                            "current": abs(price) if price not in (None, 0) else None,
                            "change_pct": direction,
                            "session_code_290": session or None,
                            "local_trade_time_51020": trade_time or None,
                            "trade_date_22": trade_date or None,
                            "has_price": "10" in values,
                        }, ensure_ascii=False, sort_keys=True), flush=True)
                        captured += 1
                        if captured >= 1:
                            break
                if captured:
                    break
            print("KIWOOM_FE_WS_SUMMARY=" + json.dumps({
                "login_ok": login_ok, "registration_acknowledged": reg_ok,
                "real_frames": seen_real, "fe_events": seen_fe, "nvda_price_events": captured,
                "watch_seconds": WATCH_SECONDS,
            }, sort_keys=True), flush=True)
            if captured:
                print("KIWOOM_FE_PROBE_RESULT=live_tick_received", flush=True)
            elif reg_ok:
                print("KIWOOM_FE_PROBE_RESULT=registered_no_tick_in_window", flush=True)
            else:
                print("KIWOOM_FE_PROBE_RESULT=registration_unconfirmed", flush=True)
            return 0 if reg_ok or captured else 6
    except Exception as exc:
        print("KIWOOM_FE_PROBE_ERROR_TYPE=" + type(exc).__name__, flush=True)
        return 7

def main():
    try:
        token = issue_access_token()
    except Exception as exc:
        print("KIWOOM_FE_AUTH_ERROR_TYPE=" + type(exc).__name__, flush=True)
        return 2
    print("KIWOOM_FE_OAUTH_OK=true", flush=True)
    return asyncio.run(_probe(token))


if __name__ == "__main__":
    raise SystemExit(main())
