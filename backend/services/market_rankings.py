"""Menu-specific market ranking result built from the shared raw price provider.

No separate ticker-by-ticker scraping, estimated trading value, or database writes.
"""
import math
import re
import threading
import time

from ..providers.market_industry import get_stock_industries
from ..providers.market_price import fetch_us_trading_value_ranking_raw


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
    if market != "us" or menu != "value":
        return None
    code = str(symbol or "").strip().upper()
    pattern = r"[A-Z0-9.^_-]{1,32}"
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
    return {**row, "market": market, "menu": menu, "currency": "USD"}


def get_market_menu_rows(market, menu, sort="source"):
    """Read previously produced rows in the same order as the sidebar."""
    if market != "us" or menu != "value":
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
    if market == "us":
        # Reuse the Neon-backed ticker/company match rather than a sidebar
        # list of company names and logos.
        from .stock_identity_store import register_us_ranking_instruments
        from .news_identity_registry import resolve_us_news_identity
        from backend.analysis.news.stock_identity import (
            _VERIFIED, normalize_us_ticker,
        )
        register_us_ranking_instruments(items)
        for item in items:
            ticker = normalize_us_ticker(item["symbol"])
            identity = resolve_us_news_identity(item["name"], symbol=item["symbol"])
            matched = identity["status"] == "verified" and identity["ticker"] == ticker
            # News matching is deliberately unchanged. A stock absent from
            # the known-company map can still have a valid exchange ticker:
            # it may request a logo by that exact ticker without being allowed
            # to borrow another company's articles or AI analysis.
            logo_candidate = bool(ticker and (matched or ticker not in _VERIFIED))
            item["mark_ticker"] = ticker if matched else ""
            item["logo_lookup_ticker"] = ticker if logo_candidate else ""
            item["identity_status"] = "verified" if matched else "pending"
    _remember_market_result(market, menu, items)
    return items


def _rank(entry, position):
    """Use the source ranking where available, preserving real rank gaps."""
    value = _field([entry], ("ranking", "rank"))
    try:
        rank = int(value)
        return rank if rank > 0 else position
    except (TypeError, ValueError):
        return position


def build_us_trading_value_result(limit=20):
    """Normalize USA ranking as USD rows; do not infer values from volume."""
    raw = fetch_us_trading_value_ranking_raw(limit=limit)
    return _with_stock_industries(_normalize_us_stock_rows(raw, limit), "us", "value")


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
