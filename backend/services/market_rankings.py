"""Menu-specific market ranking result built from the shared raw price provider.

No separate ticker-by-ticker scraping, estimated trading value, or database writes.
"""
import math
import os
import re
import threading
import time

from ..providers.market_industry import get_stock_industries
from ..providers.market_price import (
    fetch_kr_trading_value_ranking_raw, fetch_us_trading_value_ranking_raw,
    fetch_kr_popular_ranking_raw, fetch_us_popular_ranking_raw,
)


# These are the existing processed menu results, retained for central-chat
# selection. AI lookups never trigger Naver collection.
_MARKET_RESULTS = {}
_MARKET_RESULTS_LOCK = threading.Lock()
_SELECTION_TTL = 15 * 60


def _remember_market_result(market, menu, rows):
    with _MARKET_RESULTS_LOCK:
        _MARKET_RESULTS[(market, menu)] = (
            time.monotonic(), [dict(row) for row in rows],
        )


def get_market_selection(market, menu, symbol, stock=None):
    """Read one previously produced menu row by stock code, without collection."""
    if market not in ("kr", "us") or menu not in ("popular", "value"):
        return None
    code = str(symbol or "").strip().upper()
    pattern = r"[0-9]{6}" if market == "kr" else r"[A-Z0-9.^_-]{1,32}"
    if not re.fullmatch(pattern, code):
        return None
    with _MARKET_RESULTS_LOCK:
        stored = _MARKET_RESULTS.get((market, menu))
        if not stored or time.monotonic() - stored[0] >= _SELECTION_TTL:
            return None
        match = next((r for r in stored[1] if r["symbol"].upper() == code), None)
        if not match:
            return None
        row = dict(match)
    if stock is not None and row["name"].casefold() != str(stock).strip().casefold():
        return None
    return {**row, "market": market, "menu": menu,
            "currency": "KRW" if market == "kr" else "USD"}


def get_market_menu_rows(market, menu, sort="source"):
    """Read previously produced rows in the same order as the sidebar."""
    if market not in ("kr", "us") or menu not in ("popular", "value"):
        return []
    with _MARKET_RESULTS_LOCK:
        stored = _MARKET_RESULTS.get((market, menu))
        if not stored or time.monotonic() - stored[0] >= _SELECTION_TTL:
            return []
        rows = [dict(row) for row in stored[1]]
    if sort == "change_pct":
        rows.sort(key=lambda row: -(
            row["change_pct"] if isinstance(row.get("change_pct"), (float, int))
            else float("-inf")
        ))
    for index, row in enumerate(rows):
        row["display_rank"] = index + 1 if sort == "change_pct" else row.get("rank")
        row["sort"] = "change_pct" if sort == "change_pct" else "source"
    return rows


def analysis_ticker_for_selection(selection):
    """Use a source-verified code and market to avoid name-based misrouting."""
    if not selection:
        return None
    if selection["market"] == "kr":
        code = selection["symbol"]
        exchange = str(selection.get("market_type") or "").upper()
        if "KOSDAQ" in exchange or exchange == "KQ":
            return code + ".KQ"
        if "KOSPI" in exchange or exchange == "KS":
            return code + ".KS"
        return None

    symbol = str(selection.get("analysis_symbol") or selection["symbol"]).upper()
    if not re.fullmatch(r"[A-Z0-9.^_-]{1,32}", symbol):
        return None
    if not selection.get("analysis_symbol") and symbol.endswith((".O", ".N")):
        return symbol[:-2]
    return symbol


def _number(value):
    if isinstance(value, bool) or value is None or isinstance(value, dict):
        return None
    try:
        number = float(str(value).strip().replace(",", "").replace("%", "").replace("+", ""))
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _field(objects, names):
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        for name in names:
            value = obj.get(name)
            if value is not None and value != "":
                return value
    return None


def _industry_from_entry(entry):
    """Use only industry labels already inside the same Naver ranking payload.

    Never look up a symbol separately or infer an industry from other fields.
    """
    price = entry.get("price")
    stock = entry.get("stock")
    sources = [entry, stock, price]
    if isinstance(price, dict):
        sources.extend((price.get("krx"), price.get("nxt")))
    sources.extend((entry.get("krx"), entry.get("nxt")))

    names = ("industryName", "sectorName", "upjongName",
             "industryNameEng", "sectorNameEng",
             "industry", "sector", "upjong")
    for source in sources:
        if not isinstance(source, dict):
            continue
        for name in names:
            label = source.get(name)
            if isinstance(label, str) and label.strip():
                return label.strip()
    return None


def _with_stock_industries(items, market, menu):
    """Join the shared industry map, then retain this same menu result for chat."""
    if items is None:
        return None
    if not items:
        _remember_market_result(market, menu, [])
        return items
    known = {
        item["symbol"]: item["industry"]
        for item in items if item.get("industry")
    }
    labels = get_stock_industries(
        market, [item["symbol"] for item in items], known=known,
    )
    for item in items:
        if not item.get("industry"):
            item["industry"] = labels.get(item["symbol"])
    _remember_market_result(market, menu, items)
    if market == "us":
        # Register only the rows already fetched; do not change ranking or quotes.
        from .stock_identity_store import register_us_ranking_instruments
        register_us_ranking_instruments(items)
    return items


def _rank(entry, position):
    """Use the source ranking where available, preserving real rank gaps."""
    value = _field([entry], ("ranking", "rank"))
    try:
        rank = int(value)
        return rank if rank > 0 else position
    except (TypeError, ValueError):
        return position


def _price_sources(item):
    """Naver uses both flat and nested KRX/NXT price objects across versions."""
    price = item.get("price")
    sources = []
    for candidate in (
        item.get("krx"),
        price.get("krx") if isinstance(price, dict) else None,
        price,
        item,
    ):
        if isinstance(candidate, dict):
            sources.append(candidate)
    return sources


def build_kr_trading_value_result(limit=20):
    """Return an ordered result for the KR trading-value menu.

    Never manufacture price/percent/value when source fields are absent.
    None denotes source failure; [] denotes a valid but empty source list.
    """
    raw = fetch_kr_trading_value_ranking_raw(limit=limit)
    return _with_stock_industries(_normalize_kr_stock_rows(raw, limit), "kr", "value")


def _normalize_kr_stock_rows(raw, limit):
    if raw is None:
        return None

    items = []
    for entry in raw.get("items", [])[:limit]:
        if not isinstance(entry, dict):
            continue
        stock = entry.get("stock")
        price_object = entry.get("price")
        identity = [entry]
        if isinstance(stock, dict):
            identity.append(stock)
        if isinstance(price_object, dict):
            identity.append(price_object)
        name = _field(identity, ("stockName", "itemName", "itemname", "name", "displayName"))
        symbol = _field(identity, ("itemCode", "itemcode", "code", "symbol"))
        if not name or not symbol:
            continue

        quote = _price_sources(entry)
        price = _number(_field(quote, ("closePrice", "currentPrice", "nowPrice", "tradePrice", "price")))
        change = _number(_field(quote, ("fluctuationsRatio", "prevChangeRate", "changeRate", "changePct")))
        amount_raw = _field(
            quote,
            ("accumulatedTradingValue", "tradingValue", "tradingAmount"),
        )
        amount = _number(amount_raw)
        amount_label = (
            str(amount_raw).strip()
            if amount is None and isinstance(amount_raw, str) and amount_raw.strip()
            else None
        )

        items.append({
            "rank": _rank(entry, len(items) + 1),
            "name": str(name),
            "symbol": str(symbol),
            "market_type": str(_field(identity, ("marketType",)) or ""),
            "industry": _industry_from_entry(entry),
            "price": price,
            "change_pct": change,
            "trading_value": amount,
            "trading_value_text": amount_label,
        })
    return items


def _read_kiwoom_us_value_rows():
    """Render reads the existing DigitalOcean-collected Neon Top 20 snapshot.

    No market-data HTTP calls, provider tokens, ranking guesses or database writes.
    """
    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        return None
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT e.rank, e.symbol, e.display_name,
                           e.price, e.change_rate, e.trading_value, e.volume,
                           i.sector
                      FROM public.market_rank_entries e
                      JOIN public.market_instruments i
                        ON i.market=e.market AND i.symbol=e.symbol
                     WHERE e.market='US' AND e.snapshot_id=(
                        SELECT s.id FROM public.market_rank_snapshots s
                         WHERE s.source='kiwoom' AND s.market='US'
                           AND s.rank_type='trading_value'
                         ORDER BY s.captured_at DESC,s.id DESC LIMIT 1
                     )
                     ORDER BY e.rank LIMIT 20
                """)
                records = cur.fetchall()
    except Exception as exc:
        print("[market rank] kiwoom snapshot read failed: " + type(exc).__name__, flush=True)
        return None
    # Reject an incomplete source list rather than replacing it with Naver.
    if len(records) != 20 or [int(row[0]) for row in records] != list(range(1, 21)):
        return None
    items = []
    for rank, symbol, name, price, change, amount, volume, sector in records:
        stock_price = _number(price)
        pct = _number(change)
        if not symbol or not name or stock_price is None or stock_price <= 0 or pct is None:
            return None
        items.append({
            "rank": int(rank), "name": str(name), "symbol": str(symbol),
            "analysis_symbol": str(symbol), "industry": str(sector) if sector else None,
            "price": stock_price, "change_pct": pct,
            "trading_value": _number(amount),
            "trading_value_text": None, "volume": int(volume) if volume is not None else None,
        })
    return items


def build_us_trading_value_result(limit=20):
    """Read DigitalOcean's Kiwoom-ranked rows from Neon; never collect on Render."""
    rows = _read_kiwoom_us_value_rows()
    if rows is None:
        return None
    _remember_market_result("us", "value", rows)
    return rows[:max(0, min(int(limit), 20))]


def _normalize_us_stock_rows(raw, limit):
    if raw is None:
        return None
    items = []
    for entry in raw.get("items", [])[:limit]:
        if not isinstance(entry, dict):
            continue
        stock = entry.get("stock")
        price_object = entry.get("price")
        identity = [entry]
        if isinstance(stock, dict):
            identity.append(stock)
        if isinstance(price_object, dict):
            identity.append(price_object)
        name = _field(identity, ("stockName", "itemName", "name", "displayName", "stockNameEng", "englishName"))
        symbol = _field(identity, ("itemCode", "reutersCode", "symbol", "code"))
        if not name or not symbol:
            continue
        p = entry.get("price")
        quote = [p, entry] if isinstance(p, dict) else [entry]
        price = _number(_field(quote, ("closePrice", "currentPrice", "tradePrice", "nowPrice", "price")))
        change = _number(_field(quote, ("fluctuationsRatio", "changeRate", "prevChangeRate", "changePct")))
        amount_raw = _field(quote, ("accumulatedTradingValue", "tradingValue", "tradingAmount"))
        amount = _number(amount_raw)
        amount_label = (str(amount_raw).strip()
                        if amount is None and isinstance(amount_raw, str) and amount_raw.strip()
                        else None)
        items.append({
            "rank": _rank(entry, len(items) + 1), "name": str(name), "symbol": str(symbol),
            "analysis_symbol": str(_field(identity, ("symbolCode",)) or ""),
            "industry": _industry_from_entry(entry),
            "price": price, "change_pct": change,
            "trading_value": amount, "trading_value_text": amount_label,
        })
    return items


def build_kr_popular_result(limit=20):
    """Use the same KR normalization as trading value; ranks are source ordered."""
    rows = _normalize_kr_stock_rows(fetch_kr_popular_ranking_raw(limit=limit), limit)
    return _with_stock_industries(rows, "kr", "popular")


def build_us_popular_result(limit=20):
    """Use the same USA normalization, without inferring popularity metrics."""
    rows = _normalize_us_stock_rows(fetch_us_popular_ranking_raw(limit=limit), limit)
    return _with_stock_industries(rows, "us", "popular")
