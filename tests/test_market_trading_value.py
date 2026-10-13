"""KR and USA trading-value source/result regression tests (no live market calls)."""
import json
import unittest
from unittest.mock import patch

from backend.providers import market_price
from backend.services import market_rankings


class MarketTradingValueTests(unittest.TestCase):
    def test_market_raw_request_uses_naver_ranking_not_registered_tickers(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"items": []}).encode("utf-8")

        with patch.object(market_price.urllib.request, "urlopen", return_value=Response()) as open_url:
            raw = market_price.fetch_kr_trading_value_ranking_raw(limit=20)
        self.assertEqual(raw, {"items": []})
        url = open_url.call_args.args[0].full_url
        self.assertIn("/individual-stocks/v3/domestic?", url)
        self.assertIn("listingType=tradingValueDesc", url)
        self.assertIn("size=20", url)
        self.assertEqual(open_url.call_count, 1)

    def test_nested_market_quote_keeps_observed_fields(self):
        raw = {
            "items": [
                {"itemCode": "005930", "stockName": "삼성전자", "price": {
                    "krx": {"closePrice": "85,100", "fluctuationsRatio": "+2.50",
                            "accumulatedTradingValue": "500,000,000,000"}}},
                {"itemCode": "000660", "stockName": "SK하이닉스",
                 "closePrice": "190,000", "fluctuationsRatio": "-1.5",
                 "accumulatedTradingValue": "100,000,000,000"},
            ]
        }
        with patch.object(market_rankings, "fetch_kr_trading_value_ranking_raw", return_value=raw) as source:
            rows = market_rankings.build_kr_trading_value_result(20)
        source.assert_called_once_with(limit=20)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "005930")
        self.assertEqual(rows[0]["price"], 85100.0)
        self.assertEqual(rows[0]["change_pct"], 2.5)
        self.assertEqual(rows[0]["trading_value"], 500000000000.0)
        self.assertEqual(rows[1]["rank"], 2)
        self.assertEqual(rows[1]["change_pct"], -1.5)

    def test_absent_source_values_do_not_become_fake_numbers(self):
        raw = {"items": [{"itemCode": "005930", "stockName": "삼성전자"}]}
        with patch.object(market_rankings, "fetch_kr_trading_value_ranking_raw", return_value=raw):
            rows = market_rankings.build_kr_trading_value_result()
        self.assertIsNone(rows[0]["price"])
        self.assertIsNone(rows[0]["change_pct"])
        self.assertIsNone(rows[0]["trading_value"])

    def test_us_trading_value_normalizes_usd_without_estimates(self):
        raw = {"items": [
            {"itemCode": "NVDA.O", "stockName": "NVIDIA",
             "price": "140.25", "fluctuationsRatio": "1.23",
             "tradingValue": "1230000000"},
            {"itemCode": "AAPL.O", "stockName": "Apple", "tradingVolume": 500},
        ]}
        with patch.object(market_rankings, "fetch_us_trading_value_ranking_raw", return_value=raw):
            rows = market_rankings.build_us_trading_value_result()
        self.assertEqual(rows[0]["symbol"], "NVDA.O")
        self.assertEqual(rows[0]["price"], 140.25)
        self.assertEqual(rows[0]["trading_value"], 1230000000)
        self.assertIsNone(rows[1]["trading_value"])

    def test_us_trading_value_uses_cached_market_ranking(self):
        market_price.MARKET_RANKING_CACHE.clear()

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps({"items": []}).encode("utf-8")

        with patch.object(market_price.urllib.request, "urlopen", return_value=Response()) as urlopen:
            one = market_price.fetch_us_trading_value_ranking_raw()
            two = market_price.fetch_us_trading_value_ranking_raw()
        self.assertEqual(one, two)
        self.assertEqual(urlopen.call_count, 1)
        url = urlopen.call_args.args[0].full_url
        self.assertIn("sortType=tradingValue", url)
        self.assertIn("nationType=USA", url)
        self.assertIn("includeOverMarket=true", url)

    def test_popular_ranking_reuses_kr_and_us_stock_normalization(self):
        kr = {"items": [{"itemCode": "005930", "stockName": "삼성전자",
                         "price": {"krx": {"closePrice": "85100", "fluctuationsRatio": "2.5"}}}]}
        us = {"items": [{"itemCode": "NVDA.O", "stockName": "NVIDIA",
                         "price": {"closePrice": "144.23", "changeRate": "1.2"}}]}
        with patch.object(market_rankings, "fetch_kr_popular_ranking_raw", return_value=kr):
            ko = market_rankings.build_kr_popular_result()
        with patch.object(market_rankings, "fetch_us_popular_ranking_raw", return_value=us):
            en = market_rankings.build_us_popular_result()
        self.assertEqual(ko[0]["name"], "삼성전자")
        self.assertEqual(ko[0]["price"], 85100)
        self.assertEqual(en[0]["symbol"], "NVDA.O")
        self.assertEqual(en[0]["change_pct"], 1.2)

    def test_popularity_is_cached_separately_from_turnover(self):
        market_price.MARKET_RANKING_CACHE.clear()
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps({"items": []}).encode("utf-8")
        with patch.object(market_price.urllib.request, "urlopen", return_value=Response()) as req:
            market_price.fetch_kr_popular_ranking_raw()
            market_price.fetch_kr_popular_ranking_raw()
            market_price.fetch_us_popular_ranking_raw()
            market_price.fetch_us_popular_ranking_raw()
        self.assertEqual(req.call_count, 2)

    def test_industry_rows_are_categories_not_stocks(self):
        kr = {"items": [{"industryName": "반도체", "industryCode": "13", "changeRate": "2.1"}]}
        us = {"items": [{"sectorName": "Technology", "sectorCode": "45", "changeRate": "-0.3"}]}
        with patch.object(market_rankings, "fetch_kr_industry_ranking_raw", return_value=kr):
            korean = market_rankings.build_kr_industry_result()
        with patch.object(market_rankings, "fetch_us_industry_ranking_raw", return_value=us):
            american = market_rankings.build_us_industry_result()
        self.assertEqual(korean[0]["name"], "반도체")
        self.assertEqual(korean[0]["sector_code"], "13")
        self.assertIsNone(korean[0]["symbol"])
        self.assertEqual(american[0]["change_pct"], -0.3)
        self.assertIsNone(american[0]["trading_value"])

    def test_kr_us_industry_requests_are_independent_and_cached(self):
        market_price.MARKET_RANKING_CACHE.clear()
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps({"items": []}).encode("utf-8")
        with patch.object(market_price.urllib.request, "urlopen", return_value=Response()) as req:
            market_price.fetch_kr_industry_ranking_raw()
            market_price.fetch_kr_industry_ranking_raw()
            market_price.fetch_us_industry_ranking_raw()
            market_price.fetch_us_industry_ranking_raw()
        self.assertEqual(req.call_count, 2)

    def test_unavailable_source_is_not_reported_as_empty_success(self):
        with patch.object(market_rankings, "fetch_kr_trading_value_ranking_raw", return_value=None):
            self.assertIsNone(market_rankings.build_kr_trading_value_result())


if __name__ == "__main__":
    unittest.main()
