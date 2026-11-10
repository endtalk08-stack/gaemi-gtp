"""Regression: US TOP20 is not fetched from Neon in Render ranking modules."""
import unittest
from backend.providers import market_price
from backend.services import market_rankings


class MarketTradingValueTests(unittest.TestCase):
    def test_no_legacy_render_ranking_collectors(self):
        for module, names in [
            (market_price, [
                "fetch_kr_stock_quote", "fetch_kr_popular_ranking_raw",
                "fetch_kr_trading_value_ranking_raw", "fetch_us_popular_ranking_raw",
                "fetch_us_trading_value_ranking_raw", "MARKET_RANKING_CACHE",
            ]),
            (market_rankings, [
                "build_kr_popular_result", "build_kr_trading_value_result",
                "build_us_popular_result", "build_us_trading_value_result",
                "fetch_us_trading_value_ranking_raw",
            ]),
        ]:
            for name in names:
                with self.subTest(name=name):
                    self.assertFalse(hasattr(module, name))


if __name__ == "__main__":
    unittest.main()
