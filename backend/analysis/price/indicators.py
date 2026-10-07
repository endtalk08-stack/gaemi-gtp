import math


def _positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) and number > 0 else 0.0


def _calculate_rsi_14(closes):
    if not closes or len(closes) < 15:
        return None

    window = closes[-15:]
    gains = []
    losses = []
    for previous, current in zip(window, window[1:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def build_price_indicators(price_result, daily_rows):
    """현재가 결과와 공통 일봉 원천으로 첫 답변 가격 지표를 만든다."""
    current_price = _positive_float((price_result or {}).get("current_price"))
    day_high = _positive_float((price_result or {}).get("high_price"))
    day_low = _positive_float((price_result or {}).get("low_price"))

    closes = []
    for row in daily_rows or []:
        close = _positive_float(row.get("close") if isinstance(row, dict) else None)
        if close > 0:
            closes.append(close)

    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else 0.0
    ma20_gap_pct = (
        ((current_price - ma20) / ma20) * 100
        if current_price > 0 and ma20 > 0
        else None
    )

    bollinger_60_2 = None
    if len(closes) >= 60:
        window = closes[-60:]
        middle = sum(window) / 60
        variance = sum((price - middle) ** 2 for price in window) / 60
        stddev = math.sqrt(variance)
        bollinger_60_2 = {
            "upper": middle + 2 * stddev,
            "middle": middle,
            "lower": middle - 2 * stddev,
        }

    rsi_14 = _calculate_rsi_14(closes)

    daily_tag = "#중간권"
    if current_price > 0 and day_high > day_low > 0:
        if current_price >= day_high:
            daily_tag = "#고가갱신"
        elif current_price <= day_low:
            daily_tag = "#저가갱신"
        else:
            day_position = (current_price - day_low) / (day_high - day_low)
            if day_position >= 0.70:
                daily_tag = "#고가권"
            elif day_position <= 0.30:
                daily_tag = "#저가권"

    bollinger_tag = "#박스권"
    if bollinger_60_2 and current_price > 0:
        upper = float(bollinger_60_2.get("upper") or 0)
        middle = float(bollinger_60_2.get("middle") or 0)
        lower = float(bollinger_60_2.get("lower") or 0)
        if upper > middle > lower > 0:
            if current_price > upper:
                bollinger_tag = "#상승우위"
            elif current_price < lower:
                bollinger_tag = "#하락우위"

    short_term_tag = "#단기중립"
    if current_price > 0 and ma20 > 0:
        if current_price > ma20:
            short_term_tag = "#단기상승"
        elif current_price < ma20:
            short_term_tag = "#단기하락"

    rsi_tag = "#중립"
    if rsi_14 is not None:
        if rsi_14 >= 70:
            rsi_tag = "#과매수구간"
        elif rsi_14 <= 30:
            rsi_tag = "#과매도구간"

    return {
        "ma20": ma20,
        "ma20_gap_pct": ma20_gap_pct,
        "bollinger_60_2": bollinger_60_2,
        "rsi_14": rsi_14,
        "price_tags": [daily_tag, bollinger_tag, short_term_tag, rsi_tag],
    }
