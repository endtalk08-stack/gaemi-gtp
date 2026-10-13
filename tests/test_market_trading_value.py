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

    def test_naver_live_kr_popular_price_object_identity_and_rank(self):
        """Mirrors observed Naver 2026-10-13 KR popularity response fields."""
        raw = {"type": "popular", "items": [
            {"no": "1", "ranking": "1", "itemCode": "005930", "hitCount": "30719",
             "price": {"itemCode": "005930", "itemName": "삼성전자",
                       "krx": {"currentPrice": "234000", "changeRate": "-6.59",
                               "tradingValue": "5916362000000"},
                       "nxt": {"currentPrice": "233500", "changeRate": "-6.79"}}},
            {"no": "2", "ranking": "4", "itemCode": "000660",
             "price": {"itemName": "SK하이닉스",
                       "krx": {"currentPrice": "250000", "changeRate": "+1.25"}}},
        ]}
        with patch.object(market_rankings, "fetch_kr_popular_ranking_raw", return_value=raw):
            items = market_rankings.build_kr_popular_result()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "삼성전자")
        self.assertEqual(items[0]["symbol"], "005930")
        self.assertEqual(items[0]["rank"], 1)
        self.assertEqual(items[0]["price"], 234000)
        self.assertEqual(items[0]["change_pct"], -6.59)
        self.assertEqual(items[1]["rank"], 4)
        self.assertEqual(items[1]["change_pct"], 1.25)

    def test_naver_live_us_popular_price_object_identity_and_rank(self):
        """Mirrors observed Naver USA popular stock response fields."""
        raw = {"type": "popular", "items": [
            {"no": "1", "ranking": "1", "itemCode": "SKHY.O", "hitCount": "10200",
             "price": {"itemCode": "SKHY.O", "itemName": "SK하이닉스 ADR",
                       "itemNameEng": "SK hynix Inc. ADR",
                       "currentPrice": "162.2300", "changeRate": "-4.0230",
                       "sectorName": "반도체", "currencyType": "USD"}},
            {"no": "2", "ranking": "3", "itemCode": "NVDA.O",
             "price": {"itemName": "NVIDIA", "currentPrice": "190.23",
                       "changeRate": "2.5"}},
        ]}
        with patch.object(market_rankings, "fetch_us_popular_ranking_raw", return_value=raw):
            items = market_rankings.build_us_popular_result()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["name"], "SK하이닉스 ADR")
        self.assertEqual(items[0]["symbol"], "SKHY.O")
        self.assertEqual(items[0]["rank"], 1)
        self.assertEqual(items[0]["price"], 162.23)
        self.assertEqual(items[0]["change_pct"], -4.023)
        self.assertEqual(items[1]["rank"], 3)
        self.assertEqual(items[1]["name"], "NVIDIA")

    def test_popular_unavailable_fields_remain_unfabricated(self):
        raw = {"items": [{"itemCode": "000660", "price": {"itemName": "SK하이닉스"}}]}
        with patch.object(market_rankings, "fetch_kr_popular_ranking_raw", return_value=raw):
            items = market_rankings.build_kr_popular_result()
        self.assertEqual(items[0]["name"], "SK하이닉스")
        self.assertIsNone(items[0]["price"])
        self.assertIsNone(items[0]["change_pct"])

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

    def test_failed_market_source_gets_short_cooldown_not_empty_success(self):
        market_price.MARKET_RANKING_CACHE.clear()
        with patch.object(market_price.urllib.request, "urlopen", side_effect=OSError("offline")) as request:
            first = market_price.fetch_kr_trading_value_ranking_raw()
            second = market_price.fetch_kr_trading_value_ranking_raw()
        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertEqual(request.call_count, 1)

    def test_unavailable_source_is_not_reported_as_empty_success(self):
        with patch.object(market_rankings, "fetch_kr_trading_value_ranking_raw", return_value=None):
            self.assertIsNone(market_rankings.build_kr_trading_value_result())


if __name__ == "__main__":
    unittest.main()
