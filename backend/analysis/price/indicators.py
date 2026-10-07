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


def calculate_rsi_14(rows):
    """14일 Wilder RSI."""
    closes = _closes(rows)
    if len(closes) < 15:
        return None

    gains = []
    losses = []
    for previous, current in zip(closes, closes[1:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    period = 14
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period

    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0

    rs = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + rs))


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
    rsi_14 = calculate_rsi_14(rows)

    daily_tag = "#중간권"
    if current > 0 and high > low > 0:
        if current >= high:
            daily_tag = "#고가갱신"
        elif current <= low:
            daily_tag = "#저가갱신"
        else:
            day_position = (current - low) / (high - low)
            if day_position >= 0.70:
                daily_tag = "#고가권"
            elif day_position <= 0.30:
                daily_tag = "#저가권"

    bollinger_tag = "#박스권"
    if bollinger and current > 0:
        upper = _positive_float(bollinger.get("upper"))
        middle = _positive_float(bollinger.get("middle"))
        lower = _positive_float(bollinger.get("lower"))
        if upper > middle > lower > 0:
            if current > upper:
                bollinger_tag = "#상승우위"
            elif current < lower:
                bollinger_tag = "#하락우위"

    short_term_tag = "#단기중립"
    if current > 0 and ma20 > 0:
        if current > ma20:
            short_term_tag = "#단기상승"
        elif current < ma20:
            short_term_tag = "#단기하락"

    rsi_tag = "#중립"
    if rsi_14 is not None:
        if rsi_14 >= 70:
            rsi_tag = "#과매수구간"
        elif rsi_14 <= 30:
            rsi_tag = "#과매도구간"

    return {
        "rsi_14": rsi_14,
        "bollinger_60_2": bollinger,
        "week_52": calculate_52w_position(rows, current),
        "ma20": ma20,
        "price_tags": [daily_tag, bollinger_tag, short_term_tag, rsi_tag],
    }
