from ..analysis.price import build_price_result
from ..providers.market_price import fetch_kr_stock_quote, fetch_us_stock_quote


def fetch_stock_price_result(*, is_krw, ticker_symbol, clean_code=None):
    """Collect the raw quote, then normalize it through the shared price analysis."""
    if is_krw:
        current, _diff, change_pct, high, low = fetch_kr_stock_quote(clean_code)
        return build_price_result(
            is_krw=True,
            current=current,
            high=high,
            low=low,
            change_pct=change_pct,
        )

    current, previous, high, low = fetch_us_stock_quote(ticker_symbol)
    return build_price_result(
        is_krw=False,
        current=current,
        previous=previous,
        high=high,
        low=low,
    )
