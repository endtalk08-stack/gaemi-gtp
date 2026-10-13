"""Menu-specific market ranking result built from the shared raw price provider.

No separate ticker-by-ticker scraping, estimated trading value, or database writes.
"""
import math

from ..providers.market_industry import get_stock_industries
from ..providers.market_price import (
    fetch_kr_trading_value_ranking_raw, fetch_us_trading_value_ranking_raw,
    fetch_kr_popular_ranking_raw, fetch_us_popular_ranking_raw,
)


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


def _with_stock_industries(items, market):
    """Join a shared Naver industry map by itemCode, across all ranking menus."""
    if not items:
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
    return _with_stock_industries(_normalize_kr_stock_rows(raw, limit), "kr")


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
            "industry": _industry_from_entry(entry),
            "price": price,
            "change_pct": change,
            "trading_value": amount,
            "trading_value_text": amount_label,
        })
    return items


def build_us_trading_value_result(limit=20):
    """Normalize USA ranking as USD rows; do not infer values from volume."""
    raw = fetch_us_trading_value_ranking_raw(limit=limit)
    return _with_stock_industries(_normalize_us_stock_rows(raw, limit), "us")


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
            "industry": _industry_from_entry(entry),
            "price": price, "change_pct": change,
            "trading_value": amount, "trading_value_text": amount_label,
        })
    return items


def build_kr_popular_result(limit=20):
    """Use the same KR normalization as trading value; ranks are source ordered."""
    rows = _normalize_kr_stock_rows(fetch_kr_popular_ranking_raw(limit=limit), limit)
    return _with_stock_industries(rows, "kr")


def build_us_popular_result(limit=20):
    """Use the same USA normalization, without inferring popularity metrics."""
    rows = _normalize_us_stock_rows(fetch_us_popular_ranking_raw(limit=limit), limit)
    return _with_stock_industries(rows, "us")
