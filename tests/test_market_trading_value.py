"""Retained US trading-value ranking regression; removed Naver feeds stay absent."""
import json
import unittest
from unittest.mock import patch

from backend.providers import market_price
from backend.services import market_rankings


class MarketTradingValueTests(unittest.TestCase):
    def test_us_value_rows_only(self):
        raw = {"items": [
            {"itemCode": "NVDA.O", "stockName": "NVIDIA",
             "price": {"closePrice": "140.25", "fluctuationsRatio": "1.23",
                       "tradingValue": "1230000000"}},
            {"itemCode": "AAPL.O", "stockName": "Apple", "tradingVolume": 500},
        ]}
        with patch.object(market_rankings, "fetch_us_trading_value_ranking_raw",
                          return_value=raw) as fetch, \
             patch.object(market_rankings, "_with_stock_industries",
                          side_effect=lambda rows, *_: rows):
            rows = market_rankings.build_us_trading_value_result()
        fetch.assert_called_once_with(limit=20)
        self.assertEqual(rows[0]["symbol"], "NVDA.O")
        self.assertEqual(rows[0]["price"], 140.25)
        self.assertEqual(rows[0]["trading_value"], 1230000000.0)
        self.assertIsNone(rows[1]["trading_value"])

    def test_us_value_provider_keeps_cache_and_original_source(self):
        market_price.MARKET_RANKING_CACHE.clear()

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps({"items": []}).encode("utf-8")

        with patch.object(market_price.urllib.request, "urlopen",
                          return_value=Response()) as urlopen:
            self.assertEqual(market_price.fetch_us_trading_value_ranking_raw(), {"items": []})
            self.assertEqual(market_price.fetch_us_trading_value_ranking_raw(), {"items": []})
        urlopen.assert_called_once()
        url = urlopen.call_args.args[0].full_url
        self.assertIn("nationType=USA", url)
        self.assertIn("sortType=tradingValue", url)

    def test_removed_naver_ranking_collectors_are_absent(self):
        for module, names in [
            (market_price, [
                "fetch_kr_stock_quote", "fetch_kr_popular_ranking_raw",
                "fetch_kr_trading_value_ranking_raw", "fetch_us_popular_ranking_raw",
            ]),
            (market_rankings, [
                "build_kr_popular_result", "build_kr_trading_value_result",
                "build_us_popular_result",
            ]),
        ]:
            for name in names:
                with self.subTest(name=name):
                    self.assertFalse(hasattr(module, name))


if __name__ == "__main__":
    unittest.main()
