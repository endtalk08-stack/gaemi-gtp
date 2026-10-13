"""Menu-specific market ranking result built from the shared raw price provider.

No separate ticker-by-ticker scraping, estimated trading value, or database writes.
"""
import math

from ..providers.market_price import fetch_kr_trading_value_ranking_raw, fetch_us_trading_value_ranking_raw


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
    if raw is None:
        return None

    items = []
    for entry in raw.get("items", [])[:limit]:
        if not isinstance(entry, dict):
            continue
        stock = entry.get("stock")
        identity = [entry, stock] if isinstance(stock, dict) else [entry]
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
            "rank": len(items) + 1,
            "name": str(name),
            "symbol": str(symbol),
            "price": price,
            "change_pct": change,
            "trading_value": amount,
            "trading_value_text": amount_label,
        })
    return items


def build_us_trading_value_result(limit=20):
    """Normalize USA ranking as USD rows; do not infer values from volume."""
    raw = fetch_us_trading_value_ranking_raw(limit=limit)
    if raw is None:
        return None
    items = []
    for entry in raw.get("items", [])[:limit]:
        if not isinstance(entry, dict):
            continue
        stock = entry.get("stock")
        identity = [entry, stock] if isinstance(stock, dict) else [entry]
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
            "rank": len(items) + 1, "name": str(name), "symbol": str(symbol),
            "price": price, "change_pct": change,
            "trading_value": amount, "trading_value_text": amount_label,
        })
    return items
