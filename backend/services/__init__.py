"""Backend service package compatibility hooks."""

# news_feed was simplified to expose get_stock_news(), while engine.py still
# imports the previous fetch_stock_news(stock_name, market, limit) name.
# Keep the existing engine contract intact without changing either data flow.
from . import news_feed as _news_feed

if not hasattr(_news_feed, "fetch_stock_news"):
    def _fetch_stock_news_compat(stock_name, market="국내", limit=3):
        return _news_feed.get_stock_news(stock_name, limit=limit)

    _news_feed.fetch_stock_news = _fetch_stock_news_compat
