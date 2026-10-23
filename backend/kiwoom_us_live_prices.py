"""Kiwoom FE-only US trade ticks -> existing Neon Top 20 prices (15s batch).

Dedicated read-only worker. Ranking and industry remain under usa20540/usa10100.
Only a tick for an exactly subscribed stock may update its existing ranking row.
No account, order, trading, news or AI API access. No raw packets logged.
"""
import asyncio
import datetime as dt
import json
import math
import os
import re
from zoneinfo import ZoneInfo

import psycopg
from backend.providers.kiwoom_us_quotes import issue_access_token

URL = "wss://api.kiwoom.com:10000/api/us/websocket"
EXCHANGES = {"ND", "NY", "NA"}
RANK_QUERY = """
SELECT s.id, e.symbol, i.exchange
FROM public.market_rank_snapshots s
JOIN public.market_rank_entries e ON e.snapshot_id=s.id
JOIN public.market_instruments i ON i.market=e.market AND i.symbol=e.symbol
WHERE s.source='kiwoom' AND s.market='US' AND s.rank_type='trading_value'
AND s.id=(SELECT id FROM public.market_rank_snapshots
          WHERE market='US' AND rank_type='trading_value' AND source='kiwoom'
          ORDER BY captured_at DESC,id DESC LIMIT 1)
ORDER BY e.rank LIMIT 20
"""

def _open_us_session():
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    return now.weekday() < 5 and dt.time(4, 0) <= now.time() < dt.time(20, 0)

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
        updates[symbol] = (abs(price), pct)
    return updates

def _ranked_symbols(dsn):
    with psycopg.connect(dsn, connect_timeout=6) as conn:
        with conn.cursor() as cur:
            cur.execute(RANK_QUERY)
            rows = cur.fetchall()
    if not rows:
        return None, {}
    sid = int(rows[0][0])
    selected = {}
    for _, symbol, exchange in rows:
        if (isinstance(symbol, str) and re.fullmatch(r"[A-Z0-9.\\-]{1,20}", symbol)
                and exchange in EXCHANGES):
            selected[symbol] = exchange
    return sid, selected

def _persist(dsn, latest):
    """Every 15 seconds, update only changed prices on existing Top-20 rows.

    A batch adds no snapshots/history and unchanged prices do not write rows.
    Receipt time is not represented as an exchange trade time.
    """
    if not latest:
        return 0
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    saved = 0
    with psycopg.connect(dsn, connect_timeout=6) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id FROM public.market_rank_snapshots
                WHERE source='kiwoom' AND market='US' AND rank_type='trading_value'
                ORDER BY captured_at DESC,id DESC LIMIT 1""")
            record = cur.fetchone()
            if record is None:
                return 0
            sid = record[0]
            for symbol, (price, pct) in latest.items():
                # Existing ranking is authoritative for symbol membership.
                cur.execute(
                    """UPDATE public.market_rank_entries
                       SET price=%s,
                           change_rate=COALESCE(%s,change_rate),
                           entry_payload=COALESCE(entry_payload,'{}'::jsonb)
                             || jsonb_build_object('live_price_at',%s,'live_price_source','kiwoom:FE')
                       WHERE snapshot_id=%s AND market='US' AND symbol=%s
                         AND (price IS DISTINCT FROM %s OR
                              (%s IS NOT NULL AND change_rate IS DISTINCT FROM %s))""",
                    (price, pct, now, sid, symbol, price, pct, pct),
                )
                saved += cur.rowcount
        conn.commit()
    return saved

async def _one_connection(dsn, initial):
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        from websockets.client import connect

    token = issue_access_token()
    async with connect(URL, open_timeout=10, close_timeout=3,
                       ping_interval=30, max_size=1048576) as ws:
        await ws.send(json.dumps({"trnm":"LOGIN","token":token}))
        login = None
        deadline = asyncio.get_running_loop().time() + 12
        while asyncio.get_running_loop().time() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=7))
            if msg.get("trnm") == "PING":
                await ws.send(json.dumps(msg))
                continue
            if msg.get("trnm") == "LOGIN":
                login = str(msg.get("return_code")) in ("0","0000")
                break
        if not login:
            print("US_FE_LOGIN=failed", flush=True)
            return

        snapshot_id, selected = initial
        if not selected:
            return
        def registration(group):
            return {"trnm":"REG", "grp_no":"1", "refresh":"1",
                    "data":[{"item":[{"jmcode":k,"stex_tp":v} for k,v in group.items()],
                             "type":["FE"]}]}
        await ws.send(json.dumps(registration(selected)))
        print("US_FE_REGISTERED_COUNT=" + str(len(selected)),flush=True)
        buf = {}
        previous_db_read = asyncio.get_running_loop().time()
        previous_flush = previous_db_read
        while _open_us_session():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=4)
                msg = json.loads(raw)
                if isinstance(msg, dict):
                    if msg.get("trnm") == "PING":
                        await ws.send(json.dumps(msg))
                    elif msg.get("trnm") == "REG" and str(msg.get("return_code",0)) not in ("0","0000"):
                        print("US_FE_REG=failed",flush=True)
                        return
                    else:
                        buf.update(_parse_price_event(msg, selected))
            except asyncio.TimeoutError:
                pass
            except ValueError:
                pass
            now = asyncio.get_running_loop().time()
            if buf and now - previous_flush >= 15:
                try:
                    saved = await asyncio.to_thread(_persist, dsn, buf)
                    if saved:
                        print("US_FE_PRICE_ROWS_UPDATED=" + str(saved),flush=True)
                    buf.clear()
                except Exception as exc:
                    print("US_FE_PERSIST_ERROR="+type(exc).__name__,flush=True)
                previous_flush = now
            if now - previous_db_read >= 55:
                try:
                    new_snapshot, new_selected = await asyncio.to_thread(_ranked_symbols, dsn)
                    if new_selected and (new_selected != selected or new_snapshot != snapshot_id):
                        if new_selected != selected:
                            await ws.send(json.dumps(registration(new_selected)))
                            print("US_FE_REGISTERED_COUNT=" + str(len(new_selected)),flush=True)
                        snapshot_id, selected = new_snapshot, new_selected
                except Exception as exc:
                    print("US_FE_RANK_CHECK_ERROR="+type(exc).__name__,flush=True)
                previous_db_read = now
        if buf:
            await asyncio.to_thread(_persist, dsn, buf)

async def main():
    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        print("US_FE_MISSING_DATABASE",flush=True)
        return 2
    while True:
        if not _open_us_session():
            await asyncio.sleep(60)
            continue
        try:
            initial = await asyncio.to_thread(_ranked_symbols, dsn)
            if initial[1]:
                await _one_connection(dsn, initial)
            else:
                print("US_FE_NO_RANKED_SYMBOLS",flush=True)
        except Exception as exc:
            print("US_FE_CONNECTION_ERROR="+type(exc).__name__,flush=True)
        await asyncio.sleep(12 if _open_us_session() else 60)

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()) or 0)
