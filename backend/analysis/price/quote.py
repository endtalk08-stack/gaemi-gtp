def _positive_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def build_price_result(*, is_krw, current, high=None, low=None, change_pct=None, previous=None):
    """Normalize a provider quote into the price result used by stock analysis."""
    current_price = _positive_float(current)
    high_price = _positive_float(high)
    low_price = _positive_float(low)

    if change_pct is not None:
        try:
            normalized_change_pct = float(change_pct)
        except (TypeError, ValueError):
            normalized_change_pct = 0.0
    else:
        previous_price = _positive_float(previous)
        normalized_change_pct = (
            ((current_price - previous_price) / previous_price) * 100
            if current_price and previous_price
            else 0.0
        )

    if current_price <= 0:
        price_text = "시세 조회 실패"
    elif is_krw:
        price_text = f"{current_price:,.0f}원"
    else:
        price_text = f"${current_price:,.2f}"

    range_lines = []
    if current_price > 0 and high_price > 0:
        high_gap_pct = ((current_price - high_price) / high_price) * 100
        high_text = f"{high_price:,.0f}원" if is_krw else f"${high_price:,.2f}"
        range_lines.append(f"고가   {high_text}   {high_gap_pct:+.2f}% ↘")

    if current_price > 0 and low_price > 0:
        low_gap_pct = ((current_price - low_price) / low_price) * 100
        low_text = f"{low_price:,.0f}원" if is_krw else f"${low_price:,.2f}"
        range_lines.append(f"저가   {low_text}   {low_gap_pct:+.2f}% ↗")

    return {
        "current_price": current_price,
        "change_pct": normalized_change_pct,
        "high_price": high_price,
        "low_price": low_price,
        "price_text": price_text,
        "range_lines": range_lines,
    }
