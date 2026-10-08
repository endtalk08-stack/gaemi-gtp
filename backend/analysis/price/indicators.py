import math


def _positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _closes(rows):
    out = []
    for row in rows or []:
        value = _positive_float((row or {}).get("close"))
        if value > 0:
            out.append(value)
    return out


def calculate_bollinger_60_2(rows):
    """최근 60일 종가 기준 Bollinger 60, 2."""
    closes = _closes(rows)
    if len(closes) < 60:
        return {}

    window = closes[-60:]
    middle = sum(window) / len(window)
    variance = sum((value - middle) ** 2 for value in window) / len(window)
    deviation = math.sqrt(variance)
    return {
        "upper": middle + (2.0 * deviation),
        "middle": middle,
        "lower": middle - (2.0 * deviation),
    }


def calculate_52w_position(rows, current_price):
    """오늘 봉을 제외한 직전 252거래일 기준 52주 고가/저가 위치."""
    current = _positive_float(current_price)
    source_rows = list(rows or [])
    if current <= 0 or len(source_rows) < 253:
        return {}

    history = source_rows[:-1][-252:]
    highs = [_positive_float((row or {}).get("high")) for row in history]
    lows = [_positive_float((row or {}).get("low")) for row in history]
    highs = [value for value in highs if value > 0]
    lows = [value for value in lows if value > 0]
    if not highs or not lows:
        return {}

    high_52w = max(highs)
    low_52w = min(lows)
    if high_52w <= 0 or low_52w <= 0 or high_52w <= low_52w:
        return {}

    high_gap_pct = ((current - high_52w) / high_52w) * 100
    position = (current - low_52w) / (high_52w - low_52w)
    position = max(0.0, min(1.0, position))

    return {
        "high": high_52w,
        "low": low_52w,
        "high_gap_pct": high_gap_pct,
        "position": position,
        "is_new_high": current > high_52w,
    }


def build_price_indicators(rows, current_price, day_high=None, day_low=None):
    closes = _closes(rows)
    current = _positive_float(current_price)
    high = _positive_float(day_high)
    low = _positive_float(day_low)

    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else 0.0
    bollinger = calculate_bollinger_60_2(rows)
    ma20_gap_pct = (
        ((current - ma20) / ma20) * 100
        if current > 0 and ma20 > 0
        else None
    )

    daily_tag = "#당일중간권"
    if current > 0 and high > low > 0:
        if current >= high:
            daily_tag = "#당일고가권"
        elif current <= low:
            daily_tag = "#당일저가권"
        else:
            day_position = (current - low) / (high - low)
            if day_position >= 0.70:
                daily_tag = "#당일고가권"
            elif day_position <= 0.30:
                daily_tag = "#당일저가권"

    bollinger_tag = "#장기박스구간"
    if bollinger and current > 0:
        upper = _positive_float(bollinger.get("upper"))
        middle = _positive_float(bollinger.get("middle"))
        lower = _positive_float(bollinger.get("lower"))
        if upper > middle > lower > 0:
            if current > upper:
                bollinger_tag = "#장기상승구간"
            elif current < lower:
                bollinger_tag = "#장기하락구간"

    short_term_tag = "#단기중립"
    if current > 0 and ma20 > 0:
        if current > ma20:
            short_term_tag = "#단기상승"
        elif current < ma20:
            short_term_tag = "#단기하락"

    return {
        "bollinger_60_2": bollinger,
        "week_52": calculate_52w_position(rows, current),
        "ma20": ma20,
        "ma20_gap_pct": ma20_gap_pct,
        "price_tags": [daily_tag, short_term_tag, bollinger_tag],
    }
