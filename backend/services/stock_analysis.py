from .market_levels import round_krw_tick
from ..analysis.price import build_price_indicators, build_price_result
from ..providers.market_price import fetch_daily_price_history, fetch_kr_stock_quote, fetch_us_stock_quote


def _format_bollinger_lines(*, is_krw, current_price, bollinger_60_2):
    lines = []
    if not bollinger_60_2 or current_price <= 0:
        return lines

    for label, key in (("상단", "upper"), ("중심", "middle"), ("하단", "lower")):
        level_price = float(bollinger_60_2.get(key) or 0)
        if level_price <= 0:
            continue

        level_gap_pct = ((level_price - current_price) / current_price) * 100
        level_arrow = "↗" if level_gap_pct >= 0 else "↘"
        level_text = f"{round_krw_tick(level_price):,}원" if is_krw else "$" + f"{level_price:,.2f}"

        breakout_text = ""
        if key == "upper" and current_price > level_price:
            breakout_text = "   🔥 상단 돌파"
        elif key == "lower" and current_price < level_price:
            breakout_text = "   ⚠ 하단 이탈"

        lines.append(
            f"{label}  {level_text}   {level_gap_pct:+.2f}% {level_arrow}{breakout_text}"
        )

    return lines


def fetch_stock_price_result(*, is_krw, ticker_symbol, clean_code=None):
    """현재가 원천 -> 가격 가공 -> 종목 가격 결과."""
    if is_krw:
        current, _diff, change_pct, high, low = fetch_kr_stock_quote(clean_code)
        price_result = build_price_result(
            is_krw=True,
            current=current,
            high=high,
            low=low,
            change_pct=change_pct,
        )
    else:
        current, previous, high, low = fetch_us_stock_quote(ticker_symbol)
        price_result = build_price_result(
            is_krw=False,
            current=current,
            previous=previous,
            high=high,
            low=low,
        )

    daily_rows = fetch_daily_price_history(ticker_symbol)
    indicators = build_price_indicators(price_result, daily_rows)

    result = dict(price_result)
    result["indicators"] = indicators
    result["price_tags"] = list(indicators.get("price_tags") or [])
    result["bollinger_lines"] = _format_bollinger_lines(
        is_krw=is_krw,
        current_price=result["current_price"],
        bollinger_60_2=indicators.get("bollinger_60_2"),
    )

    rsi_14 = indicators.get("rsi_14")
    ma20_gap_pct = indicators.get("ma20_gap_pct")
    result["first_reply_rsi"] = f"{rsi_14:.1f} RSI" if rsi_14 is not None else ""
    result["first_reply_ma20"] = (
        f"{ma20_gap_pct:+.2f}% {'↗' if ma20_gap_pct >= 0 else '↘'} 20일선"
        if ma20_gap_pct is not None
        else ""
    )
    return result
