from datetime import date, datetime
from math import isfinite
from zoneinfo import ZoneInfo

from ..analysis.price import build_price_indicators, build_price_result
from ..providers.market_price import (
    fetch_daily_price_history,
    fetch_kr_stock_quote,
)
from .us_price_push import read_fresh_us_quote


_SPACER = "\u00a0\u00a0\u00a0"


def _format_gap(value):
    if value is None:
        return ""
    try:
        gap = float(value)
    except (TypeError, ValueError):
        return ""
    arrow = "↗" if gap >= 0 else "↘"
    return f"{gap:+.2f}% {arrow}"


def _build_52w_lines(week_52):
    if not week_52:
        return []

    try:
        position = float(week_52.get("position"))
        high_gap_pct = float(week_52.get("high_gap_pct"))
    except (TypeError, ValueError):
        return []

    width = 20
    marker_index = max(0, min(width - 1, int(round(position * (width - 1)))))
    bar = ("█" * marker_index) + "●" + ("─" * (width - 1 - marker_index))
    bar_line = f"52주\u00a0\u00a0저가\u00a0├{bar}┤\u00a0고가"

    # NBSP를 사용해 채팅의 pre-line 렌더링에서도 현재 위치 들여쓰기를 유지한다.
    current_line = ("\u00a0" * (10 + marker_index)) + "현재"
    if week_52.get("is_new_high"):
        status_line = ("\u00a0" * (7 + marker_index)) + f"52주 신고가 {high_gap_pct:+.2f}%"
    else:
        status_line = ("\u00a0" * (7 + marker_index)) + f"신고가까지 {high_gap_pct:+.2f}%"

    return [bar_line, current_line, status_line]


def _build_first_reply_metrics(price_result, indicators):
    first_parts = []

    high_gap = _format_gap(price_result.get("high_gap_pct"))
    low_gap = _format_gap(price_result.get("low_gap_pct"))
    ma20_gap = _format_gap(indicators.get("ma20_gap_pct"))
    row_one = []
    if high_gap:
        row_one.append(f"고가 {high_gap}")
    if low_gap:
        row_one.append(f"저가 {low_gap}")
    if ma20_gap:
        row_one.append(f"20일선 {ma20_gap}")
    if row_one:
        first_parts.append(_SPACER.join(row_one))

    bollinger = indicators.get("bollinger_60_2") or {}
    current = float(price_result.get("current_price") or 0)
    row_two = []
    if current > 0 and bollinger:
        for label, key in (("상단", "upper"), ("중심", "middle"), ("하단", "lower")):
            try:
                level = float(bollinger.get(key) or 0)
            except (TypeError, ValueError):
                level = 0
            if level > 0:
                gap = ((current - level) / level) * 100
                row_two.append(f"{label} {_format_gap(gap)}")
    if row_two:
        first_parts.append(_SPACER.join(row_two))

    week_lines = _build_52w_lines(indicators.get("week_52") or {})
    if week_lines:
        if first_parts:
            first_parts.append("")
        first_parts.extend(week_lines)

    return "\n".join(first_parts)


def _previous_trading_day(rows, *, is_krw, as_of_date=None):
    """Locate the last completed exchange-local session and its daily change."""
    today = as_of_date or datetime.now(
        ZoneInfo("Asia/Seoul" if is_krw else "America/New_York")
    ).date()
    completed = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            trading_date = date.fromisoformat(str(row.get("date") or ""))
            high = float(row.get("high") or 0)
            close = float(row.get("close") or 0)
        except (ValueError, TypeError, OverflowError):
            continue
        if trading_date >= today or not (isfinite(high) and isfinite(close) and high > 0 and close > 0):
            continue
        completed[trading_date] = {"high": high, "close": close}

    ordered_dates = sorted(completed)
    if not ordered_dates:
        return None
    last_date = ordered_dates[-1]
    last = completed[last_date]
    previous = {
        "date": last_date.isoformat(),
        "high": last["high"],
        "close": last["close"],
    }
    if len(ordered_dates) >= 2:
        earlier_close = completed[ordered_dates[-2]]["close"]
        if earlier_close > 0:
            previous["change_pct"] = round((last["close"] - earlier_close) / earlier_close * 100, 2)
    return previous


def _build_stock_price_result(*, is_krw, ticker_symbol, current, previous=None, high=None, low=None, change_pct=None, quote_source=None, quote_received_at_ms=None):
    price_result = build_price_result(
        is_krw=is_krw,
        current=current,
        previous=previous,
        high=high,
        low=low,
        change_pct=change_pct,
    )
    daily_rows = fetch_daily_price_history(ticker_symbol)
    indicators = build_price_indicators(
        daily_rows,
        price_result["current_price"],
        day_high=price_result.get("high_price"),
        day_low=price_result.get("low_price"),
    )
    return {
        **price_result,
        "quote_source": quote_source,
        "quote_received_at_ms": quote_received_at_ms,
        "historical_price_source": "yahoo-daily",
        "indicators": indicators,
        "previous_trading_day": _previous_trading_day(daily_rows, is_krw=is_krw),
        "price_tags": list(indicators.get("price_tags") or []),
        "first_reply_metrics_text": _build_first_reply_metrics(price_result, indicators),
    }


def fetch_stock_price_result(*, is_krw, ticker_symbol, clean_code=None):
    """Collect raw price data, calculate indicators, and build the shared price result."""
    if is_krw:
        current, _diff, change_pct, high, low = fetch_kr_stock_quote(clean_code)
        return _build_stock_price_result(
            is_krw=True,
            ticker_symbol=ticker_symbol,
            current=current,
            high=high,
            low=low,
            change_pct=change_pct,
        )

    # Kiwoom's validated, signed US FE tick already reaches Render for the
    # sidebar. Use exactly that same quote for the central analysis and AI.
    # The Yahoo 2-year daily series above is historical indicator input only.
    # If the tick is missing/stale, never mislabel yesterday's close as live.
    quote = read_fresh_us_quote(ticker_symbol)
    return _build_stock_price_result(
        is_krw=False,
        ticker_symbol=ticker_symbol,
        current=quote["price"] if quote else None,
        change_pct=quote.get("change_pct") if quote else None,
        quote_source="kiwoom-direct" if quote else "kiwoom-unavailable",
        quote_received_at_ms=quote.get("received_at_ms") if quote else None,
    )
