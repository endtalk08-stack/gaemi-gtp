"""Shared Kiwoom US real-time feed helpers for the direct Render relay.

Symbol/exchange validation and the existing DigitalOcean local Top-20 snapshot only.
This module does not collect ticks or read/write Neon/Redis.
The active collector is backend.kiwoom_us_price_relay.
"""
import datetime as dt
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "wss://api.kiwoom.com:10000/api/us/websocket"
EXCHANGES = {"ND", "NY", "NA"}
LOCAL_TOP20_PATH = "/var/lib/gaemigtp-news/kiwoom-us-top20-news.json"

def _open_us_session():
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    # Include the overnight/day market as well as premarket, regular and after.
    # US trading week: Sunday 20:00 ET through Friday 20:00 ET.
    return (now.weekday() < 4 or
            (now.weekday() == 4 and now.time() < dt.time(20, 0)) or
            (now.weekday() == 6 and now.time() >= dt.time(20, 0)))

def _num(value):
    try:
        if isinstance(value, bool) or value is None:
            return None
        n = float(str(value).strip().replace(",", ""))
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None

def _parse_price_event(message, selected):
    """Whitelist accepted FE fields and exact registered ticker/exchange."""
    if not isinstance(message, dict) or message.get("trnm") != "REAL":
        return {}
    updates = {}
    for item in (message.get("data") if isinstance(message.get("data"), list) else []):
        if not isinstance(item, dict) or item.get("type") != "FE":
            continue
        raw = str(item.get("item") or "").strip().upper()
        symbol = raw if raw in selected else ""
        if not symbol:
            for candidate, exchange in selected.items():
                if raw == candidate + "." + exchange or raw == exchange + ":" + candidate:
                    symbol = candidate
                    break
        if not symbol:
            continue
        fields = item.get("values")
        if not isinstance(fields, dict):
            continue
        price = _num(fields.get("10"))
        pct = _num(fields.get("12"))
        if price is None or not 0 < abs(price) < 10000000:
            continue
        if pct is not None and not -100 < pct < 100000:
            pct = None
        # Official Kiwoom FE fields: 17=session high, 18=session low.
        # The sidebar and central metrics must share this exact FE update.
        high = _num(fields.get("17"))
        low = _num(fields.get("18"))
        high = abs(high) if high is not None and 0 < abs(high) < 10000000 else None
        low = abs(low) if low is not None and 0 < abs(low) < 10000000 else None
        if high is not None and low is not None and high < low:
            high, low = None, None
        updates[symbol] = (abs(price), pct, high, low)
    return updates

def _ranked_symbols(snapshot_path=None):
    """Read one complete Kiwoom Top-20 snapshot from DigitalOcean local storage."""
    path = Path(snapshot_path or LOCAL_TOP20_PATH)
    if path.is_symlink():
        raise ValueError("unsafe_local_ranking_path")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or data.get("source") != "kiwoom" or data.get("market") != "US"
            or data.get("rank_type") != "trading_value"):
        raise ValueError("invalid_local_kiwoom_snapshot")
    rows = data.get("items")
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("incomplete_local_kiwoom_top20")
    selected, ranks = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_local_kiwoom_row")
        rank = row.get("rank")
        symbol = row.get("symbol")
        exchange = row.get("exchange")
        if (type(rank) is not int or not 1 <= rank <= 20 or rank in ranks
                or not isinstance(symbol, str)
                or not re.fullmatch(r"[A-Z0-9.\\-]{1,20}", symbol)
                or symbol in selected or exchange not in EXCHANGES):
            raise ValueError("invalid_local_kiwoom_row")
        ranks.add(rank)
        selected[symbol] = exchange
    if ranks != set(range(1, 21)):
        raise ValueError("incomplete_local_kiwoom_top20")
    return data.get("captured_at"), selected

async def run_qqq_fe_stream(on_quote):
    """Keep one read-only QQQ FE subscription and publish ticks to a memory callback.

    The caller owns storage and client fan-out. No DB, disk, REST quote polling,
    account, order, or ranking calls are made here.
    """
    import asyncio
    from backend.providers.kiwoom_us_quotes import issue_access_token

    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect

    selected = {"QQQ": "ND"}
    retry_delay = 5
    while True:
        if not _open_us_session():
            await asyncio.sleep(60)
            continue
        try:
            token = issue_access_token()
            async with connect(
                URL, open_timeout=8, close_timeout=2,
                ping_interval=None, max_size=131072,
            ) as ws:
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
                        break
                if not login_ok:
                    raise RuntimeError("kiwoom_qqq_login_not_confirmed")

                await ws.send(json.dumps({
                    "trnm": "REG", "grp_no": "1", "refresh": "1",
                    "data": [{"item": [{"jmcode": "QQQ", "stex_tp": "ND"}],
                              "type": ["FE"]}],
                }))
                registered = False
                deadline = asyncio.get_running_loop().time() + 10
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=3)
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
                    elif trnm == "REG":
                        registered = str(frame.get("return_code", "")) in ("0", "0000")
                        break
                if not registered:
                    raise RuntimeError("kiwoom_qqq_registration_not_confirmed")

                print("KIWOOM_QQQ_FE_CONNECTED", flush=True)
                retry_delay = 5
                while True:
                    raw = await ws.recv()
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="replace")
                    frame = json.loads(raw)
                    if not isinstance(frame, dict):
                        continue
                    if str(frame.get("trnm", "")).upper() == "PING":
                        await ws.send(json.dumps(frame))
                        continue
                    updates = _parse_price_event(frame, selected)
                    quote = updates.get("QQQ")
                    if quote is None:
                        continue
                    price, change_pct, high, low = quote
                    on_quote({
                        "symbol": "QQQ",
                        "price": price,
                        "change_pct": change_pct,
                        "high": high,
                        "low": low,
                    })
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print("KIWOOM_QQQ_FE_RECONNECT=" + type(exc).__name__, flush=True)
            await asyncio.sleep(retry_delay)
            retry_delay = min(60, retry_delay * 2)

